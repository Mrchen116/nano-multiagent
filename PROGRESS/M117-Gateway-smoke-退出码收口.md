# M117 Gateway smoke 退出码收口

## 前置确认
- 已先阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 约束：仅处理 smoke runtime / gateway 正常关闭语义；不改 `ROADMAP.md`；不手改 `data/dev-tasks.json`；不在 M104 worktree 直接提交。

## 当前处境
- Milestone: M117 / Gateway smoke 退出码收口
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M117`
- branch: `milestone/M117`
- 测试门禁命令: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120`
- 基线结果: `2 failed, 9 passed`；失败点为 smoke 收尾 `SHUTDOWN exit_code=-15`。

## Roadpoint 记录

### R1 关闭信号语义收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120`
  - Entry: 待补。
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 先补入口级 SIGTERM 回归测试，再做最小实现修复。
