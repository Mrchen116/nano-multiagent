# bugfix-453-M1: duplicate thinking visibility

## 目标

修复内部 Web IM 过程区在一轮 LLM response 返回一份 thinking + 多个 tool calls 时重复展示同一份 thinking 的问题。

## 退出标准

1. 单轮 provider response 中同一份 reasoning 被展开到多个 assistant tool-call message 时，新消息只产生一条用户可见 thinking 过程项。
2. 多轮 LLM request 各自产生相同文本 reasoning 时，仍按真实轮次显示多条 thinking。
3. provider 历史回传所需 `reasoning_content` / `reasoning_signature` 不丢失，避免破坏 Anthropic/Kimi thinking round-trip。
4. 不迁移、不清洗、不补救历史已落库重复 thinking。
5. 窄单测和相关回归测试通过。

## 测试策略

- C1：新增回归测试复现单个 assistant response group 内多条 assistant message 共享同一 thinking 时重复产生用户可见 thinking。
- C2：在展示/过程事件边界做最小修复，保留 provider 历史回传字段。
- C3：补齐 `fix.md` 的修复/验证段与本进度文档。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测：复现同一 response group 内 duplicate thinking | DONE |
| R2 | C2 实现：只展示一次同 response thinking，保留历史 round-trip | DONE |
| R3 | C3 验证与文档回填 | DONE |
