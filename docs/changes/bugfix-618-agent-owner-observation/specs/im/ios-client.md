# im/ios-client Specification delta

## ADDED Requirements

### Requirement: 原生客户端遵循 owner 只读观察权限

#### Scenario: 原生只读聊天
- **WHEN** owner 在原生客户端打开可观察协作私聊
- **THEN** 看到只读说明与双方消息，不显示 composer 或加入按钮，不将其误标为公开群。

#### Scenario: 观察会话列表与详情只读
- **WHEN** owner 长按、侧滑观察会话条目，或打开其详情
- **THEN** 条目保留查看入口，不提供置顶/静音等会话写操作；详情展示名称与真实参与者，不显示改名等写表单。
