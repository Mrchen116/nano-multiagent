# M1-fix 实施块

- [x] 只补七处 description，保留系统提示词与服务语义。
- [x] 构建、既有聚焦覆盖与实际模型请求核对。
- [x] 三个干净全局 Agent 保存自然三步计划，并核对持久图。
- [x] 核对一轮原图增量修改，清理隔离栈与身份配置。
- [x] 完成本地 docs/diff 交付检查。
- [ ] 主会话独立 code review、用户亲测确认及后续交付。

## 测试策略

保护风险是 Agent 从真实工具接口生成参数时重复试错，以及依赖方向错误。入口描述属于模型引导，精确字符串快照不能证明理解；不新增永久文案断言。既有 `task-graph-permission.test.ts`、`capabilities.test.ts`、`apps/im-server/tests/task-collaboration.test.ts` 保留，保护工具接线、权限与持久协作边界。真实 LLM 脚本仅作本次 output 证据，不放进永久套件。
