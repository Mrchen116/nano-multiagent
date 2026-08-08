"""Recoverable IM-to-Gateway Agent create and configuration apply coordination."""

from __future__ import annotations

from hashlib import sha256
import json
from uuid import uuid4

from IM.application.config_service import ConfigService
from IM.domain.models import AgentProfile
from IM.infra.repositories.agents import AgentProfileVersionConflictError
from IM.infra.repositories.agent_config_operations import (
    AgentConfigOperation,
    AgentConfigOperationRepository,
)
from IM.ws.gateway.control import GatewayControl


_GATEWAY_CONFIG_KEYS = (
    "agent_id",
    "display_name",
    "skills",
    "tool_allowlist",
    "group_reply_policy",
    "default_model",
    "reasoning_effort",
    "workspace_root",
    "features",
    "custom_prompt",
    "heartbeat_json",
)
_SAFE_REJECTION_CODES = frozenset(
    {
        "agent_id_already_exists",
        "invalid_agent_config",
        "operation_conflict",
        "operation_id_reused",
        "workspace_already_assigned",
        "workspace_confirmation_required",
        "workspace_initialization_failed",
        "workspace_parent_missing",
        "workspace_parent_unusable",
        "workspace_target_not_directory",
    }
)


class ConfigApplyPendingError(RuntimeError):
    """Signal that Gateway terminal state or compensation is still unknown."""


class ConfigApplyRejectedError(ValueError):
    """Expose a stable, API-safe Gateway rejection code."""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        self.code = code if code in _SAFE_REJECTION_CODES else "invalid_agent_config"
        self.message = message
        self.agent_id = agent_id
        super().__init__(self.code)


class ConfigApplyProfileConflictError(ValueError):
    """Signal an IM optimistic-lock loss after confirmed Gateway compensation."""


class AgentConfigOperationCoordinator:
    """Drive durable Agent operations to a truthful Gateway/IM terminal state."""

    def __init__(
        self,
        *,
        service: ConfigService,
        operations: AgentConfigOperationRepository,
        gateway: GatewayControl,
    ) -> None:
        self._service = service
        self._operations = operations
        self._gateway = gateway

    async def recover_active(
        self, *, agent_id: str, owner_id: str
    ) -> AgentProfile | None:
        """Recover one active operation, returning its committed profile when known."""
        lock = await self._gateway.config_operation_lock(agent_id=agent_id)
        async with lock:
            operation = self._operations.get_active(
                agent_id=agent_id, owner_id=owner_id
            )
            if operation is None:
                return None
            result = await self._recover_gateway_result(operation)
            if result is None:
                raise ConfigApplyPendingError("config_apply_pending")
            terminal = _result_status(result)
            if terminal == "pending":
                raise ConfigApplyPendingError("config_apply_pending")
            if terminal == "rejected":
                if operation.operation_kind == "compensation":
                    raise ConfigApplyPendingError("config_apply_pending")
                self._record_rejected(operation=operation, result=result)
                raise ConfigApplyRejectedError(
                    _safe_result_error_code(result),
                    message=_result_message(result),
                    agent_id=_result_error_agent_id(result),
                )
            operation = self._operations.mark_gateway_applied(
                operation_id=operation.operation_id, result=result
            )
            return await self._commit_gateway_applied(operation)

    async def create_agent(
        self,
        *,
        owner_id: str,
        node_id: str,
        candidate: dict[str, object],
    ) -> AgentProfile:
        """Submit and commit one Gateway-first Agent creation operation."""
        agent_id = _required_candidate_text(candidate, "agent_id")
        lock = await self._gateway.config_operation_lock(agent_id=agent_id)
        async with lock:
            operation = self._operations.create(
                operation_id=uuid4().hex,
                agent_id=agent_id,
                owner_id=owner_id,
                node_id=node_id,
                operation_kind="create",
                candidate=candidate,
                previous_candidate=None,
                candidate_fingerprint=candidate_fingerprint(candidate),
                expected_previous_fingerprint=None,
                expected_profile_version=None,
            )
            result = await self._gateway.request_agent_create(
                target_node_id=node_id,
                operation_id=operation.operation_id,
                candidate_fingerprint=operation.candidate_fingerprint,
                payload=gateway_candidate(candidate),
            )
            result = await self._resolve_initial_result(operation, result)
            operation = self._accept_applied(operation=operation, result=result)
            profile = self._commit_create(operation)
            self._operations.mark_committed(operation_id=operation.operation_id)
            return profile

    async def update_agent(
        self,
        *,
        profile: AgentProfile,
        owner_id: str,
        candidate: dict[str, object],
    ) -> AgentProfile:
        """Submit Gateway apply, then CAS the IM profile or compensate Gateway."""
        lock = await self._gateway.config_operation_lock(agent_id=profile.agent_id)
        async with lock:
            previous_candidate = candidate_from_profile(profile, service=self._service)
            operation = self._operations.create(
                operation_id=uuid4().hex,
                agent_id=profile.agent_id,
                owner_id=owner_id,
                node_id=_required_profile_node(profile),
                operation_kind="apply",
                candidate=candidate,
                previous_candidate=previous_candidate,
                candidate_fingerprint=candidate_fingerprint(candidate),
                expected_previous_fingerprint=candidate_fingerprint(previous_candidate),
                expected_profile_version=profile.profile_version,
            )
            result = await self._gateway.request_agent_config_apply(
                target_node_id=operation.node_id,
                operation_id=operation.operation_id,
                candidate_fingerprint=operation.candidate_fingerprint,
                expected_previous_fingerprint=(
                    operation.expected_previous_fingerprint or ""
                ),
                payload=gateway_candidate(candidate),
            )
            result = await self._resolve_initial_result(operation, result)
            operation = self._accept_applied(operation=operation, result=result)
            try:
                updated = self._commit_update(operation)
            except AgentProfileVersionConflictError:
                current = self._service.get_profile(agent_id=operation.agent_id)
                await self._compensate(
                    operation=operation, old_profile=current or profile
                )
                raise ConfigApplyProfileConflictError(
                    "profile_version_conflict"
                ) from None
            self._operations.mark_committed(operation_id=operation.operation_id)
            return updated

    async def _resolve_initial_result(
        self,
        operation: AgentConfigOperation,
        result: dict[str, object] | None,
    ) -> dict[str, object]:
        if result is None or _result_status(result) == "pending":
            result = await self._recover_gateway_result(operation)
        if result is None or _result_status(result) == "pending":
            raise ConfigApplyPendingError("config_apply_pending")
        return result

    async def _recover_gateway_result(
        self, operation: AgentConfigOperation
    ) -> dict[str, object] | None:
        if operation.status == "gateway_applied":
            return operation.gateway_result
        result = await self._gateway.request_agent_config_operation_status(
            target_node_id=operation.node_id,
            operation_id=operation.operation_id,
            candidate_fingerprint=operation.candidate_fingerprint,
        )
        if result is None or _result_status(result) != "pending":
            return result
        return await self._resubmit_operation(operation)

    async def _resubmit_operation(
        self, operation: AgentConfigOperation
    ) -> dict[str, object] | None:
        """Resend the same intent when Gateway has no receipt for its operation id."""
        if operation.operation_kind == "create":
            return await self._gateway.request_agent_create(
                target_node_id=operation.node_id,
                operation_id=operation.operation_id,
                candidate_fingerprint=operation.candidate_fingerprint,
                payload=gateway_candidate(operation.candidate),
            )
        return await self._gateway.request_agent_config_apply(
            target_node_id=operation.node_id,
            operation_id=operation.operation_id,
            candidate_fingerprint=operation.candidate_fingerprint,
            expected_previous_fingerprint=(
                operation.expected_previous_fingerprint or ""
            ),
            payload=gateway_candidate(operation.candidate),
        )

    def _accept_applied(
        self,
        *,
        operation: AgentConfigOperation,
        result: dict[str, object],
    ) -> AgentConfigOperation:
        if _result_status(result) == "rejected":
            self._record_rejected(operation=operation, result=result)
            raise ConfigApplyRejectedError(
                _safe_result_error_code(result),
                message=_result_message(result),
                agent_id=_result_error_agent_id(result),
            )
        return self._operations.mark_gateway_applied(
            operation_id=operation.operation_id, result=result
        )

    async def _commit_gateway_applied(
        self, operation: AgentConfigOperation
    ) -> AgentProfile:
        if operation.operation_kind == "create":
            profile = self._commit_create(operation)
            self._operations.mark_committed(operation_id=operation.operation_id)
            return profile
        if operation.operation_kind == "compensation":
            self._operations.finish_compensation(operation_id=operation.operation_id)
            raise ConfigApplyProfileConflictError("profile_version_conflict")
        current = self._service.get_profile(agent_id=operation.agent_id)
        if current is not None and _profile_matches_committed_update(
            current, operation=operation, service=self._service
        ):
            self._operations.mark_committed(operation_id=operation.operation_id)
            return current
        try:
            profile = self._commit_update(operation)
        except AgentProfileVersionConflictError:
            current = self._service.get_profile(agent_id=operation.agent_id)
            if current is None:
                raise ConfigApplyPendingError("config_apply_pending") from None
            await self._compensate(operation=operation, old_profile=current)
            raise ConfigApplyProfileConflictError("profile_version_conflict") from None
        self._operations.mark_committed(operation_id=operation.operation_id)
        return profile

    def _commit_create(self, operation: AgentConfigOperation) -> AgentProfile:
        candidate = operation.candidate
        result_agent = _result_agent(operation.gateway_result)
        workspace_root = _text_from_result(
            result_agent, "workspace_root", fallback=candidate.get("workspace_root")
        )
        if workspace_root is None:
            raise ConfigApplyPendingError("config_apply_pending")
        workspace_is_default = _bool_from_result(
            result_agent,
            "workspace_is_default",
            fallback=candidate.get("workspace_is_default"),
        )
        display_name = (
            _text_from_result(
                result_agent, "display_name", fallback=candidate.get("display_name")
            )
            or operation.agent_id
        )
        description = str(candidate.get("description") or "")
        skills = _string_list_from_result(
            result_agent, "skills", fallback=candidate.get("skills")
        )
        tool_allowlist = _string_list_from_result(
            result_agent, "tool_allowlist", fallback=candidate.get("tool_allowlist")
        )
        group_reply_policy = (
            _text_from_result(
                result_agent,
                "group_reply_policy",
                fallback=candidate.get("group_reply_policy"),
            )
            or "manual"
        )
        default_model = _optional_text_from_result(
            result_agent, "default_model", fallback=candidate.get("default_model")
        )
        reasoning_effort = _optional_text_from_result(
            result_agent,
            "reasoning_effort",
            fallback=candidate.get("reasoning_effort"),
        )
        features = _bool_dict_from_result(
            result_agent, "features", fallback=candidate.get("features")
        )
        custom_prompt = _optional_text_from_result(
            result_agent, "custom_prompt", fallback=candidate.get("custom_prompt")
        )
        existing = self._service.get_profile(agent_id=operation.agent_id)
        if existing is not None:
            if _profile_matches_create_result(
                existing,
                operation=operation,
                workspace_root=workspace_root,
                service=self._service,
            ):
                return existing
            if existing.owner_id == "" and existing.node_id == operation.node_id:
                result_display_name = result_agent.get("display_name")
                if (
                    existing.workspace_root != workspace_root
                    or existing.workspace_is_default is not workspace_is_default
                    or workspace_is_default is None
                    or not isinstance(result_display_name, str)
                    or result_display_name.strip() != str(candidate.get("display_name") or "")
                ):
                    self._operations.mark_rejected(
                        operation_id=operation.operation_id,
                        error_code="agent_id_already_exists",
                        error_message="agent_id already exists",
                        result=operation.gateway_result,
                    )
                    raise ConfigApplyRejectedError(
                        "agent_id_already_exists",
                        message="agent_id already exists",
                    )
                return self._service.claim_seeded_profile(
                    agent_id=operation.agent_id,
                    owner_id=operation.owner_id,
                    node_id=operation.node_id,
                    expected_workspace_root=workspace_root,
                    expected_workspace_is_default=workspace_is_default,
                    display_name=display_name,
                    description=description,
                    skills=skills,
                    tool_allowlist=tool_allowlist,
                    group_reply_policy=group_reply_policy,
                    default_model=default_model,
                    reasoning_effort=reasoning_effort,
                    features=features,
                    custom_prompt=custom_prompt,
                )
            raise ConfigApplyPendingError("config_apply_pending")
        return self._service.create_profile(
            agent_id=operation.agent_id,
            owner_id=operation.owner_id,
            node_id=operation.node_id,
            display_name=display_name,
            description=description,
            skills=skills,
            tool_allowlist=tool_allowlist,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            reasoning_effort=reasoning_effort,
            workspace_root=workspace_root,
            workspace_is_default=workspace_is_default,
            features=features,
            custom_prompt=custom_prompt,
            notify_config_sync=False,
        )

    def _commit_update(self, operation: AgentConfigOperation) -> AgentProfile:
        candidate = operation.candidate
        result_agent = _result_agent(operation.gateway_result)
        expected_version = operation.expected_profile_version
        if expected_version is None:
            raise ConfigApplyPendingError("config_apply_pending")
        return self._service.update_profile(
            agent_id=operation.agent_id,
            profile_version=expected_version,
            display_name=_text_from_result(
                result_agent, "display_name", fallback=candidate.get("display_name")
            )
            or operation.agent_id,
            description=str(candidate.get("description") or ""),
            skills=_string_list_from_result(
                result_agent, "skills", fallback=candidate.get("skills")
            ),
            tool_allowlist=_string_list_from_result(
                result_agent,
                "tool_allowlist",
                fallback=candidate.get("tool_allowlist"),
            ),
            group_reply_policy=_text_from_result(
                result_agent,
                "group_reply_policy",
                fallback=candidate.get("group_reply_policy"),
            )
            or "manual",
            default_model=_optional_text_from_result(
                result_agent, "default_model", fallback=candidate.get("default_model")
            ),
            reasoning_effort=_optional_text_from_result(
                result_agent,
                "reasoning_effort",
                fallback=candidate.get("reasoning_effort"),
            ),
            features=_bool_dict_from_result(
                result_agent, "features", fallback=candidate.get("features")
            ),
            custom_prompt=_resolved_custom_prompt(result_agent, candidate),
            heartbeat_json=_optional_text_from_result(
                result_agent,
                "heartbeat_json",
                fallback=candidate.get("heartbeat_json"),
            ),
            notify_config_sync=False,
        )

    async def _compensate(
        self, *, operation: AgentConfigOperation, old_profile: AgentProfile
    ) -> None:
        old_candidate = candidate_from_profile(old_profile, service=self._service)
        compensation = self._operations.replace_with_compensation(
            source_operation_id=operation.operation_id,
            compensation_operation_id=uuid4().hex,
            candidate=old_candidate,
            candidate_fingerprint=candidate_fingerprint(old_candidate),
            expected_previous_fingerprint=operation.candidate_fingerprint,
        )
        result = await self._gateway.request_agent_config_apply(
            target_node_id=compensation.node_id,
            operation_id=compensation.operation_id,
            candidate_fingerprint=compensation.candidate_fingerprint,
            expected_previous_fingerprint=(
                compensation.expected_previous_fingerprint or ""
            ),
            payload=gateway_candidate(old_candidate),
        )
        result = await self._resolve_initial_result(compensation, result)
        if _result_status(result) != "applied":
            raise ConfigApplyPendingError("config_apply_pending")
        self._operations.mark_gateway_applied(
            operation_id=compensation.operation_id, result=result
        )
        self._operations.finish_compensation(operation_id=compensation.operation_id)

    def _record_rejected(
        self,
        *,
        operation: AgentConfigOperation,
        result: dict[str, object],
    ) -> None:
        raw_message = result.get("message")
        self._operations.mark_rejected(
            operation_id=operation.operation_id,
            error_code=_safe_result_error_code(result),
            error_message=raw_message if isinstance(raw_message, str) else None,
            result=result,
        )


def candidate_from_profile(
    profile: AgentProfile, *, service: ConfigService
) -> dict[str, object]:
    """Project a persisted IM profile into the complete operation candidate shape."""
    return {
        "agent_id": profile.agent_id,
        "owner_id": profile.owner_id,
        "display_name": profile.display_name,
        "description": profile.description,
        "skills": list(profile.skills),
        "tool_allowlist": list(profile.tool_allowlist),
        "group_reply_policy": profile.group_reply_policy,
        "default_model": profile.default_model,
        "reasoning_effort": profile.reasoning_effort,
        "workspace_root": service.workspace_root_for_profile(profile),
        "features": dict(profile.features),
        "custom_prompt": profile.custom_prompt,
        "heartbeat_json": _canonical_heartbeat_json(profile.heartbeat_json),
    }


def gateway_candidate(candidate: dict[str, object]) -> dict[str, object]:
    """Return only fields durably owned by the Gateway Agent configuration."""
    agent_id = str(candidate.get("agent_id") or "").strip()
    raw_features = candidate.get("features")
    projected: dict[str, object] = {
        "agent_id": agent_id,
        "display_name": _optional_operation_text(candidate.get("display_name"))
        or agent_id,
        "tool_allowlist": _operation_string_list(candidate.get("tool_allowlist")),
        "group_reply_policy": _optional_operation_text(
            candidate.get("group_reply_policy")
        )
        or "manual",
        "default_model": _optional_operation_text(candidate.get("default_model")),
        "reasoning_effort": _optional_operation_text(candidate.get("reasoning_effort")),
        "workspace_root": _optional_operation_text(candidate.get("workspace_root")),
        "features": {
            key: value
            for key, value in raw_features.items()
            if isinstance(key, str) and isinstance(value, bool)
        }
        if isinstance(raw_features, dict)
        else {},
        "custom_prompt": _optional_operation_text(candidate.get("custom_prompt")),
        "heartbeat_json": _canonical_heartbeat_json(candidate.get("heartbeat_json")),
    }
    if "skills" in candidate:
        raw_skills = candidate.get("skills")
        projected["skills"] = (
            _operation_string_list(raw_skills) if isinstance(raw_skills, list) else None
        )
    if "confirm_existing_workspace" in candidate:
        projected["confirm_existing_workspace"] = (
            candidate.get("confirm_existing_workspace") is True
        )
    return projected


def candidate_fingerprint(candidate: dict[str, object]) -> str:
    """Hash the shared canonical Gateway configuration projection."""
    projected = gateway_candidate(candidate)
    encoded = json.dumps(
        {key: projected.get(key) for key in _GATEWAY_CONFIG_KEYS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _canonical_heartbeat_json(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return value.strip()
    return json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _operation_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _optional_operation_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _result_status(result: dict[str, object]) -> str:
    value = result.get("status")
    return value if isinstance(value, str) else "pending"


def _safe_result_error_code(result: dict[str, object]) -> str:
    value = result.get("error_code")
    if isinstance(value, str) and value in _SAFE_REJECTION_CODES:
        return value
    return "invalid_agent_config"


def _result_message(result: dict[str, object]) -> str | None:
    value = result.get("message")
    return value if isinstance(value, str) and value.strip() else None


def _result_error_agent_id(result: dict[str, object]) -> str | None:
    value = result.get("agent_id")
    return value if isinstance(value, str) and value.strip() else None


def _result_agent(result: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(result, dict):
        return {}
    value = result.get("agent")
    return dict(value) if isinstance(value, dict) else {}


def _required_candidate_text(candidate: dict[str, object], field: str) -> str:
    value = candidate.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value.strip()


def _required_profile_node(profile: AgentProfile) -> str:
    if profile.node_id is None or not profile.node_id.strip():
        raise ValueError("agent_id is not bound to a node")
    return profile.node_id


def _text_from_result(
    result: dict[str, object], field: str, *, fallback: object
) -> str | None:
    value = result.get(field, fallback)
    return value if isinstance(value, str) and value.strip() else None


def _optional_text_from_result(
    result: dict[str, object], field: str, *, fallback: object
) -> str | None:
    value = result[field] if field in result else fallback
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_list_from_result(
    result: dict[str, object], field: str, *, fallback: object
) -> list[str]:
    value = result[field] if field in result else fallback
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bool_dict_from_result(
    result: dict[str, object], field: str, *, fallback: object
) -> dict[str, bool]:
    value = result[field] if field in result else fallback
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, bool)
    }


def _bool_from_result(
    result: dict[str, object], field: str, *, fallback: object
) -> bool | None:
    value = result[field] if field in result else fallback
    return value if isinstance(value, bool) else None


def _resolved_custom_prompt(
    result_agent: dict[str, object], candidate: dict[str, object]
) -> str:
    value = (
        result_agent.get("custom_prompt")
        if "custom_prompt" in result_agent
        else candidate.get("custom_prompt")
    )
    return value if isinstance(value, str) else ""


def _profile_matches_create_result(
    profile: AgentProfile,
    *,
    operation: AgentConfigOperation,
    workspace_root: str,
    service: ConfigService,
) -> bool:
    """Recognize a profile committed just before an IM process interruption."""
    expected = dict(operation.candidate)
    expected.update(_result_agent(operation.gateway_result))
    expected["workspace_root"] = workspace_root
    return (
        profile.owner_id == operation.owner_id
        and profile.node_id == operation.node_id
        and profile.description == str(operation.candidate.get("description") or "")
        and candidate_fingerprint(candidate_from_profile(profile, service=service))
        == candidate_fingerprint(expected)
    )


def _profile_matches_committed_update(
    profile: AgentProfile,
    *,
    operation: AgentConfigOperation,
    service: ConfigService,
) -> bool:
    """Recognize an update committed just before its operation status write."""
    expected_version = operation.expected_profile_version
    return (
        expected_version is not None
        and profile.profile_version == expected_version + 1
        and profile.owner_id == operation.owner_id
        and profile.node_id == operation.node_id
        and profile.description == str(operation.candidate.get("description") or "")
        and candidate_fingerprint(candidate_from_profile(profile, service=service))
        == operation.candidate_fingerprint
    )
