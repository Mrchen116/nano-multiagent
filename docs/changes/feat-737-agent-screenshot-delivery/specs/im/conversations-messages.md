# IM Conversations and Messages Specification (delta for feat-737)

## ADDED Requirements

### Requirement: Intelligent UI 可预览同一消息的受保护图片附件

#### Scenario: 卡片按布局展示已交付截图
- **WHEN** Web 或原生 iOS 用户打开引用本消息图片附件的卡片
- **THEN** 图片按卡片布局显示，可点开原图，历史回看沿用消息所在会话的资源权限
- **AND** 同一图片已在卡片中显示时，附件区不重复展示

#### Scenario: 卡片或图像无法加载
- **WHEN** 客户端不能显示卡片内的图片
- **THEN** 同一消息的附件区仍提供原图入口
