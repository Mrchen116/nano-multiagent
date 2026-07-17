# feat-469: Web IM 粘贴图片附件

## Relations

- Closes: #202
- Related: feat-340

## 原始需求

> https://github.com/Mrchen116/nano-multiagent/issues/202
>
> ## 现象
>
> 在 Web IM 聊天页复制图片后按 Ctrl+V，输入框无反应，图片无法作为附件进入待发列表。
>
> ## 现状
>
> 聊天 composer 目前只有两条附件路径：
> - 拖拽文件进聊天窗口（`AttachmentDropzone`）
> - 点击附件按钮打开文件选择器
>
> 前端全仓（main 与当前分支）不存在任何 `onPaste` / `clipboardData` 处理器——粘贴事件从未接过。截图后想发图必须先存成文件再拖/选，操作链路长。
>
> ## 期望
>
> - 输入框 focus 时 Ctrl+V（macOS Cmd+V）读取剪贴板：
>   - 剪贴板含图片 → 转为 pending attachment（与拖拽同一上传通路 `uploadOneAttachment`），chip 列表可见、可删除
>   - 剪贴板为纯文本 → 保持现有文本粘贴行为不变
> - 图片粘贴与拖拽/选择器共用同一份校验（类型、大小上限）与失败反馈
>
> ## 实现提示
>
> - 接入点：`src/IM/frontend/src/features/chat/components/message-pane.tsx` composer 的 textarea 加 `onPaste`，从 `event.clipboardData.files` / `items` 取 `image/*` 条目，走 `use-attachment-upload` 同一 hook
> - 注意非 secure context（http://LAN-IP 访问）下 `navigator.clipboard.read` 不可用，但 `paste` 事件的 `clipboardData` 不受此限，应走事件路径而非主动读剪贴板 API
>
> 你按照change-spec，design，orchestrator系列skill，解决该问题。中途我不会任何介入不用问我任何问题。（注意，change-code-review的subagnet不需要每次开几个，会浪费token，只用一个替代）

## 澄清记录

- Q1: issue 未逐项拍板的产品边界与实现取舍是否需要继续向用户确认？
  A(原话): 中途我不会任何介入不用问我任何问题。
  Agent 解读: 用户已授权本 unit 基于 issue、当前产品行为与现有附件契约自主收口；不新增提问轮次。

## 用户场景

小林在桌面系统完成截图后，光标仍停留在 Web IM 的聊天输入框中。他直接按下系统粘贴快捷键，截图随即出现在 composer 的待发附件区，不需要先保存到磁盘。小林可以删除误粘贴的图片，也可以继续输入说明文字后把文字和图片一起发出。

当剪贴板里只有文本时，Web IM 仍按浏览器原有方式把文字插入光标位置，不把文本误当作附件。复制网页图片等同时携带图片和文本表示的内容时，Web IM 以图片附件为本次粘贴结果，不额外插入网页地址或替代文本。

粘贴图片沿用现有附件的格式、大小限制和错误表达。一次粘贴包含多张图片时，所有合规图片按剪贴板顺序进入待发区；若其中某张上传失败，已成功的图片仍保留，失败项给出明确反馈，用户可以继续编辑或重试。

## 验收标准

### Requirement: 聊天输入框支持把剪贴板图片加入待发附件

#### Scenario: 粘贴单张截图
- **GIVEN** 光标位于可编辑的 Web IM 聊天输入框
- **WHEN** 用户通过系统粘贴快捷键粘贴一张图片
- **THEN** 图片出现在 composer 的待发附件区
- **AND** 用户可以删除该图片或将其随消息发送

#### Scenario: 粘贴同时带有文本表示的图片
- **GIVEN** 光标位于可编辑的 Web IM 聊天输入框
- **WHEN** 用户粘贴的剪贴板内容同时包含图片和该图片的文本或网页表示
- **THEN** 图片进入待发附件区
- **AND** 输入框不额外插入网页地址、替代文本或其他伴随内容

#### Scenario: 一次粘贴多张图片
- **GIVEN** 光标位于可编辑的 Web IM 聊天输入框
- **WHEN** 用户一次粘贴多张图片
- **THEN** 所有合规图片按剪贴板中的顺序出现在待发附件区

### Requirement: 普通文本粘贴行为保持不变

#### Scenario: 粘贴纯文本
- **GIVEN** 光标位于可编辑的 Web IM 聊天输入框
- **WHEN** 用户粘贴不包含图片的纯文本
- **THEN** 文本按浏览器原有行为插入当前光标位置
- **AND** 待发附件区不新增附件

#### Scenario: 粘贴非图片文件
- **GIVEN** 光标位于可编辑的 Web IM 聊天输入框
- **WHEN** 用户粘贴的剪贴板内容仅包含非图片文件
- **THEN** Web IM 不把该文件加入待发附件区
- **AND** 输入框的普通粘贴行为不被阻断

### Requirement: 粘贴图片与其他附件入口共享限制和失败反馈

#### Scenario: 粘贴合规图片
- **WHEN** 用户粘贴符合当前附件格式和大小限制的图片
- **THEN** 图片与通过其他附件入口加入的图片呈现相同的待发状态和删除能力

#### Scenario: 粘贴图片被拒绝或上传失败
- **WHEN** 用户粘贴的图片不符合当前附件限制，或图片上传失败
- **THEN** Web IM 显示可理解的失败反馈
- **AND** 失败项不进入待发附件区，已经成功加入的附件继续保留

## 范围与非目标

- 在范围：桌面浏览器中、聊天输入框聚焦时通过 Ctrl+V / Cmd+V 触发的图片粘贴；图片与伴随文本的判定；多图片顺序；与现有附件上传、限制、待发 chip、删除、发送及错误表达的一致性；纯文本和非图片粘贴回归保护。
- 非目标：主动读取系统剪贴板；新增剪贴板权限申请；新增或重做文件选择按钮；支持把非图片剪贴板文件作为附件；改变服务端附件格式、大小上限或消息附件协议；重做 composer 视觉布局。
