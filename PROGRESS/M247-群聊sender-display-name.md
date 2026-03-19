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
- Next: R2 — web_relay_adapter 解析 sender.display_name
