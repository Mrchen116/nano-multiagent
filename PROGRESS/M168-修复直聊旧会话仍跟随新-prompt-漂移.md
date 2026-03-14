# M168 Progress — 修复直聊旧会话仍跟随新 prompt 漂移

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M168`
- 已确认 branch：`milestone/M168`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 已确认真实失败证据：旧直聊会话在 Agent prompt/profile 更新后继续收到新 token，新直聊收到新 token 则符合预期。

## 初始根因判断
- `ConversationRepository.create_conversation()` 当前只把 `participant_ids` 直接拿去匹配 `agent_profiles.agent_id`，而真实 Web IM 直聊中的 agent participant 常是 `users.username = agent:<agent_id>` 的 alias user，导致旧直聊根本没有冻结 `config_profile_version`。
- `RelayService._resolve_agent_snapshot()` 即使知道会话级 profile_version，也仍直接读取最新 `agent_profiles.system_prompt`，因此旧直聊会在配置更新后拿到新 prompt。
- `conversation_events` 里的 relay receipt payload 没有携带 relay metadata，自动化与真实排障都不容易把 relay_tasks / events / 浏览器可见回复三方证据对齐。

## 执行策略
1. 先补 `TASKS/M168` / `PROGRESS/M168`，明确 Roadpoints、门禁与回滚边界。
2. 先补 alias-backed 直聊 snapshot 红测，再做最小实现。
3. 最后跑聚焦 IM 单测与集成回归，把验证命令、结果与 commits 写回 PROGRESS。

## 进度

### R1 锁定 alias 直聊 snapshot 漏洞的红测
- Status: DONE
- Decision:
  - 新增 alias-backed repository / relay / API / E2E 断言，直接覆盖真实 `agent:<id>` 参与者场景。
- Evidence:
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`

### R2 实现直聊冻结 snapshot 与 relay/event 证据对齐
- Status: DONE
- Decision:
  - 在 `conversations` 表新增 `config_agent_id` / `config_system_prompt`，创建直聊时与 `config_profile_version` 一起冻结。
  - repository 解析 participant 时同时识别真实 agent user id 与 `agent:<id>` alias user。
  - relay 直聊优先读取会话冻结快照；receipt events 回填 `agent_id`、`idempotency_key` 与 `relay_metadata`。
  - Gateway 复用旧 session 时刷新 reply_context，使旧会话后续回复仍绑定新的 relay task/idempotency_key。
- Evidence:
  - `src/IM/infra/db.py`
  - `src/IM/infra/repositories.py`
  - `src/IM/application/relay_service.py`
  - `src/IM/ws/gateway_handler.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`

### R3 聚焦验证、留痕与提交收口
- Status: DONE
- Tests:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/unit/personal_assistant/test_gateway_pipeline.py`
    - 结果：`27 passed in 0.58s`
- Verification notes:
  - `test_direct_conversation_with_agent_alias_freezes_prompt_snapshot` 锁定 alias 参与者创建时的 conversation-bound snapshot。
  - `test_direct_conversation_relay_keeps_old_snapshot_while_new_conversation_uses_updated_profile` 锁定旧直聊 relay metadata 冻结、新直聊走新配置。
  - `test_profile_updates_only_affect_new_conversations` 与 `test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile` 一起覆盖 API / relay_tasks / conversation_events / 浏览器可见回复三方证据分叉。
  - `test_register_agent_keeps_existing_direct_sessions_and_uses_new_workspace_for_new_conversations` 额外锁定 Gateway 复用旧 session 时刷新 reply metadata 的行为。
- Commits:
  - C1=`f4aa713` `docs(M168): outline direct-chat prompt drift repair plan`
  - C2=`<pending>` 直聊 snapshot / relay / event / gateway 修复
  - C3=`<pending>` 文档状态与验证收口

## 当前结论
- 当前主线缺口已定位并修复：真实 alias-backed 直聊现在会在 IM 持久化层冻结 `config_agent_id` / `config_profile_version` / `config_system_prompt`，relay 不再为旧直聊回查最新 prompt。
- 旧直聊继续复用旧 kernel session，并在后续回复中带上最新 relay task / idempotency 证据；新直聊会创建新 kernel session 并命中新 workspace/title 与新 prompt。
- 自动化已同时证明 relay_tasks metadata、conversation_events receipt payload 与浏览器可见回复 metadata 在旧/新直聊分叉上保持一致，可作为 M149 重跑前的聚焦回归门禁。
