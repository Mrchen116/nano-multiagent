# kernel (agent) - SDK Boundary Specification (delta for feat-519)

## MODIFIED Requirements

### Requirement: Kernel 提供单项中立能力查询

`kernel.list_models()` / `list_tools()` / `list_features()` / `list_skills(workspace_root)` 返回 SDK-owned 不可变数据，与已装配 Kernel 实际能力一致；内核不做产品语义聚合（payload 拼装 / available 计算归应用）。消费者可在 `build_kernel(workspace_skill_dirnames=…)` 声明有序 workspace Skill 目录名；`list_skills(workspace_root)` 先按该布局从真实 Workspace 派生 roots，再叠加 `build_kernel(skill_search_roots=…)` 传入的部署级共享 roots，按“workspace 布局顺序 → 共享根传入顺序”去重保序。未传入 `workspace_skill_dirnames` 时保持既有单一 `workspace_config_dirname/skills` 行为。`list_shared_skills()` 只查询已声明的共享 roots，用于尚无真实 Workspace 的候选场景，不借用 build-time repo root。

#### Scenario: 能力查询与运行时事实一致
- **GIVEN** 已装配的 Kernel
- **WHEN** 调四个 `list_*` 查询
- **THEN** models 含目录模型 + 默认、tools 含工具目录事实、features 为内核通用项投影、skills 为指定 workspace 的完整有序布局解析结果

#### Scenario: 消费者可在工具目录中启用 skill_view
- **WHEN** 消费者通过 `Kernel.list_tools()` 或 `Kernel.list_session_tools(...)` 查看包含默认自进化工具的工具目录
- **THEN** 返回的工具目录中包含真实工具名 `skill_view`

#### Scenario: 部署级共享 skill 根叠加在每 workspace 布局之后
- **GIVEN** `build_kernel(workspace_skill_dirnames=(D1, D2), skill_search_roots=(R1, R2))` 装配的 Kernel，某 workspace 在 D1/D2 下有 skill
- **WHEN** `list_skills(workspace_root)`
- **THEN** 返回 D1/D2 下的 workspace skill + R1/R2 中的 skill，顺序为“D1 → D2 → R1 → R2”去重
- **AND** 跨 workspace 调用时共享 roots 一致，workspace 部分各自派生

#### Scenario: 无真实 workspace 时只查询共享 Skill
- **GIVEN** 已装配 Kernel 声明共享 Skill roots，但尚无会执行 session 的真实 Workspace
- **WHEN** 消费者调用 `list_shared_skills()`
- **THEN** 返回项只来自共享 roots，不包含 build-time repo root 下的 workspace Skill
