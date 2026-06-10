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
  - `listDiscoverableGroupParticipants`：直接从 `listAgentsRaw` 构建候选列表，`user_id` 优先用 `agent.user_id`，回退到 `agent:<agent_id>`
  - `createDirectConversation`、`createFreshDirectConversation`：删除 `ensureUser`，participants 只含 Actor refs，无 `participant_ids`
  - `createGroupConversation`：从 agents 列表构建参与者 Actor refs，删除 `loadUserMap`

## R5 — 最终清理；build 全绿

- 状态：DONE
- 证据：
  - `npm run test -- --run` 372 tests passed（含 R1 contract test GREEN）
  - `npm run build` 成功，无 TypeScript 错误（仅预有的 chunk size 警告）
  - `git grep '/im/v1/users' src/IM/frontend/src/features/chat/im-chat-api.ts` 无输出（确认源码已清理）

## 退出标准核验

| 标准 | 状态 |
|---|---|
| im-chat-api.ts 源码不含 `/im/v1/users` 调用 | 已满足 |
| loadUserMap 已删除；改用 conversation.participants | 已满足 |
| ensureBootstrap 不再调用 ensureUser | 已满足 |
| contract test 验证 im-chat-api.ts 不含 `/im/v1/users` | 已满足（GREEN） |
| `npm run test -- --run` 全绿 | 已满足（372 passed） |
| `npm run build` 全绿 | 已满足 |
