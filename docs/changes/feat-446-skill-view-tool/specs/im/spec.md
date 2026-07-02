# IM delta-spec: feat-446 skill 使用统计面板 + 历史会话蒸馏入口

## ADDED Requirements

### Requirement: Skill 使用统计 API

#### Scenario: 查询 agent 的 skill 使用统计
- **WHEN** 浏览器前端请求 `GET /im/v1/agents/:agentId/skills/usage`
- **THEN** 返回该 agent 的所有 skill 使用数据（name、source、state、use_count、last_used_at、session_refs）
- **AND** source 至少支持用户创建、历史会话蒸馏、自动创建、自动批量优化与 unknown

#### Scenario: agent 离线时查询 skill 统计
- **WHEN** agent 不在线（gateway 无法到达）
- **THEN** 返回 503 或空数据，前端显示离线提示

### Requirement: 历史会话蒸馏 conversation 选择入口

#### Scenario: 用户在 IM 左侧面板选择 conversation 发起蒸馏
- **WHEN** 用户在 IM 左侧 conversation 列表面板中右键 conversation 并进入"生成 skill"多选模式
- **THEN** 提供 checkbox 选择入口；`run_state=idle` 的 conversation 可选，`run_state=running` 的 conversation 禁选并显示"运行中"

#### Scenario: 用户确认写入范围后跳转新对话
- **GIVEN** 用户已选择一个或多个 `run_state=idle` 的 conversation
- **WHEN** 用户点击"生成 skill"
- **THEN** IM 弹窗让用户选择 agent 级或 PA 产品级写入范围
- **AND** 用户确认后跳转到新对话

#### Scenario: 默认 conversation 列表不显示运行态标签
- **WHEN** 用户正常浏览 IM 左侧 conversation 列表，且未进入"生成 skill"多选模式
- **THEN** conversation 行不显示"已结束/运行中"这类运行态标签

#### Scenario: 用户通过范围弹窗指定生成级别后提交蒸馏
- **GIVEN** 新对话已预填所选 conversation 对应的 `source_jsonl_paths`
- **WHEN** 用户补充意图说明并提交
- **THEN** 对话将 `/skill:conversation-skill-distiller`、`source_jsonl_paths`、用户意图与弹窗选择出的 `target_scope` 预填为用户可见消息
- **AND** 该消息按普通聊天消息发送；Gateway 不解析 `source_jsonl_paths`，不注入 transcript 上下文
- **AND** agent/蒸馏 skill 从消息文本读取 `source_jsonl_paths` 与 `target_scope`，自行读取 JSONL 路径并用于 `skill_manage(create, scope=...)`

#### Scenario: 蒸馏写入结果复用现有对话展示
- **GIVEN** 用户已发送预填后的蒸馏消息
- **WHEN** agent 成功调用 `skill_manage(create)` 写入 skill
- **THEN** IM 通过现有工具调用展示或普通 assistant 消息展示写入结果
- **AND** 不新增专门的 SKILL.md 草稿预览卡片、确认写入按钮或取消按钮

### Requirement: skill_view 工具调用审计展示

#### Scenario: skill_view 成功调用的折叠态可审计
- **WHEN** 浏览器前端展示一次成功的 `skill_view` 工具调用
- **THEN** 工具行显示真实工具名 `skill_view`，折叠态摘要显示"查看 skill：<name>"

#### Scenario: skill_view 成功调用的展开态展示内容
- **WHEN** 用户展开一次成功的 `skill_view` 工具调用
- **THEN** 展开态显示 skill name、location、content 预览，并提供展开全文入口

#### Scenario: skill_view 调用失败时展示失败态
- **WHEN** 浏览器前端展示一次 `success=false` 的 `skill_view` 工具调用
- **THEN** 工具行标红，展开态展示错误原因

### Requirement: Agent 配置页可管理 skill_view 工具

#### Scenario: 新建 agent 时默认选中 skill_view
- **WHEN** 用户在 IM 新建 PA agent 并进入工具选择区域
- **THEN** `skill_view` 出现在可选工具列表中
- **AND** 默认处于选中状态

#### Scenario: 用户取消 skill_view 后保存配置
- **WHEN** 用户在 agent 配置页取消选择 `skill_view` 并保存
- **THEN** IM 持久化该 agent 的显式工具白名单
- **AND** 白名单不包含 `skill_view`

#### Scenario: 已显式配置工具白名单的 agent 不自动选回 skill_view
- **GIVEN** agent 已持久化显式工具白名单，且其中不包含 `skill_view`
- **WHEN** 用户再次打开该 agent 配置页
- **THEN** `skill_view` 显示为未选中

## MODIFIED Requirements

### Requirement: Conversation 列表与 sync 响应

本条修改 canonical `/im/v1/conversations` 与 `/im/v1/sync` 的 conversation item 响应：新增通用运行态字段，不改变既有 conversation id / title / message 等字段语义。

#### Scenario: conversation 列表暴露通用运行态
- **WHEN** 浏览器前端请求 conversation 列表或 sync 数据
- **THEN** 每个 conversation item 包含通用字段 `run_state`，取值至少支持 `"idle"` 与 `"running"`；该字段不带 distill 命名，可被其他功能复用

## REMOVED Requirements

（无）
