# feat-773: As-built Design

> 本文在实现后整理，描述用户持续反馈后最终落地的设计。

## 实现范围

- Base: `d7f0e60173c9c3feafbec7d251364537da70478b`（origin/develop）。
- 实现 Head: `a6badf9b0`；24 个实现提交，129 个文件。收尾文档另计。
- 组件：Web home/auth/onboarding/chat/settings/shell、IM 身份/会话投影、DSH 集成中的 ROLE 和 PA 来源说明；未改动 DSH 本体。

## 最终结构与数据流

官网 `/`/`about`、认证和应用入口共享 Crewden SVG、字体与轻量色彩。场景组件以交互说明跨聊天协作；界面动效尊重 reduced-motion。语言选择使用完整名称，工作区仅在账户菜单按需展开。

首次入口根据真实账号、绑定、节点和模型状态引导；创建后进入真实聊天。无历史才显示合作说明和任务开场；草稿动作只填空输入框。职责的确认与保存继续经过普通 Agent/ROLE 工具，去掉每轮强制追问职责的提示，PA 在要求用户转发前先查询已有可读来源。

IM 的 `avatar_variant` 是可空的 0–23 身份元数据，通过创建、配置记录、联系人、Actor、消息与前端投影传递，不进入执行配置 fingerprint。启动迁移 `agent-avatar-v1` 添加可空列；老角色通过稳定 ID 选默认外观。PA 使用有机轮廓，普通 Agent 使用几何轮廓，各四种轮廓与六种颜色。头像选择不等于运行能力配置。

PA 固定入口复用会话标题、摘要、时间及未读反馈；配置提交只同步未被用户命名的默认私聊标题。首次设置发现 pending binding 时，用服务器 creation request key 和原 node 恢复同一次创建，确认 active 才跳聊天。群头部只显示人数，成员名单在详情；设置收紧排列。聊天标题去掉重复类型与参与者行，普通私聊省略重复署名，群聊/观察/代发保留必要归属。电脑名称在现有授权头像弹层中查看，在线和需处理的更新提示保留。

`conversationName` 仅按实际 reader 生成显示名。Messaging 的授权主体与 reader 分离；Work 的 PA 查询仍以原 owner/agent 权限取并集，但 reader 始终是 PA。统一覆盖列表、详情、搜索、来源、授权证据和事故通知；Inbox 沿现有 describe/info 刷新缓存。自定义/外部/群标题原样保留；不改存储标题、ID、权限和路由。

## 关键边界、失败与回滚

- 安装、模型配置和职责保存必须有真实回执；页面示意与浏览器 fixture 不宣称后台执行成功。
- 已有草稿、历史滚动、无权限、成员可见性及代发身份沿原契约。无法读取角色状态时不假装初始化完成。
- 头像是 additive nullable schema，无需一次性人工迁移；旧服务不使用该列，代码回滚不应删除用户头像数据。
- 头像随已接受的配置候选持久化。候选写入前失败时，原浏览器首次设置草稿仍可回送选择；跨浏览器没有原选择记录，不承诺恢复未被接受的头像。
- 本次没有一次性历史改写。后续正式部署需 IM/Node 使用匹配版本，不能把公开旧包 v1.0.3 与当前配置格式混用；不为本次 UI 增加兼容层。
- 已交付模型上下文不追溯重写；新的来源查询、Inbox check/read 才获得新名称。

## 审查安排与验证定位

独立完整代码审查结合非视觉 Agent Context 判断，覆盖权限/创建/迁移、提示内容与实际消费链。视觉与用户旅程复用已发生的实际试用、逐轮截图和最后验收，不重新制造全量产品验收。

作者阶段证据位于本机 `output/playwright/crewden-app/`、`crewden-friendly/`、`crewden-workspace/`、`crewden-groups/`、`avatar-redesign/`、`chat-simplify/` 和 `output/conversation-names/`。这些运行产物不提交；review 汇总可复核命令、结果与限制。公开旧包安装/绑定真实发生，但创建被协议差异拒绝；当前本地候选完成真实 PA 创建和模型回复，录像经过剪接并已注明。最终日常栈是隔离的 P/E/Q + PA，不是生产。

## Canonical 归并

本次 delta 位于 `specs/`；当前契约已随实现归入 IM auth-tenancy、agents-nodes、personal-agent、web-chat-ux、conversations-messages，以及 Gateway agent-capabilities/global-agent。最终完整 diff 与 delta 由独立 reviewer 校对。
