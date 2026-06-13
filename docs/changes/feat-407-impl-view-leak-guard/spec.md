# feat-407: SDD 流程防「实现视角泄漏进契约层与测试」

> 备注：本 unit 是 bugfix-404 PR 评审期暴露问题后的**流程改进立项**。根因取证见
> `docs/changes/bugfix-404-bg-notify-workspace-isolation/retro-impl-view-leak.md`。
> 实现（change-* skill + TESTING_GUIDE 的条款修订）已随讨论落地，本 spec 是对该需求的事后存档与验收基线。

## Relations

- Related: bugfix-404（本需求的根因证据与触发场景来自该 unit 的 PR 评审）

## 原始需求

> 这改文档本身也是个需求，帮我根据我们之前关于改文档的问答，在主仓补个 unit 写 spec.md

触发链（PR #91 评审期，用户逐条发现，原话见【澄清记录】）：审 bugfix-404 的 PR 时发现 ① 长青契约层
`docs/specs/` 里混进了大量实现层断言（`runs_registry.submit 被调用` / `log_error("...")`），② 新增测试里
有一批 mock-assert-called 的实现锁、还有一个测生产 no-op 路径的测试。顺着追根因，落到「SDD 流程没能
拦住 worker 的实现视角泄漏进 spec 和 test」。

## 澄清记录

- Q1: 契约层为什么混入实现层？
  A(原话): 「你这个 pr 在 spec 中插入了很多实现层的东西，而不是真正的 spec」「会导致长青 spec 膨胀」
  Agent 解读: 契约层应只写消费者可观察行为；实现层断言（函数被调用、日志字符串）不该进长青 spec。

- Q2: 测试有没有长期价值？
  A(原话): 「你再到 worktree 检查下，新增的那些测试是不是真正有长期价值的」
  Agent 解读: 一批 mock-assert-called 测内部调用、一个测 no-op 路径的测试，是实现锁，无长期回归价值。

- Q3: 偏离出现在哪个环节？（取证后修正了初判）
  Agent 取证: 早期推断「orchestrator §7.0 归并把 delta 改写成实现层」被 jsonl 证伪——§7.0 根本没归并
  kernel；真偏离是 M1 worker 在 C3 越界写了 kernel canonical（commit 3c085d10），凭实现视角投影。

- Q4: worker 为什么没执行已有的测试规范？
  A(原话): 「测试纪律不是在这 docs/TESTING_GUIDE.md 写了吗，是这个文件没覆盖吗，还是 worker 没读这个文件」
  A(原话): 「worker 没执行的原因是啥，我没啥思路，1. 查下是不是主 agent 给 worker 的输入，让他不完全遵守 skill 2. skill 写的不够明确，不够强调」
  Agent 取证: 文件**覆盖了**（TESTING_GUIDE line 11-12）；M1/M2 派发包标准、没弱化 skill（排除假设 1）；
  真因是 `change-impl-worker` §2.3「读上下文（不可跳过）」必读清单**漏列 TESTING_GUIDE**，worker
  （a00409/a100da）对它 Read=0 次、严格按清单读所以漏了，还照现有坏测试样本学（假设 2 成立，且更精确）。

- Q5: 修复条款的写法要求？
  A(原话，§0.13 精简): 「这个写的太啰嗦了，短点，强调了他就不会犯了」
  A(原话，§7.0 防御段删除): 「这种我觉得不用写了，新的 worker skill 应该不会再写了」
  Agent 解读: 硬规则要短而强调；§0.13 既禁 worker 碰契约层，§7.0 里「防 worker 越界写过」的兜底前提即消失，删去。

## 用户场景

作为 SDD 流程的 owner，希望未来跑 change-* 流程时，worker 的实现视角不再泄漏进两类长青产物（契约层
`docs/specs/` 与测试套件 `tests/`）：

- worker 启动「读上下文」时就读到 `docs/TESTING_GUIDE.md`，于是写 C1 红测前心里有「只测消费者可观察
  行为、别 mock-断言-内部调用、别照坏样本学」这把尺；参照现有测试时能认出并跳过反模式。
- worker 全程不碰契约层（canonical `docs/specs/` 与 delta `docs/changes/<unit>/specs/`）——发现对外行为
  有变只在 progress.md 记一句留给 orchestrator，所以实现细节进不了长青 spec。
- orchestrator 收尾把 delta 并进 canonical 时，有一道「实现层红线」把混入的内部函数名 / 类名 / 日志
  字符串 / `X 被调用` 断言滤掉；design-author 写 delta 时在源头同守这条红线。
- 某 roadpoint 改了一条实现路径（某调用变 no-op / 换了投递路径）时，测旧路径的测试被回头审视、删或改测
  新路径，不留「绿着却测一条产品不再走的路径」的死测试。

结果：长青契约层与测试套件只沉淀消费者可观察行为，不膨胀成实现日志。

## 验收标准

### Requirement: worker 不把实现细节写进契约层

#### Scenario: worker 实施 milestone 全程不碰契约层文件
- **WHEN** worker 完成一个 milestone（含 C3 文档阶段）
- **THEN** 它的 commit 只改 milestone 内 `progress.md` / `tasks.md`，不新增 / 修改 `docs/specs/` 或
  `docs/changes/<unit>/specs/` 下任何文件

#### Scenario: worker 发现对外行为有变
- **WHEN** worker 实现中发现某对外行为相对 design 有出入
- **THEN** 它在 progress.md 记一句留给 orchestrator，而不是顺手改契约层

### Requirement: worker 写测试前读到测试规范，且不照坏样本

#### Scenario: 读上下文阶段必读测试规范
- **WHEN** worker 走「读上下文（不可跳过）」清单
- **THEN** `docs/TESTING_GUIDE.md` 在必读项内、排在「现有测试」之前，worker 写任何测试前已读完

#### Scenario: 现有测试含反模式
- **GIVEN** 现有测试里掺着 mock 断言内部函数「被调用」、或测一条已失效 / no-op 的路径
- **WHEN** worker 参照现有测试组织自己的用例
- **THEN** worker 按 TESTING_GUIDE 判据识别并跳过这些反模式，不无脑模仿

### Requirement: 并进契约层的内容只含消费者可观察行为

#### Scenario: 归并时滤掉实现层断言
- **GIVEN** 某 delta 条目的 Scenario THEN 写了内部函数名 / 类名 / 日志字符串 / `X 被调用` 断言
- **WHEN** orchestrator 收尾把 delta 并进 canonical `docs/specs/<包>/spec.md`
- **THEN** 这些实现层表述被红线滤掉，不进长青契约层

#### Scenario: delta 源头即守红线
- **WHEN** design-author 产出 delta-spec
- **THEN** 其 Scenario THEN 从验收标准投影、只写消费者可观察结果，不含上述实现符号

### Requirement: 失效实现路径的测试被清理

#### Scenario: 实现路径改道后回审旧测试
- **GIVEN** 某 roadpoint 把一条实现路径废弃 / 改道（某调用变 no-op、换了发送 / 投递路径）
- **WHEN** 该 roadpoint 收尾
- **THEN** 测旧路径的测试被回头审视，删掉或改测新路径，不留「绿着却测产品不再走的路径」的死测试

## 范围与非目标

- 在范围：`change-impl-worker`（§0.13 禁碰契约层 / §2.3 TESTING_GUIDE 提为必读 + 坏样本警示）、
  `change-orchestrator`（§7.0 实现层红线 + fix 路径补 delta）、`change-design-author`（§4.8 红线 +
  Decision 不下沉实现机制）、`docs/TESTING_GUIDE.md`（§1 实现路径变更回审）的条款修订。
- 非目标：
  - 不动 `change-reviewer` / `change-verifier`（它们本就只验用户可观察，非本次泄漏源）。
  - 不回溯重写历史已合并 unit 的 spec / test（只防未来；bugfix-404 自身的收敛已在其 PR 内单独做）。
  - 不引入机械强制校验（如 `tests/contract/` 硬卡契约层措辞）——本期靠 agent 遵守 + 评审，红线是
    可机械自查的判据而非自动门禁。
</content>
</invoke>
