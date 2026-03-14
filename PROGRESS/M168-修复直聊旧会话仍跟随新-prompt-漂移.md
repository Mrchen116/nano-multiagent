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
- Status: TODO
- Notes:
  - 待补 repository / relay / API / E2E 聚焦断言，锁定真实 alias 参与者场景。

### R2 实现直聊冻结 snapshot 与 relay/event 证据对齐
- Status: TODO
- Notes:
  - 待实现 conversations 冻结快照持久化、relay snapshot 读取与 receipt event metadata 回填。

### R3 聚焦验证、留痕与提交收口
- Status: TODO
- Planned commands:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Commits:
  - C1=`<pending>` 任务拆解与留痕
  - C2=`<pending>` 红测 + 实现
  - C3=`<pending>` 验证与文档收口

## 当前结论
- 当前主线缺口不是单纯“旧会话 session key 漂移”，而是 alias-backed 直聊在 IM 持久化层没有拿到真正的 conversation-bound snapshot，后续 relay 只能回查最新 profile。
- 若按该根因修复，旧直聊、新直聊与 relay/event 证据应能同时稳定分叉到旧/新配置。
