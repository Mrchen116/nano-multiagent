# Gateway agent-capabilities delta for refactor-593

## ADDED Requirements

### Requirement: Workspace 和全局 Skill 使用禁用名单

Agent 使用 `skills_selection_mode=explicit_denylist`，`skills` 保存禁用名称。配置界面仍以勾选表示启用；保存的是取消项，暂时缺失的禁用名称保留。工具白名单不受影响。

#### Scenario: 新建或复制导入的技能默认可用
- **WHEN** 在 Agent 可发现的 Workspace 或共享全局 roots 新增有效 Skill
- **THEN** 后续模型步骤可发现并按名加载，无需修改启用名单或重启；共享全局新增技能对可访问该目录的 Agent 默认可用
- **AND** 其他 Workspace 的私有 Skill 不泄漏；同名覆盖仍按已有 roots 优先级

#### Scenario: 明确禁用在所有消费者一致生效
- **WHEN** 用户取消勾选某 Skill 并保存
- **THEN** 后续回复的目录、按名加载、显式命令、preview、distillation readiness 和 SlashPicker 一致排除该名称
- **AND** 重启、重新扫描或同名技能重新创建不会自动启用；旧回复沿配置安全边界收口

#### Scenario: 旧配置升级保留已有选择
- **WHEN** 节点连接 IM 后迁移旧 default-discovery 或 explicit-allowlist 配置
- **THEN** default 转为空禁用名单；allowlist 以该 Agent 迁移时的完整候选集合减去旧已选名称形成禁用名单，包括旧显式空名单
- **AND** 经已有版本化配置操作同时提交 Node YAML、runtime 与 IM profile；离线不猜候选，已经迁移的配置不重复转换
- **AND** 迁移后新增名称默认可用；旧配置没有记录候选历史，迁移只保证迁移当时已有候选的选择状态

#### Scenario: 创建事实不覆盖用户禁用
- **WHEN** 前台或后台成功创建 Skill 并产生知识更新事实
- **THEN** 继续记录真实来源与通知，但不追加任何 Agent 的启用配置；是否可用由发现及禁用名单共同决定

#### Scenario: 禁用蒸馏技能时明确不可用
- **GIVEN** Agent 禁用了会话蒸馏 Skill，或离线旧模式的显式 allowlist 不包含它
- **WHEN** 用户请求生成或蒸馏 Skill
- **THEN** 返回明确的 distiller unavailable 结果，不因文件存在而放行

#### Scenario: 离线历史配置保持原模式
- **GIVEN** 节点尚未完成认证迁移
- **WHEN** 节点离线工作或旧模式会话继续执行
- **THEN** 历史 default discovery 保持发现行为，显式 allowlist 包括空名单仍按原选择限制；不凭缺失候选推断禁用名单

## MODIFIED Requirements

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

Gateway 对 self-evolution review 成功产生的知识更新事实保持 session 级消费，不依赖已经结束的前台 run context。事件无论在前台 terminal 前后到达或经可恢复 stream 重连重放，都保留真实来源与通知，不为新技能修改禁用名单。

后台 Memory/Skill review fork 保留父会话历史，逐字节继承父请求已渲染的 system prompt 和完整工具定义，维护指令追加在继承历史之后；不因后台工具白名单重建请求前缀。白名单在工具执行前独立拦截，工具可见不代表获准执行。这样保留上游前缀缓存的复用条件；实际命中仍以 provider usage 为准，不承诺每次命中。

Memory 注入在首次请求惰性读取，当前会话内保持快照，原生 fork 继承快照，压缩完成后再读取最新内容；禁用 memory_curation 时不读取。后台反思分别按主会话轮次和模型迭代累计，单轮并行工具不放大计数；前台对应维护工具的成功结果重置提醒读数，失败不重置。后台 review 仅完成后推进重置点，失败或取消不消耗提醒周期。

#### Scenario: fast review 与 slow review 使用同一调和结果

- **GIVEN** Agent 的 self-evolution review 成功创建 agent-scope 或 global-scope Skill
- **WHEN** 创建事件发生在前台回答 terminal 之前或之后
- **THEN** 新 Skill 由原生发现变为可用，前后台通知按真实结果投递
- **AND** 已存在的同名禁用选择保持，不因创建事实被覆盖

#### Scenario: 后续前台轮次与 stream 重连不重复调和

- **GIVEN** 同一 session 的持久后台事件消费已建立，随后又完成前台轮次或发生可恢复 stream 重连
- **WHEN** self-evolution 创建事件被实时接收或重放
- **THEN** 同一创建结果不会被前台与后台两条路径重复处理
- **AND** 未禁用的新 Skill 在相关 Agent 的后续 session 中保持可用

### Requirement: 自进化技能自动启用不打断既有会话提示词

#### Scenario: 后台新增技能保持当前上下文缓存前缀
- **GIVEN** Agent 的后台自进化成功创建技能
- **WHEN** Gateway 保存该技能且原生发现刷新，既有会话开始下一轮
- **THEN** 技能可由工具读取，但不因该自动增量重建提示词目录或生成配置分界线
- **AND** 新会话及压缩等既有重建边界可吸收新目录；该保护以当前进程内会话快照为界，重启不保留旧快照

#### Scenario: 手动取消及重新启用技能仍立即生效
- **GIVEN** 技能由后台自动新增并启用
- **WHEN** 用户手动取消，或取消后重新启用该技能
- **THEN** 下一轮按显式配置更新目录并保留既有配置分界行为

## REMOVED Requirements

### Requirement: PA Agent 配置区分默认发现与显式空 Skill 选择
