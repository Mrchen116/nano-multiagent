# IM Agents and Nodes Specification (delta for bugfix-500)

## ADDED Requirements

### Requirement: 新建 Agent 页提供连续导航并保护未提交草稿

桌面端从 Agent 列表或节点入口进入新建页时，保持与 Agent 详情页一致的 Agent 导航栏；移动端保持单栏创建流程。用户一旦编辑表单，任何站内离开操作都必须先确认，避免草稿因误触丢失。

#### Scenario: 桌面端两个新建入口保持 Agent 导航
- **WHEN** 用户在桌面端打开 `/settings/agents/new` 或 `/settings/nodes/{node_id}/agents/new`
- **THEN** 新建页显示已有 Agent 的导航栏，并可在未编辑表单时直接切换
- **AND** 移动端仍只显示单栏创建流程

#### Scenario: 有草稿时确认站内离开
- **GIVEN** 用户已编辑新建 Agent 表单但尚未提交
- **WHEN** 用户通过 Agent 导航、取消、应用导航、用户菜单或浏览器后退离开页面
- **THEN** 页面要求确认退出，取消确认后保留当前草稿
- **AND** 用户确认后才进入原目标
