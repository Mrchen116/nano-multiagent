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
