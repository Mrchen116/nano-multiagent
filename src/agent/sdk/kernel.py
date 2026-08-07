"""agent.sdk.Kernel — in-process agent kernel assembly and interface.

build_kernel() is the composition root: it assembles platform components into
a ready-to-use Kernel without exposing any HTTP/FastAPI surface.

Design (refactor-387 M1, refactor-462):
- Mirrors create_app() assembly logic with FastAPI/routes/middleware removed.
- One shared AgentEngine and provider-client graph serves stable conversations;
  per-conversation mutable state remains in ConversationState.
- Permission flow: AgentEngine hook context races optional can_use_tool
  callback against a PermissionBroker future; gateway resolves the future
  externally via Kernel.submit_permission_decision (feat-394-M14).
- KernelExecutor owns one background loop for every typed target.
"""

from __future__ import annotations

import asyncio
import inspect
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable, Sequence

from agent.core.agent.runtime import AgentEngine
from agent.core.events.hub import EventStreamHub
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.context import HookContext
from agent.core.hooks.runner import HookRunner, log_hook_diagnostics
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.interfaces import LLMClient
from agent.core.observability.exporters.console import ConsoleTracer
from agent.core.observability.tracing import set_tracer
from agent.core.runs.registry import RunStatus, RunsRegistry
from agent.core.runs.executor import KernelExecutor
from agent.core.runs.origin import RunOrigin
from agent.core.session.conversation import ConversationSession
from agent.core.session.directory import SessionDirectory
from agent.core.session.jsonl_files import JsonlSessionFiles
from agent.core.session.jsonl_writer import JsonlWriter
from agent.core.session.types import (
    ExternalMessage,
    INTERNAL_RUNTIME_KEY,
    NewSession,
    PromptSlotSeed,
    PromptSlotText,
    SessionRef,
)
from agent.core.utils.time import utc_now_iso as _utc_now_iso
from agent.core.workspace import WorkspaceExecutionScope, WorkspaceLayout
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.config.auto_mode import AutoModeConfig, load_auto_mode_config
from agent.platform.hooks.loader import build_hook_registry, load_hooks_into_registry
from agent.platform.hooks.session_events import set_session_event_publisher_factory
from agent.platform.llm.factory import create_llm_client as _platform_create_llm_client
from agent.platform.permissions.broker import (
    PermissionBroker,
    PermissionDecision,
)

from agent.sdk.dto import (
    FeatureInfo,
    LLMConfig,
    ModelInfo,
    RunInfo,
    SessionInfo,
    SkillInfo,
    ToolInfo,
)
from agent.sdk.prompt import PromptSlots
from agent.sdk.runtime import (
    SessionReconfigureResult,
    SessionRuntimeConfig,
    SessionRuntimeIdentity,
    SessionRuntimeState,
    identify_runtime,
    runtime_metadata,
)

if TYPE_CHECKING:
    pass

# Callable type for the permission strategy injected by consumers.
# Mirrors CC CanUseToolFn: given (tool_name, tool_input, context) → PermissionDecision.
CanUseToolFn = Callable[[str, Any, Any], Awaitable[PermissionDecision]]


@dataclass
class _KernelComponents:
    """Hold all assembled platform components for a Kernel instance."""

    engine_services: AgentEngine
    directory: SessionDirectory
    executor: KernelExecutor
    tool_registry: Any
    runs_registry: RunsRegistry
    event_hub: EventStreamHub
    permission_broker: PermissionBroker
    hook_registry: HookRegistry
    hook_runner: HookRunner
    stop_all_foreground: Callable[[], None]
    finalize_resources: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class _SessionSubagentControl:
    """Expose only the current conversation's subagent capabilities to AgentTool."""

    ref: SessionRef
    directory: SessionDirectory
    files: JsonlSessionFiles
    engine: AgentEngine

    @property
    def workspace_root(self) -> Path:
        return self.ref.workspace_root

    def resolve_run_model(self) -> str | None:
        return self.engine.resolve_run_model(self.ref.session_id)

    def resolve_available_skills(
        self,
        workspace_root: Path,
        *,
        include_names: Sequence[str] | None = None,
    ) -> tuple[Any, ...]:
        return self.engine.resolve_available_skills(
            workspace_root, include_names=include_names
        )

    def create_subagent(
        self,
        *,
        workspace_root: Path,
        skills: Sequence[str] | None,
        metadata: dict[str, Any],
        parent_session_id: str | None,
        tool_allowlist: Sequence[str] | None = None,
        prompt_seed: PromptSlotSeed | None = None,
    ) -> SessionRef:
        """Create one child session for the ``agent`` tool's new-agent path.

        feat-474: unlike the legacy call (metadata + ``skills`` only), the new
        path always supplies an explicit, already-resolved ``tool_allowlist``
        (never bare ``None`` — a ``None`` here would let the child inherit the
        full registry, wider than any parent) and a type-specific
        ``prompt_seed`` (core-owned, not the sdk ``PromptSlots`` the public
        session surface uses — this internal control plane stays sdk-internal
        so ``platform``/``AgentTool`` never needs to import ``agent.sdk``).

        ``skills`` keeps its three states verbatim (``None`` / non-empty /
        empty tuple) — folding an empty sequence to ``None`` here would widen
        a deliberately empty parent skill set for the child (bugfix target of
        this change; the legacy ``if skills else None`` did exactly that).

        Args:
            workspace_root: Workspace root for the child session's JSONL.
            skills: The child's skill visibility, passed through unfolded.
            metadata: Caller-supplied session metadata (e.g. ``agent_type``).
            parent_session_id: Must equal this control's own session id.
            tool_allowlist: Explicit tool names for the child; ``None`` only
                for callers that intentionally want the registry default.
            prompt_seed: Core ``PromptSlotSeed`` for the child's dedicated
                system-prompt slots; ``None`` falls back to an empty seed.
        """

        if parent_session_id != self.ref.session_id:
            raise ValueError("subagent parent must be the active conversation")
        conversation = self.directory.create(
            NewSession(
                workspace_root=workspace_root,
                skills=tuple(skills) if skills is not None else None,
                tool_allowlist=tuple(tool_allowlist)
                if tool_allowlist is not None
                else None,
                metadata=metadata,
                parent_session_id=self.ref.session_id,
                prompt_seed=prompt_seed
                if prompt_seed is not None
                else PromptSlotSeed(),
            )
        )
        return conversation.ref

    def list_parent_enabled_tool_names(self) -> tuple[str, ...]:
        """Return this session's active-run resolved tool names (narrow window).

        feat-474: used by ``AgentTool`` only when the parent session's
        persisted ``tool_allowlist`` is ``None`` (product-default case) — the
        persisted value, when non-``None``, is read directly via
        ``directory.get(ref).tool_allowlist`` instead, so this delegates to
        the engine rather than duplicating its default-tool-id resolution.
        """

        return self.engine.resolve_active_enabled_tool_names(self.ref.session_id)

    def output_path(
        self,
        session_id: str,
        *,
        workspace_root: Path,
        parent_session_id: str,
    ) -> Path:
        return self.files.resolve_path(
            SessionRef(
                session_id=session_id,
                workspace_root=workspace_root,
                parent_session_id=parent_session_id,
            )
        )

    def find_subagent(self, agent_id: str) -> dict[str, Any] | None:
        found = self.directory.find_by_metadata(
            workspace_root=self.ref.workspace_root,
            parent_session_id=self.ref.session_id,
            query={"kind": "subagent", "agent_id": agent_id},
        )
        if found is None:
            return None
        snapshot = self.directory.get(found)
        if snapshot is None:
            return None
        return {
            "session_id": found.session_id,
            "metadata": dict(snapshot.metadata),
            "output_path": self.files.resolve_path(found),
        }


def build_kernel(
    *,
    # 2-layer surface (refactor-406 决策 1/2/5) — the sole composition entry.
    llm: LLMConfig | None = None,
    tool_approval_model: str | None = None,
    tools: Sequence[Any] | None = None,
    hooks: Sequence[Callable[[Any], None]] | None = None,
    workspace_config_dirname: str | None = None,
    global_config_root: Path | None = None,
    can_use_tool: CanUseToolFn | None = None,
    repo_root: Path | None = None,
    skill_search_roots: Sequence[Path] = (),
    global_skill_root: Path | None = None,
    pa_skill_root: Path | None = None,
    tool_search_roots: Sequence[Path] = (),
    hook_search_roots: Sequence[Path] = (),
    # Internal escape hatch for tests: skip LLM client construction and use
    # this fake instead.  Not part of the public API.
    _llm_client_override: LLMClient | None = None,
) -> "Kernel":
    """Assemble an in-process Kernel — composition root for any application (决策 1/2/5).

    ``build_kernel(llm=LLMConfig, tools=[native objects], hooks=[setup callables],
    can_use_tool=…, workspace_config_dirname=…)`` builds a product-neutral shared base:
    the model registry is initialised internally from ``llm`` (no consumer-side
    ``init_model_registry``), the consumer's native tool objects are registered into the
    kernel tool catalog, and the prompt template is the kernel skeleton (product text
    enters per-session via ``create_session(prompt=PromptSlots)``).

    refactor-406-M1 R7: the legacy ``product_profile=`` / ``llm_config=`` path
    (``bootstrap_product``) is removed now that both consumers (coding_cli /
    personal_assistant) build through this 2-layer surface.

    Args:
        llm: SDK-owned LLM config. Catalog + connection + default.
        tool_approval_model: Optional registered model used by automatic tool
            approval classification. ``None`` reuses the current run model.
        tools: Native tool objects satisfying the SDK ``Tool`` Protocol.
        hooks: ``setup(hooks)`` callables registered into the hook registry.
        workspace_config_dirname: Per-workspace config dir name (e.g. ``.nanocode``)
            governing session JSONL / memory / skill layout.
        global_config_root: Optional consumer-owned global auto-mode config root.
            Omitted means auto-mode reads no deployment-level global config.
        can_use_tool: Optional async permission callback; None → IM card flow.
        repo_root: Repository/workspace root for tool/hook discovery.
        skill_search_roots: Deployment-level skill directories shared across every
            workspace (e.g. a product's global ``~/.<product>/skills`` and compat
            roots). ``list_skills(workspace_root)`` searches the per-workspace
            ``<workspace_root>/<workspace_config_dirname>/skills`` FIRST, then these
            roots in order, deduplicating by directory. The kernel stays
            product-neutral: it only searches the roots it is handed (a deployment
            path convention the consumer factory owns — same pattern as
            ``workspace_config_dirname``). Empty → workspace-only skills.
        tool_search_roots: Deployment-level user tool-plugin directories shared across
            workspaces (e.g. ``~/.<product>/tools``), discovered in addition to the
            workspace ``<repo_root>/.nano/tools``. Same consumer-supplied-roots pattern
            as ``skill_search_roots`` — no ConfigResolver. Empty → workspace-only.
        hook_search_roots: Deployment-level user hook directories shared across
            workspaces (e.g. ``~/.<product>/hooks``), discovered in addition to the
            workspace ``<repo_root>/.nano/hooks``. Same pattern. Empty → workspace-only.
        _llm_client_override: Test-only LLM client.

    Returns:
        A fully assembled, ready-to-use Kernel.

    Raises:
        ValueError: If ``llm`` is missing, or ``tool_approval_model`` is empty
            or is not registered in the supplied LLM catalog.
    """
    if llm is None:
        raise ValueError("build_kernel requires llm= (2-layer surface)")
    resolved_tool_approval_model = _validate_tool_approval_model(
        llm, tool_approval_model
    )
    return _build_kernel_base(
        llm=llm,
        tool_approval_model=resolved_tool_approval_model,
        tools=list(tools or ()),
        hooks=list(hooks or ()),
        workspace_config_dirname=workspace_config_dirname or ".nano",
        global_config_root=global_config_root,
        can_use_tool=can_use_tool,
        repo_root=repo_root,
        skill_search_roots=tuple(skill_search_roots),
        global_skill_root=global_skill_root or pa_skill_root,
        tool_search_roots=tuple(tool_search_roots),
        hook_search_roots=tuple(hook_search_roots),
        _llm_client_override=_llm_client_override,
    )


def _validate_tool_approval_model(llm: LLMConfig, model: str | None) -> str | None:
    """Validate an explicit classifier model against the Kernel catalog."""

    if model is None:
        return None
    normalized = model.strip()
    if not normalized:
        raise ValueError("tool_approval_model must be a non-empty string")
    available = (
        {item.name for provider in llm.providers for item in provider.models}
        if llm.providers
        else {llm.model}
    )
    if normalized not in available:
        choices = ", ".join(sorted(available)) or "(none)"
        raise ValueError(
            f"tool_approval_model '{normalized}' is not registered (available: {choices})"
        )
    return normalized


def _init_model_registry_from_llm_config(llm: LLMConfig) -> None:
    """Initialise the process model registry from an SDK ``LLMConfig`` (决策 5).

    This absorbs the old "consumer must call init_model_registry first" footgun:
    build_kernel owns registry init. When the LLMConfig carries an explicit
    provider/model catalog, that is used; otherwise a single-provider catalog is
    synthesised from the active connection so a from_env()-only config still
    yields a usable registry (the env path has no catalog).

    Idempotent within a process: a re-init with the same default is tolerated by
    resetting first (mirrors the test conftest's reset/re-init discipline).
    """
    from agent.core.llm.config import (  # noqa: PLC0415
        LLMConfigPayload,
        LLMModelPayload,
        LLMProviderPayload,
    )
    from agent.core.llm.model_registry import (  # noqa: PLC0415
        _reset_for_tests,
        init_model_registry,
    )

    if llm.providers:
        providers = tuple(
            LLMProviderPayload(
                name=p.name,
                base_url=p.base_url,
                models=tuple(
                    LLMModelPayload(
                        name=m.name,
                        extra_request_body=m.extra_request_body or None,
                        context_window=m.context_window,
                    )
                    for m in p.models
                ),
            )
            for p in llm.providers
        )
        default_model = llm.default_model or llm.model
    else:
        # No catalog (e.g. LLMConfig.from_env()): synthesise a one-provider,
        # one-model catalog from the active connection so registry lookups resolve.
        providers = (
            LLMProviderPayload(
                name=llm.provider,
                base_url=llm.base_url,
                models=(LLMModelPayload(name=llm.model, extra_request_body=None),),
            ),
        )
        default_model = llm.model

    payload = LLMConfigPayload(default_model=default_model, providers=providers)
    # Re-init is required because the catalog can differ per kernel; reset then init.
    _reset_for_tests()
    init_model_registry(payload)


def _llm_config_to_factory_config(llm: LLMConfig) -> LLMFactoryConfig:
    """Map an SDK ``LLMConfig`` to the internal ``LLMFactoryConfig`` connection."""
    return LLMFactoryConfig(
        provider=llm.provider,
        model=llm.model,
        base_url=llm.base_url,
        api_key=llm.api_key,
        timeout_seconds=llm.timeout_seconds,
    )


# ---------------------------------------------------------------------------
# Boundary DTO mapping (决策 6): internal Session / RunRecord / LLMFactoryConfig
# → SDK-owned SessionInfo / RunInfo / LLMConfig at the Kernel boundary.
# ---------------------------------------------------------------------------


def _to_session_info(session: Any) -> SessionInfo:
    """Map an internal Session to the SDK-owned SessionInfo boundary DTO."""
    workspace_root = getattr(session, "workspace_root", None)
    metadata = getattr(session, "metadata", None) or {}
    return SessionInfo(
        session_id=session.session_id,
        title=getattr(session, "title", None) or metadata.get("title"),
        workspace_root=str(workspace_root) if workspace_root is not None else None,
        metadata=dict(metadata),
    )


def _to_prompt_seed(prompt: PromptSlots | None) -> PromptSlotSeed:
    """Copy SDK PromptSlots into the core-owned persistent seed structure."""

    if prompt is None:
        return PromptSlotSeed()

    def _items(name: str) -> tuple[PromptSlotText, ...]:
        return tuple(
            PromptSlotText(name=item.name, text=item.text)
            for item in getattr(prompt, name)
        )

    return PromptSlotSeed(
        head=_items("head"),
        body=_items("body"),
        custom=_items("custom"),
        tail=_items("tail"),
    )


def _to_run_info(record: Any, *, injected: bool = False) -> RunInfo:
    """Map an internal RunRecord to the SDK-owned RunInfo boundary DTO.

    ``injected`` is set by the steer path when the message was injected into an
    already active run rather than starting a new one (bugfix-426 决策1).
    """
    status = getattr(record, "status", None)
    return RunInfo(
        run_id=record.run_id,
        session_id=record.session_id,
        # status may be an enum (with .value) or already a string.
        status=getattr(status, "value", status) if status is not None else "",
        start_sequence=int(getattr(record, "start_sequence", 0) or 0),
        injected=injected,
    )


def _factory_config_to_llm_config(
    cfg: Any, *, catalog: LLMConfig | None = None
) -> LLMConfig:
    """Map the internal LLMFactoryConfig to the SDK-owned LLMConfig boundary DTO.

    Preserves the catalog (providers / default_model) from the build-time
    ``catalog`` when available, so ``get_llm_config`` carries the full provider
    list, not just the active connection.
    """
    return LLMConfig(
        provider=getattr(cfg, "provider", ""),
        model=getattr(cfg, "model", ""),
        base_url=getattr(cfg, "base_url", ""),
        api_key=getattr(cfg, "api_key", None),
        timeout_seconds=getattr(cfg, "timeout_seconds", 600.0),
        default_model=catalog.default_model
        if catalog is not None
        else getattr(cfg, "model", ""),
        providers=catalog.providers if catalog is not None else (),
    )


class _SearchRootsResolver:
    """Minimal duck resolver for build_hook_registry (M3fix #2).

    Satisfies the hook loader's ``_HookRootResolver`` Protocol (``user_hook_roots``)
    from consumer-supplied deployment roots — NOT a ConfigResolver. ``user_hook_roots()``
    returns the per-workspace ``.nano/hooks`` dir FIRST then the deployment ``extra_roots``,
    deduped, so the loader discovers both the workspace dir (unchanged behavior) and the
    user-level dirs. Same model as ``skill_search_roots``: the consumer factory owns these
    product paths.

    Only the hook registry uses a resolver; the tool path loads tool_search_roots directly
    via ``_load_tools_from_single_dir`` in ``_build_kernel_base`` (no resolver indirection),
    so no ``user_tool_roots`` is provided here.
    """

    def __init__(self, *, workspace_dir: Path, extra_roots: tuple[Path, ...]) -> None:
        ordered: list[Path] = [workspace_dir.expanduser().resolve()]
        for root in extra_roots:
            resolved = Path(root).expanduser().resolve()
            if resolved not in ordered:
                ordered.append(resolved)
        self._roots = tuple(ordered)

    def user_hook_roots(self) -> tuple[Path, ...]:
        return self._roots


class _SessionCapabilityResolver:
    """Build and cache immutable workspace capabilities for one shared Kernel."""

    def __init__(
        self,
        *,
        workspace_config_dirname: str,
        global_config_root: Path | None,
        base_tool_registry: Any,
        base_hook_registry: HookRegistry,
        llm_client: LLMClient | None,
        skill_batch_review_enqueue: Callable[[Any], bool],
    ) -> None:
        self._workspace_config_dirname = workspace_config_dirname
        self._global_config_root = (
            global_config_root.expanduser().resolve()
            if global_config_root is not None
            else None
        )
        self._base_tool_registry = base_tool_registry
        self._base_hook_registry = base_hook_registry
        self._llm_client = llm_client
        self._skill_batch_review_enqueue = skill_batch_review_enqueue
        self._scopes: dict[Path, WorkspaceExecutionScope] = {}

    def scope_for(self, workspace_root: Path) -> WorkspaceExecutionScope:
        """Return the first-use snapshot for one canonical workspace root."""

        layout = WorkspaceLayout(
            workspace_root=workspace_root,
            config_dirname=self._workspace_config_dirname,
        )
        cached = self._scopes.get(layout.workspace_root)
        if cached is not None:
            return cached

        from agent.core.tools.base import ToolContext  # noqa: PLC0415
        from agent.core.tools.result_budget import ToolResultCompressor  # noqa: PLC0415
        from agent.platform.tools.builtins.bash_policy import (  # noqa: PLC0415
            load_bash_policy_overrides_at,
        )
        from agent.platform.tools.loader import _load_tools_from_single_dir  # noqa: PLC0415
        from agent.platform.tools.safety import load_tool_safety_config  # noqa: PLC0415

        hook_registry = self._base_hook_registry.clone(share_extension_state=True)
        load_hooks_into_registry(
            registry=hook_registry,
            directory=layout.hooks,
            source="workspace",
        )
        hook_runner = HookRunner(registry=hook_registry)
        context = ToolContext.create(
            repo_root=layout.workspace_root,
            safety_config=load_tool_safety_config(repo_root=layout.workspace_root),
            llm_client=self._llm_client,
            skill_batch_review_enqueue=self._skill_batch_review_enqueue,
        )
        tool_registry = self._base_tool_registry.clone_for(
            context=context,
            hook_runner=hook_runner,
        )
        _load_tools_from_single_dir(
            tool_root=layout.tools,
            registry=tool_registry,
            replace=True,
        )
        scope = WorkspaceExecutionScope(
            layout=layout,
            tool_registry=tool_registry,
            hook_runner=hook_runner,
            tool_result_compressor=ToolResultCompressor(layout.tool_results),
            bash_policy_overrides=load_bash_policy_overrides_at(layout.policy),
            auto_mode_config_loader=lambda: load_auto_mode_config(
                global_config_dir=self._global_config_root,
                workspace_config_dir=layout.config_root,
            ),
        )
        self._scopes[layout.workspace_root] = scope
        return scope


def _build_kernel_base(
    *,
    llm: LLMConfig,
    tool_approval_model: str | None,
    tools: list[Any],
    hooks: list[Callable[[Any], None]],
    workspace_config_dirname: str,
    global_config_root: Path | None,
    can_use_tool: CanUseToolFn | None,
    repo_root: Path | None,
    skill_search_roots: tuple[Path, ...] = (),
    global_skill_root: Path | None = None,
    pa_skill_root: Path | None = None,
    tool_search_roots: tuple[Path, ...] = (),
    hook_search_roots: tuple[Path, ...] = (),
    _llm_client_override: LLMClient | None,
) -> "Kernel":
    """Assemble the product-neutral shared base (new 2-layer path, 决策 1/2/5/8).

    No ProductProfile, no bootstrap_product: the model registry is initialised
    from ``llm``, the prompt template is the kernel skeleton, and the consumer's
    native tool objects + hook setups are registered directly.
    """
    from agent.core.agent.prompt_sections.skeleton import (  # noqa: PLC0415
        build_kernel_prompt_skeleton,
    )
    from agent.platform.tools.builtins import register_builtin_tools  # noqa: PLC0415
    from agent.platform.hooks.tool_approval_model import (  # noqa: PLC0415
        set_tool_approval_model,
    )
    from agent.core.tools.base import (  # noqa: PLC0415
        ToolContext as CoreToolContext,
        set_tool_safety_config_factory,
        set_tool_safety_factory,
    )
    from agent.core.tools.registry import ToolRegistry  # noqa: PLC0415
    from agent.platform.tools.safety import (  # noqa: PLC0415
        ToolSafety,
        ToolSafetyConfig,
        load_tool_safety_config,
    )

    resolved_repo_root = (
        (repo_root or Path(os.getenv("NANO_MULTIAGENT_REPO_ROOT", os.getcwd())))
        .expanduser()
        .resolve()
    )

    _wire_console_tracer()

    # Model registry is build_kernel's responsibility (决策 5).
    _init_model_registry_from_llm_config(llm)

    factory_config = _llm_config_to_factory_config(llm)

    files = JsonlSessionFiles(
        data_dir=None,
        workspace_config_dirname=workspace_config_dirname,
    )
    writer = JsonlWriter()

    permission_broker = PermissionBroker(config=AutoModeConfig())

    # Shared hook base: built-ins, consumer setup and deployment-global
    # extensions. Workspace hooks are intentionally excluded here; a session
    # scope clones this registry and appends its own selected layout layer.
    hook_registry = build_hook_registry(
        repo_root=resolved_repo_root,
        include_default_workspace=False,
    )
    set_tool_approval_model(hook_registry, tool_approval_model)
    for setup in hooks:
        setup(hook_registry)
    for hook_root in hook_search_roots:
        load_hooks_into_registry(
            registry=hook_registry,
            directory=Path(hook_root).expanduser().resolve(),
            source="global",
        )
    hook_runner = HookRunner(registry=hook_registry)

    owned_llm_clients: list[LLMClient] = []
    if _llm_client_override is not None:
        direct_llm_client: LLMClient | None = _llm_client_override
        llm_clients: dict[str, LLMClient] | None = None
    else:
        # bugfix-429 决策3: build one client per declared provider so a run is
        # routed to the client of its model's registered provider. Within a
        # provider all models share base_url (set here); only request.model
        # varies per call, so one client per provider suffices. Providers with no
        # models are skipped — nothing routes to them (no model maps to them) and
        # building a client would resolve an empty model map.
        llm_clients = {
            p.name: _platform_create_llm_client(
                config=LLMFactoryConfig(
                    provider=p.name,
                    model=p.models[0].name,
                    base_url=p.base_url,
                    api_key=llm.api_key,
                    timeout_seconds=llm.timeout_seconds,
                )
            )
            for p in llm.providers
            if p.models
        } or None
        if llm_clients is not None:
            owned_llm_clients.extend(llm_clients.values())
        direct_llm_client = (
            llm_clients.get(factory_config.provider)
            if llm_clients is not None
            else None
        )
        if direct_llm_client is None:
            direct_llm_client = _platform_create_llm_client(config=factory_config)
            owned_llm_clients.append(direct_llm_client)

    event_hub = EventStreamHub()
    set_session_event_publisher_factory(
        registry=hook_registry,
        factory=_build_session_event_publisher_factory(event_hub=event_hub),
    )

    prompt_sections = build_kernel_prompt_skeleton()
    resolved_skill_roots = tuple(
        Path(root).expanduser().resolve() for root in skill_search_roots
    )

    def _make_engine() -> AgentEngine:
        engine = AgentEngine(
            hook_runner=hook_runner,
            repo_root=resolved_repo_root,
            permission_broker=permission_broker,
            llm_client=direct_llm_client,
            llm_clients=llm_clients,
            model=factory_config.model,
            prompt_sections=prompt_sections,
            workspace_config_dirname=workspace_config_dirname,
            skill_search_roots=resolved_skill_roots,
        )
        engine._llm_config = factory_config  # type: ignore[attr-defined]
        engine._can_use_tool = can_use_tool  # type: ignore[attr-defined]
        return engine

    # AgentEngine is task-local through ConversationState/TurnContext and owns no
    # session-id keyed state, so every stable conversation shares this dependency
    # graph and the provider clients it holds.
    engine_services = _make_engine()
    executor = KernelExecutor()

    def _conversation_factory(ref: SessionRef, transcript: Any) -> ConversationSession:
        control = _SessionSubagentControl(
            ref=ref,
            directory=directory,
            files=files,
            engine=engine_services,
        )
        return ConversationSession(
            ref=ref,
            transcript=transcript,
            engine=engine_services,
            subagent_control=control,
        )

    directory = SessionDirectory(
        files=files,
        writer=writer,
        conversation_factory=_conversation_factory,
        default_metadata={"workspace_config_dirname": workspace_config_dirname},
    )

    async def _finalize_resources() -> None:
        errors: list[BaseException] = []
        try:
            await directory.close_all()
        except BaseException as exc:  # cleanup must continue after flush failure
            errors.append(exc)
        try:
            await asyncio.to_thread(writer.close)
        except BaseException as exc:  # writer.close joins before surfacing I/O errors
            errors.append(exc)
        seen: set[int] = set()
        for client in owned_llm_clients:
            identity = id(client)
            if identity in seen:
                continue
            seen.add(identity)
            close = getattr(client, "close", None)
            if not callable(close):
                continue
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    runs_registry = RunsRegistry(
        directory=directory,
        executor=executor,
        event_hub=event_hub,
        hook_runner=hook_runner,
    )

    background_task_wiring = wire_background_tasks(
        workspace_root=resolved_repo_root,
        directory=directory,
        executor=executor,
        runs_registry=runs_registry,
    )

    # bugfix-417-M5 (#114): wire the foreground-tool subprocess reaper so
    # kernel.interrupt / kernel.cancel kill an in-flight foreground bash subprocess
    # tree (and force-cancel the parked carrier Task) instead of leaving an orphan.
    # Injected post-hoc because the wiring is built after the registry (it needs the
    # registry's event loop). The core registry only sees the ForegroundStopper
    # port — it never imports the platform BackgroundTaskRegistry (core stays
    # platform-free). bugfix-417-M7 (decision 12): the port now points at the narrow
    # ForegroundExecutionRegistry (foreground bash no longer lives in
    # BackgroundTaskRegistry); same (session_id) -> bool signature, runs/registry.py
    # interrupt/cancel logic unchanged.
    runs_registry.set_foreground_stopper(
        background_task_wiring.foreground_registry.stop_for_session
    )

    # Tool catalog: built-ins + consumer native tool objects (决策 2). The native
    # objects satisfy the SDK Tool Protocol and are registered into the registry
    # directly — no _product_root() directory scan.
    set_tool_safety_factory(ToolSafety)
    set_tool_safety_config_factory(ToolSafetyConfig)
    base_context = CoreToolContext.create(
        repo_root=resolved_repo_root,
        safety_config=load_tool_safety_config(repo_root=resolved_repo_root),
        llm_client=getattr(engine_services, "_llm_client", None),
        skill_batch_review_enqueue=engine_services.enqueue_skill_batch_review,
    )
    tool_registry = ToolRegistry(context=base_context, hook_runner=hook_runner)
    register_builtin_tools(tool_registry, wiring=background_task_wiring)
    # Self-evolution built-ins (决策 3): memory / skill_manage are kernel built-ins
    # ("any app has them → stays in kernel"), not consumer tools. They need
    # constructor-time path args so register_builtin_tools() omits them; the kernel
    # registers them here. memory_root is per-session (MemoryTool derives it at run
    # time from session_metadata[workspace_root]+[workspace_config_dirname]); skill_root
    # is the build-time per-config-dir skills dir (mirrors the legacy bootstrap's
    # workspace-skill-root preference). The two general features (memory_curation /
    # skill_creation) gate them via requires_tool presence + feature flag.
    _register_self_evolution_builtins(
        tool_registry,
        repo_root=resolved_repo_root,
        workspace_config_dirname=workspace_config_dirname,
        skill_search_roots=tuple(
            Path(r).expanduser().resolve() for r in skill_search_roots
        ),
        global_skill_root=(global_skill_root or pa_skill_root).expanduser().resolve()
        if (global_skill_root or pa_skill_root) is not None
        else None,
    )
    for tool in tools:
        tool_registry.register(tool, replace=True)

    # Deployment-global extension roots are part of the shared base.  The
    # workspace layer is discovered only by _SessionCapabilityResolver.
    from agent.platform.tools.loader import (  # noqa: PLC0415
        _load_tools_from_single_dir,
    )

    for tool_root in tool_search_roots:
        resolved_tool_root = Path(tool_root).expanduser().resolve()
        if resolved_tool_root.is_dir():
            _load_tools_from_single_dir(
                tool_root=resolved_tool_root, registry=tool_registry, replace=True
            )

    _bind_wiring_to_tool_registry(
        tool_registry=tool_registry,
        hook_runner=hook_runner,
        wiring=background_task_wiring,
    )
    engine_services.bind_tool_registry(tool_registry)
    capability_resolver = _SessionCapabilityResolver(
        workspace_config_dirname=workspace_config_dirname,
        global_config_root=global_config_root,
        base_tool_registry=tool_registry,
        base_hook_registry=hook_registry,
        llm_client=getattr(engine_services, "_llm_client", None),
        skill_batch_review_enqueue=engine_services.enqueue_skill_batch_review,
    )
    engine_services.set_execution_scope_resolver(capability_resolver.scope_for)

    components = _KernelComponents(
        engine_services=engine_services,
        directory=directory,
        executor=executor,
        tool_registry=tool_registry,
        runs_registry=runs_registry,
        event_hub=event_hub,
        permission_broker=permission_broker,
        hook_registry=hook_registry,
        hook_runner=hook_runner,
        stop_all_foreground=background_task_wiring.foreground_registry.stop_all,
        finalize_resources=_finalize_resources,
    )

    return Kernel(
        components=components,
        can_use_tool=can_use_tool,
        repo_root=resolved_repo_root,
        llm_catalog=llm,
        workspace_config_dirname=workspace_config_dirname,
        capability_resolver=capability_resolver,
        skill_search_roots=tuple(
            Path(r).expanduser().resolve() for r in skill_search_roots
        ),
    )


def _register_self_evolution_builtins(
    tool_registry: Any,
    *,
    repo_root: Path,
    workspace_config_dirname: str,
    skill_search_roots: tuple[Path, ...] = (),
    global_skill_root: Path | None = None,
) -> None:
    """Register the kernel built-in memory / skill_manage tools (决策 3).

    These are kernel built-ins, not consumer tools — every application has them, so
    they stay in the kernel (决策 3). They are excluded from ``builtin_tools()`` only
    because they need constructor-time path args; the kernel resolves those here:

    - ``MemoryTool()`` takes no fixed root — it derives memory_root per-session from
      ``session_metadata[workspace_root] + [workspace_config_dirname]`` at run time.
    - ``SkillManageTool(workspace_config_dirname, extra_roots)`` (refactor-406-M3fix #4):
      writes/lists skills **per-session**, deriving ``<workspace_root>/<dirname>/skills``
      from session_metadata at run time + the deployment ``skill_search_roots`` — so
      each agent uses its own workspace skills (no shared build-repo_root registry) and
      skill_manage aligns with ``Kernel.list_skills`` / IM (one resolver, 决策 4).
    """
    from agent.platform.tools.builtins import (  # noqa: PLC0415
        MemoryTool,
        SkillManageTool,
        SkillViewTool,
    )

    tool_registry.register(
        SkillManageTool(
            workspace_config_dirname=workspace_config_dirname,
            extra_roots=skill_search_roots,
            global_skill_root=global_skill_root,
        ),
        replace=True,
    )
    tool_registry.register(
        SkillViewTool(
            workspace_config_dirname=workspace_config_dirname,
            extra_roots=skill_search_roots,
            global_skill_root=global_skill_root,
        ),
        replace=True,
    )
    tool_registry.register(MemoryTool(), replace=True)


def _wire_console_tracer() -> None:
    """Wire the console tracer when the threshold env var is set."""
    threshold = os.getenv("NANO_MULTIAGENT_TRACE_CONSOLE_THRESHOLD_MS")
    if threshold is None:
        return
    try:
        set_tracer(ConsoleTracer(threshold_ms=float(threshold)))
    except ValueError:
        set_tracer(ConsoleTracer(threshold_ms=100.0))


# refactor-406-M3fix #5: per-agent self_evolution config (re-home, not drop).
# design 决策1: per-agent config moves to create_session. The legacy bootstrap read
# this from <workspace>/<dirname>/config.yaml's self_evolution section into session
# metadata; the self_improvement hook reads metadata["self_evolution"] for
# skill_nudge_interval / memory_nudge_interval / enabled. The 2-layer create_session
# dropped this read → hook got {} → hard-coded interval=10 overrode user config.
# Re-homed here using ONLY workspace_root + workspace_config_dirname to locate the
# file (no ConfigResolver / user roots, per the ConfigResolver-removal decision).
# Logic + fallback ported verbatim from the legacy bootstrap._load_self_evolution_config.
_DEFAULT_SELF_EVOLUTION_CONFIG: dict = {
    "enabled": True,
    "skill_creation": True,
    "memory_curation": True,
    "skill_nudge_interval": 10,
    "memory_nudge_interval": 10,
}


def _load_self_evolution_config(config_path: Path) -> dict:
    """Read the self_evolution section from a workspace config YAML, with fallback.

    Falls back to the platform default (all on, interval=10) when the file is absent
    or malformed. User values are merged over defaults so missing keys still default.
    """
    if not config_path.is_file():
        return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
    try:
        import yaml  # noqa: PLC0415

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        user_evo = raw.get("self_evolution", {})
        if not isinstance(user_evo, dict):
            return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        result = dict(_DEFAULT_SELF_EVOLUTION_CONFIG)
        result.update(user_evo)
        return result
    except Exception:  # noqa: BLE001
        return dict(_DEFAULT_SELF_EVOLUTION_CONFIG)


class Kernel:
    """In-process agent kernel: the sole public interface for products.

    Consumers create sessions, submit turns, stream events, and inject
    permission decisions through this class. No HTTP calls, no spawned
    subprocesses — all execution is in-process.

    Notes:
        ``submit()`` is synchronous and non-blocking (schedules the turn on
        RunsRegistry's background loop; returns immediately with a RunRecord).
        All session-lifecycle methods (``create_session``, ``fork_session``,
        ``compact``) are async.
    """

    def __init__(
        self,
        *,
        components: _KernelComponents,
        can_use_tool: CanUseToolFn | None,
        repo_root: Path,
        llm_catalog: LLMConfig | None = None,
        workspace_config_dirname: str | None = None,
        skill_search_roots: tuple[Path, ...] = (),
        capability_resolver: _SessionCapabilityResolver | None = None,
    ) -> None:
        self._c = components
        self._repo_root = repo_root
        # SDK-owned LLM catalog (decision 5) for list_models / get_llm_config DTO
        # mapping. None on the legacy product_profile path (catalog unknown there).
        self._llm_catalog = llm_catalog
        # Per-workspace config dir (.nanocode / .nanoassistant) for the 2-layer path.
        # list_skills uses it to resolve <workspace>/<dirname>/skills without a
        # ProductProfile (the legacy path resolves via config_resolver instead).
        self._workspace_config_dirname = workspace_config_dirname
        # Deployment-level skill roots shared across workspaces (refactor-406-M2):
        # list_skills appends them after the per-workspace root, deduplicating. The
        # consumer factory owns these product paths; the kernel stays neutral.
        self._skill_search_roots = skill_search_roots
        self._capability_resolver = capability_resolver

        # Per-conversation engines receive this callback from the composition root.
        # Keep the argument on Kernel for the public constructor shape only.
        del can_use_tool

    def _scope_for(self, workspace_root: Path) -> WorkspaceExecutionScope | None:
        """Resolve the immutable capability snapshot for one workspace."""

        resolver = self._capability_resolver
        return resolver.scope_for(workspace_root) if resolver is not None else None

    # ------------------------------------------------------------------
    # Public API — mirrors design.md §接口与数据流
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: str | Path | None = None,
        # --- new (refactor-406 决策 1/6/8) per-agent config ---
        enabled_tools: list[str] | None = None,
        features: dict[str, bool] | None = None,
        prompt: PromptSlots | None = None,
        runtime: SessionRuntimeConfig | None = None,
        # --- legacy (扩张期保留) ---
        skills: list[str] | None = None,
        tool_allowlist: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionInfo:
        """Create a session and return its SDK-owned ``SessionInfo`` (决策 6).

        Per-agent config (new path, 决策 1): ``enabled_tools`` selects the session's
        tool subset from the kernel catalog; ``features`` toggles the kernel's
        general features (memory_curation / skill_creation); ``prompt`` is the
        consumer's per-session ``PromptSlots`` placed into the kernel skeleton
        (决策 8). model is *not* taken here — it stays kernel-level (决策 5).

        Legacy ``skills`` / ``tool_allowlist`` / ``metadata`` are retained during
        the expansion phase for callers not yet migrated.

        Args:
            title: Optional human-readable title.
            workspace_root: Workspace root for session JSONL storage.
            enabled_tools: Tool names selected for this session (new path).
            features: Kernel feature toggles → session ``agent_features`` (new path).
            prompt: Per-session product PromptSlots (new path, 决策 8).
            skills: Legacy skill name list.
            tool_allowlist: Legacy tool allowlist (superseded by enabled_tools).
            metadata: Legacy session metadata.

        Returns:
            SessionInfo with session_id / title / workspace_root / metadata.
        """
        # refactor-406-M3fix-r2 R2-5：resolve to absolute so the #5 self_evolution
        # config_path (effective_root/<dirname>/config.yaml) does not depend on the
        # process cwd when workspace_root is relative — otherwise is_file() silently
        # misses the file and falls back to defaults. Mirrors resolved_repo_root.
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        if runtime is not None:
            enabled_tools = list(runtime.enabled_tools)
            skills = list(runtime.skills) if runtime.skills is not None else None
            features = dict(runtime.features) if runtime.features is not None else None
            prompt = runtime.prompt

        effective_allowlist = (
            enabled_tools if enabled_tools is not None else tool_allowlist
        )
        effective_metadata = (
            runtime_metadata(runtime, existing=metadata)
            if runtime
            else (dict(metadata) if metadata else {})
        )
        if features is not None:
            # Feature toggles drive the kernel feature gates via agent_features
            # (same key the runtime reads through resolve_flags_from_metadata).
            merged_features = dict(effective_metadata.get("agent_features", {}))
            merged_features.update(features)
            effective_metadata["agent_features"] = merged_features

        # refactor-406-M3fix #5: re-home per-agent self_evolution config (决策1: per-agent
        # config → create_session). Locate <workspace_root>/<dirname>/config.yaml using
        # only workspace_root + workspace_config_dirname (no ConfigResolver), read its
        # self_evolution section into session metadata so the self_improvement hook reads
        # the user's skill_nudge_interval / memory_nudge_interval instead of hard-coded
        # defaults. Caller-supplied metadata wins (don't override an explicit value).
        if (
            "self_evolution" not in effective_metadata
            and self._workspace_config_dirname
        ):
            config_path = (
                effective_root / self._workspace_config_dirname / "config.yaml"
            )
            effective_metadata["self_evolution"] = _load_self_evolution_config(
                config_path
            )

        conversation = self._c.directory.create(
            NewSession(
                workspace_root=effective_root,
                runtime_model=runtime.model if runtime is not None else None,
                runtime_features=(
                    dict(runtime.features)
                    if runtime is not None and runtime.features is not None
                    else None
                ),
                runtime_reasoning_effort=(
                    runtime.reasoning_effort if runtime is not None else None
                ),
                title=title,
                skills=tuple(skills) if skills else None,
                tool_allowlist=(
                    tuple(effective_allowlist)
                    if effective_allowlist is not None
                    else None
                ),
                metadata=effective_metadata,
                prompt_seed=_to_prompt_seed(prompt),
            )
        )
        session = self._c.directory.get(conversation.ref)
        if session is None:  # pragma: no cover - durable create invariant.
            raise RuntimeError("session disappeared after durable creation")
        scope = self._scope_for(effective_root)
        hook_ctx = HookContext(
            session_id=session.session_id,
            repo_root=effective_root,
            metadata=scope.metadata() if scope is not None else {},
            session_event_publisher=_build_session_event_publisher_factory(
                event_hub=self._c.event_hub
            )(session.session_id),
        )
        try:
            hook_runner = scope.hook_runner if scope is not None else self._c.hook_runner
            diagnostics = await hook_runner.dispatch_observe(
                "session_start", {"session_id": session.session_id}, hook_ctx
            )
        except Exception as exc:  # pragma: no cover - defensive fail-open fallback.
            hook_ctx.logger.warning(
                "hook observe dispatch failed", event="session_start", error=str(exc)
            )
        else:
            log_hook_diagnostics(
                hook_ctx, event="session_start", diagnostics=diagnostics
            )
        return _to_session_info(session)

    def identify_runtime(
        self, *, runtime: SessionRuntimeConfig
    ) -> SessionRuntimeIdentity:
        """Return the SDK-owned stable identity for a complete runtime."""

        return identify_runtime(runtime)

    async def get_session_runtime(
        self,
        *,
        session_id: str,
        workspace_root: Path | str,
    ) -> SessionRuntimeState | None:
        """Return a session's complete persisted runtime, if its archive supports it."""

        root = Path(workspace_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=root)
        session = self._c.directory.get(ref)
        if session is None:
            raise ValueError(f"session does not exist: {session_id}")
        conversation = self._c.directory.open(ref)
        config, seed = conversation.config_snapshot()
        if config.runtime_model is None:
            return None
        from agent.sdk.prompt import PromptText  # noqa: PLC0415

        runtime_payload = config.metadata.get(INTERNAL_RUNTIME_KEY)
        runtime_features = (
            runtime_payload.get("features")
            if isinstance(runtime_payload, dict)
            else None
        )
        runtime_reasoning_effort = (
            runtime_payload.get("reasoning_effort")
            if isinstance(runtime_payload, dict)
            and isinstance(runtime_payload.get("reasoning_effort"), str)
            else None
        )
        runtime = SessionRuntimeConfig(
            model=config.runtime_model,
            prompt=PromptSlots(
                head=tuple(PromptText(item.name, item.text) for item in seed.head),
                body=tuple(PromptText(item.name, item.text) for item in seed.body),
                custom=tuple(PromptText(item.name, item.text) for item in seed.custom),
                tail=tuple(PromptText(item.name, item.text) for item in seed.tail),
            ),
            skills=list(config.skills) if config.skills is not None else None,
            enabled_tools=list(config.tool_allowlist or ()),
            features=dict(runtime_features) if runtime_features is not None else None,
            reasoning_effort=runtime_reasoning_effort,
        )
        return SessionRuntimeState(runtime=runtime, identity=identify_runtime(runtime))

    async def reconfigure_session(
        self,
        *,
        session_id: str,
        workspace_root: Path | str,
        runtime: SessionRuntimeConfig,
    ) -> SessionReconfigureResult:
        """Durably replace every future-turn setting without changing session identity."""

        root = Path(workspace_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=root)
        if self._c.directory.get(ref) is None:
            raise ValueError(f"session does not exist: {session_id}")
        conversation = self._c.directory.open(ref)
        config, seed = conversation.config_snapshot()
        target_metadata = runtime_metadata(runtime, existing=config.metadata)
        target_prompt_seed = _to_prompt_seed(runtime.prompt)
        if (
            config.runtime_model == runtime.model
            and config.skills
            == (tuple(runtime.skills) if runtime.skills is not None else None)
            and config.tool_allowlist == tuple(runtime.enabled_tools)
            and config.metadata == target_metadata
            and seed == target_prompt_seed
        ):
            state = await self.get_session_runtime(
                session_id=session_id, workspace_root=root
            )
            if state is None:  # pragma: no cover - complete runtime already persisted.
                raise RuntimeError(
                    "session runtime disappeared during idempotent replacement"
                )
            return SessionReconfigureResult(
                session_id=session_id,
                changed=False,
                state=state,
            )
        changed = await self._c.executor.replace_runtime(
            conversation,
            runtime_model=runtime.model,
            skills=tuple(runtime.skills) if runtime.skills is not None else None,
            tool_allowlist=tuple(runtime.enabled_tools),
            metadata=target_metadata,
            prompt_seed=target_prompt_seed,
        )
        state = await self.get_session_runtime(
            session_id=session_id, workspace_root=root
        )
        if state is None:  # pragma: no cover - replacement always persists raw runtime.
            raise RuntimeError("session runtime disappeared after replacement")
        return SessionReconfigureResult(
            session_id=session_id, changed=changed, state=state
        )

    async def fork_session(
        self,
        session_id: str,
        *,
        workspace_root: str | Path | None = None,
        up_to: str | None = None,
    ) -> SessionInfo:
        """Fork an existing session into an independent new session.

        Copies the source session's conversation context into a fresh session with
        re-stamped message ids and its own JSONL file; the source is untouched and the
        two evolve independently thereafter.

        Args:
            session_id: Source session to fork from.
            workspace_root: Workspace root locating the source session JSONL; the fork
                inherits the source's workspace_root.
            up_to: feat-445-M1 — when set, the fork inherits the source's context view
                **as of the message ``up_to``** (a kernel message id = JSONL turn uuid),
                including whatever compaction state was in effect at that point, instead
                of the whole conversation. Messages after ``up_to`` are not carried.

        Returns:
            SessionInfo for the new forked session.
        """
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=effective_root)
        if self._c.directory.get(ref) is None:
            raise ValueError(f"session does not exist: {session_id}")
        session, id_map = await self._c.executor.fork(
            self._c.directory.open(ref), up_to=up_to
        )
        return replace(_to_session_info(session), fork_id_map=id_map)

    async def compact(
        self,
        session_id: str,
        *,
        workspace_root: str | Path | None = None,
        focus: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Compact session context (summarise old turns to save tokens).

        Args:
            session_id: Session to compact.
            workspace_root: Session workspace root.
            focus: Optional user-specified facts to prioritize in the summary.
            idempotency_key: Stable key that makes a replay return the first manual
                compaction result without creating another boundary.

        Returns:
            CompactResult or None when compaction is skipped.
        """
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=effective_root)
        if self._c.directory.get(ref) is None:
            raise ValueError(f"session does not exist: {session_id}")
        return await self._c.executor.compact(
            self._c.directory.open(ref),
            focus=focus,
            idempotency_key=idempotency_key,
        )

    async def discard_run_messages(self, run_id: str) -> bool:
        """Remove messages produced by one terminal run from its conversation.

        The run record supplies the canonical session address and turn identity.
        Cleanup is serialized by ``ConversationSession`` with normal turns, so
        later messages remain durable and reachable even when they arrived before
        this method acquired the conversation gate.

        Args:
            run_id: Terminal run whose persisted turn should be removed.

        Returns:
            True when the run had persisted messages that were removed. False for
            unknown, non-terminal, or pre-turn runs and repeated cleanup.
        """

        record = self._c.runs_registry.get(run_id)
        if (
            record is None
            or record.status
            not in {
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }
            or not record.turn_id
            or record.workspace_root is None
        ):
            return False
        ref = SessionRef(
            session_id=record.session_id,
            workspace_root=record.workspace_root,
        )
        if self._c.directory.get(ref) is None:
            return False
        return await self._c.executor.discard_turn(
            self._c.directory.open(ref),
            turn_id=record.turn_id,
        )

    def try_steer(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: RunOrigin = RunOrigin.USER,
        expected_run_id: str | None = None,
    ) -> RunInfo | None:
        """Try to inject one message into the session's active run.

        This operation is inject-only: it returns ``None`` when no active run can
        accept the message and never creates a fallback run. Product coordinators
        that already own normal-run admission can therefore decide when and where
        to queue exactly one fallback without racing ``submit(steer=True)``.

        Args:
            session_id: Session whose active run may receive the message.
            parts: Input parts rendered with the same rules as ``submit``.
            origin: Message origin recorded on the injected pending message.
            expected_run_id: Optional caller-owned active marker. When supplied,
                a replacement run for the same session is never targeted.

        Returns:
            The active ``RunInfo`` with ``injected=True`` when accepted, otherwise
            ``None``. A ``None`` result guarantees this call created no run.
        """

        return self._try_inject_active_run(
            session_id=session_id,
            parts=parts,
            origin=origin,
            expected_run_id=expected_run_id,
        )

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: RunOrigin = RunOrigin.USER,
        workspace_root: str | Path | None = None,
        trace_id: str | None = None,
        steer: bool = False,
        flush_held: bool = True,
        model: str | None = None,
    ) -> RunInfo:
        """Schedule a turn on the background loop and return immediately.

        Args:
            session_id: Session to run the turn in.
            parts: Input parts (text, image, etc.) for this turn.
            origin: Message origin (user, system, background, etc.).
            workspace_root: Session workspace root.
            trace_id: Optional trace correlation id.
            steer: When True and a run is already active for the session, inject
                this message into that run's next LLM round instead of queueing a
                new run (feat-338 ``priority="next"`` semantics). When no run is
                active it degrades to a normal new run. Default False keeps every
                existing call site unchanged; only run-active product entrypoints
                (IM inbound, CLI REPL) pass True (bugfix-426 决策1).
            flush_held: When True (default) any messages parked by a prior user
                /stop for this session are prepended to this run (bugfix-426 决策3).
                The gateway's /stop handler passes False for its synthetic "/stop
                命令" bookkeeping turn so the held messages ride the user's next
                real message instead.
            model: Model id for this run (bugfix-429). Supplied by the product
                layer per turn (agent.default_model, with the product's own
                default as fallback) so per-agent model selection takes effect and
                old sessions pick up a model change on the next turn. The kernel
                does not own a conversational default; it stores this on the run
                record and the loop routes the request to the model's provider.

        Returns:
            RunInfo with run_id / session_id / status. ``injected=True`` when the
            message was steered into an active run (``run_id`` is that run, no new
            run created); otherwise ``injected=False`` for a freshly created run.
        """
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=effective_root)
        if self._c.directory.get(ref) is None:
            raise ValueError(f"session does not exist: {session_id}")
        runtime_model = self._c.directory.open(ref).config_snapshot()[0].runtime_model
        if runtime_model is not None:
            if model is not None and model != runtime_model:
                raise ValueError("submit model must match the session runtime")
            model = runtime_model
        if steer:
            injected = self.try_steer(session_id=session_id, parts=parts, origin=origin)
            if injected is not None:
                return injected
        record = self._c.runs_registry.submit(
            session_id=session_id,
            parts=parts,
            origin=origin,
            workspace_root=effective_root,
            trace_id=trace_id,
            flush_held=flush_held,
            model=model,
        )
        return _to_run_info(record)

    def _try_inject_active_run(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: RunOrigin,
        expected_run_id: str | None = None,
    ) -> RunInfo | None:
        """Inject parts into the session's active run, mirroring the proven
        ``background_tasks/wiring.py`` range: check active run, then atomically
        enqueue. Returns the injected RunInfo, or None when no run is active (the
        caller then falls back to a normal new run).

        The injected message is built with the *same* parts→text rendering submit
        uses (``parse_input_parts`` + ``render_user_text``): image parts collapse
        to the placeholder, so steering carries identical content to a normal turn
        — there is no with/without-attachment divergence (bugfix-426 决策2).
        """
        from agent.core.agent.state import (  # noqa: PLC0415
            parse_input_parts,
            render_user_content_parts,
            render_user_text,
        )
        from agent.core.llm.interfaces import LLMMessage  # noqa: PLC0415

        registry = self._c.runs_registry
        parsed_parts = parse_input_parts(parts)
        user_content = render_user_content_parts(parsed_parts) or render_user_text(
            parsed_parts
        )
        accepted_run_id = registry.try_inject_pending_message(
            session_id,
            LLMMessage(role="user", content=user_content),
            origin=origin,
            expected_run_id=expected_run_id,
        )
        if accepted_run_id is None:
            return None
        record = registry.get(accepted_run_id)
        if record is None:
            raise RuntimeError(
                f"accepted steer run disappeared from registry: {accepted_run_id}"
            )
        return _to_run_info(record, injected=True)

    def stream(
        self,
        session_id: str,
        *,
        after_sequence: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return an async iterator of flattened event dicts for the given session.

        Each dict has ``event`` (name), ``session_id``, ``sequence_num``, and the
        payload fields from the event's ``data`` dict merged to the top level.
        This is the public SDK stream contract — consumers call ``event.get("run_id")``
        etc. directly, matching the SSE-decoded-dict shape used in the HTTP era.

        Yields events from history (after ``after_sequence``) then live events.
        Never closes on terminal run_status — caller must break the loop.

        Args:
            session_id: Session to subscribe to.
            after_sequence: Replay history only after this sequence number.

        Returns:
            AsyncIterator[dict] — flattened event dicts; no internal StreamEvent
            dataclass is exposed on the public surface.
        """
        return self._stream_flat(session_id=session_id, after_sequence=after_sequence)

    async def _stream_flat(
        self,
        *,
        session_id: str,
        after_sequence: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Wrap EventStreamHub.stream_session(), flattening StreamEvent → dict."""
        async for ev in self._c.event_hub.stream_session(
            session_id=session_id,
            after_sequence=after_sequence,
        ):
            # Merge StreamEvent.data (the full payload) with top-level metadata fields
            # so callers can do event.get("run_id"), event.get("event"), event.get("status")
            # without knowing about the StreamEvent.data nesting.
            flat: dict[str, Any] = dict(ev.data)
            flat.setdefault("event", ev.event)
            flat.setdefault("session_id", ev.session_id)
            flat.setdefault("sequence_num", ev.sequence_num)
            yield flat

    def interrupt(self, session_id: str) -> str | None:
        """Interrupt the active run for a session and cancel pending permissions.

        Args:
            session_id: Session whose active run to interrupt.

        Returns:
            Interrupted run_id, or None if no active run.
        """
        run_id = self._c.runs_registry.interrupt(session_id)
        # Cancel ALL parked permission futures so can_use_tool awaiters do not
        # hang indefinitely (design risk 3). We cancel all (run_id=None) because
        # permission requests registered via the SDK permission_requester are not
        # scoped to a run_id — all pending permissions should be aborted on interrupt.
        self._c.permission_broker.cancel_all_pending(run_id=None)
        return run_id

    def submit_permission_decision(
        self,
        *,
        request_id: str,
        decision: str,
        reason: str = "",
    ) -> bool:
        """Resolve a pending permission request with a user decision.

        Called by the gateway when the user clicks Allow/Deny on an IM
        permission card. Resolves the broker future so the parked run can
        resume or be denied.

        Args:
            request_id: The unique request id from the permission_request event.
            decision: One of ``allow_once``, ``deny``, ``allow_session``,
                ``allow_always``.
            reason: Optional human-readable reason forwarded to the run.

        Returns:
            True when the request was pending and has been resolved; False when
            request_id is unknown or already resolved (idempotent).
        """
        from agent.platform.permissions.broker import PermissionResponse  # noqa: PLC0415

        _VALID_DECISIONS = frozenset(
            {"allow_once", "deny", "allow_session", "allow_always"}
        )
        if decision not in _VALID_DECISIONS:
            import logging as _logging  # noqa: PLC0415

            _logging.getLogger(__name__).warning(
                "submit_permission_decision: invalid decision %r (must be one of %s)",
                decision,
                sorted(_VALID_DECISIONS),
            )
            return False

        broker = self._c.permission_broker
        response = PermissionResponse(
            decision=decision,  # type: ignore[arg-type]
            request_id=request_id,
            reason=reason,
        )
        # broker.resolve pops atomically under lock; its bool return replaces the
        # TOCTOU-prone is_pending pre-check (feat-394-M14 finding 7).
        return broker.resolve(request_id, response)

    def cancel(self, run_id: str) -> RunInfo | None:
        """Cancel a queued or running run by id.

        The registry force-cancels the carrier Task (releasing the session lock);
        here we also cancel any permission requests this run is still parked on so
        the broker future does not leak after the run is gone (bugfix-417-M1, #110).

        Args:
            run_id: Run to cancel.

        Returns:
            Updated RunInfo, or None if run not found.
        """
        record = self._c.runs_registry.cancel(run_id)
        if record is None:
            return None
        self._c.permission_broker.cancel_all_pending(run_id=run_id)
        return _to_run_info(record)

    def get_run(self, run_id: str) -> RunInfo | None:
        """Fetch the current state of a run.

        Args:
            run_id: Run to look up.

        Returns:
            RunInfo, or None if not found.
        """
        record = self._c.runs_registry.get(run_id)
        return _to_run_info(record) if record is not None else None

    def list_session_tools(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Any:
        """Return the tools available to a session.

        Args:
            session_id: Session scope.
            workspace_root: Session workspace root.

        Returns:
            ToolsInfo describing available tools.
        """
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        scope = self._scope_for(effective_root)
        tool_registry = scope.tool_registry if scope is not None else self._c.tool_registry
        if tool_registry is None:
            return {}
        return tool_registry.list_specs()

    # ------------------------------------------------------------------
    # Capability queries (决策 4) — single-item neutral facts, SDK-owned DTOs.
    # The application (Gateway reporter) projects these into IM payloads; the
    # kernel does no product-semantic aggregation.
    # ------------------------------------------------------------------

    def list_models(self) -> list:
        """Return the model catalog as SDK-owned ``ModelInfo`` DTOs (决策 4).

        Reads the process model registry installed at build time. The **catalog
        default** model (``get_default_model(get_default_provider())``) is flagged
        ``is_default`` so selectors can highlight it — this is the configured default,
        not necessarily the currently-active model (which CLI ``/model`` may have
        switched). When the registry is not initialised (test paths that bypass
        catalog install), falls back to the single active model (flagged default).

        Returns:
            List of ModelInfo(name, provider, is_default).
        """

        active = self._c.engine_services.get_llm_config()
        active_model = getattr(active, "model", None)

        try:
            from agent.core.llm.model_registry import (  # noqa: PLC0415
                get_default_model,
                get_default_provider,
                list_provider_models,
                list_supported_providers,
            )

            default_provider = get_default_provider()
            default_model = get_default_model(default_provider)
            models: list = []
            for provider in list_supported_providers():
                for meta in list_provider_models(provider):
                    models.append(
                        ModelInfo(
                            name=meta.model,
                            provider=meta.provider,
                            is_default=(meta.model == default_model),
                        )
                    )
            if models:
                return models
        except Exception:  # noqa: BLE001
            # Registry not initialised (test bypass) — fall through to active-only.
            pass

        if active_model is None:
            return []
        return [
            ModelInfo(
                name=active_model,
                provider=getattr(active, "provider", ""),
                is_default=True,
            )
        ]

    def list_tools(self) -> list:
        """Return the kernel tool catalog as ``ToolInfo`` DTOs (决策 4).

        Lists the tools registered in the shared base (name + description),
        independent of any per-session ``enabled_tools`` subset — the application
        computes per-session ``available`` itself.

        Returns:
            List of ToolInfo(name, description).
        """

        tool_registry = self._c.tool_registry
        if tool_registry is None:
            return []
        list_specs = getattr(tool_registry, "list_specs", None)
        if not callable(list_specs):
            return []
        return [
            ToolInfo(name=spec.name, description=spec.description)
            for spec in list_specs()
        ]

    def list_features(self) -> list:
        """Return the kernel's general features as ``FeatureInfo`` DTOs (决策 3/4).

        Only kernel-owned general features (those whose guidance is a core
        segment) are reported: ``memory_curation`` / ``skill_creation``.
        Product-specific toggles (heartbeat / cron) are an application-layer
        projection, not kernel features.

        Returns:
            List of FeatureInfo(key, default_on, requires_tool).
        """
        from agent.core.agent.prompt_sections.feature_registry import (  # noqa: PLC0415
            FEATURE_REGISTRY,
        )

        out: list = []
        for key, entry in FEATURE_REGISTRY.items():
            # Kernel-general features are those gated on a kernel built-in tool
            # (memory / skill_manage). Product toggles (heartbeat/cron) are
            # projected by the application, not reported here.
            if key not in ("memory_curation", "skill_creation"):
                continue
            out.append(
                FeatureInfo(
                    key=key,
                    default_on=entry["default_on"],
                    requires_tool=entry["requires_tool"],
                )
            )
        return out

    def list_skills(self, workspace_root: Path | None = None) -> list:
        """Return skills discoverable for a workspace as ``SkillInfo`` DTOs (决策 4).

        Args:
            workspace_root: Workspace whose skills to resolve. Falls back to the
                kernel's repo_root when None.

        Returns:
            List of SkillInfo(name, description) for that workspace; different
            workspaces yield their own skills with no cross-workspace mixing.
        """
        from agent.core.skills import make_skill_resolver, resolve_available_skills  # noqa: PLC0415

        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()

        # Per-workspace skill discovery: use make_skill_resolver (core helper, bugfix-431)
        # so list_skills, preview, and per-conversation engines share the same
        # resolver construction logic (决策 2/4).
        per_call_resolver = make_skill_resolver(
            effective_root,
            self._workspace_config_dirname,
            self._skill_search_roots,
        )

        skills = resolve_available_skills(
            workspace_root=effective_root,
            config_resolver=per_call_resolver,
        )
        return [
            SkillInfo(
                name=s.name,
                description=getattr(s, "description", "") or "",
                # SkillMetadata.location is a non-optional Path (registry always sets it).
                location=str(s.location),
            )
            for s in skills
        ]

    def run_skill_maintenance(
        self, *, workspace_root: Path | None = None, force: bool = False
    ) -> Any:
        """Run deterministic skill lifecycle housekeeping for one workspace."""

        from agent.core.skills.curator import (  # noqa: PLC0415
            CuratorResult,
            apply_curator_transitions,
            run_curator_scan,
        )

        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        if not self._workspace_config_dirname:
            return CuratorResult(
                skill_root=effective_root,
                now_iso=_utc_now_iso(),
                transitions=(),
                skipped=True,
                reason="missing_workspace_config_dirname",
            )
        skill_root = effective_root / self._workspace_config_dirname / "skills"
        result = run_curator_scan(skill_root=skill_root, force=force)
        return apply_curator_transitions(result)

    async def run_queued_skill_batch_reviews(
        self,
        *,
        run_background_analysis: Callable[..., Awaitable[Any] | Any],
        skill_root: Path | None = None,
    ) -> tuple[Any, ...]:
        """Drain queued per-skill batch reviews using an injected background fork."""

        from agent.platform.background.skill_batch_review import (  # noqa: PLC0415
            run_skill_batch_review_async,
        )

        triggers = self._c.engine_services.pop_queued_skill_batch_reviews(
            skill_root=skill_root
        )
        results: list[Any] = []
        for trigger in triggers:
            skill_name = getattr(trigger, "skill_name", "")
            try:
                results.append(
                    await run_skill_batch_review_async(
                        trigger,
                        run_background_analysis=run_background_analysis,
                        writable_skill_root=skill_root,
                    )
                )
            finally:
                if isinstance(skill_name, str) and skill_name:
                    self._c.engine_services.finish_skill_batch_review(trigger)
        return tuple(results)

    def set_skill_batch_review_drain_scheduler(
        self, scheduler: Callable[[Any], None] | None
    ) -> None:
        """Install a product-owned callback fired after a new F4 enqueue."""

        self._c.engine_services.set_skill_batch_review_drain_scheduler(scheduler)

    def get_llm_config(self) -> LLMConfig:
        """Return the active LLM configuration as an SDK-owned ``LLMConfig`` (决策 5).

        Returns:
            LLMConfig with current provider/model/endpoint + build-time catalog.
        """
        return _factory_config_to_llm_config(
            self._c.engine_services.get_llm_config(), catalog=self._llm_catalog
        )

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        message_id: str | None = None,
        parts: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        workspace_root: str | Path | None = None,
    ) -> Any:
        """Append a message to session history without triggering a model run.

        Used by gateway to persist outbound messages (e.g. from send_message tool)
        into the session transcript.

        Args:
            session_id: Target session.
            role: Message role ("user" or "assistant").
            content: Plain text message content.
            message_id: Optional stable message id.
            parts: Optional structured parts (overrides content when provided).
            metadata: Optional metadata to attach to the message.
            idempotency_key: Optional deduplication key.
            workspace_root: Session workspace root for JSONL location.

        Returns:
            AppendMessageResult with the persisted entry.
        """
        normalized_role = role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("role must be one of: user, assistant")
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        ref = SessionRef(session_id=session_id, workspace_root=effective_root)
        if self._c.directory.get(ref) is None:
            raise ValueError(f"session does not exist: {session_id}")
        result = self._c.directory.open(ref).append_external(
            ExternalMessage(
                role=normalized_role,
                content=content,
                message_id=message_id,
                parts=tuple(parts) if parts is not None else None,
                metadata=dict(metadata or {}),
                idempotency_key=idempotency_key,
            )
        )
        return result

    def get_session(
        self,
        session_id: str,
        *,
        workspace_root: str | Path | None = None,
    ) -> Any:
        """Return session metadata for one session.

        Used by gateway to verify workspace_root binding matches agent config.
        Returns a dict with at least {"session_id", "metadata"} shape.

        Args:
            session_id: Session to look up.
            workspace_root: Workspace root where the session JSONL is stored.

        Returns:
            Session detail dict, or raises RuntimeError when not found.
        """
        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()
        session = self._c.directory.get(
            SessionRef(session_id=session_id, workspace_root=effective_root)
        )
        if session is None:
            raise RuntimeError(f"session not found: {session_id}")
        metadata = session.metadata or {}
        return {
            "session_id": session_id,
            "status": "active",
            # workspace_root is exposed as a top-level key so that
            # _binding_matches_workspace_root can compare it directly without
            # requiring the gateway to inject it into metadata (which would
            # create two sources of truth that can drift — refactor-387 regression).
            "workspace_root": str(session.workspace_root),
            "metadata": dict(metadata),
        }

    def current_event_sequence(self) -> int:
        """Return the current maximum published event sequence number.

        Used by heartbeat runner to capture a submit-time anchor so subsequent
        ``stream(after_sequence=anchor)`` calls skip replaying history that
        predates the current run (perf: avoids O(history) scan on every tick).

        Returns:
            The sequence number of the most recently published event, or 0 when
            no events have been published yet.  Callers should pass this value
            as ``after_sequence`` to the next ``stream()`` call.
        """
        return self._c.event_hub.current_sequence()

    async def aclose(self) -> None:
        """Shut down background loops and release resources (async-native path).

        Awaitable by async consumers (Gateway, coding_cli event loop) so the
        caller's event loop is not blocked while waiting for the Registry drain.
        Multiple calls are idempotent — only the first call triggers shutdown.

        bugfix-402-M6: delegates to RunsRegistry.shutdown() via the same
        OPEN→DRAINING→CLOSED state machine used by the sync close() path so
        that submit() rejects new requests during drain and the two paths cannot
        race to call _drain_and_stop simultaneously.
        """
        if getattr(self, "_closed", False):
            return
        self._closed = True
        import asyncio as _asyncio  # noqa: PLC0415

        registry = self._c.runs_registry
        registry.begin_shutdown()
        stop_all_foreground = getattr(self._c, "stop_all_foreground", None)
        if callable(stop_all_foreground):
            stop_all_foreground()
        finalize_resources = getattr(
            self._c, "finalize_resources", self._c.directory.close_all
        )
        await _asyncio.to_thread(registry.shutdown, finalize=finalize_resources)

    def close(self) -> None:
        """Shut down background loops (sync-compat wrapper for non-async consumers).

        Callers inside an event loop must use ``aclose()`` to avoid blocking.
        This method is retained for backward compatibility with sync-only call sites.
        """
        if getattr(self, "_closed", False):
            return
        self._closed = True
        stop_all_foreground = getattr(self._c, "stop_all_foreground", None)
        if callable(stop_all_foreground):
            stop_all_foreground()
        finalize_resources = getattr(
            self._c, "finalize_resources", self._c.directory.close_all
        )
        self._c.runs_registry.shutdown(finalize=finalize_resources)

    def assemble_prompt_preview(
        self,
        *,
        workspace_root: Path | None = None,
        features: dict[str, bool] | None = None,
        custom_prompt: str | None = None,
        tool_ids: list[str] | None = None,
        scenario: str = "direct",
        skill_ids: list[str] | None = None,
        # --- new (refactor-406 决策 8) same-source-as-runtime preview ---
        prompt: PromptSlots | None = None,
        enabled_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assemble a system-prompt preview for the agent settings page.

        In-process replacement for the removed kernel HTTP /v1/prompt-preview
        endpoint (refactor-387 M3 regression).  Calls the same section-assembly
        path the runtime uses at turn time, but with RenderMode.PREVIEW so
        volatile segments emit ``<runtime-injected:…>`` placeholders rather than
        live data.

        The returned schema matches the IM side's PromptPreviewResponse contract
        so the frontend receives the same ``{prompt, section_count}`` shape as
        in the HTTP era.

        feat-394-M9: heartbeat/cron gates are now driven by ctx.flags via
        FEATURE_REGISTRY (decision D).  The old heartbeat_enabled/cron_enabled
        params (which injected into vars) are retired.  Pass them in ``features``
        instead: ``features={"heartbeat": True, "cron_scheduling": True}``.

        Args:
            workspace_root: Workspace root for skill resolution.  Falls back to
                the kernel's repo_root when None.
            features: Per-agent feature-flag overrides (key → bool).  Merged with
                FEATURE_REGISTRY defaults — same as runtime wiring.  Controls
                heartbeat/cron segments via features["heartbeat"]/["cron_scheduling"].
            custom_prompt: Optional user-supplied custom instructions injected into
                the pa.user_custom segment via ``vars["custom_prompt"]``.
            tool_ids: Tool names to treat as active for the preview turn.  Only
                names are needed — has_tool() checks gate guidance segments.
            scenario: Conversation type hint forwarded into PromptContext.scenario.
            skill_ids: Skill IDs to resolve from workspace for the skills listing.

        Returns:
            Dict with keys ``prompt`` (str) and ``section_count`` (int).
        """
        from agent.core.agent.prompt_sections.base import (  # noqa: PLC0415
            RenderMode,
            assemble_system_prompt,
        )
        from agent.core.agent.prompt_sections.wiring import (  # noqa: PLC0415
            build_prompt_context_from_metadata,
            resolve_flags_from_metadata,
        )
        from agent.core.types import ToolSpec  # noqa: PLC0415

        effective_root = workspace_root or self._repo_root

        # Resolve flags from feature overrides — mirrors runtime wiring.
        flags = resolve_flags_from_metadata(
            metadata={"agent_features": dict(features) if features else {}}
        )

        # Build lightweight ToolSpec stubs from IDs — schema is not needed for
        # preview; has_tool(name) only checks the name to gate guidance segments.
        # New path (决策 8) passes enabled_tools; legacy passes tool_ids.
        active_tool_ids = list(enabled_tools or tool_ids or [])
        active_tools: tuple[ToolSpec, ...] = tuple(
            ToolSpec(name=name, description="", input_schema={})
            for name in active_tool_ids
        )

        # Resolve skills for the listing segment — best-effort; non-existent
        # skill IDs silently produce empty SkillMetadata so the listing renders
        # whatever exists on disk without crashing (mirrors runtime path).
        active_skills: tuple = ()
        if skill_ids:
            try:
                from agent.core.skills import (  # noqa: PLC0415
                    make_skill_resolver,
                    resolve_available_skills,
                )

                # bugfix-431 决策 2: use make_skill_resolver (core helper) so preview,
                # list_skills and per-conversation engines share the same resolver
                # logic — eliminating the structural source of runtime/preview divergence.
                preview_resolver = make_skill_resolver(
                    effective_root,
                    self._workspace_config_dirname,
                    self._skill_search_roots,
                )
                active_skills = tuple(
                    resolve_available_skills(
                        workspace_root=effective_root,
                        include_names=tuple(skill_ids),
                        config_resolver=preview_resolver,
                    )
                )
            except Exception:  # noqa: BLE001
                # Skill resolution may fail when the workspace has no skills dir;
                # fall through to an empty listing rather than aborting the preview.
                active_skills = ()

        # feat-394-M9: heartbeat/cron gates now driven by ctx.flags (via features dict
        # above).  vars only carries custom_prompt; no heartbeat/cron injection needed.
        preview_vars: dict[str, str] = {"custom_prompt": custom_prompt or ""}

        ctx = build_prompt_context_from_metadata(
            metadata={"conversation_type": scenario},
            available_tools=active_tools,
            available_skills=active_skills,
            current_datetime=None,  # PREVIEW mode: segments emit placeholder
            cwd=str(effective_root),
            flags=flags,
            vars=preview_vars,
            render_mode=RenderMode.PREVIEW,
            # 决策 8: same-source preview — the consumer passes the same PromptSlots
            # its create_session uses, so preview == real assembly byte-for-byte.
            prompt_slots=prompt,
        )

        sections = getattr(self._c.engine_services, "_prompt_sections", [])
        assembled = assemble_system_prompt(sections, ctx)

        # Count active sections — segments that pass enabled_when and produce
        # non-empty output for this context.
        section_count = sum(
            1 for s in sections if s.enabled_when(ctx) and s.render(ctx)
        )

        return {"prompt": assembled, "section_count": section_count}

    @property
    def _broker(self) -> PermissionBroker:
        """Expose broker for testing purposes."""
        return self._c.permission_broker


def _bind_wiring_to_tool_registry(
    *,
    tool_registry: Any,
    hook_runner: HookRunner | None,
    wiring: Any | None = None,
) -> None:
    """Backfill hook and platform wiring onto pre-bootstrapped tool registries.

    Mirrors the identical helper in platform/http_api/app.py to avoid a
    cross-module dependency on the HTTP layer from sdk.
    """
    setattr(tool_registry, "_hook_runner", hook_runner)
    tools = getattr(tool_registry, "_tools", {})
    for tool_name in ("agent", "bash", "task_stop"):
        tool = tools.get(tool_name)
        bind_wiring = getattr(tool, "bind_wiring", None)
        if callable(bind_wiring):
            bind_wiring(wiring)


def _build_session_event_publisher_factory(
    *,
    event_hub: EventStreamHub,
) -> Callable:
    """Build session-bound event publisher factory for hook contexts.

    Mirrors the identical factory in platform/http_api/app.py.
    """

    def _factory(session_id: str) -> Callable | None:
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            return None

        def _publish(event: str, data: dict[str, Any]) -> None:
            if not isinstance(event, str) or not event.strip():
                return
            payload = dict(data)
            payload["session_id"] = normalized_session_id
            event_hub.publish(
                event=event,
                session_id=normalized_session_id,
                data=payload,
            )

        return _publish

    return _factory
