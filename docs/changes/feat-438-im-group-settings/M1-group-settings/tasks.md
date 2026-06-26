# feat-438-M1: group-settings — Tasks

> 对齐: ../design.md v1

## 目标

群聊「配置」入口打开「群设置」面板（不再错跳第一个 agent 配置页）；面板里能改群名（空名拒绝）、
看成员列表、点 agent 成员进其配置页、添加 agent 成员（候选排除已入群、空态）、移除 agent 成员
（含移到 0 agent 仍能开群设置）、解散群（确认后回会话列表）。桌面端（右侧抽屉）+ 移动端（整屏）两形态。
后端新增 `POST /conversations/{id}/participants` 端点 + `ActorPayload` 补 `user_id` 透传。

## 退出标准

- [x] 后端 `POST /participants` 端点：成功 / 幂等 / 空 / resolve 失败 400 / 跨租户 404（R1）
- [x] `ActorPayload` 序列化带 `user_id`（agent participant 的 `id`=agent_id ≠ `user_id`=UUID）（R1）
- [x] 移除成员 `DELETE /participants/{user_id}` 用 user_id 真能删（防 CRITICAL-1 回归）（R1 单测 + R5 live `DELETE .../946ac506...`）
- [x] 前端 chat-api 4 调用（update/add/remove/delete）单测（R2）
- [x] GroupSettings 组件 PC 抽屉 / 移动整屏两形态，对照 prototype.html 视觉一致（R3 + R5 截图）
- [x] chat-workspace-page 入口按 kind 门控分流（group/agent-network → 群设置；direct-agent → agent 配置；0-agent 群仍提供 ⚙）（R4 + R5 live）
- [x] `pytest -q tests/ -m "not e2e"` 与前端 `npm run test` 绿（2974 passed / 482 passed）
- [x] 真实浏览器走查全部 Runbook 关键界面 + 375px（R5，截图见 ACCEPTANCE/feat-438-M1/）

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - 后端 add_participants（repo）：resolve agent→user_id + INSERT、幂等跳过、空/resolve 失败 raise、不重冻 config_profile_version
  - 后端 `POST /participants`（route）：200 成功 / 400 空·resolve 失败 / 404 跨租户
  - 后端 ActorPayload.user_id 透传；DELETE /participants/{user_id} 用 user_id 删（防 CRITICAL-1）
  - 前端 chat-api 4 调用的 URL/method/body 契约
  - 前端 GroupSettings 关键交互（改名空名禁用、添加候选排除已入群 + 空态、移除确认、解散确认）
  - 入口分流（group → 开面板不 navigate；direct-agent → navigate agent 配置）
- 已有测试在：`tests/unit/IM/test_conversation_rename.py` / `test_conversation_delete.py`（同款 repo+route 范式，新增端点建 `test_conversation_add_participants.py`）；
  前端 `src/IM/frontend/src/features/chat/v2/chat-api.test.ts`（扩展 4 调用）；GroupSettings 新建 component test。
- 落层/目录/marker：tests/unit/IM/（后端单测，无 marker）；前端 vitest 就近 colocate。
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器走查截图（ACCEPTANCE/ 下）

### 前端

用户路径分类：
- `bug-regression`：群聊入口错跳 agent 配置 → 入口分流（integration test 落库）
- `critical-path`：成员增删改 + 解散闭环（chat-api 单测 + GroupSettings 交互测试落库）
- `normal-ui`：GroupSettings 两形态布局（浏览器临时验收 + 状态矩阵）

UI 状态矩阵（GroupSettings）：
| 状态 | 覆盖计划 |
|---|---|
| default | 成员列表渲染（PC 抽屉 / 移动整屏）— 浏览器 + 组件测试 |
| loading | 写操作 pending（按钮禁用）— 组件测试 submitting |
| empty | 添加成员候选空态「没有可添加的 agent」— 组件测试 + 浏览器 |
| error | 写操作失败 toast — 浏览器手测（不强制落库） |
| disabled | 改名空名 → 保存禁用 — 组件测试 |
| submitting | 同 loading |
| permission denied | N/A（解散权限后端硬校验，单租户单人场景操作者即创建者） |
| long content | 长群名 / 长 agent 名溢出 — 浏览器截图 |
| missing/nullable data | 0-agent 群仍能开面板 — 浏览器 + 入口门控测试 |
| mobile viewport | 375px 整屏形态各项 — 浏览器走查 |
| desktop viewport | 抽屉形态各项 — 浏览器走查 |
| dark mode | N/A（项目无暗色） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 群聊入口错跳 agent 配置（bug 根因） | integration test（入口分流）+ 浏览器 | 是 |
| 移除传 user_id 真能删（CRITICAL-1） | 后端 route 单测 + chat-api 单测 | 是 |
| 添加候选排除已入群 / 空态 | GroupSettings 组件测试 + 浏览器 | 是 |
| 改名空名拒绝 | GroupSettings 组件测试 | 是 |
| 解散回列表 | 浏览器走查 | 否（交互链路，单测验 mutation） |
| 两形态布局 / 长内容溢出 | 浏览器截图 + 状态矩阵 | 否 |

## Roadpoints

### R1 — 后端：add_participants + POST /participants + ActorPayload.user_id  — DONE

- 步骤: repo 抽 `add_participants(conversation_id, references)` 复用 resolve+INSERT（幂等、不碰 config_profile_version）；service passthrough；route `POST /conversations/{id}/participants`（404 跨租户 / 400 空·resolve 失败）；`ActorPayload` 加 `user_id`，`to_conversation_response` 透传 `Actor.user_id`。
- 验证: 新建 `test_conversation_add_participants.py`（repo + route 全分支）；扩 rename/delete 测试或新增断言验 user_id 透传 + DELETE 用 user_id 删。

### R2 — 前端 chat-api 4 调用 + Actor.user_id  — DONE

- 步骤: `chat-types.ts` Actor 加 `user_id?: string | null`；`chat-api.ts` 加 `updateConversation` / `addParticipants` / `removeParticipant` / `deleteConversation`。
- 验证: 扩 `chat-api.test.ts` 验 4 调用的 URL/method/body（removeParticipant 用 user_id）。

### R3 — GroupSettings 组件（PC 抽屉 / 移动整屏）  — DONE

- 步骤: 新建 `components/group-settings.tsx`，按 `useIsMobile` 切两形态，复用 chat-modal 设计 token；改名内联态、成员列表（点 agent → onOpenAgentConfig）、添加成员就地展开（PC）/ 二级整屏（移动）、移除确认、解散确认。状态逻辑共享、视图分叉。
- 验证: 组件测试覆盖改名空名禁用、添加候选排除已入群 + 空态、移除确认、解散确认。浏览器对照 prototype。

### R4 — 接线：入口分流 + 数据装配 + 刷新  — DONE

- 步骤: `chat-workspace-page` 按 `classifyConversationKind` 分流（group/agent-network → 开 GroupSettings；direct-agent → navigate）；message-pane ⚙ 对 group 恒提供（不再仅 agentId 真值门控）；写操作成功 `invalidateQueries(conversations)`，解散后 `navigate("/chat")`；装配 agents/members 数据喂 GroupSettings。
- 验证: integration test 验入口分流（group 开面板不 navigate / direct navigate / 0-agent 群仍提供 ⚙）。

### R5 — 真实浏览器走查（live 验收）  — DONE

- 步骤: 起 IM + Vite（ephemeral 端口），按 Runbook 走查全部关键界面 + 375px，截图存证，对照 prototype。
- 验证: progress.md Evidence 记真实入口截图（含 viewport）+ 对照结论 + console/network 检查。
