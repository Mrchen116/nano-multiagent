# Gateway external-channels Specification (delta for feat-572)

## ADDED Requirements

### Requirement: 自动获取消息附件不访问任意网络目标

#### Scenario: 正常 Web 和渠道附件
- **WHEN** Web IM 发送受保护图片，或飞书发送原生图片/Post 附件
- **THEN** Agent 仍可按既有图文顺序理解内容，IM 展示及正常渠道回复保持；自动获取使用受保护 IM 资源或已验证 provider 资源。

#### Scenario: 伪造目标与越权资源
- **WHEN** 消息图片或自动转发引用内网、loopback、任意外部 URL、跳转到非许可来源或未授权会话附件
- **THEN** 不因消息处理自动抓取目标或转发凭据；大小/类型/超时限制在实际读取时生效，不先无限下载再检查。
- **AND** 错误反馈能区分附件不可用且不泄漏令牌、内部地址细节或完整敏感 URL；普通链接不被自动当图片抓取。
