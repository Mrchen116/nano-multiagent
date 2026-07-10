# Design 评审:feat-438-im-group-settings

**结论**:Issues Found（1 CRITICAL + 1 WARNING）

独立复核了 design.md 全部承重原子，并对每个架构选择做了四角度进攻。方案整体方向正确、修的是真根因（群聊错用 direct「会话即单 agent」假设）、复用合理、无多余抽象——但**有一条现状断言是错的**，会让核心特性「移除成员」照设计实现后 404 静默失效；另有一处入口数据流闭合的边界没说清。

## 核实台账（逐条核过的承重原子；结论附证据）

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| `chat-workspace-page` 是 bug 源头 + 入口分流落点；`headerAgentContext`(229-258) 抓第一个 agent，`onOpenConfig`(457-461) 据此 navigate | 读真实代码核 | ✓ 成立。`headerAgentContext` 在 229-258，用 `participants.find(p=>p.type==="agent")`(239)；`onOpenConfig` 在 457-461，`headerAgentContext.agentId ? navigate(/settings/agents/{id}) : undefined`。群聊也走此条 → 错跳第一个 agent |
| `message-pane` ⚙ 按钮(248-263) 触发回调即群设置入口 | 读真实代码核 | ✓ 成立（message-pane.tsx:248-263）。**但**按钮**仅在 `onOpenConfig` 真值时渲染**(248)——见 WARNING-1 |
| `chat-api` 已有 createConversation，缺 update/add/remove/delete | grep chat-api.ts | ✓ 成立。仅 listConversations/listMessages/createMessage/createConversation/listMentionCandidates，无四个写操作 |
| `web_im.py` 已有 PATCH(199)/DELETE participant(263)/DELETE conversation(230)，缺 POST participants | 读 web_im.py | ✓ 成立。PATCH(199-227)、DELETE conversation(230-260)、DELETE participants/{user_id}(263-289) 均在；无 POST participants |
| 解散权限在 service 层硬校验 creator_id==requester，非创建者 403 | 读 delete 路径 | ✓ 成立。web_im.py:257 捕 PermissionError→403；service.delete_conversation(requester_id=user.id) |
| 后端 add/remove/rename/dissolve 均不发 WS 会话事件，前端靠 listConversations 刷新 | 读 service/路由 | ✓ 成立。update_conversation/remove_participant 仅写库返回快照，无事件广播 |
| **成员标识 = user_id(UUID)；前端 `participants[].id` 即该 user_id，移除直接用它，无需额外查询** | 从 repo actor 构建 + 响应序列化 + DELETE 删除条件正向追 | ✗ **不成立**。agent participant 的 `Actor.id = agent_id`（repositories.py:740-748，`username[len("agent:"):]`），`Actor.user_id` 才是 UUID；`ActorPayload` 序列化(web_im.py:88-94) **只带 id 不带 user_id**，前端拿到的 `participants[].id`(agent) = **agent_id**。而 DELETE `/participants/{user_id}` 按 `conversation_participants.user_id`(UUID) 删除(repositories.py:618-645)。→ **CRITICAL-1** |
| `create_conversation` 路径含 agent→user_id 归一 + INSERT participants(repo:478)，可复用 | 读 repo create_conversation | ✓ 成立。repo:404-412 resolve→resolved_user_id，repo:478 INSERT conversation_participants(user_id) |
| NewGroupModal 是 modal/sheet 壳 + agent 多选样板，可复用 | 读 new-group-modal.tsx + global.css | ✓ 成立。useIsMobile 分支(22)、chat-modal-sheet(47)、checkbox 列表(99)；`chat-modal-backdrop`/`chat-modal-sheet` token 在 global.css |
| relay task 由 enqueue_message_relay_all 在**发消息时**按当前 participants 动态建，非建会话/加成员时预建 | 读 relay_service + web_im_service.create_conversation | ✓ 成立。create_conversation(web_im_service:33-49) 不碰 relay；relay 经 enqueue_message_relay_all 在消息流创建。spec.md:156「为新增 agent 创建 relay task」确属作废，design 纠正正确 |

### 决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策 1：GroupSettings 独立组件，PC 抽屉/移动整屏两形态 | 拍死？落现状内？ | ✓ 拍死，形态明确，复用 chat-modal token + useIsMobile 分支范式已存在。PC 右侧抽屉无现成 token 需新写 CSS，design 已注明「落地成本可控」，属 worker 实现 |
| 决策 2：onOpenConfig 按 classifyConversationKind 分流 | 拍死？数据流闭合？ | ⚠ 分流逻辑拍死且 classifyConversationKind 存在(chat-types.ts:153，返回 direct-agent/group/agent-network/direct-user)。但**未说改 onOpenConfig 的真值门控**——0-agent 群门控失效，见 WARNING-1 |
| 决策 3：POST participants 复用 resolve+INSERT，不碰 relay，幂等，跨租户 404 | 拍死？现状证据？ | ✓ 成立。resolve+INSERT 复用源已证；relay 零改动已证；幂等/400/404 边界都点到 |
| 决策 4：写后 invalidateQueries(["chat-v2","conversations"])，解散后 navigate("/chat") | 键对得上吗？ | ✓ 成立。query key = `["chat-v2","conversations"]`(chat-workspace-page.tsx:173) 完全一致 |
| 决策间矛盾 | 逐对扫 | ✓ 无矛盾。四决策同向，均落 IM 包前后端 |

### spec 约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Req 配置入口指向群设置、direct 不变 | design 落点？ | ✓ 决策 2 覆盖 |
| Req 改群名（空名拒绝） | 落点？ | ✓ 决策 4 + 复用 PATCH；后端 update_conversation 已校验空名(repo:744 raise) |
| Req 查看成员 + 点 agent 进配置 | 落点？ | ✓ GroupSettings 成员区；participant.id(agent)=agent_id 直接喂 navigate(/settings/agents/{id})，此处恰好正确 |
| Req 移除 agent（含移到 0 不提示） | 落点？ | ⚠ 决策 3/4 名义覆盖，但移除调用受 CRITICAL-1 阻断；0-agent 后入口受 WARNING-1 阻断 |
| Req 添加 agent（候选排除已入群/空态） | 落点？ | ✓ 决策 3 + 前端候选 = agentsQuery 减 participants(按 agent_id 比对，一致) |
| Req 解散群（确认+回列表，仅创建者） | 落点？ | ✓ 决策 4 + 复用 DELETE conversation |
| Req 移动端可用 | 落点？ | ✓ 决策 1 两形态 + useIsMobile |
| 澄清 Q1/Q2'/Q3/Q4/Q5/Q6/Q7 | 逐条对齐 | ✓ 全部落入决策（不做退群、空名拒绝、0-agent 不提示、点 agent 进配置、移动端、加成员并入） |
| 非目标（群头像/描述、退群、权限分层、撤回/回复） | design 越界否？ | ✓ 未越界 |

### delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| im delta 存在；kernel/gateway/cli 注明 no spec delta | 查 specs/im/spec.md + design §契约层 | ✓ 齐全 |
| ADDED「群会话支持成员增减/改名/解散」用法 | 核 canonical 是否已有同条 | ✓ ADDED 合理。canonical im/spec.md 无「移除参与者/解散/正向改名」既有 Requirement（仅 74「会话以 Actor 建模」覆盖创建+404），非顶替既有契约 |
| Scenario THEN 是否只写可观察结果 | 逐条扫 | ✓ 全部消费者可观察（200/204/400/404/参与者集合/会话快照），无内部符号断言 |
| 消费者视角对准 | 核主语 | ✓ 主语 = 浏览器前端/终端用户，对准 |

### milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 单 M1 group-settings | 垂直 vs 横切？举证？ | ✓ 垂直切片（前端面板 + 一个后端端点端到端强耦合），未拆前后端，单 worker 窗口内，举证充分 |
| 退出标准两轨 | [reviewer]/[worker] 齐？可验？ | ✓ [reviewer] 引 spec 全 Requirement/Scenario；[worker] 列端点单测矩阵 + 前端单测 + pytest/npm 绿 + 对照 prototype，可验 |

## 架构进攻（四角度逐个走）

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | GroupSettings(前端)、POST participants(web_im.py 路由)、入口分流(chat-workspace-page)、chat-api 四调用 | ✓ 走完无存活发现。全部落 IM 包对应层，依赖方向（前端→/im/v1 HTTP→路由→service→repo）顺，无跨层/反向依赖；多决策叠加未引入隐含反向依赖 |
| 该不该存在 | 后端抽 `add_participants` 复用 create 的 resolve+INSERT | ✓ 无存活发现。删除测试：删掉它则 POST 端点要重写一遍 resolve+INSERT，复杂度真实集中、非搬家。唯一须留意：create 路径还含 config_profile_version 冻结/conversation_type 计算，add 时**不应**重新冻结既有会话——见 Recommendation |
| 深还是浅 | chat-api 四个 thin 调用、GroupSettings 面板 | ✓ 无存活发现。chat-api 是既有 narrow client 同款 thin wrapper（项目既定模式）；GroupSettings 是实质 UI 非浅封装 |
| 治本还是补丁 | 入口分流修 bug 的方式 | ✓ 无存活发现。按 classifyConversationKind 分流是正面修根因（群聊误用 direct 单 agent 假设），非在 headerAgentContext 上叠特例绕过 |

## Issues（按 CRITICAL > WARNING 排序）

- **[CRITICAL] [现状分析 / 决策 3-4 移除路径 / chat-api removeParticipant 签名]**：现状断言「`conversation.participants[].id` 即 user_id，移除直接用它，无需额外查询」**错误**。agent participant 的 `id = agent_id`（repositories.py:740-748），`ActorPayload` 序列化不带 user_id（web_im.py:88-94），而 DELETE `/participants/{user_id}` 按 `conversation_participants.user_id`(UUID) 删除（repositories.py:618-645）。worker 照设计用 `participant.id`(=agent_id) 调 `removeParticipant` → 后端查 `WHERE user_id = <agent_id>` 无匹配 → ValueError → 404，**核心 spec Requirement「移除 agent 成员」会静默失效**，且只在端到端 review 才暴露。
  - **改法**（任一，design 需拍）：① 前端用已加载的 `agentsQuery`（`AgentRow.user_id`，chat-api.ts:118）把 agent participant 的 `id`(agent_id) 映射成 user_id 再传 DELETE；② 后端 `ActorPayload` 增 `user_id` 字段、`to_conversation_response` 透传，前端直接用。需在现状分析改正「无需额外查询」的错误前提，并在决策或接口段写明 removeParticipant 传的是 UUID、来源是哪。
  - 注意 user 本人 participant 的 `id` 确实 = user_id（repositories.py:750），且成员列表「点 agent 进配置」用 `participant.id`=agent_id 直接喂 `/settings/agents/{id}` **是对的**——错只错在移除路径混用了两种 id。

- **[WARNING] [决策 2 / 入口数据流闭合]**：现状 `onOpenConfig` 由 `headerAgentContext.agentId` 真值门控（chat-workspace-page.tsx:457-461），而 message-pane 的 ⚙ 按钮**仅在 `onOpenConfig` 真值时渲染**（message-pane.tsx:248）。决策 2 只说「按 kind 分流」，未说改这层门控。spec 明确允许「移除到 0 agent，群仍存在」（Req 移除/边界 Scenario）——0-agent 群的 `headerAgentContext.agentId` 为 null → ⚙ 按钮消失 → 用户**再也打不开群设置去加回 agent 或解散**，群被锁死。worker 若沿用 agentId 门控会复现此死角。design 应写明：group/agent-network 会话**恒提供 onOpenConfig**（与是否存在 agent 无关），门控改由会话 kind 决定。

## Recommendations（不阻断门禁，作者自行取舍）

- 后端 `add_participants` 复用 create 路径时，建议显式注明**不重新冻结** `config_profile_version`（既有会话已有冻结版本，新加 agent 应沿用，不应触发 `_resolve_config_profile_version` 重算覆盖）。属 worker 实现边界，点一句可避免误抽。
- spec.md:156 仍残留作废的「为新增 agent 创建 relay task」描述。design 已在现状分析纠正、delta-spec 未带入，收尾归并前可回 spec-author 顺手清掉，避免长青化时被误并。
