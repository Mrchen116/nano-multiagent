# M207 Progress — 修复 M103 browserless roundtrip 长跑卡住

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M207/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M207/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M206/PROGRESS/M206-修复真实群聊中的-NO_REPLY-前端静默泄漏.md`。
- 注释承诺：新增/修改 public API 继续遵守 Google 风格 docstring；注释只记录意图、边界、约束，不复述代码。
- 当前处境：M207，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M207`，branch=`milestone/M207`。
- 基线观察：`pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py` 卡在 `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless`，属于本 milestone scope。
- M206 传入 blocker：唯一剩余阻塞就是该 browserless roundtrip 长跑卡住，NO_REPLY 前端泄漏已与本问题解耦。

### R1. browserless hang 根因锁定与最小收口
- Context:
  - `test_web_im_message_roundtrip_browserless` 会在 `relay_adapter.accept_relay()` 之后长时间无输出；M206 已定位到它是唯一剩余阻塞。
  - 这份 M103 集成文件同时承载 gateway registration、group creation、mention/NO_REPLY、direct-chat config sync 等回归，不允许为了过门禁放宽 timeout 或删覆盖面。
- Decision:
  - 在 `tests/im_service/integration/test_m103_im_gateway_e2e.py` 新增红测，直接约束 `_FakeKernelClient.send_message_async()` 产出的 run snapshot 必须带 `status="completed"`。
  - 仅修复该文件内的 fake kernel client；不改生产 `InboundPipeline` 终态判定，也不改 kernel API contract。
  - 顺手把同文件另外两条会卡住的群聊用例改为显式发送 `node.delivery_receipt`，并从 IM `conversation_events` 验证 `relay.accepted/relay.completed`，使测试回到真实协议方向；将 late-stream conflict 用例纠正为真实 3 人 group 前提。
- Rationale:
  - `get_run` 的正式 contract 本就要求返回 `status`；这里是测试桩失真，不是生产逻辑需要容错放宽。
  - 群聊用例的真实协议是 gateway 主动上报 receipt/report，IM 不会平空向 gateway websocket 下推 `delivery_status` 帧；修正测试前提比改产品行为更小也更正确。
- Evidence:
  - Tests:
    - 红测：`pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py -k test_fake_kernel_client_send_message_async_seeds_terminal_run_snapshot` 先失败，`KeyError: 'status'`。
    - 目标用例：`pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py -k test_web_im_message_roundtrip_browserless` → `1 passed, 9 deselected in 0.61s`
    - 群聊高风险回归：
      - `pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py -k test_group_chat_uses_live_updated_profile_after_config_sync_in_same_conversation` → `1 passed, 9 deselected in 0.71s`
      - `pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py -k test_group_chat_keeps_no_reply_when_completed_snapshot_and_late_stream_delta_conflict` → `1 passed, 9 deselected in 0.64s`
    - 全文件：`pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py` → `10 passed in 0.97s`
    - 门禁：`pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py` → `17 passed in 0.83s`
  - Entry:
    - browserless roundtrip 现已稳定返回；gateway registration、canonical labels、group creation before bind、mention/NO_REPLY、direct-chat config sync 全部继续覆盖并通过。
- Rollback:
  - 若需重做，先回退到 `548be87`（仅红测），或直接回到 `9c7d0b8`（计划提交）。
- Commits: C1=`548be87`, C2=`2eb9406`, C3=<pending>
- Next:
  - 提交 TASKS/PROGRESS 文档收口，等待主 agent 决定是否继续整体 rebase/merge main。

