# PROGRESS: M246 — 群聊 buffer 消息结构化

## 整体决策

- GroupContextStore.drain() 返回 `list[tuple[str, str]]` (sender, text)
- InboundPipeline 在 gateway 层完成 `[sender] text` 格式化，内核收到的仍是普通 text parts
- Runtime 将 parts 列表每个 part 作为独立 user message 追加 history（而非 \n join）
- parts 长度=1 时单 user message 行为不变（向后兼容）
- Communication Context 增加 message_format 说明行（仅群聊）

---

## Roadpoint 记录

（各 Roadpoint 完成后补充）
