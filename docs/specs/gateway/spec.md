# gateway (personal_assistant) Specification

> 对齐: feat-548
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

`personal_assistant`(Node Gateway)是个人助手产品的**常驻进程节点网关**:把外部 IM / 内置 Web IM 的入站消息路由到正确的 Agent、进程内持有 `agent` 内核(经 `agent.sdk`)执行、按工作模式处理结果投递,并跑本地 heartbeat / cron 两套主动机制、与可选的中心 IM 服务做配置同步与状态上报。它运行在用户机器上,通常在 NAT 后面。

它对外承担的可观察职责:① 终端用户在任一通道发消息能被正确的 Agent 接受，single_thread 的回复回到原通道原目标，全局 Agent 自主摄取 Inbox 并显式选择发言目标; ② 群聊按各 Agent 配置与命令寻址规则触发;③ 运维者用启停命令把它当后台服务管理; ④ IM 服务在线时它主动连出、注册节点、周期心跳、同步配置、中继 Web IM 消息;⑤ IM 离线时按模式保持本地自治，显式投递的可用性以目标链路为准;⑥ 进程重启后会话映射自动恢复,错过的 heartbeat / cron 周期不补跑回填。

**显式不负责**:不实现 Agent Loop、不直接调 LLM、不管会话持久化(都由内核负责);不做全局用户/组织管理(IM 服务负责);不提供终端 CLI 交互(coding_cli 负责)。它**只经 `agent.sdk`** 持有内核,禁止 import 内核内部(由 `tests/contract/` 把守)。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Routing and Delivery](routing-delivery.md) | 入站路由、逐消息时间与实际入口、会话控制与投递、后台 Agent / Workflow 原始返回、self-evolution 维护隔离与重放去重、PA 可读聊天副本 | 18 |
| [Global Agent](global-agent.md) | 跨聊天主上下文、Inbox 消费、成员查询、内部委派、显式发送、目标群复核与控制命令 | 10 |
| [Service Lifecycle](service-lifecycle.md) | 启停、macOS 登录自启与异常恢复、IM WS、reconnect/ack、auto-bind、默认本机 home/workspace、cache warning | 10 |
| [Agent Capabilities](agent-capabilities.md) | 完整运行配置、模型配置、推理能力、可恢复配置 operation、Skill 选择、self-evolution 调和、tool allowlist、全局固定基础工具与可选 Workflow | 16 |
| [Heartbeat and Cron](heartbeat-cron.md) | per-agent heartbeat / cron 开关、调度、错过周期语义与全局主/独立执行归属 | 2 |
| [Relay Protocol](relay-protocol.md) | active/idle 后台返回经既有消息协议精确绑定与透传 | 14 |
| [Workflows](workflows.md) | Web/外部 IM 的 Workflow 来源、能力开关、SDK 查询控制、权限路由与投递 | 5 |
| [External Channels](external-channels.md) | Feishu channel、富文本与多模态消息、IM 托管配置、多 Bot、listener lifecycle、trigger source、reply mirror、运行信息页脚、控制文本、群聊上下文、原生权限、shadow sync、offline autonomy、隔离 | 15 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
