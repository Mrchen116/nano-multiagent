# bugfix-358-M1 Progress

## 开工报告

已读懂 M1，范围 = relay_service.py participants/mention 解析 + agent prompt/hook + 前端 picker/chip 渲染。单 milestone 垂直切片整体交付。开始实施。

---

### R1 — IM relay payload schema 修正

- Context: `_resolve_all_participants` 返回 `{id: synth_uuid}` 导致 agent 学到 UUID 而非 agent_id；wire ID 与 display 层未分离。
- Decision: 修改 `_resolve_all_participants` 和 `_resolve_sender_info` 使 agent 条目返回 `{type, agent_id, display_name}`，user 条目返回 `{type, user_id, display_name}`，与 actor-first 协议一致。
- Rationale: 让 relay payload 携带正确 wire ID，agent 从 prompt 获得的 group_participants 只含 agent_id/user_id，不含 synth UUID。
- Evidence:
  - Tests: `pytest -xvs tests/unit/IM/test_relay_service_mention.py` 8 passed
  - Entry: relay_service 直接单测验证 payload schema
  - Frontend State Matrix: N/A (后端)
  - Browser QA: N/A (后端)
  - E2E/Regression: 集成测试 R7 覆盖
  - Visual/Interaction: N/A
- Rollback: 3dcada23
- Commits: C1=3dcada23, C2=9e65c882

### R2 — IM mention 解析改为 inline tag

- Context: 旧 `_resolve_mention_to_agent_ids` 用 `@display_name` 文本匹配，导致孤儿 agent 可以用相同 display_name 截胡。
- Decision: 删除 display_name fallback，新增 `_resolve_mentioned_agent_ids_from_tags` 仅解析 `<mention type="agent" target_id="X"/>` 标签，且 target_id 必须在 participant_agent_ids 列表中。
- Rationale: 标签包含精确 agent_id，孤儿无法伪造；display_name 只是展示层。
- Evidence:
  - Tests: `pytest -xvs tests/unit/IM/test_relay_service_mention.py tests/unit/IM/test_relay_service_broadcast.py` 12 passed
  - Entry: 单测验证 at-text 不再路由，tag 正确路由
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R7 集成测试覆盖
  - Visual/Interaction: N/A
- Rollback: 9e65c882
- Commits: C1=3dcada23 (共享), C2=9e65c882 (共享)

### R3 — Agent prompt + hook 更新

- Context: agent prompt 教 `@agent_id` 文本语法，与新 inline tag 格式不一致。
- Decision: 删除 prompts.py 旧注释行；communication_context.py 中 `message_format` 改为教 `<mention type="agent" target_id="X"/>` 语法，带示例。
- Rationale: agent 输出的 mention 必须用 inline tag 格式，IM 才能正确路由。
- Evidence:
  - Tests: `pytest -xvs tests/unit/personal_assistant/test_communication_context_bugfix358.py` 6 passed
  - Entry: hook 单测验证 inline tag 教学存在，@agent_id 语法不再出现
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A (prompt 变更无自动化 e2e)
  - Visual/Interaction: N/A
- Rollback: a333e133
- Commits: C1=a333e133, C2=ed24c121

### R4 — 前端 parseMentions 工具函数

- Context: 前端无 mention 标签解析器；composer mirror 和 MessageBubble 均需解析 `<mention/>` 标签。
- Decision: 新建 `mention-parser.ts`，导出 `parseMentions(content): Segment[]`，分割为 TextSegment 和 MentionSegment。
- Rationale: 单一解析函数被 mirror 和 bubble 两处复用，逻辑集中。
- Evidence:
  - Tests: `npm run test` mention-parser.test.ts 11 passed
  - Entry: 单元测试全覆盖
  - Frontend State Matrix: N/A (纯工具函数)
  - Browser QA: 通过 R6 browser QA 间接验证
  - E2E/Regression: 单元测试
  - Visual/Interaction: N/A
- Rollback: 798581c0
- Commits: C1=798581c0, C2=6d067ccd

### R5 — 前端 picker 写入标签 + handle 条件显示

- Context: picker 选中后插入 `@display_name` 文本，路由无法通过 agent_id；同名 agent 无法区分。
- Decision: `handleMentionSelect` 改为写 `<mention type="agent" target_id="${c.agent_id}"/>` 标签；MentionPicker 新增 `hasDuplicateNames` 检测，仅在有重名时显示 handle 列。
- Rationale: 标签携带 agent_id，IM 可精确路由；handle 列只在必要时显示，不污染正常 UI。
- Evidence:
  - Tests: mention-picker.test.tsx 6 passed；message-pane.test.tsx inline tag 测试通过
  - Entry: 浏览器验收：@ 后 picker 显示，点选后 textarea 含正确 inline tag（下面 Browser QA）
  - Frontend State Matrix: picker 正常/空态/重名/筛选 均验证
  - Browser QA: 见 R6/R7 browser QA 段
  - E2E/Regression: 组件测试落库
  - Visual/Interaction: 见截图 ACCEPTANCE/m170-runtime/r16-mention-picker-selected.png
- Rollback: 1029d349
- Commits: C1=1029d349, C2=5f1b5780

### R6 — 前端 MessageBubble MentionChip 渲染

- Context: 消息气泡展示 `<mention/>` 标签原始 XML 文本，用户体验差。
- Decision: 新增 `renderInlineContent(text, participants?)` 函数，用 parseMentions 解析后，对 agent/user mention 渲染 `<span class="chat-mention-chip">@displayName</span>`；未知 target_id 降级为 `@unknown`。同时修正 user 气泡也使用 `renderInlineContent`（agent 消息已用 MarkdownContent）。
- Rationale: 双向渲染一致性：user 发出的 mention 和 agent 回复的 mention 均显示 chip。
- Evidence:
  - Tests: message-pane.test.tsx "MessageBubble MentionChip rendering (bugfix-358)" 3 tests passed；前端总测试 322 passed
  - Entry: 浏览器验收通过（见 Browser QA）
  - Frontend State Matrix: chip 正常/unknown target/无 tag 三态覆盖
  - Browser QA: |
      URL: http://127.0.0.1:8011/chat/358879bdd812442db936145521c7fc15
      用户路径: 在群聊 "架构, Q" 中输入 @ → picker 显示 → 点选 Q → textarea 含 <mention type="agent" target_id="ArchA"/> → mirror 显示 @Q chip → 点 Send → 用户气泡显示 @Q chip
      Console error: 无
      Network failure: 无
      截图: ACCEPTANCE/m170-runtime/r16-chat-testagent-1440.png（发送后气泡含 @Q chip）
            ACCEPTANCE/m170-runtime/r16-mention-picker-selected.png（picker 显示 架构/Q 两条）
  - E2E/Regression: 组件测试落库
  - Visual/Interaction: 截图见上
- Rollback: 325a5293
- Commits: C1=325a5293, C2=7442664a

### R7 — 集成测试 + 全局验证

- Context: 需要端到端集成测试验证三向 mention 路由，并确认全局没有新引入测试失败。
- Decision: 新增 `tests/integration/test_group_mention_routing.py` 6 个测试，覆盖 agent→agent、user→agent、agent→user 路由、display_name 文本不路由、孤儿不截胡、同名消歧。
- Rationale: RelayService API 级集成测试，真实 DB，无 HTTP 服务依赖，验证完整路由链路。
- Evidence:
  - Tests: `pytest -xvs tests/integration/test_group_mention_routing.py` 6 passed
  - Entry: 集成测试使用真实 SQLite DB，覆盖所有核心路由场景
  - Frontend State Matrix: N/A
  - Browser QA: N/A (后端集成测试)
  - E2E/Regression: 6 个集成用例全部落库
  - Visual/Interaction: N/A
- Rollback: 7442664a
- Commits: C1=0fd508db
- Next: 所有 roadpoint DONE，进行集成到 unit 分支

---

## 全局验证结果

- `pytest tests/unit/IM/test_relay_service_mention.py tests/unit/IM/test_relay_service_broadcast.py tests/unit/personal_assistant/test_communication_context_bugfix358.py tests/integration/test_group_mention_routing.py` — 24 passed
- `cd src/IM/frontend && npm run test` — 322 passed, 2 pre-existing failures (token-chip 2429 sum, policies-page) 不属于本 unit
- `cd src/IM/frontend && npm run build` — ✓ built in ~850ms
- Browser QA: picker 显示、inline tag 写入、chip 渲染 均通过（截图见 R6 Evidence）
