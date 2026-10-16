# Bundles and Host plugins

Adapted from DSH `cordis-plugin-development/references/host-plugin.md`; see [provenance](../UPSTREAM.md).

A bundle is a package whose `package.json` declares `dsh.bundle.patch`; the YAML patch inserts plugin entries. Give the package and rows unique names. Read an existing patch before editing it: a matching override replaces the complete `config`.

## Manifest

A Host-only bundle needs no install scripts or build tool. Author it in this workspace, outside `.nanoassistant/dsh-plugins`:

```json
{"name":"expense-summary","version":"1.0.0","private":true,"type":"module","description":"Summarize expense files","dsh":{"bundle":{"patch":"./cordis.patch.yml"}}}
```

```yaml
- insert:
    - id: expense-summary
      name: ./tool.mjs
```

Host entry files export `apply(ctx, config)` with optional `inject` and `Config`, or a service class as default export; do not mix them. Declare imported DSH/Cordis packages in `peerDependencies`; the native linked-package resolver reuses the host interfaces. Do not install a second runtime. Ordinary business dependencies belong in the bundle manifest. Register resources through `ctx.effect` or `ctx.on` with their cleanup.

## Install, enable, and observe

`plugin_manager install_bundle` performs package installation and bundle selection; do not reproduce those steps with shell commands. Only pass `approvedBuilds` after the user explicitly approves reported pending build scripts. Preserve failures and pending states; report success only after observing the requested capability.

`list_bundles` returns exact identifiers. `set_bundle` toggles them; `remove_bundle` removes a bundle. Inspect saved-state and activation outcomes separately: `failed` requires diagnosis, and `restart-required` means the change is not live. Installing a new bundle and enabling/disabling loaded contributions can apply online; replacing an installed package follows DSH's restart requirement. A normal node restart loads the replacement. Do not promise that changing files or toggling an existing package will load new code.

Keep user source and business data when disabling or removing a bundle. Installation does not grant permission for its future business actions.

## Nano configuration difference

Nano's workspace overlay is the `cordis.patch.yml` under the `profileDir` returned by `list_bundles`. Read it first and only override the installed bundle's existing row; keep other fields. Do not add a separate duplicate, edit the managed package manifest/runtime files, or change the node's Host profile. Services shared by provider and consumer use one isolated Cordis group. Persist business data in an explicit workspace directory, not in package installation files.
