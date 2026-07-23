# kernel / skills — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/skills.md`

## ADDED Requirements

（无。子 agent skill 可见范围改为继承父会话 `skills` 配置，由 tools-hooks / 会话配置行为覆盖；不新增独立 skill API。）

## MODIFIED Requirements

（无。）

## REMOVED Requirements

### Requirement: （原 Scenario 删除）子 agent 的 load_skills 校验与 list_skills 同口径

删除 Scenario「子 agent 的 load_skills 校验与 list_skills 同口径」整条：`agent` 工具不再接受 `load_skills` 参数，亦不再做该字段校验。
