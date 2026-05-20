# M1: triage-and-layer — Tasks

## 目标

对 `pytest -m "not e2e"` 的失败（基线 164 failed）进行正确分层 + 测量，产出 triage 报告供人审，不动产品代码、不删测试。

## 退出标准

- `pytest -m "not e2e" --co` 不再收集任何 `tests/e2e/` 用例（e2e 路径自动 marker 生效）
- pytest-cov 装好，覆盖率可跑出（`pytest --cov=src --cov-report=term-missing -m "not e2e"` 不报 missing plugin）
- `docs/changes/refactor-372-test-suite-health/regression.md` 产出，包含：
  - 总览（标记前/后失败数、四类计数）
  - 逐条清单（路径::用例 | 分类 | 证据 | M2 动作 | issue#）
  - 结构问题盘点（流水号命名/巨型文件/一次性快照/跨层重复）
- [reviewer] regression.md 可读、分类有据、可据此决定 M2

## 测试策略

- 被测行为（来自退出标准）：
  1. e2e 路径自动 marker：`pytest -m "not e2e" --co` 不收集 `tests/e2e/` 任何用例
  2. pytest-cov 可用：`pytest --cov=src -m "not e2e" -q` 不报 no module named pytest_cov
- 已有测试在：无（测试基础设施改动，写验证脚本确认结果，不新建永久回归测试文件）
- 落层/目录/marker：本 M1 不写回归测试，产出是 regression.md 报告 + 基础设施改动
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无脚本；验收通过命令直接验证

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 加 e2e 路径自动 marker（conftest） | TODO |
| R2 | 加 pytest-cov 进 [dev] | TODO |
| R3 | 跑带 marker 后的 not-e2e 基线，收集残余失败列表 | TODO |
| R4 | 逐条分类残余失败（四类 + 证据 + M2 动作） | TODO |
| R5 | 盘点结构问题（流水号/巨型文件/快照/跨层重复） | TODO |
| R6 | 产出 regression.md + 真回归立 issue | TODO |
