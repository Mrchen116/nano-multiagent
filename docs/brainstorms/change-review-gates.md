# Brainstorm: Change 类型与 Review Gate

> 草稿。这里记录的是工作流设计想法,不是已经定稿的规范。

## 背景问题

当前 `change-*` 工作流容易把所有 full change 都推向同一种验收模式:实现完后派 reviewer 做"产品侧验收"。这对用户可见功能很自然,例如 IM 前端重写、CLI 交互改造、bugfix 回归。但对下面几类 change 会变形:

- 平台/内核能力:例如 session context storage 从 SQLite 改成 JSONL + in-memory history。普通用户不一定能直接感知 JSONL,但 CLI/API 使用者、开发者、运维者有可观察契约。
- 纯内部重构:目标是结构变好、行为不变。强行做产品验收会让 reviewer 硬编用户旅程。
- 性能/可靠性优化:用户可能只感知"没变慢/没丢",核心证据却是 benchmark、负载、资源占用、错误率。
- 安全/隔离/权限:有用户侧结果,但还需要边界、威胁模型、数据泄露检查。

传统人类开发流程里,"验收"不是一个固定角色,而是一组按 change 风险选择的 verification gates。Product acceptance 只是其中一个 gate。

## 讨论原话

这些原话保留为设计动机,后续改 skill 时应优先满足这些约束。

> 我用330举例子是想说，对于这种软件内部的改动，好像产品侧不需要验收，最多说验收是否各个用户场景生成或者追加了正确的jsonl，还勉强可以说得过去。有的需求是完全是重构代码相关的，完全没有用户侧变化。

含义:不是所有 change 都有 product acceptance。内部平台能力和纯重构需要不同的 verification gate。

> 所以我们参考传统的人类的开发流程，应该怎么设计，是否需要多个不同的类型的reviewer，根据需求而定，还是如何。我们需要思考的是这个问题

含义:问题核心不是 330 本身,而是工作流如何根据 change 类型选择 review/verification 方式。

> 我觉得要弄这么多skill很繁琐，其实可以合起来就是一个skill，然后在design阶段，明确当前需求需要哪些类型的review，具体review什么，然后在review阶段去读design的要求。这样是不是更加通用，而且skill没那么难维护

含义:倾向保留一个通用 reviewer skill,把 review 类型和证据要求前移到 design 的 Verification Plan。

> 这个改动没问题，重点是，改了之后我应该怎么验呢？应该拿我过去做过的一些需求来测试新的skill集合是否ok对吧

含义:skill set 本身也需要 regression/eval。历史 change 可以作为评测样本,验证新的 workflow 是否真的更稳。

## 基本判断

不要拆很多独立 reviewer skill。skill 数量多会增加维护成本,也容易让 orchestrator 选择错误角色。

更通用的做法是:

1. `change-design-author` 在 design 阶段写清本 change 需要哪些 verification gates。
2. `change-reviewer` 作为通用 verifier,按 design 的 Verification Plan 执行 `owner=reviewer` 的 gate。
3. 对 `owner=worker` / `owner=CI` / `owner=human` 的 gate,reviewer 只检查证据是否存在和是否满足 plan 声明,不重新扮演工程 reviewer。
4. `change-orchestrator` 不再无脑假设 reviewer 是产品验收员,而是读取 Verification Plan 后决定是否需要派 reviewer。

一句话:

> Reviewer 不决定该验什么;design 决定。Reviewer 只执行 Verification Plan,并拒绝执行 plan 外的猜测性验收。

## Change 类型

这些类型不是互斥标签,一个 change 可以同时命中多个。

| 类型 | 典型例子 | 主要风险 | 常见 gate |
|---|---|---|---|
| User-facing feature | 新页面、新 CLI 命令、新交互 | 用户不能完成任务,体验偏离设计 | product_acceptance, visual_reference, regression |
| Developer/platform feature | HTTP API、CLI 契约、文件格式、事件流、session 存储 | 外部契约不稳定,下游无法使用 | technical_acceptance, contract_regression, engineering_verification |
| Internal refactor | 模块拆分、依赖方向调整、存储层替换但行为不变 | 行为回归,边界破坏,测试缺口 | regression, engineering_review, contract_tests |
| Bugfix | 修复已知线上/验收问题 | 复现未闭环,同类场景回归 | regression |
| Performance/scalability | 缓存、批处理、并发、I/O 优化 | 指标没改善或新瓶颈 | benchmark, load_smoke, resource_check |
| Security/privacy/safety | 鉴权、隔离、secret、权限 | 越权、泄露、注入、供应链 | security_review, abuse_case, boundary_tests |
| Documentation/process | runbook、skill、开发流程 | 下游按文档仍跑不通 | doc_acceptance, dry_run |

## Verification Plan 建议格式

design.md 里新增一个强制段:

```md
## Verification Plan

| Gate | Type | Owner | Scope | Method | Pass Criteria | Evidence |
|---|---|---|---|---|---|---|
| V1 | product_acceptance | reviewer | 用户能完成主路径 | 真实浏览器/CLI 走旅程 | 所有必需步骤通过,无 blocking/major | 截图/录屏/终端 transcript |
| V2 | technical_acceptance | reviewer | 外部 API/CLI/文件契约可用 | 真实入口 + 只读检查 | 契约输出符合 spec | 命令输出/JSON/文件片段 |
| V3 | engineering_verification | worker/CI | 内部算法和边界正确 | 单测/集成/contract | 指定测试通过 | pytest/CI 链接 |
| V4 | regression | reviewer | 已知 bug 不复现 | 原复现步骤重跑 | 现象消失,相邻路径不坏 | 复现前后记录 |
```

字段含义:

- `Gate`: 稳定 ID,方便 reviewer 报告引用。
- `Type`: gate 类型,不是 skill 名。
- `Owner`: 谁负责给出最终证据。常见值: `reviewer`, `worker`, `CI`, `human`。
- `Scope`: 验什么,必须是可判定的边界。
- `Method`: 怎么验,尽量写真实入口或明确的测试命令。
- `Pass Criteria`: 通过标准,避免 reviewer 自己猜阈值。
- `Evidence`: 需要留下什么证据,以及证据应落在哪里。

## Reviewer 行为

通用 reviewer 的职责:

- 读取首文档和 design.md 的 Verification Plan。
- 只执行 `owner=reviewer` 的 gate。
- 对 `owner=worker/CI/human` 的 gate 做 evidence check:证据是否存在、是否对应 gate、是否足以支持 pass criteria。
- 报告里按 gate 输出结果:`pass / fail / inconclusive / not-applicable`。
- 发现 plan 缺失或 gate 不可执行时,不要自己补口径,标 `inconclusive` 或要求回 design 阶段修 plan。

通用 reviewer 不应该:

- 把所有 change 都翻译成产品验收。
- 把内部实现约束伪装成用户旅程。
- 为了验证工程 gate 去读源码定位根因或临时改代码。
- 用历史轮次的判断替代当前 gate 要求的证据,除非 Verification Plan 明确允许继承,并说明继承条件。

## 330 这类平台能力怎么验

`feat-330-session-context-storage` 不是普通用户侧功能,更像 developer/platform feature + internal architecture change。

合理 gate:

| Gate | Type | Owner | Scope | Method | Pass Criteria | Evidence |
|---|---|---|---|---|---|---|
| V1 | technical_acceptance | reviewer | 多轮会话历史对用户仍连续 | CLI/API 创建 session,发送两轮,第二轮引用第一轮信息 | assistant 能用到前文 | 终端 transcript 或 API 输出 |
| V2 | technical_acceptance | reviewer | 重启后 resume 不丢历史 | 创建 session -> 发送消息 -> 重启服务 -> resume -> 继续问 | 历史仍可用 | 终端 transcript |
| V3 | technical_acceptance | reviewer | JSONL transcript 作为开发者可见产物存在 | 完成真实 session 后只读 `.nano/sessions/*.jsonl` | 文件存在,每行可解析,含 session_created/turn | 命令输出 |
| V4 | engineering_verification | worker/CI | warm turn 不再读 SQLite/JSONL | targeted unit/integration test 或 instrumentation test | 测试通过 | pytest 输出 |
| V5 | engineering_verification | worker/CI | compact/fork/load 算法正确 | 单测 + 集成测试 | 覆盖 DAG/compact/config_update | pytest 输出 |
| V6 | regression | reviewer | 既有 CLI/API session 流程不回归 | 跑 documented CLI/API happy path | 原入口仍可用 | transcript |

这里 reviewer 不需要证明"内部一定零磁盘读",因为这不是用户/外部 actor 可直接观察的结果。它只需要确认 worker/CI 对该 engineering gate 留了有效证据。

## 纯重构怎么验

纯 refactor 可以没有 `owner=reviewer` 的 product gate。

合理 gate:

| Gate | Type | Owner | Scope | Method | Pass Criteria | Evidence |
|---|---|---|---|---|---|---|
| V1 | regression | CI | 外部行为不变 | 相关单测/集成/contract | 全绿 | CI/pytest |
| V2 | engineering_review | human 或 reviewer-lite | 模块边界更清楚 | diff review checklist | 无反向依赖/无循环/无隐式耦合 | review notes |
| V3 | doc_acceptance | reviewer | 公开文档没有过期 | 读 README/SPEC 对照新结构 | 文档与行为不冲突 | report |

如果没有真实用户侧变化,orchestrator 应允许跳过产品验收,但不能跳过 regression evidence。

## Visual/reference 类 gate

涉及原型、设计稿、reference screenshot、像素级、响应式时,需要单独 gate,不要混在功能 gate 里。

关键要求:

- reference 和 actual evidence 都要落到 repo 内或可长期访问的位置,不能只放 `/tmp`。
- 最终 pass 前必须用当前实现重新跑 reference gate,不能只继承旧轮分级。
- pass criteria 要明确。例如 spec 写"像素级对齐",就不能把"近"默认当 pass;如果允许"近",design 必须先定义"近"的阈值。
- visual gate 和 functional gate 分开。功能修通不等于视觉通过。

## Orchestrator Gate

orchestrator 不判断质量,但要检查证据完整性:

- design.md 是否有 Verification Plan。
- worker DONE 时,`owner=worker/CI` 的 gate 是否有证据。
- reviewer DONE 时,报告是否覆盖所有 `owner=reviewer` gate。
- 若 reference gate 缺少 reference + actual 对照证据,不能接受 pass。
- 若 plan 没有任何 `owner=reviewer` gate,可以跳过 reviewer,但 PR 描述要列出 worker/CI evidence。

## 用历史 change 验证新 workflow

可以把历史 change 当 workflow regression suite:

| Change | 期望行为 |
|---|---|
| feat-340-agent-native-im | 必须有 product_acceptance + visual_reference + regression;最终 pass 前需要完整 reference evidence |
| feat-330-session-context-storage | technical_acceptance + engineering_verification;不应强行产品验收 |
| bugfix-331-repl-resume-dup-render | regression gate 复现闭环 |
| feat-334-tool-result-budget | technical/product 混合;用户输出可读性 + 内部预算策略测试 |
| 纯 refactor fixture | 可跳过 product reviewer;必须有 regression + engineering evidence |

反例测试:

- design 没写 Verification Plan:reviewer 拒绝验收。
- 纯 refactor 被写成 product_acceptance:reviewer 标 plan 不合理,不硬编用户故事。
- engineering gate 没有测试/CI evidence:reviewer fail evidence check。
- visual gate 只有组件测试或 DOM 存在:reviewer fail,因为缺真实 reference 对照。

## Skill Set 评测方案

改完 skill 后,不要只靠一次真实项目试跑判断是否奏效。需要把 workflow 本身当产品,做一组轻量 eval。

目标不是验证历史业务代码是否正确,而是验证 skill set 是否能稳定做出正确流程决策:

- 能不能识别 change 类型。
- 能不能在 design 阶段生成合适的 Verification Plan。
- 能不能把 product / technical / engineering / regression / visual gate 分清楚。
- 能不能在 reviewer 阶段只执行自己该执行的 gate。
- 能不能在缺证据时拒绝 pass。
- 能不能避免把内部工程约束伪装成用户验收。

### Eval 样本集

建议建立 `docs/brainstorms/change-workflow-evals/` 或后续正式目录,每个样本一份小夹具。第一批不用多,覆盖类型即可。

| 样本 | 来源 | 评测重点 |
|---|---|---|
| E1 user-facing UI | feat-340-agent-native-im | 是否生成 product_acceptance + visual_reference gate;最终 pass 是否要求 reference + actual evidence |
| E2 platform feature | feat-330-session-context-storage | 是否生成 technical_acceptance + engineering_verification;是否跳过普通产品验收 |
| E3 bugfix | bugfix-331 或 bugfix-339 | 是否抓住原始复现步骤和回归闭环 |
| E4 mixed technical/product | feat-334-tool-result-budget | 是否同时覆盖用户可见输出和内部预算策略测试 |
| E5 pure refactor | 可造一个小 fixture | 是否允许无 reviewer product gate,但强制 regression/evidence |
| E6 security/privacy | 可造一个权限隔离 fixture | 是否生成 boundary/security gate,不只跑 happy path |

每个 eval 样本可以只包含:

- `input/spec.md`: 需求首文档。
- `input/design-before.md`: 旧设计或空设计。
- `expected/verification-plan.md`: 人类期望的 gate 形状。
- `expected/reviewer-routing.md`: 哪些 gate 应由 reviewer 执行,哪些只查证据。
- `expected/failure-cases.md`: 应该拒绝 pass 的情况。

### Eval 运行方式

第一阶段可以是人工/半自动评测,不必一开始就自动化到很复杂。

1. 让 `change-design-author` 基于样本 spec 产出或刷新 design。
2. 对照 `expected/verification-plan.md`,人工给分。
3. 构造一份 worker progress / CI output / fake acceptance evidence。
4. 让 `change-reviewer` 读取 design 和证据,产出 verification report。
5. 对照 `expected/reviewer-routing.md` 和 `expected/failure-cases.md`,人工给分。
6. 汇总到一张 eval matrix,记录 skill 修改前后的变化。

后续可以自动化:

- 用固定 prompt 跑 design/reviewer。
- 用脚本检查报告是否包含所有 gate ID。
- 用规则检查是否出现禁止模式,例如"没有 reference evidence 却 pass visual gate"。
- 用 golden file diff 检查 Verification Plan 的 gate 类型和 owner 是否接近期望。

### 评分维度

每个样本按 0/1 或 0/2 给分即可,重点看趋势。

| 维度 | 通过标准 |
|---|---|
| Change classification | 类型判断合理,没有把纯内部重构硬说成产品功能 |
| Gate coverage | 关键风险都有 gate,没有漏掉核心用户/工程风险 |
| Owner routing | reviewer / worker / CI / human 分工正确 |
| Evidence specificity | 每个 gate 写清证据形态和落点 |
| Reviewer discipline | reviewer 不执行 plan 外任务,不读源码定位根因,不改代码 |
| Failure sensitivity | 缺 evidence、缺 reference、测试缺口时能 fail/inconclusive |
| Pass strictness | 必验项未闭合时不给 pass |
| Maintainability | plan 不过度复杂,不会为简单 change 制造流程负担 |

### 关键反例

这些反例比 happy path 更能证明 skill 是否真的改好了。

1. **视觉缺证据反例**
   - 输入:spec 写"像素级对齐原型"。
   - 证据:只有组件测试通过和一张实际截图,没有原型截图/对照结论。
   - 期望:reviewer fail visual_reference gate。

2. **平台能力误派产品验收反例**
   - 输入:330 类 JSONL 存储改造。
   - 证据:CLI/API resume transcript + pytest。
   - 期望:reviewer 执行 technical_acceptance;engineering gate 只查 pytest evidence;不要求普通用户 UI 旅程。

3. **纯重构无用户变化反例**
   - 输入:模块拆分,外部行为不变。
   - 证据:contract tests + diff checklist。
   - 期望:可以没有 product_acceptance;但缺 regression evidence 时不能进入 PR。

4. **历史结论继承反例**
   - 输入:上一轮 visual gate 是 "near",本轮改了代码。
   - 证据:只写"继承上一轮 near"。
   - 期望:最终 pass 前必须重跑当前实现的 reference gate,除非 Verification Plan 显式允许继承且文件未变化。

5. **工程 gate 伪装用户验收反例**
   - 输入:要求"warm turn 零磁盘读"。
   - 证据:用户多轮聊天成功。
   - 期望:technical/product gate 可 pass,但 engineering_verification 不能因此 pass;需要 test/instrumentation evidence。

### 通过门槛

第一版 skill set 可以用以下门槛判断是否可用:

- 6 个 eval 样本中,核心 gate 类型和 owner routing 至少 5 个正确。
- 所有关键反例都不能被错误 pass。
- user-facing UI 样本必须要求真实入口截图和 reference 对照。
- platform/internal 样本不能被强行要求普通产品验收。
- reviewer 报告中的每个 pass/fail 都能追溯到 Verification Plan 的 gate ID。
- orchestrator 能在 evidence 缺失时拒收 DONE/pass,而不是代补判断。

### 评测产物

建议每次改 skill 后留下:

- `eval-run.md`: 本次用的 skill commit / 样本 / 结果矩阵。
- `failures.md`: 哪些样本失败,是 prompt 问题、规则问题还是样本期望不清。
- `skill-changelog.md`: 为修 eval 做了哪些 skill 规则调整。

这相当于给 workflow 本身建立回归测试。以后再优化 skill 时,不要只看单个真实项目是否跑通,而是看是否破坏这些历史场景和反例。

## 暂定结论

当前最值得改的是 skill 的组织方式:

- 不拆成很多 reviewer skill。
- 保留一个 `change-reviewer`,但把它从"产品验收员"改成"Verification Plan executor"。
- 把 review 类型和证据要求前移到 design 阶段。
- 让 orchestrator 做证据完整性门禁,不是质量判断。

这样既能覆盖 330 这种内部平台改造,也能覆盖 340 这种强 UI/reference 改造,并且不会让 skill 集合变得过碎。
