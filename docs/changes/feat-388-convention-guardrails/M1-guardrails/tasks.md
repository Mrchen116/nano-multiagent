# feat-388-M1: guardrails — Tasks

> 对齐: ../design.md v2

## 目标

把项目现有散文规范固化为机器执行的硬约束，搭通用执行底座 + 首批规则：
1. ruff 配置写入 pyproject.toml（B-1/B-2 真源）
2. 全仓存量违规一次性清掉（独立机械 commit）
3. 契约测试改写对齐 refactor-387（R1/R2/R3 已在 design 确认状态）
4. PostToolUse hook（触点 a）：编码循环内即时 autofix/回喂
5. GitHub Actions CI（触点 c）：push/PR 时前后端双门兜底

## 退出标准

- [ ] `ruff check .` 全绿（select=F,B006,E722；不含 B008）
- [ ] `ruff format --check .` 全绿
- [ ] `pytest -m "not e2e"` 全绿（含 R1/R2/R3 契约测试）
- [ ] PostToolUse hook 实测：编辑含 F401 的 src/ 文件 → 自动清除；加 import agent.core → exit 2 阻断
- [ ] `stop-require-explicit-ok.py` 自门控：普通会话正常停止；orchestrator 受管会话 gate 行为不变
- [ ] `.github/workflows/ci.yml`：`python` job（ruff+pytest）+ `frontend` job（vitest）两个并行 job 结构正确
- [ ] 前端基线确认：`cd src/IM/frontend && npm run test` 全绿
- [ ] 机械重排为独立 commit
- [ ] 无 baseline/xfail 永久豁免残留

## 测试策略

- 被测行为：ruff 配置生效、契约测试 R1/R2/R3 通过、hook 对 src/*.py 自动修/回喂、CI yaml 结构正确
- 已有测试在：`tests/contract/test_cli_http_only_contract.py`（R1/R2 已是新语义）、`tests/contract/test_core_no_platform_imports.py`（R3 已是正向）
- 落层/目录/marker：tests/contract/（已有），无新 e2e marker
- 可选依赖 importorskip：无
- 一次性验收证据：hook 实测输出（exit code 截图/log）/ 非前端写 N/A

UI 状态矩阵：N/A（本 milestone 无前端改动）

## Roadpoints

### R1 — pyproject.toml 加 ruff 配置

- 状态: DONE
- 步骤: 在 pyproject.toml 加 [tool.ruff] + [tool.ruff.lint] 段；dev 依赖加 ruff==0.15.*
- 验证: `ruff --version` 检查；`ruff check --select F,B006,E722 --ignore B008 .` 能运行（即配置有效）

### R2 — 全仓存量违规清理（独立机械 commit）

- 状态: DONE
- 步骤: `ruff format .`（全仓重排）+ `ruff check --fix .`（自动修 correctness）；剩余不可自动修项手动修
- 验证: `ruff format --check .` 全绿；`ruff check .` 全绿

### R3 — 契约测试复核（R1/R2/R3 状态确认）

- 状态: DONE
- 步骤: 复核 test_cli_http_only_contract.py 和 test_core_no_platform_imports.py 现状；确认 #39 xfail 已去除
- 验证: `pytest tests/contract/ -m "not e2e" -q` 全绿

### R4 — stop-require-explicit-ok.py 自门控改造

- 状态: DONE
- 步骤: 改写 hook：仅当 session 在 active-subagents.json 中有登记才进 gate；普通会话直接 exit 0
- 验证: 手动测试（构造无登记 session 确认 exit 0）；代码逻辑 review

### R5 — ruff-guardrail.py PostToolUse hook

- 状态: DONE
- 步骤: 新建 .claude/hooks/ruff-guardrail.py；读 stdin JSON 取 file_path；仅处理 src/|tests/ 下 .py；ruff format + ruff check --fix；余下违规 exit 2；src/ 下文件跑边界契约测试；更新 .claude/settings.json 加 PostToolUse + disableAllHooks: false
- 验证: 实测编辑含 F401 的 src/ 文件自动清除；加 import agent.core exit 2 回喂

### R6 — GitHub Actions CI

- 状态: DONE
- 步骤: 新建 .github/workflows/ci.yml；python job（py3.11 + ruff + pytest）+ frontend job（Node 20 + vitest）并行
- 验证: yaml lint 检查；CI 结构 review（前端 job 不跑 npm run build）
