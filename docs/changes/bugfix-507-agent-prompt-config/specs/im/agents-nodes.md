# IM Agents and Nodes Specification (delta for bugfix-507)

> 对齐 canonical: `docs/specs/im/agents-nodes.md`。

## MODIFIED Requirements

### Requirement: Agent 配置中心可读可改，版本乐观锁，新运行配置由既有聊天下一轮新回复采用

公开 Agent profile 和能力响应均不提供 `system_prompt`。`custom_prompt` 是唯一专属说明字段；
新 schema 不创建 retired prompt columns，Gateway 只同步该字段。

#### Scenario: 退休字段不能影响升级后的新回复

- **GIVEN** 某旧 profile、conversation snapshot 或 Gateway YAML 仍带 `system_prompt`
- **WHEN** 新版本读取 Agent 配置、同步 profile 或开始下一轮新回复
- **THEN** 该字段不被读取、展示、迁入 Custom Instructions 或传入运行时
- **AND** 已知生产存量的删除由发布操作完成，不属于 IM/Gateway 的自动迁移

## ADDED Requirements

### Requirement: Agent 专属说明只有可见的 Custom Instructions，预览覆盖全部稳定公开配置

Agent owner 通过 Custom Instructions 管理唯一会改变专属人设的公开文本。预览使用同一
`custom_prompt`、features、tools 与 skills 组装稳定提示词，并明确排除群聊、记忆等运行时上下文。

#### Scenario: 留空的 Custom Instructions 没有隐藏专属人设

- **WHEN** owner 打开或保存 Agent 配置，Custom Instructions 为空
- **THEN** Agent 不带任何由公开 Agent profile 注入的专属说明

#### Scenario: 预览可检查当前稳定专属说明

- **WHEN** owner 展开提示词预览，或编辑 Custom Instructions 后再次查看预览
- **THEN** 预览包含该 Agent 已保存或待保存的专属说明和已选能力配置
- **AND** 页面明确说明群聊、记忆等运行时内容不在预览内
