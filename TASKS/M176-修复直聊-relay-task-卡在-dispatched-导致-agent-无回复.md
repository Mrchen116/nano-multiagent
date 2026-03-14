# M176 - 修复直聊 relay task 卡在 dispatched 导致 agent 无回复

## Roadpoints
- [ ] 复盘 M172/M174 后直聊链路，锁定 relay task 长期停在 `dispatched` 且浏览器只见用户消息 `Sent` 的真实断点。
- [ ] 用最小回归覆盖该断点，优先验证 `relay_tasks` / `conversation_events` / 浏览器消息映射之间的闭环缺失。
- [ ] 以最小改动修复 receipt 或等价完成证据缺口，确保旧/新会话都能稳定看到 agent 回复。
- [ ] 跑最小充分测试与真实验证，并把全绿证据记录到 `PROGRESS/M176-修复直聊-relay-task-卡在-dispatched-导致-agent-无回复.md`。
- [ ] 完成提交、合并 `main`、push，并清理 worktree。

## Scope guard
- 仅处理 M176：真实 Web IM 直聊 relay task 卡在 `dispatched`、agent 不回复、M149 无法复验的问题。
- 不修改 `data/dev-tasks.json`。
- 不扩散到其他 Milestone 的产品改版。
