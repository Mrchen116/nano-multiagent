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

- Status: DONE
- Canonicalization: old Gateway YAML and old IM mirror payloads use the same
  legacy-first merge table; `AgentWorkspaceConfig` and saved YAML now contain
  only `custom_prompt`.
- Wire/runtime: first registration sends non-empty `agent_custom_prompts`;
  agent create/current/skill-patch payloads omit the retired field; session
  metadata carries `agent_custom_prompt`, and `prompt_for()` injects only the
  canonical `pa.user_custom` segment.
- Continuity: live catalog publication reconfigures existing session runtime
  without changing its durable address; IM direct/group integration fixtures
  now assert the canonical metadata and runtime path.
- Tests: 866 PA unit/integration plus Kernel internal-override regression tests
  passed (85.88s); the full IM suite passed 422 tests (57.35s). The dedicated
  migration red/green set covers all four YAML combinations, no legacy save,
  registration seed filtering, old mirror merge, and duck-typed legacy prompt
  rejection.
- Static checks: Ruff and `git diff --check` passed for all touched Python paths.
- Commit: R2 implementation commit (this commit).

## R3 — Frontend public shape 与 stable preview 文案

- Status: DONE
- Shape: `AgentConfig`, create/update requests, form normalization, fixtures,
  and mock settings data no longer contain the retired profile field. API
  regression verifies PATCH sends `custom_prompt` and no legacy key.
- Wording: preview controls now read “Preview stable system prompt” /
  “预览稳定系统提示词”; the existing help still states that group chat and
  memory runtime segments are excluded.
- Tests: Agent settings plus chat integration suite passed 15 files / 130 tests;
  the focused red/green set passed 4 files / 39 tests. Existing React `act()`
  and user-stream fixture warnings remain unchanged.
- Build: `tsc -b && vite build` passed; Vite reported only the existing large
  chunk advisory. `dist/` remains an ignored local build artifact.
- Commit: R3 implementation commit (this commit).

## R4 — 隔离真栈、浏览器与最终门禁

- Status: DONE
- Persistence: loading a legacy Gateway YAML marks canonical persistence as
  pending, so the first successful authoritative mirror rewrites the file even
  when the merged in-memory config is already equal. The saved file contains
  only `custom_prompt`.
- Real stack: the isolated config-continuity critical path passed (1 test,
  8.12s). It proves legacy YAML -> empty IM first-seen seed -> visible custom ->
  stable preview/first LLM turn -> config update -> existing conversation
  history plus updated stable prompt on the next turn, with canonical YAML
  persisted after the successful mirror.
- Browser: an isolated IM/Gateway/Vite journey edited and saved a long Custom
  Instructions value, expanded the stable system prompt preview on desktop and
  mobile, found the saved role in the preview, and confirmed the group/memory
  exclusion help. Console had 0 errors/0 warnings; config PATCH and preview
  requests returned 200. Evidence is under `evidence/`.
- Frontend final gate: Agent settings plus chat integration passed 15 files /
  130 tests; `tsc -b && vite build` passed with only the existing large-chunk
  advisory. Existing React `act()` and fixture warnings remain unchanged.
- Full gates: PA plus prompt/Kernel regression passed 867 tests; IM passed 422
  tests; Ruff, `git diff --check`, and documentation integrity passed.
- Cleanup: the browser session, Vite, isolated IM/Gateway processes and ports,
  tmux session, and untracked dependency symlink were removed.

## Reviewer fix — C1 SQLite <3.35 prompt-column retirement

- Process: original M1 worker reused its completed context and omitted a new
  tasks roadmap plus the prior baseline under the reviewer-fix lightweight
  loop; this is one reversible persistence fix with one regression owner.
- Context: `ALTER TABLE ... DROP COLUMN` is unavailable before SQLite 3.35.
  Leaving an old prompt column untouched would also re-merge legacy text on
  every later startup, duplicating the visible custom prompt.
- Decision: current SQLite still drops the two retired columns. Older SQLite
  keeps the physical columns, but clears their values after the canonical
  migration; the public schema and repositories never read them.
- Evidence:
  - Red/green: the new old-SQLite regression first failed because current code
    dropped the simulated legacy columns, then passed after the guarded
    retirement change (6 focused tests passed).
  - Entry/regression: it uses an on-disk SQLite connection, executes the real
    `initialize_schema()` startup migration twice, and observes canonical
    profile data plus cleared retained legacy storage.
  - Full gate: `pytest tests/im_service tests/unit/IM -q` — 423 passed.
  - Static: Ruff and `git diff --check` passed.
  - Frontend State Matrix / Browser QA / Visual: N/A; this changes only IM
    startup persistence behavior.
- Rollback: `3d0e45290`.
- Commits: this reviewer-fix commit.
- Next: independent code review.

## Promotion Candidates

None.
