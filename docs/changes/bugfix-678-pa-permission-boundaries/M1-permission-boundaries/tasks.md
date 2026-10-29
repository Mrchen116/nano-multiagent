# M1 实施与验证

- [x] 审核入口 / review-session / context 职责拆分；原生只读调查与原话保留。
- [x] 消息级准入状态、显式重审及当前消息截止上下文。
- [x] PA 事件沟通、真实回执、冻结动作提交及图片字节校验。
- [x] 保留 Agent 原生重试，补独立模型请求恢复。
- [x] 隔离数据库迁移 plan/apply/verify 与回滚验证。
- [ ] 独立 code review + verification / Context Implementation Review。
- [ ] 固定日常模板 R1–R8 产品回归验收。
- [x] 按用户纠偏及设计 R4 使用原生图片输入，R2/R6 真实图片成功与拒绝路径补验。
- [ ] 最终本地 CI、canonical spec 归并、归档与 Ready PR。

## 测试策略

保留原生 DSH 子进程与宿主公开 RPC seam；修改 task-execution 的旧“拒绝阻断”断言为合法替代继续。原有 codex 生命周期、披露、PA、Inbox 测试扩展现有风险。新增 retained-instructions、standalone-model-retry、input-admission、personal-input-context、personal-images 分别保护原话保留、独立请求恢复、消息状态、服务端截止、冻结字节。迁移测试保护部署入口幂等、备份与事务回滚。真实模型能力与受控 provider 故障回归分别报告，不以 fixture 图片计费代替真实路由。
