# bugfix-402-M5 — Progress

## R1 — contract test: 禁止 /im/v1/users 重现

- 状态：DONE
- Commit：(C1 RED) 见 git log，在 `v2/legacy-isolation.test.ts` 新增 describe `"im-chat-api /im/v1/users contract"`，扫描 `features/chat/` 非测试源文件，`stripComments` 剥注释后检查无 `/im/v1/users` 字符串
- 证据：提交时 test RED（im-chat-api.ts 仍含 listUsersRaw 等调用）

## R2 — 删除 listUsersRaw、createUserRaw、ensureUser；迁移 ensureBootstrap

- 状态：DONE
- 变更：
  - 删除 `listUsersRaw`、`createUserRaw`、`ensureUser`
  - `ensureSelfUser` 改为从 auth store 读取，未认证时 throw
  - `ensureBootstrap` 改用 `peerAgentId` 直查 canonical conversation，不再创建 alias user

## R3 — 删除 loadUserMap；迁移所有使用方

- 状态：DONE
- 变更：
  - 删除 `loadUserMap`，新增 `EMPTY_USER_MAP = new Map<string, ImUser>()`
  - `listConversations`、`getConversation`、`sendMessage`、`resolveConversationSendNodeState` 全部改传 `EMPTY_USER_MAP`
  - `resolveConversationParticipants` 优先走 `conversation.participants` 路径，`EMPTY_USER_MAP` 传入不影响已有 participants 的会话

## R4 — 迁移 listDiscoverableAgents、listDiscoverableGroupParticipants、createDirectConversation

- 状态：DONE
- 变更：
  - `listDiscoverableAgents`：只用 `peerAgentId` 查 canonical conversation，删除用户目录查找
  - `listDiscoverableGroupParticipants`：直接从 `listAgentsRaw` 构建候选列表；IM spec 保证 `agent.user_id` 恒非空（`ensure_agent_user` 生产路径恒返回非 None），删除 `agent:<agent_id>` 虚拟 id 死代码，改为 `filter(user_id != null)`（data integrity guard）
  - `createGroupConversation`：删除 `agentsByFallbackId`，只保留 `agentsByUserId` 单一 lookup
  - `createDirectConversation`、`createFreshDirectConversation`：删除 `ensureUser`，participants 只含 Actor refs，无 `participant_ids`

- R4 补充修正（Reviewer 要求删除死代码回退）：
  - `config_service.py:ensure_agent_user` 源码确认：`Returns None only when no UserRepository was wired`（legacy unit test 变体），生产路径 `_users` 恒非空
  - 因此 `agent.user_id ?? "agent:<id>"` 是不可达死代码，违反设计决策 8
  - 修正：改用 `.filter((agent) => agent.user_id != null)` 过滤 + `agent.user_id as string`，不构造虚拟身份

## R5 — 最终清理；build 全绿

- 状态：DONE
- 证据：
  - `npm run test -- --run` 372 tests passed（含 R1 contract test GREEN）
  - `npm run build` 成功，无 TypeScript 错误（仅预有的 chunk size 警告）
  - `git grep '/im/v1/users' src/IM/frontend/src/features/chat/im-chat-api.ts` 无输出（确认源码已清理）

## Live 浏览器验证（隔离 e2e 栈）

- 环境：worktree 隔离，IM 端口 52756，Vite dev 端口 52757，无 Gateway
- 测试时间：2026-06-10
- 测试账号：nano / nano1234（新鲜 IM 实例）

| 步骤 | 结果 | /im/v1/users 调用 |
|---|---|---|
| 登录页打开 | 正常渲染 | — |
| POST /login + 跳转 /chat | 200，跳转成功 | 无 |
| /chat bootstrap（GET /conversations, POST /conversations） | 正常，POST 400（无 agent 注册，预期） | 无 |
| "+Group" 打开 Group chat modal | modal 正常，AGENTS 空列表（无 gateway） | 无 |
| 整个会话 console 错误 | 仅 WS 未配置 proxy 警告（预有问题，非 M5 引入）；无 /im/v1/users 404 | 无 |

截图存 `ACCEPTANCE/bugfix-402-M5/`：
- `m5-01-login.png`：登录页（1440x900）
- `m5-03-chat.png`：登录后 /chat（1440x900）
- `m5-05-chat-loaded.png`：/chat 加载后（1440x900）
- `m5-06-group-modal.png`：+Group modal（1440x900）

## 退出标准核验

| 标准 | 状态 |
|---|---|
| im-chat-api.ts 源码不含 `/im/v1/users` 调用 | 已满足 |
| loadUserMap 已删除；改用 conversation.participants | 已满足 |
| ensureBootstrap 不再调用 ensureUser | 已满足 |
| contract test 验证 im-chat-api.ts 不含 `/im/v1/users` | 已满足（GREEN） |
| `npm run test -- --run` 全绿 | 已满足（372 passed） |
| `npm run build` 全绿 | 已满足 |
| live 浏览器验证无 /im/v1/users 404 | 已满足（见上方截图+网络日志） |
| agent:<id> 死代码回退已删除 | 已满足（filter + agentsByUserId only） |

> Orchestrator note: 本节引用的 ACCEPTANCE/bugfix-402-M5/*.png 截图已按用户要求从仓库移除(ACCEPTANCE/ 为历史目录,不再新增),验收时点截图真实存在并经 reviewer 核验。
