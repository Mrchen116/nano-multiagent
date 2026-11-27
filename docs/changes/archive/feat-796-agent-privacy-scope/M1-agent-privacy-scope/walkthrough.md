# M1-agent-privacy-scope: 实施与验证记录

## 变更概览

围绕 [spec.md](../spec.md) 与通过 Gate 2 独立审查的 [design.md](../design.md)，端到端落地了普通/全局 Agent 与个人助手（PA）的两档可见性（`team` = 「团队公开」默认、`owner_only` = 「私有（仅自己与名下助手）」）与双向通信权限隔离：

1. **共享入站分类契约（`packages/product-contracts`）**：
   - 在 [collaboration.ts](../../../../packages/product-contracts/src/collaboration.ts) 为 `ChatAddress` 扩展独立的 `ownerInternal` 与 `ownerObserved` 布尔位，严格保持 `ownerDirect` 仅代表真人主人 1:1 直聊 / 飞书绑定主人单聊，使 `owner_only` 助手既能正常接收同主人 `agent-agent` 私聊与私密专属群（保留普通群消息 10 分钟合并且不劫持 `SingleThread` 心跳主会话），又能让私有 PA 保留 `observer` 静默旁观。
2. **中心 IM 权限谓词、跨空间协同、群互斥与切换收口（`apps/im-server`）**：
   - 在 [identity.ts](../../../../apps/im-server/src/identity.ts) 与 [collaboration.ts](../../../../apps/im-server/src/collaboration.ts) 实现 `canTeamContactAgent`、`canViewAgentWork`、`isOwnerInternalConversation`、`canAgentAccessConversation` 与 `applyCollaborationScopeTransitionInTx`；
   - 修复启用个人空间的有效团队成员名下 `team` 普通/全局 Agent 在同事目录、斜杠命令、公司空间对话、全局 Work 与原生轨迹（含 [trajectory.ts](../../../../apps/im-server/src/trajectory.ts) 实时 WS `1008` 失权踢出）的跨空间可用性，同时对他人彻底隐藏 `owner_only` 助手与私有 PA；
   - 支持 `POST /im/v1/personal-agent` 创建时直接指定 `collaboration_scope` 并随 `request_key` 幂等恢复（冲突档位返回 `409`）；
   - 实现含私有助手群聊的私密锁定与成员互斥（`409 private_agent_in_group` / `409 private_agent_group_external_members`）、`team -> owner_only` 自动退外人群与清理关注/在途气泡/待决审批、同事历史 1:1 私聊 `write_blocked_reason: "agent_private"` 只读冻结（保留个人 `is_pinned` / `is_muted` 与会话移除，切回 `team` 自动恢复）、以及向节点主动下发 `agent.scope.revoked`；
   - 保持私有 PA 的 `personal_observation_event` 静默旁观，同时在 `pa.action.prepare` 与 `resolve_target` 中以结构化 `collaboration_scope_restricted` 拦截对外发言与代发。
3. **节点运行时与外部渠道前置拦截（`packages/personal-assistant`、`apps/node`）**：
   - 在 [attention.ts](../../../../packages/personal-assistant/src/attention.ts)、[single-thread.ts](../../../../packages/personal-assistant/src/single-thread.ts)、[global-agent.ts](../../../../packages/personal-assistant/src/global-agent.ts)、[personal-assistant.ts](../../../../packages/personal-assistant/src/personal-assistant.ts)、[external.ts](../../../../packages/personal-assistant/src/external.ts) 与 [main.ts](../../../../apps/node/src/main.ts) 接入 `ownerInternal` / 纯 `observer` 判定、`SingleThread` 专属群 10 分钟合并、非主人飞书会话发送前拦截（零外部副作用、返回结构化 `not_sent`）以及 `agent.scope.revoked` 会话级清退联动 `configuration.restrictChat`。
4. **Web IM（含 Desktop）与原生 iOS 双端体验（`src/IM/frontend`、`src/IM/ios`）**：
   - 补齐 Web 首次设置引导、PA 创建弹窗、Agent 创建/配置页，以及原生 iOS 新建/配置 Agent 与 PA 引导的两档选择与切换影响提示；
   - 落地双端新建群聊/群详情加人互斥防呆、历史私聊 `agent_private` 本地化只读说明（Web 隐藏消息分支与失效 `⚙` 链接、保留置顶与免打扰菜单；iOS `ChatRepository` 新增 `v7_write_blocked_reason` 迁移避免误显“公开群 · 加入后可参与”）。

## 验证结果

- **跨包构建、类型与运行时检查**：
  - `pnpm build && pnpm typecheck && pnpm check:ios-runtime`：通过
  - `npm --prefix src/IM/frontend run build`：通过
  - `./src/IM/ios/scripts/build.sh build`（Xcode iOS Simulator 目标完整编译）：`** BUILD SUCCEEDED **`
- **后端与前端自动化测试**：
  - `npx vitest run --maxWorkers=3 packages/product-contracts packages/personal-assistant apps/im-server apps/node src/IM/ios/Runtime`：全绿（含新增 [collaboration.test.ts](../../../../packages/product-contracts/tests/collaboration.test.ts)、[agent-privacy-visibility.test.ts](../../../../apps/im-server/tests/agent-privacy-visibility.test.ts)、[agent-privacy-groups-and-pa.test.ts](../../../../apps/im-server/tests/agent-privacy-groups-and-pa.test.ts)、[agent-privacy-scope.test.ts](../../../../packages/personal-assistant/tests/agent-privacy-scope.test.ts) 及既有 `tenancy.test.ts`、`personal-sources.test.ts`、`conversation-search.test.ts`）
  - `(cd src/IM/frontend && npx vitest run --maxWorkers=3)`：`134 passed (134)`（`1,308 passed`）
- **Python 契约、架构红线与文档完整性检查**：
  - `pytest -m "not e2e" -q`：`138 passed`
  - `ruff check . && ruff format --check .`：通过
  - `./scripts/docs-check`：通过
- **隔离真栈真实浏览器走查**：
  - 详见 [evidence/browser-journey.md](evidence/browser-journey.md)，覆盖桌面（`1280×820`）与移动（`390×844`）双视口全部 9 项关键路径，验证后已完整回收隔离栈进程与临时数据。
