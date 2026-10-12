# IM Specification

> 对齐: feat-587
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端(内置 Web IM)、原生 iPhone 客户端、Node Gateway(`personal_assistant`)、终端用户,以及 `tests/im_service/` 里的契约测试。

## Purpose

`IM` 是多人协作的即时通讯中心服务:提供账号体系、会话/消息持久化、浏览器 Web IM、Agent / Node 配置中心, 并通过 Gateway 主动建立的 WebSocket 连接把用户消息中继到本地 Agent、把回复与过程事件实时推回浏览器。

它对外承担的可观察职责:① 用户注册即拥有私人空间，团队申请获批后另取得公司资源访问；聊天叠加成员关系，全局 Agent Work 继承 Agent 的固定空间;② direct/group 会话与消息历史稳定持久化; ③ 浏览器实时收发消息、展示工具/思考过程和响应指标，全局 Agent 的内部轨迹在工作视图呈现;④ 用户管理自己所属的 Agent 配置与多个 Node 绑定;⑤ Gateway 在线时双向中继、离线时明确降级;⑥ 外部 channel 会话可镜像为 shadow conversation。

**显式不负责**:不执行 Agent、不调用 LLM、不读取 Gateway 本地 workspace、不直接接飞书等外部 channel; 这些由 `personal_assistant` 承担。IM 与 `agent` 包之间零 import,与 Gateway 只走 HTTP/WebSocket 协议。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Auth and Tenancy](auth-tenancy.md) | 持久 JWT 会话、私人空间、公司准入与停用、认证限流、资源授权与系统 policies | 10 |
| [Conversations and Messages](conversations-messages.md) | 会话/消息 CRUD、受保护附件与累计容量、配置边界、outbox、群聊、分页、fork、限定公网入口 | 25 |
| [Web Chat UX](web-chat-ux.md) | 历史加载、配置边界、滚动、输入、未发送内容按会话隔离、slash 控制命令、消息操作、Agent 内联图片、图片 attachment 预览、conversation skill 蒸馏入口、响应式体验、身份展示与自进化提示本地化 | 22 |
| [iOS Client](ios-client.md) | 原生业务与权限、会话恢复与退出隔离、媒体选择与分享、前后台提醒边界、免费个人安装说明 | 5 |
| [Tool Timeline](tool-timeline.md) | single_thread 消息内过程、真实后台返回、群回复复核与两种模式共享展示边界 | 9 |
| [Agent Work](agent-work.md) | 按 Agent 空间可读的全局主工作轨迹、关联子执行、明细与持久回看、只读原生轨迹 | 5 |
| [Workflows](workflows.md) | Workflow 在既有 tool、permission、slash 与普通消息 surface 中的呈现和开关 | 2 |
| [Response Metrics](response-metrics.md) | 墙钟耗时、气泡指标、缓存命中率 | 3 |
| [Agents and Nodes](agents-nodes.md) | 首次安装与助手引导、Agent 配置、创建工作模式、能力选择、公开联系人与管理入口、节点绑定、设备归属标注与 Workflow tool pill | 31 |
| [Gateway Relay](gateway-relay.md) | 消息中继与回执、配置边界、两种工作模式的投递与过程归属、后台返回持久化和重放去重 | 12 |
| [Task Graphs](task-graphs.md) | 私人或公司目标、真实主体维护与明确删除、跨群活动、逐节点回聊、依赖与衍生 | 9 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
