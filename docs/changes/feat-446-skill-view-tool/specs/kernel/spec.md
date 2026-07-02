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

#### Scenario: 重放同一次 skill_view 不重复计数
- **GIVEN** 同一次 `skill_view` 成功调用已经用 `{session_id, tool_call_id}` 记录过
- **WHEN** 系统因恢复或事件重放再次处理该调用
- **THEN** use_count 不再增加，session 引用不重复追加

#### Scenario: skill_view 调用注册 compaction 存活
- **WHEN** agent 在 session 中调用 skill_view 成功
- **THEN** 该 skill 的 name/location 被注册到 invoked skills 列表，compaction 时重新读取当前 SKILL.md 内容，并以 `<system-reminder>` 形式重新注入

#### Scenario: skill_view 调用不存在的 skill
- **WHEN** agent 调用 `skill_view(name="nonexistent")`
- **THEN** 返回 `{success: false, error: "..."}`，不抛异常

#### Scenario: skill_view 同名 skill 按候选优先级读取
- **GIVEN** 当前会话可见集合中存在多个同名 skill
- **WHEN** agent 调用 `skill_view(name="same-name")`
- **THEN** 内核按 `<available_skills>` / `/skill:` 候选使用的既有 search root 优先级读取第一项
- **AND** 返回结果中的 `location` 指向实际命中的 SKILL.md

## MODIFIED Requirements

### Requirement: Skill 自动发现走 prompt 列表,显式调用改写为自然语言

本条修改 canonical `docs/specs/kernel/spec.md` 中同名 Requirement：可发现 skill 仍通过 `<available_skills>` 暴露，显式 `/skill:<name>` 仍只改写为自然语言请求；但 guidance 从“读 location 文件”改为“调用 `skill_view(name=...)` 加载 skill 内容”。

#### Scenario: skill_view 启用时 available skills guidance 引导 skill_view
- **GIVEN** 消费者创建的 session 启用了 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** `<available_skills>` 中每个 skill 仍包含 name / description / location，且 guidance 指示 agent 通过 `skill_view` 按名字加载 skill 内容

#### Scenario: skill_view 关闭时不渲染 skill_view 调用 guidance
- **GIVEN** 消费者创建的 session 未启用 `skill_view`
- **WHEN** 系统提示词包含 `<available_skills>`
- **THEN** guidance 不指示 agent 调用 `skill_view`

#### Scenario: /skill 显式调用仍改写为自然语言
- **WHEN** 用户输入 `/skill:some-skill`
- **THEN** 内核仍把它改写为使用 `some-skill` 的自然语言请求，不在改写阶段直接读取文件
- **AND** 若 session 启用了 `skill_view`，agent 后续按 guidance 调用 `skill_view`

### Requirement: skill_manage 工具 action 枚举

本条补充 kernel built-in 工具 schema 约束：当前 canonical 未单列 action 枚举 Requirement，收尾时应归并到内置工具列表 / skill 工具能力相关条目。

#### Scenario: skill_manage 不含 view action
- **WHEN** 查看 skill_manage 的 input_schema
- **THEN** action 枚举为 create / edit / patch / list / write_file / remove_file，不含 view

#### Scenario: skill_manage create 支持受控写入范围
- **WHEN** 查看 skill_manage 的 input_schema
- **THEN** create action 支持可选 `scope: "agent" | "pa"`，默认 `"agent"`

#### Scenario: skill_manage create 写入 PA root
- **GIVEN** 当前产品启用了 PA 产品级 skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="pa", ...)`
- **THEN** 新 skill 写入 PA 产品级 skill root，而不是当前 agent workspace skill root

#### Scenario: PA root 不可用时不回退
- **GIVEN** 当前产品未启用 PA 产品级 skill root
- **WHEN** agent 调用 `skill_manage(action="create", scope="pa", ...)`
- **THEN** 工具返回 success=false，不写入 agent root

### Requirement: 内置工具列表包含 skill_view

#### Scenario: 消费者可在工具目录中启用 skill_view
- **WHEN** 消费者通过 `Kernel.list_tools()` 或 `Kernel.list_session_tools(...)` 查看包含默认自进化工具的工具目录
- **THEN** 返回的工具目录中包含真实工具名 `skill_view`（与 `skill_manage`、`memory` 并列）

### Requirement: 工具展示由工具自带的 presenter 决定

本条修改 canonical `docs/specs/kernel/spec.md` 中同名 Requirement：`skill_view` 和现有 `memory` / `skill_manage` 一样可返回结构化 summary/detail，供客户端做专属展示。

#### Scenario: skill_view 产出结构化展示数据
- **WHEN** `skill_view` 调用完成
- **THEN** tool result 事件包含可透传给客户端的 summary/detail，summary 能表达查看了哪个 skill，detail 包含 name / location / content preview / success 或 error 信息

### Requirement: Skill 生命周期状态影响可见集合

#### Scenario: stale skill 仍可发现和读取
- **GIVEN** skill A 的 usage state 为 stale
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 仍在候选中，并可通过 `skill_view(name="A")` 读取；读取成功后恢复为 active

#### Scenario: archived skill 退出日常候选
- **GIVEN** skill A 的 usage state 为 archived，且目录已移动到 `.archive/`
- **WHEN** 内核生成 `<available_skills>` 或处理 `/skill:` 候选
- **THEN** skill A 默认不出现在候选中，`skill_view(name="A")` 按找不到处理

### Requirement: Per-skill batch 优化由 skill_view 越线触发

#### Scenario: 自动 skill 使用计数越线后触发 batch
- **GIVEN** 自动创建的 skill A 的 `uses_since_last_B` 在一次成功 `skill_view` 后达到阈值
- **WHEN** 该 `skill_view` 调用完成
- **THEN** 内核 enqueue skill A 的 per-skill batch review，不等待 Curator 7 天扫描

#### Scenario: 手工 skill 越线不自动 batch
- **GIVEN** skill A 来源为用户创建、历史会话蒸馏、manual 或 unknown
- **WHEN** 一次成功 `skill_view` 让 `uses_since_last_B` 达到阈值
- **THEN** 内核不 enqueue 自动 batch review

## REMOVED Requirements

（无）
