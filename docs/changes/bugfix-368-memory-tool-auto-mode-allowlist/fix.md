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

<!-- M1 完成后补：改了哪几行 / commits / 是否补了"新增 tool 必须登记 gate 白名单"的约束（测试或 lint） -->

## 验证

<!-- M1 完成后补：复现脚本 / proxy logs 对照 / PA self-improvement 在 auto mode 下能正常写入 memory -->
