# bugfix-368: PA/IM self-improvement 中 memory 工具被 auto_mode_gate 全部拦死

## Relations

- Closes: #31
- Related: [[feat-349-self-evolving-skills-memory]]（self-improvement / memory 体系的来源 unit）

## 原始报告

来源：https://github.com/Mrchen116/nano-multiagent/issues/31（作者：Mrchen116，2026-05-19 当前状态 OPEN，无 label / 无 assignee）

原话粘贴如下：

> ## Problem
>
> In personal assistant (and IM) sessions, the `memory` tool is repeatedly blocked by the `auto_mode_gate` hook. When the self-improvement hook triggers a memory curation cycle, the agent calls `memory` to update its notes, but each call is denied with `"tool blocked by hook"`. The agent then retries, creating a denial loop.
>
> From LLM proxy logs (session `2026-05-18_20-03-53_640_sess_5c8151448cd2e07b`):
> - The `memory` tool was invoked **14 times** in a single turn
> - Every invocation returned: `tool blocked by hook`
>
> ## Root Cause
>
> In `src/agent/platform/hooks/builtins/auto_mode_gate.py`, the `memory` tool falls through the entire permission gate:
>
> 1. **Step 1** (`tool.check_permissions`): `MemoryTool` does **not** implement `check_permissions`, so `tool_result = None`
> 2. **Step 4** (`SAFE_TOOL_ALLOWLIST`): `memory` is **not** in the allowlist (`read`, `task_*`, `agent`, `send_message` only)
> 3. **Step 8** (yolo classifier): The classifier judges `memory` as `deny` (likely because it is a persistence/write operation)
> 4. **Result**: `{"block": True}` is returned to the agent
>
> ## Impact
>
> - Self-improvement (memory curation) is effectively **broken** for PA/IM products
> - Wasted LLM tokens: 14 classifier calls + 14 blocked tool calls in one turn
> - Poor user experience: agent appears to be in a retry loop with no progress
>
> ## Suggested Fix
>
> Add `memory` to `SAFE_TOOL_ALLOWLIST` in `auto_mode_gate.py`:
>
> ```python
> SAFE_TOOL_ALLOWLIST: frozenset[str] = frozenset({
>     "read",
>     "task_create",
>     "task_get",
>     "task_update",
>     "task_list",
>     "task_stop",
>     "task_output",
>     "agent",
>     "send_message",
>     "memory",  # <-- add this
> })
> ```
>
> Rationale: `memory` is a metadata-only self-management tool. It writes to `.nano/memory/` (agent workspace), never modifies user code or system files, and has no destructive capability. It is semantically equivalent to `read`/`task_*` — safe to auto-approve.
>
> An alternative is to implement `MemoryTool.check_permissions` returning `PermissionDecision(behavior="allow")`, but the allowlist approach is more consistent with how other safe tools are handled.
>
> ## Files
>
> - `src/agent/platform/hooks/builtins/auto_mode_gate.py` — `SAFE_TOOL_ALLOWLIST` (line ~172)
> - `src/agent/platform/tools/builtins/memory.py` — `MemoryTool` (no `check_permissions`)

## 现象 / 复现

**触发场景**：personal assistant / IM 会话里，self-improvement hook 触发 memory curation 周期。Agent 想调用 `memory` 工具更新自己的 notes / 索引。

**用户可观察现象**：

- Agent 在一个 turn 内重复调用 `memory` 工具 14 次，每次都收到 `tool blocked by hook`，陷入"拒绝-重试"死循环，本轮 self-improvement 没有任何 memory 被实际写入。
- 用户感知层面：agent 看上去卡住，没有进展；同时 LLM token 被白白烧掉（14 次 classifier 调用 + 14 次被拒的 tool 调用 / turn）。
- 不止单条 session 中招——只要 PA/IM 走 auto mode 跑 self-improvement，每次都复现，self-improvement 在 PA/IM 产品上事实上 **彻底不可用**。

**证据 session**：`2026-05-18_20-03-53_640_sess_5c8151448cd2e07b`（LLM proxy logs，14 次 `memory` 调用全部 blocked）。

## 根因

`memory` 工具在 `auto_mode_gate` 的多步审批流里 **每一步都 miss**，最终落到 classifier 被判 deny：

1. **Step 1（`tool.check_permissions`）**：`MemoryTool`（`src/agent/platform/tools/builtins/memory.py:25`）没有实现 `check_permissions`，hook 取到 `tool_result = None`，无法在工具自身这一层 allow。
2. **Step 4（`SAFE_TOOL_ALLOWLIST` 安全工具白名单）**：`auto_mode_gate.py:172` 的白名单只列了 `read` / `task_*` / `agent` / `send_message`，**未包含 `memory`**，没有走 fast-path 跳过 classifier。
3. **Step 8（yolo classifier）**：classifier 看到 `memory` 是个 write/persistence 类工具、又不在 allowlist，按"err on the side of blocking"判 deny；hook 返回 `{"block": True}`。
4. Agent 收到 `tool blocked by hook` 后重试，再次走完整套审批流再次被拒——loop。

**为什么这种错能进来**（不止"哪行错了"）：

- `memory` 工具是后引入的（来自 [[feat-349-self-evolving-skills-memory]] 自进化 skills + memory 体系），加 tool 时只接了 registry / runtime，没有同步登记到 `auto_mode_gate.SAFE_TOOL_ALLOWLIST`，也没有给 `MemoryTool` 实现 `check_permissions`。
- 这是一个 **跨模块约束**：新增 tool → 必须在 gate 里给出态度（自己 check_permissions 表态 / 白名单登记 / 或显式落到 classifier）。这条约束目前没有在 docs / 测试 / lint 里成文，全靠人记得，于是漏了。
- PA/IM 默认走 auto mode（无人值守，没有人坐在前面点 ask 弹窗），这条漏单只要不补，self-improvement 在 PA/IM 上就一直坏；而 coding_cli 平时是 attended（用户能看到 ask 并放行），同一个漏单在 coding_cli 上不会以"14 次 deny loop"形式炸出来，所以一直没暴露。

## 修复

选型：**方案 A（加入 `SAFE_TOOL_ALLOWLIST`）**。理由对照 issue 给的 rationale + 本仓既定模式——已在 allowlist 的 `read` / `task_*` / `agent` / `send_message` 一致都是"无条件 safe、不实现 `check_permissions`"；CC 上游 `SAFE_YOLO_ALLOWLISTED_TOOLS` 也是列名表。让 memory 单独写 `check_permissions` 只能返回 `allow`，无逻辑、反而破坏一致性。

实施：

1. `src/agent/platform/hooks/builtins/auto_mode_gate.py:188` 的 `SAFE_TOOL_ALLOWLIST` 追加 `"memory"`，附 inline 注释引用 bugfix-368 + 解释为什么 safe。
2. `tests/unit/test_auto_mode_gate.py::TestSafeToolAllowlist::test_memory_safe` 新增——直接回归 issue #31：`is_safe_tool("memory", AutoModeConfig()) is True`。
3. `tests/contract/test_tool_gate_coverage.py` 新增——强约束回归：扫 `agent.platform.tools.builtins` 包内每个含 `name` 字段的 Tool 类，要求都显式落到 `EXPECTED_GATE_POSITION` 表(allowlist / check / classifier 三选一)且与实际 SAFE_TOOL_ALLOWLIST / `check_permissions` 现状一致。新增 tool 时**两边都要改**才能通过 CI——堵掉"新增 tool 漏接 gate"这种漏单(issue #31 的根因模式)。
4. 顺手把 `skill_manage` 这条同类隐患**显式登记**为 `classifier`(写用户 skill 文件，per-call 判更稳)，让契约表把现状钉死，避免未来误改默认归属。

Commits（unit/bugfix-368 分支）：

- `c0ba189a` docs(bugfix-368): spec lite — memory 工具被 auto_mode_gate 全拦死,PA self-improvement 死循环
- `fix(bugfix-368/M1): memory → SAFE_TOOL_ALLOWLIST + builtin gate coverage 契约测试`（本提交）

## 验证

修前现象（issue 引用 session `2026-05-18_20-03-53_640_sess_5c8151448cd2e07b`）：14 次 `memory` 调用全部返回 `tool blocked by hook`。

修后验证：

- **单测层**：`pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_memory_tool.py tests/contract/test_tool_gate_coverage.py` → 99 passed in 0.20s。覆盖：
  - `test_memory_safe` 断言 `is_safe_tool("memory")` 走 fast-path（直接对应 issue #31 根因 step 4）。
  - `TestSafeToolAllowlist` 既有 12 条 + `test_safe_tool_allowlist_frozenset` 全绿，证明白名单结构未破坏。
  - `test_every_builtin_tool_has_an_expected_gate_position` / `test_each_builtin_tool_matches_its_declared_gate_position` 全绿，证明 9 个 builtin tool 全部有显式 gate 归属(read/agent/task_stop/memory=allowlist；bash/edit/write/web_fetch=check；skill_manage=classifier)。
  - 试验性删掉 `"memory"` 后再跑：`test_memory_safe` 红、`test_each_builtin_tool_matches_its_declared_gate_position` 红——回归测试真的会炸。
- **回归约束层**：试验性在 `builtins/__init__.py` 多 import 一个虚构 `FooTool`(name="foo") → `test_every_builtin_tool_has_an_expected_gate_position` 立刻红，提示 "New builtin tool(s) discovered without a gate position declaration: ['foo']"。证明"新增 tool 漏接 gate"这类漏单会在 CI 阶段直接被拦。
- **产品层手验**(本 unit 范围外，PR review 后用户可在 PA 跑一次 self-improvement 即可对照 proxy logs；hook 决策路径已被单测覆盖)：PA 启动 auto mode → 触发 memory curation 周期 → 期望 `memory` 工具调用不再出现 `tool blocked by hook`，`.nano/memory/` 实际更新。
