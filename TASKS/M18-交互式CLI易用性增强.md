# TASKS (Milestone: M18)

- Test command: `pytest -q`
- Branch: `milestone/M18`

## [DONE] R18.1 `/history [n]` 最近会话消息视图
- Acceptance:
  - REPL 支持 `/history` 与 `/history <n>`，默认展示最近消息，`n` 控制条数。
  - 展示采用最简文本视图（按行输出 `role: content`），不要求复杂 UI。
  - 历史按 `session_id` 维护，切换会话后读取对应会话记录。
  - 无活跃会话/无历史/参数非法时，错误提示包含可执行建议。
- Tests Plan:
  - `unit`: 选。覆盖命令解析、历史窗口裁剪、会话切换历史隔离。
  - `contract`: 不选。本 Roadpoint 仅 CLI 本地交互语义，不新增 HTTP 契约。
  - `integration`: 选。对接 ASGI app 验证真实 REPL 路径下历史输出。
  - `e2e`: 不选。已有 integration 覆盖真实 HTTP 链路，先控制变更面。
- Expected Tests:
  - `tests/unit/test_cli_main.py`（新增 history 相关用例）
  - `tests/integration/test_cli_http_flow_integration.py`（新增 history 交互流）
- DoD:
  - 测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M18-*.md` 写明证据、回滚点、提交哈希。
- Commits:
  - C1: `b6ac8ae`
  - C2: `a82a5c9`
  - C3: `821d4a1`
- Status: DONE

## [DONE] R18.2 `/tools` 与 `/compact` 可读摘要 + 可操作错误提示
- Acceptance:
  - `/tools` 输出人类可读摘要（会话、工具数、工具条目）。
  - `/compact` 输出人类可读摘要（是否压缩、摘要/保留/丢弃关键信息）。
  - 命令错误（未知命令、参数错误、会话缺失、请求失败）均包含“下一步建议”。
  - 保持既有 HTTP 调用语义，不改后端 API 协议。
- Tests Plan:
  - `unit`: 选。覆盖格式化输出与错误提示文案。
  - `contract`: 选。更新 REPL 命令集合契约（纳入 `/history`）。
  - `integration`: 选。验证 `/tools` 与 `/compact` 摘要在真实 HTTP 链路可读。
  - `e2e`: 不选。本里程碑先用 integration 稳定关键交互路径。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - 测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M18-*.md` 写明证据、回滚点、提交哈希。
- Commits:
  - C1: `a5f39c2`
  - C2: `af90901`
  - C3: `0785333`
- Status: DONE

## [DONE] R18.3 交互鲁棒性收口（空输入、Ctrl-D、参数错误）
- Acceptance:
  - 空输入（空串或空白）被忽略，不触发网络调用。
  - Ctrl-D（EOF）可稳定退出并输出一致退出提示。
  - REPL 命令参数错误提示统一且可执行（如 `/use` 缺参、`/history` 非法参数）。
  - 关键交互路径 unit + integration 覆盖补齐。
- Tests Plan:
  - `unit`: 选。覆盖 EOF、空输入忽略、参数错误路径。
  - `contract`: 不选。无新增外部契约。
  - `integration`: 选。覆盖 REPL 端到端交互链路中的鲁棒性场景。
  - `e2e`: 不选。与 integration 重叠高，先维持测试成本。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - 测试先红后绿，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M18-*.md` 写明证据、回滚点、提交哈希。
- Commits:
  - C1: `1d9305d`
  - C2: `2baa35b`
  - C3: `<pending>`
- Status: DONE
