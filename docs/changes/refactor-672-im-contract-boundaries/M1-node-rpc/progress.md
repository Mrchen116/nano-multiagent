# M1 实施与验证

- 迁移全部 21 个中心主动 RPC 到有限 NodeCommandMap；`nodeResponseTypes` 是逐命令覆盖清单，核对 control/onboarding/conversation-actions/personal-agent/work/Gateway 调用者及 Node handler。
- NodeRpc 持有 request ID、连接引用、期望响应、定时器与 shutdown；Gateway 在现有身份/生命周期检查之后才交入 accept。注册、Task 写屏障、其他上行分派保持原 owner。
- 配置/能力/预览/Task/cron/fork 等消费字段做真实校验，扩展内容保留 unknown；原 payload 不裁剪。配置字段采用产品 wire 类型，与后续 SQL 行和 HTTP 输入区分。
- 编译契约进入 IM typecheck，包含错误命令名、错输入、错输出、插件 action 等预期编译失败；不存在 string fallback。
- 既有 control/node-connection/e2e-control-work 保留（HTTP/WS/SQL 接线和鉴权风险）；新增 node-rpc 测试在最低传输 seam 覆盖错连接/响应、重复/迟到、非法字段、旧部分快照、离线/更新/超时/停服。无旧保护删除、无测试框架绕过。
- Node 24.22.1：IM typecheck（含 type-tests）通过；4 文件 32 tests passed：node-rpc、control、node-connection、e2e/control-work。源码直接运行的真实 IM 子进程使用隔离数据与随机端口，测试退出已关闭。
- M2 将把 malformed 配置回执拒绝与持久 operation 的 pending/recovery 对齐，并替换配置链剩余 Row/ImContext；M1 不是完整 unit 交付。
