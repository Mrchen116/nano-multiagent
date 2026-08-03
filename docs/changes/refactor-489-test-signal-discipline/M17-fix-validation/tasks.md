# refactor-489-M17: fix-validation — Tasks

> 对齐: ../design.md 的零产品行为约束，以及 verification.md 的 W1 / W2

## 目标

只关闭 verifier 报告中的两项发布阻塞 warning：让当前 CI 的 Ruff formatter gate 通过，并让 Gateway-IM resilience pytest 从仓库解释器启动时自行把该解释器目录传给 shell 脚本；不修改脚本、产品逻辑、spec 或 design。

## 退出标准

- [x] 只格式化 verifier 运行 `ruff format --check .` 报出的 20 个本 unit Python 测试文件，且全仓 formatter gate 通过。
- [x] resilience critical-path test 启动 `scripts/e2e-resilience.sh` 时把 `Path(sys.executable).parent` 前置到 `PATH`，不要求调用者手工修改 PATH。
- [x] verifier 指定的普通 PATH live 命令通过，并确认真 IM / Gateway 子进程与监听资源由测试清理。
- [ ] Python CI lane、文档完整性、Ruff lint/format 与 diff/scope 检查通过；无脚本或产品实现变更。

## 测试策略

- 被测行为（来自退出标准）：CI formatter gate 对当前 unit 的 Python 测试树全绿；resilience pytest 以仓库解释器启动时，脚本内裸 `python` / `python3` 解析到同一虚拟环境并完成两段真栈恢复旅程。
- 已有测试在：`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py`（扩展 subprocess harness）；不新建测试文件。
- 落层/目录/marker：`tests/e2e/critical_paths/`，marker：`e2e`；formatter gate 由 `.github/workflows/ci.yml` 的现有命令拥有。
- 可选依赖 importorskip：无新增；现有 live opt-in 与 main-config gate 保持不变。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：pytest `tmp_path` 下的 IM/Gateway config、日志、数据库与 workspace；结论和命令写入 `progress.md`，runtime 文件不提交。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| CI Ruff formatter gate | verifier 报出的 20 个 `tests/**/*.py` 文件 | keep | 只应用 Ruff 的机械格式化，不删除、不合并、不改变这些测试所保护的 seam；列表由修复前 `ruff format --check .` 固定 | `ruff format --check .` + complete Python CI lane |
| Gateway-IM 瞬态恢复的普通 PATH 可执行性 | `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults` | rewrite-merge | 风险和真进程旅程保留；只让 test harness 像 lifecycle E2E 一样把 active interpreter 目录传给子进程，不改脚本或产品 | verifier 指定的普通 PATH live command |

## Roadpoints

### R1 — 固定 verifier 基线并关闭 W1

- 状态: DONE
- 步骤: 在 `pre_fix_head=ac281030314477c44098d5888506674236a83e5e` 重现 formatter warning；仅格式化该次输出的 20 个文件并复查语义 diff。
- 验证: `ruff format --check .`，以及 Python CI lane。

### R2 — 关闭 W2 的 subprocess PATH 缺口

- 状态: DONE
- 步骤: 在 resilience test 构造继承环境，并把 `Path(sys.executable).parent` 前置到 PATH 后传给 `Popen`；不修改 `scripts/e2e-resilience.sh`。
- 验证: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py::test_gateway_recovers_node_online_after_transient_faults`。

### R3 — final sync、完整门禁与交付

- 状态: IN PROGRESS
- 步骤: 同步最新 `unit/refactor-489` 后重跑 W1/W2 和 CI 等价门禁，审计 diff/runtime residue，再合入并推送 unit branch。
- 验证: docs-check、Ruff lint/format、完整 non-E2E pytest、live resilience、`git diff --check` 与 changed-path audit。
