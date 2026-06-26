# feat-438-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

### R1 — 后端：add_participants + POST /participants + ActorPayload.user_id

- Context: 群成员管理需要一个「添加 agent」端点（后端原本只有 PATCH/DELETE participant/DELETE conversation），且前端移除路径需要 participant 的 user_id（CRITICAL-1：agent participant 的 `id` 是 agent_id，不是删除端点用的 user_id）。
- Decision:
  - `ConversationRepository.add_participants(conversation_id, references)`：复用 `_resolve_participant_user_row` 做 agent→user 解析 + 幂等 INSERT membership；**不**调用 config 快照逻辑，因此不重冻 `config_profile_version`（决策 3）。
  - `WebIMService.add_participants` 透传。
  - 新路由 `POST /im/v1/conversations/{id}/participants`：先 `_load_owner_scoped_conversation`（跨租户 404），再 resolve + add；空列表 / resolve 失败由 repo raise ValueError → route 映射 400（决策 3 要求 400 而非 422，故不在 Pydantic model 上做 min_length）。
  - `ActorPayload` 加 `user_id`，`to_conversation_response` 透传域 `Actor.user_id`（决策 5）。域 `Actor` 本就有 `user_id`，纯透传。
  - 抽 `_actor_payloads_to_references` 供 create / add 共用，避免平行实现（§0.1）。
- Rationale: membership 写入与 resolve 已存在于 create 路径，抽成可复用方法符合「复用现有架构」；不碰 relay——relay 在发消息时按 participants 动态建（design 现状分析已证）。
- Evidence:
  - Tests: `tests/unit/IM/test_conversation_add_participants.py` 13 passed（repo 全分支 + route 200/幂等/400 空/400 resolve 失败/404 跨租户 + user_id 透传 + CRITICAL-1 移除用 user_id 真删）。`tests/unit/IM/ + tests/im_service/` 406 passed / 1 skip。
  - Entry: HTTP route 测试经 TestClient 真发请求（非 mock 入口）：POST 加 agent → 200 且 participants 含该 agent；DELETE /participants/{user_id} → 204 且成员消失。
  - Frontend State Matrix: N/A
  - Browser QA: N/A（后端 roadpoint，UI 走查在 R5）
  - E2E/Regression: `test_remove_participant_by_user_id_removes_agent` 锚定 CRITICAL-1（防止前端误传 agent_id 导致删不掉的回归）。
  - Visual/Interaction: N/A
- Rollback: 回退到 R1 C1 commit（删端点 + add_participants + user_id 字段即回到现状）。
- Commits: C1=test(R1 红测), C2=feat(R1 实现), C3=docs(本段)
- Next: R2 前端 chat-api 4 调用 + Actor.user_id。

### R2 — 前端 chat-api 4 调用 + Actor.user_id

- Context: GroupSettings 组件需要四个写操作；其中移除必须用 participant.user_id（决策 5）。
- Decision: chat-types `Actor` 加 `user_id?: string | null`；chat-api 加 `updateConversation`(PATCH)/`addParticipants`(POST participants，构 `{type:"agent",id}` actor)/`removeParticipant`(DELETE participants/{userId})/`deleteConversation`(DELETE)。remove/delete 是 204 no-content，仅校验 `res.ok`、不 `jsonOrThrow`（避免空 body 解析报错）。
- Rationale: 沿用文件既有 `authFetch` + `jsonOrThrow` 范式；removeParticipant 签名第二参命名 `userId` 并在 doc 里钉死「传 user_id 不是 agent_id」，从 API 层堵 CRITICAL-1。
- Evidence:
  - Tests: `chat-api.test.ts` 10 passed（新增 5：update PATCH body、add POST participants body、remove DELETE 用 user_id 的 URL、delete DELETE URL、remove 非 ok 抛错）。
  - Entry: vitest mock fetch 校验真实 URL/method/body 契约（与后端路由对账：PATCH /conversations/{id}、POST .../participants、DELETE .../participants/{user_id}、DELETE /conversations/{id}）。
  - 其余维度: N/A（纯 API client，UI 在 R3/R5）
- Rollback: 回退 R2 C1。
- Commits: C1=test(R2 红测), C2=feat(R2 实现), C3=docs(本段)
- Next: R3 GroupSettings 组件（PC 抽屉 / 移动整屏）。

### R3 — GroupSettings 组件（PC 抽屉 / 移动整屏）

- Context: 决策 1 要求单组件两形态承载群名/成员/添加/移除/解散。
- Decision: `components/group-settings.tsx` 纯展示组件，props 接 workspace 预解析好的 `members`（含 userId/status/isSelf/isCreator/isStale）+ `addableAgents`（已排除已入群），handler 全外注。本地 state：renaming/nameDraft、adding/selectedAgentIds、confirmingRemoveId、confirmingDissolve、manageMode。按 `isMobile` 分两 return 分支，rename/picker/member-row/dissolve 子块共享。移动「添加成员」走二级整屏（`isMobile && adding` 接管整屏，对齐 prototype B4），PC 走就地展开 addbox（A3）。i18n 新增 `chat.groupSettings` 块（en+zh 同键）。样式 append global.css，token 复用 --im-*。
- Rationale: 业务逻辑（数据解析/刷新/导航）留在 workspace（R4），组件只管交互 → 可单测、不裸接 API shape。复用 NewGroupModal 的 modal/sheet 心智但不复用其居中 modal 形态（决策 1 拒绝项）。
- Evidence:
  - Tests: `group-settings.test.tsx` 9 passed（成员列表+创建者 tag、点 agent→onOpenAgentConfig(agent_id)、改名空名禁用 save / 改名 trimmed、添加候选渲染+选中确认→onAddParticipants、添加空态、**移除确认传 userId 非 id**、解散二次确认、close、移动 back）。
  - Entry: 真实组件交互（@testing-library/user-event 真点击），非 mock。浏览器形态验收在 R5。
  - Frontend State Matrix: default/disabled(空名)/empty(无可加 agent)/submitting(isBusy 禁用)/long-content(CSS 省略/换行，R5 截图验)/mobile+desktop 两形态均覆盖；error(写失败 toast) 在 R4 workspace + R5 验。
  - Browser QA: R5
  - E2E/Regression: 组件测试落库（critical-path 成员增删改 + 解散闭环 + CRITICAL-1 userId）。
  - Visual/Interaction: R5 截图对照 prototype。
- Rollback: 回退 R3 C1。
- Commits: C1=test(R3), C2=feat(R3), C3=docs(本段)
- Next: R4 接线（入口分流 + 数据装配 + 刷新）。
