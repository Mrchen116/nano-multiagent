# bugfix-431: runtime skill resolution 与 preview 不一致 — 技术方案

> 对齐: incident.md v1
>
> Unit branch: `unit/bugfix-431` (will be created by orchestrator)

## Changelog

<!-- design 阶段保持空 -->

## 现状分析

### 涉及范围

- `src/agent/sdk/kernel.py`
  - `build_kernel()`：构造 `AgentRuntime` 和 `Kernel`；持有 `workspace_config_dirname` 和 `skill_search_roots`。
  - `Kernel.list_skills(workspace_root)`：已正确，每次调用时基于 `_workspace_config_dirname + _skill_search_roots` 构造 `_WorkspaceDirnameSkillResolver`。
  - `Kernel.assemble_prompt_preview()`：已正确（refactor-406-M3fix #3），同样构造 `_WorkspaceDirnameSkillResolver` 解析 `skill_ids`。
  - `_WorkspaceDirnameSkillResolver`：per-call 构造，roots = `<workspace>/<dirname>/skills` + `extra_roots`。
- `src/agent/core/agent/runtime.py`
  - `AgentRuntime`：仍保留 `config_resolver: ConfigResolverLike | None` 字段；`build_kernel()` 未传值，故恒为 `None`。
  - `_resolve_session_available_skills*`：调用 `resolve_available_skills(..., config_resolver=self._config_resolver)`。
  - `AgentRuntime.config_resolver` property：被 `agent` 工具读取，用于子 agent 的 `load_skills` 校验。
- `src/agent/core/skills/discovery.py`
  - `resolve_available_skills(..., config_resolver=None)` 回退到 Codex-only 默认 roots。
  - 当 `config_resolver` 非 None 时，会**完全使用 resolver 的 roots，忽略传入的 workspace_root**——这是 legacy 固定 resolver 语义，不适合 2 层路径 per-workspace 需求。
- `src/agent/platform/tools/builtins/agent.py`
  - `_validate_new_agent_args()`：校验 `load_skills` 时用 `runtime.config_resolver`。
  - `_create_subagent_session()`：创建子 agent session 时传 `skills=load_skills`，子 agent 运行时同样受 `runtime.config_resolver` 影响。

### 既有约束

- `coding_cli` / `personal_assistant` 只能 `import agent.sdk`，不能反向 import `agent.core` / `agent.platform`。
- `agent.core` 不能 import `agent.platform`。
- `refactor-406` 明确退役 `ConfigResolver`，不能复活。
- kernel 必须保持 product-neutral：只搜索 `build_kernel` 被告知的 roots。

### 可复用能力

- `_WorkspaceDirnameSkillResolver` 可直接复用。
- `PA_SKILL_SEARCH_ROOTS`（`~/.nanoassistant/skills`、`~/.claude/skills`、`~/.codex/skills`）已由 PA 工厂维护并传入 `build_kernel(skill_search_roots=...)`。
- `resolve_available_skills` 调用点已存在，只需注入正确的 resolver。

### 相关历史

- `refactor-406` 解散 `agent/products/`、退役 `ConfigResolver`，建立 2 层装配 + `skill_search_roots`。
- `refactor-406-M3fix #3` 修了 preview 的 resolver，但漏了 runtime 的 `_resolve_session_available_skills*` 和 `agent` 工具的调用点。

## 架构总览

```mermaid
graph TD
    subgraph PA[personal_assistant]
        Factory[build_pa_kernel]
        Factory -->|skill_search_roots=PA_SKILL_SEARCH_ROOTS| SDK
    end

    subgraph SDK[agent.sdk]
        BK[build_kernel]
        K[Kernel]
        Helper["_make_skill_resolver(ws_root, dirname, extra_roots)"]
        Resolver[_WorkspaceDirnameSkillResolver]
        BK -->|注入 dirname + extra_roots| RT
        BK -->|同参数构造| K
        Helper -->|构造| Resolver
        K -->|调用 Helper| Helper
    end

    subgraph Core[agent.core]
        RT[AgentRuntime]
        Loop[AgentLoop]
        RT -->|持有| Loop
        RT -->|resolve_available_skills(ws, names)| SkillDisc
        SkillDisc[resolve_available_skills]
    end

    subgraph Platform[agent.platform]
        AgentTool[agent tool]
        AgentTool -->|runtime.resolve_available_skills(ws, names)| RT
    end

    RT -->|内部调用 Helper| Helper

    SDK -.->|当前 bug：未注入 dirname/extra_roots| RT
    RT -.->|config_resolver=None| SkillDisc
    SkillDisc -.->|回退 Codex roots| Roots[(~/.codex/skills only)]
```

**Before**：`AgentRuntime` 持有一个退役后恒为 `None` 的 `config_resolver`。runtime skill resolution 回退到 Codex-only 默认路径；preview / `list_skills` 已经走 `_WorkspaceDirnameSkillResolver`，三者不同源。

**After**：`agent.sdk.kernel` 抽取统一 helper `_make_skill_resolver`；`Kernel.list_skills`、`Kernel.assemble_prompt_preview`、`AgentRuntime.resolve_available_skills`、子 agent 校验全部经该 helper 构造 `_WorkspaceDirnameSkillResolver`。runtime 与 preview 完全同源，且未来改 skill 发现规则只改一处。

## 关键决策

用户授权：按架构最优选择，强调 preview 与 runtime 必须**同源**（同一处 resolver 构造逻辑），未来 system prompt 变更也能自然保持一致。

### 决策 1：runtime skill resolver 的注入方式

**选择**：让 `AgentRuntime` 持有 `workspace_config_dirname` 和 `skill_search_roots`，内部按需构造 `_WorkspaceDirnameSkillResolver`，不复活 `ConfigResolver`。

- **理由**：
  - `Kernel` 已经用同一组参数（`_workspace_config_dirname + _skill_search_roots`）构造 resolver，这是经过验证的 2 层路径模式。
  - `_WorkspaceDirnameSkillResolver` 是 per-call 构造的，天然适合 runtime 里每个 session / 子 agent 的不同 `workspace_root`。
  - 不需要改变 `resolve_available_skills` 的 public 签名或 `SkillRootResolver` Protocol。
- **拒绝**：
  - 在 `build_kernel` 里构造一个固定 workspace_root 的 `_WorkspaceDirnameSkillResolver` 传给 `AgentRuntime`：这会让不同 session 的 workspace skill root 被固定为 build-time repo_root，违反 per-agent 隔离。
  - 复活 `ConfigResolver`：`refactor-406` 明确退役该抽象，且 2 层路径下没有 ProductProfile 可供其绑定。
  - 让 `AgentRuntime.config_resolver` property 继续返回固定 resolver：legacy 语义会忽略传入的 `workspace_root`，无法处理多 workspace。
- **风险**：需要改动 `AgentRuntime.__init__` 签名；`agent` 工具读取 `runtime.config_resolver` 的调用点需同步处理。

### 决策 2：统一 resolver 构造逻辑，保证 preview / runtime / list_skills / agent 工具同源

**选择**：在 `agent.sdk.kernel` 内抽取一个私有 helper `_make_skill_resolver(workspace_root, workspace_config_dirname, skill_search_roots)`，所有 skill 发现路径都经它构造 `_WorkspaceDirnameSkillResolver`。

- **理由**：
  - **同源**：`Kernel.list_skills`、`Kernel.assemble_prompt_preview`、`AgentRuntime`、子 agent 校验全部走同一 helper，消除"preview 修了 runtime 没修"的结构性复发条件。
  - **未来-proof**：以后改 system prompt 相关的 skill 发现规则（如新增 skill root 类型、改 dedup 顺序），改一处即可，preview 与 runtime 自动一致。
  - **对齐既有最佳实践**：`features` 开关、`prompt_context` 的 volatile 段已经采用"统一 helper + per-call 构造"的同源模式，本决策把 skills 发现对齐到同一模式。
  - 保持 kernel product-neutral：helper 不硬编码 PA 路径，只组合调用方传入的 `workspace_config_dirname + skill_search_roots`。
- **拒绝**：
  - 让 `AgentRuntime` 自己内部拼 resolver、preview 用另一套代码：正是当前 bug 的根因，不能重复。
  - 把 helper 放到 `agent.core`：`agent.core` 不感知 `skill_search_roots` 这些部署级输入（那是 SDK 装配参数），放 core 会破坏层级。
- **风险**：helper 是 sdk 内部私有符号，不进入 public surface；需确保 `tests/contract/test_agent_sdk_surface_contract.py` 不把它当成新增公共导出。

### 决策 3：替换 `AgentRuntime.config_resolver` 为显式 `resolve_available_skills` 方法

**选择**：移除 `AgentRuntime.config_resolver` property，新增 `AgentRuntime.resolve_available_skills(workspace_root, include_names)` 方法；`agent` 工具的 `load_skills` 校验改为调用 runtime 该方法。

- **理由**：
  - `config_resolver` 是 legacy ProductProfile / ConfigResolver 时代的残留，2 层路径下没有固定 resolver 的概念（roots 是 per-workspace 的）。
  - 直接让 runtime 暴露一个高阶方法，内部使用决策 2 的统一 helper，调用方无需关心 resolver 细节。
  - 避免 `resolve_available_skills(..., config_resolver=...)` 当前"忽略传入 workspace_root"的 legacy 语义陷阱。
- **拒绝**：
  - 保留 `config_resolver` property 改语义：property 不能带 workspace_root 参数，无法自然表达 per-workspace；若返回"共享 roots"对象又需要改 `default_skill_search_roots` 语义，引入额外耦合。
  - 混淆 tools/hooks 路径：tools/hooks 的 resolver 由 SDK 装配层直接注入（`build_kernel` 时构造 `_SearchRootsResolver` 传给 loader），不走 runtime property；skills 改为 runtime 方法是刻意的不对称，不能把 tools/hooks 也拉进 runtime。
- **风险**：`AgentRuntime.config_resolver` 可能还有测试或旧代码引用，需 grep 全仓后同步更新或保留兼容层；`agent` 工具的改点仅 `_validate_new_agent_args` 一处。

### 决策 4：清理 `default_skill_search_roots` 的 Codex roots 默认回退

**选择**：当 `config_resolver=None` 且未传入 `product_skill_root` 时，`default_skill_search_roots` 返回空元组，不再隐式回退到 `~/.codex/skills` / `<ws>/.codex/skills` / `<ws>/.nano/skills`。

- **理由**：
  - 这些默认 roots 是 legacy ProductProfile / Codex 兼容路径的残留；2 层路径下，`~/.codex/skills` 已由消费者通过 `skill_search_roots` 显式传入，`<ws>/.codex/skills` 和 `<ws>/.nano/skills` 没有产品使用。
  - 隐式默认根违背"kernel product-neutral + 只搜索被告知 roots"的架构原则，且正是本次 bug 中"preview 走了显式 roots、runtime 走了隐式默认 roots"不同源的原因之一。
  - 清理后，所有 skill 发现必须显式声明 roots（通过 resolver 或 `SkillRegistry(search_roots=...)`），行为更可预测。
- **拒绝**：
  - 保留默认回退：继续留下隐式双路径，未来仍可能再次出现 preview/runtime 漂移。
- **风险**：
  - 任何直接调用 `resolve_available_skills(config_resolver=None)` 且无显式 roots 的代码/测试会拿到空 skills，需要同步更新。
  - `product_skill_root` 参数可能随之可移除，但为减少签名变更波及面，本 unit 先将其行为与"显式 root"对齐（非 None 时仍生效），不删除参数。

## 接口与数据流

### 核心数据流（修复后）

```mermaid
sequenceDiagram
    participant PA as personal_assistant
    participant SDK as agent.sdk build_kernel
    participant Helper as _make_skill_resolver
    participant RT as AgentRuntime
    participant Disc as resolve_available_skills
    participant LLM as LLM Proxy

    PA->>SDK: build_kernel(skill_search_roots=PA_SKILL_SEARCH_ROOTS, workspace_config_dirname=".nanoassistant")
    SDK->>RT: AgentRuntime(workspace_config_dirname=..., skill_search_roots=...)

    Note over RT: create_session(skills=["change-design-author", ...])

    RT->>Helper: _make_skill_resolver(session.workspace_root, dirname, extra_roots)
    Helper->>Disc: _WorkspaceDirnameSkillResolver
    RT->>Disc: resolve_available_skills(workspace_root, include_names, config_resolver=resolver)
    Disc-->>RT: 12 SkillMetadata

    RT->>LLM: system prompt with <available_skills> = 12 skills
```

### 关键接口变化

```python
# agent.sdk.kernel — 新增私有 helper

def _make_skill_resolver(
    workspace_root: Path,
    workspace_config_dirname: str | None,
    skill_search_roots: tuple[Path, ...],
) -> SkillRootResolver | None:
    """Build a per-workspace skill resolver from the same inputs used by preview/list_skills."""
    if not workspace_config_dirname:
        return None
    return _WorkspaceDirnameSkillResolver(
        workspace_root=workspace_root,
        workspace_config_dirname=workspace_config_dirname,
        extra_roots=skill_search_roots,
    )

# agent.sdk.kernel.build_kernel
runtime = AgentRuntime(
    ...
    workspace_config_dirname=workspace_config_dirname,
    skill_search_roots=tuple(Path(r).expanduser().resolve() for r in skill_search_roots),
    ...
)

# agent.core.agent.runtime.AgentRuntime
class AgentRuntime:
    def __init__(
        self,
        *,
        ...
        # 新增（替代恒为 None 的 config_resolver）
        workspace_config_dirname: str | None = None,
        skill_search_roots: tuple[Path, ...] = (),
        ...
    ) -> None:
        ...

    def resolve_available_skills(
        self,
        workspace_root: Path,
        include_names: Sequence[str] | None = None,
    ) -> tuple[SkillMetadata, ...]:
        """Resolve skills for a workspace using the same roots as preview/list_skills.

        Returns an empty tuple when no workspace_config_dirname was supplied at
        build time, matching the cleaned-up default_skill_search_roots behavior.
        """
        if not self._workspace_config_dirname:
            return ()
        resolver = _make_skill_resolver(
            workspace_root,
            self._workspace_config_dirname,
            self._skill_search_roots,
        )
        return resolve_available_skills(
            workspace_root=workspace_root,
            include_names=include_names,
            config_resolver=resolver,
        )

# agent.platform.tools.builtins.agent._validate_new_agent_args
# 从：
#   config_resolver = getattr(self._runtime, "config_resolver", None)
#   available = resolve_available_skills(workspace_root=ctx.repo_root, include_names=load_skills, config_resolver=config_resolver)
# 改为：
    available = self._runtime.resolve_available_skills(
        workspace_root=ctx.repo_root,
        include_names=load_skills,
    )
```

### 调用方改造清单

| 调用方 | 当前 | 改后 |
|---|---|---|
| `AgentRuntime._resolve_session_available_skills` | `resolve_available_skills(..., config_resolver=self._config_resolver)` | 调用 `self.resolve_available_skills(session.workspace_root, session.skills)` |
| `AgentRuntime._resolve_session_available_skills_from_config` | 同上 | 调用 `self.resolve_available_skills(config.workspace_root, config.skills)` |
| `AgentRuntime._compact` 路径 | `self._resolve_session_available_skills_from_config(config)` | 复用上述方法 |
| `agent` 工具 `_validate_new_agent_args` | `resolve_available_skills(..., config_resolver=runtime.config_resolver)` | `runtime.resolve_available_skills(ctx.repo_root, load_skills)` |
| `Kernel.list_skills` | 内联构造 `_WorkspaceDirnameSkillResolver` | 调用 `_make_skill_resolver` |
| `Kernel.assemble_prompt_preview` | 内联构造 `_WorkspaceDirnameSkillResolver` | 调用 `_make_skill_resolver` |
| `default_skill_search_roots` | `config_resolver=None` 时回退 Codex roots | `config_resolver=None` 时返回空元组 |
| `tests/unit/test_core_skills_location.py` | 仅导出存在性/模块归属断言 | 确认无需行为断言更新；如需补充行为断言则同步更新 |

**注意**：`ctx.repo_root` vs `ctx.cwd` 在子 agent 场景下的差异不在本 unit 修复范围内；本 unit 保持 `agent` 工具现有取值（`ctx.repo_root`），只改 resolver 来源。若后续发现子 agent workspace 取值不对，另开 bugfix。

## 契约层增量 (delta-spec)

- kernel: `docs/changes/bugfix-431-runtime-skill-resolution/specs/kernel/spec.md`（ADDED Requirement：runtime skill resolution 与 preview/list_skills 同源）
- im: no spec delta
- gateway: no spec delta
- cli: no spec delta

## 风险与回退

### 已知风险

1. **统一 helper 的私有性**：`_make_skill_resolver` 是 `agent.sdk.kernel` 内部 helper，必须确保不进入 `agent.sdk.__all__` 公开表面。
   - 缓解：helper 名称以下划线开头；精确名单守卫 `test_agent_sdk_surface_guard.py` 只校验 `__all__`，不拦截未 export 的模块级私有符号，因此在 M1 退出标准中显式加一条 `[worker]` 断言：`dir(agent.sdk)` 不含 `_make_skill_resolver`。
2. **AgentRuntime 签名变更**：新增构造参数可能影响现有单元测试直接构造 `AgentRuntime` 的用例。
   - 缓解：新增参数有默认值（`None` / `()`），保持向后兼容；旧测试不传新参数时 skill resolution 返回空（因决策 4 清理了默认 roots）。
3. **移除 `config_resolver` property 的引用点**：`agent` 工具、`AgentRuntime` 内部、可能还有测试会引用该 property。
   - 缓解：grep 全仓所有 `config_resolver` 引用，逐一更新；对无其他用途的 `ConfigResolverLike` Protocol 可一并移除。
4. **清理 Codex roots 默认回退的波及面**：直接调用 `resolve_available_skills(config_resolver=None)` 的测试/代码会拿到空 skills；需要改为显式传 resolver 或显式构造 `SkillRegistry(search_roots=...)`。
   - 缓解：grep 所有 `resolve_available_skills` 与 `default_skill_search_roots` 调用点，逐一更新；`tests/unit/test_core_skills_location.py` 等只验导出存在性的测试需同步确认。
5. **`ConfigResolverLike` Protocol 清理**：移除 `config_resolver` property 后，`ConfigResolverLike`（`runtime.py:94`）仅剩定义无引用方，可一并移除。注意 `platform/tools/loader.py` 和 `platform/hooks/loader.py` 有各自独立的 `_ToolRootResolver` / `_HookRootResolver` Protocol，不受影响。
6. **子 agent workspace root 取值**：`agent` 工具校验用 `ctx.repo_root`，创建用 `ctx.cwd`，两者可能与父 session workspace 不一致；本 unit 只改 resolver 来源，不改 workspace root 取值。
   - 缓解：与 `_create_subagent_session` 保持一致是更安全的改动；若后续发现不一致导致问题，另开 bugfix。

### 回退方案

- `git revert` 本 unit 的修改；`AgentRuntime` 回到 `config_resolver=None` 状态，runtime skill resolution 回到 Codex-only 路径。
- 或临时在 `build_kernel` 里显式传旧参数，保持现状。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid` | `IM_JWT_SECRET=<unit随机串> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port $IM_PORT > .im.log 2>&1 & echo $! > .im.pid` | `curl -sf http://127.0.0.1:$IM_PORT/im/v1/health` |
| Gateway | `stop_pidfile .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config $WT_CFG --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 node.register 成功 + IM 节点 online |

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-431-M1 | runtime-skill-resolver | — | A | `src/agent/sdk/kernel.py`（注入参数 + 统一 helper）、`src/agent/core/agent/runtime.py`（构造 + per-session resolver）、`src/agent/core/skills/discovery.py`（清理默认 roots）、`src/agent/platform/tools/builtins/agent.py`（子 agent 校验）、相关测试 | `[reviewer]` 在 IM 给 PA agent 勾选 12 个 skills，真实对话后 LLM proxy 请求中 `<available_skills>` 出现全部 12 个，与 preview 一致；`[reviewer]` 子 agent 工具加载 PA workspace skills 成功；`[worker]` 新增/更新单元测试覆盖 runtime skill resolution 与 preview 同源；`[worker]` `dir(agent.sdk)` 不含 `_make_skill_resolver`；`[worker]` `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿；`[worker]` `tests/contract/test_agent_sdk_boundary_contract.py` 绿（无 product 越界 import） |
