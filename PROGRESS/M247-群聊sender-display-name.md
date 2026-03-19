# M247 进度记录

## Milestone: M247 群聊 sender 显示名：传递用户 display name 替代原始 ID

### 全局设计决策
- relay_service 是 display_name 解析的唯一来源（IM 层拥有 users 和 agent_profiles 表访问权）
- gateway 只做透传，不查询 IM 数据
- web_relay_adapter 解析 sender.display_name 并放入 InboundMessage.metadata
- inbound_pipeline 从 metadata["sender_display_name"] 读取，fallback 到 external_user_id
- communication_context hook 从 session_metadata["participants"] 读取结构化列表
- 向后兼容：老 payload 无 sender 字段时，各层 fallback 到 id

---

### R1.1 relay_service 添加 sender/participants 字段
- Context: 群聊 relay payload 中 sender 只有 sender_user_id（UUID），agent 无法用可读名字展示发言人。
- Decision: 仅 group 类型 payload 添加顶级 `sender: {id, display_name, type}` 和 `participants: [{id, display_name, type}]`；直聊不变（backward compat）。display_name 从 users 表解析；agent 类型用户优先从 agent_profiles.display_name 获取。
- Rationale: relay_service 唯一持有 users+agent_profiles 表访问权，是解析 display_name 的正确位置；gateway 只做透传。
- Evidence:
  - Tests: 3 new unit tests 全绿，IM suite 56 unit+contract 全绿，5 个集成失败与基线一致（预存在）
  - Entry: `payload["sender"]["display_name"]` 读取 users.display_name，fallback 到 user_id
- Rollback: 回退到 test(R1.1) commit
- Commits: C1=226bdef, C2=a483f78, C3=（待写）
- Next: R2 — web_relay_adapter 解析 sender.display_name — DONE

### R2.1 web_relay_adapter 解析 sender_display_name 和 participants
- Context: RelayEnvelope 无 sender_display_name 字段；InboundMessage.metadata 不含 sender_display_name/participants。
- Decision: RelayEnvelope 新增 `sender_display_name: str | None` 和 `participants: list[dict]`（default None，`__post_init__` 归一化为 []）；`_parse_relay_payload` 从 `payload["sender"]["display_name"]` 提取；`_build_inbound` 将两个字段注入 `extra` dict（仅非空时）。
- Rationale: gateway 只透传，不查询；保持 metadata key 为 None 时不注入，维持旧 payload 的 metadata 洁净。
- Evidence:
  - Tests: 全部 adapter 测试 13 passed，im_service unit+contract 56 passed，personal_assistant unit 220 total 全绿
  - Entry: `inbound.metadata["sender_display_name"]` 可直接读取
- Rollback: 回退到 R1.1 C3 commit
- Commits: C1=50eee46, C2=540cb33, C3=（待写）
- Next: R3 — inbound_pipeline 使用 display_name 替代 UUID — DONE

### R3.1 inbound_pipeline 使用 sender_display_name 替代 UUID
- Context: pipeline 一直从 `message.external_user_id`（UUID）生成 `[sender]` 前缀，可读性差。
- Decision: 新增 `_resolve_sender_label(message)` helper，从 `metadata["sender_display_name"]` 读取（fallback 到 `external_user_id`）；在 buffer append 和 `_format_sender_text` 两处替换使用。
- Rationale: 单点逻辑，不污染现有 fallback；gateway 不查询 IM，仅透传。
- Evidence:
  - Tests: M246 file 10 passed，unit+im_service 270 passed，5 pre-existing failures 与基线一致
  - Entry: `[Alice Chen] @agent-a hello` 替代 `[uuid-alice-raw] @agent-a hello`
- Rollback: 回退到 R2.1 C3 commit
- Commits: C1=5af1fdd, C2=553f730, C3=（待写）
- Next: R4 — communication_context hook 更新 participants 格式
