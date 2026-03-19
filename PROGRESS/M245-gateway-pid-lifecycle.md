# PROGRESS M245 — Gateway 生命周期管理：stop/restart 子命令与单实例保护

## 状态: DONE

## 设计决策

- PID 文件路径：`runtime_dir / "gateway.pid"`（runtime_dir = config.source_path.parent）
- `gateway.pid` 由前台子进程（`run_gateway` + `--foreground`）写入，退出时 try/finally 删除
- `launch_gateway_in_background` 启动前检查 `gateway.pid`：若存活则 raise `GatewayStartupError`（含 PID）；若已死进程则清理后继续
- `stop_gateway` 扩展：先尝试读 `gateway.pid`，停止后删除；已有 `.gateway-state.json` 路径保留
- `restart` 子命令：stop（忽略 NOT RUNNING 类错误）→ start（background）
- 向后兼容：无参数 = start，`--foreground` 保持不变

### R1.1

- Context: main.py 已有 stop 子命令与 .gateway-state.json 状态文件；缺少 gateway.pid、单实例保护、restart
- Decision: 新增 _gateway_pid_path()、write/remove/read PID 函数；run_gateway() 用 try/finally 管理 PID；launch_gateway_in_background() 在 spawn 前检查；main() 增加 restart 分支
- Rationale: PID file 是 Unix daemon 单实例保护的标准实践；最小改动避免架构漂移
- Evidence:
  - Tests: PYTHONPATH=src python -m pytest tests/unit/ -x -q 2>&1 | tail -20
  - Entry: python -m personal_assistant.main restart --config ...
- Rollback: 回退到 plan commit (0ce69ac)
- Commits: C1=7982049, C2=9d4ae9c, C3=TBD
- Evidence:
  - Tests: 596 passed, 0 failed (PYTHONPATH=src python -m pytest tests/unit/ -x -q)
  - Entry: 7 新增测试全绿，涵盖 PID file 写入/删除/单实例拒绝/stale 清理/restart/stop 删 PID
- Next: C3 文档提交 → rebase main → merge → 更新 dev-tasks.json → 清理 worktree
