# M172 - 修复 canonical 直聊消息已送达但 agent 不回复

## Roadpoints
- [x] 定位 direct-chat 已送达但 agent 不回复的链路断点。
- [x] 用最小单测复现 reply lifecycle 因缺失 `message_id` 无法完整上报的问题。
- [x] 修复 canonical relay adapter，确保 direct-chat relay.message 把原消息 id 透传到 gateway pipeline 元数据。
- [x] 回归 gateway adapter / pipeline 单测，确认 accepted/running/completed 生命周期仍成立。
- [ ] 追加 fresh canonical runtime 最小验证，证明 direct-chat 可触发 agent reply 且事件链路完成。
- [ ] 整理 PROGRESS、提交记录与 merge readiness。

## Scope guard
- 仅收口 canonical direct-chat runtime no-reply blocker。
- 不修改 `data/dev-tasks.json`。
- 不依赖启动后手工补 runtime 状态。
