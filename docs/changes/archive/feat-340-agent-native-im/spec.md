# feat-340: Agent-native IM 前端按新原型重写

## Relations

- Depends on: 无
- Blocks:
- Related:

## 原始需求

> Fetch this design file, read its readme, and implement the relevant aspects of the design.
> https://api.anthropic.com/v1/design/h/tsTj22JLYoVBb_olKcczPw?open_file=IM+Prototype.html
>
> Implement: 我本地实现的毛胚需要按照这个新的原型重新实现，效果要全面和原型设计一致。我们先对齐需求，落入spec文档

附件:`attachments/prototype/`(Claude Design 导出的 Agent-native IM handoff bundle,含 `IM Prototype.html` + 6 个 jsx 组件 + `im-data.js` mock 数据 + i18n + 截图)。

## 澄清记录

- Q1: 像素级对齐的边界?TweaksPanel / i18n / agent-network 各自怎么处理?
  A:
  - **像素级对齐范围**:布局、配色、字体、间距、组件细节、4 种会话类型(direct-agent / group / agent-network / 含 tool_calls + token_usage)的渲染样式、新建群聊模态、@mention picker——全部按原型。
  - **TweaksPanel**(设计工具浮窗):**不保留**。
  - **i18n EN/中 切换**:本期需要。
  - **`agent-network`(agent↔agent)会话类型**:本来就是既有的 agent-to-agent 概念,本轮只是视觉对齐,不是新功能。

- Q2: 页面覆盖范围 + 桌面/移动对等度?
  A: **5 个页面全做**(Chat / Agents 列表+详情+新建 / Nodes / Account / 移动端 Me 聚合页),**桌面 + 移动响应式对等**(断点 < 768px),两端都要像素级对齐原型。路由 URL 延续现有结构,移动 Me 页新增 `/me`。

- Q3: Chat 页的富交互组件是否全做?
  A: **全部 P0**。Tool Calls 展开器 / Token Usage Chip(含 70%/90% 预警)/ @mention picker(键盘选 + Esc 取消)/ 会话列表 All/Agent/Group/Network 分类标签 / 实时搜索框 / 新建群聊模态 / 会话头部 Node 状态 Chip + Kind Badge + ⚙ 跳配置——一项不落。后端数据缺失项由 design 阶段识别并补齐,不在 spec 层 punt。

- Q4: Agents / Nodes / Account 三页的字段和操作完整度?
  A: **全部按原型实现,所有可编辑项必须真存盘**。Agents 详情(Identity / Behavior / Access & Model / Workspace & Runtime 四组卡片,dirty 检测 + Discard/Save + Open chat ↗)、新建 Agent(UserMenu + Nodes 双入口)、Nodes(列表 + relay/reporting toggle + 从节点视角新建 agent)、Account(可改字段走表单存盘)。不接受"假交互",前端不能光做视觉而后端不通。

- Q5: 实时性 + 边界状态(loading / empty / error / offline)的完整度?
  A: **全做**。流式渲染(agent 消息文本 + tool_call 状态实时增量更新,基于既有 SSE 基建)、运行中动效(pulse / spin 按原型)、节点和 agent 的实时 online/offline 反映、每个页面的空态文案、错误反馈(toast + inline,不静默吞)。

- Q6(横切原则): 只改前端不够的功能怎么办?
  A: **后端同步改**。所有原型展示的字段、状态、操作如果当前后端不支持(例如 token_usage 字段、tool_call 结构、relay_enabled toggle、heartbeat-driven online 状态、流式消息事件类型等),**后端 API + Gateway + 数据模型都要相应扩展**。本 unit 范围包括完整全栈实现,不允许"前端只做视觉、后端不通"。

- Q7: 原型没画但常被默认想要的功能,哪些纳入本期?
  A: **附件/文件上传 + 桌面通知 + 多用户 纳入本期**(原型未画但需要)。其余非目标:对话归档导出、全局 cmd-k 命令面板、消息内容全文搜索、语音/音频。注:附件、通知、多用户三块原型没给视觉,**视觉由本 unit 设计阶段补,需要与原型整体风格一致**。多用户范围:登录/注册/账号隔离/多账号下 agent 与 node 归属边界。

- Q8(design 阶段回补): 多用户支持是否包含"跨用户群聊"?用户之间能否互相发现/邀请?
  A: **不支持跨用户群聊,用户与用户之间严格隔离**。
  - 多用户:支持登录/注册/账号隔离
  - 群聊:**仅支持"单用户 + 自己的多个 agents"**,不支持把别的用户拉进自己的群
  - @mention 候选:**只来自当前用户拥有的 agents**,不含其他用户
  - 用户发现机制:本期非目标(留作未来 contacts/team unit)
  - 原因:Q4 之前的"群聊参与者支持多个真实用户"与"严格隔离"互相张力,design 阶段暴露;选择保留严格隔离,跨用户能力推后。

## 用户场景

### 场景 A:Alex 用桌面端跟单个 Agent 协作改代码

Alex(单人开发者,Mac + 远端服务器各一台节点)打开浏览器进入 nano IM。暗色顶栏左侧 "nano IM" Logo + Chat/Agents 切换,右上角是自己的头像 dropdown。默认进入 Chat 页:左 262px 侧栏列出 4 条对话(Assistant 直聊 ×2 未读、Sprint Planning 群、Planner 直聊、Agent Network: Deploy 的 agent↔agent),右侧打开第一条直聊。

他打字"修一下 relay_service.py 的 bug",Enter 发送。Agent 头像 pulse,气泡逐字流式输出"让我看看...",紧接着冒出一个 Tool Calls 面板:`list_files` ✓ 48ms、`read_file` ✓ 22ms、`str_replace_edit` ⏳ running...。每个工具点开能看到 input/output。完成后气泡下方出现 Token Chip:"312 out · 14.8k/200k(7%)",蓝色低消耗。

他切到 ⚙ 想给 Assistant 加个 web_search 工具:跳到 Agents 详情页,在 Access & Model 卡的 Tool Allowlist 多选里勾上 web_search,顶部 Save 按钮从灰变 accent,按下保存,dirty 状态消失。

### 场景 B:Alex 在群聊里 @ 唤起 Planner

切到 "Sprint Planning" 群聊。输入框敲 `@`,200ms 内弹出候选列表:Assistant / Planner / Reviewer 三个 Agent 头像 + 名字。↑↓ 键移动焦点,Enter 选中 Planner,输入框变成 `@Planner 帮我拆这周任务`。Esc 可关闭 picker。发送后只有 Planner 响应(group_reply_policy = MENTION)。Reviewer 因为是 ALWAYS 也会跟着发一条。

### 场景 C:Alex 在 Nodes 页发现远端服务器掉线

从右上头像 dropdown 进 Nodes(或移动端从 Me 标签)。看到三台节点:My MacBook Pro 🟢 online、Lab Server 🟢 online、Remote Server 🔴 offline(last_heartbeat 3 天前 + last_error 红字"connection refused")。点 Lab Server 进详情,翻到 relay_enabled toggle 关闭(他要临时断开 relay),状态实时同步到后端,heartbeat 下一帧反映新状态。

### 场景 D:Alex 用手机继续

地铁里打开同一个 Web 应用(< 768px 切到移动布局):顶栏退化为纯状态栏,底部三 tab(💬 Chat · 🤖 Agents · 👤 Me)。Me 页是聚合入口:Account / Nodes / Language 切换 / Sign out。他点开未读会话,消息流式渲染、Tool Calls 展开、附件预览全部和桌面一致。Agent 回复完成时,即使没在前台,**系统通知 banner** 弹出"Assistant: 我已完成 5 个测试"。

### 场景 E:Alex 拖文件给 Agent

在桌面 Chat 输入框拖入一张错误日志截图,输入框上方出现附件缩略图 chip(可叉掉),输入文字"看看这个堆栈",Enter 发送。Agent 气泡里能引用这张图,后续工具调用能读到附件路径。

## 验收标准

### 视觉对齐(像素级)

- [ ] 桌面布局:48px 暗色顶栏(Logo + 中央两 tab + 右侧 UserMenu)、Chat 页左 262px 会话栏 + 右消息面板、Agents 页左 240px agent 列表 + 右详情、Nodes/Account 页与原型一致
- [ ] 移动布局(< 768px):退顶栏为状态栏 spacer,底部三 tab(Chat / Agents / Me),Me 页为聚合入口
- [ ] 主色 `oklch(0.52 0.14 180)` 青色 accent、暗色顶栏 `oklch(0.19 0.012 240)`、浅色内容区,字体 `IBM Plex Sans` 正文 / `IBM Plex Mono` 代码
- [ ] 用户消息气泡 `16/16/4/16` 圆角靠右 accent 背景、Agent 气泡 `16/16/16/4` 圆角靠左浅色背景含 Markdown 渲染

### Chat 页交互

- [ ] 会话列表分类标签 All / Agent / Group / Network 实时过滤
- [ ] 会话列表搜索框输入实时过滤标题 + 最后预览
- [ ] 4 种会话类型(direct-agent / group / agent-network / 含 tool_calls)各自渲染样式与原型一致,kind badge 正确显示
- [ ] Tool Calls 面板:状态点(✓/⏳/✗)、duration_ms、可折叠展开 input/output
- [ ] Token Usage Chip:输出 tokens、上下文占比进度条;≥70% 黄色预警,≥90% 红色预警
- [ ] 群聊输入框敲 `@` 在 200ms 内弹出 mention picker;↑↓ 键导航、Enter 选中插入、Esc 关闭
- [ ] 新建群聊模态:Agent 多选 + 群名(可选)+ Create 真存盘后会话出现在列表
- [ ] 会话头部:头像 + 标题 + 参与者 + Node 状态 chip + Kind badge + ⚙ 跳对应 agent 配置页

### Agents 页

- [ ] 列表:新建 Agent 入口(`+`)、Agent 条目含头像 + display_name + agent_id + status 点
- [ ] 详情页四组卡片:Identity(display_name/description 可编辑,agent_id/owner_id 只读)、Behavior(system_prompt textarea + group_reply_policy 下拉 MENTION/ALWAYS/NO_REPLY)、Access & Model(skills 多选 + tool_allowlist 多选 + default_model 下拉)、Workspace & Runtime(workspace_root/profile_version/node_id/updated_at 只读)
- [ ] dirty 检测:任一字段改动则 Save 按钮变 accent;Discard 回滚;Save 调后端真存盘后 dirty 清除
- [ ] 顶部 Open chat ↗ 跳到对应 direct-agent 会话
- [ ] 新建 Agent:UserMenu 入口 + Nodes 节点条目入口两条路径都能进表单,Save 后真新建并出现在列表

### Nodes 页

- [ ] 列表:node_name + alias + status(online/offline 颜色点)+ agent_count + version + last_heartbeat + last_error 文本
- [ ] relay_enabled / reporting_enabled toggle 实时存盘后端
- [ ] 节点详情/操作:能从节点视角列出本节点 agents、新建 agent

### Account 页

- [ ] 字段:display_name(可改)、user_id(只读)、default_entry_node_id(可改)、owned_node_ids(列表)、created_at(只读)
- [ ] 可改字段走表单 Save 真存盘

### 实时与状态

- [ ] Agent 消息文本和 tool_call 状态实时增量更新(基于 SSE)
- [ ] running 状态有视觉指示(头像 pulse / spinner spin)
- [ ] 节点 / agent 的 online/offline 状态由 heartbeat 实时驱动,UI 实时反映
- [ ] 每个页面都有空态文案(无会话、无 agent、无 node)
- [ ] 错误反馈:发送失败、保存失败、加载失败有 toast 或 inline 错误提示,不静默吞

### i18n

- [ ] 全 UI 文本支持 EN / 中 两套,用户在 UserMenu 或 Me 页可切换并持久化

### 附件

- [ ] 桌面 + 移动 Chat 输入框支持拖入 / 选择文件附件(图片 + 文档)
- [ ] 附件以缩略图 chip 形式出现在输入框上方,可叉掉
- [ ] 附件随消息发送给 Agent,Agent 后续 tool_call 能读到附件
- [ ] 视觉风格与原型整体一致(设计阶段细化)

### 通知

- [ ] 浏览器系统通知(Notification API)在 Agent 回复完成时弹出
- [ ] 仅在窗口非前台 / 标签非活动 时触发
- [ ] 用户可在 Account 或 Me 页开关通知
- [ ] 视觉风格与原型整体一致(设计阶段细化)

### 多用户

- [ ] 支持多个独立用户账号,登录 / 登出 / 注册流程
- [ ] 每个用户拥有独立的 agents / nodes / conversations 数据集,彼此严格隔离(用户 A 看不到 / 不可改用户 B 的任何数据)
- [ ] Agent 与 Node 的归属(owner_id / owned_node_ids)与登录账号一致,他人不可见 / 不可改
- [ ] 群聊参与者**仅限当前登录用户 + 该用户拥有的 agents**(不支持跨用户拉群),@mention 候选**仅本用户的 agents**
- [ ] 视觉风格与原型整体一致(登录页 / 注册由设计阶段补)

### 全栈接通

- [ ] 上述所有"真存盘 / 真状态 / 真流式"项,后端 API + Gateway + 数据模型已相应扩展,前端不通过 mock

## 范围与非目标

### 在范围

- 桌面 + 移动响应式重写 5 个页面(Chat / Agents 列表+详情+新建 / Nodes / Account / 移动 Me),像素级对齐原型
- Chat 页 4 种会话类型(direct-agent / group / agent-network / 含 tool_calls)的视觉与渲染
- 富交互:Tool Calls 展开、Token Chip 含预警、@mention picker、会话分类标签、实时搜索、新建群聊模态、会话头部 Node 状态 chip
- Agents/Nodes/Account 三页全部字段 + 全部可编辑操作 + 真存盘
- 流式渲染 + 实时 online/offline + 空错状态完整覆盖
- i18n EN/中 切换 + 持久化
- 附件上传(图片 + 文档),桌面与移动一致
- 浏览器系统通知(非前台触发,用户可开关)
- 多用户:登录/登出/注册、账号隔离、agent 与 node 归属(群聊参与者仅限本用户 + 自有 agents)
- 后端 API / Gateway / 数据模型为以上目标所需的全部扩展

### 非目标

- TweaksPanel 设计工具浮窗(原型脚手架,不带入产品)
- 团队 / 组织 / 权限分级(多用户做账号隔离即可,不引入组织树和角色权限)
- **跨用户群聊 / 用户互相发现机制 / contacts / 邀请码**(用户之间严格隔离,不支持把别的用户拉进自己的群;留作未来 contacts/team unit)
- 对话归档导出 / 审计日志
- 全局 cmd-k 命令面板
- 消息内容全文搜索(会话列表只过滤标题+最后预览)
- 语音 / 音频消息
- 第三方 IM 集成(微信、Telegram 等 channel,不属于本 unit)
