# Feat-332: IM Stop Command

## 背景

Agent 在执行多轮工具调用时，用户可能发现它正在朝错误方向操作（如修改了不该改的文件、执行了危险命令）。当前 personal_assistant 网关没有提供任何让用户主动中断活跃 run 的手段，用户只能干等或强制重启进程。

Claude Code 的参考实现通过 `AbortController` + `yieldMissingToolResultBlocks` 在流式生成和工具执行两个阶段都能响应中断，并为未完成的 `tool_use` 补出 `interrupted` 结果、注入用户中断消息。本功能在 IM/聊天场景下提供等效能力。

## 功能边界

### In Scope

- **IM/聊天工具**（微信/飞书等）中支持发送 `/stop` 命令，立即终止当前 session 的活跃 agent run
- **Gateway 层前置拦截**：`/stop` 在 `InboundPipeline` 入口处识别，不进入正常 pipeline，也不写入 group context buffer
- **强制中断**：能中断处于 LLM 流式生成阶段或工具执行批次之间的活跃 run
- **历史注入**：
  - 未完成的 `tool_use` 收到 `error="interrupted"` 结果（复用 kernel 已有的 `AgentLoop` abort 机制）
  - 通过 `append_message` 向 session 追加一条用户中断消息 `[Request interrupted by user for tool use]`，使下一轮 LLM 能感知到「用户主动打断了上一步」，且该消息本身不触发新的模型 run
- **用户反馈**：Gateway 向发送者返回一条确认消息（如 "已停止当前操作"）
- **队列隔离**：`/stop` 不走 `SessionRunQueue` 排队，直接执行；取消后同 session 队列中后续任务正常继续

### Out of Scope

- CLI REPL 的 `/stop` 命令（CLI 用 Ctrl+C，已有独立信号机制）
- 权限校验（MVP 阶段任何人可在群聊中发送 `/stop`）
- 停止后 agent 的自动恢复/重试行为（由下一轮正常用户输入驱动）
- 跨 session / 批量 stop
- 部分停止（只停某个 tool 而不停整个 turn）

## 用户场景

### 场景 A：危险操作止损（私聊）

> 用户让 agent "清理下项目里没用的文件"，agent 开始调用 `Bash` 工具执行 `rm -rf`。用户看到 tool_start 事件后立刻意识到范围过大，发送 `/stop`。agent 立即终止，已发出的 `tool_use` 收到 interrupted 结果，历史中追加 `[Request interrupted by user for tool use]`。

### 场景 B：群聊紧急刹车

> 群聊中某成员 @agent 请求 "帮我把数据库 users 表清空"。agent 开始执行 SQL 工具。另一个有权限的成员看到后立即发送 `@agent /stop`（或直接 `/stop`，由 gateway 路由到当前活跃 agent），agent 终止并回复 "已停止当前操作"。

### 场景 C：方向错误止损

> Agent 进入了一个过长的多轮工具调用循环（反复读取不相关文件），用户发送 `/stop` 打断，下一条正常 prompt 可以直接切换到新任务，无需等待当前循环自然结束。

## 验收标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | 用户发送 `/stop` 后，活跃 run 在 3 秒内终止 | e2e 测试：注入慢工具，发送 `/stop`，断言 run 状态变为 interrupted/cancelled |
| 2 | 终止后，未完成的 tool_use 收到 `error="interrupted"` | 单元测试：断言 kernel 产出的 tool_result 消息含 `error="interrupted"` |
| 3 | 终止后，session 历史中追加一条用户中断消息 `[Request interrupted by user for tool use]`，且不触发新 run | 契约测试：调用 `get_session` 断言 messages 末尾含中断消息；单元测试断言未调用 `submit` |
| 4 | Gateway 向用户返回 "已停止" 确认 | e2e 测试：断言 outbound 消息含停止确认文本 |
| 5 | 同 session 后续正常消息仍能正常排队执行 | e2e 测试：stop 后发送新消息，断言新 run 成功完成 |
| 6 | `/stop` 本身不进入 group context buffer | 单元测试：发送 `/stop` 后 drain buffer，断言无 `/stop` 内容 |
| 7 | 无活跃 run 时发送 `/stop`，返回友好提示（如 "当前没有正在执行的操作"） | 单元测试 |

## 技术前提与风险

### 已知前提

- Kernel `AgentLoop` 在工具执行批次之间检查 `controller.is_aborted`，已为未执行的 tool calls 生成 `error="interrupted"` 结果
- `RunController` 区分 `cancel_event`（pre-turn）和 `abort_event`（force interrupt）
- `KernelApiClient` 已有 `cancel_run()` 方法，但调用的是 `RunsRegistry.cancel()`（设置 `cancel_event`）

### 待确认风险

- `cancel_run` 设置的是 `cancel_event`，而 `AgentLoop` 运行时检查的是 `abort_event`。如果 run 已在执行中，`cancel_run` 可能无法立即强制中断。需要在 `design.md` 中明确方案：
  - **方案 A**：扩展 kernel HTTP API 添加 `POST /v1/runs/{run_id}/abort`（设置 `abort_event`）
  - **方案 B**：调整 `cancel_run` 行为，对 running 状态的 run 同时触发 `abort()`
  - **方案 C**：Gateway 通过 `send_message_async` + `priority="now"` 发送内部控制消息触发 interrupt（但这会把消息透传给 kernel，与"Gateway 前置拦截"冲突）

## 关联系统

| 系统 | 文件 | 变更点 |
|------|------|--------|
| Gateway Pipeline | `personal_assistant/gateway/inbound_pipeline.py` | `/stop` 前置拦截、活跃 run 追踪 |
| Gateway Queue | `personal_assistant/gateway/run_queue.py` | 可能需支持取消/高优先级插队 |
| Gateway Client | `personal_assistant/client/kernel_api_client.py` | 可能需要新增 abort API 调用 |
| Kernel Runs | `agent/core/runs/registry.py` | 可能需要扩展 cancel/abort 行为 |
| Kernel Loop | `agent/core/agent/loop.py` | 确认 abort 检测覆盖范围 |
