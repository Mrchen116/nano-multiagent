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

TypeScript IM implementation is independently delegated. Root owns scripts, bounded asset conversion/cutover rehearsal, old runtime/tests retirement, canonical specification migration, final independent product/static gates and Ready PR with green CI.
