# feat-400: change-retro — 取证式 SDD 开发复盘 skill

> 回顾性 spec：本 unit 的实现(change-retro skill)与本 spec 在同一次对话里并行产出。
> 原始需求与澄清记录据实回填,验收标准是对已落地 skill 的用户可观察投影。

## Relations

- Related: change-spec-author / change-design-author / change-orchestrator / change-impl-worker /
  change-reviewer / change-verifier —— 既是本 skill 的**复盘对象**,也是它产出"改进清单"的**落点**。
- Refs: `docs/changes/feat-394-heartbeat-cron-redesign/retro-pipeline-rootcause.md` —— 本 skill 的
  方法论原型(那次 feat-394 灾难复盘的全过程被提炼成了这个 skill)。

## 原始需求

> 很好，整个分析比较全了。其实我们这次复盘的整个流程，以及中间的方法，能总结成一个skill，
> 后续我可以用这个skill来复盘feat开发

(背景:本次对话先对 feat-393/feat-394 做了一次完整的取证式复盘——读所有 change-* skill、抽取所有相关
session/subagent 的 jsonl、按时间线倒推每个问题的根因、产出按 skill 的改进清单。用户希望把这套**流程
和方法**固化成可复用 skill。)

## 澄清记录

- Q1: 这个复盘 skill 绑定到本仓的 change-* SDD 工作流,还是做成通用的 agent 开发复盘?
  A(原话): 绑定 change-* SDD（推荐）
  Agent 解读: skill 假定被复盘对象就是 change-spec/design/orchestrator/worker/reviewer/verifier 流程,
  懂 milestone 目录、acceptance.md/verification.md/design Changelog、worker/reviewer 派发等结构。

- Q2: 做到什么程度?要不要跑 skill-creator 的测试/benchmark 评估循环?
  A(原话): 先草稿+你审，跳过 benchmark（推荐）

- Q3(关于沿用 change-* 的格式): 你那个格式,基本上参考了我原本的 change-* 系列 skill?
  A(原话): 我觉得没必要这么搞，你按你思考觉得最佳的写法就行
  Agent 解读: 不为家族一致硬套 change-* 的 §0 硬规则/反 anti-pattern 模板,按最适合"取证手册"的写法组织。

- Q4(关于"诊断模式"清单): 里面你列的是这次遇到的问题，下次可能就不是这些问题了。或许可以作为范例？
  但是后面每次都检查这几个点，可能不太妥，要根据实际线索挖掘实际的那一次的问题
  A(原话): 同上(即用户原话本身就是这条澄清)
  Agent 解读: 这次的具体问题只能作**范例库**,不能固化成"每次必查的清单"。skill 的主干必须是"顺着这次
  的实际线索挖这次的实际问题",范例仅在线索指向时取用。

## 用户场景

开发者用 change-* SDD 流程跑完(或半途卡住)一个 feat/bugfix/refactor,感觉这次开发不顺——慢、反复、
做错、处处是问题。他想搞清楚**根因到底在哪一步**,以便改进那几个 change-* skill。

他对 change-retro 说"复盘 feat-X"(或"feat-X 为什么做这么久")。skill 接手后:先读 change-* skills 建立
"本该怎样"的标尺,定位这个 unit 涉及的所有 session/subagent jsonl 和沉淀文档;先产出一张**时间线 +
jsonl 索引**(阶段→时间→session/subagent,后续随时能下钻);然后从他**每一条反馈**出发、外加从日志挖出
的"没人干扰也自主空转"的隐蔽问题,**逐个倒推到真正引入问题的那个节点**——精确到哪个 skill 的哪条流程
缺口、哪个 agent 在哪一刻做了什么。每个结论都贴一手证据(jsonl 引文 / commit / 数字),不是泛泛感想,
也不采信当事人自己写的复盘。最后产出一份按 change-* skill 归口的改进清单,每条标来源。

复盘过程是**协作**的:他逐个问题和 skill 过;当他推翻某个结论时,skill 回去重挖 jsonl 核实,证据支持
他就改并**显式撤回**旧结论,不支持就摆证据——不嘴硬也不盲目附和。它**不会**机械地每次都过同一套
检查点,而是按这一次的实际线索挖这一次的实际问题。

对比之前:没有这个 skill 时,复盘要么靠记忆和当事人自述(不可信、停在表层),要么每次从零手写 jsonl
提取脚本(重复劳动)。

## 验收标准

### Requirement: 触发即产出取证式复盘

#### Scenario: 用户要求复盘一个 unit
- **WHEN** 用户说"复盘 feat-X / 这次开发哪里出了问题 / feat-X 为什么拖这么久"
- **THEN** change-retro 启动,并最终在 `docs/changes/<unit_dir>/` 下产出一份复盘文档

#### Scenario: 不误触发到正向开发
- **WHEN** 用户说的是"做个新功能 / 修个 bug / 把 feat-X 做完"
- **THEN** 不触发 change-retro(应走 change-spec/orchestrator)

### Requirement: 产出基于一手证据,不是感想,不采信二手

#### Scenario: 每个根因都带可核验证据
- **WHEN** 用户读复盘文档里任一根因结论
- **THEN** 该结论旁有具体一手证据(jsonl 引文 / commit hash / 量化数字 / 文档原文),能自行复核
- **AND** 不出现"沟通不顺/测试不足"这类无证据空话

#### Scenario: 当事人自述与证据冲突时以证据为准
- **GIVEN** unit 目录已有当事人写的 retro.md(或 worker/reviewer 报告)
- **WHEN** change-retro 复盘
- **THEN** 它不照搬当事人结论,而是拿 jsonl/代码核;发现当事人误判时在文中指出并给证据

### Requirement: 每条问题倒推到引入问题的节点 + 失效的 skill 阶段

#### Scenario: 症状映射到根因节点
- **WHEN** 用户看某条反馈(症状)对应的分析
- **THEN** 文档给出"真正引入问题的节点"(哪个 skill 的哪条 / 哪个 agent 哪一刻),而非停在症状复述

### Requirement: 文档含时间线 + jsonl 索引,可复用定位

#### Scenario: 开头有阶段索引
- **WHEN** 用户打开复盘文档
- **THEN** 开头有"阶段(spec/design/各 milestone/各验收轮)→时间区间→session/subagent"的索引,
  并附按角色反查 transcript 的方式

### Requirement: 能挖出用户没反馈、纯自主的异常(如长时间空转)

#### Scenario: 量化自主空转
- **WHEN** 这次开发存在"没人干扰时也连续空转很久"的情况
- **THEN** 复盘能从日志量化出这些时段并列为问题(不只覆盖用户主动反馈过的)

### Requirement: 产出按 change-* skill 的改进清单

#### Scenario: 改进清单可执行且可追溯
- **WHEN** 复盘收尾
- **THEN** 产出对每个相关 change-* skill 该改哪几条的清单,每条标注来源问题编号

### Requirement: 按实际线索挖,不机械过固定清单

#### Scenario: 不把上次的问题当这次的必查项
- **WHEN** 复盘一个新 unit
- **THEN** 挖掘按这一次的实际线索展开,而非逐条套用上次(如 feat-394)遇到的那组具体问题

## 范围与非目标

- **非目标:不做正向开发**——只回看已发生的开发,不写需求/方案/代码。
- **非目标:不改被复盘的代码,也不自动改 change-* skill**——只产出改进清单,改不改由人定。
- **非目标:不跑 benchmark/eval 循环**(澄清 Q2)——产出是分析文档,主观产物,靠人审。
- **非目标:不绑定到非 change-* 的开发流程**(澄清 Q1)——只服务本仓 SDD 流程。
- **范围内但靠 agent 自取**:被复盘 unit 的 id/PR、session 路径等由 skill 运行时定位,不在本 spec 固化。
