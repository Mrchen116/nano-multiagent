# M96 - IM Agent 配置 + 用户/设备绑定

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

- Milestone: M96 / IM Agent 配置 + 用户/设备绑定
- Branch: `milestone/M96`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M96`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M96 && PYTHONPATH=src pytest -q tests/im_service`
- Baseline:
  - Result: 24 passed
  - Notes:
    - 现有 IM 后端只有 users/conversations/messages/SSE 主链路。
    - `AgentProfile` / `NodeStatus` 仅存在于 domain model，尚未接入 SQLite/API。
    - 需要在不扩散到 M95/M97/M100 范围的前提下，补齐 M96 所需配置与绑定能力。

## R1 Agent 配置 API 与 profile_version 乐观锁
- Status: DONE
- Context: M94 只把 `AgentProfile` 放进了 domain model，SQLite / service / route 还没有对外提供 `GET /im/v1/agents`、`GET/PATCH /im/v1/agents/{id}/config`，也没有 `profile_version` 冲突检测闭环。
- Decision: 在 `src/IM/infra/db.py` 增加 `agent_profiles` 表；在 `src/IM/infra/repositories.py` 增加 `AgentProfileRepository` 与 `AgentProfileVersionConflictError`；新增 `src/IM/application/config_service.py` 和 `src/IM/api/routes/agents.py`，以 canonical 分层提供 Agent 列表、详情、PATCH 更新与 409 冲突语义。
- Rationale: 把 M96 的配置能力收敛在 IM canonical 结构内，避免把配置逻辑散落到现有 users/web_im 路由，符合 IM-SPEC §5 的 agents API 划分，也满足 prevention rule 的“单一 canonical 结构”。
- Evidence:
  - Tests:
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M96 && PYTHONPATH=src pytest -q tests/im_service`
    - `tests/im_service/integration/test_agent_config_api.py`
    - `tests/im_service/contract/test_agent_config_contract.py`
  - Entry:
    - `GET /im/v1/agents`
    - `GET /im/v1/agents/{agent_id}/config`
    - `PATCH /im/v1/agents/{agent_id}/config`
- Rollback: `git revert <M96-commit>`
- Commits: C1=, C2=, C3=
- Next: 与账户/绑定流程接线，并验证绑定后 Agent owner 自动归属。

## R2 GET/PATCH /im/v1/me 与 POST /im/v1/bind
- Status: DONE
- Context: 现有 IM 只有 `/im/v1/users` 的创建/列表入口，不符合 IM-SPEC §5 的 `me` 和 `bind` API，也没有设备绑定后 node/agent owner 归属回填。
- Decision: 在 schema 中加入 `nodes` 与 `bind_requests` 表；在 `src/IM/infra/repositories.py` 增加 `NodeRepository` / `BindRepository`；新增 `src/IM/application/bind_service.py` 与 `src/IM/api/routes/account.py`，实现 `GET/PATCH /im/v1/me` 以及 `POST /im/v1/bind` 的 start/confirm 流程。确认绑定时同步把 node owner 和该 node 下的 agent owner 归属到当前 user owner。
- Rationale: 绑定流程本质上是账户域能力，与 Agent 配置分开可保持 service/route 边界清晰；同时 owner 回填放在 bind service 中，避免 API 层散落跨仓储写操作。
- Evidence:
  - Tests:
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M96 && PYTHONPATH=src pytest -q tests/im_service`
    - `tests/im_service/integration/test_account_binding_api.py`
    - `tests/im_service/contract/test_account_binding_contract.py`
  - Entry:
    - `GET /im/v1/me?user_id=...`
    - `PATCH /im/v1/me?user_id=...`
    - `POST /im/v1/bind`
- Rollback: `git revert <M96-commit>`
- Commits: C1=, C2=, C3=
- Next: 验证配置变更仅影响新会话，并回查 canonical import/path 无并行实现漂移。

## R3 配置仅对新会话生效 + 收口复查
- Status: DONE
- Context: exit criteria 明确要求“配置变更仅对新会话生效”；现有 conversation 结构没有记录创建会话时采用的 profile version 快照。
- Decision: 给 `conversations` 表和 `Conversation` domain model 增加 `config_profile_version` 字段；`ConversationRepository.create_conversation()` 在建会话时根据参与者中的 Agent profile 记录当前 `profile_version` 快照，并保持既有会话行不被配置更新回写。同步把该字段暴露到 `ConversationResponse`，并补测试验证更新配置后旧会话仍保留旧版本、新会话拿到新版本。
- Rationale: 把“仅对新会话生效”固化为持久化快照，而不是临时运行期判断，语义更稳定，也便于后续 Gateway/Relay 层继续消费。
- Evidence:
  - Tests:
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M96 && PYTHONPATH=src pytest -q tests/im_service`
    - `tests/im_service/integration/test_agent_config_api.py::test_profile_updates_only_affect_new_conversations`
    - `tests/im_service/unit/test_repositories.py::test_agent_profile_roundtrip_and_optimistic_lock`
  - Entry:
    - `POST /im/v1/conversations` 返回 `config_profile_version`
- Rollback: `git revert <M96-commit>`
- Commits: C1=, C2=, C3=
- Next: 提交、合并本地 main、更新 dev board，并清理 M96 worktree。
