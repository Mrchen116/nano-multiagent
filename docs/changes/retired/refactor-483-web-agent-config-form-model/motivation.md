# refactor-483: 统一 Web Agent 配置表单模型

> 状态：v3（2026-07-25）

## Relations

- Depends on: 无
- Blocks: 无
- Related: refactor-482

## 原始诉求

> 再看看当前代码仓中有多少巨石代码
>
> 我希望你能明确当前所有的重要的架构问题，如果和CC有类似的概念则和CC的源码的架构做对比，然后用change-spec-author，change-design-author skill（不需要跟我逐个进行对齐），帮我创建独立的几个unit。我要逐个进行重构，完善架构。我最终做一次确认后，再开始按可并行性开始做各个unit的实现。
>
> 中途你全程负责。我只做最终的确认。

## 澄清记录

- Q1: 是否逐页对齐？
  A: “中途你全程负责。我只做最终的确认。”
- Q2: `agent-detail-page.tsx` 很大是否自动意味着要拆？
  A: 否；该页已有内部子组件。建 unit 的依据是 create/detail 两条路径重复 normalization、validation、effective feature 与 feature→tool 约束，存在配置语义漂移风险。

## 现状痛点

Agent 创建页与详情页分别实现 allowlist/text normalization、draft 到 API payload 转换、校验、feature capability 解析、feature 所需 tool 联动和 BehaviorCard 状态。默认模型、显式空 tool allowlist 与 feature 依赖工具是需要一致解释的业务规则，却没有单一表单模型所有者。

新增配置字段或修复一条路径时，另一条路径可能保留不同默认值或提交语义；超大的详情页测试必须重复证明相同规则。

代码核对还暴露出一条已经影响用户的配置契约漂移：创建页会提交 `features` 和自定义说明，但创建接口当前会丢弃它们；编辑接口也没有可靠地区分“本次未修改某块配置”和“用户明确清空该配置”。因此只在浏览器内抽取共享模型，会得到测试通过但持久化仍错误的假收敛。

## 目标状态

建立共享的 typed Agent configuration form model，统一：

- 服务端配置 ↔ draft ↔ submit payload 的投影，并让创建、保存、刷新后的持久值一致；
- normalization、validation 与 dirty state；
- capability/feature 可选项及 feature→required tool 不变量；
- missing feature override 与 explicit false、create auto-default 与 explicit empty selection 的
  provenance；
- create/edit 默认值、隐藏 passthrough 字段和显式空 allowlist 语义；
- 当前 capability snapshot 暂不认识的 feature、skill、tool 或 model 值在用户未删除时继续保留。

创建页和详情页各自保留 route、数据加载、保存反馈与现有视觉布局，只消费同一模型；不建立万能表单框架。

## 用户侧验收标准（不变性）

用户继续从 Agent 列表创建 Agent，并在详情页编辑身份、模型、tools、features、skills 等配置；保存、错误提示、Behavior 预览和响应式布局保持当前表现。此前创建时会被静默丢弃的自定义说明和 feature override 必须真正保存；只编辑一个字段时，其他配置不得被默认值覆盖。

### Requirement: 创建 Agent 保持

#### Scenario: 使用默认值或自定义配置创建
- **WHEN** 用户在创建页填写 Agent 并提交
- **THEN** 默认模型、字段校验、成功导航和失败反馈与变更前一致
- **AND** 用户填写的自定义说明、feature override、skills、tools 和 model 在创建成功后刷新仍保持

### Requirement: 编辑 Agent 保持

#### Scenario: 加载、修改并保存现有 Agent
- **WHEN** 用户在详情页修改任一配置并保存
- **THEN** 初始值、dirty state、提交字段和保存反馈与变更前一致

#### Scenario: 只改一个字段不覆盖其他配置
- **GIVEN** Agent 已有自定义说明、feature override 和 heartbeat cadence
- **WHEN** 用户只修改显示名称并保存
- **THEN** 重新加载后这些未修改配置保持原值

#### Scenario: capability 暂时缺项时保留已有选择
- **GIVEN** Agent 已保存的 feature、skill、tool 或 model 值暂未出现在当前 capability snapshot
- **WHEN** 用户修改其他字段并保存
- **THEN** 页面把缺项显示为已有但当前不可选的值，保存和刷新不会静默删除它

### Requirement: Capability 约束保持

#### Scenario: 选择需要工具的 feature
- **WHEN** 用户启用一个声明 `requires_tool` 的 feature，或显式选择空 tool allowlist
- **THEN** 可选项、联动、校验和最终持久化语义与变更前一致

#### Scenario: capability 刷新不破坏 feature 所需工具
- **GIVEN** 创建页已按默认 capability 初始化工具
- **WHEN** 用户启用一个需要工具的 feature，随后同一节点 capability 刷新
- **THEN** 该 feature 仍启用，其 required tool 仍在显式 allowlist 中

### Requirement: 当前 UI 保持

#### Scenario: 桌面与移动配置页
- **WHEN** 用户在现有桌面或移动入口创建、查看或编辑 Agent
- **THEN** 页面结构、字段分组、BehaviorCard 和操作反馈与变更前一致

## 影响范围

- Agent create/detail 页面
- 新共享 form model 与 capability projection
- IM 的 Agent 创建与局部更新持久化语义
- 页面组件及测试
- Gateway config/capability schema 不变
- 不重做视觉设计，不改变 heartbeat、cron、channel 或 session 的产品语义

## 迁移与回滚策略

先以真实创建/更新接口测试锁定字段 presence、创建持久化与未知值保留，再用共享模型测试锁定
capability missing/default/explicit 三态、显式空 allowlist、feature/tool 联动、hidden passthrough、
semantic dirty 和错误映射。随后在同一 M1 让两页切到单一模型/Behavior view，最后删除重复 helper
与 API DTO-as-draft 路径。以当前 create/detail 的桌面和移动原型、真实浏览器截图保真；不长期保留
两套 normalization 或旧请求投影。失败时整体回滚；没有数据库结构迁移。
