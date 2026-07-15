"""Synchronize IM Agent configuration into live Gateway ownership."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from urllib.parse import urlparse

import httpx

from personal_assistant.config.local_store import (
    AgentWorkspaceConfig,
    LocalConfig,
    WORKSPACE_CONFIG_DIRNAME as _WCD,
    default_local_config_path,
    ensure_workspace_defaults,
    save_local_config,
)
from personal_assistant.gateway.agent_catalog import LiveAgentCatalog
from personal_assistant.gateway.session_binder import GatewaySessionBinder
from personal_assistant.gateway.workspace_authority import resolve_runtime_workspace
from personal_assistant.reporter.upstream_reporter import UpstreamReporter

_log = logging.getLogger(__name__)
_PA_GLOBAL_SKILL_ROOT = Path("~/.nanoassistant/skills")
BootstrapClientFactory = Callable[[str], httpx.Client]
Monotonic = Callable[[], float]
Sleep = Callable[[float], None]

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
    ) -> None:
        self._base_url = _im_http_base_url(base_url)
        self._base_headers = _im_http_headers(token)
        self._timeout_seconds = timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._max_attempts = max(max_attempts, 1)
        self._agent_catalog = agent_catalog
        self._session_binder = session_binder
        self._local_config = local_config
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
        # feat-394-M3 fix: accept token_getter so auto-bind token refresh propagates
        # to config sync requests. Without this, sync_agent calls 401 after auto-bind
        # because the initial token is empty and is never updated. Mirrors the pattern
        # used by _IMBootstrapClient (main.py:599-613).
        self._token_getter = token_getter

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
        """在节点上落地工作区并注册 Agent，供 IM ``agent.create`` / ``agent.created`` 回包使用。"""
        agent_id_raw = agent_payload.get("agent_id")
        if not isinstance(agent_id_raw, str) or not agent_id_raw.strip():
            raise ValueError("agent.create requires non-empty agent_id")
        agent_id = agent_id_raw.strip()
        ws_raw = agent_payload.get("workspace_root")
        if isinstance(ws_raw, str) and ws_raw.strip():
            workspace_root = Path(ws_raw.strip()).expanduser()
            if not workspace_root.is_absolute():
                raise ValueError(
                    "workspace_root must be an absolute path or start with ~/"
                )
            workspace_root = workspace_root.resolve()
        else:
            workspace_root = self._workspace_root_factory(agent_id)
        workspace_root = ensure_workspace_defaults(workspace_root)
        display = agent_payload.get("display_name")
        title = (
            display.strip()
            if isinstance(display, str) and display.strip()
            else agent_id
        )
        desc_val = agent_payload.get("description")
        description_str = desc_val.strip() if isinstance(desc_val, str) else ""
        system_prompt_val = agent_payload.get("system_prompt")
        system_prompt = (
            system_prompt_val.strip()
            if isinstance(system_prompt_val, str) and system_prompt_val.strip()
            else None
        )
        raw_skills = agent_payload.get("skills")
        skills = tuple(
            item.strip()
            for item in (raw_skills if isinstance(raw_skills, list) else [])
            if isinstance(item, str) and item.strip()
        )
        if "skills" not in agent_payload:
            skills = _default_pa_global_skill_names()
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
        dm = agent_payload.get("default_model")
        default_model = dm.strip() if isinstance(dm, str) and dm.strip() else None
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
            title=title,
            skills=skills,
            tool_allowlist=tool_allowlist,
            system_prompt=system_prompt,
            group_reply_policy=group_reply_policy,
            default_model=default_model,
            features=features,
            custom_prompt=custom_prompt,
        )
        self._publish_agent_config(agent_config)
        if self._reporter is not None:
            self._reporter.replace_agents(tuple(self._local_config.agents))
        if self._on_agent_created is not None:
            try:
                self._on_agent_created(agent_id, workspace_root)
            except Exception:  # noqa: BLE001
                _log.warning(
                    "on_agent_created callback failed for agent=%s; "
                    "cron execution service may not be registered",
                    agent_id,
                )
        return {
            "agent_id": agent_id,
            "display_name": title,
            "description": description_str,
            "system_prompt": system_prompt or "",
            "skills": list(skills),
            "tool_allowlist": list(tool_allowlist),
            "group_reply_policy": group_reply_policy,
            "default_model": default_model,
            "workspace_root": str(workspace_root),
            "features": features,
            "custom_prompt": custom_prompt,
        }

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
            self._enable_created_skill_for_agent(agent, skill_name)
            return
        if scope == "global":
            if self._global_skill_root is None or skill_root != self._global_skill_root:
                _log.warning(
                    "ignoring global skill_created for %s: root %s is not configured global root",
                    agent_id,
                    skill_root,
                )
                return
            for agent in tuple(self._local_config.agents):
                self._enable_created_skill_for_agent(agent, skill_name)

    def _enable_created_skill_for_agent(
        self, agent: AgentWorkspaceConfig, skill_name: str
    ) -> None:
        if not agent.skills:
            self._republish_agent(agent)
            return
        if skill_name in agent.skills:
            self._republish_agent(agent)
            return
        try:
            payload = self._fetch_agent_config(agent_id=agent.agent_id)
            next_skills = [
                item.strip()
                for item in payload.get("skills", [])
                if isinstance(item, str) and item.strip()
            ]
            if skill_name not in next_skills:
                next_skills.append(skill_name)
                updated = self._patch_agent_skills(agent.agent_id, payload, next_skills)
                profile_version = int(updated.get("profile_version", 0))
                self.sync_agent(
                    agent_id=agent.agent_id,
                    profile_version=profile_version,
                )
            else:
                self._republish_agent(agent)
        except (httpx.HTTPError, ValueError, RuntimeError):
            _log.warning(
                "failed to enable created skill %s for agent %s",
                skill_name,
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
            "system_prompt": str(payload.get("system_prompt") or ""),
            "skills": skills,
            "tool_allowlist": [
                item.strip()
                for item in (raw_tools if isinstance(raw_tools, list) else [])
                if isinstance(item, str) and item.strip()
            ],
            "group_reply_policy": str(payload.get("group_reply_policy") or "manual"),
            "default_model": payload.get("default_model")
            if isinstance(payload.get("default_model"), str)
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
                for agent in self._local_config.agents
                if agent.agent_id == agent_id
            ),
            None,
        )

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
        """
        if memory_versions is None:
            memory_versions = {}
        for agent in self._local_config.agents:
            agent_id = agent.agent_id
            mem_ver = memory_versions.get(agent_id, 0)
            try:
                payload = self._fetch_agent_config(agent_id=agent_id)
            except (httpx.HTTPError, ValueError):
                _log.warning(
                    "reconcile_all_agents: failed to fetch profile for agent %s, skipping",
                    agent_id,
                )
                continue
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
            self._publish_agent_config(
                self._decode_mirror_agent_config(
                    payload=payload,
                    agent_id=agent_id,
                )
            )
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
            local_agents=self._local_config.agents,
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
        return AgentWorkspaceConfig(
            agent_id=agent_id,
            workspace_root=workspace_root,
            title=str(payload.get("display_name") or agent_id),
            skills=tuple(
                item.strip()
                for item in (raw_skills if isinstance(raw_skills, list) else [])
                if isinstance(item, str) and item.strip()
            ),
            tool_allowlist=tuple(
                item.strip()
                for item in (raw_tools if isinstance(raw_tools, list) else [])
                if isinstance(item, str) and item.strip()
            ),
            system_prompt=_optional_text("system_prompt"),
            group_reply_policy=_optional_text("group_reply_policy"),
            default_model=_optional_text("default_model"),
            features=features,
            custom_prompt=_optional_text("custom_prompt"),
            heartbeat_every=heartbeat_every,
            heartbeat_active_hours_start=hb_start,
            heartbeat_active_hours_end=hb_end,
            heartbeat_active_hours_timezone=hb_timezone,
        )

    def _persist_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        agents = list(self._local_config.agents)
        for index, existing in enumerate(agents):
            if existing.agent_id == agent_config.agent_id:
                agents[index] = agent_config
                break
        else:
            agents.append(agent_config)
        persist_path = (
            Path(self._local_config.source_path)
            if self._local_config.source_path
            else default_local_config_path()
        )
        self._local_config = LocalConfig(
            node=self._local_config.node,
            agents=tuple(agents),
            channels=self._local_config.channels,
            gateway=self._local_config.gateway,
            heartbeat=self._local_config.heartbeat,
            im_service=self._local_config.im_service,
            llm=self._local_config.llm,
            source_path=persist_path,
        )
        save_local_config(self._local_config, persist_path)

    def _publish_agent_config(self, agent_config: AgentWorkspaceConfig) -> None:
        """Converge durable and live owners independently, persisting first."""

        local_current = self._local_agent(agent_config.agent_id)
        if local_current != agent_config:
            self._persist_agent_config(agent_config)
        current = self._agent_catalog.get(agent_config.agent_id)
        if current is not None and current.config == agent_config:
            return
        self._republish_agent(agent_config)

    def _republish_agent(self, agent_config: AgentWorkspaceConfig) -> None:
        snapshot = self._agent_catalog.publish(agent_config)
        self._session_binder.invalidate_stale(
            agent_config.agent_id,
            current_revision=snapshot.revision,
        )

    def current_agent_payload(self, *, agent_id: str) -> dict[str, object] | None:
        for agent in self._local_config.agents:
            if agent.agent_id != agent_id:
                continue
            payload: dict[str, object] = {
                "display_name": agent.title or agent.agent_id,
                "system_prompt": agent.system_prompt or "",
                "skills": list(agent.skills),
                "tool_allowlist": list(agent.tool_allowlist),
                "group_reply_policy": agent.group_reply_policy or "manual",
                "default_model": agent.default_model,
                "workspace_root": str(agent.workspace_root),
                # feat-379-M2: expose per-agent features/custom_prompt for capabilities reporting
                "features": dict(agent.features),
                "custom_prompt": agent.custom_prompt,
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
        self._base_headers = _im_http_headers(token)
        # Propagate updated headers to any live client instance so in-flight
        # connections also pick up the new token without a full reconnect.
        # Injected test clients (passed via constructor) are updated in-place;
        # self-built clients are rebuilt by _get_client() on the next request
        # if they were previously None (first call) or by headers update here.
        if self._client is not None:
            self._client.headers.update(self._base_headers)

    @staticmethod
    def _default_workspace_root(agent_id: str) -> Path:
        return Path("~/nano-assistant/workspace").expanduser() / agent_id


def _make_workspace_root_factory(
    workspace_base: str | None,
) -> Callable[[str], Path] | None:
    """Build a workspace_root factory rooted at ``workspace_base`` (bugfix-424 / #127).

    When ``workspace_base`` is set, dynamically-created agents (built via IM
    ``agent.create`` without an explicit ``workspace_root``) get their workspace at
    ``<workspace_base>/<agent_id>`` — the same isolation root preset agents use.
    Returns ``None`` when ``workspace_base`` is unset so the caller keeps its legacy
    ``~/nano-assistant/workspace`` default, leaving existing deployments unchanged.

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

def _im_http_headers(token: str | None) -> dict[str, str]:
    headers = {"User-Agent": "nano-multiagent-gateway-bootstrap"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _im_http_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "http":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "ws":
        return f"http://{parsed.netloc}{parsed.path}".rstrip("/")
    if parsed.scheme == "wss":
        return f"https://{parsed.netloc}{parsed.path}".rstrip("/")
    raise ValueError("IM URL must use http(s) or ws(s)")
