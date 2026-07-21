# bugfix-471-M1 — Progress

## 启动记录

- 已读 `incident.md`、`design.md`、项目规则、`docs/TESTING_GUIDE.md`、现有 Kernel/Gateway/session/scheduler 实现与测试。
- 基线：`PYTHONPATH=src pytest -m 'not e2e'` — 3628 passed，1 skipped，20 deselected（2026-07-21）。
- 本 milestone 不修改前端、IM timeline 或 divider；M2 负责这些可见缓存边界。
