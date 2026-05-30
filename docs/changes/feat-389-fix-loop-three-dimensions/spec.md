# feat-389: change-* 修复反馈循环 — 三条正交维度纠偏

## Relations

- Related: feat-352-trivial-fix-fast-lane（本 unit 修正其 §FL「trivial 判据」偏差并补全初心）、refactor-387-kernel-sdk-no-http-api（暴露问题的实战 session）、feat-350-dispatch-checkin-clarify（复用上下文依赖的 team / SendMessage 机制）

## 原始需求

<!-- 用户原话，原样保留。按时间顺序粘三段——驱动本 unit 的两条线（复用 worker、架构治本）在对话中汇合成"三维度"。 -->

> （线一·复用 worker）我的初心就是有很多 bug 不用新派 worker，能减少 worker 浪费时间去找对应的上下文。

> （线二·架构治本）我发现 59200168-332b-4ceb-9e99-e2eb26a11e5f 这个 session 中，reviewer 找到 bug 后，orchestrator 派 worker 修复问题是考虑的最小路径，完全没思考架构最合理的问题，就会导致我们辛苦的做 spec，design，最终 worker 按架构干完后，出现了 bug，这时候就完全不考虑架构设计了，只随便把代码能跑通，解了 bug 就行，往往把架构弄乱。在那个 session 中，我说了"注意，修复问题，要的是最合理的架构，不是最短路径"，他才纠过来。

> （两线汇合）其实这里是三个问题，复用上下文、减流程仪式（流程税）、架构治本，都是正交的。

## 澄清记录

- Q1: 修复"最短路径"破坏架构的问题，约束该落在谁身上？要多重？
  A(原话): reviewer 提我决定是没问题的，这是 reviewer 的视角。但是作为研发的视角，worker 和 orchestrator 得明确。也不用太重。他们目前的问题是没有这个意识。
  Agent 解读: 不约束 reviewer 给最小路径（那是它的产品视角）；在 worker / orchestrator 植入"研发视角=治本"的意识，原则级而非强制闸。

- Q2: 快车道（复用 / 减仪式）和"做架构考虑"是不是冲突？该怎么拆？
  A(原话): 按我的理解，就刚刚看的 session 这个情况就是快车道没问题，但是和需要做架构考虑没有任何冲突。/ 其实这里是三个问题，复用上下文、减流程仪式（流程税）、架构治本，都是正交的。
  Agent 解读: feat-352 把"快车道"焊成了"trivial→全省 / 否则全不省"，并把判据绑在"改动大小"。实际是三条正交维度，各有独立判据：复用上下文（原 worker 是否还在）、减流程仪式（fix 是否自包含）、架构治本（根因在哪层、能否测到）。session 里"复用原 worker + SDK 源头根治"恰恰是三者叠加的最优解。

- Q3: feat-352 那次到底有没有落地"复用原 worker"？
  A(原话): （核实后确认）feat-352 commit a5bc48dd 只把 reviewer 的实例复用写明了，worker 侧的复用从没进 skill；§FL 重心偏到了"减流程仪式 + typo/样式 trivial 判据"，初心（复用原 worker 省冷启动）被淡化。
  Agent 解读: 这与本 unit 线一是同一个洞——需在 §FL 补"优先复用原 milestone worker"。

- Q4: 约束落点放哪？feat-352 历史文档怎么处理？
  A(原话): 放 §6.FL 就够。feat-352 文档只加个 changelog。
  Agent 解读: 不升格成 orchestrator §0 硬规则；feat-352 spec/design 正文不回改，只加 Changelog 一行追溯。

## 用户场景

**镜头：回归基线 + 新增能力混合。** "用户"是启动 `change-orchestrator` 跑一个 unit 的仓库协作者。

**当前痛点（实战 session refactor-387 暴露）**：

worker 按 spec / design 把 milestone 干完，reviewer 走旅程发现 bug。reviewer 在报告里顺手给了「最小路径：改第 X 行 `event.get`→`event.data.get`」。orchestrator 收到后**原样转包**这条最短路径派 worker——worker 在崩溃点贴个本地补丁，bug 症状是消了，但根因（SDK 把内核内部 `StreamEvent` 类型泄漏到公开表面）没动，下一个消费方还会踩，架构契约被进一步弄乱。辛苦做的 spec / design 架构，在"修 bug"环节被一点点蚀空。我必须亲口说"要最合理的架构，不是最短路径"，它才回头做源头根治。

与此并行的另一个浪费：每次 reviewer 反馈一个小问题，orchestrator 就新派一个 fix worker，新 worker 要花很多时间重新爬 6 项上下文才能动手——哪怕原来做这个 milestone 的 worker 上下文还热着、就在 team 里。

**期望状态**：

orchestrator / worker 在处理 reviewer 反馈的 fix 时，能把三件**正交**的事各自判断、互不焊死：

1. **复用上下文** —— in-unit fix 默认优先唤醒原 milestone worker（它上下文/worktree 全热），而不是新派一个重爬背景；只有原 worker 已死 / fix 跨它没碰过的模块才新派，且新派的 worker 必须读全上下文。
2. **减流程仪式** —— fix 自包含、一步到位时，省掉为 milestone-sized 工作设计的三提交 / tasks.md / fix milestone 仪式；判据是"fix 是否自包含"，不是"改动行数多少"。
3. **架构治本** —— 无论谁修、走不走前两条，修复都落在根因所在的架构层治本，reviewer 给的最小路径只当现象线索；这条是底线，永不放松。

我作为协作者观察到的：fix 循环明显变快（worker 不再重复爬背景）、PR 里看不到"为消症状而贴的补丁"把架构弄乱、commit 历史是治本而非治标。

## 验收标准

### Requirement: fix 反馈循环优先复用已有上下文，不让 worker 重爬背景

#### Scenario: 原 worker 还在、fix 落在它做过的模块
- **GIVEN** reviewer 反馈一批 in-unit fix，对应 milestone 的 worker 实例还在 team 里
- **WHEN** orchestrator 派这批 fix
- **THEN** 它优先唤醒原 worker 续修（复用其上下文 / worktree），而不是新派一个从零读背景

#### Scenario: 原 worker 已死或 fix 跨它没碰过的模块
- **WHEN** orchestrator 需要派这批 fix 但原 worker 不可复用
- **THEN** 新派一个 worker，且该 worker 读全相关上下文后再动手，不因"这是 fix"就跳过阅读

### Requirement: 修 bug 按架构最合理的方式治本，不走最短路径

#### Scenario: 崩溃点在表层、根因在更下层
- **GIVEN** 一个 bug 崩溃点在某消费方，根因是更下层的契约 / 架构问题
- **WHEN** worker / orchestrator 定义并实施修复
- **THEN** 修复落在根因所在的架构层一次根治，而不是在崩溃点贴本地补丁绕过契约

#### Scenario: reviewer 在反馈里给了"最小路径"修法
- **WHEN** orchestrator 收到带"最小路径 / 改第 X 行"建议的 reviewer 反馈
- **THEN** 它把该建议当现象线索，自行判断根因层级与正确修复位置后再派，而不是原样转包最短路径

### Requirement: 减流程仪式的判据是 fix 是否自包含，不是改动大小

#### Scenario: 行为 / 契约类 fix，即使改动只有几行
- **WHEN** worker 修一个能被测试断言的逻辑 / 契约 / 数据流缺陷
- **THEN** 仍写红测试覆盖，不因"改动小"豁免

#### Scenario: typo / 样式 / 文案类改动
- **WHEN** worker 修一个本质写不出有意义断言的表层改动
- **THEN** 可省三提交 / 红测试等仪式，单 commit 完成

### Requirement: 三条轻量化维度各自独立判断、可叠加而不互相焊死

#### Scenario: 一个 fix 同时满足三维度
- **GIVEN** 一个 fix 既能复用原 worker、又自包含、根因也清楚
- **WHEN** orchestrator 处理它
- **THEN** 三条轻量化叠加生效（复用 worker + 省仪式 + 治本），互不绑死

#### Scenario: 改动小但根因触及架构契约
- **WHEN** 一个 fix 改动虽小，但根因触及架构契约
- **THEN** 它仍走架构治本，不因"改动小"被当纯 trivial 一省了之

## 范围与非目标

- 在范围：
  - 改 `change-orchestrator`（§6.FL 重组 + §6.2 研发视角定义 fix）、`change-impl-worker`（§FL 重组 + 红测试闸 + description）、`change-reviewer`（§FL 术语统一）三份 SKILL.md 的 fix 反馈循环描述
  - 把 feat-352 的 §FL 从"trivial / 改动小"判据重组为三条正交维度
  - 补「优先复用原 milestone worker」「架构治本不走最短路径」两条原本缺失的意识
  - feat-352 `design.md` 加 Changelog 一行追溯本次纠偏
- 非目标：
  - 不改 reviewer 给修法 / 最小路径的行为——那是 reviewer 的产品视角，允许保留
  - 不立 trivial 分级表 / 字段语义 / 数值阈值（沿用 feat-352 Q3：agent 自主判断走哪条）
  - 不引入新派发包字段 / 报告字段
  - 不升格成 orchestrator §0 硬规则（放 §6.FL 即可，约束级别保持轻）
  - 不动 §FL 之外的 orchestrator / worker 主流程，不动 `change-spec-author` / `change-design-author`
