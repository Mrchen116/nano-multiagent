# M320 Re-fix unread badge that still persists after opening chat

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M320`，并将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 真实复现（强制）：已在真实浏览器打开 `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb`，可见该会话行仍显示 `8 new`（会话已打开仍未清零）。
- 运行时证据：
  - 当前服务进程 `python -m uvicorn IM.app:app --host 127.0.0.1 --port 8011` 的 `cwd` 为主仓 `/Users/czj/Repos/nano-multiagent`。
  - 当前交付 bundle 为 `src/IM/frontend/dist/assets/index-tC8820Bk.js`，不包含 `mark_as_read` 路径。

### R1.1 Runtime bundle delivery aligns with unread read-ack semantics
- Context: 待补充
- Decision: 待补充
- Rationale: 待补充
- Evidence:
  - Tests: 待补充
  - Entry: 待补充
- Rollback: 待补充
- Commits: C1=``, C2=``, C3=``
- Next: 先补 runtime 交付红测，再修复前端交付产物并做真实 URL 复验。
