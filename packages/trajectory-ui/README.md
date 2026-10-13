# Nano trajectory UI

`@nano/trajectory-ui` is the Nano-maintained source fork of
`@deepseek-ai/dsh-client-ui-trajectory@0.2.1-alpha.1`. It preserves the upstream
trajectory table, timeline, inspector, styles and event projection code.

The initial import copies all 39 source files without modification from upstream
commit `5badb15009ae1756c3afe0ae0cef1faafc290ccc`.
[upstream.json](upstream.json) records source provenance and baseline SHA-256
values. The [MIT license](LICENSE), including the DeepSeek copyright notice,
is retained and embedded in the generated client bundle.

This package is a browser UI fork. Its Host entry has no behavior. Session,
Conversation, Slots, Renderer and shared UI dependencies remain official,
version-pinned public packages. Only this package's source is independently
maintained; the repository-wide boundary is in [SPEC.md](../../SPEC.md).

## Build and integration status

```sh
pnpm --filter @nano/trajectory-ui typecheck
pnpm --filter @nano/trajectory-ui build
```

`lib/client.js` registers `@nano/trajectory-ui` with the DSH browser module loader.
It keeps React, UI primitives and service registries external so their runtime
identities are shared with the containing viewer. Package-local CSS is compiled
and injected with the bundle. `lib/` is generated and not committed.

The viewer mounts this package as its only trajectory view. `apply(ctx, {navigation})`
accepts session-scoped read/navigation operations. The native ledger renders launch
entries, scopes a local snapshot to the chosen execution, and controls its existing
timeline and inspector. Switching to session history keeps the same components.
No second record renderer, inspector or runtime loop is introduced.

CSS module identifiers remain descriptive because this bundle and its host are
built independently; independently shortened class names would collide.

## Validation and maintenance

The initial source import passed typecheck and an independent build. The native
bundle probe can mount either the official bundle or this local bundle:

```sh
NANO_TRAJECTORY_FORK=1 pnpm exec vitest run --config packages/dsh-trajectory-viewer/probes/vitest.config.mjs
```

This is a React/JSDOM registration and interaction probe, not browser acceptance.
It checks image extension registration, tool focus and manual timeline selection.
The original feasibility probe documents the public upstream slot limitations;
Nano additions use this fork's explicit navigation face. Behavioral tests run with
`pnpm exec vitest run packages/trajectory-ui/tests`.

`tests/upstream/` retains the original upstream test sources as reference. Those
files assume the original monorepo's paths, private test fixtures and runner;
they are not part of Nano's default test command and are not reported as passing.
Port the affected tests as behavior is changed, alongside final viewer acceptance.

Future upstream synchronization is deliberate: select a source commit, inspect
its UI and dependency changes, then update the baseline and affected tests.
Updating DSH runtime packages does not automatically overwrite this fork.
