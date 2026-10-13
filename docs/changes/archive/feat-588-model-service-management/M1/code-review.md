# Code Review: feat-588 M1

## Round 1 — full

- Date: 2026-10-13.
- Reviewer: independent static reviewer; did not implement the reviewed change.
- Branch: `codex/feat-588-model-services`.
- Review range: `e2e7aae53bd33a3257f33616d0311f1070d1e97a..eff9d6daf0b44cd6d1297e08500697e97561fa69`.
- `validated_at`: `eff9d6daf0b44cd6d1297e08500697e97561fa69`.
- `executed_base`: main `6275f271d`, already included in the range base with PR #337. Preceding feature behavior was read as context, not reviewed again.
- Mode: `full`. Read all changed implementation and regression tests, spec/design/deltas, M1 exit criteria, current IM/Gateway contracts, architecture and testing rules. Gate 2 R4 is the current design approval; the rejected old UI approval is not retained.
- Result: **Changes required — one CONFIRMED P1 finding.** Product acceptance is separate.

### Findings

```json
[
  {
    "file": "apps/node/src/model-setup.ts",
    "line": 145,
    "summary": "[P1] Keep surviving legacy services bound to their original credentials when removing a service",
    "failure_scenario": "A running node has legacy custom services A then B with distinct inline api_key values. B is used by an assistant and A is unused. Removing A rebuilds all provider profiles with B now at index 0, so B's apiKeyEnv changes from NANO_PROVIDER_1_KEY to NANO_PROVIDER_0_KEY. The existing runtime environment was created once in main.ts and still binds index 0 to A's key. The remove operation succeeds, but the same B session's next HTTP request sends A's key to B's endpoint. This breaks an unrelated assistant with authentication failure, or uses the wrong account when both credentials are accepted. The mismatch lasts until the whole node is restarted; a child-only restart reuses the original supervisor env. Independently reproduced against a real isolated DSH process and local HTTP fixture with dummy keys.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

### Direct evidence for the finding

The reproduction used the frozen source modules `NodeConfiguration`, `ModelSetup`, `providerProfiles` and the built `RuntimeClient`; only a new `mkdtemp` home and an HTTP server on an OS-assigned port were created. Both keys below are dummy fixture values. No production credentials, user test service on 52267, or shared fixtures on 18489/18490 were accessed.

Method:

1. Write a temporary node configuration with `default_model: b-model`, no saved agents, and two custom providers in this order: `legacy-a` (`api_key: fixture-key-A`, model `a-model`), `legacy-b` (`api_key: fixture-key-B`, model `b-model`). Each uses the isolated SSE fixture URL.
2. Compute the initial `providerProfiles(llm)` and start a real `RuntimeClient` with that `env`, matching `main.ts:29` and `main.ts:48`. Initialize it with the initial provider profiles.
3. Apply an assistant configuration using `legacy-b` / `b-model`, ensure a session, and submit `before`. Wait for `session.lookup` to report terminal. Record the actual HTTP Authorization header.
4. Call the real `ModelSetup.handle({action: 'remove', provider: 'legacy-a', revision: configuration.modelRevision})`; poll status until terminal.
5. Submit `after` to the same B session and record the actual Authorization header.
6. Kill and await the created DSH child, close the fixture server, and remove the temporary home in `finally`.

Execution: `node --import tsx /tmp/nano588-review-legacy.mts` from the reviewed checkout. The temporary script is an investigation artifact, not a permanent test; the relevant observation is preserved here:

```json
{
  "remove_operation": {"state": "succeeded"},
  "calls": [
    {"model": "b-model", "key": "Bearer fixture-key-B"},
    {"model": "b-model", "key": "Bearer fixture-key-A"}
  ],
  "remaining": ["legacy-b"]
}
```

Call chain: `ModelSetup.start` filters the removed provider (`model-setup.ts:109`), `run` recomputes profiles for every remaining provider (`:122`), then stages that complete map (`:145`). `providerProfiles` names env credentials from the current array index (`providers.ts:69`, `:85`). The child env is captured at node startup (`main.ts:29`, `:46`); the stage handler changes settings only (`packages/dsh-integration/src/model-setup.ts:65`). It does not update the running child's environment. The same startup env is reused by `RuntimeSupervisor` on child recovery.

Actionable correction: keep a surviving service's credential binding stable across list removal, or migrate the affected legacy bindings safely before installing the new profile map. Add a regression at the actual credential-resolution seam: two distinct legacy inline keys, remove the earlier unused service, and assert that the remaining service's same-session request still carries its original key. Do not weaken the S7 guarantee or require users to restart after every edit.

### Other reviewed boundaries and retained evidence

- Shared persistence queue rechecks revisions and Agent references before stage; stable product model names resolve to wire IDs for primary/fallback/approval/capabilities.
- API probes use a temporary DSH home and cleanup; credentials stay on local stdio and are filtered out of IM snapshots. Profile/key restoration, YAML failure and child-exit paths were inspected alongside their tests.
- Common Web editor, conflict comparison, offline draft retention, cancellation terminal feedback, owner checks, navigation and frontend labels were reviewed. Explicit visual quality and real product journeys remain the independent product reviewer's responsibility.
- Installer pins a complete SHA and hash, downloads the fixed GitHub URL directly, redirects the old IM package route, and preserves previous installation on failure. Publishing promotes a manifest only after anonymous hash verification. No Release publication or deployment is inferred from fixture tests.
- Reused author evidence after inspecting logs and corresponding tests: backend 67 files / 205 tests, Python 54 passed / 31 e2e deselected, frontend 89 files / 842 tests; UI redo 4 files / 22 tests, final models 8 tests and TypeScript/Vite build. Locators: `.runtime/feat-588/{native-tests-serial,python-tests,frontend-tests,typecheck,legacy-edit-test}.log`, `/tmp/nano588-ui-{tests,final-test,final-build}.log`, and `evidence/release-distribution.md`. These passing tests do not cover the surviving legacy service's env-index change reproduced above.
- `git diff --check e2e7aae..eff9d6daf` passed. No implementation, tests, config or design were changed. Existing untracked `.runtime/` and `output/` were preserved. All runtime resources created by this review were cleaned.

## Round 2 — closure

- Date: 2026-10-13; same independent static reviewer as R1.
- `validated_at`: `c4e2517b96d22f7c1a38df22ac8259ec5ab96f68`.
- `executed_base`: `b7e367cc08a642133dea28e372816cd79038818d`.
- `finding_origin_head` / `pre_fix_head`: `eff9d6daf0b44cd6d1297e08500697e97561fa69`.
- Fix commit: `db8c54e2f373e9d512f26151a912fb30edf01292`; inspected origin-head through the frozen validation head. Product code/test delta is only `apps/node/src/providers.ts` and `apps/node/tests/providers.test.ts`.
- Focus finding: R1 P1 / verifier W1. Mode: `closure`. Result: **PASS; W1 closed; no surviving findings.**

### Findings

```json
[]
```

### Focus closure and independent evidence

| Focus finding | Status | Evidence |
|---|---|---|
| W1: removing A makes remaining legacy B use A's key | closed | `providers.ts:70` derives a stable env name from the complete UTF-8 bytes of immutable `provider.name`. List position is no longer an input. Actual HTTP calls in the independent rerun use B's key before/after removal and after rebuilding the child with the original startup env. |

The fix keeps startup, live stage, rollback and child recovery on the same `providerProfiles` function. Startup computes the env once (`main.ts:29`, `:48`); live edit/rollback recompute the map (`model-setup.ts:122`, `:144`); recovery initializes from current YAML with the original supervisor env (`main.ts:51`, integration `client.ts:108`). An unchanged B service ID therefore produces the same env key in each path. No probe, stage/finish, credential-store or transaction code changed. For clarity, the R1 shorthand reference `main.ts:46` in its call-chain text should read `main.ts:48`; R1's observed defect and conclusion are unchanged.

Independent command: `node --import tsx /tmp/nano588-review-legacy-closure.mts > /tmp/nano588-review-legacy-closure.log 2>&1`, using the same temporary two-service HTTP fixture as R1, then explicitly shutting down and recreating the DSH child with the original env and the current remaining profiles. The same persisted session was ensured and submitted again. Durable result:

```json
{
  "remove_operation": {"state": "succeeded"},
  "authorization_before": "Bearer fixture-key-B",
  "authorization_after_remove": "Bearer fixture-key-B",
  "authorization_after_child_rebuild": "Bearer fixture-key-B",
  "initialBinding": "NANO_PROVIDER_6C65676163792D62_KEY",
  "liveBinding": "NANO_PROVIDER_6C65676163792D62_KEY",
  "remaining": ["legacy-b"]
}
```

This is direct local DSH/HTTP evidence, with fake keys and an OS-assigned port. The child rebuild reproduces the supervisor's env/profile inputs; it is not a full node supervisor crash/restart acceptance. All created processes, server connections and temporary home were cleaned; 52267 and 18489/18490 were untouched.

The new permanent regression (`providers.test.ts:11–77`) asserts the same live-session HTTP header across actual removal, with both inputs completed. Inspected shared red evidence `/tmp/nano588-legacy-red.log` shows the precise B→A failure under the old positional binding; green evidence `/tmp/nano588-legacy-green.log` records providers/model-setup/configuration/integration setup, 4 files / 15 tests passed. Author node typecheck pass is recorded in the handoff. No unrelated full suite was repeated.

### Retained scope and integration check

- Main `6275f271d..b7e367cc08a642133dea28e372816cd79038818d` adds only feat-589's `original-request.md` and `spec.md`; no implementation, tests, runtime dependencies or feat-588 contract were changed by that sync.
- R1's non-W1 code conclusions, public dependency boundary, Web explicit-contract comparison, common editor/owner/transaction checks and installation fixture boundary are retained. Spec/design/prototype, Web, IM, installer/publisher and probe/transaction source are unchanged.
- The IM delta's newly explicit MODIFIED requirement is documentation alignment to the already-reviewed API-first behavior; full corrected-delta reconciliation is in [verification.md](verification.md#corrected-delta-reconciliation). This does not restore the rejected old UI approval or substitute for product review of the separately running eff9 build.
- `git diff --check eff9d6daf..c4e2517b9` passed. Only the two assigned reports were changed by this reviewer; no implementation/config/test/design changes or push.

## Round 3 — patch: built-in catalog identity

- Date: 2026-10-13; same independent static reviewer.
- `validated_at`: `6309714219ba8cc1432e5e1752a94b50a7d8ad35`.
- `executed_base`: `b7e367cc08a642133dea28e372816cd79038818d` (unchanged).
- `pre_fix_head`: `310c63f85b8ce82a2f4ebea5171717388248f876` (R2 report-only commit over validated `c4e2517b96d22f7c1a38df22ac8259ec5ab96f68`). Reviewed its complete patch through the fixed validation head.
- Mode: `patch`; focus: product R1's built-in provider directory being renamed by a user service label after cold initialization, including the cached directory after removal.
- Result: **PASS — no patch findings; catalog identity defect closed at the implementation/test seam.** Product targeted acceptance is separate.

### Findings

```json
[]
```

### Evidence and retained conclusions

Only the native branch of `providerProfiles` removes the product `display_name` → DSH `displayName` override (`providers.ts:60–66`). The public DSH directory legitimately uses its configured profile display name; therefore leaving that field absent restores the runtime's built-in provider identity both before and after cold initialization. Node's existing cached catalog now starts from the same vendor identity and cannot retain the removed user-label override. No cache invalidation or compatibility mechanism is necessary for this fix.

Product service labels still live in Node YAML (`model-setup.ts:105`), safe service status (`:62`) and Agent capability `provider_display_name` (`capabilities.ts:52`). The custom-provider branch retains `displayName` (`providers.ts:79`). API URL, protocol, model metadata, immutable provider ID and all credential bindings are unchanged. Independently inspected the source result with a renamed native service and a named custom service: native profile has no `displayName`, the input product label remains `My Research API`, and custom profile label remains `Custom Service`. Removing the other service preserves B's binding `NANO_PROVIDER_6C65676163792D62_KEY`.

Read the permanent cold-initialization test (`providers.test.ts:11–33`) and its real DSH red/green evidence: `/tmp/nano588-catalog-red.log` expected `deepseek` but received `My Research API`; `/tmp/nano588-catalog-green.log` records providers/model-setup/capabilities/integration setup, 4 files / 11 tests passed. This uses a fresh temporary DSH home, reads the empty directory, then reopens the process with the renamed built-in configuration. Author node typecheck pass is provided by the handoff. These credible relevant results were reused without repeating an unrelated full suite.

W1 remains **closed**: the stable env-name code and existing same-session HTTP regression are unchanged and the latter is included in the green provider-file run. R2's remaining code conclusions and corrected-delta alignment are retained; no design/spec/prototype, Web, IM source, installer, probe or transaction change occurred. The product R1 triage document records the identity issue and a separate upstream execution observation; this patch review does not issue a browser acceptance or broader runtime verdict.

`git diff --check c4e2517b9..630971421` passed. No runtime processes/services were started or modified in this review; 52267 and shared fixtures remain untouched. Only the two assigned reports were edited; no push.

## Round 4 — patch: user-menu icon consistency

- Date: 2026-10-13; same independent static reviewer.
- `validated_at`: `c6b4455e158a32f71e179de19477ad65b2432158`; `executed_base`: `b7e367cc08a642133dea28e372816cd79038818d`.
- Mode: `patch`; complete reviewed range: `d27a8ad2347ccc8fd57c569634567ed654a4b73a..c6b4455e158a32f71e179de19477ad65b2432158`, exactly three frontend files.
- Result: **PASS — no surviving findings.**

```json
[]
```

The patch extracts the existing desktop 18px / 1.7-stroke SVGs into `UserMenuIcon`, replaces the mobile Me node/account/model/policy/company/language/sign-out glyphs with that same set, removes their icon background blocks, and adds a distinct two-person `members` glyph for both company entries. The SVG remains decorative (`aria-hidden`, `focusable=false`), while labels and whole-row click targets remain. Inspected every call site: hrefs, handlers, membership/admin conditions, language state, sign-out flow, node counts and API/query code are unchanged. No concrete correctness issue was found.

Reused caller-provided validation for this frozen patch: MePage/AppShell 2 files / 8 tests passed and TypeScript/Vite build passed; read the existing tests covering entry URLs, language persistence, sign-out, mobile/desktop shell and unread state. No backend suite was repeated. The reviewer's range-based `git diff --check` reports only `user-menu-icons.tsx:15: new blank line at EOF`; this whitespace detail is not a behavioral finding.

Subsequent whitespace cleanup `1bb8ff98e6309819abd2461930e869b818acada3` removes exactly that one EOF blank line. Inspected its complete diff: no semantic change, so the R4 conclusion is retained with the original `validated_at` and `effective_through: 1bb8ff98e6309819abd2461930e869b818acada3`. Final `git diff --check d27a8ad2347ccc8fd57c569634567ed654a4b73a..1bb8ff98e6309819abd2461930e869b818acada3` passes. Main remains `b7e367cc08a642133dea28e372816cd79038818d`.

**No spec delta.** This is the user's narrow visual consistency follow-up during PR #339 delivery; it creates no navigation, permission, state or API contract. R1–R3 static conclusions, W1/catalog-identity closure, corrected-delta alignment and all unaffected model/onboarding/installer/backend boundaries are retained. This static pass does not replace visual judgment of the new glyphs. Only the two assigned archived reports were changed; no runtime operation or push.
