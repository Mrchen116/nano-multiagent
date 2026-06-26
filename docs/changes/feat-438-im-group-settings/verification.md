# Verification Report: feat-438

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 |
| Correctness | 7/7（全部 Requirement + Scenario covered） |
| Coherence | Followed（5 条 design 决策均落地） |

No critical issues. No warnings. Ready for PR.

---

## Completeness

### Tasks: 7/7 complete

退出标准全部标 `[x]`（M1-group-settings/tasks.md）：

1. [x] 后端 POST /participants 端点（成功/幂等/空/resolve 失败 400/跨租户 404）
2. [x] ActorPayload 序列化带 user_id（agent id ≠ user_id，决策 5）
3. [x] 移除成员传 user_id 真删（CRITICAL-1 回归防护）
4. [x] 前端 chat-api 4 调用单测
5. [x] GroupSettings 组件 PC 抽屉/移动整屏，对照 prototype
6. [x] chat-workspace-page 入口按 kind 门控（0-agent 群 ⚙ 恒提供）
7. [x] pytest 2975 passed / npm test 482 passed；真实浏览器走查 + 截图（ACCEPTANCE/feat-438-M1/）

### Spec Requirements 覆盖：7/7

所有 spec.md 中的 Requirement 均有对应实现和测试，见 Correctness 节。

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| **Req: 群聊配置入口指向群设置** | chat-workspace-page.tsx:280-283（classifyConversationKind），:574-580（isGroupKind 分流） | integration test line 635（群⚙→GroupSettings dialog）| covered |
| Scenario: 群聊点配置打开群设置 | isGroupKind → setShowGroupSettings(true)（:576） | chat-workspace.integration.test.tsx line 635-648 | covered |
| Scenario: direct chat 点配置仍进 agent 配置页 | !isGroupKind → agentId → navigate（:577-578） | integration test line 675-685 | covered |
| **Req: 在群设置里修改群名** | renameMutation.mutantFn → updateConversation PATCH（:489）；GroupSettings nameInvalid guard（group-settings.tsx:79, 156） | test_conversation_rename.py line 64,179；group-settings.test.tsx line 53-65 | covered |
| Scenario: 改群名成功 | updateConversation → PATCH /conversations/{id}（chat-api.ts:108）；onSuccess invalidateConversations（:490） | test_patch_conversation_title_ok（rename test）；chat-api.test.ts line 127-138 | covered |
| Scenario: 群名不能为空 | nameInvalid = trim().length===0 → save disabled（group-settings.tsx:79, 156）；后端 repo:525 `if not next_title: raise ValueError` → 400 | group-settings.test.tsx line 53-65；test_patch_empty_title_returns_400 | covered |
| **Req: 查看群成员并可进入某成员 agent 的配置页** | groupMembers 预解析（:288-311）；GroupSettings members 渲染（group-settings.tsx:254-275） | group-settings.test.tsx line 37-51 | covered |
| Scenario: 成员列表展示全部成员 | activeConversation.participants.map → groupMembers（:290）；GroupSettings 渲染每行 | group-settings.test.tsx line 37-44 | covered |
| Scenario: 点 agent 成员进其配置页 | onOpenAgentConfig(m.id)（group-settings.tsx:270）；workspace → navigate('/settings/agents/{agentId}')（:619） | group-settings.test.tsx line 46-51（onOpenAgentConfig called with "planner"） | covered |
| **Req: 移除群里的 agent 成员** | removeParticipantMutation(userId)（:501）；removeParticipant 传 user_id（chat-api.ts:137-148）；后端 DELETE /participants/{user_id}（web_im.py:278） | test_remove_participant_by_user_id_removes_agent；group-settings.test.tsx line 83-89 | covered |
| Scenario: 移除一个 agent 成员 | removeParticipant(conversationId!, userId)（:501）；后端 DELETE 按 user_id 删 membership | test_remove_participant_by_user_id_removes_agent（204 + 成员消失）；chat-api.test.ts line 158-166 | covered |
| Scenario: 移除到一个 agent 不剩（边界） | isGroupKind = conversationKind==="group"（不依赖 agentId），0-agent 群 ⚙ 恒提供（:283, 574-576）；GroupSettings 无「没人回」提示 | integration test line 664-673（0-agent 群仍有 ⚙ 且能打开面板） | covered |
| **Req: 向群里添加 agent 成员** | addParticipantsMutation（:495）；addParticipants POST /participants（chat-api.ts:120-130）；后端 add_participants repo（repositories.py:618） | test_post_participants_adds_agent_returns_200；integration test line 650-662 | covered |
| Scenario: 添加一个 agent 进群 | addParticipants(conversationId!, agentIds)→POST /participants（:495）；repo resolve + INSERT（:654-668） | test_post_participants_adds_agent_returns_200；test_add_participants_resolves_agent_and_inserts | covered |
| Scenario: 已在群里的 agent 不重复出现在候选 | addableAgents filter（:313-330）：从 agentsQuery 排除已是 participants 的 agent | integration test line 650-662（候选只含 Reviewer，不含 Planner/Writer） | covered |
| Scenario: 没有可添加的 agent（空态） | addableAgents 为空 → "No agents available to add"（group-settings.tsx:179） | group-settings.test.tsx line 76-81 | covered |
| **Req: 解散群** | dissolveMutation → deleteConversation + navigate("/chat")（:507-513）；后端 DELETE /conversations/{id}（creator only，403 非创建者）（web_im.py:249-275） | test_delete_conversation_by_creator_cascades_data；group-settings.test.tsx line 91-100 | covered |
| Scenario: 解散群成功 | dissolveMutation onSuccess: setShowGroupSettings(false) + invalidateConversations + navigate("/chat")（:509-512） | group-settings.test.tsx dissolve confirm calls onDissolve；ACCEPTANCE/feat-438-M1/r5-pc-dissolve-confirm-1280.png live 证据 | covered |
| Scenario: 取消解散 | confirmingDissolve state，取消不调 onDissolve（group-settings.tsx:75） | group-settings.test.tsx line 91-100（onDissolve not called before confirm） | covered |
| **Req: 移动端可用** | isMobile prop + group-settings.tsx:332+（整屏形态） | group-settings.test.tsx line 110-118；ACCEPTANCE/feat-438-M1/r5-mobile-*.png 4 张 | covered |
| Scenario: 移动端完成群管理 | isMobile → role="dialog" 整屏（:334）；移动端改名/添加成员二级整屏（:303+）/移除/解散均可操作 | 组件测试 mobile 分支；ACCEPTANCE r5-mobile-info-375, r5-mobile-add-375, r5-mobile-manage-375, r5-mobile-dissolve-375 | covered |

### delta-spec 软对账（docs/changes/feat-438-im-group-settings/specs/im/spec.md）

delta-spec 7 条 Scenario 逐一核对：

| delta Scenario | 测试锚点 | 状态 |
|---|---|---|
| 向已存在的群会话添加参与者 → 200 + 成员出现 | test_post_participants_adds_agent_returns_200 | ✓ |
| 重复添加已在群参与者 → 幂等 | test_post_participants_idempotent；test_add_participants_idempotent_skips_existing | ✓ |
| 空列表或 resolve 失败 → 400 | test_post_participants_empty_returns_400；test_post_participants_unknown_agent_returns_400 | ✓ |
| 跨租户 POST /participants → 404 | test_post_participants_cross_tenant_returns_404 | ✓ |
| 修改群名生效，空名被拒 | test_patch_empty_title_returns_400（后端）；group-settings.test.tsx 空名禁用 save（前端） | ✓ |
| 会话参与者带 user_id | test_participant_payload_carries_user_id（agent id ≠ user_id，均存在） | ✓ |
| 移除参与者后该成员从群消失（传 user_id） | test_remove_participant_by_user_id_removes_agent（204 + 成员消失） | ✓ |
| 仅创建者可解散群，非创建者 403 | test_delete_conversation_by_non_creator_raises_permission_error（repo）；web_im.py:272-275（PermissionError → 403） | ✓ |

**Advisory**: delta-spec 尚未并入 canonical `docs/specs/im/spec.md`（截至本次验证）；orchestrator 在收尾归并时需确保 8 条 Scenario 完整合入。

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1：GroupSettings 独立组件，PC 右侧抽屉 / 移动整屏（不用居中 modal / 独立路由） | ✓ | group-settings.tsx:332+（mobile fullscreen）/ :384+（PC aside drawer）；复用 `--im-*` token，不引入新路由 |
| 决策 2：onOpenConfig 按 classifyConversationKind 分流；**group/agent-network 恒提供 ⚙**（与是否有 agent 无关） | ✓ | chat-workspace-page.tsx:280-283（isGroupKind = kind==="group"\|\|"agent-network"）；:574-580（isGroupKind 分流，不由 agentId 门控）；integration test 664-673（0-agent 群 ⚙ 在位） |
| 决策 3：POST /participants 复用 create resolve+INSERT，**不重冻 config_profile_version**，幂等 | ✓ | repositories.py:618-671（无 `_resolve_config_profile_version` 调用）；docstring 显式注明（:625-627）；test_add_participants_does_not_refreeze_config_profile_version |
| 决策 4：写后 invalidateQueries(["chat-v2","conversations"])；解散后 navigate("/chat") | ✓ | chat-workspace-page.tsx:485-486（invalidateConversations 用精确 key）；:509-512（dissolveMutation onSuccess navigate("/chat")）；query 定义 key 完全一致（:190） |
| 决策 5：ActorPayload 补 user_id 透传；removeParticipant 传 user_id（UUID）非 agent_id | ✓ | web_im.py:23（user_id 字段）、:106（透传 Actor.user_id）；chat-api.ts:137-148（removeParticipant 签名 userId，URL 拼 userId）；test_participant_payload_carries_user_id + test_remove_participant_by_user_id_removes_agent |

### 架构自洽性（§4.3）

- **依赖方向**：所有改动限 IM 包前端 + 后端，路由 → service → repo 方向正确；前端仅经 `/im/v1/*` HTTP，无跨包 import。✓
- **跨机边界**：无假设两端同机的直访（无文件系统直读）。✓
- **复用 vs 平行**：`_actor_payloads_to_references` 复用于 create / add 两条路径（web_im.py:340-356），无平行实现。✓

---

## Issues

### CRITICAL
_无_

### WARNING
_无_

### SUGGESTION

- **delta-spec 并入提醒**（advisory，非代码问题）：`docs/changes/feat-438-im-group-settings/specs/im/spec.md` 的 8 条 Scenario 尚未合并入 `docs/specs/im/spec.md`。orchestrator 收尾归并时需确认全部合入，特别是「会话参与者带 user_id」和「向已存在的群会话添加参与者」两条是本 unit 新增的 HTTP 契约行为，canonical spec 当前无对应 Requirement 覆盖。

---

All checks passed. Ready for PR.
