# M100 - Gateway Channel 系统 + 入站四步流水线

## 前置阅读
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/ROADMAP.md`
- 已在编码前阅读：`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`

## 任务拆分
- [x] 在 M100 worktree 内先跑 baseline，确认当前失败面。
- [x] 设计并实现 ChannelAdapter 协议与消息 envelope。
- [x] 实现 channel_registry/bootstrap，支持 start_channels()/stop_channels()。
- [x] 实现 session_keys + session_binding_store。
- [x] 实现 run_queue，保证同会话串行 FIFO、跨会话并行。
- [x] 实现 outbound_router，按 reply_context 回发原通道。
- [x] 实现 inbound_pipeline，完成 Agent 路由 → 会话键 → 串行队列 → 出站回发。
- [x] 增加模拟 channel/kernel 的单测，验证四步流水线与串并行策略。
- [x] 顺手修复 baseline 暴露的 ToolRegistry 回归，避免新 milestone 交付被旧红灯阻塞。
- [ ] 运行目标测试并整理提交、合并、看板更新、worktree 清理。

## 范围约束
- 仅修改 M100 Gateway Channel system / inbound pipeline 所需代码、测试、TASKS/PROGRESS。
- 不扩展到 heartbeat、WebSocket client、send_message、IM relay 等后续 milestone。
- 保持一个 canonical gateway 结构，不引入平行旧路径。
