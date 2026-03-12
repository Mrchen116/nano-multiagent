# M131 Gateway 后台关闭命令

- Milestone: M131
- Title: Gateway 后台关闭命令
- Goal: 为默认后台启动的 Gateway 提供显式 stop 命令，让用户无需手工 kill pid，也不必依赖隐藏实现细节即可关闭当前后台 Gateway。
- Test Command: `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_main.py tests/e2e/test_personal_assistant_main_e2e.py`
- Scope: `src/personal_assistant/**`, `tests/unit/personal_assistant/**`, `tests/e2e/test_personal_assistant_main_e2e.py`, `README.md`, `docs/operator-runbook.md`, `TASKS/**`, `PROGRESS/**`
- Out of Scope: 手工修改 `data/dev-tasks.json`、无关产品/功能、大范围重构
- Notes:
  - 默认用户路径必须提供可发现的 stop 命令，不能把 `kill pid` 当成产品方案。
  - stop 必须覆盖成功关闭、未运行、状态陈旧/坏 pid，并给出可执行反馈。
  - README / runbook 的默认启动/停止文案必须与真实 CLI 一致，不能把 `--foreground` 调试路径写成默认路径。
  - 参考 LOGBOOK：本地入口异常优先确认真实占端口进程；默认用户链路必须经真实 CLI/e2e 入口验证。

## Roadpoints

### R1 停止契约与状态文件
- Status: TODO
- Acceptance:
  - 新增 stop 用户命令的单元/入口测试，先证明当前缺失能力。
  - 后台启动会写入与配置路径绑定的运行态元数据，供 stop 定位当前 Gateway。
  - stop 会按状态文件判断 running / not-running / stale pid，并输出清晰反馈。
  - 测试覆盖成功关闭、未运行、陈旧 pid 三种用户态结果。
- Tests Plan:
  - unit: 选。主覆盖 CLI 解析、状态文件读写、停止分支判定。
  - contract: 不单独建。通过 stdout/stderr 文案与状态文件字段断言覆盖用户契约。
  - integration: 选最小范围。验证 launch/stop 之间通过同一配置目录状态文件串联。
  - e2e: 暂不在本 Roadpoint 展开，留到 R2 用真实子进程验证。
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py::test_main_stop_command_*`
  - `tests/unit/personal_assistant/test_main.py::test_launch_gateway_in_background_*state*`
- DoD:
  - Red -> C1 -> Green/Refactor -> `test_command` 全绿 -> C2 -> TASKS/PROGRESS 更新 -> C3

### R2 真实 CLI 停止入口与文档
- Status: TODO
- Acceptance:
  - 真实 CLI 默认后台启动后，可用显式 stop 命令关闭同一配置对应的 Gateway。
  - stop 对成功关闭、未运行、陈旧状态给出可读反馈，且不要求用户记忆 pid。
  - README 与 `docs/operator-runbook.md` 写清默认启动/停止路径，并与真实 CLI 行为一致。
  - `test_command` 全绿。
- Tests Plan:
  - unit: 选。补充少量文案/分支防回归。
  - contract: 不单列。通过 CLI 输出文本与 exit code 契约断言。
  - integration: 选。真实子进程启动后 stop，验证 health 恢复为不可达。
  - e2e: 选。`subprocess` 跑真实 `python -m personal_assistant.main` 的 start/stop 主链路。
- Expected Tests:
  - `tests/e2e/test_personal_assistant_main_e2e.py::test_main_stop_command_stops_background_gateway`
  - `tests/e2e/test_personal_assistant_main_e2e.py::test_main_stop_command_handles_stale_state`
  - 文档无单独测试，靠门禁与人工对照。
- DoD:
  - Red -> C1 -> Green/Refactor -> `test_command` 全绿 -> C2 -> TASKS/PROGRESS 更新 -> C3
