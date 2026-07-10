# M1-fix tasks

范围:堵住 e2e 测试在 `tests/e2e/test_personal_assistant_main_e2e.py` 异常路径上泄漏 Gateway + kernel 子进程。

## Roadpoints

- [x] R1 — killpg 化 `_terminate_background_pid` + `stop_gateway` (commit `7b1b3758`)
- [x] R2 — `tests/e2e/conftest.py` session finalizer + 单元测试 (commit `71e60ceb`)
- [x] R3 — 验证 + 回填 `fix.md` 修复/验证段

## Out of scope

- 手工运行 `personal_assistant.main` 异常崩溃留子进程(见 spec Q2,留单独 issue)
- IM running 占位消息超时回收(已有 issue #22)
- `_parse_started_pid` 正则 drift 是顺手修的(否则验证不了 R1/R2),非本 unit 主修目标

## 预先存在的 e2e API drift(out of scope, 留 issue)

- `tests/e2e/test_personal_assistant_main_e2e.py::test_kernel_session_workspace_root_controls_runtime_pwd`
- `tests/e2e/test_personal_assistant_main_e2e.py::test_new_kernel_session_uses_its_own_workspace_root_after_workspace_change`

两个测试调 `create_app(auth_token=...)` 但 `agent.platform.http_api.app.create_app` 已经不再接受 `auth_token` 参数(API drift)。本 unit 不修,验证时已 deselect。
