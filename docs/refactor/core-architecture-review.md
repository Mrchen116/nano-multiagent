# 内核架构审查

> 审查范围：`src/agent/core` + `src/agent/platform`，不含 IM 和 CodingCLI。
> 审查时间：2026-04-15

---

## 一、结构性问题

### 1. Sync/Async 人格分裂

整个系统基于 FastAPI（本质异步），但路由全是 `def`（同步），内部再用 `asyncio.run()` 调 hook 的 async 方法。

```python
# runtime.py —— 每次 hook dispatch 都创建一个新的 event loop
asyncio.run(self._hook_runner.dispatch_observe(event, payload, hook_ctx))
```

这个模式在 `AgentLoop._dispatch_observe` 和 `AgentRuntime._dispatch_observe` 里各出现 5+ 次。

后果：
- 永远不能从真正的 async 上下文调用（会崩）
- 每次都重建 event loop，性能差
- 看起来是 async 系统，实际上完全 sync

### 2. `session.metadata` 是无类型的领域模型

`session.metadata: dict[str, Any]` 里实际装着结构化的领域数据：

```python
# 散落在 runtime.py 各处的 string key 访问
session.metadata.get("workspace_root")
session.metadata.get("system_prompt")
session.metadata.get("skills")
session.metadata.get("tool_allowlist")
session.metadata.get("conversation_type")
session.metadata.get("participant_agent_ids")
```

这些是真正的领域字段，但没有类型约束，导致每处访问都伴随防御代码：

```python
if not isinstance(raw_workspace_root, str):
    raise ValueError(...)
if not isinstance(raw_skills, list):
    return self._loop.available_skills
if isinstance(system_prompt_override, str):
    ...
else:
    system_prompt_override = None
```

根本原因：把结构体塞进了 dict，所有消费方都要自行解析和防御。

### 3. `_dispatch_observe` / `_log_hook_diagnostics` 完全重复

`AgentLoop` 和 `AgentRuntime` 各自持有一份几乎一模一样的实现：

```python
# loop.py 和 runtime.py 里各有一份
def _dispatch_observe(self, event, payload, hook_ctx): ...
@staticmethod
def _log_hook_diagnostics(hook_ctx, *, event, diagnostics): ...
```

---

## 二、`AgentRuntime.run()` 过于臃肿

这个方法约 200 行，混合了多个阶段：

1. 从 `session.metadata` 解析 workspace_root、system_prompt、skills、tools
2. 两轮 hook intercept（`input` → `before_agent_start`）
3. 三处 `user_text` 非空验证（L151、L183、L196）
4. append user message → preflight compaction → 再取 history 排除那条消息
5. M246 multi-part expansion（inline 逻辑块，靠注释分隔）
6. execute_loop → 捕获 ModelError → compaction → retry（重复调用 `_execute_loop`，参数完全相同）

这些阶段没有方法边界，只靠注释分隔，改动风险高，读起来费力。

---

## 三、`_append_turn_events` 的三重循环

```python
for assistant_message in turn_result.messages:  # loop 1：从 messages.metadata 取 tool call
    ...
for tool_call in turn_result.tool_calls:         # loop 2：补漏 tool call
    ...
for tool_result in turn_result.tool_results:     # loop 3：补漏 tool result
    ...
```

使用 set 做 de-duplication 是因为同一份 tool call 信息同时存在于：
- `messages[].metadata["tool_calls"]`
- `turn_result.tool_calls`

根本原因：`TurnResult` 数据模型里同一件事存了两遍，上层因此需要对账逻辑。

---

## 四、其他问题

| 问题 | 位置 | 说明 |
|------|------|------|
| Hook 事件用裸字符串 | `loop.py`, `runtime.py` | `HookEventType` 枚举存在但未在调用侧使用 |
| 层间穿刺 | `session.py:628` | route 通过 `getattr(runtime, "_compaction_settings")` 访问私有字段 |
| `list_sessions` O(n×m) | `manager.py` | 每个 session 都做一次全量 event replay |
| `append_turn_message` 多一次读 | `manager.py:80` | 写入前先 `get_session()` 验证存在，等于每次写都做一次全量 replay |
| `del payload.message_id` | `session.py:463` | 字段定义后立刻被删，意图不明 |

---

## 优先级汇总

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 🔴 高 | Sync/async 人格分裂 | 架构上走不远，async 化改造很痛 |
| 🔴 高 | `session.metadata` 是无类型领域模型 | 所有使用方都有防御代码，易出 bug |
| 🟡 中 | `AgentRuntime.run()` 太胖 + hook dispatch 重复 | 可读性差，改动风险高 |
| 🟢 低 | 其他小问题 | 可逐步清理 |
