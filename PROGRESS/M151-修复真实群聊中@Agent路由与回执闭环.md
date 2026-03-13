# M151 Progress — 修复真实群聊中 @Agent 路由与回执闭环

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M151/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M151/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 注释承诺：新增/修改 public API 继续遵守 Google 风格 docstring；注释只记录意图、边界、约束，不复述代码。
- 当前处境：M151，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M151`，branch=`milestone/M151`。
- 基线观察：现有分支已包含 `fix(M151): route group mentions to the addressed agent`，但测试与 milestone 文档仍缺收口；并且真实浏览器输入常见的 `@agent,` 标点场景尚未被回归锁定。

### R1. 锁定群聊 @mention 解析与目标 agent 快照回归
- Context:
  - 真实群聊输入并不总是裸 `@agent-a`，常见形式是 `@agent-a,` 或句尾带标点；若解析不清洗标点，relay payload 仍会错过 mention 命中并回退到首个参与者。
  - M151 的正确修复点在 IM relay payload 构造层，而不是 gateway/browser 侧兜底。
- Decision:
  - 保留 `src/IM/application/relay_service.py` 中已落地的 `_extract_mentioned_agent_ids()` 与按 `mentioned_agent_ids` 优先选 agent 的逻辑。
  - 把 relay unit test 收紧到真实标点 mention 文本，锁定 `agent_id/system_prompt/config_profile_version` 都来自被点名 agent。
- Rationale:
  - 用 punctuation case 锁住真实输入比继续用理想化空格分词更可靠，也能直接证明当前实现修复了已知根因。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py::test_enqueue_message_relay_targets_the_mentioned_agent_in_group_chats`
    - 结果：`1 passed`
  - Entry:
    - `tests/im_service/unit/test_relay_service.py` 现在用 `@agent-b, please reply in thread`，并断言 payload 快照到 `agent-b`。
- Rollback:
  - 若需重做，回退到 `6dec70d` 前的稳定点，或只撤回 unit test tightening 与 mention parser 改动。
- Commits: C1=`<pending>`, C2=`6dec70d`, C3=`<pending>`
- Next:
  - 继续校正 integration/documentation，使其与真实当前行为一致，并跑完 targeted gate。

### R2. 验证真实群聊 roundtrip 命中被点名 agent 且不回退 NO_REPLY
- Context:
  - 现有 integration 文本断言与真实修复后的系统行为不一致：它错误要求两次 session 都落到 `Agent-B`，实际上第一次 `@agent-a` 应命中 Agent-A，第二次 `@agent-b` 才命中 Agent-B。
  - Fake kernel client 也未记录真实 gateway 传入的 session metadata，导致无法断言 profile snapshot 是否随 relay 正确传递。
- Decision:
  - 更新 `tests/im_service/integration/test_m136_group_chat_flow.py`：
    - fake kernel client 记录 `metadata`；
    - roundtrip 文本改为带标点 mention；
    - 明确断言第一次命中 Agent-A、第二次命中 Agent-B；
    - 断言 relay frame / outbound metadata 都携带 `conversation_type`、`mentioned_agent_ids`、`config_profile_version`、`system_prompt`；
    - 保持 `NO_REPLY` 群聊静默回归不变并复跑。
- Rationale:
  - M151 不是把所有会话钉到同一个 agent，而是“每次显式 mention 都命中被点名 agent”；测试应直接表达这一点。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/im_service/integration/test_m136_group_chat_flow.py::test_group_conversation_creation_and_explicit_agent_mentions_roundtrip`
    - `PYTHONPATH=src pytest -q tests/im_service/integration/test_m136_group_chat_flow.py::test_group_message_with_mention_and_no_reply_token_stays_silent`
    - `PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py`
    - `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py`
    - `PYTHONPATH=src pytest -q tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - Entry:
    - roundtrip 回归已可证明两次真实群聊消息分别建立 `Agent-A` / `Agent-B` session，且 `NO_REPLY` 静默边界未回退。
- Rollback:
  - 若需重做，可回退到 `6dec70d` 并重新编写 integration 断言；生产修复无需回退。
- Commits: C1=`<pending>`, C2=`6dec70d`, C3=`<pending>`
- Next:
  - 提交测试与文档收口，确认 milestone 分支恢复 clean，再交还主 agent 做真实浏览器复验。

## Merge-readiness note
- 自动化层面：当前 targeted suites 已覆盖群聊 @mention 路由、group `NO_REPLY` 静默、gateway targeted regressions 与 IM↔Gateway 直聊回归。
- 未完成项：真实浏览器 / 真实在线 acceptance 仍需主 agent 在 M141 复验；本 worker 不做 merge 到 `main`。
