"""Synchronize IM Agent configuration into live Gateway ownership."""

from __future__ import annotations

import json
from hashlib import sha256
import logging
import os
import stat
import time
import threading
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from pathlib import Path

import httpx

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    LocalConfig,
    RuntimeConfigOwner,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
    default_local_config_path,
    enabled_feishu_agent_ids,
    ensure_workspace_defaults,
    save_sensitive_local_config,
)
from personal_assistant.config.model_reasoning import ModelReasoningCatalog
from personal_assistant.config.skill_selection import (
    DEFAULT_DISCOVERY,
    EXPLICIT_ALLOWLIST,
    VALID_SELECTION_MODES,
    effective_skills_selection_mode,
)
from personal_assistant.builtin_skills.lark_bundle import lark_skill_names
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.config_apply_receipts import (
    ConfigApplyReceiptStore,
    ConfigOperationReceipt,
    OperationIdReusedError,
)
from personal_assistant.gateway.im_http_transport import (
    build_im_http_headers,
    normalize_im_http_base_url,
)
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.workspace_authority import resolve_runtime_workspace
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

# Preserve the extracted owner's injectable persistence seam while making its
# production default safe for feat-464's secret-bearing channel configuration.
save_local_config = save_sensitive_local_config

_log = logging.getLogger(__name__)
_PA_GLOBAL_SKILL_ROOT = Path("~/.nanoassistant/skills")
BootstrapClientFactory = Callable[[str], httpx.Client]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]
OperationPhaseHook = Callable[[str], None]


def _selection_mode(value: object) -> str | None:
    mode = value.strip() if isinstance(value, str) else None
    if mode is not None and mode not in VALID_SELECTION_MODES:
        raise ValueError("invalid skills_selection_mode")
    return mode


class _WorkspaceOperationRejected(ValueError):
    """Carry a user-actionable workspace rejection through the operation protocol."""

    def __init__(self, error: Mapping[str, object]) -> None:
        code = error.get("code")
        detail = error.get("detail")
        self.code = code if isinstance(code, str) else "invalid_agent_config"
        self.detail = detail if isinstance(detail, str) else self.code
        raw_agent_id = error.get("agent_id")
        self.agent_id = raw_agent_id if isinstance(raw_agent_id, str) else None
        super().__init__(self.detail)


def _canonical_heartbeat_json(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("heartbeat_json must encode an object")
    return json.dumps(parsed, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonical_agent_operation_payload(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Return the stable non-secret Agent config projection used for fingerprints."""

    agent_id = str(payload.get("agent_id") or "").strip()
    display_name = str(payload.get("display_name") or agent_id).strip()
    raw_skills = payload.get("skills")
    raw_tools = payload.get("tool_allowlist")
    raw_features = payload.get("features")
    workspace_root = payload.get("workspace_root")
    return {
        "agent_id": agent_id,
        "display_name": display_name,
        "skills": list(_operation_string_tuple(raw_skills))
        if isinstance(raw_skills, list)
        else None,
        "skills_selection_mode": _selection_mode(payload.get("skills_selection_mode")),
        "tool_allowlist": list(_operation_string_tuple(raw_tools)),
        "group_reply_policy": _optional_operation_text(
            payload.get("group_reply_policy")
        )
        or "manual",
        "default_model": _optional_operation_text(payload.get("default_model")),
        "reasoning_effort": _optional_operation_text(payload.get("reasoning_effort")),
        "workspace_root": workspace_root.strip()
        if isinstance(workspace_root, str) and workspace_root.strip()
        else None,
        "features": {
            key: value
            for key, value in raw_features.items()
            if isinstance(key, str) and isinstance(value, bool)
        }
        if isinstance(raw_features, Mapping)
        else {},
        "custom_prompt": _optional_operation_text(payload.get("custom_prompt")),
        "heartbeat_json": _canonical_heartbeat_json(payload.get("heartbeat_json")),
    }


def agent_operation_fingerprint(payload: Mapping[str, object]) -> str:
    """Fingerprint one canonical Gateway-owned Agent configuration."""

    canonical = canonical_agent_operation_payload(payload)
    encoded = json.dumps(
        canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return sha256(encoded.encode()).hexdigest()


def _default_pa_global_skill_names() -> tuple[str, ...]:
    """Resolve the PA global user skills that new IM-created agents inherit."""

    root = _PA_GLOBAL_SKILL_ROOT.expanduser().resolve()
    if not root.is_dir():
        return ()
    try:
        names: set[str] = set()
        for skill_file in sorted(root.rglob("SKILL.md")):
            if ".archive" in skill_file.parts:
                continue
            names.add(_read_skill_name(skill_file))
        return tuple(sorted(names))
    except Exception:  # noqa: BLE001
        _log.warning(
            "failed to resolve PA global skill defaults from %s", root, exc_info=True
        )
        return ()


def _read_skill_name(skill_file: Path) -> str:
    """Return the skill's declared name, falling back to its directory name."""

    for line in skill_file.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped == "---" or not stripped:
            continue
        if stripped.startswith("name:"):
            return (
                stripped.split(":", 1)[1].strip().strip("\"'") or skill_file.parent.name
            )
        if not stripped.startswith("#"):
            break
    return skill_file.parent.name


class IMAgentConfigSync:
    """Fetch IM agent config snapshots and extend the live gateway agent registry."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        agent_catalog: LiveAgentCatalog,
        session_binder: GatewaySessionBinder,
        local_config: LocalConfig,
        config_owner: RuntimeConfigOwner | None = None,
        workspace_root_factory: Callable[[str], Path] | None = None,
        reporter: UpstreamReporter | None = None,
        client: httpx.Client | None = None,
        client_factory: BootstrapClientFactory | None = None,
        global_skill_root: Path | None = None,
        timeout_seconds: float = 5.0,
        retry_interval_seconds: float = 0.1,
        max_attempts: int = 50,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleep = time.sleep,
        token_getter: Callable[[], Awaitable[str | None]] | None = None,
        on_agent_created: Callable[[str, Path], None] | None = None,
        reasoning_catalog: ModelReasoningCatalog | None = None,
        operation_receipts: ConfigApplyReceiptStore | None = None,
        operation_phase_hook: OperationPhaseHook | None = None,
    ) -> None:
        self._base_url = normalize_im_http_base_url(base_url)
        self._base_headers = build_im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._max_attempts = max(max_attempts, 1)
        self._agent_catalog = agent_catalog
        self._session_binder = session_binder
        self._config_owner = config_owner or RuntimeConfigOwner(local_config)
        self._workspace_root_factory = (
            workspace_root_factory or self._default_workspace_root
        )
        self._on_agent_created = on_agent_created
        self._reporter = reporter
        self._client_factory = client_factory
        self._client = client
        self._global_skill_root = (
            global_skill_root.expanduser().resolve()
            if global_skill_root is not None
            else None
        )
        self._monotonic = monotonic
        self._sleep = sleep
        self._agent_create_lock = threading.Lock()
        # feat-394-M3 fix: accept token_getter so auto-bind token refresh propagates
        # to config sync requests. Without this, sync_agent calls 401 after auto-bind
        # because the initial token is empty and is never updated. Mirrors the pattern
        # used by _IMBootstrapClient (main.py:599-613).
        self._token_getter = token_getter
        self._reasoning_catalog = reasoning_catalog or ModelReasoningCatalog(
            local_config.llm
        )
        self._operation_receipts = operation_receipts or ConfigApplyReceiptStore(
            local_config.source_path.parent / "config-apply-receipts-v1.json"
        )
        self._operation_phase_hook = operation_phase_hook
        self._operation_lock = threading.RLock()

    def sync_agent(self, *, agent_id: str, profile_version: int) -> None:
        deadline = self._monotonic() + self._timeout_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                payload = self._fetch_agent_config(agent_id=agent_id)
                resolved_profile_version = int(payload.get("profile_version", 0))
                if resolved_profile_version < profile_version:
                    raise RuntimeError(
                        f"agent {agent_id} config stale: expected >= {profile_version}, got {resolved_profile_version}"
                    )
                payload = self._ensure_static_feishu_bundle(
                    agent_id=agent_id,
                    payload=payload,
                )
                self._publish_agent_config(
                    self._decode_mirror_agent_config(
                        payload=payload,
                        agent_id=agent_id,
                    )
                )
                return
            except (httpx.HTTPError, RuntimeError, ValueError):
                if attempt >= self._max_attempts or self._monotonic() >= deadline:
                    raise
                self._sleep(self._retry_interval_seconds)

    def handle_agent_create(
        self, agent_payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Create one local workspace or return a structured recoverable rejection."""
        with self._agent_create_lock:
            return self._handle_agent_create(agent_payload)

    def _handle_agent_create(
        self, agent_payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Execute one serialized Agent create check-and-publish operation."""
        agent_id_raw = agent_payload.get("agent_id")
        if not isinstance(agent_id_raw, str) or not agent_id_raw.strip():
            raise ValueError("agent.create requires non-empty agent_id")
        agent_id = agent_id_raw.strip()
        create_operation_raw = agent_payload.get("create_operation_id")
        create_operation_id = (
            create_operation_raw.strip()
            if isinstance(create_operation_raw, str) and create_operation_raw.strip()
            else None
        )
        ws_raw = agent_payload.get("workspace_root")
        workspace_is_default = not (isinstance(ws_raw, str) and ws_raw.strip())
        if isinstance(ws_raw, str) and ws_raw.strip():
            workspace_root = Path(ws_raw.strip()).expanduser()
            if not workspace_root.is_absolute():
                return self._workspace_rejection(
                    code="workspace_parent_unusable",
                    detail="Workspace root must be an absolute path or start with ~/.",
                )
            workspace_root = workspace_root.resolve()
        else:
            workspace_root = (
                self._workspace_root_factory(agent_id).expanduser().resolve()
            )

        existing_agent = self._local_agent(agent_id)
        if existing_agent is not None:
            if (
                existing_agent.workspace_root.expanduser().resolve() == workspace_root
                and existing_agent.workspace_is_default == workspace_is_default
                and create_operation_id is not None
                and existing_agent.create_operation_id == create_operation_id
            ):
                description = agent_payload.get("description")
                return self._agent_create_payload(
                    existing_agent,
                    description=(
                        description.strip() if isinstance(description, str) else ""
                    ),
                )
            return self._workspace_rejection(
                code="agent_id_already_exists",
                detail="Agent ID already exists on this node.",
            )

        assigned_agent_id = self._assigned_agent_for_workspace(workspace_root)
        if assigned_agent_id is not None:
            return self._workspace_rejection(
                code="workspace_already_assigned",
                detail="Workspace is already assigned to another Agent.",
                agent_id=assigned_agent_id,
            )

        dm = agent_payload.get("default_model")
        default_model = dm.strip() if isinstance(dm, str) and dm.strip() else None
        effort = agent_payload.get("reasoning_effort")
        reasoning_effort = (
            effort.strip() if isinstance(effort, str) and effort.strip() else None
        )
        # Validate the candidate before any workspace setup can mutate its path.
        self._reasoning_catalog.validate(default_model, reasoning_effort)

        if workspace_is_default:
            try:
                workspace_root = ensure_workspace_defaults(workspace_root)
            except OSError:
                return self._workspace_rejection(
                    code="workspace_initialization_failed",
                    detail="Workspace could not be initialized on the selected node.",
                )
        else:
            rejection = self._prepare_custom_workspace(
                workspace_root,
                confirm_existing=agent_payload.get("confirm_existing_workspace")
                is True,
            )
            if rejection is not None:
                return rejection
            try:
                workspace_root = ensure_workspace_defaults(workspace_root)
            except OSError:
                return self._workspace_rejection(
                    code="workspace_initialization_failed",
                    detail="Workspace could not be initialized on the selected node.",
                )
        display = agent_payload.get("display_name")
        title = (
            display.strip()
            if isinstance(display, str) and display.strip()
            else agent_id
        )
        desc_val = agent_payload.get("description")
        description_str = desc_val.strip() if isinstance(desc_val, str) else ""
        raw_skills = agent_payload.get("skills")
        skills = tuple(
            item.strip()
            for item in (raw_skills if isinstance(raw_skills, list) else [])
            if isinstance(item, str) and item.strip()
        )
        if "skills" not in agent_payload:
            skills = _default_pa_global_skill_names()
        skills_selection_mode = _selection_mode(
            agent_payload.get("skills_selection_mode")
        )
        raw_tools = agent_payload.get("tool_allowlist")
        tool_allowlist = tuple(
            item.strip()
            for item in (raw_tools if isinstance(raw_tools, list) else [])
            if isinstance(item, str) and item.strip()
        )
        grp = agent_payload.get("group_reply_policy")
        group_reply_policy = (
            grp.strip() if isinstance(grp, str) and grp.strip() else "MENTION"
        )
        # feat-379-M2: per-agent features and custom_prompt from IM push payload
        raw_features = agent_payload.get("features")
        features = (
            {
                k: v
                for k, v in raw_features.items()
                if isinstance(k, str) and isinstance(v, bool)
            }
            if isinstance(raw_features, dict)
            else {}
        )
        cp_val = agent_payload.get("custom_prompt")
        custom_prompt = (
            cp_val.strip() if isinstance(cp_val, str) and cp_val.strip() else None
        )
        agent_config = AgentWorkspaceConfig(
            agent_id=agent_id,
            workspace_root=workspace_root,
            workspace_is_default=workspace_is_default,
            create_operation_id=create_operation_id,
            title=title,
            skills=skills,
            skills_selection_mode=skills_selection_mode,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features=features,
            custom_prompt=custom_prompt,
        )
        self._publish_agent_config(agent_config)
        if self._reporter is not None:
            self._reporter.replace_agents(tuple(self._config_snapshot().agents))
        if self._on_agent_created is not None:
            try:
                self._on_agent_created(agent_id, workspace_root)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "on_agent_created callback failed for agent=%s; "
                    "cron execution service may not be registered",
                    agent_id,
                )
        return self._agent_create_payload(agent_config, description=description_str)

    @staticmethod
    def _agent_create_payload(
        agent: AgentWorkspaceConfig, *, description: str
    ) -> dict[str, object]:
        """Serialize the stable creation success payload for a local Agent config."""
        payload: dict[str, object] = {
            "agent_id": agent.agent_id,
            "display_name": agent.title or agent.agent_id,
            "description": description,
            "skills": list(agent.skills),
            "skills_selection_mode": effective_skills_selection_mode(
                agent.skills_selection_mode, agent.skills
            ),
            "tool_allowlist": list(agent.tool_allowlist),
            "group_reply_policy": agent.group_reply_policy or "MENTION",
            "default_model": agent.default_model,
            "reasoning_effort": agent.reasoning_effort,
            "workspace_root": str(agent.workspace_root),
            "workspace_is_default": agent.workspace_is_default,
            "features": dict(agent.features),
            "custom_prompt": agent.custom_prompt,
        }
        if agent.create_operation_id is not None:
            payload["create_operation_id"] = agent.create_operation_id
        return payload

    def handle_agent_config_operation(
        self, kind: str, payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Apply or recover one write-ahead Agent configuration operation.

        Args:
            kind: ``create`` or ``apply``.
            payload: Gateway RPC payload containing operation identity and candidate.

        Returns:
            Canonical applied/rejected/pending operation result.
        """

        if kind not in {"create", "apply"}:
            raise ValueError("config operation kind must be create or apply")
        operation_id = _required_operation_text(payload, "operation_id")
        candidate_fingerprint = _required_operation_text(
            payload, "candidate_fingerprint"
        )
        expected_raw = payload.get("expected_previous_fingerprint")
        expected_previous = (
            expected_raw.strip()
            if isinstance(expected_raw, str) and expected_raw.strip()
            else None
        )
        if kind == "apply" and expected_previous is None:
            return _operation_rejection(
                operation_id,
                candidate_fingerprint,
                "invalid_agent_config",
                "apply requires expected_previous_fingerprint",
            )
        if kind == "create" and expected_previous is not None:
            return _operation_rejection(
                operation_id,
                candidate_fingerprint,
                "invalid_agent_config",
                "create expected_previous_fingerprint must be null",
            )
        raw_candidate = payload.get("agent")
        if not isinstance(raw_candidate, Mapping):
            return _operation_rejection(
                operation_id,
                candidate_fingerprint,
                "invalid_agent_config",
                "agent candidate is required",
            )
        try:
            canonical_request = canonical_agent_operation_payload(raw_candidate)
            actual_fingerprint = agent_operation_fingerprint(canonical_request)
        except (TypeError, ValueError) as exc:
            return _operation_rejection(
                operation_id,
                candidate_fingerprint,
                "invalid_agent_config",
                str(exc),
            )
        if actual_fingerprint != candidate_fingerprint:
            return _operation_rejection(
                operation_id,
                candidate_fingerprint,
                "invalid_agent_config",
                "candidate_fingerprint does not match agent candidate",
            )
        if kind == "create":
            canonical_request["create_operation_id"] = operation_id

        with self._operation_lock:
            try:
                existing_receipt = self._operation_receipts.get(operation_id)
                if existing_receipt is None:
                    # Validate deterministic candidate fields before workspace
                    # setup can create or initialize a custom directory.
                    try:
                        self._reasoning_catalog.validate(
                            _optional_operation_text(
                                canonical_request.get("default_model")
                            ),
                            _optional_operation_text(
                                canonical_request.get("reasoning_effort")
                            ),
                        )
                    except ValueError as exc:
                        receipt = self._operation_receipts.prepare(
                            operation_id=operation_id,
                            kind=kind,
                            candidate_fingerprint=candidate_fingerprint,
                            expected_previous_fingerprint=expected_previous,
                            candidate=canonical_request,
                            desired_state_fingerprint=agent_operation_fingerprint(
                                canonical_request
                            ),
                        )
                        return _receipt_result(
                            self._operation_receipts.finish(
                                receipt.operation_id,
                                status="rejected",
                                error_code="invalid_agent_config",
                                message=str(exc),
                            )
                        )
                    candidate = self._resolve_operation_workspace(
                        kind=kind,
                        candidate=canonical_request,
                        confirm_existing=raw_candidate.get("confirm_existing_workspace")
                        is True,
                    )
                else:
                    candidate = dict(existing_receipt.candidate)
                receipt = self._operation_receipts.prepare(
                    operation_id=operation_id,
                    kind=kind,
                    candidate_fingerprint=candidate_fingerprint,
                    expected_previous_fingerprint=expected_previous,
                    candidate=candidate,
                    desired_state_fingerprint=agent_operation_fingerprint(candidate),
                )
            except OperationIdReusedError as exc:
                return _operation_rejection(
                    operation_id,
                    candidate_fingerprint,
                    "operation_id_reused",
                    str(exc),
                )
            except _WorkspaceOperationRejected as exc:
                return _operation_rejection(
                    operation_id,
                    candidate_fingerprint,
                    exc.code,
                    exc.detail,
                    agent_id=exc.agent_id,
                )
            except ValueError as exc:
                return _operation_rejection(
                    operation_id,
                    candidate_fingerprint,
                    "invalid_agent_config",
                    str(exc),
                )
            if receipt.status != "prepared":
                return _receipt_result(receipt)
            self._notify_operation_phase("prepared")
            return self._resume_config_operation(receipt)

    def config_operation_status(
        self, payload: Mapping[str, object]
    ) -> dict[str, object]:
        """Return or recover one durable config-operation result."""

        operation_id = _required_operation_text(payload, "operation_id")
        with self._operation_lock:
            receipt = self._operation_receipts.get(operation_id)
            if receipt is None:
                return {
                    "operation_id": operation_id,
                    "status": "pending",
                }
            if receipt.status == "prepared":
                return self._resume_config_operation(receipt)
            return _receipt_result(receipt)

    def _resolve_operation_workspace(
        self,
        *,
        kind: str,
        candidate: Mapping[str, object],
        confirm_existing: bool,
    ) -> dict[str, object]:
        agent_id = str(candidate.get("agent_id") or "").strip()
        if not agent_id:
            raise ValueError("agent candidate requires non-empty agent_id")
        existing = self._local_agent(agent_id)
        raw_workspace = candidate.get("workspace_root")
        workspace_is_default = not (
            isinstance(raw_workspace, str) and raw_workspace.strip()
        )
        if kind == "create":
            if isinstance(raw_workspace, str) and raw_workspace.strip():
                workspace_root = Path(raw_workspace).expanduser()
                if not workspace_root.is_absolute():
                    raise _WorkspaceOperationRejected(
                        {
                            "code": "workspace_parent_unusable",
                            "detail": "Workspace root must be an absolute path or start with ~/.",
                        }
                    )
                workspace_root = workspace_root.resolve()
            else:
                workspace_root = self._workspace_root_factory(agent_id).resolve()
            if existing is not None:
                operation_id = candidate.get("create_operation_id")
                if (
                    isinstance(operation_id, str)
                    and operation_id == existing.create_operation_id
                    and workspace_root == existing.workspace_root.resolve()
                    and workspace_is_default == existing.workspace_is_default
                    and str(candidate.get("display_name") or agent_id)
                    == (existing.title or agent_id)
                ):
                    resolved = _agent_operation_payload(existing)
                    resolved["workspace_root"] = str(workspace_root)
                    resolved["workspace_is_default"] = workspace_is_default
                    resolved["create_operation_id"] = operation_id
                    resolved["confirm_existing_workspace"] = confirm_existing
                    return resolved
                raise _WorkspaceOperationRejected(
                    {
                        "code": "agent_id_already_exists",
                        "detail": "Agent ID already exists on this node.",
                        "agent_id": agent_id,
                    }
                )
            assigned_agent_id = self._assigned_agent_for_workspace(workspace_root)
            if assigned_agent_id is not None:
                raise _WorkspaceOperationRejected(
                    {
                        "code": "workspace_already_assigned",
                        "detail": "Workspace is already assigned to another Agent.",
                        "agent_id": assigned_agent_id,
                    }
                )
            if workspace_is_default:
                try:
                    workspace_root = ensure_workspace_defaults(workspace_root)
                except OSError as exc:
                    raise _WorkspaceOperationRejected(
                        {
                            "code": "workspace_initialization_failed",
                            "detail": "Workspace could not be initialized on the selected node.",
                        }
                    ) from exc
            else:
                rejection = self._prepare_custom_workspace(
                    workspace_root, confirm_existing=confirm_existing
                )
                if rejection is not None:
                    error = rejection.get("error")
                    if isinstance(error, Mapping):
                        raise _WorkspaceOperationRejected(error)
                    raise ValueError("workspace setup rejected")
                try:
                    workspace_root = ensure_workspace_defaults(workspace_root)
                except OSError as exc:
                    raise _WorkspaceOperationRejected(
                        {
                            "code": "workspace_initialization_failed",
                            "detail": "Workspace could not be initialized on the selected node.",
                        }
                    ) from exc
        else:
            if existing is None:
                raise ValueError(f"agent {agent_id!r} does not exist")
            workspace_root = existing.workspace_root.resolve()
            workspace_is_default = existing.workspace_is_default
            if (
                isinstance(raw_workspace, str)
                and raw_workspace.strip()
                and Path(raw_workspace).expanduser().resolve() != workspace_root
            ):
                raise ValueError("workspace_root does not match Gateway local config")
        resolved = dict(candidate)
        resolved["workspace_root"] = str(workspace_root)
        resolved["workspace_is_default"] = workspace_is_default
        resolved["confirm_existing_workspace"] = confirm_existing
        if candidate.get("skills") is None:
            if kind == "apply":
                raise ValueError("apply agent candidate requires skills")
            resolved["skills"] = list(_default_pa_global_skill_names())
        return resolved

    def _resume_config_operation(
        self, receipt: ConfigOperationReceipt
    ) -> dict[str, object]:
        if receipt.status != "prepared":
            return _receipt_result(receipt)
        try:
            candidate_config = self._decode_operation_agent(receipt.candidate)
            self._reasoning_catalog.validate(
                candidate_config.default_model, candidate_config.reasoning_effort
            )
        except ValueError as exc:
            return _receipt_result(
                self._operation_receipts.finish(
                    receipt.operation_id,
                    status="rejected",
                    error_code="invalid_agent_config",
                    message=str(exc),
                )
            )

        self._notify_operation_phase("workspace_initialized")
        conflict = False

        def update(current: LocalConfig) -> LocalConfig:
            nonlocal conflict
            agents = list(current.agents)
            index = next(
                (
                    item_index
                    for item_index, agent in enumerate(agents)
                    if agent.agent_id == candidate_config.agent_id
                ),
                None,
            )
            existing = agents[index] if index is not None else None
            existing_fingerprint = (
                agent_operation_fingerprint(_agent_operation_payload(existing))
                if existing is not None
                else None
            )
            if existing_fingerprint == receipt.desired_state_fingerprint:
                return current
            if existing_fingerprint != receipt.expected_previous_fingerprint:
                conflict = True
                return current
            if index is None:
                agents.append(candidate_config)
            else:
                agents[index] = candidate_config
            return replace(current, agents=tuple(agents))

        self._config_owner.persist(update, save_config=save_local_config)
        if conflict:
            return _receipt_result(
                self._operation_receipts.finish(
                    receipt.operation_id,
                    status="rejected",
                    error_code="operation_conflict",
                    message="Gateway Agent config no longer matches expected previous state",
                )
            )
        self._notify_operation_phase("config_persisted")
        live = self._agent_catalog.get(candidate_config.agent_id)
        published = live is None or live.config != candidate_config
        if published:
            self._agent_catalog.publish(candidate_config)
        if self._reporter is not None:
            self._reporter.replace_agents(tuple(self._config_snapshot().agents))
        if (
            published
            and receipt.kind == "create"
            and self._on_agent_created is not None
        ):
            self._on_agent_created(
                candidate_config.agent_id, candidate_config.workspace_root
            )
        self._notify_operation_phase("published")
        terminal = self._operation_receipts.finish(
            receipt.operation_id, status="applied"
        )
        return _receipt_result(terminal)

    def _decode_operation_agent(
        self, payload: Mapping[str, object]
    ) -> AgentWorkspaceConfig:
        agent_id = str(payload.get("agent_id") or "").strip()
        workspace_text = str(payload.get("workspace_root") or "").strip()
        if not agent_id or not workspace_text:
            raise ValueError("operation candidate requires agent_id and workspace_root")
        raw_features = payload.get("features")
        heartbeat_raw = payload.get("heartbeat_json")
        heartbeat_payload = json.loads(heartbeat_raw) if heartbeat_raw else None
        heartbeat_every, hb_start, hb_end, hb_timezone = (
            _parse_heartbeat_from_im_payload(heartbeat_payload)
        )
        default_model = _optional_operation_text(payload.get("default_model"))
        reasoning_effort = _optional_operation_text(payload.get("reasoning_effort"))
        self._reasoning_catalog.validate(default_model, reasoning_effort)
        return AgentWorkspaceConfig(
            agent_id=agent_id,
            workspace_root=Path(workspace_text).expanduser().resolve(),
            workspace_is_default=(
                payload.get("workspace_is_default")
                if isinstance(payload.get("workspace_is_default"), bool)
                else True
            ),
            create_operation_id=_optional_operation_text(
                payload.get("create_operation_id")
            ),
            title=str(payload.get("display_name") or agent_id),
            skills=_operation_string_tuple(payload.get("skills")),
            skills_selection_mode=_selection_mode(payload.get("skills_selection_mode")),
            tool_allowlist=_operation_string_tuple(payload.get("tool_allowlist")),
            group_reply_policy=_optional_operation_text(
                payload.get("group_reply_policy")
            ),
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features={
                key: value
                for key, value in raw_features.items()
                if isinstance(key, str) and isinstance(value, bool)
            }
            if isinstance(raw_features, Mapping)
            else {},
            custom_prompt=_optional_operation_text(payload.get("custom_prompt")),
            heartbeat_every=heartbeat_every,
            heartbeat_active_hours_start=hb_start,
            heartbeat_active_hours_end=hb_end,
            heartbeat_active_hours_timezone=hb_timezone,
        )

    def _notify_operation_phase(self, phase: str) -> None:
        if self._operation_phase_hook is not None:
            self._operation_phase_hook(phase)

    def resolve_preview_workspace(
        self,
        *,
        workspace_mode: str,
        agent_id_hint: str | None,
        workspace_root: str | None,
    ) -> str:
        """Resolve one draft workspace on this node without creating it.

        Args:
            workspace_mode: ``default`` delegates to the node factory; ``custom``
                resolves the supplied node-local path.
            agent_id_hint: Draft Agent id used by the default workspace factory.
            workspace_root: Custom path supplied by the create form.

        Returns:
            Canonical node-local path, or an empty string while the draft lacks
            enough information to resolve a workspace.

        Raises:
            ValueError: When the mode or custom path is invalid.
        """
        if workspace_mode == "default":
            if not isinstance(agent_id_hint, str) or not agent_id_hint.strip():
                return ""
            return str(
                self._workspace_root_factory(agent_id_hint.strip())
                .expanduser()
                .resolve()
            )
        if workspace_mode != "custom":
            raise ValueError("workspace_mode must be default or custom")
        if not isinstance(workspace_root, str) or not workspace_root.strip():
            return ""
        candidate = Path(workspace_root.strip()).expanduser()
        if not candidate.is_absolute():
            raise ValueError("workspace_root must be an absolute path or start with ~/")
        return str(candidate.resolve())

    def _assigned_agent_for_workspace(self, workspace_root: Path) -> str | None:
        canonical_root = workspace_root.expanduser().resolve()
        for agent in self._config_snapshot().agents:
            if agent.workspace_root.expanduser().resolve() == canonical_root:
                return agent.agent_id
        return None

    def _prepare_custom_workspace(
        self, workspace_root: Path, *, confirm_existing: bool
    ) -> dict[str, object] | None:
        try:
            target_stat = workspace_root.stat()
        except FileNotFoundError:
            parent = workspace_root.parent
            try:
                parent_stat = parent.stat()
            except FileNotFoundError:
                return self._workspace_rejection(
                    code="workspace_parent_missing",
                    detail="Workspace parent directory does not exist.",
                )
            except OSError:
                return self._workspace_rejection(
                    code="workspace_parent_unusable",
                    detail="Workspace parent directory is not usable.",
                )
            if not stat.S_ISDIR(parent_stat.st_mode) or not os.access(
                parent, os.W_OK | os.X_OK
            ):
                return self._workspace_rejection(
                    code="workspace_parent_unusable",
                    detail="Workspace parent directory is not usable.",
                )
            try:
                workspace_root.mkdir()
            except FileNotFoundError:
                return self._workspace_rejection(
                    code="workspace_parent_missing",
                    detail="Workspace parent directory does not exist.",
                )
            except OSError:
                return self._workspace_rejection(
                    code="workspace_parent_unusable",
                    detail="Workspace parent directory is not usable.",
                )
            return None
        except OSError:
            return self._workspace_rejection(
                code="workspace_parent_unusable",
                detail="Workspace target cannot be inspected on the selected node.",
            )

        if not stat.S_ISDIR(target_stat.st_mode):
            return self._workspace_rejection(
                code="workspace_target_not_directory",
                detail="Workspace target exists but is not a directory.",
            )
        if not confirm_existing:
            return self._workspace_rejection(
                code="workspace_confirmation_required",
                detail="Workspace target is an existing directory and requires confirmation.",
            )
        return None

    @staticmethod
    def _workspace_rejection(
        *, code: str, detail: str, agent_id: str | None = None
    ) -> dict[str, object]:
        error: dict[str, object] = {"code": code, "detail": detail}
        if agent_id is not None:
            error["agent_id"] = agent_id
        return {"error": error}

    def ensure_agent_skills_enabled(
        self, agent_id: str, skill_ids: tuple[str, ...]
    ) -> bool:
        """Enable declared skills for a local agent with an explicit allowlist."""

        agent = self._local_agent(agent_id)
        if agent is None:
            return False
        self._enable_skills_for_agent(agent, skill_ids)
        updated = self._local_agent(agent_id)
        return updated is not None and (
            not updated.skills
            or all(skill_id in updated.skills for skill_id in skill_ids)
        )

    def ensure_agent_skill_enabled(self, agent_id: str, skill_id: str) -> bool:
        """Enable one declared skill through the shared collection operation."""

        return self.ensure_agent_skills_enabled(agent_id, (skill_id,))

    def handle_skill_created(self, agent_id: str, event: Mapping[str, object]) -> None:
        """Enable a successfully created skill for the affected live agents."""

        skill_name = event.get("name")
        scope = event.get("scope")
        raw_skill_root = event.get("skill_root")
        if not (
            isinstance(skill_name, str)
            and skill_name.strip()
            and isinstance(scope, str)
            and isinstance(raw_skill_root, str)
            and raw_skill_root.strip()
        ):
            return
        skill_name = skill_name.strip()
        skill_root = Path(raw_skill_root).expanduser().resolve()
        if scope == "agent":
            agent = self._local_agent(agent_id)
            if agent is None:
                return
            if skill_root != self._agent_skill_root(agent):
                _log.warning(
                    "ignoring agent-scoped skill_created for %s: root %s is not the agent skill root",
                    agent_id,
                    skill_root,
                )
                return
            self._enable_skills_for_agent(
                agent, (skill_name,), explicit_capability_change=True
            )
            return
        if scope == "global":
            if self._global_skill_root is None or skill_root != self._global_skill_root:
                _log.warning(
                    "ignoring global skill_created for %s: root %s is not configured global root",
                    agent_id,
                    skill_root,
                )
                return
            for agent in tuple(self._config_snapshot().agents):
                self._enable_skills_for_agent(
                    agent, (skill_name,), explicit_capability_change=True
                )

    def _enable_skills_for_agent(
        self,
        agent: AgentWorkspaceConfig,
        skill_ids: tuple[str, ...],
        *,
        explicit_capability_change: bool = False,
    ) -> None:
        required_skills = tuple(dict.fromkeys(skill_ids))
        if not required_skills:
            return
        mode = effective_skills_selection_mode(
            agent.skills_selection_mode, agent.skills
        )
        if mode == DEFAULT_DISCOVERY:
            self._republish_agent(agent)
            return
        if not agent.skills and not explicit_capability_change:
            self._republish_agent(agent)
            return
        if all(skill_id in agent.skills for skill_id in required_skills):
            self._republish_agent(agent)
            return
        try:
            payload = self._fetch_agent_config(agent_id=agent.agent_id)
            next_skills = [
                item.strip()
                for item in payload.get("skills", [])
                if isinstance(item, str) and item.strip()
            ]
            missing_skills = [
                skill_id for skill_id in required_skills if skill_id not in next_skills
            ]
            if missing_skills:
                next_skills.extend(missing_skills)
                updated = self._patch_agent_skills(agent.agent_id, payload, next_skills)
                self._publish_agent_config(
                    self._decode_mirror_agent_config(
                        payload=updated,
                        agent_id=agent.agent_id,
                    )
                )
            else:
                self._republish_agent(agent)
        except (httpx.HTTPError, ValueError, RuntimeError):
            _log.warning(
                "failed to enable skills %s for agent %s",
                required_skills,
                agent.agent_id,
                exc_info=True,
            )

    def _patch_agent_skills(
        self,
        agent_id: str,
        payload: Mapping[str, object],
        skills: list[str],
    ) -> dict[str, object]:
        raw_tools = payload.get("tool_allowlist")
        raw_features = payload.get("features")
        patch_payload: dict[str, object] = {
            "profile_version": int(payload.get("profile_version", 1)),
            "display_name": str(payload.get("display_name") or agent_id),
            "description": str(payload.get("description") or ""),
            "skills": skills,
            "skills_selection_mode": str(
                payload.get("skills_selection_mode")
                or effective_skills_selection_mode(
                    None,
                    tuple(
                        item.strip()
                        for item in payload.get("skills", [])
                        if isinstance(item, str) and item.strip()
                    ),
                )
            ),
            "tool_allowlist": [
                item.strip()
                for item in (raw_tools if isinstance(raw_tools, list) else [])
                if isinstance(item, str) and item.strip()
            ],
            "group_reply_policy": str(payload.get("group_reply_policy") or "manual"),
            "default_model": payload.get("default_model")
            if isinstance(payload.get("default_model"), str)
            else None,
            "reasoning_effort": payload.get("reasoning_effort")
            if isinstance(payload.get("reasoning_effort"), str)
            else None,
            "features": raw_features if isinstance(raw_features, dict) else {},
            "custom_prompt": payload.get("custom_prompt")
            if isinstance(payload.get("custom_prompt"), str)
            else None,
            "heartbeat_json": payload.get("heartbeat_json")
            if isinstance(payload.get("heartbeat_json"), str)
            else None,
        }
        response = self._get_client().patch(
            f"/im/v1/agents/{agent_id}/config",
            json=patch_payload,
        )
        response.raise_for_status()
        updated = response.json()
        if not isinstance(updated, dict):
            raise ValueError("agent config patch response must be an object")
        return updated

    def _local_agent(self, agent_id: str) -> AgentWorkspaceConfig | None:
        return next(
            (
                agent
                for agent in self._config_snapshot().agents
                if agent.agent_id == agent_id
            ),
            None,
        )

    def _ensure_static_feishu_bundle(
        self, *, agent_id: str, payload: dict[str, object]
    ) -> dict[str, object]:
        """Patch static Feishu mirror profiles before they replace local runtime.

        Default discovery and explicit-empty allowlists are both left unchanged;
        only non-empty explicit allowlists are reconciled with the packaged bundle.
        """

        if agent_id not in enabled_feishu_agent_ids(self._config_snapshot()):
            return payload
        skills = [
            item.strip()
            for item in payload.get("skills", [])
            if isinstance(item, str) and item.strip()
        ]
        mode = effective_skills_selection_mode(
            _selection_mode(payload.get("skills_selection_mode")), tuple(skills)
        )
        if mode != EXPLICIT_ALLOWLIST or not skills:
            return payload
        missing_skills = [
            skill_id for skill_id in lark_skill_names() if skill_id not in skills
        ]
        if not missing_skills:
            return payload
        return self._patch_agent_skills(agent_id, payload, [*skills, *missing_skills])

    def _config_snapshot(self) -> LocalConfig:
        """Return the process-wide config snapshot shared by all durable writers."""

        return self._config_owner.snapshot()

    @staticmethod
    def _agent_skill_root(agent: AgentWorkspaceConfig) -> Path:
        return (agent.workspace_root / _WCD / "skills").expanduser().resolve()

    def close(self) -> None:
        client = self._client
        if client is not None:
            client.close()
            self._client = None

    def reconcile_all_agents(
        self,
        *,
        memory_versions: dict[str, int] | None = None,
        latest_memory_version: Callable[[str], int | None] | None = None,
    ) -> None:
        """拉 IM 权威 profile 做全量对账，按 profile_version 取大覆盖内存 config。

        feat-394-M12 决策 F：gateway WS bind 完成（含重连）后调用一次，消除「漏一次
        增量推送即永久停在旧状态」的问题。对每个 local_config.agents 拉 source=mirror
        profile；若 IM 返回的 profile_version >= memory_versions[agent_id] 则
        register_agent 覆盖内存，否则保留内存（取大原则，避免回退新版本）。HTTP 失败
        时记录警告并跳过该 agent——不抛出，WS 连接生命周期不受影响。

        Args:
            memory_versions: 可选的 agent_id → 当前内存 profile_version 映射（由
                ConfigSyncClient 维护）。缺失或无对应 key 时视作内存版本为 0，即接受
                任意 IM 版本。
            latest_memory_version: 可选的当前版本读取器。后台 reconcile 在拉取期间
                可能有新的 config.sync 到达，发布前须按该读取器再次避免回退。
        """
        if memory_versions is None:
            memory_versions = {}
        for agent in self._config_snapshot().agents:
            agent_id = agent.agent_id
            memory_version = lambda: max(
                memory_versions.get(agent_id, 0),
                (latest_memory_version(agent_id) or 0) if latest_memory_version else 0,
            )
            mem_ver = memory_version()
            try:
                payload = self._fetch_agent_config(agent_id=agent_id)
                im_version = int(payload.get("profile_version", 0))
                if im_version < mem_ver:
                    # IM 版本落后内存（增量推送已带来更新版本），保留内存不回退
                    _log.debug(
                        "reconcile_all_agents: skipping agent %s — IM version %d < memory %d",
                        agent_id,
                        im_version,
                        mem_ver,
                    )
                    continue
                payload = self._ensure_static_feishu_bundle(
                    agent_id=agent_id,
                    payload=payload,
                )
                if im_version < memory_version():
                    _log.debug(
                        "reconcile_all_agents: skipping agent %s after fetch — IM version %d is stale",
                        agent_id,
                        im_version,
                    )
                    continue
                self._publish_agent_config(
                    self._decode_mirror_agent_config(
                        payload=payload,
                        agent_id=agent_id,
                    )
                )
            except (httpx.HTTPError, ValueError):
                _log.warning(
                    "reconcile_all_agents: failed to reconcile profile for agent %s, skipping",
                    agent_id,
                    exc_info=True,
                )
                continue
            _log.debug(
                "reconcile_all_agents: updated agent %s to IM version %d",
                agent_id,
                im_version,
            )

    def _decode_mirror_agent_config(
        self, *, payload: Mapping[str, object], agent_id: str
    ) -> AgentWorkspaceConfig:
        """Purely decode one IM mirror payload into the local runtime shape."""

        workspace_root = resolve_runtime_workspace(
            agent_id=agent_id,
            local_agents=self._config_snapshot().agents,
            workspace_root_factory=self._workspace_root_factory,
        )
        raw_features = payload.get("features")
        features = (
            {
                key: value
                for key, value in raw_features.items()
                if isinstance(key, str) and isinstance(value, bool)
            }
            if isinstance(raw_features, dict)
            else {}
        )
        heartbeat_raw = payload.get("heartbeat")
        heartbeat_json = payload.get("heartbeat_json")
        if isinstance(heartbeat_json, str) and heartbeat_json.strip():
            try:
                heartbeat_raw = json.loads(heartbeat_json)
            except (ValueError, TypeError):
                pass
        heartbeat_every, hb_start, hb_end, hb_timezone = (
            _parse_heartbeat_from_im_payload(heartbeat_raw)
        )

        def _optional_text(field: str) -> str | None:
            value = payload.get(field)
            return value.strip() if isinstance(value, str) and value.strip() else None

        raw_skills = payload.get("skills")
        raw_tools = payload.get("tool_allowlist")
        default_model = _optional_text("default_model")
        reasoning_effort = _optional_text("reasoning_effort")
        self._reasoning_catalog.validate(default_model, reasoning_effort)
        existing_agent = self._local_agent(agent_id)
        return AgentWorkspaceConfig(
            agent_id=agent_id,
            workspace_root=workspace_root,
            workspace_is_default=(
                existing_agent.workspace_is_default
                if existing_agent is not None
                else True
            ),
            create_operation_id=(
                existing_agent.create_operation_id
                if existing_agent is not None
                else None
            ),
            title=str(payload.get("display_name") or agent_id),
            skills=tuple(
                item.strip()
                for item in (raw_skills if isinstance(raw_skills, list) else [])
                if isinstance(item, str) and item.strip()
            ),
            skills_selection_mode=_selection_mode(payload.get("skills_selection_mode")),
            tool_allowlist=tuple(
                item.strip()
                for item in (raw_tools if isinstance(raw_tools, list) else [])
                if isinstance(item, str) and item.strip()
            ),
            group_reply_policy=_optional_text("group_reply_policy"),
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            features=features,
            custom_prompt=_optional_text("custom_prompt"),
            heartbeat_every=heartbeat_every,
            heartbeat_active_hours_start=hb_start,
            heartbeat_active_hours_end=hb_end,
            heartbeat_active_hours_timezone=hb_timezone,
        )

    def _persist_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        def update(current: LocalConfig) -> LocalConfig:
            agents = list(current.agents)
            for index, existing in enumerate(agents):
                if existing.agent_id == agent_config.agent_id:
                    agents[index] = agent_config
                    break
            else:
                agents.append(agent_config)
            return replace(
                current,
                agents=tuple(agents),
                source_path=current.source_path or default_local_config_path(),
            )

        self._config_owner.persist(
            update,
            save_config=save_local_config,
        )

    def _publish_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        """Converge durable and live owners independently, persisting first."""

        local_config = self._config_snapshot()
        local_current = next(
            (
                agent
                for agent in local_config.agents
                if agent.agent_id == agent_config.agent_id
            ),
            None,
        )
        if local_current != agent_config:
            self._persist_agent_config(agent_config)
        current = self._agent_catalog.get(agent_config.agent_id)
        if current is not None and current.config == agent_config:
            return
        self._republish_agent(agent_config)

    def _republish_agent(self, agent_config: AgentWorkspaceConfig) -> None:
        """Publish desired configuration without replacing existing chat sessions."""

        self._agent_catalog.publish(agent_config)

    def current_agent_payload(self, *, agent_id: str) -> dict[str, object] | None:
        for agent in self._config_snapshot().agents:
            if agent.agent_id != agent_id:
                continue
            payload: dict[str, object] = {
                "display_name": agent.title or agent.agent_id,
                "skills": list(agent.skills),
                "skills_selection_mode": effective_skills_selection_mode(
                    agent.skills_selection_mode, agent.skills
                ),
                "tool_allowlist": list(agent.tool_allowlist),
                "group_reply_policy": agent.group_reply_policy or "manual",
                "default_model": agent.default_model,
                "reasoning_effort": agent.reasoning_effort,
                "workspace_root": str(agent.workspace_root),
                "workspace_is_default": agent.workspace_is_default,
                # feat-379-M2: expose per-agent features/custom_prompt for capabilities reporting
                "features": dict(agent.features),
                "custom_prompt": agent.custom_prompt,
                "heartbeat_json": _heartbeat_json_for_agent(agent),
            }
            return payload
        return None

    def _fetch_agent_config(self, *, agent_id: str) -> dict[str, object]:
        response = self._get_client().get(
            f"/im/v1/agents/{agent_id}/config", params={"source": "mirror"}
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("agent config response must be an object")
        return payload

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            self._client = self._client_factory(self._base_url)
        else:
            self._client = httpx.Client(
                base_url=self._base_url,
                headers=self._base_headers,
                timeout=self._timeout_seconds,
                trust_env=False,
            )
        return self._client

    def update_token(self, token: str | None) -> None:
        """Propagate a refreshed access token so future sync requests use it.

        feat-394-M3 fix: called by the token_getter wrapper in _run_gateway after
        each successful token refresh so this client does not hold a stale/empty
        Bearer token when auto-bind has rotated credentials.  Mirrors the
        _refresh_token pattern in _IMBootstrapClient (main.py:621-628).

        Args:
            token: New access token, or None to clear.
        """
        self._base_headers = build_im_http_headers(token)
        # Propagate updated headers to any live client instance so in-flight
        # connections also pick up the new token without a full reconnect.
        # Injected test clients (passed via constructor) are updated in-place;
        # self-built clients are rebuilt by _get_client() on the next request
        # if they were previously None (first call) or by headers update here.
        if self._client is not None:
            self._client.headers.update(self._base_headers)

    @staticmethod
    def _default_workspace_root(agent_id: str) -> Path:
        return Path("~/.nanoassistant/workspaces").expanduser() / agent_id


def _required_operation_text(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_operation_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _operation_string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


def _heartbeat_json_for_agent(agent: AgentWorkspaceConfig) -> str | None:
    heartbeat: dict[str, object] = {}
    if agent.heartbeat_every is not None:
        heartbeat["every"] = agent.heartbeat_every
    active_hours: dict[str, str] = {}
    if agent.heartbeat_active_hours_start is not None:
        active_hours["start"] = agent.heartbeat_active_hours_start
    if agent.heartbeat_active_hours_end is not None:
        active_hours["end"] = agent.heartbeat_active_hours_end
    if agent.heartbeat_active_hours_timezone is not None:
        active_hours["timezone"] = agent.heartbeat_active_hours_timezone
    if active_hours:
        heartbeat["active_hours"] = active_hours
    if not heartbeat:
        return None
    return json.dumps(
        heartbeat, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def _agent_operation_payload(agent: AgentWorkspaceConfig) -> dict[str, object]:
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.title or agent.agent_id,
        "skills": list(agent.skills),
        "skills_selection_mode": agent.skills_selection_mode,
        "tool_allowlist": list(agent.tool_allowlist),
        "group_reply_policy": agent.group_reply_policy or "manual",
        "default_model": agent.default_model,
        "reasoning_effort": agent.reasoning_effort,
        "workspace_root": str(agent.workspace_root),
        "features": dict(agent.features),
        "custom_prompt": agent.custom_prompt,
        "heartbeat_json": _heartbeat_json_for_agent(agent),
    }


def _receipt_result(receipt: ConfigOperationReceipt) -> dict[str, object]:
    result: dict[str, object] = {
        "operation_id": receipt.operation_id,
        "candidate_fingerprint": receipt.candidate_fingerprint,
        "status": receipt.status if receipt.status != "prepared" else "pending",
    }
    if receipt.status == "applied":
        result["agent"] = dict(receipt.candidate)
    if receipt.error_code is not None:
        result["error_code"] = receipt.error_code
    if receipt.message is not None:
        result["message"] = receipt.message
    return result


def _operation_rejection(
    operation_id: str,
    candidate_fingerprint: str,
    error_code: str,
    message: str,
    *,
    agent_id: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "operation_id": operation_id,
        "candidate_fingerprint": candidate_fingerprint,
        "status": "rejected",
        "error_code": error_code,
        "message": message,
    }
    if agent_id is not None:
        result["agent_id"] = agent_id
    return result


def _make_workspace_root_factory(
    workspace_base: str | None,
) -> Callable[[str], Path] | None:
    """Build a workspace_root factory rooted at ``workspace_base`` (bugfix-424 / #127).

    When ``workspace_base`` is set, dynamically-created agents (built via IM
    ``agent.create`` without an explicit ``workspace_root``) get their workspace at
    ``<workspace_base>/<agent_id>`` — the same isolation root preset agents use.
    Returns ``None`` when ``workspace_base`` is unset so the caller uses the
    managed ``~/.nanoassistant/workspaces`` default.

    Args:
        workspace_base: Base directory from ``node.workspace_base``, or None.

    Returns:
        A factory mapping ``agent_id`` to an absolute workspace path, or None.
    """
    if not (isinstance(workspace_base, str) and workspace_base.strip()):
        return None
    base = Path(workspace_base.strip()).expanduser()

    def _factory(agent_id: str, _base: Path = base) -> Path:
        return _base / agent_id

    return _factory


def _parse_heartbeat_from_im_payload(
    raw: object,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse heartbeat cadence fields from an IM agent config payload.

    feat-394 decision 5 / M9-E: enable state lives in features["heartbeat"] (decision D).
    This function only extracts cadence data: every, active_hours_{start,end,timezone}.

    Args:
        raw: The raw value of ``payload["heartbeat"]`` from an IM API response.

    Returns:
        4-tuple of (heartbeat_every, active_hours_start, active_hours_end,
        active_hours_timezone).  All fields are None when absent.
    """
    if not isinstance(raw, dict):
        return None, None, None, None
    every_raw = raw.get("every")
    heartbeat_every = (
        every_raw.strip() if isinstance(every_raw, str) and every_raw.strip() else None
    )
    active_hours_raw = raw.get("active_hours")
    if isinstance(active_hours_raw, dict):
        start_raw = active_hours_raw.get("start")
        end_raw = active_hours_raw.get("end")
        tz_raw = active_hours_raw.get("timezone")
        hb_start = (
            start_raw.strip()
            if isinstance(start_raw, str) and start_raw.strip()
            else None
        )
        hb_end = (
            end_raw.strip() if isinstance(end_raw, str) and end_raw.strip() else None
        )
        hb_tz = tz_raw.strip() if isinstance(tz_raw, str) and tz_raw.strip() else None
    else:
        hb_start, hb_end, hb_tz = None, None, None
    return heartbeat_every, hb_start, hb_end, hb_tz
