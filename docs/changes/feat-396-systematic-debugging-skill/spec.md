# feat-396: 引入 systematic-debugging 技法 skill 到 change 工作流

## Relations

- Related: feat-341

## 原始需求

> 我没有单独skill做 systematic-debugging，这个是干嘛的

> 按照我的skill体系，我想纳入这条skill，然后在其他skill中合理的地方写入，调用这个skill。你觉得可行不，如果可行应该放在哪些地方

> 我思考了下，除了systematic-debugging，其他的都暂时不用引入。你先把两边skills的对比写一个文档，放到新unit目录下。然后开始做spec

> systematic-debugging也不用改成change-debugging，保留原名就行

补充上下文:
- 调研来源 superpowers（obra/superpowers），对比文档见同目录 `superpowers-comparison.md`。
- 已决定：只引入 `systematic-debugging`，保留原名（不改 change-debugging）；`receiving-code-review`、增量代码审查暂不引入。

## 澄清记录

- Q1: 本 unit 范围是只创建 skill 文件,还是 skill + call-in 一起?含 call-in 的话本期接入哪几处?
  A(原话): 一起
  Agent 解读: 确认推荐——skill + call-in 一起;本期接入 change-impl-worker / change-orchestrator / change-spec-author 三处,并在 change-reviewer 显式声明「不接入」。

- Q2: 本 unit 只产出 skill markdown,验收标准写到什么程度?静态(文档存在 + 自洽)还是要动态演示撞 bug 场景?
  A(原话): ok
  Agent 解读: 确认推荐——验收以「文档存在性 + 自洽性」为主(skill 可 invoke、3 处 call-in 就位且引用一致、reviewer 不接入声明、call-in 与 skill 内容不打架),不强求动态演示。本 unit 接近「零用户面」,真正核对落在 design/verifier 层。

- Q3: 接入 call-in 时允许改动现有角色文本吗,还是严格纯增量?
  A(原话): 可以改现有的，可能有重复的。但是不要改和这个无关的内容
  Agent 解读: 不限于纯增量——允许修改/合并现有「调试相关」的重复内容(如 worker §7 调试段、spec bugfix RCA 与新 skill 重叠处),把散落的调试精神收敛到新 skill。但边界严格:只动与「根因优先/调试」相关的内容,不碰无关规则。

- Q4: skill 内容从 superpowers 搬多少?要不要按你现有 skill 的语气/写法重写?
  A(原话): 要变成中文。其他的，你来考虑，原则就是效果优先，不用符合我现在的skill的写法，完全不需要。
  Agent 解读: skill 内容用中文。形式/结构/取舍由我定,唯一原则是「效果优先」——明确不要求符合现有 change-* skill 的写法规范(可贴近原始最有效的形式,不必套 §0 硬规则、机制性表达等既有风格)。据此取全量:4 阶段根因纪律 + Red Flags + 3 子技法(root-cause-tracing / defense-in-depth / condition-based-waiting),裁掉与三提交重叠的提交流程。

## 用户场景

> 本 unit 的「用户」= 跑 change-* 工作流的人 / agent。这是个对开发方法论本身的新增能力(feat),用憧憬式镜头写。

今天,change-* 工作流里的某个角色在干活时撞上一个 bug —— worker 实施 milestone 时某个测试突然挂了、或修一个 bugfix unit 时要定位用户报的崩溃、或重构后老测试红了查不出原因。**注意:这和「当前 unit 是不是 bugfix」无关** —— 它是「干任何活时半路冒出来的故障」,做 feat、refactor 时一样会撞上。

撞上之后,agent 手里**没有一套专门的调试纪律**。现状是:调试的精神散落在 worker §7(测试失败/连续失败回退)和 spec-author 的 bugfix RCA 段里,东一块西一块,没有一份「撞到故障后、动手修之前该怎么查」的强制顺序手法。结果就是 agent 容易退化成「猜一个改一下试试 → 不行再猜一个」的 thrashing:越改越乱、还引入新 bug、症状盖住了根因。

本变更后,工作流里多了一条 `systematic-debugging` 技法 skill,把「根因优先」的调试纪律写成可被任意角色随时 invoke 的展开手法:**没找到根因之前不许动手修**;按「读完整报错 → 稳定复现 → 多组件系统先打边界日志定位是哪层断 → 反向追到坏值源头 → 写下单一假设最小验证 → 修根因不修症状」的顺序走;同类修复连续失败若干次就停手质疑架构、找人。配套三个子技法:反向追调用栈、找到根因后多层加校验、用条件轮询替代写死 timeout 治 flaky。

而且这条纪律在**真正会用到它的地方被接上**:worker 实施中撞 bug 时(主场)、orchestrator 给 reviewer 反馈打包 fix 判根因在哪层时、spec-author 写 bugfix RCA 做根因调查时,都被引导去走这套纪律。**唯独 reviewer 显式不接它** —— reviewer 只走产品旅程、报用户可观察现象,一旦让它调起调试纪律就会去翻源码/抓帧/加日志,滑进 engineer 模式让整轮验收作废,正是工作流要防的事。

于是下次任何角色撞到 bug,不再是凭手感乱试,而是有一份照着走就能稳定定位根因的手册;同时现有 worker §7 / spec RCA 里那些和它重复的调试碎片被收敛过去,工作流里不再有两套打架的调试说法。

## 验收标准

> 本 unit 接近「零用户面」:产出只有 skill markdown,无产品 UI / 测试套件 / 产品旅程。下列 Scenario 的「可观察」= 在 skill 体系里 invoke / 阅读对应文件即可核验(对齐 Q2:验收以文档存在性 + 自洽性为主,不要求动态演示 agent 行为)。

### Requirement: systematic-debugging skill 可用且内容完整(中文)

#### Scenario: invoke 该 skill 得到完整调试纪律
- **WHEN** 在 skill 体系中 invoke `systematic-debugging`
- **THEN** 返回中文内容,包含「根因优先」铁律、4 阶段调查纪律、Red Flags 自查清单、以及「同类修复连续失败 → 质疑架构」的停手条件

#### Scenario: 三个子技法在位
- **WHEN** 阅读该 skill
- **THEN** 含三个子技法:反向追调用栈到坏值源头、找到根因后多层加校验、条件轮询替代写死 timeout 治 flaky

#### Scenario: 内容是中文、效果优先
- **WHEN** 阅读该 skill 全文
- **THEN** 正文为中文,无英文原文残留;不强制套用现有 change-* skill 的写法范式(形式以表达清楚、好照着走为准)

### Requirement: worker 实施中撞 bug 被引导走根因优先

#### Scenario: worker 读到调试指引
- **WHEN** worker 在 change-impl-worker skill 里读到「遇到 bug / 测试失败 / 意外行为」相关段落
- **THEN** 看到「动手修之前先 invoke `systematic-debugging` 找根因」的明确指引,且指引指向真实存在的 skill 名

#### Scenario: 不和三提交重复
- **WHEN** worker 按指引走完根因定位、进入修复
- **THEN** 修复仍回到现有三提交循环(C1 写复现测试),调试 skill 不另起一套提交流程与之打架

### Requirement: orchestrator 打包 fix 时引用根因纪律

#### Scenario: fix 路由引用调试纪律
- **WHEN** orchestrator 处理 reviewer/verifier 反馈、准备打包 fix
- **THEN** 对应段落引用 `systematic-debugging`,说明 reviewer 给的「最小路径 / 改第 X 行」是现象线索,要按根因纪律判根因在哪层

### Requirement: spec-author 写 bugfix RCA 时用调查纪律(仅调查)

#### Scenario: RCA 调用调查部分
- **WHEN** spec-author 写 bugfix 的根因分析(RCA)段
- **THEN** 含引用 `systematic-debugging` 调查部分的指引,且明确标注「只用调查阶段、不做修复」(spec-author 禁碰代码)

### Requirement: reviewer 显式不接入

#### Scenario: reviewer 含不接入声明
- **WHEN** 阅读 change-reviewer skill
- **THEN** 含显式声明「不 invoke `systematic-debugging`」,并给出理由(会推 reviewer 进 engineer 模式、让整轮验收作废)

### Requirement: 现有重复调试内容已收敛

#### Scenario: 无两套打架的调试说法
- **WHEN** 阅读改动后的 worker §7 调试段 / spec bugfix RCA 段
- **THEN** 与新 skill 重复的调试指引已合并或指向新 skill;两处涉及「连续失败该停手」的阈值表述不互相矛盾(有明确的层次/适用范围区分)

## 范围与非目标

- 在范围：
  - 新建 `systematic-debugging` 技法 skill(中文;效果优先,不受现有 change-* skill 写法约束):4 阶段根因纪律 + Red Flags + 「3 次质疑架构」停手条件 + 三个子技法
  - 三处 call-in:change-impl-worker(实施中撞 bug,主场)、change-orchestrator(fix 根因路由)、change-spec-author(bugfix RCA,仅调查阶段)
  - change-reviewer 显式「不接入」声明
  - 收敛现有「调试相关」的重复内容(可改 worker §7 调试段、spec RCA 与新 skill 重叠处,含「连续失败停手」阈值的去冲突)
- 非目标：
  - 不引入 `receiving-code-review`、不引入增量代码审查(本期明确推迟,见对比文档 §7)
  - 不改与「根因优先 / 调试」无关的现有规则文本
  - 不要求动态演示 agent 行为改变(prompt 变更无法 e2e 验证)
  - 不改名(保留 `systematic-debugging`,不叫 change-debugging)
  - skill 不被 orchestrator 当 milestone 派发、不建 worktree、不产文档契约(它是技法,非被派发角色)
