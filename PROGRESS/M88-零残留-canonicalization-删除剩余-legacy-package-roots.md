# PROGRESS (Milestone: M88)

- Milestone: M88
- Title: 零残留 canonicalization：删除剩余 legacy package roots
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M88`
- Branch: `milestone/M88`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `python3 -m pytest -q` 当前红灯（9 failed, 596 passed, 4 skipped）；失败集中在 `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 仍引用已移除的 `nano_multiagent.cli.app|events|input` layered legacy paths，属于 M88 scope（authoritative base: `origin/main` commit `d912bb7`）
- Notes:
  - 目标是物理零残留，不接受最小 shim 留存。
  - source/tests/docs 需要一起改向 `core/platform/products/apps` canonical homes；README / architecture / SPEC 与 acceptance contract 必须同步收口。

## Roadpoints

### R88.1 zero-residue contract 先红
- Context:
  - 待补充。
- Decision:
  - 待补充。
- Rationale:
  - 待补充。
- Evidence:
  - 待补充。
- Rollback:
  - 最近稳定点：`d912bb7`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 先把 acceptance/location/import guard 改到零残留口径并取红测证据。

### R88.2 迁移 source/tests/docs 并物理删除 legacy roots
- Context:
  - 待补充。
- Decision:
  - 待补充。
- Rationale:
  - 待补充。
- Evidence:
  - 待补充。
- Rollback:
  - 最近稳定点：`TBD`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 完成 focused green 后再跑 full sweep。

### R88.3 full sweep、live 验证、main 集成与清理
- Context:
  - 待补充。
- Decision:
  - 待补充。
- Rationale:
  - 待补充。
- Evidence:
  - 待补充。
- Rollback:
  - 最近稳定点：`TBD`
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - full sweep + live + merge + board + cleanup。
