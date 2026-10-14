> Delta baseline: branch canonical at `89c47478b054b8d788022752213ff6d494b5f9d9`. This extends the tool-install requirement to standard workspace plugins.

## MODIFIED Requirements

### Requirement: Agent 可在 workspace 自助安装原生工具

Agent 启用 `plugin_manager` 后，可以在可信配置确定的 workspace 创建标准 DSH bundle（包括工具、提示词和其他适用 workspace scope 的插件贡献），安装、启用、停用和移除。新增且不与既有工具名冲突的 workspace 工具自动并入该 Agent 的有效集合，不要求人工修改白名单。静态工具选择和禁用保持；关闭管理能力或显式空工具集不自动获得这些工具。子任务保留既有继承与角色限制。bundle 的启停由管理入口控制。

#### Scenario: 安装后既有聊天立即使用
- **WHEN** Agent 成功安装并启用 workspace 工具
- **THEN** 同 workspace 既有及新聊天可使用它，不需重启；其他 workspace 不可发现或执行

#### Scenario: 失败不声称已启用
- **WHEN** 包安装或实际加载失败
- **THEN** Agent 收到失败状态和真实诊断；包管理成功不代替执行可用证据

#### Scenario: 重启和撤销
- **WHEN** 节点重启或 Agent 停用/移除已安装 bundle
- **THEN** 重启保留持久选择，停用/移除后后续调用不可执行对应工具

#### Scenario: 保留其他工具选择
- **GIVEN** 已有禁用工具或显式空集
- **WHEN** 该 workspace 安装新增工具
- **THEN** 既有禁用选择不改变，空集不自动扩宽

#### Scenario: 非工具插件及整体停用
- **WHEN** Agent 安装不注册工具的提示词插件，随后用户停用或重新启用
- **THEN** 当前 workspace 的提示词贡献生效、撤销或恢复，其他 workspace 不受影响；DSH 生命周期管理的资源一并回收

#### Scenario: 网页与聊天管理同一原生插件状态
- **WHEN** 已认证的所属用户从 Agent 设置管理插件
- **THEN** Node 从可信 Agent 配置解析 workspace，网页与聊天操作同一份持久安装和启用状态，不修改宿主全局 profile
- **AND** 忙碌时网页操作等待 workspace 执行空闲，状态查询仍可用，并发管理明确返回忙碌而不死锁；未完成操作不报成功

#### Scenario: 停用状态在更新时保留
- **GIVEN** 已安装包处于停用
- **WHEN** Agent 更新同名包且没有显式要求开启
- **THEN** 包仍停用，重启保持已完成的选择
