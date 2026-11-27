# IM Specification

> 对齐: feat-794
>
> 写法与归并规则见 [长青行为契约编写规范](../CONTRIBUTING.md)。

## Purpose

`IM` 是多人协作的即时通讯中心服务:提供账号体系、会话/消息持久化、浏览器 Web IM、Agent / Node 配置中心, 并通过 Gateway 主动建立的 WebSocket 连接把用户消息中继到本地 Agent、把回复与过程事件实时推回浏览器。

它对外承担的可观察职责:① 新注册用户可立即使用个人空间，加入公司须申请并获批；有效公司成员可查找公司内的人和设为「团队公开」的 Agent，聊天读取遵循会话公开范围、成员及只读观察资格、写入要求成员资格且受对端私有助手隔离约束，有效公司成员名下设为「团队公开」的普通全局 Agent Work 与原生轨迹对有效公司成员完整开放，设为「私有」的 Agent 对其他成员隐藏且不开放外部通信与 Work，PA 私人配置与 Work 按 [Personal Agent](personal-agent.md) 保持主人可见;② direct/group 会话与消息历史稳定持久化; ③ 浏览器实时收发消息、展示工具/思考过程和响应指标，全局 Agent 的内部轨迹在工作视图呈现;④ 用户管理自己所属的 Agent 配置与多个 Node 绑定;⑤ Gateway 在线时双向中继、离线时明确降级;⑥ 外部 channel 会话可镜像为 shadow conversation。

**显式不负责**:不执行 Agent、不调用 LLM、不读取 Gateway 本地 workspace、不直接接飞书等外部 channel; 这些由 `personal_assistant` 承担。与 Gateway 的通信使用 HTTP/WebSocket，跨包依赖边界见[仓库架构](../../../SPEC.md)。

**Web 前端的体验方向是[活泼亲和](../../product/web-im-principles.md#crewden-的视觉风格)。** 为降低第一次接触 Agent 协作的陌生感，访客能从[一件具体的团队工作](auth-tenancy.md#scenario-协作示例与真实工作明确区分)看懂谁在协作；开始设置后，用户只需理解眼前这一步。进入[首次私聊](personal-agent.md#首次建立合作约定)就可以尝试一件自己的小事，介绍背景和商量长期职责都由用户选择时机。

## Canonical Areas

本包长青行为契约按 area 拆分维护。`spec.md` 是入口索引;具体 Requirement/Scenario 以同目录下的 area 文档为准。

| Area | Covers | Requirements |
|---|---|---|
| [Auth and Tenancy](auth-tenancy.md) | Crewden 官网（含多端客户端智能下载入口）与认证入口、持久 JWT 会话、公司准入与停用、认证限流、成员可见性、资源管理归属、账号设置与系统策略预设 | 16 |
| [Conversations and Messages](conversations-messages.md) | 会话/消息 CRUD、回执、卡片预览、受保护附件与累计容量、配置边界、outbox、群聊与私有助手成员互斥、外部历史私聊只读与可逆恢复、外部 Worker 主人私聊审批、分页、fork、限定公网入口、私聊交互背景与群聊明确提交、通用草稿仅填入输入框 | 41 |
| [Web Chat UX](web-chat-ux.md) | 应用内新消息来源提醒、聊天日期与时间分隔、聊天搜索、会话切换与阅读位置恢复、历史加载、配置边界、滚动、输入、未发送内容按会话隔离、slash 控制命令、消息操作、Agent 正文换行与内联图片、图片 attachment 预览、conversation skill 蒸馏入口、响应式体验、身份展示、自进化提示及摘要本地化、页面入口缓存、连续交互探索、面板自适应消息布局、Open Intelligent UI 表达与发布前诊断 | 38 |
| [iOS Client](ios-client.md) | 原生业务与权限、通用交互与私人状态、本地聊天首绘与离线阅读、按账号和服务隔离、未确认发送迁移、持久发送恢复与退出隔离、媒体与提醒、安装维护、聊天阅读连续性与 Agent 停用、首次交办与助手公开/私有权限设置、引用定位、原生 Work 与助手管理 | 20 |
| [Desktop Client](desktop-client.md) | macOS Apple Silicon 与 Windows 10/11 x64 桌面客户端零命令行首次接入、已有后台节点平滑接管、登录自启与常驻菜单栏/托盘、受管热更新与回退、原生与屏幕角落通知直达、按服务与账号隔离、本机原生轨迹与工作区文件直读、本机节点状态/日志/代理/Worker/审批模型图形化管理 | 5 |
| [Tool Timeline](tool-timeline.md) | single_thread 消息内过程、真实后台返回、群回复复核与两种模式共享展示边界 | 9 |
| [Agent Work](agent-work.md) | 按团队公开/私有与主人权限控制的全局主工作轨迹、关联子执行、明细与持久回看、增量恢复、按 Agent 确认并刷新工作状态、只读原生轨迹及父子执行范围导航、独立 Dreaming 整理回执与历史复盘用途、卡片内关联入口、回复定位展开且保留完整列表、关联执行与轮次按需分页 | 20 |
| [Workflows](workflows.md) | Workflow 在既有 tool、permission、slash 与普通消息 surface 中的呈现和开关 | 2 |
| [Response Metrics](response-metrics.md) | 墙钟耗时、气泡指标、缓存命中率 | 3 |
| [Agents and Nodes](agents-nodes.md) | 固定版本安装、主动更新电脑、电脑页按需管理与连接、首次助手引导与模型服务管理、Agent 配置与独立停用/重新启用、已停止 Agent 永久删除、创建工作模式与团队公开/私有权限档位、Feature依赖联动与轻提示、Dreaming 自动整理控制、能力选择、公开联系人与私有助手隐藏、停用摘要与管理入口、节点绑定、设备归属标注、Workflow tool pill、Goal 显式开启、workspace 插件管理及真实概览/关联会话、群成员执行节点身份 | 56 |
| [Gateway Relay](gateway-relay.md) | 消息中继与回执、更新切换时持久等待、配置边界、两种工作模式的投递与过程归属、后台返回持久化和重放去重 | 15 |
| [Task Graphs](task-graphs.md) | 会话归属与访问、行动焦点台与北极星全景图、渐进式单卡与多层细分、创建者与负责人、领取和明确删除、通知与聊天活卡片、依赖与衍生、九状态与可选定时/静默等待及原生统一编辑 | 20 |
| [Personal Agent](personal-agent.md) | 固定主人、创建与配置公开/私有档位、双身份历史、消息协助与私有静默旁观、用户主身份代发与外部隔离边界、来源限制与对外披露边界、主动筹划开关、双端本人配置入口、按主人明确要求聊天创建独立 Agent；通用能力复用 Global | 8 |

## Maintenance Rule

- 新增或修改契约时,优先落到语义最窄的 area 文档;只有包级职责、边界或 area 索引变化才改本入口。
- 同一事实只在一个 area 写全,其他文档通过链接指向 canonical 落点。
- delta-spec 归并时可以修改本入口或任一 area 文档,但每条 Requirement 仍必须保持 `Purpose + Requirement/Scenario` 形态。
