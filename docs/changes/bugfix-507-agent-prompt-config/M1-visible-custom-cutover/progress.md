# bugfix-507-M1 — Progress

## Baseline

- Context: M1 同时切断 profile/API/storage/runtime/UI 的公开 legacy prompt 路径，必须先确认相关现有覆盖可运行。
- Evidence:
  - Python: 相关 IM/PA 91 tests passed（10.58s）。
  - Frontend: 相关 5 files / 42 tests passed（2.89s）；worktree 复用主 checkout 的 frontend `node_modules`。初次 `npm test` 仅因 worktree 未安装依赖报 `vitest: command not found`，建立未提交的本地依赖 symlink 后基线通过。

## R1 — IM canonical profile、schema 与 register seed

- Status: DONE
- Behavior: fresh schema and public Agent profile/API now contain only
  `custom_prompt`; old SQLite profiles are migrated idempotently with the
  approved legacy-first merge table, and conversation prompt snapshots are
  dropped while identity/version snapshots remain.
- Registration: `node.register.agent_custom_prompts` seeds only a first-seen
  profile; re-registration preserves existing values, including explicit null.
- Tests: 67 focused IM unit/contract/integration tests passed (14.02s), covering
  migration combinations, repeated initialization, API shape, create/update,
  real Gateway WebSocket registration, seed precedence, and relay continuity.
- Static checks: Ruff passed for touched IM and IM test paths; `git diff --check`
  passed.
- Commit: R1 implementation commit (this commit).

## R2 — Gateway YAML、sync 与 runtime prompt 单源

- Status: IN PROGRESS

## R3 — Frontend public shape 与 stable preview 文案

- Status: TODO

## R4 — 隔离真栈、浏览器与最终门禁

- Status: TODO

## Promotion Candidates

None.
