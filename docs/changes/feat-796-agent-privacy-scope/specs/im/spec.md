# IM Specification index (delta for feat-796)

## MODIFIED Purpose

`IM` 对外承担的可观察职责中：① 新注册用户可立即使用个人空间，加入公司须申请并获批；有效公司成员可查找公司内的人和设为「团队公开」的 Agent，聊天读取遵循会话公开范围、成员及只读观察资格、写入要求成员资格且受对端私有助手隔离约束，有效公司成员名下设为「团队公开」的普通全局 Agent Work 与原生轨迹对有效公司成员完整开放，设为「私有」的 Agent 对其他成员隐藏且不开放外部通信与 Work，PA 私人配置与 Work 按 [Personal Agent](personal-agent.md) 保持主人可见。

## MODIFIED Canonical Areas

| Area | Covers | Requirements |
|---|---|---|
| [Conversations and Messages](conversations-messages.md) | 会话/消息 CRUD、回执、卡片预览、受保护附件与累计容量、配置边界、outbox、群聊与私有助手成员互斥、外部历史私聊只读与可逆恢复、分页、fork、限定公网入口、私聊交互背景与群聊明确提交、通用草稿仅填入输入框 | 40 |
| [iOS Client](ios-client.md) | 原生业务与权限、通用交互与私人状态、本地聊天首绘与离线阅读、按账号和服务隔离、未确认发送迁移、持久发送恢复与退出隔离、媒体与提醒、安装维护、聊天阅读连续性与 Agent 停用、首次交办与助手公开/私有权限设置、引用定位、原生 Work 与助手管理 | 20 |
| [Agent Work](agent-work.md) | 按团队公开/私有与主人权限控制的全局主工作轨迹、关联子执行、明细与持久回看、增量恢复、按 Agent 确认并刷新工作状态、只读原生轨迹及父子执行范围导航、独立 Dreaming 整理回执与历史复盘用途、卡片内关联入口、回复定位展开且保留完整列表、关联执行与轮次按需分页 | 20 |
| [Agents and Nodes](agents-nodes.md) | 固定版本安装、主动更新电脑、电脑页按需管理与连接、首次助手引导与模型服务管理、Agent 配置与独立停用/重新启用、已停止 Agent 永久删除、创建工作模式与团队公开/私有权限档位、Feature依赖联动与轻提示、Dreaming 自动整理控制、能力选择、公开联系人与私有助手隐藏、停用摘要与管理入口、节点绑定、设备归属标注、Workflow tool pill、Goal 显式开启、workspace 插件管理及真实概览/关联会话、群成员执行节点身份 | 56 |
| [Personal Agent](personal-agent.md) | 固定主人、创建与配置公开/私有档位、双身份历史、消息协助与私有静默旁观、用户主身份代发与外部隔离边界、来源限制与对外披露边界、主动筹划开关、双端本人配置入口、按主人明确要求聊天创建独立 Agent；通用能力复用 Global | 8 |
