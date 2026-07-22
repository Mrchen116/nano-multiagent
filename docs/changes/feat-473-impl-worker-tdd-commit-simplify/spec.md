# feat-473: impl-worker 保留 TDD、去掉三提交仪式

## Relations

- Related: feat-352, feat-389, feat-396

## 原始需求

> TDD还是重要的，但llm越来越强，可能不需要三提交了。你理解不

## 澄清记录

- Q1: Red 还硬不硬？三提交松掉后，是仍要求先写测试、亲眼看到红、再写实现，还是允许测试+实现同一次落地？
  A(原话): red也要。roadpoint还是一样的呀，没说要变啊。原来三提交要写commit id到文档的，现在不需要了。
  Agent 解读: 保留先红后绿；roadpoint 拆分与推进不变；progress 不再记 C1/C2/C3 多套 commit id。

- Q2: （复述确认）TDD 保留、三提交仪式去掉；roadpoint 不变；文档跟交付一起收口。
  A(原话): 对。现在复述一遍，我的思路 →（确认后）好，帮我改吧
  Agent 解读: 方向确认，进入改 skill / 文档。

- Q3: TDD 要不要写成 §0 硬规则里的「TDD 红绿不跳过」？
  A(原话): ## §0 不可越界的硬规则 不用强调。. **TDD 红绿不跳过**。这条删了。
  Agent 解读: TDD 留在执行流程（§5），不进 §0 硬规则清单。

- Q4: 文档里要不要用「纪律在红绿、不在拆几次 commit」这类对比旧仪式的说法？
  A(原话): “**纪律在红绿,不在拆几次 commit**—”，你不说不就行了。你不说，他完全不知道以前有三提交这个事情啊，简化描述
  Agent 解读: 只描述现状怎么做；不提、不对比已废除的三提交仪式。

## 用户场景

仓库协作者用 `change-orchestrator` 派 `change-impl-worker` 做 milestone。worker 仍按 roadpoint 推进：先写出能证明当前缺失能力的测试/验收并确认红，再写实现让它绿，门禁过了再提交、补 progress。

和以前不同的是：同一个 roadpoint 不必再拆成「测试 commit / 实现 commit / 文档 commit」三次；通常一次提交带走测试+实现+progress。progress 里只记本 roadpoint 的 commit hash，不再要求填三套 id。

撞到非平凡 bug 时，仍先走 `systematic-debugging` 根因纪律，再回到 worker 的红测→修复路径——措辞跟 worker 一致，不再绑「三提交 / C1」。

读 skill 的人（新 worker / 后人）只看到「按 roadpoint 做 TDD，通常一次提交」，不会被旧仪式名词绊住。

## 验收标准

### Requirement: roadpoint 仍走先红后绿

#### Scenario: 后端/API roadpoint
- **WHEN** worker 完成一个后端/API/纯逻辑 roadpoint
- **THEN** 该 roadpoint 曾先有失败测试（失败点对应当前缺失能力），再有实现使测试转绿
- **AND** 提交前相关测试门禁全绿

#### Scenario: 行为/契约类小修也不免红
- **WHEN** reviewer 反馈循环里的 fix 涉及逻辑 / 契约 / 数据流（能被测试断言）
- **THEN** worker 仍先写复现红测再修
- **AND** 仅 typo / 样式 / 文案等写不出有意义断言的改动可免红测

### Requirement: roadpoint 粒度与提交流程简化

#### Scenario: 同一 roadpoint 通常一次提交
- **WHEN** worker 完成一个普通 roadpoint（非需按需拆分的例外）
- **THEN** 测试、实现与 progress 更新通常落在同一次提交（或少量提交），不再按「测试 / 实现 / 文档」固定拆三次

#### Scenario: progress 只记本 roadpoint hash
- **WHEN** worker 补齐某 roadpoint 的 progress
- **THEN** Commits 字段记录本 roadpoint 的 hash 即可
- **AND** 不要求填写多套分阶段 commit id

#### Scenario: roadpoint 拆分方式不变
- **WHEN** worker 规划 milestone 的 tasks
- **THEN** 仍把 milestone 拆成若干可独立完成的 roadpoint（数量与退出节奏与既有约定一致）
- **AND** 不因提交流程简化而取消 roadpoint 或把整个 milestone 糊成一步

### Requirement: 流程文档只描述现状

#### Scenario: skill / 变更流程说明不提旧仪式
- **WHEN** 协作者阅读 `change-impl-worker`、`systematic-debugging` 以及 `docs/changes/readme.md` 中与 worker 执行相关的现行说明
- **THEN** 看到的是「按 roadpoint 做 TDD（先 Red/Verify 再 Green）」的现行做法
- **AND** 不出现需要读者先理解「以前三提交」才能读懂的对比表述

#### Scenario: TDD 不进 §0 硬规则清单
- **WHEN** 协作者阅读 `change-impl-worker` 的 §0 不可越界硬规则
- **THEN** 列表中没有单独的「TDD 红绿不跳过」硬规则条目
- **AND** TDD 红绿仍在执行循环（§5）中说明

### Requirement: 调试路径与 worker 对齐

#### Scenario: 根因确认后回到红测再修
- **WHEN** worker 在非平凡失败上走完 `systematic-debugging` 根因确认
- **THEN** 修复路径要求先写复现红测、确认红后再改实现
- **AND** 调试 skill 不另起一套与 worker 冲突的提交流程

## 范围与非目标

- 在范围：
  - `change-impl-worker` 现行执行约定（TDD / roadpoint / 提交与 progress）
  - `systematic-debugging` 中与 worker 衔接的措辞
  - `docs/changes/readme.md` 中阶段 3（实施）对 worker 的现行描述
- 非目标：
  - 不改 roadpoint 拆分哲学、测试门禁、真实入口验收、前端浏览器验收等其他质量手段
  - 不改 §FL 小修快车道的其余轻量化（复用上下文、可省 tasks 模板等）
  - 不回头改写 `docs/changes/archive/` 里历史 unit 文档
  - 不改变产品（IM / Gateway / CLI）用户可见行为
