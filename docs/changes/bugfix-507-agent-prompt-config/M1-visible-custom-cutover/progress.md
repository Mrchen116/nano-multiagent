# bugfix-507-M1 — Progress

## Baseline

- Context: M1 同时切断 profile/API/storage/runtime/UI 的公开 legacy prompt 路径，必须先确认相关现有覆盖可运行。
- Evidence:
  - Python: 相关 IM/PA 91 tests passed（10.58s）。
  - Frontend: 相关 5 files / 42 tests passed（2.89s）；worktree 复用主 checkout 的 frontend `node_modules`。初次 `npm test` 仅因 worktree 未安装依赖报 `vitest: command not found`，建立未提交的本地依赖 symlink 后基线通过。

## R1 — IM canonical profile、schema 与 register seed

- Status: TODO

## R2 — Gateway YAML、sync 与 runtime prompt 单源

- Status: TODO

## R3 — Frontend public shape 与 stable preview 文案

- Status: TODO

## R4 — 隔离真栈、浏览器与最终门禁

- Status: TODO

## Promotion Candidates

None.
