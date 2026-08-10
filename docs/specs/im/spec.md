# IM Specification

> 对齐: feat-519
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端(内置 Web IM)、Node Gateway(`personal_assistant`)、终端用户,以及 `tests/im_service/` 里的契约测试。

## Purpose

`IM` 是多租户即时通讯中心服务:提供账号体系、会话/消息持久化、浏览器 Web IM、Agent / Node 配置中心, 并通过 Gateway 主动建立的 WebSocket 连接把用户消息中继到本地 Agent、把回复与过程事件实时推回浏览器。

它对外承担的可观察职责:① 用户注册/登录后只能看到自己的数据;② direct/group 会话与消息历史稳定持久化; ③ 浏览器实时收发消息、展示工具/思考过程和响应指标;④ 用户管理 Agent 配置与 Node 绑定;⑤ Gateway 在线时双向中继、离线时明确降级;⑥ 外部 channel 会话可镜像为 shadow conversation。

**显式不负责**:不执行 Agent、不调用 LLM、不读取 Gateway 本地 workspace、不直接接飞书等外部 channel; 这些由 `personal_assistant` 承担。IM 与 `agent` 包之间零 import,与 Gateway 只走 HTTP/WebSocket 协议。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Auth and Tenancy](auth-tenancy.md) | JWT、owner 隔离、系统 policies | 3 |
| [Conversations and Messages](conversations-messages.md) | 会话/消息 CRUD、shadow conversation、配置边界、outbox、群聊、分页、fork | 15 |
| [Web Chat UX](web-chat-ux.md) | 历史加载、配置边界、滚动、输入、slash 控制命令、消息操作、图片 attachment 预览、conversation skill 蒸馏入口、响应式体验与自进化提示本地化 | 15 |
| [Tool Timeline](tool-timeline.md) | tool/reasoning 实时状态、展示、权限卡、长输出 | 8 |
| [Response Metrics](response-metrics.md) | 墙钟耗时、气泡指标、缓存命中率 | 3 |
| [Agents and Nodes](agents-nodes.md) | agent 配置保存与实际采用、Skill 选择与分组、可见专属说明与稳定提示词预览、创建/配置 UX、外部 channel 控制面、skill_view、产品说明书、skill usage、heartbeat/cron、能力、节点绑定/状态、托管默认 workspace | 23 |
| [Gateway Relay](gateway-relay.md) | WS 协议、配置边界事件、幂等回执、离线降级、后台通知、自进化通知归因、liveness、授权决策 | 11 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
