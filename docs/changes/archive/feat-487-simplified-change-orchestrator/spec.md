# feat-487: 简化 change-orchestrator 实施流程

## 原始需求

> 帮我主仓切回到main，然后我想把change-orchestrator实现需求的流程简化，不要给太多约束，比如强制要求每个milestone要开subagent，还有一些流程的约束，来让现在的更强的agent模型发挥自己的能力，从而有更快的速度，更好的实现。原有的流程继续保留不变，因为我想对比下两边的效果和速度。
>
> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 理解吗，跟我对齐

## 澄清记录

- Q1: 新流程是否作为与原 `change-orchestrator` 并存的独立 feat，并暂名 `change-orchestrator-autonomous`？
  A(原话): autonomous不好，是简化。
  Agent 解读: 新流程的定位是“简化现有实施流程”；更强模型获得更大自主空间是简化后的效果，不是流程本身的定位。
- Q2: 简化版是否同时取消“orchestrator 不写代码”和“一个 milestone 必须派一个 worker”，由主 Agent 自己决定实现方式？
  A(原话): 当然，他自己要怎么干，他自己决定
  Agent 解读: 主 Agent 对实现负责，并自主决定亲自完成、拆分、派发 subagent 或组合使用，不预设执行角色与 milestone 的绑定关系。
- Q3: 简化版是否只固定交付终点，不固定中间过程？
  A(原话): 有些东西是不能省的，比如独立的检查。比如一个unit要开一个worktree。这你自己分析完再跟我对，不要甩手给我分析
  Agent 解读: 简化不等于取消全部过程约束。Agent 应先根据现有流程的真实风险分析出不可省的最小约束集合，再把已经完成取舍的建议交给用户确认。
- Q4: 是否把需求边界、unit worktree、实现自证、一个综合独立检查、问题闭环、完整交付和对比数据作为全部硬约束，其余执行方式交给主 Agent？
  A(原话): 三道闸还是要做的。
  Agent 解读: 验收不能合并为单一综合检查；现有 reviewer、verifier、code review 三个独立质量视角都必须保留。
- Q5: 是否要求首次验收完整执行 reviewer、verifier、code review 三道闸，fix 后按实际 delta 选择性复验，最终三道闸都对交付状态持有有效结论？
  A(原话): 对。
- Q6: 简化版是否还需要从 `change-impl-worker` 中识别并保留不能省略的实现质量约束？
  A(原话): impl worker skill你也要读下，里面有的东西也不能省，比如代码规范？
  Agent 解读: 取消强制 worker 派发不等于取消 worker 承载的工程质量职责；简化版主 Agent 必须继承其中与架构、代码规范、测试、真实入口验证、根因修复和资源隔离有关的底线，再去掉角色绑定与流程仪式。
- Q7: 是否以“简生命周期 + 工程质量底线 + 三道闸”为最终边界，不再复制 worker 的详细 SOP？
  A(原话): 对
  Agent 解读: 简化版保留 unit 隔离、实现质量、三道闸和完整交付；主 Agent 对内部实施组织拥有自主权。
- Q8: 简化版相对既有实施流程的改动边界是什么？
  A(原话): 我们唯一的目的是减流程稅，你不要自己加额外的东西，也不要自己多删东西，你整体自检一遍
  Agent 解读: 只解除角色绑定、固定拓扑、roadpoint、过程台账和轮次等实施编排税；现有需求、
  工程质量、独立验收与交付语义不增不减。流程效果比较复用任务时间线、三道闸报告和 PR / CI
  等自然产生的证据，不新增统计动作。
- Q9: 三道验收闸如何确保独立检查不被实施上下文中的自我审查替代？
  A(原话): 有个问题，你三道闸，有强调subagent吗
  Agent 解读: reviewer 与 verifier 分别由独立于实施上下文、彼此独立的 subagent 执行；
  code review 按自身 skill 派发独立 finder / verifier subagent。验收 subagent 不承担实现或
  修复，复验可复用原验收上下文。
- Q10: 如何避免实施过程自行选择原流程专用的 worker skill？
  A(原话): 然后，我担心他不小心调用了change-impl-worker。所以帮我把change-impl-worker的描述改一下，这个skill他不应该是agent自己选择触发的，而是change-orchestrator的要求触发的
  Agent 解读: `change-impl-worker` 仅在 `change-orchestrator` 明确要求被派发的 subagent 使用时
  触发；其他 agent 和实施流程不得自行选择。只收紧触发描述，不改变其正文职责与原派发行为。

## 用户场景

仓库协作者已经通过 spec / design 阶段把一个 change unit 的需求边界和技术意图对齐，希望开始实施。
现有 `change-orchestrator` 会把每个 milestone 绑定到独立 worker、milestone worktree、固定派发包和
`tasks.md` / `progress.md` 执行仪式。即使当前主 Agent 已有能力直接完成整个 unit，也必须承担多次冷启动、
上下文切换和调度成本。

协作者需要一条与原流程并存的简化版实施入口。选择简化版后，主 Agent 在该 unit 的独立 worktree 中对
“高质量完成需求并交付绿灯 PR”端到端负责。它可以亲自完成所有实现，也可以根据任务结构、上下文容量和
风险自主决定是否派 subagent、如何拆分、串行还是并行；milestone 继续表达必须覆盖的交付目标，但不再
天然绑定 worker、分支或 worktree。

这种自主性不能削弱工程质量。主 Agent 需要继承 `change-impl-worker` 中真正防止坏实现进入仓库的职责：
遵守现有架构和代码规范、复用既有机制、为可测试行为留下有效回归保护、从真实入口证明产品能用、对
非平凡失败追到根因，并隔离和回收自己使用的运行时资源。它不需要复制 worker 的固定阅读顺序、报信、
roadpoint、文档模板、提交拆分或 HANDOFF 协议。

实现完成后，简化版仍完整执行 reviewer、verifier、code review 三道闸，分别回答产品是否可用、
实现是否符合 spec / design、代码 diff 是否存在可交付风险。首轮三道闸全部执行；修复后由主 Agent
依据实际 delta 判断哪些结论失效，只复验受影响的范围，但交付时三道闸都必须对最终状态保有有效结论。

最终，协作者拿到与原流程同等级的交付结果：需求和必要文档完整、unit 可追溯、PR 已创建且 CI 全绿。
协作者可以直接用 Codex 任务时间线、三道闸报告和 PR / CI 记录比较两条流程的耗时、执行组织和返工情况，
不需要简化版额外维护统计记录。

## 验收标准

### Requirement: 原流程与简化版流程并存

#### Scenario: 用户选择简化版实施
- **GIVEN** 一个 change unit 已完成需求与设计对齐，可以进入实施
- **WHEN** 用户明确选择简化版流程实施该 unit
- **THEN** 主 Agent 使用 `$change-orchestrator-simple` 的职责完成该 unit
- **AND** 用户不需要修改或停用原有 `change-orchestrator`

#### Scenario: 用户继续选择原流程
- **WHEN** 用户选择原有 `change-orchestrator` 实施另一个 unit
- **THEN** 原流程的角色、派发、文档和验收行为保持不变

#### Scenario: 原流程明确派发 implementation worker
- **WHEN** `change-orchestrator` 在派发给 subagent 的任务中明确要求使用 `change-impl-worker`
- **THEN** `change-impl-worker` 正常触发并执行指定 milestone 或定向 fix

#### Scenario: 其他实施过程自行选择执行方式
- **WHEN** agent 没有收到 `change-orchestrator` 明确使用 `change-impl-worker` 的派发要求
- **THEN** 即使任务涉及 milestone、编码或 reviewer finding，也不会自行触发 `change-impl-worker`

### Requirement: 每个 unit 保持独立工作区

#### Scenario: 简化版开始实施
- **WHEN** 主 Agent 开始实施一个 unit
- **THEN** 用户能看到该 unit 使用独立 unit 分支和独立 unit worktree
- **AND** 主仓当前分支、已有修改和未跟踪文件保持不变

#### Scenario: unit 需要启动运行时服务
- **WHEN** 实现或验证需要启动监听端口、持有 socket 或使用持久化配置的服务
- **THEN** 用户现有的主仓服务和其他 unit 服务不被占用、覆盖或停止
- **AND** 本 unit 结束或暂停时不遗留由它启动的孤儿进程

#### Scenario: 无法安全建立隔离环境
- **WHEN** unit worktree 或所需运行时资源无法安全隔离
- **THEN** 主 Agent 不会改在主仓实施或用降级证据假装完成
- **AND** 用户得到保留现场的明确阻塞说明

### Requirement: 主 Agent 自主组织实现

#### Scenario: 主 Agent 判断直接实现更合适
- **WHEN** 主 Agent 判断自己可以高质量完成一个或多个 milestone
- **THEN** 它可以直接在 unit worktree 中完成实现
- **AND** 流程不会因为没有为每个 milestone 创建 subagent、分支或 worktree 而阻塞

#### Scenario: 主 Agent 判断委派更合适
- **WHEN** unit 中存在适合独立探索、并行实现或上下文隔离的工作
- **THEN** 主 Agent 可以自主选择是否派发 subagent 以及如何组织协作
- **AND** 用户不需要预先指定“一 milestone 一 worker”或固定模型、并行度和派发协议

#### Scenario: design 中存在多个 milestone
- **WHEN** 主 Agent 实施含多个 milestone 的 unit
- **THEN** 最终交付覆盖所有 milestone 的目标和退出标准
- **AND** milestone 不被当作必须采用某种人员或 worktree 拓扑的约束

### Requirement: 简化版继承实现质量底线

#### Scenario: 主 Agent 编写或修改代码
- **WHEN** 用户查看最终 PR 的实现
- **THEN** 代码遵守 design、仓库架构边界、现有实现模式和完整项目规范
- **AND** 简化版流程不另外新增或重新定义代码规范

#### Scenario: 新增或修复可测试行为
- **WHEN** unit 改变能够被自动化验证的行为
- **THEN** 用户能在 PR 中看到针对该行为的有效测试或回归保护
- **AND** 相关测试验证的是可观察行为而非私有实现细节

#### Scenario: unit 改变用户可见或跨进程行为
- **WHEN** unit 声明实现了新用户能力或修复了运行时问题
- **THEN** 用户能复查从真实产品入口得到的验证证据
- **AND** mock、stub 或进程内替代验证不会被当作真实链路成功的唯一依据

#### Scenario: unit 涉及前端界面
- **WHEN** 主 Agent 完成受影响的用户路径
- **THEN** 用户能复查真实浏览器中的关键交互、适用状态以及 console / network 检查结果
- **AND** 核心路径或历史 bug 留下与风险相称的回归保护

#### Scenario: 实施中出现非平凡失败
- **WHEN** 主 Agent 修复测试失败、运行时异常或 reviewer finding
- **THEN** 最终交付说明问题根因以及修复为什么位于正确层次
- **AND** 不以吞错、神秘 fallback、临时常量或 heuristic 绕过症状

#### Scenario: 实施发现技术方案需要调整
- **WHEN** 调整仍在用户已经确认的需求与验收范围内
- **THEN** 主 Agent 可以自主修订技术方案并保持 unit 文档与实现一致
- **AND** 如果调整会改变用户需求或验收范围，主 Agent 在继续前重新与用户对齐

### Requirement: 三道验收闸保持独立且完整

#### Scenario: 实现首次进入验收
- **WHEN** 主 Agent 判断 unit 已完成实现和自证
- **THEN** 用户能看到 reviewer、verifier、code review 三道闸均完成一次完整检查
- **AND** 三道闸分别提供产品旅程、需求与设计一致性、代码 diff 风险的独立结论
- **AND** reviewer 与 verifier 分别由独立于实施上下文、彼此独立的 subagent 执行
- **AND** code review 按自身 skill 派发独立 finder / verifier subagent，而不是由实施上下文自审
- **AND** 验收 subagent 不承担实现或修复

#### Scenario: 验收发现真实阻塞问题
- **WHEN** 主 Agent 判断某条 finding 证据充分、属于本 unit 且阻塞交付
- **THEN** 该问题在交付前被修复
- **AND** 用户能看到受影响的验收结论已经重新核实

#### Scenario: fix 只影响部分验收范围
- **WHEN** 修复没有使某些已有验收结论失效
- **THEN** 未受影响的结论可以保留，受影响的闸进行针对性或完整复验
- **AND** 最终交付摘要能说明三道闸各自的最新有效结论及其依据

#### Scenario: 三道闸或 CI 尚未通过
- **WHEN** 任一道闸仍有未关闭的阻塞问题，或 CI 仍然失败
- **THEN** 主 Agent 不会向用户报告 unit 已完成
- **AND** 用户得到当前状态、剩余问题和可恢复现场

### Requirement: 交付结果完整且可以与原流程比较

#### Scenario: 简化版成功完成 unit
- **WHEN** 实现、自证、三道闸和 CI 全部通过
- **THEN** 用户获得包含完整代码、测试、必要文档同步和 unit 历史的 PR
- **AND** unit 已按仓库现行规则归档，PR 可供人审查和合并

#### Scenario: 用户比较两种流程
- **WHEN** 简化版交付完成
- **THEN** 用户能使用任务时间线、三道闸报告和 PR / CI 记录比较两条流程的耗时、执行组织和返工情况
- **AND** 简化版不会为比较目的新增统计步骤或流程 ledger

## 范围与非目标

- 在范围：
  - 新增 `$change-orchestrator-simple` 作为可由用户明确选择的简化版 unit 实施流程，
    与原 `change-orchestrator` 并存
  - 收紧 `change-impl-worker` 的触发描述，使其只响应 `change-orchestrator` 的明确派发要求
  - 从已完成需求与设计对齐的 unit 接手，一直交付到 PR 创建且 CI 全绿
  - 主 Agent 端到端拥有实现，可自主决定是否以及如何使用 subagent
  - 每个 unit 的独立分支、unit worktree、运行时资源隔离与清理
  - 继承 `change-impl-worker` 中与架构、代码规范、测试、真实入口验证、根因修复有关的质量底线
  - reviewer、verifier 使用独立验收 subagent，code review 使用自身的独立 finder / verifier
    subagent；首轮完整检查并在 fix 后选择性复验
  - 必要文档同步、unit 归档和可追溯 PR
  - 使用任务时间线、三道闸报告和 PR / CI 等自然证据进行流程比较，不新增统计动作
- 非目标：
  - 不修改或替换原 `change-orchestrator` 的既有流程
  - 不修改 spec / design 阶段及其既有门禁
  - 不削弱仓库架构边界、代码规范、测试规范、真实入口验证、三道闸或 CI
  - 实现阶段不强制一 milestone 一 worker、milestone worktree、固定 subagent 模型/数量/并行方式
  - 不强制复制 `change-impl-worker` 的阅读顺序、报信、`tasks.md` / `progress.md` 模板、roadpoint、
    commit 拆分、HANDOFF 或固定失败次数
  - 不新增与降低实施编排税无关的质量门槛、交付步骤或度量流程
  - 不删除既有需求边界、工程质量、三道独立验收闸和完整交付语义
  - 不承诺简化版在每个 unit 上必然更快或更好；本期目标是提供可比较的替代流程并留下客观结果
