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
    """

    run_id: str
    session_id: str
    status: str
    start_sequence: int = 0


# ---------------------------------------------------------------------------
# LLMConfig (决策 5) — catalog + connection + default, with from_env()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMModel:
    """One model entry in an LLMConfig provider.

    Args:
        name: Model identifier (e.g. ``"kimiCoding:K2.6"``).
        extra_request_body: Provider-specific extra request fields (e.g. thinking).
    """

    name: str
    extra_request_body: dict = field(default_factory=dict)


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
    return type of ``get_llm_config`` / ``reconfigure_llm``.

    model stays kernel-level (决策 5 scope A): ``create_session`` does not take a
    model; CLI ``/model`` switches via ``reconfigure_llm``.

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
        / ``reconfigure_llm`` (CLI ``/model``). The active connection is derived
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
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else 600.0,
            default_model=default_model,
            providers=providers,
        )


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
    """

    name: str
    description: str = ""


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
]
