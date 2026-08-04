# gateway (personal_assistant) Specification

> 对齐: bugfix-496
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

`personal_assistant`(Node Gateway)是个人助手产品的**常驻进程节点网关**:把外部 IM / 内置 Web IM 的入站消息路由到正确的 Agent、进程内持有 `agent` 内核(经 `agent.sdk`)执行、把结果回发原通道,并跑本地 heartbeat / cron 两套主动机制、与可选的中心 IM 服务做配置同步与状态上报。它运行在用户机器上,通常在 NAT 后面。

它对外承担的可观察职责:① 终端用户在任一通道发消息能被正确的 Agent 处理、回复回到原通道原目标; ② 群聊只在被 @提及 / 回复 Agent / 控制命令时才触发 Agent;③ 运维者用启停命令把它当后台服务管理; ④ IM 服务在线时它主动连出、注册节点、周期心跳、同步配置、中继 Web IM 消息;⑤ IM 服务离线时外部 IM 主路径仍可用(本地自治);⑥ 进程重启后会话映射自动恢复,错过的 heartbeat / cron 周期不补跑回填。

**显式不负责**:不实现 Agent Loop、不直接调 LLM、不管会话持久化(都由内核负责);不做全局用户/组织管理(IM 服务负责);不提供终端 CLI 交互(coding_cli 负责)。它**只经 `agent.sdk`** 持有内核,禁止 import 内核内部(由 `tests/contract/` 把守)。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Routing and Delivery](routing-delivery.md) | 入站路由、群聊触发、/stop、运行中插话、配置边界、回复线程、会话映射、产品投递、失败反馈 | 11 |
| [Service Lifecycle](service-lifecycle.md) | 启停、IM WS、reconnect/ack、auto-bind | 5 |
| [Agent Capabilities](agent-capabilities.md) | 完整运行配置、模型配置、tool_allowlist、context window、Lark skill bundle | 6 |
| [Heartbeat and Cron](heartbeat-cron.md) | per-agent heartbeat / cron 开关、调度、错过周期语义 | 1 |
| [Relay Protocol](relay-protocol.md) | tool relay、skill usage RPC、附件透传、tool terminal events、图片、授权决策、cache/thinking、fork、配置边界与 shadow mirror | 11 |
| [External Channels](external-channels.md) | Feishu channel、IM 托管配置、多 Bot、listener lifecycle、trigger source、reply mirror、控制文本、群聊上下文、原生权限、shadow sync、offline autonomy、隔离 | 13 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
