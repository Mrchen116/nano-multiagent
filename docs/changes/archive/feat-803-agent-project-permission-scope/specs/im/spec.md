# im/spec.md (delta for feat-803)

## MODIFIED Purpose & Canonical Areas

### Purpose（更新段落）

它对外承担的可观察职责:① 新注册用户可立即使用个人空间，加入公司须申请并获批；有效公司成员可查找公司内的人、设为「团队公开」的 Agent 与 PA，以及与本人共同处于未解散私密群的「项目级」普通/全局 Agent；聊天读取遵循会话公开范围、成员及只读观察资格，写入要求成员资格且受对端私有或项目级助手范围约束；有效公司成员名下的普通全局 Agent 在「团队公开」下对有效公司成员开放 Work 与原生轨迹、在「项目级」下对主人及当前同项目私密群成员开放 Work 与原生轨迹、在「私有」下对其他成员隐藏且不开放外部通信与 Work，PA 私人配置与 Work 按 [Personal Agent](personal-agent.md) 始终保持仅主人可见；完整多档能力对照以 [统一权限矩阵](auth-tenancy.md#requirement-agent-与个人助手按统一权限矩阵控制发现会话轨迹与披露审核) 为准；② direct/group 会话与消息历史稳定持久化; ③ 浏览器实时收发消息、展示工具/思考过程和响应指标，全局 Agent 的内部轨迹在工作视图呈现;④ 用户管理自己所属的 Agent 配置与多个 Node 绑定;⑤ Gateway 在线时双向中继、离线时明确降级;⑥ 外部 channel 会话可镜像为 shadow conversation。

### Canonical Areas（更新行）

| Area | Covers | Requirements |
|---|---|---|
| [Auth and Tenancy](auth-tenancy.md) | Crewden 官网（含多端客户端智能下载入口）与认证入口、持久 JWT 会话、公司准入与停用、认证限流、成员可见性、资源管理归属、Agent 与 PA 多档协作权限统一矩阵、账号设置与系统策略预设 | 17 |
| [Conversations and Messages](conversations-messages.md) | 会话/消息 CRUD、回执、卡片预览、受保护附件与累计容量、配置边界、outbox、群聊与私有/项目级助手治理及跨私密群互通确认、外部历史私聊只读与可逆恢复、外部 Worker 主人私聊审批、分页、fork、限定公网入口、私聊交互背景与群聊明确提交、通用草稿仅填入输入框 | 41 |
| [iOS Client](ios-client.md) | 原生业务与权限、通用交互与私人状态、本地聊天首绘与离线阅读、按账号和服务隔离、未确认发送迁移、持久发送恢复与退出隔离、媒体与提醒、安装维护、聊天阅读连续性与 Agent 停用、首次交办与助手团队公开/项目级/私有权限设置、引用定位、原生 Work 与助手管理 | 20 |
| [Agent Work](agent-work.md) | 按团队公开/项目级/私有与主人权限控制的全局主工作轨迹、关联子执行、明细与持久回看、增量恢复、按 Agent 确认并刷新工作状态、只读原生轨迹及父子执行范围导航、独立 Dreaming 整理回执与历史复盘用途、卡片内关联入口、回复定位展开且保留完整列表、关联执行与轮次按需分页 | 20 |
| [Agents and Nodes](agents-nodes.md) | 固定版本安装、主动更新电脑、电脑页按需管理与日常 Chrome 引导配对、首次助手引导与模型服务管理、Agent 配置与独立停用/重新启用、已停止 Agent 永久删除、创建工作模式与团队公开/项目级/私有权限档位、Feature依赖联动与轻提示、Dreaming 自动整理控制、能力选择、公开/项目级联系人发现与私有助手隐藏、停用摘要与管理入口、节点绑定、设备归属标注、Workflow tool pill、Goal 显式开启、workspace 插件管理及真实概览/关联会话、群成员执行节点身份 | 57 |
| [Personal Agent](personal-agent.md) | 固定主人、创建与配置团队公开/私有两档、双身份历史、消息协助与私有静默旁观、同主人助手内部转发、用户主身份代发与外部隔离边界、来源限制与对外披露边界、主动筹划开关、双端本人配置入口、按主人明确要求聊天创建独立 Agent；通用能力复用 Global | 8 |
