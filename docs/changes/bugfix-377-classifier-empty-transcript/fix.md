# bugfix-377: auto_mode 安全门拿到空 transcript（observe 重复盲跑 + strip 漏拷字段）

## Relations

- Closes: #45
- Related: bugfix-375（#44 深度任务 e2e 暴露了这两个潜伏缺陷；本 unit 从 #44 剥离独立修复）

## 原始报告

用户在 bugfix-375 收尾后,翻 LLM proxy 日志发现安全门分类器的 `<transcript>` 为空,要求"钉死"根因:

> 你看看你的验证历史里，automated security classifier是不是没拿到transcript
>
> logs/session/2026-05-21_01-09-38_927_sess_b54061b526c22fe3/2026-05-21_01-11-08_668-req-anthropic_messages.json 比如这个日志中`<transcript></transcript>`里没有东西
>
> 很好，但是我怀疑和#44相关。你自己把握。全权交给你。
>
> 钉死啊

## 现象 / 复现

auto_mode_gate（统一权限安全门）在每个工具执行前调用 LLM 分类器判定 allow/block，分类器靠 `<transcript>`（对话历史 + 当前动作）判断用户意图。LLM proxy 日志显示分类器**大面积拿到空 `<transcript>`**：

- 近 7 天分类器子调用 345 次中 **225 次 transcript 为空（~65%）**；2026-05-20 单日空 306 次（同日非空 159）。
- 2026-05-15（message_history wiring 刚落）当天 87/87 全非空；05-20 深度任务 e2e 量大后空数暴增。
- 同一 session 内主 agent 的分类调用**非空（正常）**，空的是并发的另一类调用——按时间成对出现：每个工具一次「空 S1 → 升级空 S2」+ 一次「非空 S1」。

复现（确定性，进程内隔离）：用真 `HookRegistry` 注册 auto_mode_gate，对同一 `tool_call` 分别走 `dispatch_observe` 与 `dispatch_intercept`，观察分类器模型调用次数与 transcript 是否为空。

## 根因

两个独立的潜伏缺陷，均在 main 上、非 #44 引入，被 #44 深度任务的工具调用量放大暴露。

### 根因 A（主因，对应那 306 个空）— 安全门在 observe dispatch 里被重复盲跑

auto_mode_gate 的 `tool_call` handler 用**默认 OBSERVE 模式**注册（`hooks.on("tool_call", on_tool_call, ...)` 未传 mode）。`AgentLoop` 为通知流式/metrics 观察者，每个工具会**额外** dispatch 一次 observe `"tool_call"`（`_dispatch_tool_call_hook`）。而 `HookRunner.dispatch_observe` 用 `handlers_for(event)` 跑全部 handler、**不按 mode 过滤** → 门在这次 observe pass 里**也被执行**：

- 用的是 **run 级 ctx（无 `message_history`）→ 空 `<transcript>` → 盲分类 → 升级 stage-2**；
- observe 的返回值根本不被采纳（observe 不能 block）→ 纯浪费 1~2 次分类器模型调用 + 制造空 transcript 日志。

真正生效的门在 `ToolRegistry.execute` 的 `dispatch_intercept` 里、用带 `message_history` 的 `tool_hook_ctx` 跑，非空、被采纳。

**为什么这种错能进来**：hook 体系约定"两种 dispatch 都跑全部 handler，只在 intercept 采纳返回值"，多数 observe-注册的 handler 靠 intercept dispatch 采纳返回值（chat_history input 改写、communication_context before_agent_start 注入）。门也照此惯例注册成 observe，但它的判定**带模型调用**，在 observe pass 里跑既无意义又昂贵——而 mode 字段一直存在却从未用于 dispatch 过滤（只排除 BACKGROUND）。隔离测从未走真实 dispatch（都直接 mock ctx），所以漏网。根因起点：feat-333（门注册 mode）。

### 根因 B（独立）— `_strip_fork_conversation` 漏拷字段

`HookRunner._strip_fork_conversation` 手写重建 `HookContext` 时只拷了 7 个字段，**漏拷 `message_history` 与 `permission_requester`**（这两个字段 2026-05-15 才加入 HookContext，加时未同步更新此处重建）。任何携带 `fork_conversation` 的 observe/intercept dispatch 经此剥离后：

- 分类器拿到空 `<transcript>`（盲判）；
- `request_permission` 因 `permission_requester`（PermissionBroker）丢失 → **fail-closed 自动 deny**：fork/background 路径遇到需用户批准的操作会闷头拒绝，用户根本不被问到。

**为什么这种错能进来**：手写逐字段重建是脆弱模式——新增 HookContext 字段时极易漏更新，且无测试锁定"strip 只置空 fork_conversation、其余字段守恒"。根因起点：2026-05-15。

## 修复

根因 A（observe 重复盲跑）：
- `src/agent/platform/hooks/builtins/auto_mode_gate.py`：门的 `tool_call` handler 注册改为 `mode="intercept"`（其 block/allow 仅在 intercept dispatch 有意义）。
- `src/agent/core/hooks/runner.py`：`dispatch_observe` 跳过 `mode==INTERCEPT` 的 handler。`dispatch_intercept` 保持运行全部 handler，向后兼容 chat_history（input 改写）/ communication_context（before_agent_start 注入）等 observe 注册但靠 intercept 采纳返回值的处理器。

根因 B（strip 漏拷字段）：
- `src/agent/core/hooks/runner.py`：`_strip_fork_conversation` 由手写逐字段重建改为 `dataclasses.replace(ctx, fork_conversation=None)`——只置空 `fork_conversation`，保全其余全部字段，未来新增字段不会再被静默丢弃。

测试：
- `tests/unit/test_hooks_runner.py::test_dispatch_observe_skips_intercept_mode_handlers`（锁定根因 A：intercept handler 不在 observe dispatch 执行）。
- `tests/unit/test_hooks_runner.py::test_strip_fork_conversation_preserves_message_history_and_permission_requester`（锁定根因 B：strip 只置空 fork_conversation、其余字段守恒）。

## 验证

- **确定性复现（隔离）**：真 `HookRegistry` 注册 auto_mode_gate，对同一 `tool_call`——
  - 修前：`dispatch_observe("tool_call")` 触发 **1 次**空 transcript 分类器模型调用（盲判、升级 stage-2）。
  - 修后：`dispatch_observe` **0 次**；`dispatch_intercept` 仍 **1 次**且 transcript 非空（带 `message_history`）。
- **根因 B 红测**：修前 strip 后 `message_history` 变 `()`（红）；修后守恒（绿）。
- **回归**：`test_hooks_runner` / `test_auto_mode_gate` / `test_auto_mode_gate_dispatch` / `test_hook_event_coverage` / `test_hook_lifecycle_event_coverage` 全绿（95 passed）。真观察者（realtime_stream 等 observe 注册）仍走 observe，不受影响。
- **用户侧净效果**：每个非 safe 工具只分类一次（带完整 transcript、按用户意图判定），砍掉一半以上分类器模型调用；fork/background 路径不再丢 `message_history` 与 `permission_requester`（ask 流程不再 fail-closed 自动 deny）。
