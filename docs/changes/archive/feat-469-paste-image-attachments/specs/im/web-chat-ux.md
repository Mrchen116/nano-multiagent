# IM Web Chat UX Specification (delta for feat-469)

## ADDED Requirements

### Requirement: Web IM 聊天输入框支持把剪贴板图片加入待发附件

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
- **THEN** Web IM 显示可理解的失败反馈，失败项不进入待发区，已经成功加入的附件继续保留
