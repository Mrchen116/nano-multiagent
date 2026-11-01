# IM Agent 目录契约增量

## MODIFIED Requirements

### Requirement: 节点 runtime 能力按需向在线网关解析,不入库快照

工具候选合并 Gateway 的 PA 内置声明与对应上下文中已注册的工具：内置声明保持既有顺序及 default_on，其他注册工具去重追加、default_on=false；已有注册项携带真实描述，缺失 runtime 实例的内置声明仍保留。节点创建页使用共享目录，Agent 编辑页还包含其工作区工具并采用该工作区的同名覆盖。候选可见不代表已启用；选中状态和保存值仍由用户配置决定，不因新增候选而扩大已有白名单（含显式空集），global 固定基础工具规则不变。

新建/编辑 Agent 页需要的 runtime 候选项（skills / tools / models / features）由在线 Gateway 解析，IM 可在相同 owner、绑定、连接、Workspace 和配置版本下复用最长五分钟的内存候选缓存，IM 不在本地持久化该能力目录，也不据 IM 部署机文件系统推断。Agent 设置页可保留已成功取得的有限展示信息，供离线只读；这些信息带真实取得时间，不作为当前候选目录、保存校验或操作许可；缓存命中不伪造新的确认时间，保存仍由运行时按真实候选校验。节点级 `GET /im/v1/nodes/{id}/capabilities`（agent 尚不存在时用）与 agent 级 `GET /im/v1/agents/{id}/capabilities` 都把网关返回的 `features` 和每模型安全的 reasoning descriptor 透传给前端；节点级响应另透传可选的 `default_workspace_template`，供创建页展示该 Gateway 的默认路径，IM 不自行推导。Skill 候选的 `location` 和可选 `source_group` 亦由 Gateway 解析；IM 只透传，不直读 Gateway Workspace。

#### Scenario: 节点能力含 features 列表供创建页渲染
- **GIVEN** 一个已知节点,网关在线
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities`
- **THEN** 200 返回 `{node_id, skills:[{name,description}], tools:[{name,description}], models:[...], platform_default_model, default_workspace_template?, features:[...]}`；网关 payload 无 features 时 IM 返回空 `features` 列表（优雅降级）

#### Scenario: 用户发现并启用新安装的共享工具
- **GIVEN** 在线 Gateway 已成功注册共享用户工具 T
- **WHEN** 用户打开该节点的新建页或其 Agent 的编辑页
- **THEN** 工具候选包含 T 及其注册描述，新建默认不选中 T；已有 Agent 未启用 T 时仍保持未选中
- **WHEN** 用户主动勾选 T 并保存
- **THEN** T 加入该 Agent 工具白名单，重新打开页面仍为选中，并按既有配置下一轮生效契约可用
- **WHEN** 用户取消 T 并保存
- **THEN** T 仍是候选但不在保存的白名单，后续会话按既有执行层权限契约拒绝未授权调用

#### Scenario: 工作区候选不跨 Agent 混入
- **GIVEN** Agent A 与 B 使用不同工作区，各有各自的用户工具
- **WHEN** 用户分别编辑 A 与 B，或打开其节点的新建页
- **THEN** 各编辑页只包含共享目录及自身工作区工具；节点新建页不借用 A/B 的工作区目录
- **AND** 同名工具只显示一次，其描述与该 Agent 的实际工作区覆盖一致

#### Scenario: agent 能力透传 features 五元字段
- **WHEN** 前端 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 200 含 `features` 列表,每项携 `{key, label_i18n, help_i18n, default_on, available}`（可含 `requires_tool`）,由网关 FEATURE_REGISTRY 投影原样转发

#### Scenario: 可选模型列表每项携带其注册的 provider
- **WHEN** 前端 `GET /im/v1/nodes/{id}/capabilities` 或 `GET /im/v1/agents/{id}/capabilities`
- **THEN** 返回的 `models` 列表中每项带有它注册的 provider（例：`codex_oauth:gpt-5.5` → `openai_compat`，`kimiCoding:K2.6` → `anthropic`）,供 agent 配置页模型下拉展示格式

#### Scenario: 用户按有效模型能力选择推理设置
- **GIVEN** 创建或编辑页已取得在线节点能力
- **WHEN** 用户选择一个可调推理模型，或当前继承的 platform default 是可调推理模型
- **THEN** 页面只提供该 model descriptor 声明的 levels，新建或用户主动切换模型时可初始选择其 default；读取已有配置时保留已存强度及继承语义，不因刷新自动补值
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
- **AND** 同一 Agent 的同名 Skill 只返回有序 roots 中最先命中的版本；多 Agent 聊天的 SlashPicker 使用会话成员 commands 投影的 opaque `skill_key` 区分不同节点／位置的同名 Skill，保留独立说明与来源 Agent；上述管理能力接口仍保留 `location`／`source_group`，成员候选不暴露本机路径

#### Scenario: 旧节点未提供来源分组时安全降级
- **GIVEN** 在线 Gateway 返回的旧 capability payload 不含 `source_group`
- **WHEN** 前端打开 Agent 配置页
- **THEN** Skill 候选仍可显示和逐项选择
- **AND** 页面不因缺少该可选字段崩溃或误报能力请求失败

#### Scenario: 技能禁用名单显示为灰色
- **GIVEN** Agent 配置使用 `explicit_denylist`，其中名称表示禁用的 Skill
- **WHEN** 用户打开配置页、保存后重新打开或刷新
- **THEN** 禁用名单中的候选 Skill 显示为灰色未选中，名单外显示为绿色选中，分组计数表示启用数量
- **AND** 编辑并保存后仍持久化禁用名称，保留暂时不可见的禁用名称。

#### Scenario: 无实时能力不误判已保存配置
- **GIVEN** 节点失联或本次能力读取失败
- **WHEN** 用户查看已保存的模型、推理强度、Features、工具和 Skills
- **THEN** 页面保留显式配置和最近确认的名称、来源与派生状态；未取得的信息明确未知
- **AND** 不因缺少目录显示强度不受支持、移除配置项或填入默认值，历史展示信息不能用于开启编辑

#### Scenario: 连续读取与故障后恢复
- **WHEN** 同一 Agent 的设置被连续或并发读取
- **THEN** 已确认且仍有效的候选可复用；失效时并发读取合并为一次有界刷新，普通读不占有配置写锁
- **WHEN** 构建超时或失败
- **THEN** settings 按既有 last-known/只读语义返回，后续重试可以重新构建；一次失败不能要求重启聊天运行时
- **AND** 权限、配置、绑定或连接变化后的迟到结果不能解锁页面或覆盖新状态
