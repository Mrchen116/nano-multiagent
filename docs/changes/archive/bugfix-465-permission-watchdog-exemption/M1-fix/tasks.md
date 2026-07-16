# bugfix-465-M1: permission-watchdog-exemption

## 目标

让 Gateway 的 idle 看门狗在 run 处于 `permission_request` 等待人工决策时完全暂停计时；`permission_resolved` 发出后恢复正常 idle 检测。确保用户离开、关闭 IM 页面后回来仍能继续审批，同时决策后的内部卡死仍被看门狗捕获。

## 退出标准

- `permission_request` 期间，即使超过默认 120 秒没有 `run_heartbeat` 或业务事件，run 也不被 reap。
- `permission_resolved` 后，若 run 再次失去活性，仍按 idle 超时判定 stalled 并 reap。
- 非权限等待的 run 保持原有看门狗行为，bugfix-417 不回归。
- 单元测试、contract 测试全绿，并通过真 IM + 真 Gateway 端到端验证。

## 测试策略

| 类型 | 覆盖点 | 方式 |
|---|---|---|
| 单元测试 | 权限等待豁免、恢复、无权限 stalls、post-decision stalls | `test_inbound_pipeline_permission_watchdog.py` |
| 契约测试 | 模块边界、SDK 行为未变 | `tests/contract/` |
| 真实入口 | 审批等待 125 秒后仍能 resolve 并继续执行 | `scripts/e2e-up.sh` + 临时 Python 脚本，走 IM WebSocket |

## Roadpoints

- [x] R1 — Verify/Red：写出能复现 bug 的单元测试，确认 `permission_request` 等待超过 idle 窗口会被误杀。
- [x] R2 — Green：在 `inbound_pipeline.py` 实现 `current_timeout` 切换逻辑，让测试转绿。
- [x] R3 — Browser/Entry QA：在真 IM + 真 Gateway 走通 125 秒等待 + 审批 + 工具执行。
- [x] R4 — Docs：回填 `fix.md`“修复/验证”段，写 `progress.md` 与 `tasks.md`。
