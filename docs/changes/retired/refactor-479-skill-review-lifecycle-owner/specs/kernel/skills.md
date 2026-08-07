# Kernel Skills delta — refactor-479

> 本 delta 对 `docs/specs/kernel/skills.md` 的已漂移 scope 词汇做 current-state 校正。
> 生产行为已经使用 `global`；本 unit 只把 canonical 归并到该消费者可观察事实。

## MODIFIED Requirements

### Requirement: skill_manage 工具 action 枚举保持写入与列表语义

`skill_manage` 是写入/维护 skill 的工具，不承担读取全文的 view action；读取全文由
`skill_view` 承担。

#### Scenario: skill_manage 不含 view action
- **WHEN** 消费者查看 `skill_manage` 的 input schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file，不含 view

#### Scenario: skill_manage create 支持受控写入范围
- **WHEN** 消费者查看 `skill_manage` 的 input schema
- **THEN** create action 支持可选 `scope: "agent" | "global"`，默认 `"agent"`

#### Scenario: skill_manage create 写入 product global root
- **GIVEN** 当前产品经 `build_kernel` 提供了 product global skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="global", ...)`
- **THEN** 新 skill 写入 product global skill root，而不是当前 agent workspace skill root

#### Scenario: product global root 不可用时不回退
- **GIVEN** 当前产品未提供 product global skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="global", ...)`
- **THEN** 工具返回 `success=false`，不写入 agent root
