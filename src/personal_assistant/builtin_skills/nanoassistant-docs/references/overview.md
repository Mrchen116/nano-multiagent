# 产品定位与核心概念

Nano Personal Assistant 是一套在用户自己的节点上运行、配置和协作多个长期 Agent 的个人助手产品。

- Web IM 是默认入口：负责账号、会话、消息、Agent/节点配置和状态展示。
- Gateway 运行在用户节点上：主动连接 IM，接收消息，在本机执行 Agent，再把回复送回原入口。
- Agent 是可长期识别和配置的主体：拥有稳定身份、独立工作区、会话历史、skills、tools 和 memory。
- 飞书等外部渠道扩展触达范围，但不是使用 PA 的前置条件。
- heartbeat 与 cron 让 Agent 主动工作；权限、运行状态、历史和中断能力让行动保持可见、可控。

PA 不等同于终端 Coding CLI。本手册只覆盖个人助手所需的 Web IM、Gateway、Agent 和外部渠道产品表面。

## 核心概念

| 概念 | 含义 |
|---|---|
| IM / Web IM | 中心账号与消息服务及其浏览器界面。保存会话、消息和期望配置，不执行 Agent。 |
| Node | 用户拥有的一台运行节点，在 Web IM 中完成绑定并上报在线状态。 |
| Gateway | Node 上的常驻个人助手进程。主动连接 IM，托管本机 Agents、调度器和外部渠道。 |
| Agent | 长期助手主体。配置模型、提示词、skills、tools、features 和工作区。 |
| Workspace | Agent 在 Node 上的本地目录，保存会话、memory、任务和 Agent 自有资源。 |
| Conversation | 用户、Agent 或群组之间的连续聊天。历史与实时事件最终汇成同一条时间线。 |
| Channel | Web IM 或飞书等消息入口。回复通常回到触发它的原通道和原目标。 |
| Skill | 按需加载的专业说明或工作流；模型先看到名称与描述，命中后用 `skill_view` 读取入口，再按入口指引读取所需资料。 |
| Tool | Agent 可实际调用的操作能力。每个 Agent 的 tool allowlist 决定本轮能执行哪些工具。 |
| Workflow | 可选的多 Agent 编排工具。仅在 Agent 启用且用户明确 opt-in 后运行；详细用法见 [Workflow 手册](workflows.md)。 |
| Memory | 跨会话保留的稳定用户偏好和环境事实，不等同于当前任务进度或聊天历史。 |
