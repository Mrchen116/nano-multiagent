# M3: REPL Resume Loads and Prints Chat History

## 目标

`--resume sess_xxx` 启动 REPL 时，自动拉取最近 N 条消息并打印到终端，让用户立即回到上下文。

## Roadpoints

### RP1: 新增历史消息 API

**文件**: `src/agent/platform/http_api/routes/session.py`

- 新增 `GET /{session_id}/messages`
  - `limit: int = Query(default=20, ge=1, le=100)`
  - 调用 `session_service.list_entries(session_id)`
  - 过滤 `kind == "message"` 的 entries
  - 返回 `{"messages": [...]}`，每条含 `role`, `content`, `message_id`, `turn_id`, `created_at`

**验收**: curl 调用返回正确消息列表

### RP2: CLI client 封装

**文件**: `src/coding_cli/client.py`

- `ServerClient` 新增 `get_session_messages(session_id: str, limit: int = 20) -> dict[str, Any]`

**验收**: 单元测试验证 HTTP 调用和参数传递

### RP3: REPL resume 时打印历史

**文件**: `src/coding_cli/commands.py`

- `_run_repl()`: resume 模式下，进入输入循环前调用 `client.get_session_messages()`
- 打印格式：
  - user 前缀 `> `
  - assistant 前缀 `< `
  - 空内容跳过

**验收**:
- `--resume sess_xxx` 自动显示最近消息
- user/assistant 区分清晰
- 空 session 不报错
