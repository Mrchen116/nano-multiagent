# Code Review: feat-610

## Metadata

- reviewer: independent agent `workspace_tools_static_review`
- review_mode: full
- completed_at: 2026-10-15T00:05:00+08:00
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`
- validated_at: `33ef0d76d342a10c411ccbc0828f82d0d564e810`
- scope: complete `origin/main..HEAD` implementation diff; spec/design/design-review and corrected gateway delta.
- findings: `[]`

## Verdict

Approved. No confirmed or plausible actionable defect remains in the reviewed implementation. This is code and contract review; independent product acceptance remains separate.

## Coverage and evidence

- Reviewed all eight changed implementation, test, manual, dependency and lock files. Startup still disables the host-global management tool; the new tool is registered in a trusted workspace preset (`workspace-tools.ts:42-64`). Workspace identity is canonicalized from configuration, and model arguments cannot select another profile.
- Native PluginManager owns package transactions in a workspace-only management Context (`79-94`, `166-209`). Execution uses native Include and the host HMR queue. No runtime fork, private import, cache rewrite, second execution loop or separate permission database was introduced.
- Local bundle staging produces distinct generations, validates executable entries inside that generation, and parses execution patches from the persisted `file:` source rather than pnpm's hoisted copy (`96-109`, `149-164`). The published APIs and imports were checked against the installed locked packages and the pinned upstream reference.
- Actual Loader/fiber audit precedes an `applied` result; failed rows are retired without dropping unrelated working entries (`111-147`, `202-208`). Source evaluation failure, corrected reinstall and immediate same-turn dispatch are protected by `workspace-tools.test.ts:62-69`; an unrelated failed bundle leaves a good tool callable at `79-84`.
- Dynamic names exclude names present before managed installation (`56`, `144`). ToolSelection requires management permission for additions, preserves explicit empty sets and existing selections, and applies the same collection to execution and configuration selection (`capabilities.ts:24-29,47-59`; `index.ts:318`). Native child composition restrictions intersect across the scope chain; this implementation does not replace or dispose the child's inherited mask.
- The native process regression covers same-workspace chats, actual cross-workspace dispatch rejection, disabled static `read`, explicit empty selection, restart, disable/re-enable and removal (`workspace-tools.test.ts:70-101`). Existing capabilities, knowledge-policy and communication-native coverage remains applicable.
- Reused implementation evidence at the validated revision: `pnpm build`, `pnpm typecheck` pass; `pnpm test`: 84 files / 313 tests pass (`/tmp/nano-feat610-tests.log`, inspected). Additional caller evidence: non-E2E pytest 56 pass / 31 deselected; frontend 94 files / 881 tests pass; Ruff check/format pass.
- Independently executed `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_runtime_dependency_contract.py`: 13 pass. `git diff --check origin/main..HEAD` passes.

## Findings JSON

```json
[]
```

The caller identified a relative documentation link requiring a path-only correction during closeout; it does not alter the reviewed contracts or code. No source, tests, configuration or design were modified by this reviewer.

## Round 2 — Installed package-manager patch

- review_mode: patch
- diff_range: `c4822c94f6c388fc4807a2bc88a199b581f42e03..d7265f0a3a11a3467d9acb421ad6e45ec4721fbd`
- executed_base: `9182699fca58d42fbf166f3de7445c635dcb3527`
- validated_at: `d7265f0a3a11a3467d9acb421ad6e45ec4721fbd`
- completed_at: 2026-10-15T00:20:00+08:00
- verdict: Approved; findings `[]`.

The patch fixes the observed `spawn pnpm ENOENT` in environments without global pnpm. Review is limited to the new installed command, trusted initialization plumbing, affected regression and documentation changes; Round 1's core implementation conclusions are retained.

- `apps/node/src/release.ts:40-43` derives `../../tooling/node_modules/pnpm/bin/pnpm.cjs` from the verified release directory. This matches `apps/im-server/assets/install.sh:43-46,65` (`<install-root>/tooling`, `<install-root>/releases/<hash>`) and `apps/node/src/update-worker.ts:22,34-35`. `process.execPath` supplies an absolute Node invocation, and its directory is added only to the package operation environment. Source releases return no override.
- `apps/node/src/main.ts:61` sends that Node-owned fact over the existing stdio initializer. `packages/dsh-integration/src/index.ts:251` installs it after Loader readiness and before any configured Agent preset registration. `agent-config.ts:41` passes it to WorkspaceExtensions, which captures it on workspace owner creation (`workspace-tools.ts:47,80-87`). RuntimeSupervisor repeats initialization on process restarts; all owner creation paths therefore receive the same invocation.
- Integration uses the published `ProfilePnpmInvocation` / `ProfileContext.packageManager` seam; Node does not import DSH. The installed package exports and native manager support command, argument and environment overrides. Independent runtime dependency contract rerun at the new snapshot: **13 passed**. Patch whitespace check passed.
- Inspected `/tmp/feat610-pinned-pnpm-red.log`: real install failed with exit 127 / `spawn pnpm ENOENT`. Inspected `/tmp/feat610-pinned-pnpm-green.log`: **2 files / 4 tests passed**. Workspace regression now hides runtime PATH, supplies a real absolute pnpm invocation through initialize, and completes installation, failed-source repair, isolation, restart and revocation. The node-updater fixture independently executes the derived private CLI path, rather than only comparing its string. Build/typecheck success is caller-provided evidence at this snapshot.
- `acceptance.md` records the independent real-LLM **7/7** journey at `33ef0d76d`; its product behavior evidence remains applicable. This patch supplies the missing installer execution command and changes neither workspace selection, permission filtering, lifecycle semantics nor user-facing tool protocol. No full product re-acceptance is required for this delta. It does not claim a published installer/fleet deployment was performed.
- Final snapshot suite results inspected: `pnpm test` **84 files / 313 tests passed** (`/tmp/feat610-final-tests.log`); non-E2E pytest **56 passed / 31 deselected** (`/tmp/feat610-final-pytest.log`). Independent design-review R4 passed with 0 CRITICAL / 0 WARNING; isolated product services were cleaned by caller.

```json
[]
```

No source, tests, configuration or design were modified by this reviewer; only this report and verification were appended.
