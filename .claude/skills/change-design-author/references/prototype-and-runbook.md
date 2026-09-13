# 前端原型与验收前置

仅前端 UI/交互变化需要原型。基于当前页面、组件、状态和适用 viewport，记录需继承的布局、信息层级、交互与视觉约束；重做既有 UX 必须是已确认的设计决定。

`prototype.html` 可含演示 JS，不接真实后端、不代替产品实现。design 的“前端原型”段链接它，并用表说明：区域/状态、`must-match | may-adapt | out-of-scope`、真实产品入口、viewport/状态、milestone 退出标准。

- must-match 的结构/交互语义必须保留；样式可遵循项目设计系统。
- may-adapt 写清可调整内容；out-of-scope 写清真实产品会呈现什么。
- 每个 must-match 都投影到 `[reviewer]` 用户结果与 `[worker]` 可复查的原型对照证据。

Runbook for Reviewer 列出本 unit 相关服务的停止、启动/构建和健康检查命令，以及真实入口驱动方式。不改客户端面时可用客户端实际调用的同一接口；改客户端面必须驱动真实客户端。

从必验旅程确定账号、凭据、测试租户、外部对象、权限或硬件的来源和可用性；没有则写“无”。未落实的必验资源阻塞 Gate 2；只有用户明确调整验收范围或授权替代验证后才能改变标准。运行隔离遵循 [worktree-runtime](../../../../docs/development/worktree-runtime.md)。
