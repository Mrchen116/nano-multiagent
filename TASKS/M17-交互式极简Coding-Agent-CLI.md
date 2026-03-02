# TASKS (Milestone: M17)

- Test command: `pytest -q`
- Branch: `milestone/M17`

## [TODO] R17.1 会话级 `/compact` 与 `/tools` HTTP API
- Acceptance:
  - 新增 `POST /v1/sessions/{session_id}:compact`，可触发手动压缩并返回结构化结果。
  - 新增 `GET /v1/sessions/{session_id}/tools`，返回当前会话可用工具列表。
  - 两个端点都遵循统一鉴权与错误形状，未知会话返回 `session_not_found`。
  - 端点接入仅在 `server/routes/session.py`，不引入 provider/tool 语义改造。
- Tests Plan:
  - `unit`: 不选。该改动核心是 HTTP 路由契约与依赖注入，单测价值低于 contract/integration。
  - `contract`: 选。锁定新增端点响应字段与错误码语义。
  - `integration`: 选。覆盖 runtime/tool-registry 依赖注入到 session routes 的链路。
  - `e2e`: 选。真实 HTTP 调用验证 session 生命周期中的 `/tools` 与 `/compact`。
- Expected Tests:
  - `tests/contract/test_sessions_contract.py`（扩展）
  - `tests/integration/test_session_flow_integration.py`（扩展）
  - `tests/e2e/test_message_sync_e2e.py`（扩展）
- DoD:
  - 目标测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M17-*.md` 记录决策/证据/回滚点/哈希。
- Commits:
  - C1: <pending>
  - C2: <pending>
- Status: TODO

## [TODO] R17.2 CLI HTTP 客户端分层重构（`cli/main.py + cli/commands.py + cli/http_client.py`）
- Acceptance:
  - CLI 目录按目标形态落地：`main.py` 仅负责入口，`commands.py` 负责命令调度，`http_client.py` 负责 HTTP 调用。
  - CLI 代码不出现 `agent.runtime` 直连 import，所有动作通过 HTTP API。
  - `sdk/client.py` 做必要最小兼容转发，避免无关范围破坏。
  - 现有 CLI 非交互能力（health/create-session/send-message）可继续工作或被兼容层覆盖。
- Tests Plan:
  - `unit`: 选。覆盖 HTTP client 请求拼装与错误路径。
  - `contract`: 选。锁定 HTTP-only 边界与 CLI 模块依赖关系。
  - `integration`: 选。验证 CLI + ASGI app 的端到端调用。
  - `e2e`: 不选。本 Roadpoint 聚焦目录与模块边界，入口行为在 R17.3 通过 REPL e2e 覆盖。
- Expected Tests:
  - `tests/unit/test_cli_main.py`（重写/扩展）
  - `tests/unit/test_sdk_client.py`（迁移到新 client 语义）
  - `tests/contract/test_cli_http_only_contract.py`（扩展）
  - `tests/integration/test_cli_http_flow_integration.py`（扩展）
- DoD:
  - 目标测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M17-*.md` 记录决策/证据/回滚点/哈希。
- Commits:
  - C1: <pending>
  - C2: <pending>
- Status: TODO

## [TODO] R17.3 交互式 REPL 与会话命令（`/help /new /use /session /tools /compact /exit`）
- Acceptance:
  - CLI 默认启动进入持续提示符，支持普通文本多轮对话。
  - 支持命令：`/help /new /use <session_id> /session /tools /compact /exit`。
  - `/tools` 调用 `GET /v1/sessions/{session_id}/tools`；`/compact` 调用 `POST /v1/sessions/{session_id}:compact`。
  - 空输入可忽略，EOF 可退出，错误信息保持可读且不崩溃会话循环。
- Tests Plan:
  - `unit`: 选。覆盖命令解析与会话状态切换。
  - `contract`: 选。锁定 REPL 支持的命令集合与帮助文本关键字。
  - `integration`: 选。覆盖 REPL 对真实 HTTP 客户端的调用序列。
  - `e2e`: 选。用子进程喂 stdin，验证持续对话与命令行为。
- Expected Tests:
  - `tests/unit/test_cli_main.py`（扩展 REPL 单测）
  - `tests/contract/test_cli_http_only_contract.py`（命令集合契约扩展）
  - `tests/integration/test_cli_http_flow_integration.py`（REPL 集成）
  - `tests/e2e/test_minimal_flow.py` 或新增 `tests/e2e/test_cli_repl_e2e.py`
- DoD:
  - 目标测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M17-*.md` 记录决策/证据/回滚点/哈希。
- Commits:
  - C1: <pending>
  - C2: <pending>
- Status: TODO
