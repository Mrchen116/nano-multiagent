"""agent.sdk.Kernel — in-process agent kernel assembly and interface.

build_kernel() is the composition root: it assembles platform components into
a ready-to-use Kernel without exposing any HTTP/FastAPI surface.

Design (refactor-387 M1):
- Mirrors create_app() assembly logic with FastAPI/routes/middleware removed.
- LLMClientFactory injected into AgentRuntime (decision 4, #40).
- Permission flow: runtime._build_hook_context races optional can_use_tool
  callback against a PermissionBroker future; gateway resolves the future
  externally via Kernel.submit_permission_decision (feat-394-M14).
- All methods async-native; RunsRegistry runs in its own background loop
  (decision 2 — pre-condition for M2 async-native CLI).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable, Sequence

from agent.core.agent.runtime import AgentRuntime
from agent.core.hooks.registry import HookRegistry
from agent.core.hooks.runner import HookRunner
from agent.core.llm.factory import LLMFactoryConfig
from agent.core.llm.interfaces import LLMClient
from agent.core.observability.exporters.console import ConsoleTracer
from agent.core.observability.tracing import set_tracer
from agent.core.runs.registry import RunsRegistry
from agent.core.runs.origin import RunOrigin
from agent.core.session.jsonl_store import JsonlSessionStore
from agent.platform.background_tasks.wiring import wire_background_tasks
from agent.platform.config.auto_mode import AutoModeConfig
from agent.platform.hooks.loader import build_hook_registry
from agent.platform.hooks.session_events import set_session_event_publisher_factory
from agent.core.events.hub import EventStreamHub
from agent.platform.llm.factory import create_llm_client as _platform_create_llm_client
from agent.platform.permissions.broker import (
    PermissionBroker,
    PermissionDecision,
)
from agent.platform.persistence.session.service import SessionService

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

if TYPE_CHECKING:
    pass

# Callable type for the permission strategy injected by consumers.
# Mirrors CC CanUseToolFn: given (tool_name, tool_input, context) → PermissionDecision.
CanUseToolFn = Callable[[str, Any, Any], Awaitable[PermissionDecision]]


@dataclass
class _KernelComponents:
    """Hold all assembled platform components for a Kernel instance."""

    runtime: AgentRuntime
    runs_registry: RunsRegistry
    event_hub: EventStreamHub
    permission_broker: PermissionBroker
    session_service: SessionService
    hook_registry: HookRegistry
    hook_runner: HookRunner


def build_kernel(
    *,
    # 2-layer surface (refactor-406 决策 1/2/5) — the sole composition entry.
    llm: LLMConfig | None = None,
    tools: Sequence[Any] | None = None,
    hooks: Sequence[Callable[[Any], None]] | None = None,
    workspace_config_dirname: str | None = None,
    can_use_tool: CanUseToolFn | None = None,
    repo_root: Path | None = None,
    skill_search_roots: Sequence[Path] = (),
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
        tools: Native tool objects satisfying the SDK ``Tool`` Protocol.
        hooks: ``setup(hooks)`` callables registered into the hook registry.
        workspace_config_dirname: Per-workspace config dir name (e.g. ``.nanocode``)
            governing session JSONL / memory / skill layout.
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
    """
    if llm is None:
        raise ValueError("build_kernel requires llm= (2-layer surface)")
    return _build_kernel_base(
        llm=llm,
        tools=list(tools or ()),
        hooks=list(hooks or ()),
        workspace_config_dirname=workspace_config_dirname or ".nano",
        can_use_tool=can_use_tool,
        repo_root=repo_root,
        skill_search_roots=tuple(skill_search_roots),
        tool_search_roots=tuple(tool_search_roots),
        hook_search_roots=tuple(hook_search_roots),
        _llm_client_override=_llm_client_override,
    )


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
        title=getattr(session, "title", None),
        workspace_root=str(workspace_root) if workspace_root is not None else None,
        metadata=dict(metadata),
    )


def _to_run_info(record: Any) -> RunInfo:
    """Map an internal RunRecord to the SDK-owned RunInfo boundary DTO."""
    status = getattr(record, "status", None)
    return RunInfo(
        run_id=record.run_id,
        session_id=record.session_id,
        # status may be an enum (with .value) or already a string.
        status=getattr(status, "value", status) if status is not None else "",
        start_sequence=int(getattr(record, "start_sequence", 0) or 0),
    )


def _factory_config_to_llm_config(
    cfg: Any, *, catalog: LLMConfig | None = None
) -> LLMConfig:
    """Map the internal LLMFactoryConfig to the SDK-owned LLMConfig boundary DTO.

    Preserves the catalog (providers / default_model) from the build-time
    ``catalog`` when available, so ``get_llm_config`` / ``reconfigure_llm`` carry
    the full provider list, not just the active connection.
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


def _build_kernel_base(
    *,
    llm: LLMConfig,
    tools: list[Any],
    hooks: list[Callable[[Any], None]],
    workspace_config_dirname: str,
    can_use_tool: CanUseToolFn | None,
    repo_root: Path | None,
    skill_search_roots: tuple[Path, ...] = (),
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

    session_store = JsonlSessionStore(
        data_dir=None,
        workspace_config_dirname=workspace_config_dirname,
    )
    # Thread workspace_config_dirname into the session-metadata baseline so the
    # kernel built-in MemoryTool derives memory_root per-session via
    # derive_memory_root(workspace_root, workspace_config_dirname) — the same path the
    # runtime's memory snapshot reads from. workspace_config_dirname is a deployment
    # constant (build_kernel scope); workspace_root is injected per-session by the
    # runtime. Mirrors the legacy bootstrap default_session_metadata threading and
    # decision 10's "store is stateless, location comes from workspace_root" pattern.
    session_service = SessionService(
        store=session_store,
        default_session_metadata={"workspace_config_dirname": workspace_config_dirname},
    )

    permission_broker = PermissionBroker(config=AutoModeConfig())

    # Hook registry: built-in hooks + consumer setup callables (决策 2).
    # refactor-406-M3fix #2: when the consumer supplies deployment-level hook dirs
    # (hook_search_roots, same pattern as skill_search_roots — no ConfigResolver), feed
    # them via a minimal resolver whose user_hook_roots() = workspace <repo>/.nano/hooks
    # FIRST then the deployment roots, so build_hook_registry discovers both. Absent →
    # the resolver-less path which already scans <repo>/.nano/hooks (unchanged behavior).
    if hook_search_roots:
        hook_resolver = _SearchRootsResolver(
            workspace_dir=resolved_repo_root / ".nano" / "hooks",
            extra_roots=hook_search_roots,
        )
        hook_registry = build_hook_registry(
            repo_root=resolved_repo_root, config_resolver=hook_resolver
        )
    else:
        hook_registry = build_hook_registry(repo_root=resolved_repo_root)
    for setup in hooks:
        setup(hook_registry)
    hook_runner = HookRunner(registry=hook_registry)

    if _llm_client_override is not None:
        llm_client_factory = None
        direct_llm_client: LLMClient | None = _llm_client_override
    else:
        llm_client_factory = lambda cfg: _platform_create_llm_client(config=cfg)  # noqa: E731
        direct_llm_client = None

    runtime = AgentRuntime(
        session_manager=session_service.manager,
        hook_runner=hook_runner,
        repo_root=resolved_repo_root,
        permission_broker=permission_broker,
        llm_client=direct_llm_client,
        llm_client_factory=llm_client_factory,
        model=factory_config.model,
        # Product-neutral kernel skeleton; product text enters per-session via
        # create_session(prompt=PromptSlots) (决策 8).
        prompt_sections=build_kernel_prompt_skeleton(),
    )
    # Inject the env-resolved active connection so get_llm_config reflects llm=.
    runtime._llm_config = factory_config  # type: ignore[attr-defined]

    event_hub = EventStreamHub()
    set_session_event_publisher_factory(
        registry=hook_registry,
        factory=_build_session_event_publisher_factory(event_hub=event_hub),
    )

    runs_registry = RunsRegistry(
        runtime=runtime,
        session_manager=session_service.manager,
        event_hub=event_hub,
        hook_runner=hook_runner,
    )

    background_task_wiring = wire_background_tasks(
        workspace_root=resolved_repo_root,
        runtime=runtime,
        runs_registry=runs_registry,
    )

    # bugfix-417-M5 (#114): wire the foreground-tool subprocess reaper so
    # kernel.interrupt / kernel.cancel kill an in-flight foreground bash subprocess
    # tree (and force-cancel the parked carrier Task) instead of leaving an orphan.
    # Injected post-hoc because the wiring is built after the registry (it needs the
    # registry's event loop). The core registry only sees the ForegroundStopper
    # port — it never imports the platform BackgroundTaskRegistry (core stays
    # platform-free).
    runs_registry.set_foreground_stopper(
        background_task_wiring.registry.stop_foreground_for_session
    )

    # Tool catalog: built-ins + consumer native tool objects (决策 2). The native
    # objects satisfy the SDK Tool Protocol and are registered into the registry
    # directly — no _product_root() directory scan.
    set_tool_safety_factory(ToolSafety)
    set_tool_safety_config_factory(ToolSafetyConfig)
    base_context = CoreToolContext.create(
        repo_root=resolved_repo_root,
        safety_config=load_tool_safety_config(repo_root=resolved_repo_root),
        llm_client=getattr(runtime, "_llm_client", None),
    )
    tool_registry = ToolRegistry(context=base_context, hook_runner=hook_runner)
    register_builtin_tools(
        tool_registry, runtime=runtime, wiring=background_task_wiring
    )
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
    )
    for tool in tools:
        tool_registry.register(tool, replace=True)

    # refactor-406-M3fix #1 (决策2 红线)：恢复工作区 `<repo_root>/.nano/tools` 运行时
    # 工具发现——决策2 明写「.nano/tools 运行时发现机制不变」，但新 build_kernel 直接手搓
    # registry（builtins + 显式 tools=）跳过了它。仅扫 workspace .nano/tools（字面 .nano，
    # 非 workspace_config_dirname），不经 ConfigResolver。
    # refactor-406-M3fix-r2 R2-1 (崩溃回归修)：用 _load_tools_from_single_dir(replace=True)
    # 而非 load_tools_from_directory(replace=False)——后者遇到工作区 .nano/tools 里与内置
    # 同名的 override（如 bash.py 导出 name='bash'）会 register 抛 ValueError → build_kernel
    # 崩溃、Gateway/CLI 起不来。旧行为允许 .nano/tools override 内置（replace=True），且与下方
    # user-root 加载一致。
    from agent.platform.tools.loader import (  # noqa: PLC0415
        _load_tools_from_single_dir,
    )

    workspace_tools_dir = resolved_repo_root / ".nano" / "tools"
    if workspace_tools_dir.is_dir():
        _load_tools_from_single_dir(
            tool_root=workspace_tools_dir, registry=tool_registry, replace=True
        )

    # refactor-406-M3fix #2: deployment-level user tool dirs (tool_search_roots, same
    # consumer-supplied-roots pattern as skill_search_roots — no ConfigResolver). Loaded
    # after workspace .nano/tools so user-level plugins are discovered too.
    for tool_root in tool_search_roots:
        resolved_tool_root = Path(tool_root).expanduser().resolve()
        if resolved_tool_root.is_dir():
            _load_tools_from_single_dir(
                tool_root=resolved_tool_root, registry=tool_registry, replace=True
            )

    _bind_runtime_to_tool_registry(
        tool_registry=tool_registry,
        runtime=runtime,
        hook_runner=hook_runner,
        wiring=background_task_wiring,
    )
    bind_tool_registry = getattr(runtime, "bind_tool_registry", None)
    if callable(bind_tool_registry):
        bind_tool_registry(tool_registry)

    components = _KernelComponents(
        runtime=runtime,
        runs_registry=runs_registry,
        event_hub=event_hub,
        permission_broker=permission_broker,
        session_service=session_service,
        hook_registry=hook_registry,
        hook_runner=hook_runner,
    )

    return Kernel(
        components=components,
        can_use_tool=can_use_tool,
        repo_root=resolved_repo_root,
        llm_catalog=llm,
        workspace_config_dirname=workspace_config_dirname,
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
    )

    tool_registry.register(
        SkillManageTool(
            workspace_config_dirname=workspace_config_dirname,
            extra_roots=skill_search_roots,
        ),
        replace=True,
    )
    tool_registry.register(MemoryTool(), replace=True)


class _WorkspaceDirnameSkillResolver:
    """Minimal SkillRootResolver for the 2-layer path (no ProductProfile).

    Resolves skills under ``<workspace_root>/<workspace_config_dirname>/skills``
    FIRST (per-workspace), then the build-time deployment ``extra_roots`` (shared
    user-level/global/compat skill dirs the consumer factory owns), deduplicating by
    directory while preserving order. This is the kernel-neutral equivalent of the
    legacy reporter's 4-tier search (workspace → global → compat-claude →
    compat-codex): the kernel only searches the roots it is handed, so it stays
    product-neutral; the consumer passes its product-specific deployment roots via
    ``build_kernel(skill_search_roots=)``.
    """

    def __init__(
        self,
        *,
        workspace_root: Path,
        workspace_config_dirname: str,
        extra_roots: tuple[Path, ...] = (),
    ) -> None:
        ordered: list[Path] = [
            (workspace_root / workspace_config_dirname / "skills")
            .expanduser()
            .resolve()
        ]
        for root in extra_roots:
            resolved = Path(root).expanduser().resolve()
            if resolved not in ordered:
                ordered.append(resolved)
        self._roots = tuple(ordered)

    def user_skill_roots(self) -> tuple[Path, ...]:
        return self._roots


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

        # Inject can_use_tool into runtime so _build_hook_context can race it
        # against the broker future when building _permission_requester closures.
        # None = no consumer callback; permission gates rely solely on broker futures
        # (resolved externally via submit_permission_decision).
        if can_use_tool is not None:
            self._c.runtime._can_use_tool = can_use_tool  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Public API — mirrors design.md §接口与数据流
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        title: str | None = None,
        workspace_root: Path | None = None,
        # --- new (refactor-406 决策 1/6/8) per-agent config ---
        enabled_tools: list[str] | None = None,
        features: dict[str, bool] | None = None,
        prompt: PromptSlots | None = None,
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
        effective_root = (workspace_root or self._repo_root).expanduser().resolve()

        effective_allowlist = (
            enabled_tools if enabled_tools is not None else tool_allowlist
        )
        effective_metadata = dict(metadata) if metadata else {}
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

        session = self._c.session_service.create_session(
            workspace_root=effective_root,
            title=title,
            skills=tuple(skills) if skills else None,
            tool_allowlist=tuple(effective_allowlist) if effective_allowlist else None,
            metadata=effective_metadata or None,
        )

        # Register per-session PromptSlots on the runtime (决策 8). The slots are
        # read structurally at turn time; not persisted (rebuilt per process by
        # the consumer factory on session open).
        if prompt is not None:
            self._c.runtime.register_session_prompt_slots(session.session_id, prompt)

        return _to_session_info(session)

    async def fork_session(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> SessionInfo:
        """Fork an existing session for parallel execution.

        Args:
            session_id: Source session to fork from.
            workspace_root: Workspace root for the forked session.

        Returns:
            SessionInfo for the new forked session.
        """
        effective_root = workspace_root or self._repo_root
        session = self._c.session_service.create_session(
            workspace_root=effective_root,
        )
        return _to_session_info(session)

    async def compact(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
    ) -> Any:
        """Compact session context (summarise old turns to save tokens).

        Args:
            session_id: Session to compact.
            workspace_root: Session workspace root.

        Returns:
            CompactResult or None when compaction is skipped.
        """
        effective_root = workspace_root or self._repo_root
        return await self._c.runtime.compact(session_id, workspace_root=effective_root)

    def submit(
        self,
        *,
        session_id: str,
        parts: list[dict],
        origin: RunOrigin = RunOrigin.USER,
        workspace_root: Path | None = None,
        trace_id: str | None = None,
    ) -> RunInfo:
        """Schedule a turn on the background loop and return immediately.

        Args:
            session_id: Session to run the turn in.
            parts: Input parts (text, image, etc.) for this turn.
            origin: Message origin (user, system, background, etc.).
            workspace_root: Session workspace root.
            trace_id: Optional trace correlation id.

        Returns:
            RunInfo with run_id / session_id / status (initially QUEUED).
        """
        effective_root = workspace_root or self._repo_root
        record = self._c.runs_registry.submit(
            session_id=session_id,
            parts=parts,
            origin=origin,
            workspace_root=effective_root,
            trace_id=trace_id,
        )
        return _to_run_info(record)

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
        tool_registry = getattr(self._c.runtime, "_tool_registry", None)
        if tool_registry is None:
            return {}
        list_tools = getattr(tool_registry, "list_tools", None)
        if callable(list_tools):
            return list_tools(session_id=session_id)
        return {}

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

        active = self._c.runtime.get_llm_config()
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

        tool_registry = getattr(self._c.runtime, "_tool_registry", None)
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
        from agent.core.skills.discovery import resolve_available_skills  # noqa: PLC0415

        effective_root = Path(workspace_root or self._repo_root).expanduser().resolve()

        # Per-workspace skill discovery requires a config_resolver bound to THIS
        # call's workspace_root — not the build-time one. The 2-layer path resolves
        # skills under the consumer's per-workspace config dir
        # (<workspace_root>/<workspace_config_dirname>/skills) plus the deployment-level
        # skill_search_roots, so list_skills is per-workspace with no cross-workspace
        # mixing (决策 4). (The legacy ProductProfile-bound ConfigResolver path was
        # removed in refactor-406-M2 with products/.)
        per_call_resolver = None
        if self._workspace_config_dirname:
            per_call_resolver = _WorkspaceDirnameSkillResolver(
                workspace_root=effective_root,
                workspace_config_dirname=self._workspace_config_dirname,
                extra_roots=self._skill_search_roots,
            )

        skills = resolve_available_skills(
            workspace_root=effective_root,
            config_resolver=per_call_resolver,
        )
        return [
            SkillInfo(name=s.name, description=getattr(s, "description", "") or "")
            for s in skills
        ]

    def get_llm_config(self) -> LLMConfig:
        """Return the active LLM configuration as an SDK-owned ``LLMConfig`` (决策 5).

        Returns:
            LLMConfig with current provider/model/endpoint + build-time catalog.
        """
        return _factory_config_to_llm_config(
            self._c.runtime.get_llm_config(), catalog=self._llm_catalog
        )

    def reconfigure_llm(self, **patch: Any) -> LLMConfig:
        """Reconfigure provider/model connection without recreating the runtime.

        Used by CLI ``/model`` (决策 5 scope A): switches the kernel-level model
        with immediate effect; subsequent turns use the new model.

        Args:
            **patch: Fields to update on the active connection
                (provider, model, base_url, timeout_seconds, api_key).

        Returns:
            Updated LLMConfig DTO.
        """
        updated = self._c.runtime.reconfigure_llm(**patch)
        return _factory_config_to_llm_config(updated, catalog=self._llm_catalog)

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
        workspace_root: Path | None = None,
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
        effective_root = workspace_root or self._repo_root
        result = self._c.session_service.append_message(
            session_id,
            role=role,
            content=content,
            message_id=message_id,
            parts=parts,
            metadata=metadata,
            idempotency_key=idempotency_key,
            workspace_root=effective_root,
        )
        # Keep the runtime's cache-first history coherent with this out-of-band
        # JSONL write. The runtime serves _session_histories cache-first, so a
        # message appended between turns is invisible to the next run unless the
        # stale entry is dropped and the transcript re-read (feat-394: cron
        # awareness injection was written but never seen by the model).
        self._c.runtime.invalidate_session_cache(session_id)
        return result

    def get_session(
        self,
        session_id: str,
        *,
        workspace_root: Path | None = None,
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
        effective_root = workspace_root or self._repo_root
        session = self._c.session_service.manager.get_session(
            session_id, workspace_root=effective_root
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
        loop = registry.get_event_loop()
        if loop is not None and loop.is_running():
            # Run shutdown() in a thread so the Registry's blocking drain_future.result()
            # does not block this event loop.  shutdown() itself handles DRAINING→CLOSED
            # and awaiting owned tasks before stopping the Registry loop.
            await _asyncio.to_thread(registry.shutdown)
        else:
            registry.shutdown()

    def close(self) -> None:
        """Shut down background loops (sync-compat wrapper for non-async consumers).

        Callers inside an event loop must use ``aclose()`` to avoid blocking.
        This method is retained for backward compatibility with sync-only call sites.
        """
        if getattr(self, "_closed", False):
            return
        self._closed = True
        self._c.runs_registry.shutdown()

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
                from agent.core.skills import resolve_available_skills  # noqa: PLC0415

                # refactor-406-M3fix #3 (决策8 同源)：2 层路径 runtime._config_resolver 恒
                # None → 旧实现 resolve_available_skills(config_resolver=None) 走 default
                # 搜索根（不含 <ws>/<dirname>/skills + 部署 root），skill_ids 解析恒空白、
                # 技能段不出现。改用与 list_skills 同源的 _WorkspaceDirnameSkillResolver
                # （per-call workspace_root + 部署 skill_search_roots），preview = 真实会话。
                preview_resolver = (
                    _WorkspaceDirnameSkillResolver(
                        workspace_root=effective_root,
                        workspace_config_dirname=self._workspace_config_dirname,
                        extra_roots=self._skill_search_roots,
                    )
                    if self._workspace_config_dirname
                    else None
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

        sections = getattr(self._c.runtime, "_prompt_sections", [])
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


def _bind_runtime_to_tool_registry(
    *,
    tool_registry: Any,
    runtime: AgentRuntime,
    hook_runner: HookRunner | None,
    wiring: Any | None = None,
) -> None:
    """Backfill runtime/hook wiring onto pre-bootstrapped tool registries.

    Mirrors the identical helper in platform/http_api/app.py to avoid a
    cross-module dependency on the HTTP layer from sdk.
    """
    setattr(tool_registry, "_hook_runner", hook_runner)
    tools = getattr(tool_registry, "_tools", {})
    for tool_name in ("agent", "bash", "task_stop"):
        tool = tools.get(tool_name)
        bind_runtime = getattr(tool, "bind_runtime", None)
        if callable(bind_runtime):
            bind_runtime(runtime)
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
