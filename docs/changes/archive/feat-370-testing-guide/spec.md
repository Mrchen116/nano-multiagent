# feat-370: 确立测试规范 TESTING_GUIDE，约束 worker 的测试产出

## Relations

- Related: change-impl-worker skill（消费本规范）

## 原始需求

> 当前代码仓里面有大量的测试，但我怀疑有很多都是没用的，或者可以整合的。你帮我从代码规范，以及代码仓管理的角度去审视一下现在的情况。

（讨论过程中收敛出真正的需求）

> 我现在是用ai agent做开发的，我在change-impl-worker skill要求，他要进行tdd。但是我现在又没有一套明确的规范，应该怎么写这些测试？所以他有可能会写的乱七八糟。写一大堆。我觉得这也是现在需要治理的一个根因。那我觉得后面我们是不是可以在 COMMENTING_GUIDE.md 写下测试的规范，但是我不懂，有什么规范？

> 现在主要就是有很多东西没有进行约束，就没有告诉 agents。实际上如果告诉他了，他的遵从性是很好的。可能都不需要太多的硬性约束，或者反复强调。

## 澄清记录

- Q1: 测试规范放进 COMMENTING_GUIDE.md 还是独立成文？
  A(原话): 「对。」（同意"单独开 docs/TESTING_GUIDE.md，而不是塞进 COMMENTING_GUIDE.md。测试规范的体量和 change-impl-worker 引用它的频率，都值得独立成文"）
  Agent 解读: 独立 `docs/TESTING_GUIDE.md`，COMMENTING_GUIDE 只管注释，职责分开。

- Q2: 约束力度——要不要同时建机械校验的 contract 测试当"牙齿"？
  A(原话): 「现在主要就是有很多东西没有进行约束，就没有告诉 agents。实际上如果告诉他了，他的遵从性是很好的。可能都不需要太多的硬性约束，或者反复强调。」
  Agent 解读: 本期只做"告诉 agent"（写规范 + 接线让 worker 必然读到），不建 contract 校验；等观察到某条仍反复被违反再针对性加机械校验。

- Q3: 缺的到底是哪些规范？（通过回顾 change-* skill + 实际产出文档分析得出）
  A(原话): 「说白了就是你找到现在的缺点是什么？你才能用一套规范文档让他不再犯。」
  Agent 解读: change-impl-worker 已有测试指导，但都是"软劝告/anti-pattern"，没有可机械执行、事后可检查的硬规则。对照 skill 说的 与 实际产出，定位到 6 类缺口：①每 milestone 默认新建文件→320 文件爆炸 ②无命名法/无"目录=层"法→`test_m170_*`/`corrigendum` 流水号命名、测试错放层 ③可选重依赖裸 import→playwright 炸全套收集 ④临时验收证据与永久回归测试混为一谈→acceptance 快照永久堆积 ⑤无停止条件/无行数上限→2000+ 行巨型文件 ⑥跨层重复断言→m102/m103 测同一逻辑。

- Q4: CI 是否纳入本期？
  A(原话): 「我这个就是开源仓库。」（确认 GitHub Actions 对 public repo 免费无限）
  Agent 解读: CI 与存量清理（修 m170、拆巨型文件、清快照）是"治存量"，与本期"约束新产出"是两件事；本期不做，列入后续。

## 用户场景

本仓用 AI agent 做开发，`change-impl-worker` 在 TDD 三提交循环里写测试。它当前**有**测试指导（skill §3.1 陷阱清单、§9 anti-pattern），但全是"避免/陷阱"式的软劝告——没有一条是 worker 能机械照做、且事后能被复核的硬规则。结果在"必须证明功能能用"的压力下，worker 反复产生同类乱象：

- 每个 milestone 默认新建 `test_<新文件>.py`，从不先找"这个行为现在在哪测"，导致测试文件累积到 320 个；
- 当 milestone 本身是"主语"时，直接拿编号命名文件（`test_m170_*`、`test_refactor353_corrigendum`、`*_rerun_acceptance`），半年后无人能解读；
- 浏览器/重依赖测试落在 `tests/unit/` 且裸 `import playwright`，缺依赖时 `pytest --co` 整个中断，2170 个用例一个都跑不了；
- 把"这次交付时验一下"的一次性验收脚本当成永久 `test_*.py` 提交，快照越堆越多；
- 没有停止条件和行数上限，单文件涨到 2754 行；
- 同一逻辑在 unit + integration 各测一遍（m102/m103）。

用户的判断：agent 不是不听话，是**没人告诉它规则**——「如果告诉他了，他的遵从性是很好的」。所以治理的杠杆是把这些散落的软劝告，收成一份 worker 写测试前必读的硬规范，并让 worker 在流程中必然撞见它、并把关键决策显式记录到 tasks.md 供复核。

变更后：worker 启动写测试前先读 `docs/TESTING_GUIDE.md`，按规则决定"该不该写/写在哪/归谁"，并在 tasks.md 测试策略段逐项填空记录决策；reviewer 与人能据此复核。不引入机械强制——先靠"告诉它"，观察遵从度。

## 验收标准

- [ ] 仓库根下存在 `docs/TESTING_GUIDE.md`，覆盖：测什么/不测什么的停止条件、先定位再新建、命名禁流水号、目录即分层 + e2e marker、可选依赖 importorskip、临时验收证据 ≠ 永久回归测试、单文件行数上限、tasks.md 测试策略必填。
- [ ] `AGENTS.md` 顶部"开发规范"区与"关键文档索引"表都能查到指向 `docs/TESTING_GUIDE.md` 的入口。
- [ ] `change-impl-worker` skill 的测试规划段开头指向 `docs/TESTING_GUIDE.md` 为规则唯一真源，规则细节不在 skill 内重复。
- [ ] worker 复制的 `tasks.md` 模板里"测试策略"段是逐项填空（被测行为／已有测试在哪／落层 marker／importorskip／一次性验收证据），不再是自由散文。
- [ ] 后续一个真实 milestone 跑下来，worker 产出的 tasks.md 测试策略段按填空项填齐，且新增测试不出现 milestone 流水号命名、浏览器测试落在 e2e 并带 marker。

## 范围与非目标

- 在范围：新建测试规范文档；接线（AGENTS.md 索引、skill 引用、tasks.md 模板）让 worker 必然读到并记录决策。
- 非目标（治存量，另立 unit）：修 `test_m170_rerun_acceptance.py` 的 collection 报错；拆 2000+ 行巨型测试文件；清理 milestone 快照/acceptance 一次性脚本；合并跨层重复测试；引入 GitHub Actions CI；建机械校验的 contract 测试。
