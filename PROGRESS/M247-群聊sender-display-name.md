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

<!-- Roadpoint 记录将追加在此 -->
