# gateway (personal_assistant) Specification

> 对齐: refactor-653
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

`personal_assistant`(Node Gateway)是个人助手产品的**常驻进程节点网关**:把外部 IM / 内置 Web IM 的入站消息路由到正确的 Agent、通过产品 RuntimePort 接入由 Node 管理的 DSH 子进程执行、按工作模式处理结果投递,由 PA 管理 Heartbeat 策略并接入 DSH 原生 Cron 调度、与可选的中心 IM 服务做配置同步与状态上报。它运行在用户机器上,通常在 NAT 后面。

它对外承担的可观察职责:① 终端用户在任一通道发消息能被正确的 Agent 接受，single_thread 的回复回到原通道原目标，全局 Agent 自主摄取 Inbox 并显式选择发言目标; ② 群聊按各 Agent 配置与命令寻址规则触发;③ 运维者用启停命令把它当后台服务管理; ④ IM 服务在线时它主动连出、注册节点、周期心跳、同步配置、中继 Web IM 消息;⑤ IM 离线时按模式保持本地自治，显式投递的可用性以目标链路为准;⑥ 进程重启后会话映射自动恢复,Heartbeat 错过周期不补跑；Cron 使用原生持久调度并按一次性/周期语义恢复。

**显式不负责**：不实现 Agent Loop、不直接执行模型/工具、不代管原生执行日志；这些由 DSH 负责。IM 拥有账号、私人/公司空间与聊天。Node 管理运行时子进程；PA 通过产品 RuntimePort 接入，只有 integration 使用公开 DSH exports。旧 Coding CLI 已退役，边界见 [SPEC](../../../SPEC.md)。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Routing and Delivery](routing-delivery.md) | 入站路由、逐消息时间与实际入口、会话控制与图文投递、后台 Agent / Workflow 原始返回、self-evolution 维护隔离与重放去重、按需原始历史导出 | 22 |
| [Global Agent](global-agent.md) | 跨聊天主上下文、Inbox 消费、成员查询、内部委派、显式发送、目标群及私聊复核与控制命令、任务过程沟通与内部收尾 | 19 |
| [Service Lifecycle](service-lifecycle.md) | 同源安装与空节点设置、主动更新和回退、节点启停、独立 Agent 停用与只读管理、macOS 登录自启与异常恢复、IM WS、reconnect/ack、auto-bind、默认本机 home/workspace、cache warning | 14 |
| [Agent Capabilities](agent-capabilities.md) | 直接真人来源语义、网页模型服务管理与验证、完整运行配置、模型配置、推理能力、可恢复配置 operation、Skill 选择、self-evolution 知识归属、当前读取、联合复盘和跨会话 F4、完整Feature依赖与独立工具开关、占用保护、tool allowlist、全局固定基础工具、workspace 自建插件管理、默认无摘要换窗与按需恢复、开发指导与可选 Workflow、通用交互表达与背景理解、原生 Goal 默认关闭及显式开启 | 46 |
| [Heartbeat and Cron](heartbeat-cron.md) | per-agent heartbeat / cron 开关、有效责任保护、独立调度工具、调度、错过周期语义与对应原生主会话归属 | 5 |
| [Relay Protocol](relay-protocol.md) | active/idle 后台返回经既有消息协议精确绑定与透传、只读原生轨迹观察、断连重连持久诊断 | 22 |
| [Workflows](workflows.md) | Web/外部 IM 的 Workflow 来源、能力开关、运行时查询控制、权限路由与投递 | 9 |
| [External Channels](external-channels.md) | Feishu channel、富文本与多模态消息、IM 托管配置、多 Bot、listener lifecycle、trigger source、reply mirror、运行信息页脚、控制文本、群聊上下文、原生权限、shadow sync、offline autonomy、隔离、限定附件来源 | 17 |
| [Task Graphs](task-graphs.md) | 会话内任务协作、真实 Agent 授权、本人全层持续责任、有效等待、停止恢复、停用冻结与真人指定恢复、原子修改与未知回执 | 20 |
| [Personal Agent](personal-agent.md) | 可信主人与参与关系、双身份历史、观察背景批次、来源限制与对外披露边界、代表用户发送与原委托延续；通用能力复用 Global | 11 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
