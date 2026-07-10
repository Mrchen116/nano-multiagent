# Gateway delta-spec: feat-446 skills_usage WS RPC provider

## ADDED Requirements

### Requirement: Skills 使用统计 WS RPC

#### Scenario: IM 前端通过 gateway 读取 skill 使用统计
- **WHEN** gateway 收到 WS RPC `skills_usage_request`（含 agentId）
- **THEN** 读取该 agent workspace 的 `.usage.json`，聚合后返回 `skills_usage_response`

#### Scenario: workspace 不存在或 .usage.json 缺失
- **WHEN** agent workspace 不存在或 `.usage.json` 文件缺失
- **THEN** 返回空 skill 列表（不报错）

### Requirement: PA 内置 skill 启动自举

#### Scenario: Gateway 启动时安装缺失的 PA 内置 skill
- **WHEN** Gateway 启动并发现包内 `builtin_skills/<skill-name>/SKILL.md`
- **THEN** 若 `~/.nanoassistant/skills/<skill-name>/SKILL.md` 不存在，复制整个内置 skill 目录到该运行态全局 skill root
- **AND** 复制后的 skill 可被 PA agent 的 skill discovery 发现

#### Scenario: 用户已有同名内置 skill 时不覆盖
- **GIVEN** `~/.nanoassistant/skills/<skill-name>/SKILL.md` 已存在
- **WHEN** Gateway 启动
- **THEN** 不覆盖该目录中的用户文件

### Requirement: skill_manage create 后按 scope 默认启用

用户或 agent 通过 `skill_manage(create)` 成功创建新 skill 后，Gateway 必须按 scope 更新启用配置：`agent` 只启用给执行 agent，`global` 默认启用给所有 agent。该语义只覆盖本次创建事件，不把 workspace/global root 中所有已存在 skill 扫描式塞回 allowlist。

#### Scenario: 显式 skills allowlist 追加新建 agent skill
- **GIVEN** PA agent A 已持久化非空 `skills` allowlist，且不包含 `new-skill`
- **WHEN** A 的一次会话成功调用 `skill_manage(action="create", scope="agent", name="new-skill", ...)`
- **THEN** Gateway 将 `new-skill` 追加到 A 的启用 skills 配置
- **AND** 该配置持久化到 Gateway 本地 config 与 IM profile

#### Scenario: 未显式配置 skills 时不 materialize 全量列表
- **GIVEN** PA agent A 未显式配置 `skills` allowlist（运行时语义为全部可发现 skills）
- **WHEN** A 成功调用 `skill_manage(action="create", scope="agent", name="new-skill", ...)`
- **THEN** Gateway 不把全部可发现 skills 展开写入配置
- **AND** 新建 skill 在后续新 session 中按全部可发现语义可用

#### Scenario: 显式 skills allowlist 追加新建 global skill 到所有 agent
- **GIVEN** PA agent A 与 B 均已持久化非空 `skills` allowlist，且不包含 `shared-skill`
- **WHEN** 任一会话成功调用 `skill_manage(action="create", scope="global", name="shared-skill", ...)`
- **THEN** Gateway 将 `shared-skill` 追加到 A 与 B 的启用 skills 配置
- **AND** 这些配置持久化到 Gateway 本地 config 与 IM profile

#### Scenario: 未显式配置 skills 的 agent 不因 global skill materialize 全量列表
- **GIVEN** PA agent A 未显式配置 `skills` allowlist
- **WHEN** 任一会话成功调用 `skill_manage(action="create", scope="global", name="shared-skill", ...)`
- **THEN** Gateway 不把全部可发现 skills 展开写入 A 的配置
- **AND** `shared-skill` 在 A 的后续新 session 中按全部可发现语义可用

#### Scenario: 自动启用不热改已有 kernel session
- **GIVEN** agent A 已有绑定到 conversation 的 kernel session
- **WHEN** A 成功创建 skill 并触发配置更新
- **THEN** 已存在 kernel session 的系统提示词和 JSONL 不被改写
- **AND** Gateway 丢弃受影响 agent 的 conversation session binding，使下一条消息创建的新 kernel session 使用更新后的 skills 配置

## MODIFIED Requirements

### Requirement: PA agent 默认工具集合

本条修改 canonical Gateway/PA agent 配置契约：PA 产品默认工具集合新增 `skill_view`。该默认只在 agent 未显式配置工具白名单时生效；已有显式白名单仍是精确白名单。

#### Scenario: 未显式配置工具白名单的 agent 默认启用 skill_view
- **GIVEN** PA agent 没有持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 启用 PA 默认工具集合
- **AND** 默认工具集合包含 `skill_view`

#### Scenario: 显式工具白名单不被默认集合自动扩宽
- **GIVEN** PA agent 已持久化非空 `tool_allowlist`
- **WHEN** Gateway 为该 agent 创建新 session
- **THEN** session 只启用该白名单列出的工具
- **AND** 若白名单不含 `skill_view`，session 不启用 `skill_view`

#### Scenario: Gateway 上报能力时标记 skill_view 默认开启
- **WHEN** Gateway 向 IM 上报当前节点可配置工具
- **THEN** 工具列表包含 `skill_view`
- **AND** `skill_view` 的 `default_on` 为 true

## REMOVED Requirements

（无）
