# Delta: kernel - Tools and Hooks (bugfix-468)

> 对齐: bugfix-468
> 上级: [kernel Specification](../../../../../specs/kernel/spec.md)

## ADDED

### Requirement: 显式工具名单的会话在执行层拒绝名单外工具

会话携带显式 `tool_allowlist`(含空名单)时,执行层拒绝名单外的工具调用:工具不产生任何副作用,
调用方收到含「该工具未在本会话启用」语义与工具名的错误结果。名单为 None(未配置)时不做执行层
限制。拒绝措辞与权限拒绝、子代理拒绝相区分。

#### Scenario: 显式空名单会话全部工具被拒
- **GIVEN** 会话的 `tool_allowlist` 为显式空名单
- **WHEN** 模型调用任何工具
- **THEN** 工具不执行,返回含工具名与未启用语义的错误结果

#### Scenario: 显式非空名单只放行名单内工具
- **GIVEN** 会话的 `tool_allowlist` 为显式名单 [read, bash]
- **WHEN** 模型依次调用 read 与 edit
- **THEN** read 正常执行,edit 被拒并返回未启用错误

#### Scenario: 未配置名单的会话不限制
- **GIVEN** 会话未配置 `tool_allowlist`(None)
- **WHEN** 模型调用已注册工具
- **THEN** 工具按既有规则(权限门等)正常执行,无执行层额外限制

## MODIFIED

### Requirement: 工具参数校验错误逐条列出字段名

工具参数校验失败(missing / unexpected / 类型错误)时,错误文本按问题逐条列出字段名:缺失为
`The required parameter \`X\` is missing`,多余为 `An unexpected parameter \`Y\` was provided`,
类型错为 `The parameter \`Z\` type is expected as \`E\` but provided as \`A\``,多个问题组装为
多行错误返回。结构化 details(missing/unknown/field/expected)保持可供程序消费。

#### Scenario: 多个 required 字段缺失
- **WHEN** 模型调用工具时缺失两个以上 required 字段
- **THEN** 错误文本逐条列出每个缺失字段名,不再出现无字段名的笼统文案

#### Scenario: 类型错误列出字段与期望类型
- **WHEN** 模型为某字段提供了错误类型的值
- **THEN** 错误文本包含该字段名、期望类型与实际类型
