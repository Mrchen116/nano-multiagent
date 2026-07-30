# IM Web Chat UX Specification (delta for feat-484)

## MODIFIED Requirements

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

## ADDED Requirements

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
