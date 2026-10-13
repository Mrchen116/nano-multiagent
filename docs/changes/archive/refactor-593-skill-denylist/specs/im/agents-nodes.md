# IM agents-nodes delta for refactor-593

## ADDED Requirements

### Requirement: Skill 配置保存取消项

#### Scenario: 新增技能与手动选择
- **WHEN** 用户创建或编辑 Agent 的技能选择
- **THEN** 勾选表示启用，取消项保存为 `explicit_denylist` 下的禁用名称；Workspace、全局、兼容来源使用相同规则
- **AND** 界面说明新技能默认启用，重新打开后已禁用项保持未选；暂时缺失的禁用名称不被丢弃

### Requirement: 配置 API 表达 Skill 禁用名单与旧选择模式

Agent profile 的公开配置与保存结果表达 Skill selection mode：explicit denylist 的 names 是禁用名称；勾选代表启用，首次单项或分组编辑保存取消项。尚未迁移的 default discovery / explicit allowlist 按既有语义读取；认证节点上线后以真实候选迁移。

#### Scenario: 显式空选择在配置页和后续回复中一致
- **GIVEN** 用户在 Agent 配置页显式取消所有 Skill 并保存成功
- **WHEN** 用户重新打开配置页或在既有聊天开始下一轮回复
- **THEN** 配置页显示保存时所有候选均未选择；之后新增名称默认启用
- **AND** 新回复不重新启用已保存的禁用名称

#### Scenario: 保存后聊天候选立即采用新选择
- **GIVEN** 用户已在既有聊天打开过 SlashPicker，浏览器仍缓存旧 Skill 候选
- **WHEN** 用户在 Agent 配置页成功禁用部分或全部当前 Skill 后立即回到该聊天
- **THEN** SlashPicker 重新解析候选，不在缓存有效期内继续显示已禁用 Skill

#### Scenario: 只读 mirror 保留旧模式，认证迁移单独提交
- **GIVEN** 某历史 Agent 的 Gateway YAML 与 IM mirror profile 未携带 selection mode
- **WHEN** IM 只读 mirror profile
- **THEN** 只读响应保留历史缺席状态，前端仍按有效语义呈现
- **AND** 只读本身不写 YAML；认证节点重连后的独立迁移使用真实候选和版本化配置操作写入禁用名单

## REMOVED Requirements

### Requirement: 配置 API 表达默认 Skill discovery 与显式 allowlist 的不同意图
