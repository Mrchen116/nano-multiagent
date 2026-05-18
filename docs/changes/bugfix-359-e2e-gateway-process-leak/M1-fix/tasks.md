# M1-fix tasks

范围:堵住 e2e 测试在 `tests/e2e/test_personal_assistant_main_e2e.py` 异常路径上泄漏 Gateway + kernel 子进程。

## Roadpoints

- [ ] R1 — killpg 化 `_terminate_background_pid` + `stop_gateway` (主仓改 1 helper + 1 函数)
- [ ] R2 — `tests/e2e/conftest.py` session finalizer + 单元测试
- [ ] R3 — 验证 + 回填 `fix.md` 修复/验证段

## Out of scope

- 手工运行 `personal_assistant.main` 异常崩溃留子进程(见 spec Q2,留单独 issue)
- IM running 占位消息超时回收(已有 issue #22)
