# M151 Task — 修复真实群聊中 @Agent 路由与回执闭环

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 当前处境：M151 / 修复真实群聊中 @Agent 路由与回执闭环；`execution_mode=parallel`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M151`；branch=`milestone/M151`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
- 允许范围：`src/IM/**`、`tests/im_service/**`、`tests/unit/personal_assistant/**`、`TASKS/**`、`PROGRESS/**`
- 禁止范围：`data/dev-tasks.json`、新增 worktree、与 M151 无关的前端/CLI/core 改动
- Prevention rules:
  - 修复必须落在真实群聊 relay/source-of-truth 路径，不能靠浏览器 mock 或手工回填 frame 伪造闭环。
  - 既要锁定被点名 agent 命中，也要保住既有 `NO_REPLY` 静默和直聊/动态同步门禁。
  - 文档必须诚实记录已跑自动化证据与仍需主 agent 执行的真实浏览器复验。

## Roadpoints

### R1. 锁定群聊 @mention 解析与目标 agent 快照回归
- Status: DONE
- Acceptance:
  - 群聊 relay payload 从正文提取 `@agent-id` 时可清洗常见标点，不因 `@agent-a,` 这类真实输入漏配。
  - payload `agent_id` 与 `metadata.system_prompt/config_profile_version` 优先取被点名 agent，而不是首个参与者。
  - 无匹配 mention 时仍保持原回退策略，不扩大行为面。
- Tests Plan:
  - unit: 新增/收紧 relay service 回归，直接锁定 mention 解析与 payload 快照。
  - contract: 不新增；字段形状不变。
  - integration: 由 R2 覆盖真实 IM→Gateway 群聊 roundtrip。
  - e2e: 不在本 milestone 内重跑真实浏览器，仅在文档交接中给出复验入口。
- Expected Tests:
  - `tests/im_service/unit/test_relay_service.py::test_enqueue_message_relay_targets_the_mentioned_agent_in_group_chats`
- DoD:
  - 红测先失败并暴露真实标点 mention 缺口。
  - 最小修复后 unit 绿。
  - C1/C2/C3 齐全并记入 PROGRESS。

### R2. 验证真实群聊 roundtrip 命中被点名 agent 且不回退 NO_REPLY
- Status: DONE
- Acceptance:
  - 真实群聊 roundtrip 中，第一次 `@agent-a` 建立 Agent-A session，第二次 `@agent-b` 建立 Agent-B session。
  - relay frame 和 outbound metadata 保留 `conversation_type`、`mentioned_agent_ids`、`config_profile_version`、`system_prompt`。
  - 既有 `NO_REPLY` 群聊静默回归继续为绿。
  - 不破坏 M103 IM↔Gateway 直聊回归和 gateway targeted suite。
- Tests Plan:
  - unit: 复用 gateway targeted suite 做回归保护。
  - contract: 不新增；沿用现有 payload shape。
  - integration: 收紧 `test_m136_group_chat_flow.py` 断言真实 roundtrip。
  - e2e: 由主 agent 在真实浏览器验收中复跑。
- Expected Tests:
  - `tests/im_service/integration/test_m136_group_chat_flow.py::test_group_conversation_creation_and_explicit_agent_mentions_roundtrip`
  - `tests/im_service/integration/test_m136_group_chat_flow.py::test_group_message_with_mention_and_no_reply_token_stays_silent`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
- DoD:
  - targeted gate 全绿。
  - PROGRESS 记录实际失败根因、修复点与证据。
  - C1/C2/C3 齐全。

## 当前结果
- 代码提交已存在：`6dec70d` (`fix(M151): route group mentions to the addressed agent`)
- 本次补充并校正测试/文档，使之与真实当前行为一致并覆盖标点 mention 场景。
- 待完成：提交本次测试/文档收口，让分支恢复干净。

## 回滚点
- 若需要回滚，只需撤回：
  - `src/IM/application/relay_service.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `TASKS/M151-修复真实群聊中@Agent路由与回执闭环.md`
  - `PROGRESS/M151-修复真实群聊中@Agent路由与回执闭环.md`
