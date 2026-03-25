# M320 Re-fix unread badge that still persists after opening chat

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M320`，并将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 真实复现（强制）：已在真实浏览器打开 `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb`，可见该会话行仍显示 `8 new`（会话已打开仍未清零）。
- 运行时证据：
  - 当前服务进程 `python -m uvicorn IM.app:app --host 127.0.0.1 --port 8011` 的 `cwd` 为主仓 `/Users/czj/Repos/nano-multiagent`。
  - 当前交付 bundle 为 `src/IM/frontend/dist/assets/index-tC8820Bk.js`，不包含 `mark_as_read` 路径。

### R1.1 Runtime bundle delivery aligns with unread read-ack semantics
- Context: 真实产品 URL `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb` 可稳定复现“已打开会话仍显示 `8 new`”。排查确认运行时实际交付的 bundle 为 `src/IM/frontend/dist/assets/index-tC8820Bk.js`，其中不包含 `mark_as_read` 参数路径，导致 M317 的已读语义未进入真实前端运行时。
- Decision:
  - 在 `tests/im_service/integration/test_messages_api.py` 增加运行时交付回归：从 `/chat/...` 解析脚本地址并断言 bundle 包含 `mark_as_read`。
  - 修复前端构建阻塞（`createGroupConversation` 中 `ImActorRef[]` 推断失败），确保 `npm run build` 能稳定产出最新 bundle。
  - 重新构建并提交 `src/IM/frontend/dist` 产物，确保运行时交付与源码 read-ack 路径一致。
  - 按 orchestrator 要求先同步分支基线：`git merge --no-ff main`，已将本地 `main`（`cca839d`）并入 `milestone/M320`（merge commit `3507eda`，无冲突）。
- Rationale: 这次故障是“真实运行时交付漂移”而非逻辑缺失；必须把 read-ack 路径放进实际被 IM 服务对外提供的 bundle，才能让真实 URL 中会话未读角标及时清零并在刷新后保持一致。
- Evidence:
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts`（仍有 2 个既有失败：`uses per-agent identity to keep same-turn multi-agent relay replies distinct`、`keeps same-turn group replies from multiple agents visible instead of collapsing them`；与 M320 变更无关）。
  - Tests: `pytest tests/im_service/integration/test_messages_api.py -k mark_as_read`（2 passed）。
  - Tests: Playwright 真实 E2E（`run-code`）在 `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb` 执行“打开+刷新后都不含 `8 new`”断言，通过（无异常抛出）。
  - Entry: 真实运行时验证（sync 后复验）：
    - bundle：`/assets/index-hutXMXlb.js`，包含 `mark_as_read`。
    - 浏览器快照：`.playwright-cli/page-2026-03-25T04-14-48-442Z.yml`、`.playwright-cli/page-2026-03-25T04-19-55-485Z.yml`，目标会话 `5e82e46169d044d18662e5bc853065bb` 行不再出现 `8 new`。
- Rollback: 回退到 `9e3318d` 可撤销 C2 实现，仅保留 runtime 红测。
- Commits: C1=`9e3318d`, C2=`688eda5`, C3=`f460eff`
- Next: 已完成 C3 与 dev-tasks DONE，等待 orchestrator 集成。
