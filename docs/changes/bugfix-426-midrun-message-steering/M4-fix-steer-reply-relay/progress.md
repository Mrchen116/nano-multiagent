# bugfix-426-M4 — Progress

> #140 修复：决策5（同 run 续轮，消除 continuation 新 run_id）+ 决策6（消费点滚动气泡）+ 决策3 收窄。

## 启动澄清

- 派发包指向 design.md 的 M4 行 + 决策5/6，但主仓 cwd 的 design.md 是旧版（只有 M1/M2）；
  权威版本在 unit/bugfix-426 分支（commit de317913 `docs(bugfix-426/M4): 新增 #140 修复方案`）。
  M4 worktree 从 origin/unit/bugfix-426 创建，读到完整 M4 决策 + delta-spec。无需问 leader。
- venv：worktree 无法 editable install（pyproject 非 setuptools editable）；用 main 仓 .venv 的 pytest +
  `PYTHONPATH=src` 跑，已确认 `agent` import 解析到 worktree src。

## R1 — 决策5：loop 末轮 re-drain 续同一 run + commit_terminal 原子化

- Context:
- Decision:
- Rationale:
- Evidence:
- Rollback:
- Commits:

## R2 — 决策3 收窄：continuation 仅兜异常终止

## R3 — 决策6 信号：消费点发 pending_injection_consumed → injection_consumed

## R4 — 决策6 气泡滚动 + #140 e2e
