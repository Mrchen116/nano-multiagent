# refactor-489-M1 — Progress

## R1 — 固化唯一处置规范

- 状态: DONE
- Context: 既有规范只要求实现路径变化后回看旧测试，没有定义影响边界、三种处置和删除前提，worker 无法留下可复核的一致结论。
- Decision: 在 `docs/development/testing.md` 的停止条件下增加“受影响的既有测试”小节，并把实际记录格式纳入原有 `tasks.md` 测试策略模板。
- Rationale: 测试规范是测试选择的唯一 owner；skill 只需路由和执行动作，避免三处各自维护完整判据。
- Evidence:
  - Tests: 修改前结构检查显示 `keep`、`rewrite-merge`、`delete`、非全仓台账和精确文本边界均缺失；修改后待 R3 统一校验。
  - Entry: 从 `docs/README.md` → `docs/development/README.md` → `testing.md` 可进入完整处置规则；本 milestone 无产品运行入口。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面文档改动）。
  - E2E/Regression: N/A（不为文档措辞新增永久回归测试）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `cfa2bdb7f`。
- Commits: `bc1055d56`。
- Next: R2 将规范接入 worker 规划、执行与实际任务模板。

## R2 — 接入 worker 与实际模板

- 状态: DONE
- Context: testing owner 已有完整判据，但 worker 的规划、执行与完成条件尚未消费它，实际复制的模板也没有处置表。
- Decision: 在 skill 的上下文结论、规划输入、roadpoint 执行、集成前检查和输出契约中接入处置动作；在 `assets/tasks.md` 加入五列处置表及“无受影响覆盖”的填写方式。
- Rationale: skill 只保留触发、动作和完成条件，具体 keep/rewrite-merge/delete 判据继续由 `testing.md` 单点维护；模板承载实际交付数据。
- Evidence:
  - Tests: 修改前结构检查确认 skill 与模板均缺少 `rewrite-merge`、五列表头和非全仓边界；修改后 `quick_validate.py` 报告 `Skill is valid!`，结构搜索命中 skill 的规划/执行要求和模板五列表头，`scripts/docs_check.py` 通过（190 sources / 65 routes）。
  - Entry: worker 从 §2.3 识别受影响覆盖，§3 填模板，§5 执行处置，§6/§10 检查闭环，路由完整。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面 skill/template 改动）。
  - E2E/Regression: N/A（结构校验足以证明本次交付格式，不把文档句子固化为永久测试）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退提交 `bc1055d56`，不影响 R1 的 canonical 规范。
- Commits: 本 roadpoint 提交（最终 hash 在 R3 汇总）。
- Next: R3 做去重审读，并运行 skill、文档和 workflow contract 校验。

## R3 — 校验格式、路由与去重

- 状态: DOING

## Promotion Candidates

None.
