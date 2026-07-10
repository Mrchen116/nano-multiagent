# bugfix-402-M5: actor-first-web-im — Tasks

> 对齐: ../design.md v1 (决策 8)

## 目标

从 `im-chat-api.ts` 中删除所有 `/im/v1/users` 调用及其 alias bootstrap 逻辑（`listUsersRaw`、`createUserRaw`、`ensureUser`、`loadUserMap`），将身份解析切换到三个 Actor-first 数据源：auth store（自身身份）、`/im/v1/agents`（候选 Agent）、`conversation.participants`（会话参与者），并增加源码级 contract test 禁止 `/im/v1/users` 重现。

## 退出标准

- [x] `im-chat-api.ts` 源码不含 `/im/v1/users` 调用（`listUsersRaw`、`createUserRaw`、`ensureUser`、alias bootstrap 已全部删除）
- [x] `loadUserMap` 已删除；使用 `conversation.participants` 作为参与者解析来源
- [x] `ensureBootstrap` 不再调用 `ensureUser` 创建 alias 用户
- [x] 新增 contract test 验证 im-chat-api.ts 不含 `/im/v1/users` 字符串
- [x] `npm run test -- --run` 全绿
- [x] `npm run build` 全绿

## 测试策略

- 被测行为（来自退出标准）：
  1. im-chat-api.ts 源码不含 `/im/v1/users`（contract test 覆盖）
  2. bootstrap、listConversations、createDirectConversation、createGroupConversation、
     listDiscoverableAgents、listDiscoverableGroupParticipants 等不再调用 users 端点
  3. 参与者 display name 来自 conversation.participants，而非全局用户目录

- 已有测试在：
  - `src/features/chat/im-chat-api.test.ts`（扩展：修改 mock 去掉 `/im/v1/users`，删除已过期断言）
  - `src/features/chat/v2/legacy-isolation.test.ts`（已有隔离 guard，属于 v2；需扩展覆盖 im-chat-api.ts 本身）

- 落层/目录/marker：`src/features/chat/v2/legacy-isolation.test.ts`（前端 contract），不需要 e2e marker
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（浏览器验收在 progress.md 记录）

用户路径分类：`bug-regression`（历史 bug 修复，`/im/v1/users` 已被后端删除，前端调用会 404）

UI 状态矩阵（受影响的页面状态）：

| 状态 | 覆盖计划 |
|---|---|
| default | contract test 保证不调用 /users |
| loading | N/A（非视觉变化） |
| empty | N/A |
| error | N/A（删除 ensureUser 的 fallback，错误大声失败） |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | N/A |
| missing/nullable data | 参与者 display_name 缺失时 fallback 逻辑保留 |
| mobile viewport | N/A（非视觉变化） |
| desktop viewport | N/A（非视觉变化） |
| dark mode（如项目支持） | N/A |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| im-chat-api.ts 引入新的 /im/v1/users 调用 | contract test 扫描源码 | 是 |
| bootstrap 在删除 ensureUser 后出错 | 现有 im-chat-api.test.ts 修改 mock 验证 | 是 |
| listDiscoverableGroupParticipants 改用 agents 后 build 报错 | npm run build 验证 | 是 |

## Roadpoints

### R1 — contract test: 禁止 /im/v1/users 重现

- 步骤：在 `src/features/chat/v2/legacy-isolation.test.ts` 扩展，新增一个 test case 扫描整个 `features/chat/` 目录（排除 test 文件和注释），验证 `im-chat-api.ts` 的实现源码不含 `/im/v1/users` 路径字符串
- 验证：此 test 当前应当 RED（因为 im-chat-api.ts 仍含 `/im/v1/users`）

状态：DONE

### R2 — 删除 listUsersRaw、createUserRaw、ensureUser；迁移 ensureBootstrap 和 ensureSelfUser

- 步骤：
  1. 删除 `listUsersRaw`、`createUserRaw`、`ensureUser` 函数
  2. `ensureSelfUser` 去掉 legacy fallback（直接用 auth store，session 缺失则 throw）
  3. `ensureBootstrap` 不再调用 `ensureUser` 创建 starterPeer；`starterConversation` 直接用 `pickCanonicalDirectConversation`（用 `peerAgentId`），不找不到时用 `createConversationRaw`（只含 Actor participants，不含 `participant_ids`）
  4. 删除 `buildLegacyParticipantIds` 或清空其 `participant_ids` 用法（保留函数仅供未迁移处暂用）
- 验证：R1 的 contract test 仍 RED；`npm run test -- --run` 其余 test 全绿

状态：DONE

### R3 — 删除 loadUserMap；迁移所有使用方

- 步骤：
  1. 删除 `loadUserMap` 函数
  2. 所有之前传入 `userById` 的地方改用空 Map；`resolveConversationParticipants` 已有从 `conversation.participants` 解析的分支，participants 非空时会优先走那条路
  3. `listConversations`、`getConversation`、`sendMessage`、`resolveConversationSendNodeState`、`pickCanonicalDirectConversation` 等不再 await `loadUserMap()`
- 验证：R1 contract test 仍 RED（因为 `listUsersRaw` 函数声明还存在，但实际调用已无）；其余 test 全绿

状态：DONE

### R4 — 迁移 listDiscoverableAgents、listDiscoverableGroupParticipants、createDirectConversation、createFreshDirectConversation、createGroupConversation

- 步骤：
  1. `listDiscoverableAgents`：删除 `listUsersRaw`、`usersByUsername` 查找；仅用 `pickCanonicalDirectConversation`（peerAgentId 直查）
  2. `listDiscoverableGroupParticipants`：改用 `listAgentsRaw` 直接返回 agent 列表作为选项，不再 `ensureUser` 再 `listUsersRaw`；group 参与者选项从 agents 构建
  3. `createDirectConversation`：删除 `ensureUser`、`loadUserMap`；只用 Actor participants（无 `participant_ids`），先查 canonical conversation（peerAgentId），不存在则创建
  4. `createFreshDirectConversation`：同上，删除 `ensureUser`
  5. `createGroupConversation`：删除 `loadUserMap`；title 用参与者 agent display name 生成；participants 从 agents 列表构建 Actor refs
- 验证：`npm run test -- --run` 全绿；R1 contract test 此时应 GREEN

状态：DONE

### R5 — 最终清理：删除残余 ImUser、alias 相关代码；确认 build 全绿

- 步骤：
  1. 删除 `ImUser` interface（或保留用于 `toActorFromUser` 的局部使用）
  2. 删除 `isAgentUsername`、`toActorFromUser`（若已无其他用处）
  3. 删除 `SELF_USERNAME`、`PEER_USERNAME` 等 alias 常量（若已无引用）
  4. `npm run build` 确认无 TypeScript 类型错误
  5. `npm run test -- --run` 全绿
- 验证：contract test GREEN；build 成功；371 tests + 新 contract test 全绿

状态：DONE
