# feat-532-M0 — Progress

## Baseline

- Claim: feat-532 M0 从未修改的 unit branch 开始，现有共享 suite 可作为绿色基线。
- Baseline: `unit/feat-532` at `29e8a8d1a743c4df5dd972f6efacf2bbe3451586`。
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q evals/spec_design_alignment/base_repo/tests`; `.../python evals/spec_design_alignment/validate_dataset.py`; `.../python scripts/docs_check.py`。
- Result: pass；10 tests passed，validator 与 docs-check 零错误退出。
- Locator: 本 milestone plan 前的 worker command output。
- Limit: 尚未包含 feat-532 overlay 或任何真实 Codex pilot。

## R1 — Overlay 契约与确定性控制面

- Context: feat-397 的 H02 base 可复用，但它的 workflow/终点是 spec+design；M0 必须另建 spec-only overlay，并先把 provisional context、whole-lineage corpus exclusion、唯一 Skill closure、neutral repo 和封存身份变成可执行契约。
- Decision: 新建 feat-532 独立 overlay；复用共享 H02 materializer 后重写为无父历史 neutral/candidate projection，Candidate 只保留 `.agents/skills/change-spec-author`；匿名 corpus 用固定 seed 重排并只给 builder 暴露 opaque document/source locator，private receipt 单独保存真实来源；owner/judge context 使用不同 schema，所有资产固定 `formal_eligible=false`。
- Rationale: 共享 case/base 继续是单一事实来源，但 feat-397 protocol/dataset 零改动；投影和 hash 由 Python 控制面生成，不依赖 Agent 自觉隔离。
- Debug evidence: 首次真实 prepare 看似长期无输出；按 `systematic-debugging` 分层检查后，采样显示进程仍在共享 materializer 内持续 fork Git、对象数增长且 CPU 活跃。根因是正式 H02 物化要为约 4.5k 文件建立 byte-canonical Git objects，而最初基线的 10 个测试只使用小 fixture；并发启动的 pytest 又被 90 秒门禁中断后留下子进程，放大了“挂死”表象。物化完成后又准确暴露两份 legacy archive 没有当前四类首文档；根因是 corpus 枚举把旧 archive 目录误当成现行 change unit。新增红测后改为跳过无首文档 legacy 目录、仍对多个首文档 fail closed。没有增加 timeout/retry 或修改共享 materializer；永久测试改为最低层的快速投影契约，正式重物化留给一次 live/replay 证据。
- Evidence:
  - Tests: Red 为 runner 缺失导致 2 failed；Green 为 overlay 3 tests + shared base 10 tests，共 13 passed in 7.75s；共享 dataset validator 零错误退出；Ruff 与 `git diff --check` 通过。
  - Entry: `runner.py prepare` 是确定性 CLI 入口；正式 H02 重物化和封存由 R4 live/replay 执行，R1 不把重外部依赖伪装成日常 unit test。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `evals/spec_design_alignment/experiments/feat_532_spec_memory/tests/test_pilot_control_plane.py` 保护 anonymous whole-lineage projection、single-Skill/parentless candidate projection 和 provisional schema/结论边界；真实 LLM E2E 由 R2-R4 durable pilot evidence 承担。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert R1 commit；共享 feat-397 资产未修改。
- Commits: R1 commit（本段同 commit）。
- Next: 实现 manifest-driven Codex adapter、一次 Memory build、direct-load consumption 与双 arm Candidate/Owner 持久会话。

## Promotion Candidates

None.
