# feat-396-M1: impl — Tasks

> 对齐: ../design.md v1

## 目标

skill 体系里出现可 invoke 的 `systematic-debugging` 技法 skill(中文,4 阶段根因纪律 + Red Flags + 3-strike + 3 子技法),并在 worker / spec-author 两处接上 call-in、在 reviewer 处声明不接入;现有散落的调试碎片收敛到新 skill,无两套打架的说法。

## 退出标准

- [x] `.claude/skills/systematic-debugging/SKILL.md` 存在,中文,含 根因铁律 + 4 阶段 + Red Flags + 3-strike
- [x] `references/` 含三子技法 `root-cause-tracing.md` / `defense-in-depth.md` / `condition-based-waiting.md`,SKILL.md 在对应步骤按需引
- [x] worker §0.12 新增硬规则 + §7.2 展开 invoke + §7.3 并列说明(6 次数值不动)
- [x] spec-author §4 RCA call-in 就位,明标「只调查不修」
- [x] reviewer §0.8 「不接入」声明就位
- [x] 自洽:引用名与 skill `name` 一致;3-vs-6 有并列说明;未重复三提交流程;orchestrator/verifier 未动

## 测试策略

> 本 milestone 产出全为 `.claude/skills/` 下的 markdown(skill prompt + 方法论文档),**无可断言的代码行为**——按 `docs/TESTING_GUIDE.md` 与 worker §FL,prompt/文案类本质写不出有意义断言,**免 C1 红测**。验收 = 文档存在性 + 自洽性(自审 + 下游 verifier 读文档核对 spec 5 条 Requirement)。

- 被测行为:无(纯方法论文档,无运行时入口)。
- 已有测试:N/A —— 不新建测试文件(无可测断言)。
- 落层/目录/marker:N/A。
- 可选依赖 importorskip:无。
- 一次性验收证据:`grep` 核对 4 处 call-in 引用名与 skill name 一致(见 progress.md Evidence),不进套件。
- 前端:N/A(无 UI)。

## Roadpoints

### R1 — 新建 systematic-debugging skill(SKILL.md + 3 子技法)

- 步骤:写 `.claude/skills/systematic-debugging/SKILL.md`(铁律 + 4 阶段 + 3-strike + Red Flags + 子技法索引);写 `references/` 三子技法(中文,例子换 Python/pytest 语境,忠实改写 superpowers 原文)。
- 验证:文件存在;通读中文无英文残留;SKILL.md 在 阶段1.5/4.4/4.5 处分别引到三个 references 文件。
- 状态:DONE

### R2 — 接 call-in + 收敛重复

- 步骤:worker §0.12 + §7.2 + §7.3;spec-author §4 RCA;reviewer §0.8 不接入。
- 验证:`grep "systematic-debugging"` 命中 worker(3 处)+ spec-author(1 处)+ reviewer(1 处);引用名一致;§7.3 仍写「6 次」且新增 3-vs-6 并列说明;orchestrator/verifier 无改动。
- 状态:DONE
