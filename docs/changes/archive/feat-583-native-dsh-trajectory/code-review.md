# feat-583 independent code review

- Mode: full; reviewer `/root/feat583_static`, independent of implementation.
- Base / HEAD: `1128a2b6e30911e4658ed0d935dfff6b1424c740`; branch `codex/feat-583-native-dsh-trajectory`.
- Reviewed scope: task-owned tracked dirty diff plus new application/package source and tests, including `packages/dsh-trajectory-viewer`; `output/` was used only as evidence, not reviewed as shipped code.
- Snapshot: 2026-10-12 05:35 UTC. Subsequent root fixes require targeted closure. Initial SHA256: `trajectory-attachments.ts=b1bde5ec3a80cba9acd03041e917d9030e4f2f25b39281d1c93049759c2a0d00`; IM `trajectory.ts=b325380d4b427b0604c5b22e0ae1b6270ad1d61fb780dba9872a2c2758930ffc`; architecture test `c70bbfcbdcfd8aa9ff571194763f7303e76c50e117d6cdd47489ac54a7b8a2e2`.

```json
[
  {
    "file": "packages/dsh-integration/src/trajectory-attachments.ts",
    "line": 26,
    "summary": "[P1] Isolate failed provenance writes from later business input",
    "failure_scenario": "After read_image succeeds, its source file can be removed by another concurrent tool before the deferred realpath runs. That rejection is unhandled and leaves the shared writes promise permanently rejected. Every later record/read inherits it. SingleThread supplies attachmentSources even for text-only input, and NanoRuntime.submit awaits record before agent.followup/steer/inject, so this auxiliary viewer metadata failure rejects ordinary messages or terminates the runtime. A direct Cordis Context reproduction emitted a successful tools/result for a now-missing file and then called record with plain text: both the unhandled rejection and the subsequent text record failed with the same ENOENT. Handle each provenance failure without poisoning the chain or failing ordinary input; keep unproven images inaccessible.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "tests/contract/test_runtime_dependency_contract.py",
    "line": 38,
    "summary": "[P2] Enforce the narrow browser exception in the architecture guard",
    "failure_scenario": "The changed contract permits every @deepseek-ai public export inside the viewer and never scans src/IM/frontend. For example importing @deepseek-ai/dsh-api-session-controller at its root Host entry passes both checks because the dependency already exists and '.' is exported. A DSH import in the existing business frontend is outside the scan altogether. SPEC/D2 explicitly reserve Host dependencies for integration and require the browser exception to remain confined to official client/remote exports in the isolated viewer. Add the actual allowed browser entrypoints and frontend exclusion to this contract so these prohibited changes fail the required gate. No current Host import in viewer or DSH import in frontend was observed.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

Evidence inspected or independently checked:

- Root `pnpm test` log `output/feat-583-runtime/backend-tests.log`: 57 files / 161 tests passed, start 13:28:01 local, duration 39.75 s. This includes real IM process, cold runtime and stream tests; it does not establish final browser acceptance.
- Independent `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q`: 10 passed.
- Independent `pnpm --dir src/IM/frontend exec vitest run src/features/settings/agents/agent-work-panel.test.tsx`: 17 passed. These are existing Work regression tests; they do not exercise the new native observer.
- Independent `git diff --check`: passed.
- Independently resolved each of the 12 final manifest module IDs through its public `/client` export and compared the shipped viewer copy byte-for-byte: all equal. Source inspection found no DSH fork, private-source import or substitute renderer. The additional shell uses official renderer/Session Controller/conversation/trajectory/attachment/locale/theme services.
- Provenance failure reproduction used only an in-memory Cordis context and mock storageDomain; it wrote no source/config/test files and started no service. Its precise trigger and limits are in the first finding.

Rejected candidate: standalone Cron Work entries. Work's historical schema accepts this scope, but current `GlobalAgent` produces only global_main and native subagent/workflow descendants; native Cron runs in its original bound Session. No current independently bound native Cron root was found. Schema acceptance alone does not establish an authorized native execution. Returning a read failure for historical entries is compatible with R4 and the explicit exclusion of old Python trajectory conversion; the candidate is REFUTED as a blocking defect. Do not broaden native authorization for it.

Conclusion: changes required. Two CONFIRMED findings remain at this initial snapshot. No speculative issue is included. Inspector-selection restoration is being handled by the separate product reviewer/root and must be checked in the final closure, rather than treating the changing source as frozen here.

## Final targeted closure — 2026-10-12

- review_mode: closure; fixed validated commit `7e22a91d28fff92d07980845cfbabb9821cd1316`.
- Original reviewed baseline: `1128a2b6e30911e4658ed0d935dfff6b1424c740` plus the task-owned dirty snapshot/hashes above. Executed/effective integration base supplied by root: `origin/main` at `9e4b0a8a0`. Merge `24a3ac021` adds only five feat-573 design-workflow documentation/skill files relative to the original baseline; it changes no product code. The larger diff against main includes the separate refactor-581 migration dependency and is not a request to re-review that completed migration.
- Scope: C1, W2, corrected workspace-image delta, and the final root/product-review fixes to empty state, native row/tab/scroll bookmark, actual Inbox source identity, inherited native image source and inline-image refusal. No expansion to the REFUTED standalone Cron candidate.

| Focus finding | Final evidence | Closure |
|---|---|---|
| C1 / P1 provenance failure poisons ordinary input | `TrajectoryAttachments.enqueue` catches each failed write and leaves the serial chain fulfilled; `record` waits for that safe chain. Independent `trajectory-attachments.test.ts` rerun passed: a disappeared image has no source, the following text admission resolves, and a later valid image's source is still readable. | closed |
| W2 / P2 browser exception not guarded | The contract now scans `src/IM/frontend` and permits viewer only browser packages, shared Cordis and three explicit remote client entries, while retaining declared-public-export checks. Independent suite rerun 11/11; two temporary-source negative checks confirmed the exact formerly accepted viewer Host root and business-frontend DSH import now raise AssertionError. | closed |

Final new-finding result:

```json
[]
```

Additional changes reviewed without surviving defects:

- Work's main execution with no recorded turns uses the empty state instead of trying to create/read an execution to populate the page.
- Bookmark holds only `top/firstSeq/rowKey/detailTab`, scoped to user/revision/session. The original public Session Controller loads fresh history before restoring selected row/tab and scroll. This does not retain native payload or add a second renderer.
- Inbox image source records the actual bare `InboxStore.read` target, so IM compares the same conversation identity as the stored message/media. Source collection for a native child searches only its already-verified parent chain and still requires the official attachment API to prove the selected native history references the image. Inline legacy image bytes/URLs are replaced before history delivery; they cannot bypass the provenance gate.
- The workspace-image delta now documents Work-qualified preview after successful trusted workspace read and native Session-reference proof, including source-failure noninterference.

Validation reused from the final frozen tree: all-package build/typecheck passed; backend 58 files / 162 tests passed; Python 54 passed / 31 deselected; frontend full suite 825 passed before the final small host/bookmark fixes, followed by the affected 17-test Work regression and final build. Exact locators/limits are in `M1-work-native-trajectory/evidence.md`. Full suites were not rerun without a changed risk. Independent narrow reruns and negative architecture checks are described above; final `git diff --check` passed.

Final code-review conclusion: both focus findings closed, no CONFIRMED or PLAUSIBLE finding survives. Product-acceptance completeness is separately reconciled in `verification.md` using the independent acceptance report; this code conclusion does not substitute for that report.

## Post-PR compact Work toolbar — bounded patch review

- review_mode: **patch**; reviewed fixed range `c7d127bdc91c238522fc3edeb16d04bd719e4e47..d4a88e5af06285c0c54a712f4c2a404f26be347c` on 2026-10-12, independent reviewer `/root/feat583_static`.
- Product scope: only `src/IM/frontend/src/features/settings/agents/agent-work-panel.tsx` and `agent-work.css`. The third changed path is the milestone evidence record. The patch responds to the user's explicit feedback about repeated Work heading/description/badges and a separate switch row in the open PR delivery session.
- Checked actual diff and surrounding callers: the two mode buttons keep their callbacks/selected semantics; native execution select keeps the same session value/options/change callback; the same conditional `AgentTrajectory` receives unchanged scope/bookmark/back props. Record content remains mounted behind `hidden`, preserving the existing position/selection mechanism. Record mode retains main execution status; offline indication/callout remain, and native read status continues to come from `AgentTrajectory`. Removing a duplicated online badge does not remove its connection/error state.
- CSS changes are confined to the removed header selectors and compact toolbar/select styling. Narrow screens wrap the execution selector to its own row with `min-width:0` and a shrinking select; focus outlines remain explicit. No runtime, observer, authorization, native renderer or dependency changes were included.
- Evidence reused after reading the actual logs: `output/feat-583-toolbar-tests.log`, Work regression 17/17 at 14:19:09 local; `output/feat-583-toolbar-build.log`, `tsc -b && vite build` passed. Independently inspected desktop and 390px record-mode screenshots and ran patch `git diff --check` successfully. Browser native-mode/narrow-screen acceptance is separately owned by the product reviewer; screenshots of record mode are not claimed to prove it.

Patch findings:

```json
[]
```

Conclusion: no CONFIRMED or PLAUSIBLE finding in this bounded patch. Prior C1/W2 closure and the unaffected backend/native code-review evidence remain retained. No full re-review or additional implementation loop is required.
