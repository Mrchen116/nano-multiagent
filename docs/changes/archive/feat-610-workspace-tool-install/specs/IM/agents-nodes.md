## ADDED Requirements

### Requirement: Agent 配置页展示 workspace 自动工具的实际可用状态

Agent 配置页将 workspace 自建工具与静态工具选择分开展示，包含来源、工具说明及实际启用或不可用状态。已自动启用的工具不要求用户手工勾选，不因保存其他配置而把其名称加入静态白名单；停用/移除仍由聊天中的管理入口完成。

#### Scenario: 安装后查看与保存配置
- **GIVEN** Agent 已在 workspace 自助安装工具并实际可用
- **WHEN** 用户打开配置页并保存无关配置
- **THEN** 工具显示为 workspace 已启用，静态名单不添加工具名

#### Scenario: 关闭管理能力
- **GIVEN** workspace 工具仍安装但管理能力已关闭
- **WHEN** 用户重新打开配置页
- **THEN** 页面如实显示不可用，不把持久安装等同当前可调用
