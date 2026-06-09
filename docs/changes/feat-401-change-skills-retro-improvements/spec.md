# feat-401: change-* skills 按 feat-394 复盘改进

> 回顾性 spec:本 unit 的实现(改 6 个 change-* skill)与本 spec 在同一次对话里并行产出。
> "用户"= 用 change-* SDD 流程开发的人;"用户可观察"= 跑 SDD 流程时各阶段的行为变化。

## Relations

- Depends on: feat-400(change-retro skill)—— 本 unit 的改进项全部来自用 change-retro 方法对 feat-394 做的复盘。
- Related: change-spec-author / change-design-author / change-orchestrator / change-impl-worker /
  change-reviewer / change-verifier —— 被改进的对象。
- Refs: `docs/changes/feat-394-heartbeat-cron-redesign/retro-pipeline-rootcause.md`(P0–P8 根因 + 按 skill 改进清单,本 unit 据此实施)。

## 原始需求

> 一个个skill来，认真分析当前skill和要克服的问题，再改进去。改一个给我看完再改下一个
>
>（前序:用户先用 change-retro 对 feat-393/394 做了取证复盘,在
> `retro-pipeline-rootcause.md` 末尾产出"按 skill 的改进清单";本 unit 即逐个 skill 落实该清单。）

## 澄清记录

逐 skill 改进过程中、用户给的关键约束(原话):

- **不要人工介入**(贯穿 orchestrator 改动):
  A(原话): "我不希望在明确设计还需要人介入实现"——orchestrator 的自主闭环(磨到 pass / 撞轮次 cap)不是问题,改进只让 autonomous 闭环跑得更对,不引入"早点叫人"。
- **写法**:
  A(原话): "这是基于原本的skill的认知，新的agent用新的skill，不存在旧的认知，直接告诉他新的认知是啥就行" —— 正面陈述新规则,不 negate 已删的旧措辞。
  A(原话): "不要用'你本能xxx'这个句式，你应该说，'你要xxx，注意不要xxx'" —— 用祈使,不揣摩 agent 倾向。
- **不要过拟合本需求**:
  A(原话): "过窄了，这是完全针对了本需求…核心是agent 默认优化的是'尽快把功能写出来/让测试过'，不是'维护现有架构的一致性'" —— 改进对准通用根因,不写死成 feat-394 那个具体机制。
- **env 处置**:
  A(原话): "更合理的应该是worker发现有环境问题，自己摸不准，问orchestrator，orchestrator再靠他的全局视野去解决" —— env 反应式 + worker 发起,不是 orchestrator 每次派活预先保障。
- **reviewer 副作用 vs out-of-unit**:
  A(原话): "review的目的…还要保证整个产品的角度不产生副作用，影响到其他能力…我不确定和现有的out-of-unit机制是否有冲突" —— 采纳"suspected-regression"层:本 unit 顺带打坏别的能力默认 in-unit,reviewer 不证因果(留给 fix worker),无关旧 bug 才 out-of-unit。

## 用户场景

开发者用 change-* SDD 跑需求时,流程在六个点上的行为相比改进前不同——这些点正是 feat-394 复盘出的根因:

1. **spec 阶段**:作者不再把"读代码"整个当禁区躲开,也不再拿坏现状当产品真值——开问前(及澄清中撞到不明确时)会从产品特性高度读当前系统的对应功能 + **用户点名的参考产品**,把"这是什么特性、是一个机制还是两个"搞清,再立验收标准。
2. **design 阶段**:作者会找"同类的事项目已有什么模式"、默认扩展而非另造平行物;用户中途加需求时,新增部分重走现状调研,不直接打补丁撞穿既有约束。
3. **实施阶段(orchestrator)**:live-critical 工作必须真端到端跑到用户可见结果才被签收;worker 没给 live 证据时,orchestrator 自修 env 或打回,而不是签收后把 live 验证甩给下一轮 reviewer。全程不拉人介入。
4. **实施阶段(worker)**:design 没写、自己填的实现细节默认复用现有架构;live 跑不通时报 BLOCKED 求助 + 如实披露 env 受阻,不降级用单测凑 DONE;一个没修完的问题复用同一 fix worker。
5. **验收阶段(reviewer)**:走旅程时不只逐条对 Scenario 答案,还会发现"答案对了、旁边塌了"的副作用;本 unit 顺带打坏其他能力的,按 in-unit 回归处理,而非以"不属本 unit 域"放走。
6. **验证阶段(verifier)**:除了核"实现 vs design",还独立核"实现 + design 是否和代码仓既有架构自洽"(依赖方向 / 跨机 / 复用 vs 平行),违反判 CRITICAL(阻塞);并会指出测试堆积。

对比改进前:feat-393 整单建在错前提上(spec 没识别两个机制);feat-394 实施陷数十小时往返轮(假绿假 DONE 甩 reviewer 轮)、自造平行机制、跨机违规被标 WARNING 放行——这些根因逐一被上面六点堵住。

## 验收标准

> 这些是对 skill 文本的可核对断言(skill 是 prompt,"用户可观察"= 跑流程时的行为约束已写进 skill)。

### Requirement: spec 阶段做产品特性 grounding

#### Scenario: 读代码的边界按目的划
- **WHEN** 看 change-spec-author 的实现层边界规则
- **THEN** 它按"读来干嘛"划界(理解产品特性 → 该读多深读多深;定实现方案 → 留 design),而非"禁止碰代码"

#### Scenario: grounding 是流程显式步骤且贯穿澄清
- **WHEN** 看其澄清流程
- **THEN** 有一个澄清前必做、且澄清中可随时补的"产品特性 grounding"步骤(读现状对应功能 + 读用户点名的参考),并进入完成门禁

### Requirement: design 阶段默认复用既有架构、晚加需求重走 grounding

#### Scenario: 调研既有模式
- **WHEN** 看 change-design-author 的现状调研清单
- **THEN** 有"该沿用的既有模式"一项(同类的事项目按什么模式做、默认扩展)

#### Scenario: 中途加需求
- **WHEN** 用户在 design 阶段后追加 / 修订需求
- **THEN** skill 要求新增部分重走现状调研 + 自检,不直接打补丁

### Requirement: live 验证前置到 worker 签收,不甩 reviewer 轮(全自主)

#### Scenario: live-critical 工作的签收
- **WHEN** worker 对 live-critical 工作报 DONE 但只有单测 / stub 证据
- **THEN** orchestrator 不签收;自修 env 或打回 worker 真跑到可见结果,而非签收后开新一轮 reviewer
- **AND** 全程不引入人工介入

### Requirement: worker 默认复用现有架构 + 撞 env 报 BLOCKED 不降级

#### Scenario: design 未规定的实现细节
- **WHEN** worker 实现 design 没写明的细节
- **THEN** 默认沿用项目同类的事已有的做法,不另造局部平行实现

#### Scenario: live 环境跑不通
- **WHEN** worker 跑 live 验证时环境起不来 / 不通
- **THEN** 报 BLOCKED 求助 + 在回报里如实披露 env 受阻,不降级用单测 / 集成顶替报 DONE

### Requirement: reviewer 抓本次顺带打坏的副作用

#### Scenario: 同屏副作用
- **WHEN** reviewer 走某 Scenario,该 Scenario 本身通过,但同屏 / 相邻功能明显坏了
- **THEN** 记为问题,按 suspected-regression 默认 in-unit 处理(不因"属别的能力域"就 out-of-unit 放走)

### Requirement: verifier 抓架构自洽违反 + 测试堆积

#### Scenario: 架构边界违反
- **WHEN** 实现(或 design 本身要求的)破坏依赖方向 / 跨机边界 / 另造平行机制
- **THEN** verifier 标 CRITICAL(阻塞提 PR),并指出根因是否在 design

#### Scenario: 测试过剩
- **WHEN** 存在一次性迁移红测 / 死代码存在性断言 / 跨层重复断言
- **THEN** verifier 标 SUGGESTION 并建议按 TESTING_GUIDE 剪

## 范围与非目标

- **非目标:不引入人工介入**——所有改进都让 autonomous 闭环跑得更对,不增加"叫人 / 早停求助"。
- **非目标:不重写 skill 结构**——在既有章节内最小改动、复用既有规则,只补缺口(如 §6.FL 不新开 §6.2.1)。
- **非目标:不过拟合 feat-394**——对准通用根因(架构一致性、live 验证、复用),不写死成那个具体机制。
- **非目标:不改 change-retro 本身**(那是 feat-400)、不改非 change-* 的 skill。
