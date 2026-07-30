# M219 fresh rerun 首条 relay websocket 重连卡死

## Milestone Context
- Milestone: M219 / 修复 fresh rerun 首条 relay 因 websocket 重连卡死
- Execution: serial
- Worktree: `true`
- Worktree dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M219`
- Branch: `milestone/M219`
- Test gate: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M219/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
- Allowed scope:
  - `src/personal_assistant/**`
  - `src/IM/**`
  - `scripts/acceptance/m170_runtime.py`
  - `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
  - `tests/**`
  - `TASKS/M219-*.md`
  - `PROGRESS/M219-*.md`
  - `LOGBOOK.md`
- Forbidden scope:
  - `data/dev-tasks.json`
  - `docs/**`
  - 其他 milestone 的 `TASKS/PROGRESS/ACCEPTANCE`
- Prevention notes:
  - 真实入口若与源码矛盾，先确认端口上运行的 checkout/进程，避免旧 worktree 干扰。
  - M170 rerun 只能使用 fresh rebuilt current-main runtime 与真实浏览器证据。
  - 当前问题不是“多等一会儿”，而是 fresh runtime 首条 turn 在 `relay.accepted` 后 websocket 断开，导致 receipt/lifecycle 丢失。
  - 优先修复 runtime/gateway 在 websocket 短暂断开后的 receipt/lifecycle 投递可靠性；不能只靠延长 sleep 掩盖。
- Baseline:
  - `test_command` 当前失败：`vitest: command not found`，属于前端依赖未安装的环境问题，不代表本 milestone 业务基线红；后续需在满足依赖后重跑门禁。

## Completion Summary
- R1 已用 gateway 单测锁定：发送期 websocket 断开时，旧实现会丢失 reconnect 窗口内的 lifecycle frame。
- R2 已以最小边界修复：`IMConnectionManager` 改为缓冲/重连后 flush，并在发送失败时主动关闭旧 socket；IM 集成测试确认 `relay.processing -> relay.report -> relay.completed -> message.delivered` 完整落库。
- R3 已以 fresh rebuilt canonical runtime + 真实浏览器证据确认：首条 alpha/beta 群聊 turn 均进入 completed，流程已稳定推进到 picker/no-reply 阶段；同时补齐 current-main picker 文案与 worktree 脚本路径的 acceptance 守卫。

## Roadpoints

### R1. 固化 websocket 短暂断连导致 relay 生命周期丢失的红测
- Status: DONE
- Acceptance:
  - 复现 gateway 侧在 `accepted` 后发送 `running/completed` 生命周期时遭遇 IM websocket 发送失败的场景。
  - 红测能证明仅靠当前 `send_json` 直发会丢失 `relay.processing` / `relay.report` / `relay.completed` / `message.delivered` 链。
  - 覆盖 callback 与连接管理边界，不把问题伪装成单纯 sleep/wait。
  - 明确断言重连后需要补投哪些 frame。
- Tests Plan:
  - unit: 是；在 `tests/unit/personal_assistant/` 覆盖 IMConnectionManager / relay lifecycle callback 的断连重连行为。
  - contract: 否；协议字段未变化，本里程碑聚焦可靠投递语义。
  - integration: 是；在 `tests/im_service/integration/` 覆盖 receipt/report 进入 IM 后的事件链完整性。
  - e2e: 否；R1 先锁定缺口，再在后续 roadpoint 做真实 runtime 复验。
- Expected Tests:
  - `tests/unit/personal_assistant/test_m102_gateway_im_connection.py::*reconnect*`
  - `tests/unit/personal_assistant/test_main.py::*relay_lifecycle*`
  - `tests/im_service/integration/test_gateway_websocket_api.py::*delivery_receipt*`
- DoD:
  - 红测稳定失败且指向当前缺失能力。
  - C1/C2/C3 齐全。
  - `test_command` 可运行后全绿。
  - `PROGRESS` 记录红测证据、方案与回滚点。

### R2. 最小修复 websocket 重连窗口内的 report/receipt 可靠补投
- Status: DONE
- Acceptance:
  - Gateway 在 websocket 短暂断连后，已生成的 relay lifecycle frame 不会因单次 `send_json` 抛错而永久丢失。
  - 首条 relay 至少能稳定补齐 `relay.processing` / `relay.report` / `relay.completed` / `message.delivered`。
  - 修复保持最小边界，只改允许范围内的 websocket/report/receipt 相关实现。
  - 不引入“假完成”或重复刷事件的副作用。
- Tests Plan:
  - unit: 是；验证排队、重连后 flush、失败时连接状态更新。
  - contract: 否；无新增外部 contract。
  - integration: 是；验证 IM persistence 路径收到补投后事件完整。
  - e2e: 否；真实 runtime 放到 R3。
- Expected Tests:
  - `tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/im_service/integration/test_gateway_websocket_api.py`
- DoD:
  - 修复后新增/既有相关测试全绿。
  - `test_command` 可运行后全绿。
  - `PROGRESS` 写清重连语义、为何不靠 sleep、以及回滚点。

### R3. fresh rebuilt M170 runtime 验证首条 group relay 不再卡死并记录证据
- Status: DONE
- Acceptance:
  - fresh rebuild 后的 canonical M170 runtime 首条 group message 不会停在 `relay.accepted` / `receipt sent`。
  - 对应 relay_task 稳定进入 `completed`，并写出 `relay.processing` / `relay.report` / `relay.completed` / `message.delivered`。
  - 真实 rerun 至少跑到 picker / no-reply 阶段。
  - 输出运行证据、产物路径、日志定位与结果摘要。
- Tests Plan:
  - unit: 否；R3 聚焦真实入口证据。
  - contract: 否。
  - integration: 是；如需补 acceptance 脚本的存储断言，保持最小联动。
  - e2e: 是；运行 `scripts/acceptance/m170_runtime.py` + `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`。
- Expected Tests:
  - `python3 /Users/czj/Repos/nano-multiagent/.worktrees/M219/scripts/acceptance/m170_runtime.py rebuild`
  - `python3 /Users/czj/Repos/nano-multiagent/.worktrees/M219/scripts/acceptance/m170_runtime.py start`
  - `python3 /Users/czj/Repos/nano-multiagent/.worktrees/M219/ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py`
- DoD:
  - runtime 证据落到 canonical `ACCEPTANCE/m170-runtime/`。
  - `test_command` 可运行后全绿。
  - `PROGRESS` 记录实跑结论、关键日志与回滚点。
