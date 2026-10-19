# im/web-chat-ux Specification delta

## ADDED Requirements

### Requirement: Network 展示 Agent 私聊并标识只读

#### Scenario: Network 私聊入口
- **WHEN** owner 使用 Network 筛选
- **THEN** 包含有观察资格的 Agent 私聊和既有 Agent 群聊，显示双方身份。

#### Scenario: 只读观察界面
- **WHEN** owner 打开协作私聊
- **THEN** 能查看和滚动往来，明确只读，不显示输入、发送或加入入口；普通成员聊天仍可发言。


#### Scenario: 在线观察资格失效
- **GIVEN** 同账号同空间保持前台查看，只改变参与 Agent 的实际 owner
- **WHEN** 下一次权限复查拒绝读取
- **THEN** 清除当前正文、挂载媒体与过期列表条目，回到列表并显示不可访问提示；迟到历史响应不重新显示内容。
