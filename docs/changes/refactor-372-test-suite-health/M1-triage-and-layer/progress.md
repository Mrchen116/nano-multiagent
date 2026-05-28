# M1: triage-and-layer — Progress

基线（2026-05-20）：`pytest -m "not e2e"` → 164 failed / 2015 passed / 4 deselected / 220 warnings（168s）。
比 motivation.md 记载的 161 多 3，可能是近期新增的失败；以本次实测 164 为准。

---

### R1 — e2e 路径自动 marker

- Context: `pytest -m "not e2e"` 在标记前误收集 47 个 `tests/e2e/` 用例（只有 4/29 个文件手写了 marker），导致需要真实进程的测试在基线里失败。
- Decision: 在 `tests/e2e/conftest.py` 追加 `pytest_collection_modifyitems` hook，对路径含 `tests/e2e/` 的 item 自动添加 `e2e` marker。
- Rationale: design.md 决策 1 选定此方案；单点修改，新增 e2e 文件天然被覆盖，不会再漏标。
- Evidence:
  - Tests: `pytest -m "not e2e" --co -q | grep "tests/e2e/"` → 0（修前 47）
  - Entry: 不涉及产品入口
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（本身是测试基础设施）
  - Visual/Interaction: N/A
- Rollback: 删掉 `tests/e2e/conftest.py` 新增的 `pytest_collection_modifyitems` 函数即恢复原状。
- Commits: C1=9529755b（verify：47 个 e2e 被误收集），C2=396ad8ad（feat：自动 marker）

### R2 — pytest-cov 进 [dev]

- Context: 删除测试候选需要覆盖率证据（design.md 决策 4），但 pytest-cov 未在 dev 依赖中。
- Decision: 在 `pyproject.toml [project.optional-dependencies].dev` 加 `pytest-cov>=5.0,<7.0`。
- Rationale: 标准工具，pytest 原生集成，一行改动。
- Evidence:
  - Tests: `pytest --cov=src --cov-report=term-missing -m "not e2e" -q` 不报 missing plugin，正常输出覆盖率。
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 删 `pyproject.toml` 中 pytest-cov 那行
- Commits: C2=b4648987

### R3 — 跑带 marker 后基线，收集残余失败列表

- Context: e2e marker 生效后重跑，145 failed（原 164，移除 19 个 e2e 误跑失败）。
- Decision: 用 `pytest -m "not e2e" -q --tb=line 2>&1 | grep "^FAILED"` 收集完整 145 条失败列表。
- Rationale: 为 R4 分类提供精确基础。
- Evidence:
  - Tests: 145 failed / 1987 passed / 51 deselected（81s）
  - Entry: N/A（测量步骤）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: N/A（只是测量）

### R4-R6 — 分类 + 结构盘点 + regression.md

- Context: 145 个残余失败全部经人工核实错误详情 + 产品代码交叉验证。
- Decision: 归类为：过期预期 128 个、真回归 1 个（#37）、一次性快照 3 个、环境干扰 1 个；同时盘点结构问题（17 个 >400 行文件、9 个流水号命名文件、2 个一次性快照文件）。
- Rationale: 每类代表样本都做了产品代码交叉核实，确认是测试漂移还是产品错误。
- Evidence:
  - Tests: regression.md 已产出，包含逐条清单 + M2 动作建议
  - Entry: 真回归 #37 已立 gh issue，idempotency_key 失效经独立 Python 脚本验证确认
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（M1 不动测试，M2 据 regression.md 执行）
  - Visual/Interaction: N/A
- Rollback: N/A（只产出报告文件）
- Next: M1 完成，等待人审 regression.md 后进 M2。
