# feat-616：复用 Global 与 IntelligentUI 的个人助手

> R9，2026-10-19。替代旧设计。用户已明确授权此收敛版；历史代码和审查是旧行为证据，不作为本轮通过依据。

## 基线与职责

实施工作树为 feat-616 原工作树；初始基于 feat-617 `87f5214a7`，集成提交 `b50704bdd`，随后同步最新远端 `e61588616` 于 `d370ab6b7`。两次基线产品代码相同，后次仅更新 feat-617 文档与证据保存规则。最终再同步 `2aee3995e` 于 `e5eb09a12`，包含聊天宽度布局更新。收尾同步 feat-617 `d9876365f` 和 main `d9be419c7`（集成 `e0b192bbb`），仅补文档及 Issue 模板/维护脚本，产品代码与 `0b4b8ee46` 相同。保持现有顶栏/聊天布局。Global 主 session、Inbox、conversations、send_message、task_graph、schedule、Heartbeat、普通文件与插件机制继续作为唯一能力实现。

```mermaid
flowchart TD
 U[主人直接指令] --> P[同一个 Global PA]
 S[主人聊天双向消息 + PA 自己的消息] --> A[可信身份、实时权限、外部风险检查]
 A --> P
 P --> Q[现有查询/工具/子 Agent/任务/定时]
 Q --> P
 P --> UI[feat-617 IntelligentUI]
 UI -->|主人选择回原会话| P
 UI -->|采用回复草稿| C[原聊天输入框，主人发送]
 P --> X[具体对外消息或共享内容审查]
 X --> G[复核权限、内容和受众后提交]
 G -->|真实回执| P
 P --> PS[personal_sources：来源排除/恢复]
 PS --> A
```

### 注册与加入公司的连续体验

注册后进入现有首次设置，完成电脑绑定和模型连接后，直接调用同一个 createPersonalAgent 创建固定 PA；不是先创建普通助手再转换。允许稍后继续设置，个人使用无需公司资格。绑定以 owner_id 为稳定归属，成员申请/批准只更新 membership_status，不创建或迁移 PA、主人私聊、配置与执行上下文。获批后在同一 PA 中继续使用；新增公司资源访问仍逐项遵循现有权限，主人私人聊天与 Work 保持私人。

首次设置只保留连接电脑、连接模型、创建个人助手三步，创建只收集名字；聊天入口的创建弹窗保持一致。移除 initial_goal 的业务参数和创建后自动投递路径，不把配置操作变成发消息。创建成功打开 canonical 主人私聊；消息查询已成功确认无历史时提供三条本地化简短示例，且仅主人、空输入框、无待发送附件时显示。示例只更新现有 composer draft 并聚焦，不调用发送、任务或模型；用户编辑/发送继续走普通聊天路径。已有消息后不展示首次引导，无额外 onboarding 状态机或已读标记。

注册验收必须从 /register 开始，覆盖创建前 company none、申请后 pending、批准后 active 三个阶段；核对同一 agent_id/binding_id/conversation_id 和原消息。实际安装包未发布的本地环境可使用隔离源码构建的电脑端，但必须明确记录这不构成下载安装验收，不可预置 PA 冒充注册创建。

### 身份与双向消息

保留 personal_agent_bindings 和既有 owner-only 配置/Work ACL、身份 epoch。PA 自己的可读会话与主人可读且参与过的会话取并集；source exclusions 应用于整个 PA 的查询与接收。查询扩展现有 conversations 工具的 list/info/read，并增加 search 参数能力，不新增 PA 历史工具或数据库。消息来源附原消息 URL 和主人是否可读的事实；仅 PA 可读时明确说明并给出相关事实摘要，不把链接展示为主人可打开的入口。Agent 建群复用现有会话权限，依据实时 profile/owner 权限而非运行账号的成员状态。

IM 消息事件为主人所在聊天创建观察事件，包含主人发出的消息；PA 自身聊天仍走正常 relay，持久消息 ID 去重。观察只增加 Inbox 输入，不创建目标。PA 自发消息跳过自动唤醒。直接主人消息无需独立审核；主人其他聊天发言作为事实，不自动当作 PA 指令。外部输入的风险判断保留来源，失败只影响相应外部输入。

### 权限与来源控制

新增薄工具 personal_sources，动作 list/exclude/include。主 PA 根据原始主人指令调用，服务端检查真实绑定、owner DM 消息证据、会话访问权和 policy revision；无独立语义调用。设置页使用同一后端。修改后撤销尚未摄入的事件和 Inbox 队列、使未执行的披露许可失效，并向主 session 提供来源变更事实；不重建上下文、不清空记忆/成果、不删除定时。

不提供全局 observation_enabled。移除 PA 的 cleanup 产品、PersonalState 来源派生追踪/退休 session、自动知识排除机制。当前上下文已经读过的内容无法保证遗忘；后续访问由后端拒绝，使用/披露约束通过当前来源策略和外发审查处理。

### 共用能力与审核边界

撤销 PERSONAL_TOOLS 白名单、禁用代码/插件/Skill creation、个人文件工具与替代 web_search。PA 使用普通 Global 的能力目录、配置和权限规则，保留主人私人运行实例作为数据归属隔离，不把它当 OS 沙箱。

删除 pa_assistance、pa_goal_scopes、pa_decisions 及其 PA 工具/API/UI、PA schedule 恢复和目标暂停钩子。任务和定时按普通 Global 行为使用。原 PA 自建任务仍是正常 task_graph，数据保留。

主人原始消息和 feat-617 已提交选择是授权证据，不再先抽取结构化目标许可。外发审查从服务端取 canonical owner DM 中真实用户输入、已发布提案与 interaction_reply，并结合真实执行材料、当前来源权限、接收人、已披露内容判断。模型提案不能签发许可。普通内部工具不加 PA 审核；直接给主人发消息无需独立披露审查。

保留冻结具体提案→独立审核→后端复核→真实提交/回执的披露流程，应用于消息、附件与别人可见的任务修改。任务调用复用原 task_graph 参数与执行路径，仅在目标受众不是主人私聊时加入披露检查，不限制任务动作种类。代码、shell、插件沿普通权限边界；不宣称它们的任意外传都被该检查覆盖。审核模型无业务工具；该保证不能推出模型永不误判。

### IntelligentUI 与原聊天草稿

send_message 保留 feat-617 interactive 参数、发布/更新/私有草稿/提交语义。主人消息无需前置审核，提交的选择随原始消息进入主 PA。删除 PA decision 业务与重复状态机。

PA 可以在给主人发送的 interactive 消息上附加 reply_draft 元数据：target_conversation_id、source_message_id、field_name。该元数据只用于“采用到原聊天”导航，不自带发送许可；后端核对主人可写原会话、消息归属、PA 主人私聊及字段存在。正文编辑状态仍在 feat-617 interaction_drafts，不另存正文。

聊天气泡上的“在原聊天使用”取当前用户的字段值填入原聊天输入框；真正发送沿普通用户发送按钮。采用失败保留原编辑内容；主人在源聊天已回复时标明草稿可能过时，不自动覆盖用户编辑或自动发送。原聊天输入非空且不同于草稿时，保留原内容，由用户明确选择替换；取消采用不丢编辑。手机端复用现有聊天返回路径，不新增全局导航。对外发送 interactive 的全部内容也是审核 payload，不能只检查 text。

### 可疑事件与外部渠道

保留 pa_incidents 和原消息证据、主人提醒、对方告知顺序。输入明确 deny 必须走通知，即使审核模型省略可选事件说明。主人提醒包含原请求短摘录、依据和处理结果，不依赖主人有源会话读取权。系统固定告知必须有主人通知回执，不由主 PA 宣称。后端核定固定文案与当前权限后，其独立审核只接收完整固定 payload、实际受众、通知回执和策略，不让无关历史行为成为这次拒绝语的审核对象；任意对外内容仍带完整执行证据。发送沿实际现有 channel adapter；外部渠道不支持交互时使用 feat-617 文本降级，不把源代码发出去。

## 数据与清理

保留绑定、来源 policy/events/reads、披露 operation/audit、代发标记、incident、node epoch/runtime status。删除未交付旧 PA assistance/scopes/decisions/cleanup 的代码与新库 schema；本地旧表可保留为未读取历史，不添加兼容流程或批量删除用户原任务。

reply_draft 保存来源定位元数据，与消息绑定，正文和编辑 revision 由 feat-617 唯一持有。当前数据从头到尾保留真实 actor，不把 owner 变为 PA 发言的实际 sender。

## Milestone

| ID | 依赖 | 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|---|
| M1-personal-agent | feat-617 87f5214a7 | 单组 | IM/PA/runtime/contracts/Web 与本 unit | [reviewer] 双身份历史、双向消息、草稿编辑采用、代发身份、来源控制、实际持续协助与拒绝泄露；[worker] 旧机制无生产引用、普通 Global 回归、工具/插件能力一致、真实模型与重启证据、独立静态门禁 |

## 验证与风险

窄测试先验证：主人请求在审核不可用时仍可接收；PA 独立聊天能被查询；主人主动发出的消息能摄入；来源排除不销毁上下文；完整普通工具目录；IntelligentUI 提交和草稿采用不越权/不自动发送；私人任务不审核，外发真实 payload 必须审核。真实旅程采用现有隔离服务与两个测试用户，保留原测试数据，不接生产。主模型 6.1 Sol、审核 6 Luna。

删除旧机制是实质变化，R8 Gate 2/产品通过项不自动覆盖 R9；独立复审收口后实施，产品验收只扩展已失效范围。原型只表示既有 IM 内的新增交互，不自建导航。

## Changelog

## R12 默认职责与持续工作规程

新建时一次性把产品默认职责写入已有 custom_prompt，通过普通配置/Persona 路径运行。用户可以在现有设置查看、编辑或清空，不增加模板版本、重置入口或自动迁移；已有实例与重试/恢复保留自己的配置。默认文案说明主动推进、减少打扰、相关消息协助、按需读取共用 Skill、真实交付；从 PA 固定 system section 中删除重复的持续推进/交互偏好要求，只保留身份、授权来源、历史出处、草稿工具协议和披露边界。普通 Global 的通用执行协议继续共用。

新增随包 nano-ongoing-work Skill，由现有 installer/discovery/selection/native skill 加载。采用独立产品名称避免覆盖用户原有 workspace ongoing-work；默认发现不等于把全文常驻注入。规程沿用现有任务/工作文件，无现成记录且确需跨轮次时才记简短 workspace 笔记；原始授权与实际执行/发送回执继续走现有机制。等待依赖实际消息事件、子 Agent 完成、Heartbeat 或 schedule；无真实触发不得声称已经安排。保留用户已有 HEARTBEAT.md，按当前事项需要才补充，不自动建立全局巡检。
