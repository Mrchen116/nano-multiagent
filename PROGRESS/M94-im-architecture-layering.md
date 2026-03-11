# M94 - IM 分层架构迁移

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

## Baseline
- Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M94 && PYTHONPATH=src pytest -q tests/im_service`
- Result: 23 passed
- Notes:
  - 当前 IM 后端仍是扁平结构：`app.py` 同时承载 DTO、路由、装配；`models.py` 与 `repositories.py` 在顶层。
  - 现有测试全绿，迁移必须以“结构收敛、不改外部 HTTP 契约”为第一目标。

### R1 规划与分层骨架落位
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 domain models 扩展并对齐 IM-SPEC
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R3 清理旧路径并收口 canonical imports
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
