# TASKS M245 — Gateway 生命周期管理：stop/restart 子命令与单实例保护

## Roadpoints

### R1 — restart 子命令 + 单实例保护 + PID file

**Acceptance**
1. `gateway.pid` 文件在前台 child 进程启动后写入，退出时（含异常）删除（try/finally）
2. `launch_gateway_in_background` 在启动前检查 `gateway.pid`，若进程存活则抛出明确错误（含 PID）
3. `main restart` = stop（忽略未运行错误）+ start，正常退出码 0
4. `main stop` 成功停止并删除 `gateway.pid`（兼容旧 `.gateway-state.json` 场景）
5. 现有 `main` 无参数启动行为不变（向后兼容）

**Tests Plan**
- unit：覆盖所有新 CLI 路径（`restart`、单实例拒绝、PID file 写入/删除）
- contract：不适用（无新协议字段）
- integration：不适用（现有启动链路单测已覆盖）
- e2e：不适用（scope 限于 unit）

**Expected Tests**（`tests/unit/personal_assistant/test_main.py`）
- `test_gateway_pid_file_written_on_start_and_removed_on_exit`
- `test_launch_background_refuses_if_pid_file_exists_and_process_alive`
- `test_launch_background_allows_start_if_pid_file_exists_but_process_dead`
- `test_main_restart_command_stops_then_starts`
- `test_main_restart_command_succeeds_when_not_running`
- `test_stop_gateway_removes_pid_file`

**DoD**
- `test_command` 全绿
- C1/C2/C3 提交齐全
- PROGRESS 补齐

**状态**: DONE

---

## 完成摘要

所有 R1 Roadpoints 完成。PID 文件管理、单实例保护、restart 子命令均已实现并通过测试。
