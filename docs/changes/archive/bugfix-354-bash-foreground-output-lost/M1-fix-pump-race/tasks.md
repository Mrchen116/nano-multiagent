# M1-fix-pump-race — tasks

## Roadpoints

- [x] R1: 写回归测试 — `test_shell_runner_output_ready_when_complete_callback_fires`,通过 `_SlowAppendOutput` 包装把竞态窗口拉到确定级,在 `on_complete` 内无 sleep 断言 output file 含命令输出
- [x] R2: 修 `_start_pump` 签名 — 返回 `threading.Thread`,`start()` 保存 stdout / stderr pump 句柄
- [x] R3: 在 `_monitor` 三条 callback 触发分支前统一 `_drain_pumps()` join — 正常退出 / `TimeoutExpired` / 通用 `Exception`,timeout 10s,超时不抛错只记 warning
- [x] R4: 回归测试套件全绿 — `test_platform_adapters.py` 15/15 + `test_bash_tool.py` 8/8

## Exit criteria(对齐 design.md Milestone 表)

- [x] `pytest tests/unit/agent/background_tasks/test_platform_adapters.py` 全绿,包含新增回归测试(无 sleep)
- [x] `pytest tests/unit/agent/tools/test_bash_tool.py` 全绿
- [x] 三条分支都 join pump 后再 callback;join 超时不抛错且记 warning
- [x] 回填 `fix.md` 的"修复"与"验证"章节
- [ ] reviewer 在 Gateway 模式下验证 `bash ls <有文件目录>` 返回文件列表(reviewer 阶段)
