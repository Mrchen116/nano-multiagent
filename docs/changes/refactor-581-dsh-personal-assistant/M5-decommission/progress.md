# M5 — TypeScript center and old-path retirement

Implementation in progress. No production change, merge or final acceptance has occurred.

## Personal-assistant operations

- `pnpm pa [start|stop|restart|status|bind]` is the TypeScript node lifecycle entry. Foreground runs remain available. Config-scoped lifecycle/runtime locks and OS process birth prevent duplicate consumers and unsafe signalling. Runtime readiness identifies the owned DSH process.
- macOS preserves the config-derived LaunchAgent identity, persistent login/crash recovery, stop for the current login, explicit removal when autostart is disabled, and failure reporting if login-service setup falls back to ordinary background execution. Config environment loads in the foreground child; secrets are absent from the plist.
- Device binding retains X25519 proof, browser acceptance, local confirmation, credential resealing and recoverable operation identity. Binding after a lost commit response does not commit twice. Ownership transfer preserves prior runtime files in a distinct archive and installs the transferred encrypted manifest before reconnecting.
- Focused CLI tests passed against a real node/DSH child, including runtime cleanup, inherited configured environment, and PID mismatch refusal. Device-binding lost-response recovery passed through HTTP fixtures.
- A dedicated real LaunchAgent was started in `.dsh-runtime/lifecycle-acceptance/`: PID 97098 was deliberately killed, launchd recovered PID 97302, manual stop held, autostart=false removed the persistent definition, and the final process was stopped. Evidence: ignored `evidence.json` in that directory.
- The new binding CLI also completed a real proof/accept/commit/recover exchange with the isolated Python IM (node `e2e-cli-binding-1791567668`, owner `u_nqk675hf`). The config now contains only its runtime token; transient account credentials and operation file were removed. This is compatibility evidence, not yet TS center acceptance.

## Work still underway

The independent TypeScript IM implementation is integrated. Root owns remaining old runtime/tests retirement, canonical specification migration, final independent product/static gates and Ready PR with green CI.

Offline asset conversion is implemented and tested. Two real node snapshots were converted without changing production sources. The bounded inventory and exact reconciliation limits are recorded in [asset-migration.md](../asset-migration.md#m5-two-node-rehearsal-2026-10-10). Mini retains three unresolved external-control outcomes; candidate startup refuses them. Production cutover has not been attempted.

## Native center integration and operations

- The native IM first registration now seeds the complete canonical local Agent configuration. Reconnect preserves the existing center revision. This closes an observed first configuration PATCH conflict on the real node/center stack; a transport regression checks local model/prompt/features plus reconnect preservation.
- Usage comes from DSH public `deriveTurnTokenUsage` over persisted own turn events, including native children and cached input. Node persists reports before delivery; IM accepts each `(node_id, native session/turn)` once and records owner/conversation/Agent scopes. Offline/reconnect retries do not increase totals. Child inherited history is excluded from usage and Work projections.
- `pnpm build` and `pnpm test` passed on 2026-10-10: 48 files, 112 tests. New usage protections sit at the native runtime accounting seam, durable node report handoff, and actual HTTP/WebSocket IM process; each guards a distinct failure cause. Existing fork/history and Workflow tests were extended for inherited history and cold accounting.
- `scripts/e2e-up.sh` and `e2e-down.sh` now use native TypeScript binaries, real device binding and process identity checks. Python remains only a standalone fixture/helper language. Isolation keeps the copied config, workspace, owner skill root, DSH state, identity and IM data in the selected runtime directory.
- `scripts/e2e-resilience.sh --wt .dsh-runtime/native-resilience` passed against TypeScript IM + Node: restart IM without restarting Node, then start the already bound Node while IM is unavailable and recover when IM returns. Durable identity/data were retained; both services were stopped afterward.
- `scripts/e2e-gateway-autostart.sh --wt .dsh-runtime/native-autostart` passed: launchd initial PID 6730, crash replacement 7180, simulated login 7225; manual stop and permanent disable verified. Owned processes and plist were cleaned. These checks do not prove physical sleep/network recovery.
- Feishu fixture rendering remains covered by three passing standalone helper tests. The final native-center Feishu and iOS acceptance are still pending.
- Final native-center model smoke passed in `.dsh-runtime/usage-live`: a real `deepseek:deepseek-v4-flash` call read an isolated sentinel through the native `read` tool, returned the exact content, and the center reported all three scopes with 4,594 owner tokens. Conversation `c_n93dc539`, message `7ec4cf9474624c869419122229050233`; ignored `chat-evidence.json` and `usage-evidence.json` preserve results. Both test services were stopped afterward.
