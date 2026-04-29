# Design: CC 风格后台任务基础设施

> **依赖**: feat-338 Kernel Message SSE 已落地。
>
> feat-338 提供了本 feature 唤醒父会话所需的全部产品交付链路：
> - `RunOrigin` 枚举与 `runs.submit(..., origin, source_task_id)` 入参。
> - `run_status` 事件携带 `origin` / `source_task_id`。
> - `GET /v1/sessions/{id}/stream` 持久 SSE 通道。
> - REPL 常驻 reader 与 Gateway per-session 订阅；非 user origin 的渲染 / 路由路径就位。
>
> 本 feature 仅是 feat-338 在内核侧的一个新的 run 触发源。除内部使用 `runs.submit(origin=BACKGROUND_TASK)` 之外，不动任何 HTTP / 客户端代码。

## 1. 目标

本设计实现一套统一后台任务基础设施，覆盖：

- 后台 subagent：`Agent(run_in_background=true)`
- 后台 bash：`bash(run_in_background=true)`
- foreground subagent 运行超过 120 秒后自动转后台
- foreground bash 在主线程运行超过 120 秒后自动转后台
- 后台任务完成后通过 `<task-notification>` 自动唤醒父会话
- `task_stop(task_id=...)` 停止后台 subagent 或后台 bash
- 通过 `output_file` 读取后台输出，不引入 `TaskOutputTool` 或 `background_output`

核心原则：

- 只有一套 task registry、状态机、通知队列、输出文件和停止机制。
- subagent 与 bash 只是不同 task type，不是两套系统。
- 后台任务结果不能只存在内存或 LLM proxy 日志中。
- 通知必须能让主 agent 在用户无新输入时继续工作。

## 2. 架构概览

新增能力按“内核语义 + 平台适配”拆分。原因是后台任务不是单个工具的实现细节，而是 agent loop 需要理解的一类异步输入来源：它有 task state、父会话 wakeup、notification priority、stop contract、tool prompt 语义和 session transcript 关系。这些属于内核运行时契约。

`core` 仍然保持无 IO。它定义模型、状态机、队列协议和 notification 格式，不直接访问文件系统、shell process 或 HTTP。`platform` 只提供这些协议的生产实现。

```text
src/agent/core/background_tasks/
  __init__.py
  ids.py
  models.py
  registry.py
  notifications.py
  queue.py
  interfaces.py
  runners.py

src/agent/platform/background_tasks/
  __init__.py
  task_store.py
  file_output.py
  shell_runner.py
  runtime_runner.py
  wiring.py
```

职责划分：

- `core/background_tasks/ids.py`：生成 CC 风格 background task id。agent 的用户可见 ID 为 `agent_id`，bash 的用户可见 ID 为 `task_id`。
- `core/background_tasks/models.py`：定义 `BackgroundTaskRecord`、状态枚举、task type、pending notification 类型。
- `core/background_tasks/interfaces.py`：定义 `BackgroundTaskStore`、`BackgroundTaskOutput`、`BackgroundTaskStopper`、`SessionInputQueue` 等 Protocol。
- `core/background_tasks/registry.py`：状态机、terminal 状态保护、notified 标记、stop 查找。它只依赖 `BackgroundTaskStore` 协议。
- `core/background_tasks/notifications.py`：生成 `<task-notification>` XML 和 prompt 约束文本。
- `core/background_tasks/queue.py`：定义父会话 pending input 的 priority/mode 规则。
- `core/background_tasks/runners.py`：定义 subagent/bash runner 的共同生命周期模板，具体执行通过注入接口完成。

core 层禁止直接调用 `datetime.utcnow()`、文件系统、shell。所有时间戳通过注入的 `Clock` Protocol 取得;`core/background_tasks/interfaces.py` 定义该协议,`platform/background_tasks/wiring.py` 装配真实时钟。这与现有 core 模块对 IO 的零依赖约束一致。
- `platform/background_tasks/task_store.py`：`BackgroundTaskStore` 的进程内实现，可把 terminal metadata 追加到 task 目录下的 manifest JSONL。
- `platform/background_tasks/file_output.py`：稳定 `output_file`、JSONL transcript、symlink/fallback、append/flush。
- `platform/background_tasks/shell_runner.py`：shell process handle、进程树停止、stdout/stderr 追加。
- `platform/background_tasks/runtime_runner.py`：把 `AgentRuntime` / `RunsRegistry` 接到 core runner 接口。
- `platform/background_tasks/wiring.py`：在 HTTP app / product bootstrap 中装配 registry、queue、tool context。

现有工具接入：

```text
AgentTool ─┐
           ├─ core.background_tasks.BackgroundTaskRegistry
BashTool  ─┘                       │
                                   ├─ BackgroundTaskStore protocol
                                   ├─ BackgroundTaskOutput protocol
                                   ├─ SessionInputQueue protocol
                                   └─ StopHandle protocol

platform adapters ── memory state / files / shell process / AgentRuntime / RunsRegistry / SSE
```

依赖方向：

```text
core.background_tasks      -> core types/protocols only
platform.background_tasks  -> core.background_tasks + platform persistence/safety/runtime
platform.tools.builtins    -> core.background_tasks + platform adapters
core.agent.runtime/loop    -> core.background_tasks queue protocol only where needed
```

这样做能避免 platform 反向决定内核行为，也不会让 core 直接碰 IO。`platform/tools/builtins/` 仍然放工具实现，是因为现有架构把内置工具实现归在 platform，但工具调用后进入的是 core 级后台任务生命周期。

## 3. 数据模型

后台任务记录：

```python
class BackgroundTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

class BackgroundTaskType(StrEnum):
    SUBAGENT = "subagent"
    BASH = "bash"

@dataclass(frozen=True, slots=True)
class BackgroundTaskRecord:
    task_id: str
    task_type: BackgroundTaskType
    parent_session_id: str
    agent_id: str | None
    agent_session_id: str | None
    description: str
    prompt: str | None
    agent_type: str | None
    command: str | None
    status: BackgroundTaskStatus
    created_at: str
    started_at: str | None
    ended_at: str | None
    output_file: str
    result_text: str | None
    error: str | None
    exit_code: int | None
    pending_messages: tuple[str, ...]
    usage: Mapping[str, Any] | None
    tool_use_count: int | None
    duration_ms: int | None
    notified: bool
```

ID 规则：

- subagent：`agent_id` 为 `a` + 16 hex，例如 `a1b2c3d4e5f6a7b8`
- bash：`b` + 16 hex，例如 `b1b2c3d4e5f6a7b8`
- subagent record 内部仍有 `task_id` 字段以共用 registry；对 agent task，`task_id == agent_id` 是内部不变量，但 tool result 和 prompt 不同时暴露两种字段。
- 主 agent 只看到 `agent_id`，并用 `Agent(agent_id=...)` 继续该 agent。
- bash 只看到 `task_id`，不能传给 `Agent(agent_id=...)`。

状态与输出保存选择：

- core 层只依赖 `BackgroundTaskStore` 协议。
- CC 的 local agent/local shell task state 是 live AppState，不是 SQLite；磁盘上稳定保存的是 task output file、subagent transcript，以及 remote task 这类需要跨进程轮询的 sidecar。
- 本项目对齐 CC：running task state 和 stop handle 放在进程内 registry；`output_file` 和 subagent transcript 写稳定文件。
- terminal metadata 可以追加到 task 目录下的 manifest JSONL，用于调试、回放和启动后展示历史状态；它不是 job database，也不负责恢复本地 running process。
- 进程重启后无法恢复 OS process 或 LLM future；已有 `output_file` 保持可读。后台任务数据库不是本功能目标。

## 4. 输出文件

### 4.1 路径

后台任务的 `output_file` 必须落在当前 session workspace 内，使用 `platform/persistence/session/service.py` 提供的 workspace 根解析器，禁止在 `core` 或工具实现里硬编码 `.nano/`。

bash：

```text
<workspace_root>/tasks/<parent_session_id>/<task_id>.output
```

subagent：不另开文件。`output_file` 直接指向该 subagent session 的 transcript JSONL，由现有 `core/session/jsonl_store.py` 写入；路径由 `JsonlSessionStore` 已有逻辑决定，后台任务只读取它的真实路径并暴露给主 agent。

### 4.2 subagent transcript

只有一份真相源：session transcript。

- subagent 仍然是一个普通 session，由 `SessionManager` 创建，`JsonlSessionStore.append(session_id, entry, parent_session_id=parent)` 写每一条 user/assistant/tool entry。
- `output_file` 等于该 subagent session 的 transcript 文件路径；不再单独维护 `transcript_file` 字段。
- continuation 复用同一个 subagent session,继续向同一 transcript 追加。
- 主 agent 用 `read` 工具读 `output_file` 即得 JSONL transcript;不引入并行 transcript writer,也不在 task 目录复制同等 JSONL。

`BackgroundTaskRecord` 因此移除 `transcript_file`,只保留 `output_file`。subagent 的 `output_file` 由后台任务 wiring 在创建 session 后向 `JsonlSessionStore` 询问得到。

### 4.3 bash output

- `output_file` 是 stdout/stderr 追加文件,位置见 §4.1。
- stderr 使用 `[stderr] ` 前缀或结构化等价标记。
- 后台 bash 启动后立即创建文件;无输出时写入一行状态头,避免 `read` 看到不存在文件。
- **输出文件硬上限**: 默认 **256 MiB**（`BACKGROUND_BASH_MAX_OUTPUT_BYTES`, 通过 `agent_settings.yaml` 覆盖）。超过上限后:
  - 终止进程并发送 `SIGKILL`（参考 CC 的 5GB kill-switch,本项目取值更保守）。
  - 标记 task 为 `killed`,`<task-notification>` 中说明 `output_truncated=true`。
  - 保留已产生的输出文件内容（到 256 MiB 为止）。
- 不设 model-facing 截断（如 CC 的 30K `BASH_MAX_OUTPUT_LENGTH`）。后台任务不直接把 stdout 喂给模型;主 agent 用 `read` 工具按需读取,由 `read` 自身的预算控制。

### 4.4 写入 API

core 只暴露 bash 输出协议;subagent 走 `JsonlSessionStore`,不复制一份。

```python
class BashTaskOutput(Protocol):
    def open(self, parent_session_id: str, task_id: str) -> Path: ...
    def append(self, task_id: str, text: str, *, stream: Literal["stdout", "stderr"]) -> None: ...
    def flush(self, task_id: str) -> None: ...
```

写入必须是追加式、线程安全、失败可记录。不得在任务完成时删除 output file。`platform/background_tasks/file_output.py` 是该协议的生产实现,内部使用 workspace 根解析器。

## 5. Registry 接口

```python
class BackgroundTaskStore(Protocol):
    def insert(self, record: BackgroundTaskRecord) -> None: ...
    def update(self, record: BackgroundTaskRecord) -> None: ...
    def get(self, task_id: str) -> BackgroundTaskRecord | None: ...
    def list_non_terminal(self) -> Sequence[BackgroundTaskRecord]: ...

class BackgroundTaskRegistry:
    def register_subagent(...)-> BackgroundTaskRecord: ...
    def register_bash(...)-> BackgroundTaskRecord: ...
    def mark_running(task_id: str) -> None: ...
    def complete(task_id: str, *, result_text: str | None, usage: Mapping[str, Any] | None) -> None: ...
    def fail(task_id: str, *, error: str) -> None: ...
    def kill(task_id: str, *, reason: str = "stopped") -> None: ...
    def get(task_id: str) -> BackgroundTaskRecord | None: ...
    def request_stop(task_id: str) -> StopHandle: ...
    def enqueue_agent_message(agent_id: str, prompt: str) -> None: ...
    def drain_agent_messages(agent_id: str) -> tuple[str, ...]: ...
```

Registry 是 core 层状态机。它只管理生命周期，不直接执行 LLM、shell、文件写入或数据库细节；这些都由注入的 store/output/runner 适配器完成。

状态转换：

```text
queued -> running
running -> completed
running -> failed
running -> killed
queued -> killed
```

Terminal 状态不可覆盖，除非同一状态补充 `notified=true`。

## 6. Subagent Runner

### 6.1 显式后台

`Agent(run_in_background=true)` 流程：

1. 生成 `agent_id`。
2. 创建 subagent runtime session，并写入内部映射 `agent_id -> runtime_session_id`。
3. 创建 transcript/output file。
4. 注册 `BackgroundTaskRecord(type=subagent, task_id=agent_id, agent_id=agent_id, agent_session_id=runtime_session_id, status=running)`。
5. 在线程池提交 subagent turn。
6. 立即返回 tool result：

```json
{
  "status": "async_launched",
  "agent_id": "a...",
  "description": "...",
  "output_file": "..."
}
```

7. worker 完成后写状态、flush transcript、发送 `<task-notification>`。

### 6.2 Foreground 自动转后台

`Agent(run_in_background=false)` 不再只是 `future.result(timeout=...)`。

设计：

- foreground subagent 启动时也注册 task，`is_backgrounded=false`。
- 主线程等待结果，同时启动 foreground 预算 timer。
- 默认 foreground 预算 = 120 秒；若工具调用显式传入 `timeout_seconds`，该值覆盖 120s。
- timer 到且任务仍 running：
  - 设置 `is_backgrounded=true`
  - 当前 tool call 返回 `async_launched`
  - worker future 继续运行
  - 完成后发送通知
- 如果 timer 内完成，返回同步 completed 结果，并把 task terminal 化。
- 超过 `timeout_seconds` 仍 running：同 auto-background 路径返回 `async_launched`，不返回 `Task timed out`。

这避免现在的 `Task timed out` 与后台 future 继续跑之间的错位。

### 6.3 Continuation

`Agent(agent_id=...)` 的解析顺序：

1. **In-memory live runtime**：如果 `agent_id -> runtime_session_id` 映射在进程内存且 runtime 实例仍活，按 §6.3.1 处理（running 或 terminal-but-loaded）。
2. **In-memory registry only**：映射存在但 runtime 已被释放（例如缓存淘汰）—— 走 §6.3.2 的 rehydrate-from-JSONL 路径，但跳过 SessionStore 反查。
3. **None of the above（kernel 重启或父会话 resume）**：进程内既无映射也无 runtime；走 §6.3.2，从 SessionStore + manifest 反查 + JSONL 恢复。
4. 如果都查不到，工具返回 `ToolError(agent_id_not_found)`。

#### 6.3.1 Running / loaded 路径

- 如果 ID 对应 running subagent，不启动第二个 run，不直接注入 active context；把 `prompt` 追加到该 agent 的 `pending_messages` 队列，并立即返回 `message_queued`。
- running agent 在安全点消费 pending messages：当前 LLM response 完成、当前工具执行批次完成、下一次 LLM request 构建前。不能在 tool execution 中途或 LLM stream 中途打断。
- 消费时，按 FIFO 把 pending messages 作为 user-role input 追加到该 subagent runtime session 和 transcript，然后由同一个 worker 继续下一轮推理。
- 如果 ID 对应 terminal subagent 且 runtime 仍在内存：用同一 transcript/output file 启动新一轮；完成后发 `<task-notification>`。
- 如果恢复运行超过 120 秒，同样转后台。
- `Agent(agent_id=...)` 不用于查询后台结果。查询只能读 `output_file`。

运行中插话返回：

```json
{
  "status": "message_queued",
  "agent_id": "a...",
  "description": "...",
  "output_file": "...",
  "message": "Message queued for delivery to the agent at its next tool round."
}
```

这对齐 CC 的 local agent task：运行中的 agent task 持有 `pendingMessages`；`SendMessage` 命中 running local agent 时调用 `queuePendingMessage()`，并返回"queued for delivery at its next tool round"。本项目不用单独 `SendMessage` 工具，但 `Agent(agent_id=..., prompt=...)` 的 running 行为必须等价。

#### 6.3.2 从 JSONL 恢复（kernel 重启 / 主 agent resume）

场景：父会话因 kernel 重启或主 agent 长时间 idle 后恢复，进程内 background task registry 已丢失；主 agent 想接着对某个之前用过的 subagent 说话。

为了支持这一场景，subagent session 创建时必须把 `agent_id` 写入 session metadata（落地到 JSONL，由 `JsonlSessionStore` 持久化）：

```python
session_manager.create_session(
    parent_session_id=parent,
    metadata={
        "kind": "subagent",
        "agent_id": agent_id,
        "agent_type": agent_type,
        # ... other subagent metadata
    },
)
```

`Agent(agent_id=...)` 在内存中找不到时：

1. 调 `session_store.find_session_by_metadata(parent_session_id=parent, agent_id=agent_id)`（需要在 `JsonlSessionStore` 上新增按 metadata 反查的能力，详见 §10）。
2. 命中后调 `session_manager.load_session(session_id)` 读取 JSONL，重建 session 状态（messages / tool calls / transcript）。
3. 重建的 session 注册回内存映射：`agent_id -> runtime_session_id`，状态为 terminal/loaded。
4. 之后走 §6.3.1 的 terminal 路径：用同一 transcript 启动新一轮，把 `prompt` 作为 user-role input 追加。
5. 如果重建超过 120 秒（由读取 + reconstruct 触发的延迟），按现有 foreground 自动后台化逻辑转后台。

恢复必须是无损的：

- transcript 中所有历史 user/assistant/tool entries 完整加载到新 runtime session。
- 后续追加进 transcript 的内容仍是同一文件（`output_file` 路径不变）。
- 恢复后的 run 的 `origin = USER`（这是主 agent 显式调起的延续，不是后台任务唤醒），也不带 `source_task_id`。

如果 SessionStore 查不到（agent_id 从未在该 parent 下创建过，或 transcript 文件被删除）：

- 工具返回 `ToolError(code="agent_not_found", message="No subagent with agent_id=... found in session history.")`。
- 不要降级为"创建新 agent"，避免 silent identity 漂移。

## 7. Bash Runner

### 7.1 工具 schema

`bash` 新增：

```json
"description": {
  "type": "string",
  "description": "Clear concise description of what this command does."
},
"run_in_background": {
  "type": "boolean",
  "description": "Set true to run the command in the background. Use this for long-running commands when you do not need the result immediately. The call returns immediately with task_id/output_file; the command keeps running and you will be notified automatically when it completes. Do not append '&' to the command."
}
```

`timeout` description 更新：

```text
Command timeout. This controls when the command itself should be terminated. It is separate from foreground auto-backgrounding: foreground bash may move to the background after 15 seconds without failing the command.
```

### 7.2 显式后台

`bash(run_in_background=true)`：

1. 生成 `b...` task id。
2. 创建 output file。
3. 注册 `type=bash, status=running`。
4. 启动 shell process，stdout/stderr 直接追加 output file。
5. 立即返回 `async_launched` 风格结果。
6. process exit 后标记 completed/failed，发送 notification。

需要新增安全执行接口，因为当前 `ctx.safety.run_command_stream()` 是同步封装。

协议必须新增在 **`src/agent/core/tools/safety_types.py`** 的 `ToolSafetyLike` Protocol 中，与现有 `run_command` / `enforce_command_policy` 同层。`platform/tools/safety.py` 实现该方法。这是硬约束：协议不得只在 platform 层定义，否则 builtin 工具会反向依赖 platform。

```python
# core/tools/safety_types.py
class BackgroundCommandHandle(Protocol):
    pid: int | None
    output_file: Path
    def wait(self) -> CommandExecution: ...
    def terminate_tree(self) -> None: ...

class ToolSafetyLike(Protocol):
    ...  # existing methods
    def start_command_background(
        self,
        command: str,
        *,
        cwd: Path,
        tool_name: str,
        output_file: Path,
        timeout: float | None,
    ) -> BackgroundCommandHandle: ...
```

platform 实现复用当前 command policy、cwd、allow_unlisted、timeout 逻辑；差别是返回 handle 而不是阻塞到结束,stdout/stderr 由 handle 内部 pump 到 `output_file`。

### 7.3 Foreground 15 秒自动转后台

为了避免一开始就要求所有 bash 走异步 process API，bash 执行统一走 background-capable handle：

- foreground bash 也先创建 task record，`is_backgrounded=false`。
- 主线程等待 process 完成。
- 15 秒到且仍 running：
  - 设置 `is_backgrounded=true`
  - 返回后台回执
  - process 继续写同一个 output file
- 15 秒内完成：
  - 读取 output file 返回原有同步结果
  - terminal task 不发 `<task-notification>`，因为用户已经在当前 tool result 中看到结果。

如果实现上保留当前同步 path，就无法无损转后台；因此 bash 必须迁移到 handle-based execution。

## 8. task_stop

新增内置工具 `task_stop`：

schema：

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string",
      "description": "ID of the running background task returned by Agent(run_in_background=true), bash(run_in_background=true), or foreground auto-backgrounding. For an agent, pass its agent_id."
    }
  },
  "required": ["task_id"],
  "additionalProperties": false
}
```

行为：

- 查 registry。
- 非 running/queued：返回 `ToolError` 并给出替代操作建议，方便模型直接处理。

  ```text
  code: task_not_running
  message: Task "{task_id}" is not running (status: {status}). Use Read on output_file to inspect output or result.
  output_file: /path/to/...
  ```

- subagent：调用 runner stop，取消 LLM run 和正在执行的工具；记录 partial result。
- bash：终止进程树。
- 标记 `killed`。
- 保留 output file。
- 对父会话发送 killed notification。

## 9. 通知与自动唤醒

### 9.1 Notification 格式

subagent：

```xml
<task-notification>
<task-id>a...</task-id>
<agent-id>a...</agent-id>
<output-file>/...</output-file>
<status>completed</status>
<summary>Agent "..." completed</summary>
<result>...</result>
<usage><total_tokens>...</total_tokens><tool_uses>...</tool_uses><duration_ms>...</duration_ms></usage>
</task-notification>
```

bash：

```xml
<task-notification>
<task-id>b...</task-id>
<output-file>/...</output-file>
<status>completed</status>
<summary>Command "..." completed with exit code 0</summary>
<exit-code>0</exit-code>
</task-notification>
```

### 9.2 唤醒投递机制

后台任务完成时由 `core/background_tasks/runners.py` 的 lifecycle 末尾调用：

```python
def _deliver_completion_notification(record: BackgroundTaskRecord) -> None:
    notification_xml = build_task_notification_xml(record)
    parent = record.parent_session_id
    active = runs.get_active_run_id(parent)
    if active is not None:
        # 复用现有 pending message 注入路径，活跃 run 下一个工具轮次边界消费。
        runs.inject_pending_message(
            parent,
            LLMMessage(role="user", content=notification_xml),
        )
        return
    # 父会话空闲：直接启动新 run。
    runs.submit(
        session_id=parent,
        parts=[{"type": "text", "text": notification_xml}],
        origin=RunOrigin.BACKGROUND_TASK,
        source_task_id=record.task_id,
    )
```

要点：

- **不新增** `SessionInputQueue` 抽象。pending 注入直接复用 `inject_pending_message`，与 feat-338 `priority=next` 走同一队列。用户输入到来时（`priority=next`）会自然按 FIFO 排在 pending 之后；但因为活跃 run 处理 pending 是在 round 边界批量 drain，实际效果是"用户输入和后台通知都在下一轮被一起喂给模型"，这与 spec §7.1 的批量合并要求一致。
- 父会话空闲时启动的新 run 的 `origin = BACKGROUND_TASK`，`source_task_id` 指向触发的后台任务。事件由 feat-338 `/stream` 自然下发。
- 父会话已有 run 时注入路径走 `priority=next` 等价语义，新 run 的 origin 仍是该活跃 run 自己的（通常是 `USER`）；通知出现在该 run 的 user-role messages 中，模型按 prompt 规则识别。

### 9.3 多通知合并

如果短时间内多条后台任务完成、父会话仍空闲：

- 每条通知都会触发 `runs.submit`，串行启动多个 origin=BACKGROUND_TASK run。
- 如果希望合并为一个 run，可以在 `_deliver_completion_notification` 加一个短窗口（例如 50ms）合并器：把同 session 内 50ms 内到达的多条 notification 合并到一个 `parts=[{type:text,text:joined_xmls}]` 提交。
- 实现可选；首版采用"一通知一 run"，简单且与 feat-338 的 `/stream` fan-out 配合自然。后续观察体验再决定是否合并。

### 9.4 产品交付契约

REPL / Gateway / Web IM 看到唤醒输出的能力以 feat-338 `/stream` 为基础，但 feat 337 必须把客户端交付前提验收清楚。不能只假设“常驻 reader 已就位”，因为后台任务的核心体验是“用户无新输入时也能看到主 agent 被后台结果唤醒后的输出”。

- REPL：常驻 `/stream` reader 看到 `run_status{origin=background_task, source_task_id=...}`，渲染 background 标头，逐帧渲染该 run 的 assistant_message / tool_start / tool_end，直到 terminal `run_status`。
- Gateway：per-session `/stream` 订阅识别 `origin != user` 的 run，按 session_key 串行队列调度 outbound 回 IM channel，`upstream_reporter.report` 携带 `origin` / `source_task_id`。
- 离线 / 重连：客户端通过 `Last-Event-ID` 续传，或调用消息历史 API 拉取 transcript。

HTTP 路由和 SSE 编码不需要新增。但如果现有 REPL / Gateway 不满足下列交付契约，必须作为本 feature 的补齐范围，而不是把后台任务停在“内核已发事件”的半成品状态。

REPL delivery contract：

- Session active 后必须保持 per-session `/stream` reader。
- 当前用户 run drain 时，非当前 run 的 `origin != user` 事件不能丢弃。
- 用户停在 prompt 等输入时，REPL 必须周期性 poll reader；后台唤醒输出不能依赖用户下一次按键才显示。
- 同一个 background run 的 seen/pending 状态必须跨 main-run drain、post-turn grace drain、prompt-idle drain 共享。`run_status` 在一个阶段到达、assistant/tool 事件在另一个阶段到达时不能丢消息。
- `run_status` 之前到达的 assistant/tool 事件必须按 `run_id` buffer，等 origin 被确认后再渲染。
- Grace drain 只能是短促 opportunistic drain，不能每轮固定等待数秒；prompt idle callback 才是持续后台可见性的主路径。

TTY rendering contract：

- Raw terminal mode 下必须恢复 `OPOST | ONLCR`，否则 `print()` 的 `\n` 可能成为 bare LF。
- 所有 assistant/tool/background/summary/context/error 输出必须经统一 terminal-safe renderer 或显式 CRLF；裸 `\n` 会继承当前光标列，造成阶梯缩进。
- 在已有 prompt/input 正在显示时，外部输出必须 clear 当前输入行、输出完整 block、再恢复 prompt 和草稿。
- `State`、`Usage`、`Context budget` 等 turn summary 行必须从第 0 列开始。

IME/input contract：

- Prompt idle polling 不得混用 `select(fd)` 和 `TextIO.read(1)`。Python TextIO 可能已经缓冲输入法一次 commit 的后续字符，导致 `select(fd)` 认为无新数据。
- Idle key reader 必须从 fd 读取 bytes、增量解码并排入 token queue。中文输入法一次提交 `你好吗` 时，三个字符必须连续进入输入缓冲，不依赖下一次按键触发刷新。

M10 将 CLI 侧补齐为明确架构：

- `coding_cli.events.background_runs`：识别非 user run、维护 seen/pending、输出 display lines。
- `coding_cli.render.terminal_output`：TTY-safe CRLF line emission。
- `coding_cli.input.repl_input`：idle-aware, IME-safe raw key reader。
- `coding_cli.commands`：只编排 reader、processor、renderer，不直接拥有后台 run 状态机。

### 9.5 Prompt 约束

`<task-notification>` 是 core 后台任务机制的一部分,主 agent 必须知道它的身份。提示片段必须同时满足两件事：

1. 属于 core（定义由 core 给出，产品不能各自发明版本）。
2. 拼入主 agent 的 system prompt 末尾（逻辑上作为 system 指令的一部分，不是 tool description）。

落点：

- `core/background_tasks/notifications.py` 暴露常量 `BACKGROUND_TASK_PROMPT_BLOCK: str`，内容包含规则列表，并由该模块同时负责生成 `<task-notification>` XML，保证两者用词一致。
- 各 product 的 system prompt 装配代码（如 `products/local_coding/prompt_builder.py`、`products/personal_assistant/prompt_builder.py` 或等价模块）在拼装最终 prompt 时，把 `BACKGROUND_TASK_PROMPT_BLOCK` 追加到 system prompt 末尾。
- core 不直接改 product 的 prompt 源码文件，只导出常量；product 层负责接入。这是装配契约，验收时由 contract test 检查最终 prompt 是否包含该 block。

规则内容：

- `<task-notification>` 是 worker/system signal，不是真实用户请求。
- 不要感谢 notification。
- 综合新信息，继续服务用户目标。
- 如果需要细节，读取 `output_file`。
- 不要轮询后台任务；完成会通知。

## 10. Session transcript

subagent transcript 复用现有 session 存储,不新建并行 transcript writer:

- subagent session 通过 `SessionManager` 创建,`parent_session_id` 指向父会话。
- session metadata 必须包含 `kind="subagent"` 和 `agent_id`,以支持 §6.3.2 的 rehydrate-from-JSONL 反查。
- 每条 subagent user/assistant/tool entry 由现有 runtime/loop 经 `JsonlSessionStore.append(session_id, entry, parent_session_id=parent)` 写入。后台任务模块不旁路这条链路。
- `output_file` = 该 subagent session 的 transcript 文件实际路径。后台任务 wiring 在创建 session 后向 store 询问该路径并写入 `BackgroundTaskRecord.output_file`。
- continuation 复用同一个 subagent session,自然向同一 transcript 追加。
- bash 没有 session,output 由 §4.4 的 `BashTaskOutput` 协议管理,不写入 `JsonlSessionStore`。

### 10.1 SessionStore 元数据反查能力

为支持 §6.3.2 的 rehydrate,`JsonlSessionStore` 需要新增按 metadata 反查的能力:

```python
class JsonlSessionStore:
    def find_session_by_metadata(
        self,
        *,
        parent_session_id: str | None,
        match: Mapping[str, Any],
    ) -> str | None:
        """Return session_id whose metadata matches all key/value pairs in `match`.

        Used by background tasks to resolve agent_id → runtime session_id when
        the in-memory mapping has been lost (kernel restart, parent agent resume).
        """
```

实现细节:

- session metadata 已经是 JSONL session 的第一行(meta entry)。本方法扫描 store 的 session index,读取每个 session 的 meta 行,做精确匹配。
- 性能保护:`match` 必须包含 `agent_id`(本 feature 唯一调用模式);store 内部维护 `agent_id -> session_id` 二级索引(初次扫描时构建,后续 append 增量更新)。索引可以是内存 dict,也可以落到 store 目录下的 sidecar 文件,首版选内存即可,kernel 重启后第一次反查时按需扫描 rebuild。
- 反查范围限定 `parent_session_id`:防止跨父会话拿错 subagent。

### 10.2 内部映射

subagent 必须使用内部映射,而不是让 runtime session id 等于用户可见 `agent_id`:

```text
agent_id -> runtime_session_id
```

理由：

- `agent_id` 是用户/模型可见的 worker identity，对齐 CC 的 Agent ID。
- `runtime_session_id` 是内核会话存储和执行细节，不应出现在工具 schema、回执或 prompt 中。
- 强行让 runtime session 支持外部指定 ID，会把 session store 的 ID 生成、唯一性和兼容性约束暴露给 Agent 工具。
- 映射只存在于后台任务 registry/session metadata 中；主 agent 不需要知道它。

## 11. Tool Prompt 与 Schema 对齐

这里要全盘对齐 CC 的用户交互语义，而不是只给 `run_in_background` 加一句说明。需要同时调整 tool description、参数 description、tool result 文案和 system prompt 中的后台任务规则。实现可以保留本项目工具名小写风格，但语义要和 CC 一致。

### 11.1 Agent 工具整体语义

CC `AgentTool` 的核心描述是“Launch a new agent to handle complex, multi-step tasks autonomously”。本项目用户可见工具命名为 `Agent`，首要语义是“启动 autonomous subagent 处理复杂、多步骤、可并行的任务”。项目开发态、无向后兼容承诺，`task` 工具名直接删除，不保留 alias。

description 必须覆盖：

- 用于复杂、多步骤、需要独立上下文或并行探索的任务。
- 不用于读取明确文件路径、搜索单个符号、或 2-3 个文件内的简单查找；这些应使用 `read`/`bash`/搜索工具。
- 新 subagent 默认从自己的上下文开始；prompt 必须给足目标、背景、约束、已知信息和期望输出。
- 如果用户要求并行，主 agent 应在同一轮中发起多个独立 `Agent` 调用。
- foreground 是默认：当主 agent 下一步依赖 subagent 结果时使用 foreground。
- background 只用于真正独立的工作；后台完成会自动以 `<task-notification>` 返回，不要 sleep、poll 或主动查进度。
- subagent 的结果对真实用户不可见，主 agent 需要综合后回复用户。
- `output_file` 是后台任务输出读取入口；不要引入或暗示 `TaskOutputTool`。
- `task_stop(task_id=...)` 可停止后台 subagent；对 agent 传入的值就是 `agent_id`。

### 11.2 Agent 参数 schema

Agent schema 不暴露 `session_id`。继续已有 subagent 使用同一个工具的 `agent_id` 参数。

```json
{
  "description": {
    "type": "string",
    "description": "A short (3-5 word) description of the task."
  },
  "prompt": {
    "type": "string",
    "description": "The task or follow-up instruction for the agent to perform. For a fresh agent, include enough context for it to act independently. When agent_id is provided, this is the follow-up message for that existing agent."
  },
  "subagent_type": {
    "type": "string",
    "description": "The type of specialized agent to use for this task."
  },
  "category": {
    "type": "string",
    "description": "Predefined category that selects a specialized agent. Mutually exclusive with subagent_type for new tasks."
  },
  "load_skills": {
    "type": "array",
    "description": "Skill names to load for the spawned agent. Pass [] when no extra skills are needed."
  },
  "run_in_background": {
    "type": "boolean",
    "description": "Set true to run this agent in the background. The call returns immediately with agent_id and output_file. You will be notified automatically when it completes; do not sleep, poll, or proactively check progress."
  },
  "agent_id": {
    "type": "string",
    "description": "Send a follow-up instruction to an existing agent by ID with full context preserved. If the agent is running, the message is queued and delivered at the agent's next tool-round boundary. If the agent is stopped, it resumes from its transcript. Do not use this to check background progress or output; read output_file for output."
  },
  "timeout_seconds": {
    "type": "number",
    "description": "Maximum foreground wait before this call stops waiting. This is distinct from the default 120 second foreground auto-background behavior."
  }
}
```

**注**：`timeout_seconds` 不是 CC 原生参数（CC 的 AgentTool 没有 timeout，只有 120s auto-background 且默认关闭）。本项目引入它作为 convenience 参数，语义为"覆盖 120s 默认值的前台等待预算；超预算后转后台"。

当前描述中的这些文案必须删除或改写：

- `Use background=true ONLY for parallel exploration with 5+ independent queries.` CC 并没有这个 5+ 门槛；是否后台取决于“是否需要立即结果”。
- `Use task with session_id=... to check progress.` 这是 bug 来源；新 Agent 工具不再暴露 `session_id`。
- `Task timed out` 但后台仍继续跑。超过默认 foreground budget 后应返回后台回执，而不是把仍在运行的任务描述为 failed。

### 11.3 Agent result 文案

后台启动回执必须和 CC 一样让模型知道三件事：任务已经在后台跑、无需轮询、完成会通知。

```text
Background task launched.

agent_id: a...
description: ...
status: running
output_file: /...

You will be notified automatically when this task completes. Do not poll.
Read output_file only if the user asks for progress or you need details.
Use task_stop with task_id="a..." to stop it.
Use Agent with agent_id="a..." only to continue the agent conversation.
```

foreground 自动后台化返回同一类回执，但标题用 `Agent moved to background.`。同步完成仍返回 agent 最终结果，并提醒“结果对用户不可见，需要主 agent 汇总给用户”的语义。

### 11.4 bash 工具整体语义

CC `BashTool` 的 description 不只是“执行命令”。它同时告诉模型如何和文件工具分工、如何处理并行命令、timeout、git、安全、sleep、后台任务。完整迁移时，本项目 `bash` description 至少要覆盖这些与当前产品相关的部分：

- 执行 bash 命令并返回 stdout/stderr。
- shell working directory 绑定当前 session workspace；不要依赖跨 tool call 的 shell state。
- 读文件优先用 `read`，写文件优先用 `write`/`edit`；bash 用于这些工具无法自然完成的命令、测试、构建、git、系统检查。
- 多个互不依赖的命令应使用并行 tool calls；有依赖关系时才在单个 command 中串联。
- 避免无意义 `sleep`。长任务需要稍后通知时用 `run_in_background`；等待后台任务完成时不要 poll。
- 不需要在 command 末尾加 `&`；后台能力由工具参数提供。
- `timeout` 是命令终止策略，不是 foreground UI 等待预算。
- foreground bash 运行超过 15 秒默认自动转后台，并返回 `task_id/output_file`。
- 后台 stdout/stderr 写入 `output_file`；完成后自动通知。
- 用 `task_stop(task_id=...)` 停止后台命令。

### 11.5 bash 参数 schema

```json
{
  "command": {
    "type": "string",
    "description": "The bash command to execute."
  },
  "description": {
    "type": "string",
    "description": "Clear concise description of what this command does."
  },
  "timeout": {
    "type": "number",
    "description": "Command timeout in seconds. This controls when the command itself is terminated and is separate from foreground auto-backgrounding."
  },
  "run_in_background": {
    "type": "boolean",
    "description": "Set true to run the command in the background. Use this when you do not need the result immediately and are OK being notified when it completes. The call returns immediately with task_id and output_file. Do not append '&' to the command."
  }
}
```

`description` 对 bash 应是必填还是可选，取决于本项目对现有模型兼容性的取舍。设计要求是：tool description 必须鼓励模型提供；实现若设为可选，也要在回执中能从 command 推导 fallback summary。

### 11.6 bash result 文案

显式后台或 15 秒自动后台化：

```text
Background command started.

task_id: b...
description: ...
status: running
output_file: /...

You will be notified automatically when this command completes. Do not poll.
Read output_file only if the user asks for progress or you need details.
Use task_stop with task_id="b..." to stop it.
```

同步完成保持现有 stdout/stderr/exit code 体验；如果输出超预算，继续使用现有 result budget 压缩机制，但压缩预览必须包含完整输出文件路径。

### 11.7 task_stop 工具

CC 的 `TaskStop` 语义是“Stop a running background task by ID”，同一个工具停止 background shell、async agent、remote session。本项目新增 `task_stop`，语义对齐：

description：

```text
Stop a running background task by ID.
```

prompt：

```text
- Stops a running background task by its ID
- Takes a task_id parameter identifying the task to stop
- Returns a success or failure status
- Use this tool when you need to terminate a long-running task
```

schema：

```json
{
  "task_id": {
    "type": "string",
    "description": "The ID of the background task to stop."
  }
}
```

输出包含 `message`、`task_id`、`task_type`、`command` 或 `description`。不需要兼容 CC 的 deprecated `shell_id`，因为本项目没有历史 `KillShell` 工具。

### 11.8 TaskOutputTool / Read 的关系

CC 已把 `TaskOutputTool` 标记为 deprecated，prompt 明确要求优先 Read task output file。本项目不实现 `TaskOutputTool`、`background_output` 或“用 `session_id` 查询输出”的替代工具。

因此还需要确认 `read` 工具 description 能自然承接后台输出：

- `read` 可以读取普通文本文件。
- 后台任务回执和 notification 提供的是可直接读取的 `output_file`。
- 不需要在 `read` 工具 schema 中新增后台任务参数。

### 11.9 system prompt 对 `<task-notification>` 的解释

仅更新工具 description 不够。主 agent 的系统 prompt 必须解释 notification 的身份，否则模型容易把它当成真实用户输入。

新增规则：

```text
<task-notification> messages are internal worker/system notifications delivered as user-role messages. They are not new user requests. Do not thank them. Use the result to continue the user's original task, synthesize any useful findings for the user, and read output_file only when details are needed.
```

这条规则应由 core prompt 拼装提供，因为 notification 是 core 后台任务机制的一部分，不应散落在 CLI 或 gateway 产品 prompt 中。

## 12. 数据流

### 12.1 后台 subagent

```text
LLM calls Agent(run_in_background=true)
  -> AgentTool validates args
  -> BackgroundTaskRegistry.register_subagent()
  -> create subagent session/transcript
  -> submit worker to executor
  -> return async_launched
  -> worker runs AgentRuntime
  -> transcript append
  -> registry completed/failed/killed
  -> enqueue <task-notification>
  -> parent session queue wakes main run when idle
```

### 12.2 foreground subagent auto-background

```text
LLM calls Agent(run_in_background=false)
  -> register foreground task
  -> start worker
  -> wait for result and 120s timer
  -> result wins: return completed
  -> timer wins: mark backgrounded, return async_launched
  -> worker continues
  -> completion notification wakes parent
```

### 12.2.1 message to running agent

```text
LLM calls Agent(agent_id=a..., prompt="...")
  -> AgentTool resolves agent_id
  -> registry verifies task type is subagent
  -> task is running
  -> registry.enqueue_agent_message(agent_id, prompt)
  -> append the user message to transcript/view state as pending
  -> return message_queued immediately
  -> worker reaches next safe point
  -> registry.drain_agent_messages(agent_id)
  -> append drained messages to subagent runtime session as user-role inputs
  -> continue the same worker loop
```

Safe point means after the current model stream or tool execution batch completes, before building the next model request. It must not interrupt an active shell command, file edit, tool call, or model stream.

### 12.3 后台 bash

```text
LLM calls bash(run_in_background=true)
  -> BashTool validates policy
  -> BackgroundTaskRegistry.register_bash()
  -> start process handle
  -> stdout/stderr append output_file
  -> return async_launched
  -> process exits
  -> registry completed/failed
  -> enqueue <task-notification>
  -> parent session queue wakes main run when idle
```

### 12.4 foreground bash auto-background

```text
LLM calls bash(run_in_background=false)
  -> start process handle + register foreground bash task
  -> wait for process and 15s timer
  -> process wins: return normal stdout/exit result
  -> timer wins: mark backgrounded, return async_launched
  -> process continues writing output_file
  -> completion notification wakes parent
```

## 13. 错误处理

- 启动失败：tool call 直接返回 ToolError，不创建 running task；如果已创建 record，标记 failed。
- worker 异常：标记 failed，通知带 error。
- bash exit code 非 0：标记 failed，通知带 exit code，output file 保留。
- stop：标记 killed，通知带 partial output 或 stop summary。
- 进程重启：本地 running task 不恢复；已有 output file 保持可读，manifest 可用于调试或展示最后已知状态。
- notification enqueue 失败：registry 保持 `notified=false`；同进程内重试投递。

## 14. 关键权衡

### 14.1 统一 registry，而不是分别实现

选择统一 registry，因为 stop、通知、SSE、output file、恢复语义完全一致。分开实现会导致用户看到两个不兼容后台系统，也会让 `task_stop` 复杂化。

### 14.2 不实现 TaskOutputTool

拒绝 `background_output`/`TaskOutputTool`，因为目标是对齐 CC 的最终交互：工具回执和通知都给 `output_file`，模型用现有 `read` 工具读取。少一个查询工具也减少 `session_id` 被误用成“查询”的风险。

### 14.3 不引入 SQLite 后台任务库

CC 的本地后台任务不依赖 SQLite registry。对本项目而言，核心问题是当前后台任务完成后没有投递回父会话，而不是缺少可查询数据库。running task 需要的是内存中的 future/process/stop handle；完成后需要的是 notification 和稳定 `output_file`。引入 SQLite 会增加迁移、并发更新和恢复语义成本，还容易把后台任务误设计成持久 job queue。

设计采用：

- live registry：进程内保存 running/queued task state 和 stop handle。
- stable files：subagent transcript、bash stdout/stderr、manifest JSONL 放在 task 目录。
- session queue：负责把 completion notification 投递回父会话。

这样对齐 CC，也更简单。

### 14.4 foreground bash 必须使用 handle-based execution

当前同步 `run_command_stream()` 无法在 15 秒后无损转后台。为了实现自动后台化，bash 必须从一开始就持有可等待、可停止、可继续写文件的 process handle。

### 14.5 通知入队，不直接打断 active run

直接注入 active run 会改变当前推理上下文，可能在工具执行中间引入结果。采用 pending queue，等 run idle 后启动新 turn，符合 CC 行为，也避免并发写同一会话。

## 15. 拒绝的方案

- **只修旧 TaskTool._task_results**：仍然没有自动唤醒、稳定输出和 bash 支持。
- **用 `session_id` 查询后台结果**：这是当前 bug 的来源，会触发 continuation。
- **新增 `background_output`**：增加一套查询语义，偏离以 `output_file` 为中心的目标。
- **subagent 和 bash 分别做后台系统**：重复状态机、停止、通知、恢复逻辑。
- **只靠 LLM_PROXY 日志找结果**：日志不是产品状态，不可作为用户交互链路。
- **后台完成后只发 SSE 不唤醒主 agent**：用户无新输入时主 agent不会继续工作，不满足核心体验。

## 16. 测试策略

单元测试：

- ID 生成格式。
- registry 状态转换和 terminal 状态不可覆盖。
- output append/flush/symlink fallback。
- notification XML 生成。
- `task_stop` 对 subagent/bash 的分派。
- tool schema description 包含后台语义。

集成测试：

- `Agent(run_in_background=true)` 立即返回，完成后 registry terminal + notification queued。
- `Agent(run_in_background=false)` 超过 120 秒转后台。
- `bash(run_in_background=true)` 立即返回，stdout/stderr 写入 output file。
- foreground bash 超过 15 秒转后台。
- `task_stop` 停止后台 bash 进程树。
- `task_stop` 停止后台 subagent。
- 父会话 idle 时 notification 自动创建 main run。
- 父会话 active 时 notification 排队，run 结束后再处理。
- 用户 prompt 与 task notification 同时排队时，用户 prompt 优先。

E2E：

- 用户：“开个 subagent 在后台研究核心 loop，然后读 README。”
- 用户：“后台跑 pytest，然后继续检查 README。”
- 后台完成时用户不输入任何内容，主 agent 自动恢复并继续。
- 读取 `output_file` 能看到 subagent JSONL 或 bash stdout/stderr。
