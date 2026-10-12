# Native DSH trajectory viewer

This isolated browser composition mounts the published DSH `0.2.1-alpha.1`
trajectory UI. It uses the official Connection, Typert registry, generated Remote
contributions, Session Controller, Conversation, Session, Trajectory and Attachment
plugins. Native events, incremental assistant chunks, projections and attachment
results cross the carrier unchanged; this package does not implement a transcript
decoder or a second trajectory renderer.

`pnpm --filter @nano/dsh-trajectory-viewer build` creates `dist/`. Serve that
directory at `/trajectory/` with CORS allowed for the opaque iframe origin,
including JavaScript, CSS, JSON and fonts. The builder copies published
registration bundles and their chunks without modification. Its module loader
maps the official logical combo URL to ordinary static paths. The singleton
React and UI support modules are bundled separately by esbuild. All DSH packages
are version-pinned; do not mix a new Host version with this composition.

The host creates an iframe with `sandbox="allow-scripts"`. After receiving
`nano-trajectory-ready` from that iframe, it transfers one MessagePort with
`nano-trajectory-init`, `sessionId`, `version` and `assetBase`. The viewer accepts
initialization only from its parent. `transport.ts` carries the `call`, `open`,
`next` and `abort` protocol from `product-contracts/src/trajectory.ts`. The parent
owns authentication, target authorization and observation lifetime; no owner
token or Gateway URL is passed into the iframe.

Only session list/page/projections/attachment calls and control/follow streams
can leave the viewer. The native `$events` readiness handshake stays local; no
Host-wide event or approval channel is subscribed. The root mounts only the
official `conversation.view` trajectory slot. Workspace navigation, uploads and
configuration writes have explicit read-only faces. Official conversation UI
preferences use an iframe-local, ephemeral Storage object because an opaque
sandbox cannot access origin localStorage. This does not grant same-origin
access or persist preferences.

Each observation stream pulls one bounded parent batch after its buffered frames
have been consumed. `generation_changed` requests an official Connection
reconnect; Session Controller rebuilds the window in a new generation. Leaving
unmounts React, releases the Session reference and Cordis fiber, aborts read
streams and closes the port. A read-stream abort never invokes Agent cancel.

Validation:

- `pnpm exec vitest run packages/dsh-trajectory-viewer/tests/transport.test.ts`
- `pnpm --filter @nano/dsh-trajectory-viewer typecheck`
- `pnpm --filter @nano/dsh-trajectory-viewer build`

The transport tests cover mutation refusal, unchanged RPC payload/results,
bounded pull ordering, read cancellation, local readiness and native-generation
recovery. Browser acceptance must additionally exercise the sandboxed final
bundle through the host and a real Gateway; fixture data establishes component
and carrier compatibility only.
