# IM Web Chat UX Specification (delta for bugfix-512)

## ADDED Requirements

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
