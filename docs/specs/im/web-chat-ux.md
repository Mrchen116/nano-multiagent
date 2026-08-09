# IM - Web Chat UX Specification

> 对齐: bugfix-518
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

### Requirement: Web IM slash 面板发现并填写会话控制命令

用户在聊天输入框开头输入 `/` 时，slash 面板将 `/stop`、`/new`、`/compact` 与可用 skill 一起显示并按前缀过滤；用户可通过键盘或指针选择命令，输入框收到可直接发送的文本命令。在群聊中，`/new` 明确说明它会为群内所有 Agent 开始新会话。

#### Scenario: 单聊中从 slash 面板选择新会话
- **WHEN** 用户在单聊 composer 开头输入 `/` 或 `/new` 的未完成前缀
- **THEN** 面板显示 `/new` 及“在当前聊天中开始新会话”的说明
- **AND** 用户选择后，composer 填入可发送的 `/new`

#### Scenario: 群聊中从 slash 面板选择全体新会话
- **GIVEN** 当前群聊有多个 Agent 参与
- **WHEN** 用户在 composer 开头输入 `/`
- **THEN** 面板显示 `/new` 并说明它会为群内所有 Agent 开始新会话
- **AND** 用户选择后，composer 填入可发送的 `/new`

### Requirement: Web IM 消息气泡支持复制与长按/右键菜单

Web IM SHALL 让消息正文的文本选择、链接和代码优先使用浏览器原生交互，同时通过不干扰阅读的独立入口提供整条消息复制和既有 fork 能力。

#### Scenario: 桌面端选区使用浏览器原生复制
- **GIVEN** 终端用户在一条消息正文内建立了非空文本选区
- **WHEN** 用户使用复制快捷键，或在选区内右键并复制
- **THEN** 剪贴板只得到被选择的可见文字
- **AND** Web IM 不以整条消息菜单替换浏览器文本菜单

#### Scenario: 移动端正文与链接保留原生长按
- **WHEN** 终端用户在移动浏览器中长按消息正文或链接
- **THEN** 浏览器可以提供文本选择、选区调整或链接预览与操作
- **AND** Web IM 不弹出消息级操作菜单

#### Scenario: 桌面端普通消息区域打开短菜单
- **GIVEN** 当前消息没有覆盖触发点的文本选区，且触发点不在链接、代码或其他原生交互控件内
- **WHEN** 终端用户用 mouse 或 trackpad 右键消息气泡普通区域
- **THEN** Web IM 显示只包含当前消息可用动作的短菜单
- **AND** 菜单提供整条消息复制，并只对符合既有资格的 Agent 回复提供 fork

#### Scenario: 桌面端按需发现消息动作
- **WHEN** 终端用户悬停消息，或用键盘聚焦消息动作
- **THEN** Web IM 显示轻量消息 toolbar
- **AND** 普通阅读状态不常驻成排动作

#### Scenario: 触控环境通过 More 打开消息动作
- **GIVEN** 当前是 compact viewport，或设备存在 coarse pointer
- **WHEN** 终端用户点击消息 metadata 旁的 More 入口
- **THEN** Web IM 显示适合触控的短 action sheet
- **AND** action sheet 与 desktop 使用相同的整条复制和 fork 可用性

#### Scenario: 混合输入设备按本次输入自然响应
- **GIVEN** 同一设备同时支持 mouse 与 touch 或 pen
- **WHEN** 终端用户用 touch 或 pen 长按消息正文
- **THEN** Web IM 保留浏览器原生文本或链接操作，并提供独立 More 入口
- **WHEN** 终端用户改用 mouse 在无选区普通区域右键
- **THEN** Web IM 可以显示消息级短菜单

#### Scenario: 复制消息可见正文
- **GIVEN** 消息正文包含段落、列表、引用、表格、代码或链接
- **WHEN** 终端用户选择“复制整条消息”
- **THEN** 剪贴板得到结构可读的消息正文，具名链接同时保留链接文字与真实地址
- **AND** 不包含头像、发送者、时间、耗时、token、过程、思考、授权卡、投递状态或消息操作控件

#### Scenario: 显式整条复制不受页面选区影响
- **GIVEN** 页面中已有非空文本选区
- **WHEN** 终端用户对某条消息执行“复制整条消息”
- **THEN** 剪贴板得到被操作消息的完整正文
- **AND** 不误复制原有选区或另一条消息

#### Scenario: 消息或代码复制反馈
- **WHEN** Web IM 成功写入用户请求的整条消息或代码
- **THEN** 页面短暂显示本地化“已复制”反馈
- **WHEN** 浏览器无法写入剪贴板
- **THEN** 页面显示本地化失败反馈并让用户可以重试
- **AND** 当前聊天、阅读位置和未发送输入保持不变

#### Scenario: 键盘与触控可达
- **WHEN** 终端用户用键盘访问 toolbar、菜单、链接或代码复制，或在触控设备点击 More/action row
- **THEN** 所有入口有可理解的本地化名称、清晰焦点或足够触控区域
- **AND** 菜单关闭后焦点回到仍存在的发起入口

### Requirement: Web IM 桌面与移动端在聊天页保持一致的滚动与交互体验

无论是桌面浏览器还是移动浏览器，进入同一聊天页都能获得相同的分页加载、Enter 发送、composer 自动增高、正文可选择、整条复制和 eligible fork 能力；设备差异只体现在符合输入方式的入口。

#### Scenario: 在手机端向上滚动加载历史
- **WHEN** 终端用户在移动设备上打开同一聊天并向上滚动
- **THEN** 同样触发加载更早消息,且阅读位置保持稳定

#### Scenario: 在手机端从 More 对 Agent 回复 fork
- **GIVEN** 当前消息是符合既有 fork 资格的 Agent 回复
- **WHEN** 终端用户点击该消息的 More 并选择“从此处分支”
- **THEN** 触发既有 fork 流程并给出明确反馈
- **AND** 长按该消息正文仍保留系统文本选择能力

#### Scenario: desktop 与 mobile 使用同一消息动作资格
- **WHEN** 同一条消息分别显示在 desktop toolbar/context menu 与 mobile action sheet
- **THEN** 整条复制和 fork 的出现、enabled、disabled 与 in-flight 状态一致

### Requirement: Web IM 聊天链接按目标类型自然导航

Web IM SHALL 让外部网页链接在新标签页打开并保留当前聊天状态，让 IM 内链在当前产品内导航，同时保留浏览器原生链接操作。

#### Scenario: 普通点击外部网页链接
- **GIVEN** Agent 消息包含跨 origin 的 HTTP 或 HTTPS 链接
- **WHEN** 终端用户普通点击该链接
- **THEN** 浏览器在新标签页打开目标
- **AND** 当前聊天、阅读位置和未发送输入保持不变

#### Scenario: 普通点击 IM 内链或同源资源
- **GIVEN** Agent 消息包含相对地址、hash 或与当前 IM 同源的 HTTP/HTTPS 地址
- **WHEN** 终端用户普通点击该链接
- **THEN** 浏览器使用真实 anchor 在当前标签导航
- **AND** Web IM 不把未知同源文档、API 或下载地址强制交给 SPA Router

#### Scenario: 外链提示不重复网址
- **WHEN** 外链使用具名文字
- **THEN** Web IM 提供克制且可访问的新标签页提示
- **WHEN** 外链的可见文字本身就是完整网址
- **THEN** Web IM 不重复添加可见外链图标或文字

#### Scenario: 链接保留浏览器原生操作
- **WHEN** 终端用户悬停、键盘聚焦、右键或移动长按一个受支持链接
- **THEN** 链接保持真实 anchor 语义，并可使用浏览器提供的链接操作

#### Scenario: 不支持的链接目标
- **WHEN** Agent 消息包含空、malformed 或产品不支持 scheme 的链接目标
- **THEN** Web IM 保留其可见文字但不表现为可正常打开的链接
- **AND** 当前聊天不发生意外跳转

### Requirement: Web IM Agent 代码块支持独立复制

Web IM SHALL 为 Agent Markdown 中的每个 block code 提供独立、可访问的复制入口，不为 inline code 增加消息级操作。

#### Scenario: 复制一个代码块
- **GIVEN** 一条消息含一个或多个 fenced code block
- **WHEN** 终端用户执行某个代码块的复制动作
- **THEN** 剪贴板只得到该代码块的代码内容
- **AND** 保留代码缩进与内部空行，不包含代码围栏、其他正文或其他代码块

#### Scenario: 键盘复制代码块
- **WHEN** 键盘用户聚焦并执行代码块复制动作
- **THEN** 得到与指针或触控用户相同的代码内容和复制反馈

### Requirement: 历史会话蒸馏 conversation 选择入口

用户可从 IM 左侧 conversation 列表选择已完成、属于同一 Gateway 的会话生成 skill。IM 只按 source Agent
与其 `source_node_id` 做 owner、idle 和同节点选择；不扫描或读取 Gateway JSONL。用户确认 execution Agent 与
scope 后，IM 保留既有 distiller/`skill_view` preflight，并向该 Gateway 请求当前格式的 distill prompt。成功才新建
固定到该 node 的 execution Agent 单聊并原样预填 prompt；后续普通 relay 优先该固定 node，不因 Agent profile
重新注册而改送其他 Gateway。用户随后按既有普通聊天发送；builtin skill 继续从 prompt fields 读取该 Gateway
本机的 JSONL paths。

#### Scenario: 选择第一个来源后锁定同一 Gateway
- **WHEN** 用户在 conversation 列表进入“生成 skill”多选模式并选择一个 idle、带 source Agent 的会话
- **THEN** IM 用该会话的 `source_node_id` 锁定本次选择
- **AND** running、无 source Agent 或其他 Gateway 的会话不可选，并显示现有可理解原因

#### Scenario: Gateway 返回当前格式 prompt 后预填普通聊天
- **GIVEN** 用户选择同 Gateway sources、execution Agent 与 target scope
- **WHEN** IM 通过该 Gateway 成功取得 distill prompt
- **THEN** IM 创建 execution Agent 的 direct conversation，并原样预填包含
  `/skill:conversation-skill-distiller`、`source_jsonl_paths`、`execution_agent_id` 与 `target_scope` 的 prompt
- **AND** 用户可按既有方式补充意图并作为普通聊天消息发送；服务端固定路由优先于任何 client node hint，消息仍到生成该 prompt 的同一 Gateway

#### Scenario: execution Agent 不具备 distiller 或 skill_view 时不创建空聊天
- **WHEN** execution Agent 缺少 `conversation-skill-distiller` 或 `skill_view`
- **THEN** dialog 显示不可执行原因，且不请求或不接受 prompt
- **AND** 不创建或导航到新的 execution conversation

#### Scenario: 取得 prompt 失败时不创建空聊天
- **WHEN** target Gateway 离线，或不能为任一 source 解析本机 path
- **THEN** IM 在 dialog 显示可理解失败原因
- **AND** 不创建或导航到新的 execution conversation，也不发送普通 relay

#### Scenario: 普通 sidebar 浏览不显示蒸馏选择状态
- **WHEN** 用户未进入“生成 skill”选择模式
- **THEN** conversation 列表保持既有普通浏览外观
- **AND** 不显示 running、different Gateway 或 checkbox 等只服务于蒸馏选择的标签

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

### Requirement: Web IM 按当前语言和会话类型展示后台自进化提示

Web IM 在聊天时间线中把后台自进化结果显示为既有轻量 system 行：中文界面用中文、英文界面用英文，覆盖 skills、memory 与两者更新。群聊行显示产生该次 review 的 Agent 显示名，单聊不重复 Agent 名；system 行保持无头像、无发送者头和无消息操作。刷新、重进和实时到达使用同一结构化语义。

#### Scenario: 中文群聊显示来源 Agent 与更新对象
- **GIVEN** 当前界面语言为中文且 conversation 是包含多个 Agent 的群聊
- **WHEN** `SpecLab Product` 的 memory review notice 到达
- **THEN** 居中轻量 system 行以中文表达记忆已更新，并显示 `SpecLab Product`
- **AND** 该行不呈现为 Agent 消息气泡

#### Scenario: 英文群聊中的不同 Agent 分别归因
- **GIVEN** 当前界面语言为英文且群聊有多个 Agent
- **WHEN** 两个 Agent 先后产生 skills、memory 或两者更新 notice
- **THEN** 每行用英文表达自己的更新对象，并分别显示各自的来源 Agent 快照名

#### Scenario: 单聊本地化但不重复 Agent 名
- **WHEN** 用户在中文或英文 IM 单聊收到 self-evolution notice
- **THEN** system 行使用当前界面语言和正确更新对象
- **AND** 不额外显示当前 Agent 名

#### Scenario: 实时、刷新与语言切换使用同一语义
- **GIVEN** 一条结构化 self-evolution notice 已实时出现
- **WHEN** 用户刷新、重新进入 conversation 或切换界面语言
- **THEN** 来源归因与更新对象不变，文案按当时界面语言重新渲染

#### Scenario: 修复前历史提示不被改写
- **WHEN** 用户打开一条没有结构化 notice 的旧 system message
- **THEN** Web IM 继续显示其已存正文，不猜测来源 Agent 或改写历史语言

#### Scenario: fork 后的结构化提示继续按当前语言显示
- **GIVEN** direct-chat fork 带入了一条结构化 self-evolution notice
- **WHEN** 用户打开分支单聊或切换界面语言
- **THEN** 提示保留源消息的更新对象和来源快照，并按分支界面的当前语言显示

### Requirement: Web IM 收到的图片 attachment 以可辨认原图预览

Web IM 在消息流中直接预览收到的图片 attachment，保持图片原始宽高比并限制在聊天气泡可用范围内。attachment-only 用户消息不为获得气泡正文而合成无意义的文本占位符。

#### Scenario: attachment-only 图片消息直接显示图片
- **WHEN** 消息正文为空且携带一个图片 attachment
- **THEN** 用户在消息流中直接看到保持原比例的图片预览
- **AND** 消息不显示 `[图片]` 或空白正文气泡

#### Scenario: 正文和图片 attachment 同时存在
- **WHEN** 消息同时携带展示正文与图片 attachment
- **THEN** 用户在同一消息中看到正文和可辨认的图片预览
- **AND** 图片不会被固定裁剪成无法审阅内容的小方块
