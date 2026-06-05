# Multi-Agent 系统设计复盘报告：从“拟人化争议”到 SDD Spec/Design Agent Team 架构

## 0. 报告目的

本文整理一次关于 multi-agent 系统设计的讨论，重点回答四个问题：

1. 很多论文和社区为什么反对“拟人化地设计多个不同工种的 agent”？
2. multi-agent 到底解决了哪些 single-agent 很难解决的问题？
3. 如果使用多 agent，怎样避免 context 分离、沟通误解、错误传播和验证不足？
4. 对 Spec-Driven Development（SDD）里的 spec/design 两个阶段，应该如何设计 agent team？

本文结论不是“不要 multi-agent”，也不是“不要人类岗位隐喻”，而是：

> Multi-agent 的价值不是让 AI 像人类公司一样演戏，而是用多个 context-specialized agents 扩大覆盖面、引入异质视角、隔离工具权限、形成中间证据链，并通过中心 orchestrator、claim ownership、closed-loop communication 和 verification gates 控制错误传播。

---

## 1. 核心结论

### 1.1 反对的不是 multi-agent，而是“浅层拟人化”

很多人反对的不是：

```text
一个主 agent 拆任务，多个 sub-agent 并行探索，最后汇总。
```

他们反对的是：

```text
CEO Agent
CTO Agent
PM Agent
Architect Agent
Engineer Agent
QA Agent

大家像公司开会一样聊天，最后主 agent 总结。
```

如果这些 agent 实际上：

```text
同一个模型
同一套工具
同一份 context
同样权限
同样目标
只是 prompt 里写了不同角色
```

那它们只是 persona cosplay，不是真正分工。

真正的问题不是“拟人化”这个词本身，而是：

> 只学了人类岗位的名字，没有实现岗位背后的信息边界、工具边界、权限边界、责任边界、产物边界和验证边界。

### 1.2 人类岗位隐喻可以保留，但必须机制化

人类岗位不是一个人格，而是一个 bundle：

```text
Role =
  Context
  Tools
  Authority
  Responsibility
  Incentive
  Ritual
  Artifact
```

翻译成 agent 系统，应该是：

```text
Agent Role =
  accessible_context
  allowed_tools
  allowed_actions
  decision_rights
  objective_function
  output_artifacts
  communication_protocol
  verification_obligations
```

所以，PM / Architect / QA 这类岗位名不是不能用。问题在于：这些岗位是否真的拥有不同的 context、tools、authority、artifact 和 gate responsibility。

如果只是：

```text
你是 PM，请从产品角度思考。
你是架构师，请从技术角度思考。
你是 QA，请从测试角度思考。
```

这不够。

如果是：

```text
Product Agent:
  context = 用户需求、历史需求、用户反馈、产品指标
  tools = issue tracker / feedback search / analytics
  output = user goals, acceptance criteria, non-goals, ambiguities
  authority = 定义需求范围和验收标准，但不能决定实现方案

Codebase Agent:
  context = 代码仓、调用链、依赖图、测试、历史 bug
  tools = code search / AST / call graph / test inventory
  output = impact map, evidence, negative searches, unknowns
  authority = 提供代码事实和影响范围，但不能决定产品范围

QA/Risk Agent:
  context = spec、design、历史缺陷、测试库存、风险 checklist
  tools = test runner / browser automation / coverage / bug database
  output = risk register, test matrix, blockers
  authority = 可以 block gate，但不能私自改需求或设计
```

这就不再是浅层拟人化，而是岗位机制的计算化。

---

## 2. Multi-Agent 真正解决 single-agent 的什么问题？

Multi-agent 的正面价值可以概括成六类。

### 2.1 Context scaling：扩大有效上下文和注意力容量

Single-agent 的问题不只是 context window 大小，还有 attention dilution。

即使一个模型理论上能塞进很多内容，它也不一定能稳定关注所有重要细节。尤其在 SDD 场景里，一个需求可能同时涉及：

```text
用户原始需求
历史需求
产品约束
代码仓
接口
数据库
权限
账单
测试
历史 bug
部署环境
监控
失败回滚
```

单 agent 同时处理这些信息，很容易漏。

Multi-agent 可以把一个巨大的 context 问题拆成多个更小、更聚焦的 context 问题：

```text
Product Context Agent:
  专注用户意图、验收标准、范围边界

Codebase Agent:
  专注代码事实、调用链、影响面

Test Agent:
  专注测试库存、覆盖缺口、可验证性

Risk Agent:
  专注历史 bug、边界条件、失败路径
```

这类设计的本质不是“多个角色聊天”，而是 context engineering。

### 2.2 Parallel exploration：并行探索，提高搜索覆盖和速度

很多任务不是线性推理，而是宽搜索：

```text
查多个代码模块
查多个竞品
比较多个设计方案
并行扫多个风险维度
验证多个可能原因
探索多个实现路径
```

单 agent 也能做，但通常是串行的，慢，而且容易早停。

Multi-agent 可以并行探索：

```text
Codebase Agent A 查 API 层
Codebase Agent B 查 DB 层
Codebase Agent C 查权限链
Codebase Agent D 查测试和历史 bug
Architecture Agent A 生成最小改动方案
Architecture Agent B 生成长期正确方案
Risk Agent 查边界条件和失败路径
```

这对 breadth-first research、大代码仓探索、多方案设计特别有价值。

### 2.3 Diversity：引入互补视角，降低过早收敛

Single-agent 容易先形成一个解释，然后后续推理围绕这个解释补理由。

Multi-agent 可以通过异质性减少过早收敛：

```text
不同模型
不同 prompt
不同 context
不同工具
不同目标函数
不同审查角度
```

但注意：不是 agent 数量越多越好。真正有价值的是“互补信息通道多”。

坏设计：

```text
派 10 个几乎一样的 agent 看同样内容。
```

好设计：

```text
Product Lens:
  从用户价值、范围和验收标准看

Codebase Lens:
  从真实代码约束和技术债看

Risk Lens:
  从失败路径、历史 bug 和边界条件看

Test Lens:
  从可验证性和测试覆盖看

Architecture Lens:
  从方案权衡、接口、数据、迁移和回滚看
```

### 2.4 Role separation：把生成、批判、验证、裁决分开

Single-agent 自己生成方案，再自己评价方案，容易“护短”。

Multi-agent 可以把不同认知角色拆开：

```text
Generator:
  尽可能提出可行方案

Critic:
  专门找漏洞

Verifier:
  检查证据、覆盖、约束

Adversary:
  假设方案是错的，主动找反例

Judge / Gate:
  判断是否可以进入下一阶段
```

这在软件设计里非常重要。比如：

```text
Design Agent:
  提出技术方案

Risk Agent:
  攻击方案，找边界条件和失败路径

Codebase Agent:
  验证设计依赖的代码事实是否成立

QA Agent:
  验证 acceptance criteria 是否可测试

Gate Verifier:
  判断是否存在 blocker
```

Reviewer / QA / Security agent 的意义不是它们叫这个名字，而是它们拥有不同目标函数、不同证据要求和 block 权限。

### 2.5 Tool / authority isolation：隔离工具、权限和环境

Single-agent 如果拥有所有工具和全部权限，会有几个问题：

```text
工具太多，选择困难
权限太大，安全风险高
上下文太杂，容易混乱
不同工具状态互相污染
难以审计谁做了什么
```

Multi-agent 可以按工具和权限域拆分：

```text
Codebase Explore Agent:
  只读代码、AST、call graph，不允许写文件

Implementation Agent:
  可以改代码，但必须基于 approved design

Test Agent:
  可以跑测试、读 coverage、做浏览器验收，但不能改 spec/design

Security Agent:
  可以扫描权限和敏感信息，但不能部署

Release Agent:
  可以读 CI、日志、部署配置，但不能直接上线
```

这对生产系统非常重要。不是所有 agent 都应该拥有同样权限。

### 2.6 Structured workflow / auditability：形成阶段产物和证据链

Single-agent 很容易把中间假设糊在长上下文里。最终你看到的是一篇 design，但很难回答：

```text
这个代码事实谁说的？
证据在哪里？
哪个设计决策用了它？
谁确认过？
哪个风险还没解决？
为什么 gate 过了？
```

好的 multi-agent 设计可以强制产生中间 artifact：

```text
Spec artifact
Impact map
Design options
Risk register
Test matrix
Claim registry
Gate verdict
Blocker list
```

这让系统更可审计，也更方便人类在关键节点介入。

---

## 3. Multi-Agent 的主要风险

Multi-agent 的收益不是免费的。它引入了新的系统级风险。

### 3.1 L1：局部任务失败

sub-agent 自己没做好任务。

例子：

```text
Codebase Agent 漏掉 billing/seat.ts。
QA Agent 漏掉权限测试。
Product Agent 没识别 partial success 的产品语义问题。
```

解决方法：

```text
更清晰的 task spec
更好的 tools
更好的 context slice
固定 checklist
evidence-backed output
negative search
confidence / unknowns
局部 verifier
```

### 3.2 L2：交接 / 理解失败

上游 agent 输出没错，但下游 agent 用错了。

例子：

```text
Codebase Agent:
  “billing/seat.ts 需要考虑。”

Architecture Agent:
  “那我只要在批量导入前做一次总 seat 检查。”

但 Codebase Agent 原意其实是：
  “单个 invite 创建路径里有 seat check。
   bulk import 是整体预检还是逐行检查，需要产品语义和事务边界决定。”
```

解决方法：

```text
claim id
scope
caveat
downstream usage tracking
owner review
state reconciliation
canonical artifact update
```

### 3.3 L3：系统组合失败

每个 agent 局部都看起来没错，但整体组合后不成立。

例子：

```text
Product Agent 定义了批量导入成员。
Codebase Agent 找到了 invite / billing / audit。
Architecture Agent 设计了逐行导入。
QA Agent 写了 CSV、重复邮箱、seat 超限测试。

但整体漏掉：
第 60 行失败时，前 59 行是否回滚？
seat 是否已经占用？
audit 是否记录 partial failure？
用户看到的结果是什么？
```

这不是某个 agent 单独没做好，而是跨产品语义、架构事务、账单逻辑、审计要求和测试验收的组合问题。

解决方法：

```text
main orchestrator
canonical artifact
cross-context consistency check
design gate
human decision on product semantics
```

---

## 4. Single-Agent 与 Multi-Agent 的错误形态差异

### 4.1 Single-agent 不是没有错误

Single-agent 也会有：

```text
漏查
幻觉
过早收敛
上下文过载
自我确认偏误
工具调用失败
```

不能说 single-agent 更可靠。

### 4.2 Single-agent 少了一类错误：跨 agent 信任边界

Single-agent 的中间假设通常在同一条推理轨迹里：

```text
我刚才以为只影响 invite.ts。
但现在看到 billing/seat.ts。
所以我要修正前面的判断。
```

Multi-agent 多了一层：

```text
A agent 产出局部结论
B agent 把它当外部事实
C agent 基于 B 的设计继续写测试
D agent 汇总时继承这个前提
```

这会产生 error propagation / error amplification。

所以不是：

```text
single-agent 更聪明。
```

而是：

```text
single-agent 的优势是全局连续性；
multi-agent 的优势是覆盖面和异质性；
multi-agent 的风险是协调、交接和信任边界。
```

合理设计不是二选一，而是 hybrid：

```text
Main Orchestrator:
  保持全局任务连续性

Specialist Agents:
  扩大 context 覆盖和局部深挖

Verification Gates:
  防止局部错误进入全局状态
```

---

## 5. 对“拟人化 agent”的最终判断

### 5.1 不应该说“拟人化一定不合理”

这太粗糙。

更准确的是：

> 人类岗位可以作为设计隐喻，但不能只实现岗位名字，必须实现岗位机制。

### 5.2 浅层拟人化的问题

浅层拟人化是：

```text
PM Agent
Architect Agent
Engineer Agent
QA Agent

所有人：
  同模型
  同 context
  同工具
  同权限
  同目标
  最后靠自然语言讨论
```

这会制造虚假的专业性。

### 5.3 机制化岗位是合理的

合理设计是：

```text
Product Agent:
  独立 context：用户需求、反馈、指标
  独立 artifact：user goals, AC, non-goals, ambiguities
  独立 authority：定义范围和验收，不决定实现

Codebase Agent:
  独立 context：代码仓、调用链、测试、历史 bug
  独立 artifact：impact map, evidence, unknowns
  独立 authority：提供代码事实，不决定产品语义

Architecture Agent:
  独立 context：approved spec + code evidence + system constraints
  独立 artifact：design options, tradeoffs, interface/data/migration plan
  独立 authority：提出设计，不私自改需求

QA/Risk Agent:
  独立 context：spec + design + risk checklist + historical bugs
  独立 artifact：risk register, test matrix, blockers
  独立 authority：可以 block gate

Gate Verifier:
  独立 context：所有 canonical artifacts
  独立 artifact：gate verdict, blocker list
  独立 authority：决定是否进入下一阶段
```

这不是 cosplay，而是 protocol-driven multi-agent organization。

---

## 6. Closed-loop communication：为什么“群聊/会议机制”有价值

### 6.1 会议的真实价值

人类开会不只是为了同步信息。很多时候，把某个人叫进会，是为了确保别人使用他的领域信息时没有误解。

对应到 agent 系统：

```text
A Agent 输出 claim。
B Agent 使用 A 的 claim。
A Agent 应该看到 B 如何使用自己的 claim。
如果 B 用歪了，A 要及时澄清。
```

这叫 closed-loop coordination。

### 6.2 普通群聊不够

普通群聊只提供 visibility，不提供 reliability。

问题：

```text
消息太多，agent 未必注意到
没人知道谁该确认
大家都看到了，但没人负责
澄清留在聊天里，没有写回正式状态
```

### 6.3 可靠版本：claim registry + usage tracking + owner review

应该设计成：

```text
Claim Registry:
  每个关键结论都有 id、owner、evidence、scope、caveat、confidence、unknowns

Usage Tracking:
  下游 artifact 必须声明用了哪些 claim

Owner Review:
  claim owner 必须确认下游使用是否准确

Canonical Artifact:
  所有澄清必须写回正式 spec/design/test/risk artifact

Gate Verifier:
  未确认、被误解、存在冲突的 claim 不能过 gate
```

流程示例：

```text
1. Codebase Agent 产出 claim C-017：
   “billing/seat.ts 对新增成员有 seat limit 约束。”

2. Architecture Agent 在 design decision D-004 中引用 C-017：
   “批量导入前先整体检查 seat limit。”

3. 系统自动通知 Codebase Agent：
   “D-004 使用了你的 C-017，请确认是否准确。”

4. Codebase Agent 返回：
   needs_revision:
     C-017 只能证明单个 invite 创建前会检查 seat。
     不能推出 bulk import 必须整体预检查。
     需要 Product Agent 决定 partial success vs all-or-nothing。
     需要 Architecture Agent 定义事务边界。

5. Main Orchestrator 更新 canonical artifact：
   新增 unresolved design question:
     批量导入是 all-or-nothing 还是 partial success？

6. Gate Verifier block：
   Design gate blocked until product semantics + transaction behavior are resolved.
```

一句话：

> 群聊是可见性机制，不是可靠性机制；claim-owner review 才是可靠性机制。

---

## 7. Verification：multi-agent 系统的骨架

Verification 不能只是最后加一个 Reviewer Agent。它应该贯穿每个关键产物、每次交接、每个阶段 gate。

### 7.1 Verification 要覆盖四件事

```text
verify local work
verify handoff usage
verify global consistency
verify human intent
```

### 7.2 L1 局部验证：sub-agent 不能只交结论

坏输出：

```text
主要影响 member/invite.ts。
```

好输出：

```json
{
  "impact_map": [
    {
      "component": "member/invite.ts",
      "impact_type": "direct_entrypoint",
      "evidence": ["..."],
      "confidence": 0.92
    },
    {
      "component": "billing/seat.ts",
      "impact_type": "seat_limit_dependency",
      "evidence": ["..."],
      "confidence": 0.81
    }
  ],
  "negative_searches": [
    "searched audit log writers",
    "searched permission guards",
    "searched seat accounting"
  ],
  "unknowns": [
    "未确认 legacy import path 是否仍被使用"
  ],
  "recommended_followups": [
    "run call graph from invite service",
    "inspect billing tests"
  ]
}
```

sub-agent 的完成标准不是“说了一个结论”，而是：

> 提交一个可审计、可复查、可挑战、可合并的 artifact。

### 7.3 L2 交接验证：上游 owner 确认下游 usage

流程：

```text
A 产出 claim C-17
B 的设计 D-04 使用 C-17
系统自动通知 A：
  B 使用了你的 claim，请确认是否准确
A 返回：
  approved / needs_revision / out_of_scope / missing_caveat
```

这解决：

```text
A 是对的，但 B 用歪了。
```

### 7.4 L3 系统验证：检查闭环，而不是检查文档是否齐全

弱 gate：

```text
有 spec
有 design
有 test plan
有风险分析
```

强 gate：

```text
每条用户目标 → 是否有 acceptance criteria？
每条 acceptance criteria → 是否有 design support？
每个 design decision → 是否有 evidence / rationale？
每个 critical claim → 是否有 owner / evidence / scope / caveat？
每个 risk → 是否有 mitigation / test / monitoring？
每个 unknown → 是否 resolved 或 blocking？
每个 API / data change → 是否有 error path / migration / rollback？
每个 claim usage → 是否经过 owner review？
```

### 7.5 Mechanical / Semantic / Human 三类 verifier

#### Mechanical Verifier

负责硬规则：

```text
schema 是否合法
必填字段是否存在
claim id 是否能解析
AC 是否映射到 design/test
文件是否存在
测试是否能跑
引用是否完整
```

#### Semantic Verifier

负责语义挑战：

```text
设计是否真的满足 AC？
有没有过度推导？
有没有遗漏风险？
不同 agent 的 claim 是否冲突？
unknown 是否被错误地当成 resolved？
```

#### Human Verifier

负责人类判断：

```text
需求范围是否正确？
产品语义是否符合预期？
风险是否接受？
tradeoff 是否可接受？
是否批准进入下一阶段？
```

### 7.6 Verification 必须能 block

Reviewer 只说“我发现风险”，但流程继续推进，这不叫 gate。

真正的 gate 必须能输出：

```json
{
  "status": "blocked",
  "blockers": [
    "AC-03 没有设计映射",
    "C-17 被 D-04 过度推导，claim owner 未批准",
    "批量导入 partial success 语义未确认"
  ]
}
```

只有 blocker 清零，才能进入下一阶段。

---

## 8. 推荐的 SDD Spec/Design Agent Team 架构

### 8.1 总体拓扑

```text
                         Main Orchestrator
                                │
                                ▼
                      Canonical Artifact Store
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
 Product Context Agent   Codebase Context Agent   QA/Risk Agent
          │                     │                     │
          ▼                     ▼                     ▼
   Product Claims        Impact Claims        Risk/Test Claims
          └─────────────────────┼─────────────────────┘
                                ▼
                         Claim Registry
                                │
                                ▼
                    Downstream Usage Review
                                │
                                ▼
                    Architecture / Design Agent
                                │
                                ▼
                  Mechanical + Semantic Verifiers
                                │
                                ▼
                            Human Gate
```

### 8.2 Main Orchestrator

职责：

```text
维护全局任务连续性
维护 canonical artifacts
拆分任务给 specialist agents
追踪 claim dependency
触发 owner review
处理 conflict / unknown / blocker
决定是否进入下一阶段
```

注意：Main Orchestrator 不应该做所有局部探索。它的核心价值是保持全局一致性和推进状态机。

### 8.3 Product Context Agent

输入：

```text
用户原始需求
历史需求
产品目标
用户反馈
业务约束
```

输出：

```text
user goals
acceptance criteria
non-goals
ambiguities
open questions
product semantics decisions
```

关键验证：

```text
每条 AC 是否可验收？
是否有非目标？
是否有 unresolved ambiguity？
是否需要 human confirmation？
```

### 8.4 Codebase Context Agent

输入：

```text
代码仓
调用链
模块边界
接口
数据库模型
测试
历史 bug
架构文档
```

输出：

```text
impact map
direct / indirect touchpoints
call graph evidence
data/API/test impact
negative searches
unknowns
confidence
recommended followups
```

关键验证：

```text
是否覆盖权限、账单、数据、接口、测试、迁移、监控？
是否有 evidence？
是否有 negative search？
是否列出 unknown？
critical claim 是否需要二次验证？
```

### 8.5 Architecture / Design Agent

输入：

```text
approved spec
product claims
codebase impact claims
system constraints
risk register
```

输出：

```text
design options
tradeoffs
selected design
interface changes
data changes
migration / rollback plan
error handling
observability plan
implementation decomposition
```

关键验证：

```text
每个 design decision 是否引用上游 claim？
是否存在过度推导？
是否处理失败路径？
是否有 migration / rollback？
是否有兼容策略？
```

### 8.6 QA / Risk Agent

输入：

```text
spec
design
historical bugs
test inventory
risk checklist
```

输出：

```text
risk register
edge cases
AC → test mapping
risk → test mapping
missing verifiability
blockers
```

关键验证：

```text
每条 AC 是否有测试策略？
每个 critical risk 是否有 mitigation 或 test？
是否存在不可测试需求？
是否需要人类确认风险接受？
```

### 8.7 Gate Verifier

输入：

```text
canonical spec
impact map
design
risk register
test matrix
claim registry
owner review status
```

输出：

```text
gate verdict:
  pass / blocked / needs_human_review

blockers:
  unresolved AC
  missing design mapping
  unreviewed claim usage
  unresolved conflict
  missing migration/rollback
  missing test coverage
  unknown not resolved
```

---

## 9. Spec/Design 阶段推荐 Gate

### 9.1 Gate 1：Spec Gate

目标：确认“做什么”。

检查：

```text
用户目标清楚吗？
非目标清楚吗？
acceptance criteria 可验收吗？
open questions 是否清零或显式标注？
边界条件是否列出？
是否需要人类确认产品语义？
```

Human gate：

```text
确认需求范围
确认验收标准
确认优先级
确认产品语义
```

### 9.2 Gate 2：Context / Evidence Gate

目标：确认“我们理解了现有系统”。

检查：

```text
impact map 是否有证据？
是否覆盖关键系统维度？
是否有 negative searches？
是否有 unknown？
critical claim 是否二次验证？
```

Human gate：

```text
高风险代码影响范围是否需要人工确认？
```

### 9.3 Gate 3：Design Gate

目标：确认“怎么做”。

检查：

```text
每条 AC 是否映射到设计？
每个设计决策是否有依据？
是否处理错误路径、回滚、兼容、监控？
是否存在 unresolved conflict？
上游 claim 是否被正确使用？
```

Human gate：

```text
确认技术方案
确认风险接受
确认产品/技术 tradeoff
```

### 9.4 Gate 4：Implementation-Ready Gate

目标：确认“能不能开工”。

检查：

```text
任务是否可拆成实现单元？
每个任务是否有明确输入输出？
测试策略是否覆盖验收标准和主要风险？
是否存在 blocker？
是否可以交给 coding agent？
```

Human gate：

```text
批准进入实施阶段
```

---

## 10. 设计原则 Checklist

以后评估一个 multi-agent 设计，可以直接问 15 个问题。

### 10.1 Agent 分工

```text
1. 每个 agent 的 context 是否真的不同？
2. 每个 agent 的 tools 是否真的不同？
3. 每个 agent 的 authority 是否明确？
4. 每个 agent 的 output artifact 是否结构化？
5. 每个 agent 的完成标准是否可验证？
```

### 10.2 Communication / Handoff

```text
6. 每个关键 claim 是否有 id、owner、evidence、scope、caveat？
7. 下游 artifact 是否声明用了哪些 claim？
8. claim owner 是否必须 review 下游 usage？
9. 澄清是否会更新 canonical artifact？
10. conflict / unknown 是否会进入 blocker list？
```

### 10.3 Verification

```text
11. 是否有 local verifier 检查 sub-agent 产物？
12. 是否有 handoff verifier 检查 claim usage？
13. 是否有 global verifier 检查整体闭环？
14. gate 是否能 block，而不是只给建议？
15. 哪些判断必须由人类确认？
```

如果这些都没有，那就是浅层 multi-agent。

如果这些都具备，哪怕 agent 名字叫 PM / Architect / QA，也不是问题。

---

## 11. 最终参考架构：Protocol-driven Multi-Agent Organization

最终推荐架构不是：

```text
多个 agent 自由聊天
```

而是：

```text
protocol-driven multi-agent organization
```

它包含：

```text
1. Main Orchestrator
   保持全局连续性、状态、冲突处理和阶段推进。

2. Context-specialized Agents
   分别负责产品、代码、架构、测试、风险等局部 context。

3. Evidence-backed Artifacts
   每个 agent 输出可审计 artifact，而不是自然语言意见。

4. Claim Registry
   所有关键结论有 owner、evidence、scope、caveat、confidence、unknowns。

5. Closed-loop Communication
   下游使用上游 claim 时，触发 claim owner review。

6. Canonical Artifact Store
   聊天不是最终状态，正式状态必须写入 spec/design/risk/test artifacts。

7. Mechanical Verifier
   检查 schema、链接、覆盖、测试、引用完整性。

8. Semantic Verifier
   检查语义冲突、过度推导、遗漏风险。

9. Human Gate
   处理需求范围、产品语义、风险接受、tradeoff。

10. Blocking Gate
   blocker 未清零，不允许进入下一阶段。
```

---

## 12. 一句话总收束

Multi-agent 的价值是：

```text
扩大 context 覆盖
并行探索
引入异质视角
分离生成/批判/验证
隔离工具权限
形成中间证据链
```

Multi-agent 的风险是：

```text
局部错误
交接误解
状态不一致
错误传播
验证不足
协调成本
```

所以，一个成熟的 SDD spec/design multi-agent 系统应该是：

```text
中心主 agent 保持全局连续性
+
多个 context-specialized sub-agents 扩大覆盖面
+
每个 sub-agent 产出 evidence-backed artifact
+
所有关键 claim 被注册、引用、确认
+
每个阶段都有 mechanical / semantic / human verification gate
+
blocker 未清零不得推进
```

最终原则：

> 不要为了像人类公司而设计 multi-agent；要为了 context、parallelism、diversity、authority isolation、auditability 和 verification 来设计 multi-agent。岗位名可以保留，但岗位机制必须落地。

来源索引：Anthropic 的《Building effective agents》强调从简单方案开始，只在必要时增加 agentic complexity，并列出 prompt chaining、routing、parallelization、orchestrator-workers、evaluator-optimizer 等模式；Anthropic 的 multi-agent research system 文章说明了用 lead agent + parallel subagents 扩展上下文和并行探索的价值。([Anthropic][1])

MAST《Why Do Multi-Agent LLM Systems Fail?》把 MAS 失败模式归为 specification/system design、inter-agent misalignment、task verification/termination 三类，并指出仅改 role specification 或 orchestration strategy 不足以解决所有失败。([arXiv][2])

Google Research 的 scaling agent systems 研究强调任务结构决定 multi-agent 是否有效：parallelizable tasks 更适合，sequential reasoning tasks 可能退化；它也讨论了错误级联和 centralized coordination 的 validation bottleneck 价值。([谷歌研究][3])

MetaGPT、ChatDev、AutoGen 分别代表了 SOP/assembly-line 式多 agent 软件工程、chat-chain 式多轮沟通、以及可编程多 agent conversation framework 这三类路线。([arXiv][4])

Multi-agent debate 工作支持“多个实例通过辩论/互证提升事实性和推理”的方向，但也提醒价值来自多样性、证据和验证，不是简单堆人数。([arXiv][5])

[1]: https://www.anthropic.com/research/building-effective-agents?utm_source=chatgpt.com "Building Effective AI Agents"
[2]: https://arxiv.org/abs/2503.13657?utm_source=chatgpt.com "Why Do Multi-Agent LLM Systems Fail?"
[3]: https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/?utm_source=chatgpt.com "Towards a science of scaling agent systems - Google Research"
[4]: https://arxiv.org/abs/2308.00352?utm_source=chatgpt.com "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework"
[5]: https://arxiv.org/abs/2305.14325?utm_source=chatgpt.com "Improving Factuality and Reasoning in Language Models through Multiagent Debate"
