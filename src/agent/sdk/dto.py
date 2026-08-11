"""SDK-owned boundary DTOs for Kernel inputs/outputs (refactor-406 决策 5/6).

The kernel maps its internal ``Session`` / ``RunRecord`` / ``LLMFactoryConfig``
to these frozen, SDK-owned value objects at the boundary so internal refactors
never silently change the public contract and consumers get typed access + IDE
completion. The kernel maps **at the boundary**; core never imports these (no
core→sdk inversion).

Field sets are kept to what products actually consume (取证 in design.md
§现状分析「产品实际消费的 Kernel 出参字段」): SessionInfo →
session_id/title/workspace_root/metadata; RunInfo → run_id/session_id/status;
LLMConfig → connection (provider/model/base_url/api_key/timeout) + catalog
(default_model + providers/models) with ``from_env()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


@dataclass(frozen=True)
class SessionInfo:
    """Result of ``create_session`` / ``fork_session`` (决策 6).

    Args:
        session_id: Stable session identifier.
        title: Optional human-readable title.
        workspace_root: Workspace root where the session JSONL is stored.
        metadata: Session metadata (routing context, agent_features, …).
    """

    session_id: str
    title: str | None = None
    workspace_root: str | None = None
    metadata: dict = field(default_factory=dict)
    # feat-445-M2 #5: present only on a fork result — maps each source message_id to its
    # re-stamped branch message_id, so the caller can realign display-side anchors
    # (e.g. IM's per-bubble kernel_message_id) to the branch session's JSONL uuids.
    fork_id_map: dict[str, str] | None = None


@dataclass(frozen=True)
class RunInfo:
    """Result of ``submit`` / ``get_run`` / ``cancel`` (决策 6).

    Args:
        run_id: Stable run identifier.
        session_id: Session the run belongs to.
        status: Run status string (e.g. ``"queued"``, ``"running"``,
            ``"completed"``, ``"failed"``, ``"cancelled"``). Values match the
            existing run-status vocabulary (``TERMINAL_RUN_STATUSES`` re-exported
            from agent.sdk covers terminal ones).
        start_sequence: Event-stream sequence at which this run's events begin.
            Consumers anchor ``stream(after_sequence=…)`` to it so each turn
            receives exactly this run's events without replaying stale session
            history (the Gateway SSE relay path depends on this).
        injected: True when a ``submit(steer=True)`` was injected into an already
            active run's next round (``run_id`` is that active run; no new run was
            created); False for a freshly created run. Consumers use this to decide
            whether to start their own per-run event loop (bugfix-426 决策1).
    """

    run_id: str
    session_id: str
    status: str
    start_sequence: int = 0
    injected: bool = False


# ---------------------------------------------------------------------------
# LLMConfig (决策 5) — catalog + connection + default, with from_env()
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelReasoningCapability:
    """Describe one model's safe public reasoning capability.

    Args:
        kind: Either ``"fixed"`` or ``"selectable"``.
        default: Recommended value for a selectable capability.
        levels: Ordered selectable values exposed to users.
    """

    kind: str
    default: str | None = None
    levels: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        """Return the JSON-safe public descriptor."""

        if self.kind == "fixed":
            return {"kind": "fixed"}
        return {
            "kind": "selectable",
            "default": self.default or "",
            "levels": list(self.levels),
        }

    @classmethod
    def from_payload(
        cls, value: object, *, field_name: str
    ) -> "ModelReasoningCapability | None":
        """Parse one safe reasoning descriptor from a decoded payload.

        Args:
            value: ``None``, ``"fixed"``, or a mapping with ``default`` and
                ordered ``levels``.
            field_name: Input path used in a validation error.

        Returns:
            Parsed descriptor, or ``None`` when no descriptor was declared.

        Raises:
            ValueError: When the descriptor is malformed.
        """

        if value is None:
            return None
        if value == "fixed":
            return cls(kind="fixed")
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name} must be 'fixed' or a mapping")
        default = value.get("default")
        if not isinstance(default, str) or not default.strip():
            raise ValueError(f"{field_name}.default must be a non-empty string")
        raw_levels = value.get("levels")
        if not isinstance(raw_levels, list) or not raw_levels:
            raise ValueError(f"{field_name}.levels must be a non-empty list")
        levels: list[str] = []
        for index, raw_level in enumerate(raw_levels):
            if not isinstance(raw_level, str) or not raw_level.strip():
                raise ValueError(
                    f"{field_name}.levels[{index}] must be a non-empty string"
                )
            level = raw_level.strip()
            if level in levels:
                raise ValueError(f"{field_name}.levels must not contain duplicates")
            levels.append(level)
        normalized_default = default.strip()
        if normalized_default not in levels:
            raise ValueError(f"{field_name}.default must be one of {field_name}.levels")
        return cls(
            kind="selectable", default=normalized_default, levels=tuple(levels)
        )


@dataclass(frozen=True)
class LLMModel:
    """One model entry in an LLMConfig provider.

    Args:
        name: Model identifier (e.g. ``"kimiCoding:K2.6"``).
        extra_request_body: Provider-specific extra request fields (e.g. thinking).
        context_window: Per-model context window driving compaction边界 (feat-436);
            None → 内核默认上限.
        reasoning: Safe fixed/selectable reasoning capability exposed to product
            controls. ``None`` means no selectable reasoning is declared.
    """

    name: str
    extra_request_body: dict = field(default_factory=dict)
    context_window: int | None = None
    reasoning: ModelReasoningCapability | None = None


@dataclass(frozen=True)
class LLMProvider:
    """One provider entry in an LLMConfig catalog.

    Args:
        name: Provider name (e.g. ``"anthropic"``, ``"openai_compat"``).
        base_url: Provider base URL.
        models: Ordered models offered by this provider.
    """

    name: str
    base_url: str
    models: tuple[LLMModel, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LLMConfig:
    """SDK-owned LLM configuration: catalog + connection + default (决策 5).

    Passed to ``build_kernel(llm=…)`` to install the provider/model catalog and
    active connection; the model registry is initialised inside ``build_kernel``
    (no consumer-side ``init_model_registry`` ordering obligation). Also the
    return type of ``get_llm_config``.

    bugfix-429: model is per-run now — ``submit(model=...)`` carries the model the
    consumer selects each turn; the kernel holds no conversational default and
    ``reconfigure_llm`` is retired. ``get_llm_config`` still reports the build-time
    active connection (provider/base_url/default catalog) for selectors.

    Args:
        provider: Active provider name.
        model: Active model name.
        base_url: Active provider base URL.
        api_key: Optional API key for the active connection.
        timeout_seconds: Request timeout.
        default_model: Catalog default model (for selectors / capability report).
        providers: Provider/model catalog.
    """

    provider: str
    model: str
    base_url: str
    api_key: str | None = None
    timeout_seconds: float = 600.0
    default_model: str | None = None
    providers: tuple[LLMProvider, ...] = field(default_factory=tuple)

    # Env-resolution defaults (mirror the legacy LLMFactoryConfig field defaults
    # so a fully-unset environment still yields a usable local-proxy connection).
    _ENV_DEFAULT_PROVIDER = "anthropic"
    _ENV_DEFAULT_MODEL = "codex_oauth:gpt-5.5"
    _ENV_DEFAULT_BASE_URL = "http://127.0.0.1:4000"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Build an LLMConfig connection purely from environment variables.

        Resolves provider/model/base_url/api_key/timeout from ``NANO_MULTIAGENT_*``
        env vars **without** touching the model registry — so a consumer can call
        this to build the ``llm=`` argument *before* ``build_kernel`` initialises
        the registry (决策 5: registry init is build_kernel's job, no consumer-side
        ordering obligation; the old ``LLMFactoryConfig.from_env`` registry
        fallback was the footgun this removes). The catalog
        (``providers``/``default_model``) is empty here; consumers that have a
        catalog (e.g. from gateway config) construct LLMConfig directly with it.

        Returns:
            LLMConfig carrying the env-resolved active connection.
        """
        provider = os.getenv("NANO_MULTIAGENT_LLM_PROVIDER", cls._ENV_DEFAULT_PROVIDER)
        model = os.getenv("NANO_MULTIAGENT_LLM_MODEL", cls._ENV_DEFAULT_MODEL)
        base_url = os.getenv("NANO_MULTIAGENT_LLM_BASE_URL", cls._ENV_DEFAULT_BASE_URL)
        timeout_seconds = float(os.getenv("NANO_MULTIAGENT_LLM_TIMEOUT_SECONDS", "30"))
        api_key = os.getenv("NANO_MULTIAGENT_LLM_API_KEY")
        return cls(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            default_model=model,
        )

    @classmethod
    def from_payload(
        cls,
        payload: "object",
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "LLMConfig":
        """Build an LLMConfig (catalog + active connection) from an LLMConfigPayload.

        Consumers that already have a provider/model catalog — coding_cli (env /
        CLI args) and the gateway (config.yaml) — convert it here so the catalog
        flows into ``build_kernel(llm=…)`` and stays available for ``list_models``
        and per-run model routing (bugfix-429). The active connection is derived
        from the payload's ``default_model`` and the provider that owns it.

        Args:
            payload: An ``LLMConfigPayload`` (duck-typed: ``default_model`` +
                ``providers`` each with ``name`` / ``base_url`` / ``models``).
            api_key: Optional API key for the active connection.
            timeout_seconds: Optional request timeout (defaults to the field default).

        Returns:
            LLMConfig carrying the full catalog and the resolved active connection.
        """
        default_model = getattr(payload, "default_model")
        raw_providers = tuple(getattr(payload, "providers", ()) or ())
        providers = tuple(
            LLMProvider(
                name=p.name,
                base_url=p.base_url or "",
                models=tuple(
                    LLMModel(
                        name=m.name,
                        extra_request_body=dict(m.extra_request_body or {}),
                        # feat-436: 鸭子类型读 PA payload 的 context_window（旧 payload 无此属性→None）。
                        context_window=getattr(m, "context_window", None),
                        reasoning=getattr(m, "reasoning", None),
                    )
                    for m in (p.models or ())
                ),
            )
            for p in raw_providers
        )
        # Resolve the active provider/base_url from the provider that owns the
        # default_model; fall back to the first provider so a usable connection
        # is always produced.
        active_provider = providers[0] if providers else None
        for prov in providers:
            if any(m.name == default_model for m in prov.models):
                active_provider = prov
                break
        provider_name = active_provider.name if active_provider else ""
        base_url = active_provider.base_url if active_provider else ""
        return cls(
            provider=provider_name,
            model=default_model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 600.0,
            default_model=default_model,
            providers=providers,
        )

    @classmethod
    def from_catalog(
        cls,
        *,
        default_model: str,
        providers: "tuple[LLMProvider, ...]",
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "LLMConfig":
        """Build an LLMConfig from SDK-owned catalog parts (决策 5/6).

        The SDK-owned construction path: consumers assemble ``LLMProvider`` /
        ``LLMModel`` objects themselves (no internal wire-payload type) and hand them
        here. The active connection is resolved from the provider owning
        ``default_model`` (falling back to the first provider).

        Args:
            default_model: Catalog default + active model id.
            providers: SDK-owned provider/model catalog.
            api_key: Optional API key for the active connection.
            timeout_seconds: Optional request timeout.

        Returns:
            LLMConfig with the catalog and resolved active connection.
        """
        active_provider = providers[0] if providers else None
        for prov in providers:
            if any(m.name == default_model for m in prov.models):
                active_provider = prov
                break
        return cls(
            provider=active_provider.name if active_provider else "",
            model=default_model,
            base_url=active_provider.base_url if active_provider else "",
            api_key=api_key,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 600.0,
            default_model=default_model,
            providers=providers,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> "LLMConfig":
        """Build an LLMConfig from a gateway-style LLM catalog JSON string (决策 5).

        Parses the ``{default_model, providers:[{name, base_url, models:[{name,
        extra_request_body}]}]}`` wire schema (the same one the gateway serializes to
        ``NANO_MULTIAGENT_LLM_CONFIG_JSON``) directly into SDK-owned types — no
        consumer-visible internal payload class.

        Args:
            raw: JSON catalog string.
            api_key: Optional API key for the active connection.
            timeout_seconds: Optional request timeout.

        Raises:
            ValueError: When the JSON is not an object or lacks ``default_model``.
            json.JSONDecodeError: When ``raw`` is not valid JSON.

        Returns:
            LLMConfig with the parsed catalog and resolved active connection.
        """
        import json  # noqa: PLC0415

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM catalog JSON must be an object")
        if "default_model" not in data:
            raise ValueError("LLM catalog JSON missing 'default_model'")
        providers = tuple(
            LLMProvider(
                name=p["name"],
                base_url=p.get("base_url") or "",
                models=tuple(
                    LLMModel(
                        name=m["name"],
                        extra_request_body=dict(m.get("extra_request_body") or {}),
                        context_window=m.get("context_window"),
                        reasoning=ModelReasoningCapability.from_payload(
                            m.get("reasoning"),
                            field_name=(
                                f"providers[{provider_index}].models["
                                f"{model_index}].reasoning"
                            ),
                        ),
                    )
                    for model_index, m in enumerate(p.get("models", []))
                ),
            )
            for provider_index, p in enumerate(data.get("providers", []))
        )
        return cls.from_catalog(
            default_model=data["default_model"],
            providers=providers,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )


class ModelReasoningCatalog:
    """Resolve safe per-model reasoning capabilities from an SDK LLM catalog.

    Args:
        llm_config: SDK-owned catalog carrying model reasoning descriptors.
    """

    def __init__(self, llm_config: LLMConfig) -> None:
        self._default_model = llm_config.default_model or llm_config.model
        self._capabilities: dict[str, ModelReasoningCapability | None] = {}
        for provider in llm_config.providers:
            for model in provider.models:
                self._capabilities[model.name] = model.reasoning

    def capability_for(self, model: str) -> ModelReasoningCapability | None:
        """Return one model's descriptor, or ``None`` when it has none."""

        return self._capabilities.get(model)

    def validate(self, model: str | None, selected_effort: str | None) -> None:
        """Validate one model and selected effort pairing.

        Raises:
            ValueError: When the model is unknown or the effort is unsupported.
        """

        resolved_model = model or self._default_model
        if resolved_model not in self._capabilities:
            raise ValueError(f"unknown model: {resolved_model}")
        capability = self._capabilities[resolved_model]
        if capability is None or capability.kind == "fixed":
            if selected_effort is not None:
                raise ValueError(
                    f"model {resolved_model!r} does not accept reasoning_effort"
                )
            return
        if selected_effort is not None and selected_effort not in capability.levels:
            raise ValueError(
                "reasoning_effort "
                f"{selected_effort!r} is not supported by model {resolved_model!r}"
            )

    def resolve(self, model: str, selected_effort: str | None) -> str | None:
        """Resolve a valid selected effort to its effective provider value."""

        self.validate(model, selected_effort)
        capability = self._capabilities[model]
        if capability is None or capability.kind == "fixed":
            return None
        return selected_effort or capability.default


# ---------------------------------------------------------------------------
# Capability-query DTOs (决策 4) — list_models / list_tools / list_features / list_skills
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelInfo:
    """One model in ``list_models`` output.

    Args:
        name: Model identifier.
        provider: Owning provider name.
        is_default: Whether this is the catalog default model.
    """

    name: str
    provider: str
    is_default: bool = False


@dataclass(frozen=True)
class ToolInfo:
    """One tool in ``list_tools`` output (name + description).

    Args:
        name: Tool name.
        description: Tool description.
    """

    name: str
    description: str


@dataclass(frozen=True)
class FeatureInfo:
    """One kernel feature in ``list_features`` output (决策 3/4).

    Only the kernel's two general features (memory_curation / skill_creation) are
    reported; product-specific toggles (heartbeat/cron) are an application-layer
    projection, not kernel features.

    Args:
        key: Feature key (e.g. ``"memory_curation"``).
        default_on: Product-level default for the toggle.
        requires_tool: Tool that must be in the session toolset for the feature's
            guidance to render, or None.
    """

    key: str
    default_on: bool
    requires_tool: str | None = None


@dataclass(frozen=True)
class SkillInfo:
    """One skill in ``list_skills`` output.

    Args:
        name: Skill name.
        description: Skill description.
        location: Absolute path to the skill's SKILL.md, or None when unknown.
            Lets consumers distinguish same-named skills at different paths (feat-430).
    """

    name: str
    description: str = ""
    location: str | None = None


class WorkflowControlAction(StrEnum):
    """Supported Workflow control operations."""

    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RESTART_AGENT = "restart_agent"


class WorkflowSaveScope(StrEnum):
    """Supported saved Workflow destination scopes."""

    PROJECT = "project"
    PERSONAL = "personal"


@dataclass(frozen=True)
class WorkflowPhaseInfo:
    """Describe one phase in a Workflow snapshot."""

    title: str
    detail: str = ""
    status: str = "pending"
    agent_call_ids: tuple[str, ...] = ()
    usage: Mapping[str, int] | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class WorkflowAgentInfo:
    """Describe one logical child Agent call in a Workflow snapshot."""

    agent_call_id: str
    start_ordinal: int
    status: str
    prompt: str
    label: str | None = None
    phase: str | None = None
    terminal_ordinal: int | None = None
    result: Any = None
    error: str | None = None
    usage: Mapping[str, int] | None = None
    duration_ms: int | None = None
    session_id: str | None = None
    transcript_path: str | None = None
    worktree_path: str | None = None


@dataclass(frozen=True)
class WorkflowRunInfo:
    """Expose one complete, revisioned Workflow run snapshot."""

    run_id: str
    task_id: str
    parent_session_id: str
    revision: int
    status: str
    name: str
    description: str
    current_phase: str | None = None
    phases: tuple[WorkflowPhaseInfo, ...] = ()
    agents: tuple[WorkflowAgentInfo, ...] = ()
    logs: tuple[str, ...] = ()
    usage: Mapping[str, int] | None = None
    duration_ms: int | None = None
    size_guideline: str = "medium"
    large_warning: str | None = None
    script_path: str = ""
    transcript_dir: str = ""
    resumed_from: str | None = None
    result: Any = None
    error: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SavedWorkflowInfo:
    """Describe one discovered or newly saved named Workflow."""

    name: str
    scope: str
    path: str
    description: str = ""
    namespace: str | None = None


__all__ = [
    "SessionInfo",
    "RunInfo",
    "LLMConfig",
    "LLMProvider",
    "LLMModel",
    "ModelInfo",
    "ToolInfo",
    "FeatureInfo",
    "SkillInfo",
    "WorkflowControlAction",
    "WorkflowSaveScope",
    "WorkflowPhaseInfo",
    "WorkflowAgentInfo",
    "WorkflowRunInfo",
    "SavedWorkflowInfo",
]
