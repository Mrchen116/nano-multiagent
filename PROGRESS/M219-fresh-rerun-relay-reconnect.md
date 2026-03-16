# M219 fresh rerun 首条 relay websocket 重连卡死

## Notes
- 已阅读 `LOGBOOK.md`：优先确认真实端口上的运行 checkout；不要把 websocket 断连问题伪装成等待策略。
- 已阅读 `COMMENTING_GUIDE.md`：后续 public API/docstring 与注释只写契约/意图，不复述实现。
- 基线门禁 `test_command` 当前因前端环境缺少 `vitest` 失败，需在依赖可用后重跑作为最终门禁。

## Roadpoint Records

### R1 固化 websocket 短暂断连导致 relay 生命周期丢失的红测
- Context: fresh rebuilt M170 runtime 的首条群聊消息已写入 `messages`，但真实运行只停在 `relay.accepted/receipt sent`；根因要先在 gateway unit 层证明是 reconnect 窗口内的 lifecycle frame 丢失，而不是“多等一会儿”。
- Decision: 先在 `tests/unit/personal_assistant/test_m102_gateway_im_connection.py` 加入 send-failure 后的 buffered resend 红测，再在 `tests/unit/personal_assistant/test_main.py` 锁定 `connected=False` 时 completed/report callback 仍必须继续下发 frame。
- Rationale: 先把断连窗口拆成“连接管理器丢帧”和“上层 callback 过早 return”两个明确失败点，后续修复才能保持最小边界。
- Evidence:
  - Tests: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/personal_assistant/test_m102_gateway_im_connection.py /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/personal_assistant/test_main.py -k "reconnect or relay_lifecycle"`
  - Entry: 临时 stash acceptance 脚本修复后，`python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/test_m170_rerun_acceptance.py -k "pick_mention_candidate_matches_current_main_picker_copy"` 稳定先红，证明 R3 的 selector/worktree 守卫也确实指向当前缺口。
- Rollback: 9d551dd (`main` at milestone start)
- Commits: C1=42c9ab5 `test(R1.1): 锁定重连窗口内的 relay 生命周期丢失（先红）`, C2=e61f995 `fix(R1.1): 重连后补投 relay 生命周期帧（全绿）`, C3=未单独提交（本 milestone 历史在接手前已污染，文档统一在末尾补齐）
- Next: 用最小实现让 frame 在 reconnect 后可补投，并验证 IM 落库链条完整。

### R2 最小修复 websocket 重连窗口内的 report/receipt 可靠补投
- Context: 旧实现里 `send_json()` 直发 websocket；一旦发送期撞上短断连，frame 会直接丢失，而且旧 socket 仍可能卡在 `recv()`，导致 `run_forever()` 迟迟不重连，首条 turn 永远等不到 `relay.completed`。
- Decision: 在 `src/personal_assistant/ws/im_connection.py` 引入 pending frame 队列，`send_json()` 改为入队 + flush，`connect_once()` 成功后补 flush；发送失败时主动关闭当前 websocket。并在 `src/personal_assistant/main.py` 去掉 `not manager.connected` 的提前 return，让 reconnect 窗口内的 report/receipt 也能进入队列。
- Rationale: 问题本质是投递可靠性，不是等待预算；只有把 lifecycle frame 缓冲在 gateway 边界，才能既不伪造完成态，也不靠 sleep 掩盖时序问题。
- Evidence:
  - Tests: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/personal_assistant/test_m102_gateway_im_connection.py /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/personal_assistant/test_main.py -k "reconnect or relay_lifecycle"` 与 `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/im_service/integration/test_gateway_websocket_api.py -k "completed_relay_chain or delivery_receipt"` 全绿。
  - Entry: 集成测试 `test_gateway_websocket_persists_completed_relay_chain_from_report_and_receipt` 断言 IM 最终事件链为 `message.sent -> relay.accepted -> relay.processing -> relay.report -> relay.completed -> message.delivered`，且 `relay_tasks.status/receipt_status` 都为 `completed`。
- Rollback: 42c9ab5（R1 红测稳定点）
- Commits: C1=42c9ab5 `test(R1.1): 锁定重连窗口内的 relay 生命周期丢失（先红）`, C2=42e49b2 `fix(R2.1): 保障 websocket 重连后的 relay 完成链落库（全绿）`, C3=未单独提交（文档统一在末尾补齐）
- Next: 用 fresh rebuilt canonical runtime 做真实浏览器 rerun，确认首条 group turn 不再卡死，并把 acceptance 脚本 selector/path 漂移一起收口。

### R3 fresh rebuilt M170 runtime 验证首条 group relay 不再卡死并记录证据
- Context: 修复后首次 full rerun 已不再卡在首条 relay，但 acceptance 脚本仍受 current-main mention picker 文案与主仓绝对路径漂移影响；必须把真实 rerun 能推进到 picker/no-reply 的证据，与脚本守卫一起固定下来。
- Decision: 在 `tests/unit/test_m170_rerun_acceptance.py` 先红锁定“从当前 worktree 加载 acceptance 脚本 + picker option 文案拼接”为 `Agent M170 BetaAgent M170 Beta mention`，再更新 `ACCEPTANCE/m170-runtime/m170_rerun_acceptance.py` selector。真实入口证据继续以 canonical runtime 产物为准：`m170-rerun-result.json`、`m170-20260316-ui-observations.json`、相关截图/日志/SQLite。
- Rationale: 这是最小联动；不改产品代码，只修复 acceptance 脚本对 current-main DOM 文案与 worktree 路径的假设，让 rerun 证据可复验。
- Evidence:
  - Tests: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M219/tests/unit/test_m170_rerun_acceptance.py` 与 `cd /Users/czj/Repos/nano-multiagent/.worktrees/M219/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build` 全绿。
  - Entry: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-rerun-result.json` 记录 alpha/beta/picker/no-reply 四段真实浏览器结果：alpha 与 beta 的 `relay.status=completed`、`receipt_status=completed`，事件链都包含 `relay.processing/report/completed + message.delivered`；picker turn 也成功 completed，并枚举出 `Agent M170 Alpha/Beta` 两个候选。`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/m170-20260316-ui-observations.json` 进一步证明 mention picker 可见，`composer_value` 为 `@agent:`，`option_count=2`。
- Rollback: 42e49b2（R2 全绿实现点）
- Commits: C1=2036746 `test(R3): 锁定当前 picker 文案与复验脚本路径（先红）`, C2=3bb074d `fix(R3): 对齐当前 picker 文案并从 worktree 加载复验脚本（全绿）`, C3=待本次文档提交
- Next: 把 Roadpoint 状态、证据和可复用经验补到 TASKS/PROGRESS/LOGBOOK，然后处理 milestone 分支污染后的安全集成。
