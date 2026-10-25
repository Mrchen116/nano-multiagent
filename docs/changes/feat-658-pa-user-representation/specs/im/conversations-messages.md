# IM conversations-messages Specification (delta for feat-658)

## MODIFIED Requirements

### Requirement: Agent 交互回复与普通消息共同持久化和授权

交互内容 SHALL 属于已公开且由真实 Agent 提供的消息，包括经审核的 PA 代表用户消息，按同一会话权限读取；公开作者与实际执行 Agent 分别保留。文字摘要在不支持交互的客户端仍可独立阅读。重复交付不新增同一消息，私有草稿不自动公开。

#### Scenario: 刷新与节点离线
- **WHEN** 用户刷新、换设备或 Agent 节点离线后读取交互回复
- **THEN** 已交付内容及已确认结果仍可读，未授权用户不能读取。

#### Scenario: 分支与原会话删除
- **WHEN** 用户 fork 含交互内容的历史，再删除原会话
- **THEN** 复制范围内公开内容与确认结果仍可读；旧交互作为只读历史，不复制私人未提交草稿。

## ADDED Requirements

### Requirement: 通用草稿采用只填入目标输入框

#### Scenario: 编辑后采用
- **WHEN** 用户在 Web 或原生 iOS 编辑普通 Agent 或 PA 的卡片，并触发 ComposeMessage
- **THEN** 按实际点击用户的目标会话写权限，将点击时文本放入明确目标聊天输入框；不发送会话消息、交互请求或启动 Agent，由用户后续自行发送。
- **AND** 不要求原消息绑定；目标后来有新消息不自动使草稿失效，私有编辑状态不回传卡片作者。

#### Scenario: 目标不可写或已有草稿
- **WHEN** 用户采用时目标不可写、失效，或已有不同未发送内容
- **THEN** 无权限时保留编辑并说明原因；已有草稿时可取消或明确替换，不能静默覆盖或混合旧附件；替换后仍未发送。

#### Scenario: 与明确请求区分
- **WHEN** 用户点击 ToAssistant 等明确提交请求的动作
- **THEN** 继续按现有交互确认契约提交本会话消息；ComposeMessage 不以默认按钮提交或组合隐藏提交改变其仅填稿含义。
- **AND** 被替换或 fork 的只读卡片不接受新的采用动作。
