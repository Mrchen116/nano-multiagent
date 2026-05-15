# feat-349-M1: hook-background-fork — Tasks

## 目标

扩展 hook 内核，新增 `background` dispatch mode：
1. `HookEventMode` 增 `BACKGROUND` 枚举值
2. `HookRegistration` 增 `mode` 字段（默认 `observe`）
3. `HookRegistry.on()` 支持 `mode="background"` 注册
4. `HookRunner.dispatch_background()` fire-and-forget（`asyncio.create_task`），不 await、不受 timeout_ms 约束
5. `HookContext` 增 `fork_conversation` callable（仅 background dispatch 时注入），内部封装 `AgentContextFork`
6. `AgentContextFork` 承载 `fork_conversation`，继承父 turn `rendered_system_prompt` / `active_tools`，`tool_allowlist` 做执行层拦截
7. `AgentRuntime._run_locked` 给 `agent_end` 追加 `tool_iterations`（从 loop turn_meta 读取），构建 background hook context
8. `AgentLoop` turn_meta 暴露 `tool_iterations`（loop 内 `api_round_count`）
9. 防递归：fork context 内不注入 `fork_conversation`（直接传 `fork_conversation=None` 给子 context）

## 退出标准

- 能注册 `mode="background"` 的 hook；
- turn 结束后 `HookRunner` fire-and-forget 跑 background hook，不阻塞主 turn、不受 timeout_ms 约束；
- `fork_conversation` 复用父 turn 的 `rendered_system_prompt` + `active_tools`（测试断言字节一致）、按 `tool_allowlist` 做执行层拦截；
- 递归 fork 被抑制（fork context 内 `fork_conversation=None`，覆盖 R1）；
- `core/hooks` + 相关 runtime 单测全绿。

## 测试策略

**场景**：纯后端/核心逻辑。用单元测试覆盖，入口为 `pytest tests/unit/` 内 hook 相关测试。

C1 测试文件：`tests/unit/test_background_hook_fork.py`

覆盖点：
1. 注册 background hook — `registry.on(event, handler, mode="background")` 注册成功
2. `dispatch_background` fire-and-forget — 主 turn 不等待 background hook 完成
3. `fork_conversation` 字节一致 — 断言 fork 传入的 system_prompt = 父 turn rendered_system_prompt
4. `tool_allowlist` 执行层拦截 — 白名单外工具调用被 deny
5. 防递归 — fork context 的 `fork_conversation` 为 None
6. `turn_meta` 暴露 `tool_iterations` — loop 输出 turn_meta 含 tool_iterations 字段

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | HookEventMode 增 BACKGROUND + HookRegistration/Registry 支持 mode | DONE |
| R2 | HookRunner.dispatch_background fire-and-forget | DONE |
| R3 | HookContext 增 fork_conversation + AgentContextFork 承载 | DONE |
| R4 | loop.py turn_meta 暴露 tool_iterations + runtime agent_end 带计数 | DONE |
| R5 | runtime _run_locked 构建 background dispatch + agent_end hook 注入 fork_conversation | DONE |
