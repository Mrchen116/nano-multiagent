# IM Agents and Nodes Specification (delta for feat-759)

## ADDED Requirements

### Requirement: Agent 配置页可直接编辑工作区角色约定

#### Scenario: 管理者直接读写角色
- **WHEN** PA 主人或独立 Agent 的管理者在 Web 或原生 iOS 打开使用文档记忆的 Agent 配置页
- **THEN** 页面可读取工作区现行角色约定并提供独立编辑与保存入口。本人主动保存就是对这份约定的确认。
- **AND** 保存成功表示节点已保存 `.nanoassistant/ROLE.md`。清空后页面显示未设置，主 Agent 恢复主动对齐。普通配置与角色分别保存，各自草稿互不提交。

#### Scenario: 草稿超过角色约定长度上限
- **WHEN** 角色约定草稿超过 2,000 个 UTF-16 码元
- **THEN** Web 和原生 iOS 显示长度提示并禁用保存。直接提交超限内容时，服务端拒绝写入。

#### Scenario: 编辑期间角色变化或节点不可用
- **GIVEN** 用户有未保存的角色草稿
- **WHEN** 文件版本变化、读取失败、连接断开或保存结果未确认
- **THEN** 保留草稿，显示可确认的状态。获取当前版本后，由用户核对再主动保存，旧草稿不自动覆盖现行文件。

#### Scenario: 角色约定是管理者专用内容
- **WHEN** 非管理者浏览公开资料或请求角色设置
- **THEN** 不获得约定正文或编辑能力。节点当前无法读取时，页面不会将未取得的数据视为未设置。

## MODIFIED Requirements

### Requirement: Agent 专属说明只有可见的 Custom Instructions，预览覆盖全部稳定公开配置

本需求替换为 ROLE 唯一用户角色来源；名称在归并时更新为“Agent 用户角色约定唯一入口与系统配置预览”。

#### Scenario: 查看与编辑用户角色
- **WHEN** 管理者在Web或iOS创建、查看或编辑Agent
- **THEN** 只提供角色约定入口，不提供独立Custom Instructions，不读写custom_prompt。已有ROLE独立保存，普通配置保存不能覆盖其正文。

#### Scenario: 稳定系统配置预览
- **WHEN** 管理者查看提示词预览
- **THEN** 展示适用系统角色与所选能力；PA服务默认指导由系统提供。预览不把未保存ROLE当作已生效内容，明确排除运行时角色文件、记忆和聊天。

#### Scenario: 一次性迁移退休用户配置
- **WHEN** 获授权部署新版
- **THEN** 按unit部署提示词将应保留的旧用户指令归入ROLE，去除旧字段；产品不自动迁移或兼容读取custom_prompt/system_prompt。

### Requirement: Agent 创建必须挂在已绑定且在线的节点下,workspace_root 仅在创建时由节点确定

以下场景增加到已有节点创建与恢复契约，其他既有场景不变。

#### Scenario: 初始角色与创建结果一致
- **WHEN** 用户通过客户端或PA提交带initial_role的创建请求
- **THEN** 仅在目标workspace实际保存该角色后才确认创建成功；正文不得超过2,000 UTF-16单元。未填写则保持角色未设置。
- **AND** 初始角色仅在持久创建意图中保留，不成为长期配置副本。重复请求必须匹配同一初始角色，创建完成后的恢复不覆盖后续用户编辑。
- **AND** 复用已有工作区时，不覆盖不同的非空ROLE，冲突有明确结果。普通配置更新不能提交initial_role。
