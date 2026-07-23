# kernel / skills — delta (feat-474)

> 目标 canonical: `docs/specs/kernel/skills.md`

## ADDED Requirements

### Requirement: 经 agent 工具新建的子会话继承父会话 skills 配置

经 `agent` 工具新建子 agent 时，子会话的 `skills` 配置与父会话相同（`None` 表示未收窄、非空为白名单、空序列为零可见 skill），不得比父会话更宽。`agent` 工具不再接受单独的 skill 列表参数来加宽或覆盖。

#### Scenario: 子会话 skills 与父会话一致且不更宽
- **GIVEN** 父会话 `skills` 为某一配置（未收窄 / 白名单 / 空）
- **WHEN** 消费者经 `agent` 新建子 agent（不传已删除的 skill 列表字段）
- **THEN** 子会话面向模型可见的 skill 集合与父会话在同一 workspace 解析口径下一致，且不出现父不可见而子可见的 skill

## MODIFIED Requirements

### Requirement: 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致

`assemble_prompt_preview` 预览展示的技能、`list_skills(workspace_root)` 查询返回的技能、以及一次真实
session turn 注入 system prompt `<available_skills>` 的技能,对同一 `(workspace_root, skills)` 配置解析
出**同一集合**——搜索根均为 `<workspace_root>/<workspace_config_dirname>/skills` 叠加
`build_kernel(skill_search_roots=…)`,不存在「预览看得到、运行时看不到」的分歧。

#### Scenario: 预览与运行时技能一致
- **GIVEN** `build_kernel(skill_search_roots=…, workspace_config_dirname=…)` 装配的 Kernel,某 session
  的 `skills` 含若干在 workspace 配置目录或 `skill_search_roots` 下暴露的技能名
- **WHEN** 取 `assemble_prompt_preview(skill_ids=…, workspace_root=…)` 展示的技能,与该 session 真实
  执行一轮后 LLM 请求中 `<available_skills>` 列出的技能
- **THEN** 两者为同一集合(同名 + 同路径),不会出现预览齐全而运行时缩水成单个共享根技能的情形

#### Scenario: 未提供 workspace_config_dirname 时技能集合为空
- **GIVEN** 经 `build_kernel()` 未传入 `workspace_config_dirname`
- **WHEN** 取 preview / `list_skills` / 运行时注入的技能
- **THEN** 三者均为空,不隐式回退到 `~/.codex/skills` 等 legacy 默认路径

#### Scenario: list_skills 返回项携带 SKILL.md 路径
- **WHEN** 消费者调用 `list_skills(workspace_root)`
- **THEN** 返回的每个 `SkillInfo` 携带 `location`(该技能 SKILL.md 路径,可空),消费者据此区分同名但不同路径的技能

（归并说明：删除原 Scenario「子 agent 的 load_skills 校验与 list_skills 同口径」——`agent` 工具不再接受 `load_skills`。）

## REMOVED Requirements

（无整 Requirement 删除。）
