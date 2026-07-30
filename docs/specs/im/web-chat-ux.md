# IM - Web Chat UX Specification

> 对齐: bugfix-471
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

Web IM 聊天页滚动、输入、消息操作和桌面/移动一致性的用户可见契约。

## Requirements

### Requirement: Web IM 聊天页消息历史支持向上滚动分页加载

Web IM 的聊天页在会话历史超过一页时,用户向上滚动消息列表即可加载并查看更早内容;加载过程不破坏当前阅读位置。

#### Scenario: 用户向上滚动触发更早消息加载
- **GIVEN** 当前会话有更多历史消息
- **WHEN** 终端用户在消息列表中向上滚动到接近顶部
- **THEN** 更早的消息自动加载并插入到现有内容顶部
- **AND** 用户原来的阅读位置保持稳定,不自动跳到底部

#### Scenario: 已加载到最老的消息
- **GIVEN** 当前会话已经加载到第一条消息
- **WHEN** 终端用户继续滚动到顶部
- **THEN** 不再发起新的加载请求
- **AND** 列表顶部显示「没有更多消息」或等效空态提示

#### Scenario: 加载更早消息时显示加载状态
- **WHEN** 终端用户触发更早消息加载且请求尚未返回
- **THEN** 消息列表顶部出现加载状态提示

### Requirement: Web IM 新消息到达不打扰正在翻看历史的用户

当用户正在查看较早内容时,新到达的消息不会自动把视图拉到底部;只有当用户已经位于底部附近时,才自动跟随到最新内容。

#### Scenario: 用户正在看历史时收到新消息
- **GIVEN** 终端用户已经向上滚动离开底部,正在查看较早内容
- **WHEN** 有新消息或 agent 回复到达
- **THEN** 消息列表不自动滚动到底部
- **AND** 用户仍停留在当前阅读位置

#### Scenario: 用户位于底部时收到新消息
- **GIVEN** 终端用户位于消息列表底部附近
- **WHEN** 有新消息或 agent 回复到达
- **THEN** 消息列表自动滚动到底部,让用户看到最新内容

### Requirement: Web IM 实时体验在连接恢复后保持一致且不重复消息或时间线边界

Web IM 的当前会话、会话列表、消息、配置边界、提醒与状态共享同一事件连续性。短暂断网后，已处理事件不再次显示；断线期间遗漏的持久消息和时间线边界经恢复或刷新与历史一致。

#### Scenario: 恢复连接不重放已处理提醒
- **GIVEN** 用户已处理某条提醒，随后短暂断网
- **WHEN** 实时连接恢复
- **THEN** 历史提醒不再次弹出

#### Scenario: 断线期间的新消息与配置边界恢复后可见
- **GIVEN** 断线期间某聊天收到新消息并实际跨过运行配置边界
- **WHEN** 浏览器恢复网络
- **THEN** 消息与分界线最终按正确锚点顺序显示，不产生重复气泡或分界线

#### Scenario: 状态恢复到当前权威值
- **WHEN** 浏览器恢复网络并查看 Chat、Nodes 或 Agents
- **THEN** 非持久状态显示当前权威值，不永久停留在断线前快照

#### Scenario: 切换账号不展示前一账号缓存
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** Web IM 只展示 B 的消息、配置边界、提醒与状态

### Requirement: Web IM 用持久非消息分界线说明 Agent 运行配置缓存边界

某个既有聊天首次真正使用不同的 Agent 运行配置时，Web IM 在该轮首条用户消息前显示持久小字：“Agent 配置已更新 · 后续请求将不再命中此前的上下文缓存”。分界线不是消息气泡，没有头像、发送者、时间、投递状态或消息菜单。页面刷新、重进、分页和连接恢复后位置不变。

#### Scenario: 运行配置更新后继续既有聊天
- **GIVEN** 用户成功修改会改变后续模型请求的 Agent 配置
- **WHEN** 某个既有聊天开始第一轮真正使用新配置的交流
- **THEN** 首条用户消息前出现固定文案的非消息分界线
- **AND** Agent 回复仍能引用分界线前的聊天历史

#### Scenario: 分界线在刷新和重进后保持位置
- **GIVEN** 聊天已显示配置分界线
- **WHEN** 用户刷新页面、离开后重进、向前分页或断线重连
- **THEN** 分界线仍唯一地位于同一锚点用户消息之前

#### Scenario: 分界线不提供消息交互
- **WHEN** 用户在桌面或移动端查看或操作配置分界线
- **THEN** 分界线无头像、气泡、发送者、投递状态和复制或 fork 消息菜单

#### Scenario: 休眠聊天不被批量插入
- **GIVEN** 同一 Agent 有多个既有聊天
- **WHEN** 用户修改运行配置，但某些聊天没有继续交流
- **THEN** 未继续的聊天不新增分界线

#### Scenario: 连续修改只显示最终边界
- **GIVEN** 某聊天再次使用前，Agent 运行配置连续成功修改多次
- **WHEN** 用户回到该聊天开始新回复
- **THEN** 时间线只新增一条分界线，不依次显示中间版本

#### Scenario: 纯展示更新与保存失败不显示分界线
- **WHEN** 用户只修改展示信息，或运行配置保存没有成功
- **THEN** 聊天页不出现配置缓存分界线

#### Scenario: desktop 与 mobile 保持低层级时间线样式
- **WHEN** 用户在桌面或移动浏览器查看带分界线的聊天
- **THEN** 分界线横跨消息内容区，以低于消息正文的视觉层级显示
- **AND** 不破坏既有 desktop sidebar/chat 布局或 mobile 单页 chat 布局，不产生横向滚动

#### Scenario: 外部 channel 影子聊天补齐分界线
- **GIVEN** 外部 channel 的既有对话采用了新配置，Web IM 暂时离线
- **WHEN** 用户稍后打开或刷新对应影子聊天
- **THEN** 分界线唯一地显示在正确的外部用户消息前
- **AND** 外部 channel 本身没有收到伪造的分界线消息

### Requirement: Web IM 移动端输入法回车发送消息

在移动设备上,终端用户在聊天输入框中按下输入法回车键即可发送消息,而不需要点击发送按钮。

#### Scenario: 移动端按回车发送
- **GIVEN** 终端用户在移动端的聊天输入框中输入了文字
- **WHEN** 用户按下输入法回车键
- **THEN** 消息被发送,输入框清空
- **AND** 不回车换行

### Requirement: Web IM composer 输入框随内容自动增高

聊天输入框会根据输入内容自动增高,直到达到最大行数;超过最大行数后输入框内部可滚动。

#### Scenario: 输入多行文字时 composer 增高
- **GIVEN** 终端用户在 composer 中输入文字
- **WHEN** 文字超过一行
- **THEN** composer 自动增高以展示更多内容
- **AND** 增高到最大行数后不再继续变高,内部可滚动

### Requirement: Web IM 消息气泡支持复制与长按/右键菜单

终端用户可以长按(移动端)或右键(桌面端)消息气泡,调出操作菜单复制消息文本;在移动端单聊里,还可以对可 fork 的 agent 回复进行 fork。

#### Scenario: 长按/右键消息气泡调出菜单
- **GIVEN** 聊天列表中有任意消息气泡
- **WHEN** 终端用户在移动端长按气泡,或在桌面端右键气泡
- **THEN** 弹出操作菜单,至少包含「复制」

#### Scenario: 复制消息文本
- **GIVEN** 操作菜单已打开
- **WHEN** 终端用户选择「复制」
- **THEN** 该消息的文本内容被复制到剪贴板

#### Scenario: 移动端单聊里长按 agent 回复进行 fork
- **GIVEN** 当前是直接用户↔agent 的会话,且某条 agent 回复已完成并可 fork
- **WHEN** 终端用户在移动端长按该 agent 回复,并在菜单中选择 fork
- **THEN** 触发 fork 流程,并给终端用户明确反馈(如进入新分支会话)

### Requirement: Web IM 桌面与移动端在聊天页保持一致的滚动与交互体验

无论是桌面浏览器还是移动浏览器,进入同一聊天页都能获得相同的分页加载、Enter 发送、composer 自动增高和消息菜单能力。

#### Scenario: 在手机端向上滚动加载历史
- **WHEN** 终端用户在移动设备上打开同一聊天并向上滚动
- **THEN** 同样触发加载更早消息,且阅读位置保持稳定

#### Scenario: 在手机端长按 agent 消息 fork
- **WHEN** 终端用户在手机端长按可 fork 的 agent 回复
- **THEN** 出现包含 fork 选项的菜单

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择已完成会话,生成一条普通聊天消息来调用历史会话蒸馏 skill。IM 负责选择来源、执行 agent 与写入范围;Gateway 不解析蒸馏路径或注入 transcript 上下文。

#### Scenario: 用户在 IM 左侧面板选择 conversation 发起蒸馏
- **WHEN** 用户在 conversation 列表中进入"生成 skill"多选模式
- **THEN** 提供 checkbox 选择入口;`run_state=idle` 的 conversation 可选,`run_state=running` 的 conversation 禁选并显示"运行中"

#### Scenario: 单一来源 agent 时自动确定执行 agent
- **GIVEN** 用户已选择一个或多个 `run_state=idle` 的 conversation
- **WHEN** 用户点击"生成 skill"
- **THEN** 若所选 conversation 都属于同一个 agent,IM 自动把该 agent 作为执行 agent
- **AND** IM 弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到执行 agent 的新对话

#### Scenario: 跨 agent 来源时选择执行 agent
- **GIVEN** 用户已选择多个 `run_state=idle` 的 conversation,且这些 conversation 来自多个 agent
- **WHEN** 用户点击"生成 skill"
- **THEN** IM 弹窗让用户选择一个执行 agent
- **AND** 同一弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到执行 agent 的新对话

#### Scenario: 执行 agent 未启用历史会话蒸馏 skill
- **GIVEN** 执行 agent 的可见 skill 集合不包含 `conversation-skill-distiller`
- **WHEN** 用户点击"生成 skill"
- **THEN** IM 提示执行 agent 未启用历史会话蒸馏 skill
- **AND** 不跳转新对话,也不预填 `/skill:conversation-skill-distiller`

#### Scenario: 默认 conversation 列表不显示运行态标签
- **WHEN** 用户正常浏览 IM 左侧 conversation 列表,且未进入"生成 skill"多选模式
- **THEN** conversation 行不显示"已结束/运行中"这类运行态标签

#### Scenario: 用户通过范围弹窗指定生成级别后提交蒸馏
- **GIVEN** 新对话已预填所选 conversation 对应的 `source_jsonl_paths`
- **WHEN** 用户补充意图说明并提交
- **THEN** 对话将 `/skill:conversation-skill-distiller`、`source_jsonl_paths`、用户意图、`execution_agent_id` 与 `target_scope` 预填为用户可见消息
- **AND** 该消息按普通聊天消息发送;Gateway 不解析 `source_jsonl_paths`,不注入 transcript 上下文

#### Scenario: 蒸馏写入结果复用现有对话展示
- **GIVEN** 用户已发送预填后的蒸馏消息
- **WHEN** agent 成功调用 `skill_manage(create)` 写入 skill
- **THEN** IM 通过现有工具调用展示或普通 assistant 消息展示写入结果
- **AND** 不新增专门的 SKILL.md 草稿预览卡片、确认写入按钮或取消按钮

### Requirement: Web IM 聊天输入框支持把剪贴板图片加入待发附件

桌面端用户可以把剪贴板中的一张或多张图片直接粘贴到聊天输入框，并沿用既有附件的上传、待发、删除、发送与失败反馈能力；不包含图片的剪贴板内容继续由浏览器按原生编辑语义处理。

#### Scenario: 粘贴图片进入待发区
- **GIVEN** 终端用户已聚焦桌面 Web IM 聊天输入框
- **WHEN** 用户粘贴一张或多张图片
- **THEN** 合规图片按剪贴板顺序显示为可删除、可随消息发送的待发附件

#### Scenario: 图片带有文本或网页表示
- **GIVEN** 终端用户已聚焦桌面 Web IM 聊天输入框
- **WHEN** 用户粘贴同时包含图片与文本或网页表示的剪贴板内容
- **THEN** 图片显示为待发附件，输入框不额外插入伴随文本、网页地址或替代文本

#### Scenario: 纯文本或非图片内容保持原粘贴行为
- **GIVEN** 终端用户已聚焦桌面 Web IM 聊天输入框
- **WHEN** 用户粘贴的剪贴板内容不包含图片
- **THEN** 输入框保持浏览器原有粘贴行为，待发附件区不新增附件

#### Scenario: 图片被拒绝或上传失败
- **WHEN** 用户粘贴的图片不符合当前附件限制或上传失败
- **THEN** Web IM 显示可理解且可关闭的失败反馈，失败项不进入待发区，已经成功加入的附件继续保留
