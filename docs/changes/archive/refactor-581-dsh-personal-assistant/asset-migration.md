# Non-chat asset migration

This is the implementation/cutover inventory for refactor-581. Original assets stay in place. The isolated rehearsal uses `NANO_OWNER_CONFIG_ROOT` and does not change the production owner root.

## Verified local inventory

The 2026-10-10 bounded read inspected only the configured owner's `tools/*.py`, `hooks/*.py` and the corresponding directories in workspaces named by that owner's configuration. It found two shared source files (five tools), no workspace Python tools and no Python hooks. This does not assert that another node has the same inventory; the fleet cutover must reconcile each node's configured roots.

| Existing source | Recorded SHA-256 | Native destination |
|---|---|---|
| `native_social_tools.py` (21,996 bytes) | `10eda4f535768fbca5fe2fdf91293ef7413de7e89ee7b41d6575cdccab860067` | Opt-in `@nano/dsh-integration/assets/social-tools` |
| `user_plugin_reviewer.py` (646 bytes) | `50e5feab4050cd9228fd953cf19908fc69f958cf75b23321e5a708ca05407482` | Owner's `owner-echo.mjs` native declaration below |

The social plugin retains `read_x_post`, `read_xiaohongshu_note`, `read_douyin_video` and `download_douyin_video`. Their single-URL constraints, fixed CLI arguments, reduced output and download evidence checks remain; the native body receives cancellation and waits for its owned reader process to close. `opencli` and `parsehub-douyin-once` remain separately installed commands. The plugin does not import or execute the old Nano SDK/classes. Downloads still require an explicit user request and are not performed by migration.

Declare the converted extensions in the destination owner root's `plugins.json`, preserving any other entries:

```json
[
  {"module": "@nano/dsh-integration/assets/social-tools"},
  {"module": "./owner-echo.mjs"}
]
```

Default command/data directories are relative to the actual OS home, matching the old installation. A different installation supplies `opencli`, `opencliCwd`, `douyin`, `douyinCwd` and `downloadDir` in the plugin entry's `config`. Workspace declarations use `.nanoassistant/plugins.json` and retain the tested same-name local override. Installing a package alone never enables its tools.

The actual echo asset becomes this owner-local declaration:

```js
export const name = 'user-plugin-reviewer';
export const inject = ['tools'];
export function apply(ctx) {
  ctx.tools.register({
    name: 'user_plugin_reviewer',
    description: 'User-level plugin test tool — confirms owner plugin discovery.',
    parameters: {type: 'object', properties: {msg: {type: 'string'}}, additionalProperties: false},
    output: {schema: {type: 'string'}, render: (_args, value) => [{type: 'text', text: value}]},
    async execute(args) { return `User plugin discovered! msg=${args.msg ?? 'none'}`; }
  });
}
```

No hooks needed conversion in this inventory. Future hooks are native Cordis declarations in the same manifest, using public events; there is no generic legacy Python hook loader.

## Search and model configuration

Native `web_search` keeps its `queries` schema. The node explicitly selects `DSH_WEB_SEARCH_PROVIDER`, or SearxNG when `SEARXNG_URL` is configured, otherwise DuckDuckGo. Registered adapters are `duckduckgo`, `brave` (`BRAVE_API_KEY`) and `searxng` (`SEARXNG_URL`). A selected unavailable backend or failed request returns an error; it does not silently switch providers. Search uses the same public DSH HTTP proxy route as native fetch. Service launchers must preserve the intended proxy environment; an existing tmux server does not automatically inherit a later shell's proxy variables.

`web_fetch` retains native HTTP retrieval, URL/redirect restrictions, HTML conversion, output limits and citation metadata. Its optional `prompt` uses the current Agent model for extraction. Extraction failure returns the already-fetched original page; cancellation propagates. No second network implementation is introduced.

The actual owner configuration uses Anthropic protocol through a local proxy. Selectable effort models map to pi-ai's adaptive effort wire configuration, including `high`, `xhigh`, `max` and disabled effort. Existing static `extra_request_body: {thinking: {type: adaptive}}` models map to native adaptive thinking with a default `high` effort. Native pi-ai also supplies its standard display/effort fields; migration preserves the thinking behavior rather than copying an arbitrary HTTP-body dictionary. Other extra-body shapes fail at configuration preparation with the model name instead of disappearing silently. No account credentials or global Git settings are changed.

## Evidence and remaining cutover work

- Native profile search/fetch regression exercises actual tool dispatch and a local HTTP SearxNG endpoint; DuckDuckGo/Brave adapter fixtures verify their wire arguments and failure/cancellation behavior.
- Native Anthropic adapter regression captures real HTTP request bodies, proving static adaptive thinking, `high`/`max` effort and disabled thinking.
- Social reader regression executes bounded fixture commands for all four contracts, mismatched item identity, invalid URLs and cancellation. It creates its download fixture only in a temporary test directory.
- The isolated Web IM probe successfully fetched/extracted `https://example.com` and searched DuckDuckGo for IANA example domains. An earlier network failure was traced to missing proxy variables in the owned tmux launch; the successful repeat used the native proxy route. Evidence: ignored `web-live.json`, native Session `9637a1a5-260f-415a-9ed4-4ef9b2566d27`.
- Actual shared plugin loading and native dispatch also passed in the isolated Node; echo and invalid-input evidence are in `assets-global-live.json`. Work Inbox short confirmation passed with a persisted Nano Auto allow record and file readback after confirmation.
- The full production cutover, second-node inventory and final document/entrypoint reconciliation remain M5 work. No production assets have been replaced.

## M5 two-node rehearsal (2026-10-10)

`pnpm pa migrate --source-root <old-owner-root> --destination <new-empty-directory>` opens source databases read-only, obtains SQLite backups, converts into a private staging directory and renames only the complete destination. It never starts a service, modifies the source config, loads old consent or reads old transcripts. A repeated invocation refuses an existing destination. Failed conversions remove only their own new staging directory.

The candidate contains a new config (native tool-name mapping and autostart disabled), new node storage, retained key/encrypted manifest, converted known owner plugins, and `migration-source/` copies of the old business databases and operation receipts. Workspaces and knowledge files retain their original locations. The cutover operator installs reviewed candidate state and converted plugin declarations into the original owner root; the rehearsal is not a second production listener. New DSH Session IDs map explicitly to old IDs, business keys and original binding timestamps in `migration-report.json` and `migration_bindings`; canonical direct selection retains oldest binding order. A new Work journal is used. Historical execution, publication, control, image and read facts remain in the source archive, without being presented as new execution.

Unread Inbox fragments retain their exact original boundaries and consumed-part flags; no old read receipt grants permission to a new tool call. Source message/ingress identities remain attached. The old relay deduplication window remains effective. External event identities are marked already admitted, preventing a resent platform event from starting new cognition. Group context for configured Agents is imported; records belonging to removed Agents remain only in the source archive.

| Snapshot | Source / active converted evidence |
|---|---|
| MacBook Air | 95 old bindings; 29 active bindings including the global main. 268 source group rows; 228 belong to configured Agents and enter the new buffer. Three relay dedup keys preserved. 40 external ingress events retained. No unread Inbox. |
| Mac mini | 18 old chat bindings plus three global mains map to 21 active bindings. All 27 group rows retained. 33 Inbox rows retain 32 consumed / one unread. All 257 external ingress identities retained. |

Both nodes have no configured nonempty legacy Cron job file in the bounded inventory. The converter refuses to claim readiness if such a file appears; importing an unobserved schedule shape is not an implicit compatibility path. Existing empty job files and Heartbeat cadence are retained. Mini's active Heartbeat `last_due_at` is imported; inactive Agent cadence remains archived. The shared tool inventory remains Air's two known Python source files (converted), zero Mini owner tools, and no Python hooks; custom source hashes not matching the reviewed conversions are reported as blockers.

Mini has three `gateway_pending_external_control_deliveries` in `outbound_handed_off`. Their original operation IDs and bodies remain in the source archive; the report marks them unresolved. Starting a node from that candidate is refused until those actual platform/IM outcomes are reconciled. No result was invented and no external action was resent. All observed shadow bubbles are already `reconciled` (Air 157, Mini 559). Config operation archives contain only applied/rejected outcomes; current channel control/status outboxes have no live head/inflight payload.

Fixture validation covers partial unread-page preservation, source immutability, canonical binding order, new execution IDs, relay dedup and unresolved-operation reporting. Actual snapshot evidence is under the worktree's ignored `.dsh-runtime/migration-{air-final,mini-rehearsal}/`; it contains private runtime data and is not committed. Asset readiness in a report does not prove production ingress was drained or authorize activation. Production deployment still requires the separate cutover procedure and authorization.
