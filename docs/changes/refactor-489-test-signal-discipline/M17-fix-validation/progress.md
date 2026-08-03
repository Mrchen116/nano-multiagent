# refactor-489-M17 — Progress

## Baseline / Audit

- Claim: verifier W1 与 W2 均可在报告 commit 上独立复现，且修复范围可限制为 formatter 报出的 20 个测试文件与 resilience pytest harness。
- Baseline: verifier validated head `e8f31eb47fa1c75183868cf92591173ea82a7d85`；verification report / `pre_fix_head` `ac281030314477c44098d5888506674236a83e5e`；branch `milestone/refactor-489-M17-fix-validation`。
- Method: 完整读取 motivation/design、仓库测试/evidence/worktree runtime/E2E catalog 规范、verification.md、CI workflow、resilience test/script 与 lifecycle reference；随后在未修改 worktree 上运行 verifier 的两条失败路径。
- Result:
  - W1 reproduced: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check .` exit 1，报告 20 个 `tests/**/*.py` 文件需要格式化，792 个文件已格式化。
  - W2 reproduced: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults` exit 1；shell 的 bare `python3` 解析到普通 PATH，config setup 报 `ModuleNotFoundError: No module named 'yaml'`。
- Locator: verifier issue definitions在 `verification.md`；W2 失败发生于 `test_gateway_im_resilience_critical_path.py` 启动的 `scripts/e2e-resilience.sh` 配置派生阶段；参考实现为 `test_worktree_stack_lifecycle_e2e.py` 的 active-interpreter PATH。
- Limit: 基线在 YAML config 派生前即失败，因此不证明两段 Gateway-IM 恢复旅程；修复后必须用同一普通 PATH 命令真跑。W1 的 20 文件列表以本次 Ruff 输出为唯一格式化范围。

## R1 — 固定 verifier 基线并关闭 W1

- 状态: DONE
- Context: CI 明确执行 `ruff format --check .`，当前 unit 的 20 个 Python 测试文件产生真实红灯。
- Decision: 只对基线输出的精确 20 文件列表运行 `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format <paths...>`；未向命令加入其他文件，也未改测试断言。
- Rationale: 机械收敛到 CI 的当前可执行规则即可关闭 W1，同时避免把修复 lane 扩成无关格式整理。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff format --check .` PASS，`812 files already formatted`；`git diff --check` PASS。
  - Entry: `.github/workflows/ci.yml` 的现有 `ruff format --check .` 命令原样运行；无需修改 workflow。
  - Frontend State Matrix: N/A（Python 测试机械格式化）。
  - Browser QA: N/A。
  - E2E/Regression: N/A；格式化不改变测试 seam，完整 Python lane 在 R3 运行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 的纯格式化 commit。
- Commits: `7c7143737`。

## R2 — 关闭 W2 的 subprocess PATH 缺口

- 状态: DONE
- Context: resilience pytest 虽由仓库 venv interpreter 启动，但其 `Popen` 继承调用 shell 的普通 PATH；脚本内 bare `python3` 因而落到系统解释器并缺少 PyYAML。相邻 lifecycle E2E 已通过 active-interpreter PATH 解决同一 harness 边界。
- Decision: 在 `_run_resilience_script` 中复制当前环境，用 `os.pathsep` 把 `Path(sys.executable).parent` 前置到 PATH，并把该环境传给 `Popen`；live gate、command、timeout、process-group cleanup 与 `scripts/e2e-resilience.sh` 均不变。
- Rationale: pytest 启动的真栈子进程应使用 pytest 自己的已安装环境；由 test harness 明确传递解释器目录能消除调用者手工 export 前置条件，又不把环境选择写进产品/运维脚本逻辑。
- Evidence:
  - Tests: ordinary shell PATH 下运行 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults` PASS，`1 passed in 23.56s`。
  - Entry: pytest 仍直接驱动 `scripts/e2e-resilience.sh`；脚本完成 Scenario A（IM restart 后自动 online）与 Scenario B（Gateway 先起、IM 后起 online），并返回现有 `RESILIENCE E2E PASS` marker。
  - Frontend State Matrix: N/A（Gateway/IM 进程韧性）。
  - Browser QA: N/A。
  - E2E/Regression: 同上 live critical-path node；没有手工 PATH prefix。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Cleanup: pytest tmp `pytest-164/test_gateway_recovers_node_onl0` 无 `.im.pid` / `.gateway.pid`，派生 IM port `54608` 无 listener；进程扫描无该运行的 IM/Gateway 残留。
- Rollback: 回退本 roadpoint commit，恢复 verifier W2 的调用者 PATH 依赖；无产品数据迁移。
- Commits: `7db6c3fa1`。

## R3 — final sync、完整门禁与交付

- 状态: DONE
- Context: W1/W2 定向验证通过后，需要在最新 unit 基线上证明完整 Python CI lane 没有被 20 个格式化 diff 或 test-harness 环境改动破坏。
- Decision: `git fetch origin --prune` 后确认 `origin/unit/refactor-489` 仍为 dispatch/report commit `ac2810303`，milestone 无需吸收新 delta；按 `.github/workflows/ci.yml` 原样运行 Python job 的四个 gate，并复核 `pre_fix_head..HEAD` 范围。
- Rationale: formatter warning 必须与完整 Python lane 一起关闭；在 executed base 未变化且最后一个代码 commit 已固定后运行，证据同时绑定 W1/W2 的实际实现。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e" -n 4 --dist worksteal --durations=20 --durations-min=0.5` PASS，`2836 passed, 22 warnings in 38.30s`。
  - Quality: `scripts/docs_check.py` PASS（223 maintained Markdown sources / 65 required routes）；`ruff check .` PASS；`ruff format --check .` PASS（812 files）；`git diff --check` PASS。
  - Entry: W2 的 real-process critical node 继续由 `scripts/e2e-resilience.sh` 的公开入口完成两段恢复旅程；W1 直接使用 CI workflow 中未修改的 formatter command。
  - Frontend State Matrix: N/A（无 frontend/product delta）。
  - Browser QA: N/A。
  - E2E/Regression: ordinary PATH live resilience `1 passed in 23.56s`；complete non-E2E lane 2,836 tests 全绿。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Scope: `ac2810303..HEAD` 只含 M17 tasks/progress、verifier 报出的 20 个 Python test formatting paths，以及一个 resilience pytest harness；`.github/workflows/ci.yml`、`scripts/e2e-resilience.sh`、product `src/`、spec/design 均未修改。
  - Final sync: `origin/unit/refactor-489@ac2810303` 与 dispatch base 一致，无 rebase delta；final milestone head 提交后再次运行这些 gate，以最终 HEAD 为 `validated_at`。
- Rollback: 回退 `7db6c3fa1` 恢复旧 test harness；回退 `7c7143737` 恢复 formatter 前测试文本。两者均无产品数据或 schema 迁移。
- Commits: `7c7143737`（W1）、`7db6c3fa1`（W2）、本 progress closure commit（SHA 以 Git history 为准）。

## Promotion Candidates

None.
