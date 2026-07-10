# IM Specification

> 对齐: feat-447
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

`IM` 是**独立部署的可选中心服务**:内置 Web IM + 配置中心 + 消息中继。它让用户无需接入任何外部 IM 即可
完整使用 Multi-Agent 能力,并统一管理跨机器的 Agent 节点。它对外呈现两个面:

- **HTTP `/im/v1/*`**:账号/会话/消息/Agent 配置/节点/绑定/统计/策略,供浏览器前端调用。
- **WebSocket 两条**:`/im/ws/user`(浏览器用户维事件流)、`/im/ws/gateway`(Node Gateway 持久双向连接)。

对 IM 而言**人和 Agent 都是平等的消息参与者(Actor)**;对外接口以稳定业务标识(`user_id` / `agent_id` /
`conversation_id`)建模,不暴露内部路由主键。权限是**个人 owner 模型**:每个用户是自己所有节点/Agent 的
owner,用户之间数据隔离,无团队/组织 RBAC。

**显式不负责**:不执行 Agent 推理(交 agent 内核);不直接调用 agent 内核(经 Node Gateway 中继);不对接
外部 IM(由 Node Gateway 的 Channel 负责);不触发 heartbeat 调度(由 Node Gateway 本地控制);不持久化节点
的 runtime 能力目录(skills/tools/models 当场向在线网关解析,不入库)。IM 离线时外部 IM 主路径不受影响
(Node Gateway 本地自治)。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Auth and Tenancy](auth-tenancy.md) | JWT、refresh token、Bearer 鉴权、owner 隔离、policies | 3 |
| [Conversations and Messages](conversations-messages.md) | Actor 模型、shadow conversation、外部消息写入/可见性、消息排序、群会话、fork | 11 |
| [Web Chat UX](web-chat-ux.md) | 分页滚动、输入法、composer、消息菜单、桌面/移动一致性 | 6 |
| [Tool Timeline](tool-timeline.md) | 工具徽标/摘要/图标/详情、长输出、执行中状态、思考时间线、权限卡 | 8 |
| [Response Metrics](response-metrics.md) | 回复墙钟、工具聚合展示、token 缓存命中率 | 3 |
| [Agents and Nodes](agents-nodes.md) | AgentProfile、HEARTBEAT/cron RPC、节点绑定、workspace_root、user WS、runtime capability、node status | 10 |
| [Gateway Relay](gateway-relay.md) | gateway WS、relay ack、optional center、background notification、watchdog、authorization persistence | 6 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
