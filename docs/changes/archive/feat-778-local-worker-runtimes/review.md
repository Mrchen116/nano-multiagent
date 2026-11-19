# feat-778 交付审查

## 版本与范围

独立审查从 `76b14cfce`（develop）检查本机 worker 实现和四份契约 delta，在 `015f3e1c5` 完成整体验证，并复核到 `d60faf5f0`。最后一笔改动保留 Work RPC 接收者，更新两处原生恢复测试。独立审查者回报无未关闭缺陷，四份 delta 与 canonical 一致。

| 问题 | 验证人及方法 | 观察 |
|---|---|---|
| 派工、权限、关系投影与恢复 | 独立代码与契约审查 | 核对三种框架、机器配置、原会话续派、停止、Auto 剩余请求、父级身份、持久状态与旧轨迹入口。集成构建及 56 项相关测试通过。 |
| worker 实际上下文与 Dreaming 来源 | 独立 Context 审查 | 亲读受控 provider 收到的 Global 与 PA 工作首轮、工具后和冷续做请求，以及 document／legacy worker 与 Dreaming 请求。worker 有任务、父级回报入口与授权边界。记忆指导和工具由 root 消费；Dreaming 可见 root 收到的汇报，查询来源只列 root。 |
| 本机登录、模型、工具和控制 | 实施者用真实 CLI 实测 | Codex CLI 0.169.1 使用本机默认账号与模型。Claude Code 2.1.325 使用隔离的 Anthropic Messages 到 OpenAI Responses 适配服务与 gpt-6.2-sol。两者均在独立目录读取随机文件，使用 MCP 回报、中途接受更正、恢复原会话，并在等待工具期间确认停止。权限拒绝、错误和重复通知另有可控协议对端回归。 |
| 从 IM 到回复，再看派工图 | 实施者，隔离 daily 栈和真实 Chrome | 同一台机器先由普通 Global 与 PA 分别派出 Codex。改为 Claude 并重启后，在原 Global 聊天补充要求，原 Codex worker ID 保持一致并返回新的随机码；另交独立事项则出现新 Claude worker。实际图上两个不同 ID 都为 completed，均有框架、标题、状态。另从工程 Global 观察 Claude 活动与完成，打开根轨迹核对回报和公开投递。旧 DSH 入口另在隔离 HTTP 图中核对。 |

## 记录与范围

真实 CLI 端到端由实施者执行。独立审查亲读的是实际 DSH 发出的受控模型请求，并另外查看了派工图截图。OpenAI 测试适配服务仅用于该次 Claude 实测，测试凭据和账号设置未写入仓库。当前交付待用户亲自试用。跨机派工另行决定。
