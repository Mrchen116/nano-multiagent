# feat-392-M1 — Progress

> 本 milestone 产物是文档 + skill 文本(meta unit),无运行时代码改动。每个 roadpoint 的"真实入口验证"
> = 拿契约层每条 Requirement/Scenario 对照 `tests/contract/` + `src/agent/sdk/kernel.py` 逐条核对(料源 ①②)。

## R1 — docs/SPEC_GUIDE.md 文档规范

- Context: SDD 长青文档体系的地基。先定"放什么/不放什么 + 骨架",后续 kernel 契约层(R2)
  和 M2-M4 三包才有统一规范可照,否则回填进烂结构=重新 rot(spec.md 澄清 Q3)。
- Decision: 新建 `docs/SPEC_GUIDE.md`,含六块:① 判据两问(稳定 + 不可廉价重建);② 不进 spec
  的分流表(实现→代码/决策→design.md/how-to→AGENTS·runbook/跨包→SPEC.md/瞬态→changes·issue);
  ③ 契约层文件骨架(`# <包> Specification` → `> 对齐:` 行 → `## Purpose` → `## Requirements`
  含 `### Requirement:` + `#### Scenario:` GIVEN/WHEN/THEN);④ 库/内核契约写法纪律
  (照 research §7.5:WHEN/THEN 主语=消费者、每 Req 一份 pre→post 契约或 invariant、CDC 裁剪、
  spec-anchored);⑤ 收尾归并 checklist(orchestrator 提 PR 前直接编辑 canonical + bump 对齐行
  + 软对账,无 delta 工件);⑥ 读侧 grounding checklist(spec 阶段读契约层取词汇、design 阶段
  对代码 grounding 报不一致);⑦ 迁移料源优先级(tests/contract → 代码 → 旧文档仅备忘)。
- Rationale: 严格遵循 design 决策 4——契约层保持纯 `Purpose + Requirement/Scenario`,**无**
  `覆盖:` 行 / `[可执行]`·`[行为]` 标签 / freshness 测试;drift 走软对账(follow OpenSpec)。
  research §10 曾主张 RTM 内联 `覆盖:`+freshness 硬卡,但 design 决策 4 明确否决——以 design 为准,
  GUIDE 里明文写"不写覆盖行、不建 freshness 测试"。
- Evidence:
  - Tests: N/A(纯文档,无可断言行为;决策 4 否决 freshness 测试)。本 unit 收尾复跑全树确认不破坏。
  - Entry: 自审对照 spec.md 验收 Requirement「文档规范 GUIDE 定义放什么/不放什么 + 骨架」的
    Scenario「作者按规范判断内容归属」——GUIDE 给出判据(两问)、契约层骨架、分流表,三要素齐 ✓。
  - Frontend State Matrix: N/A(无界面)
  - Browser QA: N/A
  - E2E/Regression: N/A — 决策 4 走软对账,不做机械绑定/freshness,无回归用例可落。
  - Visual/Interaction: N/A
- Rollback: 纯新增文件,`git rm docs/SPEC_GUIDE.md` 即回退。
- Commits: 见 git log(R1 单 commit,文档规范类无可断言红测试,省独立 C1,理由见 §FL②红测试豁免)。

## R2 — docs/specs/kernel/spec.md 内核契约层

<!-- 待填 -->

## R3 — 顶点 SPEC.md 重定位 + AGENTS.md 索引 + 退役旧内核 SPEC

<!-- 待填 -->

## R4 — change-* skill 接入读写闭环

<!-- 待填 -->
