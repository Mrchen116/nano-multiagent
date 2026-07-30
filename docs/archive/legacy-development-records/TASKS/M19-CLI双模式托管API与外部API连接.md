# TASKS (Milestone: M19)

- Test command: `pytest -q`
- Branch: `milestone/M19`

## [DONE] R19.1 CLI 运行模式与托管进程生命周期
- Acceptance:
  - CLI 新增 `--mode`，支持 `managed` 与 `remote` 两种模式（默认 `managed`）。
  - `managed` 模式下 CLI 启动时可自动拉起本地 API（uvicorn）并等待就绪后再执行命令/REPL。
  - CLI 退出时（正常退出、异常退出）均会回收 managed 子进程，避免孤儿进程。
  - 子进程启动失败、端口占用等失败路径有明确报错与下一步建议。
- Tests Plan:
  - `unit`: 选。覆盖模式解析、生命周期管理器（启动成功判定、清理、异常路径）。
  - `contract`: 不选。本 Roadpoint 不新增 HTTP 协议字段，仅新增 CLI 启动语义。
  - `integration`: 选。通过可替换进程工厂验证 CLI 对进程生命周期的编排。
  - `e2e`: 不选。先用 integration 覆盖启动编排，不引入真实外部进程依赖。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py` 或新增 CLI 生命周期 integration 文件
- DoD:
  - Red -> Green，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M19-*.md` 补齐证据、回滚点、提交哈希。
- Commits:
  - C1: `cb71da7`
  - C2: `c58db82`
  - C3: `7ef1b9f`
- Status: DONE

## [DONE] R19.2 remote 模式直连语义与 REPL 命令兼容
- Acceptance:
  - `remote` 模式仅连接既有 `--base-url`（或环境变量），不会启动本地服务。
  - 两模式下都可执行现有 REPL 命令：`/new /tools /compact /history`。
  - 单命令模式（`health/create-session/send-message`）在两模式下保持可用。
  - 缺失 remote 连接必需信息时给出明确报错和建议。
- Tests Plan:
  - `unit`: 选。覆盖 remote 模式下“不拉起进程”与参数校验。
  - `contract`: 选。更新 CLI 模式相关命令契约（参数与默认值）。
  - `integration`: 选。验证 REPL 命令在 managed/remote 路径都可走通。
  - `e2e`: 不选。已有 integration 可覆盖真实 HTTP 调用链。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - Red -> Green，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M19-*.md` 补齐证据、回滚点、提交哈希。
- Commits:
  - C1: `1de9b4c`
  - C2: `d875363`
  - C3: `9ce1fcb`
- Status: DONE

## [DONE] R19.3 连接诊断与可操作错误提示收口
- Acceptance:
  - 端口占用、托管启动失败、连接失败三类场景均输出可操作建议。
  - managed/remote 失败提示能区分“本地服务问题”与“远端不可达问题”。
  - README 补充双模式使用示例与故障排查建议。
  - 关键失败路径有 unit + integration 回归测试。
- Tests Plan:
  - `unit`: 选。覆盖错误分类与建议文案。
  - `contract`: 不选。本 Roadpoint 主要是交互提示与文档，不新增 API 契约。
  - `integration`: 选。覆盖 CLI 启动失败/连接失败链路。
  - `e2e`: 不选。与 integration 重叠高，控制测试成本。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `README.md` 示例检查（文档变更）
- DoD:
  - Red -> Green，且 `pytest -q` 全绿。
  - C1/C2/C3 提交齐全。
  - `PROGRESS/M19-*.md` 补齐证据、回滚点、提交哈希。
- Commits:
  - C1: `d71a7e3`
  - C2: `ba661ca`
  - C3: `eba6f1c`
- Status: DONE
