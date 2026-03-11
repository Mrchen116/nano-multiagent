# Hook体系设计细化

## 1. 目标
- 为内核提供类似 `pi-mono` extension 的事件订阅能力：`on(event, handler)`。
- 覆盖 Agent 运行主链路关键节点（输入、回合、消息流、工具、压缩、异常、超时）。
- 允许开发者在一个 Hook 模块内使用闭包变量，实现跨事件状态共享与复杂逻辑编排。
- 默认非阻塞与异常隔离，不影响主流程稳定性。

## 2. Hook 模块编程模型

### 2.1 模块约定
- 每个 Hook 文件导出 `setup(hooks: HookAPI)`。
- 由 `platform/hooks/loader.py` 在启动时按四层来源扫描加载，`core/hooks/registry.py` 保存事件处理器映射。
- Hook 初始化一次后常驻进程；其闭包变量在进程生命周期内有效。
- 四层加载来源（优先级从低到高）：
  1. 内核内置：`src/agent/platform/hooks/builtins/`
  2. 产品默认：`src/agent/products/<product>/hooks/` + profile 筛选
  3. 用户全局：`<global_config_home>/hooks/`（如 `~/.nanocode/hooks/`）
  4. 工作区：`<workspace>/<workspace_config_dirname>/hooks/`（如 `<repo>/.nanocode/hooks/`）
- 同名事件下，高优先级层的 handler 后执行，便于本地覆盖内置行为。
- Hook 文件新增/修改/删除后默认需重启服务生效（首版不做运行时热重载）。

### 2.2 Handler 签名（建议）

```python
from typing import Any, Awaitable, Callable

HookHandler = Callable[[dict, "HookContext"], Awaitable[dict | None] | dict | None]

class HookAPI:
    def on(
        self,
        event: str,
        handler: HookHandler,
        *,
        priority: int = 100,
        timeout_ms: int = 1500,
    ) -> None: ...
```

- `priority`：数值越小越先执行；同优先级按注册顺序。
- `timeout_ms`：单 handler 超时保护。

### 2.3 目录示例

```text
# 第 1 层：内核内置
src/agent/platform/hooks/builtins/
├─ __init__.py
├─ base_guard.py
└─ default_status.py

# 第 2 层：产品默认（以 local_coding 为例）
src/agent/products/local_coding/hooks/
├─ bash_risk_gate.py
└─ realtime_stream.py

# 第 3 层：用户全局（以 nanocode 产品为例）
~/.nanocode/hooks/
└─ my_custom_guard.py

# 第 4 层：工作区
<workspace>/.nanocode/hooks/
└─ project_specific.py
```

- 任何符合命名约定的 `*.py` 文件都可作为 Hook 模块加载。
- 四层按序加载，每层内部按文件名升序，模块内按 `hooks.on()` 注册顺序。
- 同优先级下高层 Hook 后执行，便于本地覆盖内置行为。
- 若需要精确控制执行顺序，使用 `hooks.on(..., priority=...)` 参数。

## 3. 事件清单（首版）

| 事件名 | 阶段 | 类型 | 可返回结果 |
|---|---|---|---|
| `session_start` | 会话启动 | observe | 无 |
| `session_compact` | 压缩完成 | observe | 无 |
| `session_shutdown` | 会话关闭/进程退出 | observe | 无 |
| `input` | 输入进入内核后 | intercept | `continue/transform/handled` |
| `before_agent_start` | Agent Loop 前 | intercept | `append_message/override_system_prompt` |
| `agent_start` | Agent Loop 开始 | observe | 无 |
| `agent_end` | Agent Loop 结束 | observe | 无 |
| `turn_start` | 每轮开始 | observe | 无 |
| `turn_end` | 每轮结束 | observe | 无 |
| `message_start` | 消息开始 | observe | 无 |
| `message_update` | 流式消息增量 | observe | 无 |
| `message_end` | 消息结束 | observe | 无 |
| `tool_call` | 工具执行前 | intercept | `block/reason` |
| `tool_execution_start` | 工具执行开始 | observe | 无 |
| `tool_execution_update` | 工具执行增量 | observe | 无 |
| `tool_execution_end` | 工具执行结束 | observe | 无 |
| `tool_result` | 工具结果回写前 | intercept | `content/details/is_error` 重写 |
| `run_error` | 运行异常 | observe | 无 |
| `run_timeout` | 运行超时 | observe | 无 |
| `run_abort` | 用户中断 | observe | 无 |

## 4. 拦截型事件返回契约

### 4.1 `input`

```python
InputHookResult = (
    {"action": "continue"}
    | {"action": "transform", "text": str, "images": list | None}
    | {"action": "handled"}
)
```

- `transform`：链式生效，后续 Hook 看到的是已变换后的输入。
- `handled`：短路，主流程不再继续处理该输入。

### 4.2 `before_agent_start`

```python
BeforeAgentStartHookResult = {
    "message": {"custom_type": str, "content": str} | None,
    "system_prompt": str | None,
}
```

- `system_prompt`：链式覆盖，后执行 Hook 基于前者结果继续改写。

### 4.3 `tool_call`

```python
ToolCallHookResult = {"block": bool, "reason": str | None}
```

- 任一 Hook 返回 `block=True` 即短路，工具调用终止。

### 4.4 `tool_result`

```python
ToolResultHookResult = {
    "content": list | None,
    "details": Any,
    "is_error": bool | None,
}
```

- 多个 Hook 串行合并：后者可以继续覆盖前者产物。

## 5. 调度与合并规则
- `observe` 事件：执行所有已加载 handler；异常仅记录，不中断主流程。
- `intercept` 事件：按优先级串行执行并合并结果。
- 短路规则：
  - `input.handled` 立即停止后续 `input` handler。
  - `tool_call.block` 立即阻断工具执行。
- 超时规则：单 handler 超时视为失败，记录 `hook_timeout` 诊断。
- 审计日志：记录 `hook_id/event/duration_ms/status/error`。

## 6. 闭包共享状态（对齐 status-line 思路）

Hook 可以在 `setup()` 中定义闭包变量，供多个事件共享。

```python
def setup(hooks):
    # 进程内共享状态；按 session_id 隔离，避免串会话污染
    state_by_session: dict[str, dict] = {}

    def state(session_id: str) -> dict:
        return state_by_session.setdefault(session_id, {
            "turn_count": 0,
            "last_tool_error": None,
        })

    async def on_turn_start(event, ctx):
        s = state(ctx.session_id)
        s["turn_count"] += 1

    async def on_tool_result(event, ctx):
        s = state(ctx.session_id)
        if event.get("is_error"):
            s["last_tool_error"] = event.get("content")

    async def on_turn_end(event, ctx):
        s = state(ctx.session_id)
        if s["last_tool_error"]:
            ctx.logger.warn(f"turn={s['turn_count']} had tool error")

    hooks.on("turn_start", on_turn_start)
    hooks.on("tool_result", on_tool_result)
    hooks.on("turn_end", on_turn_end)
```

建议：
- 共享状态必须以 `session_id` 为 key。
- 高并发场景下若存在跨会话全局可变状态，需配锁（`asyncio.Lock`）。

## 7. 与现有内核模块集成点
- `agent.runtime.run()`
  - 触发：`input -> before_agent_start -> agent_start`
- `agent.loop`
  - 每轮触发：`turn_start -> message_* -> turn_end`
- `tools.registry.execute()`
  - 触发：`tool_call -> tool_execution_* -> tool_result`
- `agent.compaction`
  - 触发：`session_compact`
- 统一异常出口
  - 触发：`run_error/run_timeout/run_abort`

## 8. 失败策略（默认值）
- 默认 `on_error = isolate`：Hook 报错不影响主链路。
- 默认 `on_timeout = isolate`：超时仅记日志与诊断事件。
- 仅当 Hook 显式返回拦截结果时改变主流程行为。

## 9. 最小测试集
- 输入链路：`input transform` 能串联多个 Hook。
- 阻断链路：`tool_call block` 能阻断执行并返回原因。
- 改写链路：`tool_result` 可重写 `content/details/is_error`。
- 稳定性：Hook 报错与超时不会让 Agent Loop 崩溃。
- 闭包：单 Hook 文件内多事件共享变量可稳定工作。

## 10. 只读查询接口
- `GET /v1/hooks/events`
  - 返回：事件清单、事件类型（observe/intercept）、返回值契约摘要。
- `GET /v1/hooks`
  - 返回：当前加载 Hook 列表（模块名、路径、来源 `source=builtin|workspace`、订阅事件、priority、timeout_ms）。
- 说明：仅查询，不支持注册/更新/卸载；Hook 管理通过四层来源目录（内核内置 → 产品默认 → 用户全局 → 工作区）+ 重启生效。`source` 字段标识来源层（`builtin` / `product` / `global` / `workspace`）。
