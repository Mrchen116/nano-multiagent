# M168 Task — 修复直聊旧会话仍跟随新 prompt 漂移

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M168`
- 已确认 branch：`milestone/M168`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 已确认失败事实：真实 M149 复验里，旧直聊会话在 Agent prompt/profile 更新后漂移到新配置；新直聊命中新配置是正确行为。
- 首轮阅读：
  - `src/IM/infra/repositories.py`
  - `src/IM/infra/db.py`
  - `src/IM/application/relay_service.py`
  - `src/IM/ws/gateway_handler.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`

## 目标
修复真实 Web IM 直聊链路中旧会话在 Agent prompt/profile 更新后仍吃到新配置的问题，确保已存在的直聊会话冻结原有 `config_profile_version` / prompt 快照，只有更新后新建的直聊会话使用新配置，并让 relay / conversation_events / 浏览器回复证据在自动化里保持一致。

## 根因假设
1. 直聊会话创建时的配置快照解析只按 `participant_ids` 直接匹配 `agent_profiles.agent_id`，无法识别真实 Web IM 中 `users.username = agent:<agent_id>` 的 agent-alias 参与者，所以很多真实直聊根本没有写入 `config_profile_version`。
2. relay 组包时即便读到了会话版本，也仍会回查 `agent_profiles` 的最新 `system_prompt`，导致旧直聊在 Agent 更新后 metadata 漂移。
3. `conversation_events` 当前不携带 relay metadata，真实复验很难把 relay_tasks 与事件流证据对齐到同一份快照。

## Scope
- 修复直聊会话创建时对 alias agent participant 的 snapshot 解析。
- 为直聊会话持久化冻结的 agent_id / profile_version / system_prompt snapshot。
- 修复 relay metadata 读取路径，使旧直聊命中会话冻结快照，新直聊命中新配置。
- 补充 conversation_events 中的 relay metadata 证据，便于与 relay_tasks / 浏览器回复对齐。
- 增加聚焦单测与集成回归，覆盖旧直聊冻结与新直聊更新语义。
- 更新 `TASKS/M168-*.md` 与 `PROGRESS/M168-*.md`，记录 Roadpoints、验证命令、结果与 commits。

## 非目标
- 不修改 `data/dev-tasks.json`。
- 不在本 milestone 内重做群聊配置策略。
- 不做无关 UI 改动或重新执行完整真实浏览器验收。

## Roadpoints

### R1. 锁定 alias 直聊 snapshot 漏洞的红测
- Status: TODO
- Acceptance:
  - alias-backed 直聊在创建时就能写入 `config_profile_version`。
  - Agent 更新后，旧直聊 relay metadata 继续保留旧 prompt/version；更新后新建直聊使用新 prompt/version。
- Tests Plan:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_m103_im_gateway_e2e.py -k "alias or snapshot or direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile or profile_updates_only_affect_new_conversations"`
- DoD:
  - 先有失败断言，再进入最小实现。

### R2. 实现直聊冻结 snapshot 与 relay/event 证据对齐
- Status: TODO
- Acceptance:
  - 直聊创建时写入冻结的 agent_id / profile_version / system_prompt。
  - relay metadata 对旧直聊使用冻结快照，对更新后新直聊使用新快照。
  - `conversation_events` 至少在 relay receipt 事件中携带同一份 relay metadata。
- Tests Plan:
  - 复跑 R1 命令，确认由红转绿。
- DoD:
  - 代码改动保持在 IM 侧 snapshot / relay / event 相关路径。

### R3. 聚焦验证、留痕与提交收口
- Status: TODO
- Acceptance:
  - 跑完 milestone 聚焦验证命令并记录结果。
  - 形成小步 TDD commits，PROGRESS 记录命令、结果、回滚点与结论。
  - worktree 清洁，可明确是否 ready to merge。
- Tests Plan:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_repositories.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/unit/test_relay_service.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M168/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- DoD:
  - 返回 exact files changed / exact test commands / commit hashes / clean 状态 / merge readiness。

## 回滚点
- 若需回滚本 milestone，只需撤回：
  - `src/IM/infra/db.py`
  - `src/IM/infra/repositories.py`
  - `src/IM/application/relay_service.py`
  - `src/IM/ws/gateway_handler.py`
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `TASKS/M168-修复直聊旧会话仍跟随新-prompt-漂移.md`
  - `PROGRESS/M168-修复直聊旧会话仍跟随新-prompt-漂移.md`
