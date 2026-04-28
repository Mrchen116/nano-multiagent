# Spec: CC 风格后台任务交互体验

> **依赖**: feat-338 Kernel Message SSE。feat-338 已落地：
> - `POST /v1/sessions/{id}/messages` JSON submit + `GET /v1/sessions/{id}/stream` 持久 SSE。
> - `RunOrigin` 枚举（`USER` / `BACKGROUND_TASK` / `HEARTBEAT`）；`runs.submit(..., origin, source_task_id)` 入参；`run_status` 事件携带 `origin` / `source_task_id`。
> - REPL 常驻 reader、Gateway per-session `/stream` 订阅、非 user origin 渲染/路由路径已就位且有 fixture 校验。
>
> 本 feature 不新增任何 HTTP 端点、不修改任何客户端代码。后台任务唤醒父会话的产品交付完全复用 feat-338 的 `/stream` 通道。

## 1. 背景

当前 `task(run_in_background=true)` 只实现了“后台执行”，还没有实现完整的“后台任务”体验；本功能把用户可见 subagent 工具对齐 Claude Code，命名为 `Agent`。当前 `bash` 工具没有 `run_in_background` 参数。

已确认的问题：

- 后台 subagent 完成后，结果只写入 `TaskTool._task_results` 内存字典，没有事件通知、没有持久化、没有用户可见完成消息。
- `task` 回执中写着 `System notifies on completion`，但系统实际不会通知。
- 回执中提示用 `session_id` 检查进度，但当前 `task(session_id=...)` 实际语义是“继续该 subagent 开新一轮”，不是“查询后台任务结果”。新 `Agent` 工具不暴露 `session_id`。
- blocking continuation 超时后不会取消底层 future，因此可能出现“主 agent 看到 timeout，但后台 subagent 后来已经完成”的错位体验。
- `bash` 工具当前只有 `command` 和 `timeout` 参数，同步等待命令完成；长命令超时后返回 `ToolError`，没有后台 task state、`output_file`、完成通知或 `task_stop` 集成。

本功能目标是参考 Claude Code 的后台任务机制，把后台 subagent 和后台 bash 的用户交互体验完整迁移过来。

## 2. 参考设计：Claude Code

参考代码位置：

- `/Users/czj/Repos/opensource-hub/claude-code/src/tools/AgentTool/AgentTool.tsx`
- `/Users/czj/Repos/opensource-hub/claude-code/src/tasks/LocalAgentTask/LocalAgentTask.tsx`
- `/Users/czj/Repos/opensource-hub/claude-code/src/tools/BashTool/BashTool.tsx`
- `/Users/czj/Repos/opensource-hub/claude-code/src/tasks/LocalShellTask/LocalShellTask.tsx`
- `/Users/czj/Repos/opensource-hub/claude-code/src/tools/TaskStopTool/TaskStopTool.ts`
- `/Users/czj/Repos/opensource-hub/claude-code/src/utils/task/diskOutput.ts`
- `/Users/czj/Repos/opensource-hub/claude-code/src/tools/AgentTool/forkSubagent.ts`

Claude Code 的关键体验：

1. 后台 subagent 和后台 bash 共用同一套 task state 基础设施。
2. 启动后台 agent 后立即返回 `agent_id`、描述、输出文件路径、后续操作指引；启动后台 bash 后立即返回 `task_id`、描述、输出文件路径、后续操作指引。
3. 后台任务是独立状态实体，有 `running/completed/failed/killed` 等生命周期状态。
4. 后台输出写到稳定文件，主 agent 可在完成前读取或 tail。
5. 完成后系统主动通知主会话，而不是要求主 agent 盲查。
6. 有 `TaskStop` 停止工具，能停止后台 subagent 和后台 bash。
7. 同步 agent 长时间运行时，可以转入后台，主对话保持响应。
8. bash 支持 `run_in_background`，长时间阻塞命令也可以自动转后台。
9. 回执文本明确要求主 agent 不要重复后台任务的工作。

Claude Code 中已确认的具体交互语义：

- worker 结果以 `user-role message` 的形式进入主会话，但内容必须用 `<task-notification>` XML 包裹；它看起来像用户消息，但语义上是系统/worker 事件，不是用户指令。
- coordinator prompt 明确要求：worker result 和 system notification 是内部信号，不是对话对象；主 agent 不应感谢或回应通知本身，而应把新信息综合后告诉用户或继续执行。
- 完成通知经由统一 command queue 投递，默认优先级为 `later`；普通用户输入默认优先级为 `next`，因此用户新输入优先于后台完成通知。
- 队列处理只在主 query 空闲、没有阻塞 UI 时触发；后台通知不会中断正在运行的主 agent turn。
- 多条同 mode 的非 slash command 会被批量取出；因此多个 pending `<task-notification>` 可以在一次主 agent turn 中一起进入上下文。
- 对 agent，Claude Code 的用户可见 ID 是 `agentId`；该 ID 用于完成通知、`TaskStop`，也可用于继续该 worker。本项目对齐为 `agent_id`。
- 对后台 subagent，`outputFile` 通过 `initTaskOutputAsSymlink(taskId, getAgentTranscriptPath(agentId))` 指向该 agent 的 sidechain transcript；即它不是额外整理出来的摘要文件，而是 subagent 会话 transcript 文件。
- subagent transcript 是 JSONL，每条记录是会话消息或相关 transcript entry；它用于恢复 subagent、读取完整过程，以及作为 output file 暴露给主 agent。
- 对后台 bash，`outputFile` 由 `TaskOutput` / `getTaskOutputPath(taskId)` 管理，内容是命令 stdout/stderr，而不是 JSONL transcript。
- `LocalAgentTask` 与 `LocalShellTask` 都注册到同一个 task registry，并由同一个 `TaskStopTool` 停止。
- foreground agent 通过 `backgroundSignal` 与 `Promise.race(nextMessage, backgroundSignal)` 切到后台；切后台后立刻返回 `async_launched`，后台继续消费 agent stream，完成时再发 `<task-notification>`。
- foreground agent 在 Claude Code 中运行 2 秒后显示后台化提示；自动后台化逻辑是 120 秒后切后台，但在 Claude Code 中受 `CLAUDE_AUTO_BACKGROUND_TASKS` 或 feature gate 控制。本项目不实现 2 秒提示，120 秒自动后台化默认开启。
- bash 显式 `run_in_background=true` 时直接后台运行；在 Claude Code assistant mode 中，主线程阻塞 bash 会在 15 秒后自动后台化。本项目对齐该 15 秒默认后台化语义。

## 3. 产品目标

把用户在 Claude Code 中使用后台任务的体验迁移到本项目：

- 用户要求“开个 subagent 后台挂着”时，主 agent 应启动后台任务并立即继续当前工作。
- 用户要求“后台跑这个 bash 命令”时，主 agent 应调用 `bash(run_in_background=true)` 并立即继续当前工作。
- 主 agent 不应因为后台任务还没完成而阻塞当前 turn。
- 后台任务完成后，主 agent 或 REPL 应收到完成通知，用户能看到结果或结果摘要。
- 用户和主 agent 可以通过 `output_file` 读取后台任务输出。
- 用户可以停止后台任务。
- 对齐 Claude Code，subagent 的用户可见 ID 只有 `agent_id`。同一个 `agent_id` 用于完成通知、停止后台任务、读取 output file 对应关系，以及继续该 worker。
- 如果 `Agent(agent_id=..., prompt=...)` 发送给正在运行的 agent，消息必须排队进入该 agent 的 pending message 队列，并在 agent 下一次工具轮次边界消费；不得中断正在执行的工具或当前 LLM stream。
- bash 后台任务使用同一套 registry、状态机、`output_file`、通知和停止机制；bash 用户可见 ID 是 `task_id`，不能用 `Agent(agent_id=...)` 继续。

## 4. 用户可见交互

### 4.1 启动后台 agent

输入示例：

```json
{
  "description": "研究核心 loop",
  "prompt": "Study the core loop implementation and report key files.",
  "run_in_background": true,
  "subagent_type": "explore"
}
```

期望返回给主 agent 的 tool result：

```text
Background agent launched.

agent_id: a1b2c3d4e5f6a7b8
description: 研究核心 loop
status: running
output_file: /path/to/task_....output

The agent is working in the background. You will be notified automatically when it completes.
Do not duplicate this agent's work. Work on non-overlapping tasks, or briefly tell the user what you launched and continue.
Use Read on output_file to inspect progress or final output.
Use Agent with agent_id="a1b2c3d4e5f6a7b8" only when you want to continue the agent conversation.
```

要求：

- 必须给出 `agent_id`，格式对齐 Claude Code 的 agentId：`a` + 16 位 hex，例如 `a1b2c3d4e5f6a7b8`。
- 不得在 agent 回执中同时暴露 `task_id` 和 `agent_id`。对主 agent 来说只有一个 agent identity。
- 文案必须明确：读后台结果用 `output_file`；继续子会话用 `Agent(agent_id=...)`；停止时 `task_stop(task_id=...)` 传入同一个 `agent_id` 值。
- 必须给出 `output_file`。
- 主 agent 看到该回执后，应知道不要重复后台 agent 的工作。

### 4.1.1 给运行中的 agent 追加消息

输入示例：

```json
{
  "agent_id": "a1b2c3d4e5f6a7b8",
  "prompt": "Stop looking at gateway code. Focus only on AgentTool and SendMessage semantics."
}
```

如果该 agent 仍在 `running`：

```text
Message queued for agent.

agent_id: a1b2c3d4e5f6a7b8
status: running
output_file: /path/to/task_....output

The message will be delivered at the agent's next tool-round boundary.
Do not poll. You will be notified when the agent completes.
```

要求：

- 这不是新建 agent，也不是立即启动第二个并发 run。
- 消息按 FIFO 进入该 agent 的 pending message 队列。
- agent 当前正在执行 tool、shell command、file edit 或 LLM stream 时，不得中断。
- agent 在下一次安全点消费 pending message，把它作为 user-role input 追加到该 agent runtime session 和 transcript。
- 如果 agent 已经 terminal，`Agent(agent_id=..., prompt=...)` 恢复该 agent，并继续使用同一个 transcript/output file。

### 4.2 后台完成通知

后台任务完成后，系统应向父会话投递一条通知事件。主 agent 下一次取上下文或 REPL 事件流展示时，应能看到类似：

```text
<task-notification>
agent_id: a1b2c3d4e5f6a7b8
description: 研究核心 loop
status: completed
output_file: /path/to/task_....output

Result:
...

<usage>
duration_ms: 42103
tool_uses: 8
total_tokens: 12345
</usage>
</task-notification>
```

要求：

- `completed` 通知必须包含最终结果摘要或完整最终文本。
- `failed` 通知必须包含错误信息。
- `killed` 通知应尽量包含 partial result。
- 通知必须绑定父会话，不能只留在子会话历史里。
- 后台 bash 完成通知也必须使用同一 `<task-notification>` 包装，包含 `task_id`、`status`、`summary`、`output_file`、退出码或错误信息。bash 通知不包含 `agent_id`，也不支持 continuation。

### 4.3 启动后台 bash

`bash` 工具必须新增 `run_in_background` 参数：

```json
{
  "command": "pytest tests/e2e",
  "description": "Run e2e tests",
  "run_in_background": true
}
```

期望返回给主 agent 的 tool result：

```text
Background command launched.

task_id: b1b2c3d4e5f6a7b8
description: Run e2e tests
status: running
output_file: /path/to/b1b2c3d4e5f6a7b8.output

The command is running in the background. You will be notified automatically when it completes.
Use Read on output_file to inspect progress or final output.
Use task_stop with task_id="b1b2c3d4e5f6a7b8" to stop it.
```

要求：

- `run_in_background=true` 必须立即返回后台回执，不等待命令完成。
- 后台 bash 的 `task_id` 格式使用 `b` + 16 位 hex，例如 `b1b2c3d4e5f6a7b8`。
- 后台 bash 必须写入稳定 `output_file`，内容为 stdout/stderr。
- 后台 bash 完成、失败或停止后必须向父会话发送 `<task-notification>`。
- 主线程 foreground bash 运行超过 15 秒后，默认自动转后台并返回后台回执。
- bash 的 `timeout` 仍表示命令自身超时策略；因 15 秒前台预算转后台不是命令失败。

### 4.4 读取后台输出

本功能不引入 `TaskOutputTool` 或 `background_output`。以终为始，后台输出的唯一读取通道是 `output_file`，并对标 Claude Code 的 transcript 设计：

- 后台任务启动回执必须返回 `output_file`。
- `<task-notification>` 必须返回同一个 `output_file`。
- 对 subagent，`output_file` 应指向该 subagent 的 transcript 文件；如果当前平台无法安全创建 symlink，可以创建一个稳定路径并持续写入同等 transcript 内容。
- transcript 应使用 JSONL，每行一条可恢复/可分析的消息或事件记录。
- 对 bash，`output_file` 应是 stdout/stderr 输出文件；stderr 可以带 `[stderr]` 前缀或等价标记。
- 主 agent 如需查看运行中进度或最终结果，应直接调用现有 `read` 工具读取该文件。
- 输出文件应随后台任务持续追加；subagent 完成后必须包含完整 transcript 和最终回复所在记录，bash 完成后必须包含 stdout/stderr。
- 任务失败或停止后，输出文件应保留已产生的 transcript、partial output 和错误信息。

### 4.5 停止后台任务

新增用户可见工具：`task_stop`。

输入：

```json
{
  "task_id": "a1b2c3d4e5f6a7b8"
}
```

期望：

- running 任务被取消，状态变为 `killed`。
- 后台 subagent 应尽力停止 LLM run 和正在执行的工具。
- 后台 bash 应终止对应进程树。
- 已产生的输出保留在 `output_file`。
- 父会话收到 killed 通知。

### 4.6 前台任务转后台

参考 Claude Code 的 foreground → background 体验，本项目应支持：

- foreground subagent 运行超过 120 秒后，默认自动转后台并返回 `async_launched` 回执。
- foreground bash 在主线程运行超过 15 秒后，默认自动转后台并返回后台回执。
- 不实现 Claude Code 的 2 秒 background hint。它是给人看的 UI 提示，不是本项目需要的运行语义。
- 用户显式要求后台时直接后台运行。
- 转后台不是失败，不应返回 `Task timed out`。

这需要对齐 Claude Code 的语义：前台 subagent 或 bash 启动时也注册为 task state，只是尚未 backgrounded；达到阈值或触发后台化后，父会话立即收到后台回执，原任务继续在后台执行，完成后通过 `<task-notification>` 自动唤醒父会话。

## 5. 状态机

后台任务状态包括：

| 状态 | 含义 |
|---|---|
| `queued` | 已创建，尚未开始执行 |
| `running` | 正在执行 |
| `completed` | 成功完成 |
| `failed` | 执行失败 |
| `killed` | 被用户或父任务取消 |

任务状态、停止逻辑和通知必须使用同一套状态枚举。

## 6. 数据模型

后台任务记录包含：

```text
task_id
task_type
parent_session_id
agent_id
agent_session_id
description
prompt
agent_type
command
status
created_at
started_at
ended_at
output_file
transcript_file
result_text
error
exit_code
usage
tool_use_count
duration_ms
notified
pending_messages
```

后台任务 running state 和 stop handle 可以是进程内 registry；subagent transcript 和 bash output 必须写入稳定文件，避免进程内 `_task_results` 丢失导致用户无法查看。进程重启后不要求恢复本地 running task。

## 7. 事件流要求

后台任务生命周期应进入现有 session event/SSE 体系：

- `background_task_started`
- `background_task_progress`
- `background_task_completed`
- `background_task_failed`
- `background_task_killed`

事件必须带：

```text
task_id
task_type
parent_session_id
agent_id
agent_session_id
status
description
output_file
```

如果存在父会话活跃 run，通知不应破坏当前 run；如果父会话空闲，通知应可在下一次 prompt 构建时进入上下文。

### 7.1 自动唤醒父会话

本功能必须实现 Claude Code 风格的自动恢复体验。机制如下：

后台任务完成时，系统调用：

```python
runs.submit(
    session_id=parent_session_id,
    parts=[{"type": "text", "text": <task-notification XML>}],
    origin=RunOrigin.BACKGROUND_TASK,
    source_task_id=task_id,
)
```

由此触发的 run 走和用户消息完全一样的内核路径，事件经 feat-338 `/stream` 通道下发到所有订阅该 session 的客户端（REPL、Gateway）。

要求：

- 父会话当前空闲：`runs.submit` 直接启动新 run。
- 父会话当前正在运行：复用现有 pending message 队列机制（与 `priority=next` 注入语义对齐），通知作为 user-role part 注入活跃 run 的 pending 队列；活跃 run 在下一个工具轮次边界消费。
- 用户输入和后台通知同时排队：pending message 队列按 FIFO 顺序消费，不区分来源优先级。
- 多条后台通知在主 agent 空闲前到达：允许批量注入到同一轮 turn 的 pending（合并为多段 user-role text 或多次 enqueue）。
- 自动唤醒后主 agent 可以正常调用工具，不限于"只总结"。
- 是否立即发用户可见文本由主 agent 决定。
- `<task-notification>` 不应被当成普通用户请求。主 agent prompt 必须明确说明：这是 worker/system signal，不能感谢它，也不能把它当成用户新需求；应综合结果并继续服务真实用户目标。

产品侧（REPL / IM channel / Web IM）能否看到本次唤醒的输出，**完全由 feat-338 保证**：

- REPL 的常驻 `/stream` reader 推送事件到渲染层；`origin=background_task` 时打印 background 标头。
- Gateway 的 per-session `/stream` 订阅识别非 user origin 的 run，按 session_key 串行队列调度 outbound 回 IM channel。
- 离线再上线的客户端通过 `Last-Event-ID` 续传或读取消息历史 API 看到唤醒结果。

自动唤醒父会话是本 feature 的必需能力，但产品交付路径是 feat-338 的 `/stream`。本 feature 不引入新的事件通道、不修改 REPL / Gateway 代码。

## 8. 与现有 task 工具的语义调整

### 调整为 Agent

- 用户可见工具名改为 `Agent`，对齐 Claude Code `AgentTool`。
- `Agent(..., run_in_background=false)`：同步等待子 agent 结果。
- `Agent(..., run_in_background=true)`：启动后台 agent。
- `Agent(..., agent_id=...)`：继续已有 agent 会话。这里的 `agent_id` 是唯一用户可见 agent identity。
- 项目处于开发态，不保留向后兼容；`task` 工具名彻底移除，schema/prompt/transcript replay/contract test 全部改为 `Agent`，不保留 alias。
- `bash(..., run_in_background=false)`：同步等待命令结果。
- `bash(..., run_in_background=true)`：启动后台 bash。

### 调整

- `session_id` 不再是 Agent 工具 schema 的一部分，也不再被描述为“check progress”。
- 后台输出读取必须使用回执或通知中的 `output_file`。
- `Agent` 后台启动回执必须返回 `agent_id` 和 `output_file`，不得额外返回 agent 的 `task_id`。
- `bash` 后台启动回执必须返回 `task_id` 和 `output_file`。
- blocking 超时不应默认等价为任务失败；可转后台时应返回后台回执。

### 废弃

当前回执中的这类表述必须移除或改写：

```text
System notifies on completion. Use `task` with session_id='...' to check.
```

替换为：

```text
System notifies on completion. Use Read on output_file to inspect progress or final output.
Use `Agent` with agent_id="<agent_id>" only to continue the agent conversation.
```

## 9. 必须实现

- 后台启动必须不阻塞主 agent。
- 后台完成必须通知父会话。
- 用户和主 agent 必须能通过 `output_file` 读取后台输出。
- 用户必须能停止后台任务。
- foreground subagent 必须默认在 120 秒后自动转后台。
- foreground bash 必须默认在 15 秒后自动转后台。
- 后台任务 live registry 必须服务同进程内的状态、停止和通知；不要求用 SQLite 或持久 job queue 恢复本地 running task。
- `output_file` 必须稳定存在，并持续追加 subagent JSONL transcript。
- `output_file` 必须稳定存在，并持续追加 bash stdout/stderr。
- subagent 对主 agent 只暴露 `agent_id`。查询输出、停止、继续对话的行为由 `output_file`、`task_stop(task_id=<agent_id>)`、`Agent(agent_id=...)` 这些入口区分。
- bash 后台任务必须与 subagent 后台任务共用同一套 registry、状态机、通知队列、`output_file` 管理和 `task_stop`。

## 10. 验收标准

### 10.1 真实 CLI 场景

用户输入：

```text
开个 subagent 在后台研究核心 loop，然后你读 README
```

期望行为：

1. 主 agent 调用 `Agent(run_in_background=true)`。
2. 终端显示后台 agent 启动回执，包含 `agent_id` 以及 `output_file`，不显示独立 `task_id`。
3. 主 agent 继续读 README，不等待后台 subagent 完成。
4. 主 agent 完成 README 相关工作后，即使用户没有新指令，后台 subagent 完成也会把 `<task-notification>` 投递回父会话。
5. 父会话空闲时自动启动新的 main agent turn，主 agent 基于 subagent 结果继续工作。
6. 主 agent 不需要自己重复研究核心 loop。
7. 用户或主 agent 可读取 `output_file` 获取结果。

### 10.2 输出文件场景

当后台任务还在运行：

- `output_file` 已经存在。
- 读取 `output_file` 可看到已产生的输出或明确的“尚无输出”内容。

当后台任务完成：

- `<task-notification>` 包含 `output_file`。
- 读取 `output_file` 可看到最终输出。

### 10.3 停止场景

当后台任务正在运行：

- `task_stop(task_id=...)` 返回 stopped/killed 结果。
- `output_file` 保留 partial output 或停止说明。
- 父会话收到 killed 通知。

### 10.4 后台 bash 场景

用户要求后台运行长命令时：

1. 主 agent 调用 `bash(run_in_background=true)`。
2. tool result 立即返回 `task_id` 和 `output_file`。
3. 主 agent 继续当前工作，不等待命令完成。
4. bash 输出持续写入 `output_file`。
5. 命令完成后，父会话收到 `<task-notification>`。
6. 父会话空闲时自动启动新的 main agent turn，主 agent 可读取 `output_file` 并继续工作。

当 foreground bash 在主线程运行超过 15 秒：

1. 该 bash 任务自动转后台。
2. tool result 返回后台回执，而不是 timeout failure。
3. 命令继续运行并写入同一个 `output_file`。
4. 命令完成后发送 `<task-notification>`。

### 10.5 跨 kernel 重启的 subagent 恢复

给定主 agent 之前用 `Agent(run_in_background=true)` 启动过 subagent S（agent_id=a...），后台任务完成后主 agent 收到通知；之后 kernel 重启或主 agent 长时间 idle 后被唤醒，主 agent 进程内的 background task registry 已丢失：

1. 主 agent 调用 `Agent(agent_id="a...", prompt="继续刚才的话题，再分析下 X")`。
2. kernel 在内存映射中找不到该 `agent_id`。
3. kernel 通过 `JsonlSessionStore.find_session_by_metadata(parent_session_id=parent, match={"agent_id": "a..."})` 反查到 S 的 session。
4. 从 JSONL 完整加载 S 的 transcript 并重建 runtime session。
5. 把 prompt 作为 user-role input 追加到 S 的 transcript，启动新一轮 subagent run。
6. 输出 `output_file` 不变（同一 transcript 文件）。
7. 完成后发 `<task-notification>` 给父会话。

如果 SessionStore 也找不到该 `agent_id`（agent 从未在该父会话下创建过，或 transcript 文件被删除）：返回 `ToolError(agent_not_found)`，不得降级为"创建新 agent"。

### 10.6 回归场景

不得再出现：

- 后台 subagent 实际完成，但主 agent 只能看到 `Task timed out`。
- 后台完成结果只存在 LLM_PROXY 日志里，产品层无法访问。
- 用旧 `task(session_id=...)` 查询后台结果时误触发新的 continuation turn。
- 后台任务完成后无任何事件或通知。
- 主 agent 已结束上一轮回复、用户无新输入时，后台完成通知只停留在队列中而没有自动触发主 agent 继续。
- bash 长命令只能同步等待或超时报错，无法后台运行。
- 后台 bash 和后台 subagent 各自实现一套互不兼容的任务状态、停止、输出和通知机制。

## 11. 非目标

- 不复制 Claude Code 的 React/Ink UI。
- 不实现 Claude Code 的 2 秒 background hint。
- 不实现 remote CCR。
- 不实现 teammate/swarm。
- 不实现 worktree isolation。
- 不实现 prompt-cache fork。
- 不实现完整后台任务面板。
- 不复制 Claude Code 的内部 TypeScript 架构。

本功能的目标是迁移用户交互语义：后台任务是可见、可查、可停、会通知的一等任务。
