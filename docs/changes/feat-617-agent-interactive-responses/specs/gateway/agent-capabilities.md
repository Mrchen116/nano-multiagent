# Gateway agent-capabilities Specification (delta for feat-617)

## ADDED Requirements

### Requirement: 任意 Agent 可按任务需要交付通用交互回复

普通与 Global/Personal Agent SHALL 能为 Web IM 任务选择通用交互表达；简单文字任务不被强制转成表单。交互选择按真实用户来源进入既有任务执行链，界面不能绕过当前权限与公开交付约束。

#### Scenario: 不同任务选择表达方式
- **WHEN** 用户提出知识讲解、条件探索、方案比较、草稿修改或信息提醒
- **THEN** Agent 能组合适合的交互形式，并理解用户实际选择；不要求进入专用业务页面。

#### Scenario: 不支持交互的渠道
- **WHEN** Agent 向其他客户端或外部 channel 交付包含交互的内容
- **THEN** 用户得到可读文字摘要，原始界面源码不作为回复泄露。

### Requirement: Intelligent UI Feature 可配置

#### Scenario: 默认启用和显式关闭
- Agent 配置页 Features 提供 `intelligent_ui`，默认勾选，缺失值按开启解释。
- 取消勾选并保存后，运行时移除交互生成指导且发布接口拒绝新卡片；文字交付保留。重新勾选恢复。
- 关闭不删除已发布卡片、个人草稿或选择，历史卡片继续按原消息权限读取与提交。

### Requirement: 普通提问能主动获得适用交互表达

#### Scenario: 无界面提示的知识提问
- **WHEN** 用户只提出“给我讲解下冒泡排序”这样的普通问题
- **THEN** Agent 能主动用有助于理解过程的交互回复，不要求用户点名界面形式；实现与提示不含该题专用逻辑。
- **AND** 跨领域普通问题同样按内容选择表达，单一事实仍可简短文字回答。

#### Scenario: 保留 OpenUI 能力并遵守既有执行权限
- **WHEN** Agent 使用上游组件、局部状态、计算、动作或已接入查询/修改工具
- **THEN** 不因静态表单切片额外裁剪界面能力；真实业务工具执行继续受既有身份与审批约束，未接入能力如实说明。
