# IM - Agents and Nodes Specification (delta for bugfix-505)

## MODIFIED Requirements

### Requirement: 桌面 Agent 页面提供连续导航，并保护新建草稿

桌面端从 Agent 列表或节点入口进入新建页，以及打开或切换既有 Agent 详情时，保持 Agent 导航栏。详情请求处于 loading 或 initial error 时，导航栏仍可用，内容区显示局部 loading/error 状态与可重试操作；移动端保持单栏流程。用户一旦编辑新建表单，任何站内离开操作都必须先确认，避免草稿因误触丢失。

#### Scenario: 桌面端两个新建入口保持 Agent 导航
- **WHEN** 用户在桌面端打开 `/settings/agents/new` 或 `/settings/nodes/{node_id}/agents/new`
- **THEN** 新建页显示已有 Agent 的导航栏，并可在未编辑表单时直接切换
- **AND** 移动端仍只显示单栏创建流程

#### Scenario: 桌面端详情切换期间保持 Agent 导航
- **WHEN** 用户在桌面端打开或从一个 Agent 切换到另一个 Agent，详情请求处于 loading 或返回 initial error
- **THEN** Agent 导航栏保持可见且可切换，内容区仅显示该 Agent 的局部 loading/error 状态
- **AND** error 状态提供重试操作，移动端仍只显示单栏内容

#### Scenario: 有草稿时确认站内离开
- **GIVEN** 用户已编辑新建 Agent 表单但尚未提交
- **WHEN** 用户通过 Agent 导航、取消、应用导航、用户菜单或浏览器后退离开页面
- **THEN** 页面要求确认退出，取消确认后保留当前草稿
- **AND** 用户确认后才进入原目标
