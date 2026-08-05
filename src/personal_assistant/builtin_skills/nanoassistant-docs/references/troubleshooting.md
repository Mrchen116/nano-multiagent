# 故障排查

先保留首个错误、当前 config 绝对路径和运行身份，再执行恢复。不要一遇到问题就重启全部服务，否则会丢失最有价值的因果证据。

按以下顺序排查：

1. 确认当前命令属于哪个安装或 checkout，Gateway 使用哪份 config，浏览器访问哪个 IM 地址。
2. 用 OpenAPI 检查 IM HTTP；再确认 Web IM 静态页面是否存在。
3. 交叉核对 `.gateway-state.json`、live process 和 `gateway.log` 是否属于同一 config 与同一次启动。
4. 查看节点是否已绑定、是否 online，以及日志中的 `ACTION`、`NEXT` 或第一个启动错误。
5. 最后走一次真实路径：登录、打开会话、发送消息、收到回复。

| 症状 | 优先检查与处理 |
|---|---|
| `/` 或 `/chat` 打不开 | 检查 IM 进程、8011 监听和 `/openapi.json`；端口占用时先确认占用者。 |
| OpenAPI 可达但页面不存在 | 检查 Web IM 静态构建是否随当前安装提供。 |
| Gateway 启动后立刻退出 | 阅读 `gateway.log` 第一个错误；检查必填 `llm`、provider 协议、web_relay 和 IM 地址。 |
| `gateway already running` | 使用同一 config 的 `restart`，不要再启动第二实例。 |
| `NOT RUNNING` / `STALE` | 确认 stop 使用与 start 相同的 `--config`；保留旧日志后重新启动。 |
| 浏览器要求绑定 | 按 `gateway.log` 的 `NEXT Open ...`，用当前登录 owner 完成确认。 |
| Web IM 显示 Gateway offline | 检查 Gateway 进程、IM WebSocket、节点页 `last_error`；恢复后验证消息往返。 |
| Agent 能力为空或接口 503 | 检查是否有旧 Gateway、重复 node_id 或目标 Gateway 尚未完成注册。 |
| `workspace_root does not exist` | 创建 config 中的准确目录，或移除显式路径使用默认 workspace。 |
| Agent 不回复或 LLM 报错 | 核对实际 `default_model`、provider 协议、上游健康和本次 LLM 日志。 |
| 飞书保存后未连接 | 查看通道 runtime diagnostics、节点 online、App 凭据、Bot/长连接设置和权限；修正后重连。 |
| 飞书群普通消息没进入上下文 | 检查 `im:message.group_msg` 是否已授权。 |
| 产品回答与现场不一致 | 明确记录差异，以已核实的现场事实描述本机；不要静默把手册或猜测当作运行事实。 |

恢复时只对目标 config 执行 stop/restart。状态文件中的 PID 未通过 live process birth 校验时，不要向该 PID 手工发信号。整套服务关闭时先停 Gateway，再停 IM；恢复后重新验证节点 online 和一次真实消息往返。
