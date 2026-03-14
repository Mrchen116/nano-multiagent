# M171 Task — 修复 canonical 运行态 agent 列表为空导致群聊无法创建

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M171`
- 已确认 branch：`milestone/M171`
- 已确认约束：仅处理 M171；不修改其他 milestone；不改 `data/dev-tasks.json` 状态
- 已确认 `data/dev-tasks.json` 在 worktree 内为指向主仓同一份文件的 symlink：`/Users/czj/Repos/nano-multiagent/.worktrees/M171/data/dev-tasks.json -> /Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- 首轮阅读：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/api/routes/agents.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/application/config_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/ws/gateway_handler.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py`

## 目标
修复 canonical fresh runtime 中 gateway 刚注册但尚未 bind 的阶段，`GET /im/v1/agents` 被错误过滤成空数组，导致前端 `Create group chat` 面板拿不到真实 agent 候选、真实群聊创建被前置阻塞的问题。

## 明确问题
1. 当前 `list_runtime_selectable_profiles()` 要求 `nodes.owner_id != ''`，fresh runtime 在 bind 前天然不满足，导致刚注册的 runtime agent 全部被过滤掉。
2. 前端群聊候选 `listDiscoverableGroupParticipants()` 直接依赖 `/im/v1/agents`，因此 API 为空时面板里也没有真实可选参与者。
3. 现有集成测试只锁定“bind 后 agent 出现”，没有锁住“fresh runtime 未 bind 前 agent 也必须可见”的回归门禁。

## Scope
- 修正后端 runtime-selectable agent 的筛选逻辑，使 ownerless fresh runtime agent 可见。
- 保留已 bind runtime 的 owner 隔离语义，避免跨 owner 污染。
- 补齐 fresh runtime API / 群聊创建 / real-process 三层回归测试。
- 更新本 milestone 的 TASKS 与 PROGRESS。

## 非目标
- 不新增新的后端路由。
- 不改 `data/dev-tasks.json` 状态。
- 不修改其他 milestone 文档或状态。
- 不扩展与本缺陷无关的群聊 UX。

## Roadpoints

### R1. 修复 runtime selectable agent 筛选语义
- Status: DONE
- Acceptance:
  - fresh canonical runtime 中，node 已注册但未 bind 时，ownerless profile 仍可从 `/im/v1/agents` 返回。
  - node 已 bind 时，仅允许同 owner 或待重分配空 owner profile 出现。
  - stale cross-owner profile 在未 bind runtime 中仍被过滤。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py -q`
- DoD:
  - `src/IM/infra/repositories.py` 的筛选逻辑与注释更新到位。

### R2. 锁定 fresh runtime → group chat 可创建链路
- Status: DONE
- Acceptance:
  - gateway fresh register 后，`/im/v1/agents` 立即返回真实 agent。
  - 这些 agent 可作为群聊参与者来源，完成群聊会话创建。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py -q`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 集成层和前端层都能说明 Create group chat 面板有真实候选来源。

### R3. 提供 real-process fresh runtime 证据并完成收口
- Status: DONE
- Acceptance:
  - real HTTP/WS 入口证明 fresh runtime 的 `/im/v1/agents` 不为空。
  - real HTTP 入口可成功创建包含真实 agent alias 的 group conversation。
  - TASKS/PROGRESS 写明根因、验证命令、证据、回滚点、提交计划。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py -k "fresh_runtime_agents_list_and_group_creation_before_bind" -q`
- DoD:
  - milestone 可提交、可 merge main、可 push、可清理 worktree。

## 当前结果
- 已修复 `list_runtime_selectable_profiles()`：fresh unbound runtime 的 ownerless agent 现在会返回给 `/im/v1/agents`。
- 已新增 3 组回归：repository/API 筛选、gateway fresh runtime 群聊创建、real-process fresh runtime HTTP/WS 证据。
- 已验证前端群聊候选与 `Create group chat` 面板测试继续通过，说明浏览器侧可见真实候选的前置数据源已恢复。

## 回滚点
- 若需要回滚本 milestone，只需撤回：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/infra/repositories.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/TASKS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M171/PROGRESS/M171-修复 canonical 运行态 agent 列表为空导致群聊无法创建.md`

## 验证命令
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py -q`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/e2e/test_m112_real_process_roundtrip_e2e.py -k "fresh_runtime_agents_list_and_group_creation_before_bind" -q`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts`

## 提交计划
- C1: 代码 + 测试 + milestone 记录收口提交
- C2: merge `main` 后如需解决冲突，追加最小 merge/fix 提交
