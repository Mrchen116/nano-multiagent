# M92 Product 目录结构对齐

## Milestone Notes
- 先对齐 `SPEC.md` 与 `docs/内核设计SPEC.md` 中 `products/<product>/tools|hooks|skills` 目标态，再收敛加载器。
- 测试避免写死 hooks 总量，优先断言关键模块/来源/路径存在，遵守 `LOGBOOK.md` 规则。
- 涉及 legacy 路径/负向断言时，改动后需复查 contract tests，避免批量替换误伤。

### R92.1 产品目录目标态与 profile/hook 默认声明对齐
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M92 && PYTHONPATH=src pytest -q`
  - Entry:
- Rollback:
- Commits: C1=<...>, C2=<...>, C3=<...>
- Next:

### R92.2 四层 tools/hooks/skills 加载路径可验证
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M92 && PYTHONPATH=src pytest -q`
  - Entry:
- Rollback:
- Commits: C1=<...>, C2=<...>, C3=<...>
- Next:
