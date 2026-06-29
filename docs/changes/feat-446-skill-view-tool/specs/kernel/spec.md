# kernel delta-spec: feat-446 skill_view + skill_manage 变更

## ADDED Requirements

### Requirement: skill_view 工具可用

agent 通过 `skill_view` 工具按名字加载 skill 的完整内容。

#### Scenario: agent 调用 skill_view 读取 skill
- **WHEN** agent 调用 `skill_view(name="some-skill")`
- **THEN** 返回 `{success: true, name, content, location}`，content 为 SKILL.md 全文

#### Scenario: skill_view 调用记录使用统计
- **WHEN** agent 调用 `skill_view(name="some-skill")` 成功
- **THEN** 该 skill 的 use_count +1，last_used_at 更新，session 引用记录到 .usage.json

#### Scenario: skill_view 调用注册 compaction 存活
- **WHEN** agent 在 session 中调用 skill_view 成功
- **THEN** 该 skill 内容被注册到 invoked skills 列表，compaction 后以 system-reminder 形式重新注入

#### Scenario: skill_view 调用不存在的 skill
- **WHEN** agent 调用 `skill_view(name="nonexistent")`
- **THEN** 返回 `{success: false, error: "..."}`，不抛异常

## MODIFIED Requirements

### Requirement: skill_manage 工具 action 枚举

#### Scenario: skill_manage 不含 view action
- **WHEN** 查看 skill_manage 的 input_schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file，不含 view

## REMOVED Requirements

（无）
