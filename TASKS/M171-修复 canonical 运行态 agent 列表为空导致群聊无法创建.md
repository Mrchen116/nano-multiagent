# M171 Task — 修复 canonical 运行态 agent 列表为空导致群聊无法创建

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M171`
- 已确认 branch：`milestone/M171`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M141/ACCEPTANCE/M141-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/docs/需求.md`
  - `src/IM/api/routes/agents.py`
  - `src/IM/application/config_service.py`
  - `src/IM/infra/repositories.py`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `src/IM/ws/gateway_handler.py`

## 目标
修复 fresh canonical IM/Gateway runtime 下 `/im/v1/agents` 与浏览器群聊参与者来源不一致、导致 Create group chat 面板无可选参与者的问题，确保运行态只暴露当前 runtime 真正可选的 agent，并补齐回归测试与证据记录。

## 最终根因摘要
1. 旧实现的 `/im/v1/agents` 直接返回 profile 全量配置行，而不是“当前 runtime 真可选 agent”。
2. 浏览器群聊面板最终参与者来自 `listDiscoverableGroupParticipants()`：先读 `/im/v1/agents`，再创建/匹配 alias user（`agent:<agent_id>`），再从 `/im/v1/users` 派生参与者选项。
3. 单纯收紧 `/im/v1/agents` 的查询口径还不够；fresh runtime 中 Gateway `node.register` 只上报 node 在线与 `agents[]`，却没有把这些运行态 agent materialize 成 `agent_profiles` 记录，因此绑定完成后 `/im/v1/agents` 仍可能为空。
4. 所以 M171 的真正闭环修复需要两部分同时成立：
   - `/im/v1/agents` 只能返回已绑定、owner 匹配的 runtime-selectable agents
   - Gateway 注册时必须把广告出来的运行态 agent 同步为最小 profile 记录并绑定到当前 node

## Scope
- 收紧 `/im/v1/agents` 的来源，只返回当前 runtime 可选择的 agent。
- 在 Gateway `node.register` 路径 materialize 运行态 agent profiles。
- 补后端集成测试，覆盖：
  - 绑定且 owner 一致的 agent 会出现在 `/im/v1/agents`
  - 未绑定或 cross-owner 的 profile 不会出现在 `/im/v1/agents`
  - fresh gateway 注册 + bind 后，`/im/v1/agents` 会出现真实 selectable agents
- 补前端 helper 回归，锁定群聊参与者列表来自 runtime agents + alias user 派生链路。
- 更新 `TASKS/M171` 与 `PROGRESS/M171`。

## 非目标
- 不扩展新的 IM API 路由。
- 不改动无关 relay / mention / NO_REPLY 逻辑。
- 不修改 `data/dev-tasks.json`。

## Roadpoints

### R1. 固化 runtime-selectable agent 查询口径
- Status: DONE
- Acceptance:
  - `/im/v1/agents` 只返回当前 runtime 真正可选的 agent profile。
  - 过滤掉未绑定 node 的 profile，以及 owner 与当前 node owner 不一致的 profile。
  - 未绑定节点不会在 fresh runtime 中过早暴露 agent。
- DoD:
  - `AgentProfileRepository` / `ConfigService` / `agents.py` 完成最小改动闭环。

### R2. 让 fresh gateway 注册真实落地为可选 agent profiles
- Status: DONE
- Acceptance:
  - Gateway `node.register` 后会为广告的 agent ids materialize 最小 profile。
  - bind 完成后，这些 profiles 会被 reassign 到当前 owner，并出现在 `/im/v1/agents`。
- DoD:
  - `gateway_handler.py` 在注册路径内完成 runtime profile materialization。

### R3. 补回归门禁
- Status: DONE
- Acceptance:
  - 后端测试覆盖 selectable / unbound / cross-owner 三种状态。
  - 后端测试覆盖 fresh gateway 注册 + bind 后 `/im/v1/agents` 非空。
  - 前端 helper 测试覆盖运行态 agent 经过 alias user 派生为 group participants 的链路。
- DoD:
  - Python 与 Vitest 聚焦回归通过。

### R4. 记录证据与收口
- Status: DONE
- Acceptance:
  - PROGRESS 记录根因、修复点、验证结果、阻塞项与 merge readiness。
- DoD:
  - 可给出精确文件、精确测试、精确阻塞说明。

## 验证命令
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend install`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M171/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M171/tests/im_service/integration/test_m103_im_gateway_e2e.py`

## 当前结果
- runtime-selectable `/im/v1/agents` 查询口径已修复。
- Gateway 注册缺少 runtime agent profile materialization 的问题已修复。
- Python 与 Vitest 聚焦回归均通过。
- 本机真实浏览器复验尝试受到外部已有 IM 进程占用/争抢本地端口影响，未获得一轮完全独占、可重复的 localhost 浏览器证据；该阻塞已在 PROGRESS 如实记录。

## 提交计划
- C1: `fix(M171): materialize runtime-selectable agents for fresh group creation`
- C2: `docs(M171): record runtime-agent verification evidence`
