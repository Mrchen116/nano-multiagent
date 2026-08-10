# kernel (agent) - Skills Specification (delta for feat-519)

## MODIFIED Requirements

### Requirement: 同一 workspace 下 preview、list_skills 与运行时注入的技能集合一致

`build_kernel()` 的消费者可提供有序的工作区 Skill 目录布局以及有序的共享 Skill roots。对同一 `(workspace_root, skills)` 配置，`assemble_prompt_preview`、`list_skills(workspace_root)`、真实 session turn 注入的 `<available_skills>`，以及该 session 的 `skill_view`，必须从同一有序 root sequence 解析同一集合和同一同名覆盖结果。工作区 roots 先于共享 roots；同名 Skill 采用最先命中的 root，且返回实际命中的 `location`。未声明扩展工作区布局的 consumer 保持其既有单个 workspace config Skill 目录行为。

#### Scenario: 多个有序工作区目录在各读取路径中一致
- **GIVEN** 某 SDK consumer 为一个 workspace 声明多个有序的工作区 Skill 目录，且这些目录与共享 roots 中存在独有或同名 Skill
- **WHEN** 消费者查询 `list_skills`、组装同一 skills 配置的 prompt preview、执行一轮 session 并调用 `skill_view`
- **THEN** 四条路径发现相同的 Skill names 和实际 `location`
- **AND** 同名 Skill 均采用有序 root sequence 中最先命中的版本

#### Scenario: 预览与运行时技能一致
- **GIVEN** `build_kernel()` 装配的 Kernel 为某 workspace 声明 Skill root layout，某 session 的 `skills` 含若干可发现的 Skill names
- **WHEN** 取 `assemble_prompt_preview(skill_ids=…, workspace_root=…)` 展示的技能，与该 session 真实执行一轮后 LLM 请求中 `<available_skills>` 列出的技能
- **THEN** 两者为同一集合（同名 + 同路径），不会出现预览齐全而运行时使用另一组 roots 的情形

#### Scenario: 未提供额外 workspace Skill layout 时保持既有单目录默认
- **GIVEN** 经 `build_kernel()` 未传入新的 `workspace_skill_dirnames`
- **WHEN** 取 preview、`list_skills` 或运行时注入的技能
- **THEN** 三者只从有效 `workspace_config_dirname` 派生一个 workspace Skill root，再叠加消费者显式传入的共享 roots
- **AND** 连 `workspace_config_dirname` 也省略时，保持 SDK 当前使用 `.nano` 的默认，不因本 unit 改变外部 consumer 行为

#### Scenario: list_skills 返回项携带 SKILL.md 路径
- **WHEN** 消费者调用 `list_skills(workspace_root)`
- **THEN** 返回的每个 `SkillInfo` 携带实际命中 Skill 的 `location`（该技能 SKILL.md 路径，可空），消费者据此区分当次解析来源

## ADDED Requirements

### Requirement: Skill 管理写入不因兼容读取 root 改变目标目录

消费者为 session 声明多个只读兼容 Skill roots 时，`skill_manage` 的 agent scope 仍只写入该消费者声明的原生 agent Skill root；兼容 roots 参与候选和 `skill_view` 读取，不成为 agent scope 的写入目标。

#### Scenario: 管理工具从兼容 root 读取但写入原生 root
- **GIVEN** 某 session 可从兼容工作区或共享 root 发现一个 Skill，且消费者声明了原生 agent Skill root
- **WHEN** agent 读取该 Skill 后以 agent scope 创建另一个 Skill
- **THEN** 读取返回兼容 Skill 的实际 location
- **AND** 新 Skill 写入原生 agent Skill root，不修改兼容目录中的已有文件

### Requirement: SDK 消费者可在没有真实 workspace 时只查询共享 Skill roots

当 SDK consumer 尚未拥有一个将实际执行 session 的 Workspace（例如准备创建 Agent 时），它可请求只从其声明的共享全局 roots 发现 Skill，而不以 build-time repo root 或任意占位路径派生 workspace roots。已拥有真实 Workspace 的 session/list/preview 继续使用完整有序 layout。

#### Scenario: prospective Agent capability 不把 repo workspace Skill 当候选
- **GIVEN** 某 consumer 的 build-time repo root 含 workspace Skill，但待创建 Agent 尚无 canonical workspace
- **WHEN** consumer 查询仅用于创建表单的共享 Skill candidates
- **THEN** 返回项只来自消费者声明的共享全局 roots
- **AND** repo root 下的 workspace Skill 不作为可选择的 prospective Agent Skill 返回
