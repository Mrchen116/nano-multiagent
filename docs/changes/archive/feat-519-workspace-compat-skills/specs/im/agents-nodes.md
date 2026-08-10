# IM - Agents and Nodes Specification (delta for feat-519)

## MODIFIED Requirements

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

新建/编辑 Agent 页需要的 runtime 候选项（skills / tools / models / features）由 IM **当场**经 gateway WS 向在线节点解析后返回，IM 不在本地持久化该能力目录，也不据 IM 部署机文件系统推断。节点级 `GET /im/v1/nodes/{id}/capabilities`（agent 尚不存在时用）与 agent 级 `GET /im/v1/agents/{id}/capabilities` 都把网关返回的 `features` 和每模型安全的 reasoning descriptor 透传给前端；节点级响应另透传可选的 `default_workspace_template`，供创建页展示该 Gateway 的默认路径，IM 不自行推导。Skill 候选的 `location` 和可选 `source_group` 亦由 Gateway 解析；IM 只透传，不直读 Gateway Workspace。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...], platform_default_model, default_workspace_template?, features:[...]}`；网关 payload 无 features 时 IM 返回空 `features` 列表（优雅降级）

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}`（可含 `requires_tool`）,由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider（例：`codex_oauth:gpt-5.5` → `openai_compat`，`kimiCoding:K2.6` → `anthropic`）,供 agent 配置页模型下拉展示格式

#### Scenario: 用户按有效模型能力选择推理设置
- **GIVEN** 创建或编辑页已取得在线节点能力
- **WHEN** 用户选择一个可调推理模型，或当前继承的 platform default 是可调推理模型
- **THEN** 页面只提供该 model descriptor 声明的 levels，并初始选择其 default
- **AND** 继承 default 时保存的 `default_model` 仍为空，只持久化用户明确选择的强度
- **WHEN** 有效模型是 fixed、平台默认不可解析，或目录未声明推理能力
- **THEN** 页面分别显示固定思考、无法确定模型或不可配置说明，不提交不属于有效模型的强度

#### Scenario: 可选模型列表每项携带安全的推理能力
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 若节点将模型声明为可调推理模型，model 含 `{kind:"selectable", default, levels}`；固定思考模型含 `{kind:"fixed"}`；未声明的模型不含 reasoning 字段
- **AND** 响应不含模型静态请求参数或上游密钥

#### Scenario: agent 能力的 skills 项携带 location 与来源分组
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `skills` 列表中每项携带实际命中的 `location`（SKILL.md 路径，可空）
- **AND** Gateway 能确定来源时，该 Skill 同时携带 `source_group: "workspace" | "global" | "compatibility"`，供配置页分组
- **AND** 同一 Agent 的同名 Skill 只返回有序 roots 中最先命中的版本；多 Agent 聊天的 SlashPicker 仍可用 `location` 区分不同 Agent 暴露的同名不同路径 Skill

#### Scenario: 旧节点未提供来源分组时安全降级
- **GIVEN** 在线 Gateway 返回的旧 capability payload 不含 `source_group`
- **WHEN** 前端打开 Agent 配置页
- **THEN** Skill 候选仍可显示和逐项选择
- **AND** 页面不因缺少该可选字段崩溃或误报能力请求失败

## ADDED Requirements

### Requirement: Agent 配置页可按 Skill 来源分组批量调整选择

Agent 创建/编辑页在已有 Skill 来源分组内提供紧凑的批量选择和取消选择能力，同时保留单个 Skill 的独立选择。分组状态清楚反映当前草稿中该组可见 Skill 的未选、部分选择或全选状态；批量操作沿用既有 profile draft、保存、Gateway apply 与下一轮生效流程，不增加立即生效旁路或脱离分组的笨重全局操作区。

#### Scenario: 用户批量选择一个来源分组后继续逐项调整
- **GIVEN** Agent 配置页的一个 Skill 来源分组有多个可选 Skill
- **WHEN** 用户对该分组执行批量选择
- **THEN** 该组当前可见 Skill 一同进入配置草稿
- **AND** 用户仍可在保存前取消或加入任意单个 Skill

#### Scenario: 用户批量取消部分已选分组
- **GIVEN** 某来源分组的全部或部分可见 Skill 已在配置草稿中选择
- **WHEN** 用户对该分组执行批量取消或修改其中一个 Skill
- **THEN** 页面清楚反映未选、部分选择或全选的实际状态
- **AND** 不把尚未保存的草稿误显示为已在运行时生效

#### Scenario: 窄屏配置仍保持清晰的分组操作
- **GIVEN** 用户在窄屏浏览器打开 Agent 创建或编辑页
- **WHEN** 页面显示多个 Skill 来源分组和其批量选择能力
- **THEN** 分组标题、选择状态和单个 Skill 仍可辨认与触达
- **AND** 不出现脱离 Skill 分组、占据页面主要空间的独立批量操作区

### Requirement: 配置 API 表达默认 Skill discovery 与显式 allowlist 的不同意图

Agent profile 的公开配置与保存结果表达 Skill selection mode：默认 discovery 使用当前可发现集合；explicit allowlist 只使用其 names，允许 names 为空。前端以该意图正确呈现有效选择，用户的首次单项或分组编辑将配置转为显式 allowlist；已有不带该意图的 profile 按既有语义兼容读取。

#### Scenario: 显式空选择在配置页和后续回复中一致
- **GIVEN** 用户在 Agent 配置页显式取消所有 Skill 并保存成功
- **WHEN** 用户重新打开配置页或在既有聊天开始下一轮回复
- **THEN** 配置页显示没有已选择的 Skill
- **AND** 新回复不使用默认 discovery 来重新启用全部可发现 Skill

#### Scenario: 保存后聊天候选立即采用新选择
- **GIVEN** 用户已在既有聊天打开过 SlashPicker，浏览器仍缓存旧 Skill 候选
- **WHEN** 用户在 Agent 配置页成功收窄或清空显式 allowlist 后立即回到该聊天
- **THEN** SlashPicker 重新解析候选，不在缓存有效期内继续显示已禁用 Skill

#### Scenario: 只读 mirror 不迁移历史缺席 mode
- **GIVEN** 某历史 Agent 的 Gateway YAML 与 IM mirror profile 未携带 selection mode
- **WHEN** IM 读取 mirror profile，或 Gateway 重连并以该 mirror 调和本地配置
- **THEN** 只读响应保留历史缺席状态，前端仍按有效语义呈现
- **AND** Gateway 不仅因这次读取或重连就在 YAML 中写入 mode
