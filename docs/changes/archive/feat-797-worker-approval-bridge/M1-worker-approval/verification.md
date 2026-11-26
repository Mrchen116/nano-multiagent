# 审批桥验证

基线 bf20e1da2。Node 24.22.1、pnpm 11.7.0。先构建 product-contracts、dsh-integration。macOS 本地测试用 realpath 解析 TMPDIR，避免同一项目说明经 /var 和 /private/var 被重复加载；未修改基线在默认临时目录同样触发 approval.test.ts 的去重断言。

| 边界 | 复现与结果 |
|---|---|
| 三种原生协议 | local-worker-{drivers,antigravity,conformance,permissions}.test.ts 四套共 19 项通过。本机真实 stdio 子进程模拟各协议。覆盖一次答复、并发撤回、拒绝和终局、较宽授权选项、业务选择题、MCP 来源冲突。Codex 0.171.0 本地生成 schema 核实单次 accept 与 turn/session scope 不同。 |
| 根会话和模型输入 | external-worker-approval.test.ts 启动 DSH runtime、两个 CLI 协议子进程和 fixture 模型。A 派工后根转到 B，AGY 实际出站输入保存 A 的原话/来源，B 不在派工证据快照。审核中撤回使旧 allow 失效。Codex 成功没有宿主模型调用。真人点过的请求重复 approval.answer 被拒绝，无人值守不发卡。明确拒绝和证据过期在 unattendedFallback=allow 时仍被阻断。 |
| 投递与身份 | worker-approvals.test.ts、runtime-partitions.test.ts、worker-permission-cards.test.ts。真实 IM HTTP/WebSocket、独立 SQLite。普通 Global 与 PA 主人、owner_id 与 user_id 不同、飞书群和 shadow 隔离、回执前点击、拒绝其他人/串卡、过期回收、禁用/节点换代。 |
| 主人浏览器答卡 | 隔离 IM 和产品 WorkerApprovals、真实 DSH 进程、fixture Codex app-server、Chromium。根完成委派后处理另一个聊天，CLI 发起 ls /review-target。浏览器进入真实主人私聊并点击允许一次，经 HTTP、node.streaming_delta、approval.answer，CLI 实收 accept。刷新后终态和动作可读且无按钮。另跑取消场景，刷新后看到已取消，仍无按钮。每次关闭独立浏览器、节点连接和临时 IM，未使用生产数据。|
| 客户端 | Web message-pane 组件套件 114 项通过。iOS 现有 ChatPermissionCard 使用 question、tool_input、options 和 resolved 状态；已检查实现及协议，本次未运行模拟器或真机 UI。|
| 外部账号 | 已检查安装的 CLI 协议，测试模型和 Worker 动作可控。未向已登录的 Codex、Claude 或 Antigravity 云端账号发送业务任务。|
