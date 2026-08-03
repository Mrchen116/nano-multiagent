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
- Commits: `49ebf276a`。
- Next: R3 做去重审读，并运行 skill、文档和 workflow contract 校验。

## R3 — 校验格式、路由与去重

- 状态: DONE
- Context: 需要确认三处内容既能形成可执行闭环，又没有把完整处置判据复制进 skill/template 或越出 milestone 范围。
- Decision: 保留 `testing.md` 为唯一判据 owner；skill 只写识别、规划、执行和完成检查；模板只提供五列表格与“无覆盖”的填写方式。
- Rationale: 这种分工让未来判据只改一处，同时保证 worker 实际产物不会漏掉既有测试处置。
- Evidence:
  - Claim: M1 规范、skill 路由和任务模板格式有效，且既有 change workflow contract 未漂移。
  - Baseline: `origin/unit/refactor-489@0b9607147`，验证前 milestone HEAD `49ebf276a`。
  - Method: 运行 skill `quick_validate.py`、`scripts/docs_check.py`、`pytest -q tests/contract/test_change_workflow_documentation_contract.py`、跨文件结构搜索、`git diff --check origin/unit/refactor-489...HEAD` 和 changed-path scope 检查。
  - Result: PASS；skill valid；文档完整性通过（190 sources / 65 routes）；contract `3 passed`；完整删除/精确文本判据只命中 `testing.md`；changed paths 仅为三处派发文件与 M1 交付物。
  - Locator: `docs/development/testing.md`“受影响的既有测试是持续维护资产”、`change-impl-worker` §2.3/§3/§5/§6/§10、`assets/tasks.md`“受影响的既有测试处置”。
  - Limit: 零用户面，无浏览器或 live runtime 验证；本轮不评估 M2--M16 的具体测试处置。
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_change_workflow_documentation_contract.py` → `3 passed`。
  - Entry: `docs/README.md` → `docs/development/README.md` → `testing.md` 的 current 路由有效；worker 从读取规范到模板、执行和交付检查的内部路由完整。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: N/A（无产品或运行时行为）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 分别回退 `49ebf276a`（skill/template 接入）与 `bc1055d56`（canonical 规范）。
- Commits: 本收尾提交，SHA 以 Git history 为准。
- Next: M1 完成，合入 `unit/refactor-489` 后可解锁 M2--M16。

## Promotion Candidates

None.
