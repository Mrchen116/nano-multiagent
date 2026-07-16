# feat-464 M3 — Permission diagnostics evidence

## Evidence boundary

- Runtime: the worktree stack was started with `scripts/e2e-up.sh` on IM
  `127.0.0.1:64311`, node `wt-feat-464-M3-496`, and a worktree-local Gateway
  config/cache/key. The final authoritative projection was read through the real
  authenticated IM HTTP endpoint.
- Real Feishu application: connection, the official tenant-scope probe,
  stop/restart, listener cardinality, and secret scans use the configured test
  application. Its grants were not changed merely to manufacture a limited state.
- Deterministic diagnostic states: limited, reconnecting/unknown, and
  failed/unknown were written with production `ChannelControlStore` status-result
  handling and the production capability catalog into the live IM SQLite store,
  then read through real IM HTTP and rendered by the real frontend. No HTTP route
  mock, static replacement DOM, or fake Feishu provider was used. Restarting the
  real Gateway restored the authoritative complete snapshot after each harness run.

This split is the approved M3-E8 evidence adjustment: the actual test application
is already fully authorized, so external permissions were not revoked and a fake
provider result was not presented as live evidence. The permanent provider, HTTP,
and frontend tests still enforce limited and unknown behavior.

## Real Feishu application proof

At `2026-07-15T11:27:42.535995Z`, a direct official
`application/v6/scope/list` probe returned a complete parse with 34 granted tenant
scopes. The production catalog matched these accepted sets:

| Capability | Matched granted set |
|---|---|
| `feishu.receive_p2p` | `im:message.p2p_msg:readonly` |
| `feishu.receive_group_at` | `im:message.group_at_msg:readonly` |
| `feishu.send_message` | `im:message:send_as_bot` |
| `feishu.receive_group_message` | `im:message.group_msg` |
| `feishu.message_history` | `im:message:readonly` |
| `feishu.group_history` | `im:message:readonly` + `im:message.group_msg` |
| `feishu.write_reaction` | `im:message.reactions:write_only` |
| `feishu.read_chat` | legacy accepted `im:chat:read` |

The final authenticated HTTP snapshot at `2026-07-15T11:23:52.422905Z` was
`connected/complete`, with 8 satisfied, 0 missing, and 0 unknown checks. The final
controlled restart terminated Gateway/listener PIDs `30176/31110` and started
Gateway/listener PIDs `43122/44037`; the old pair was dead and the final process
tree contained exactly one listener and one multiprocessing resource tracker.

The SDK originally logged its full WebSocket connection URL at INFO, including
temporary `access_key` and `ticket` query values. R4 added a red regression test
and now constructs `lark.ws.Client` with `LogLevel.WARNING`. All retained logs and
evidence were regenerated after that fix. Two expected SDK ERROR records from a
transient keepalive/SSL failure remain in the pre-final-restart log; the subsequent
official probe and authoritative `connected/complete` projection prove recovery.

Final count-only security audit:

| Surface | Secret hits |
|---|---:|
| IM SQLite DB | 0 |
| Gateway encrypted cache and private-key file | 0 |
| Worktree Gateway config | 0 |
| Gateway/IM logs, including restart logs | 0 |
| Durable screenshots/evidence | 0 |
| Fresh authenticated channels HTTP response | 0 |
| `access_key=` / `ticket=` in retained logs | 0 |
| Lark SDK INFO records in retained logs | 0 |

The worktree config contained one `credentialRef` and no `appSecret`; the config,
encrypted manifest, and private-key file were all mode `0600`.

## Browser journeys

All screenshots came from headed Chromium through the real Agent detail → Channels
entry. Desktop screenshots are 1440×1000; mobile screenshots are exactly 375×812.

| Screenshot | State and proof | SHA-256 |
|---|---|---|
| `feishu-real-connected-complete.png` | Real Feishu app, connected and complete | `3f1598c028989af34f97589a6b16ac89d7f13ac12f1804c0aeac865b3a6f88d0` |
| `channel-limited-production-store.png` | Connected/limited; missing group-message scope, group-context impact, raw scopes and remediation | `e61e545b97176e9abd82cbbcba24a0131807e4a6d24505c67ccb9fa919ec2e09` |
| `channel-reconnecting-unknown-production-store.png` | Reconnecting and permission unknown remain separate | `fd6e673cb9a6b3515ef05065a97c7f15c15e2bb437672a9b4db8cb29c2f7a68a` |
| `channel-failed-unknown-production-store.png` | Failed and permission unknown remain separate | `6e434ff69fe5357489562270ee9e776f7e608afce799c182e2082ebd278e1fb3` |
| `channels-list-error-real-im-outage.png` | Real IM outage renders error + Retry, never empty | `23da89d9da4e015c94b227882649e56b97f1485272c15ab3e663c06b7f764122` |
| `channels-mobile-375x812.png` | Single-column mobile card and reachable actions | `ee4c5b1bc31f7911d32474183dff9aeaebb2f8d08882a01c4b58dc5d9ceac26a` |
| `channels-mobile-add-bottom-sheet.png` | Add channel uses the production bottom sheet | `9b8d82b96f5596390f3b2c6fce70f198a94c976950a8b6f804a58f212678c56e` |
| `channels-mobile-edit-bottom-sheet.png` | Edit channel uses the production bottom sheet | `da6fad38a960e024644a64d999ccc6738658a7e9b11ae5caa0c0ea8332f6c61a` |
| `channels-mobile-delete-bottom-sheet.png` | Destructive confirmation uses the production bottom sheet; confirmation was not submitted | `c93fb16f462734eeb9caed565f5425c340fb273c8c9de235dfffd76c05fdeccf` |

Before the deliberate outage, the browser console had zero errors and warnings.
With IM stopped, the first channels request and the request triggered by clicking
Retry both failed with real `ERR_CONNECTION_REFUSED`; the page retained the error
card and did not render the empty state. Restarting the same IM DB/JWT/port restored
the page. Mobile DOM inspection confirmed `chat-modal-bottom-sheet` for add, edit,
and delete confirmation.

## Verification gates

- Focused Feishu worker/client/scope tests: 35 passed.
- Full backend: `pytest -m "not e2e"` → 3425 passed, 1 skipped, 20 deselected.
- Full frontend: 66 files / 617 tests passed.
- Frontend production build: 443 modules transformed, PASS.
- Ruff: PASS.
- Test naming/size contract: 2 passed.

## M3 exit evidence

| Exit | Evidence |
|---|---|
| M3-E1 | Production-store limited screenshot plus provider/HTTP/frontend regressions show connected/limited, raw scopes, impact/remediation, and explicit incomplete group context. |
| M3-E2 | Reconnecting/unknown and failed/unknown screenshots plus scope API/parse unit cases prove unknown is not converted to missing and remains separate from connection lifecycle. |
| M3-E3 | Real IM outage and real Retry request show list error without empty state. |
| M3-E4 | 375×812 card and add/edit/delete bottom-sheet screenshots plus interaction tests prove key actions remain reachable. |
| M3-E5 | Parameterized provider tests cover every current/legacy accepted set and grant/identity/malformed/API failure branches; the official complete probe matched all 8 live capabilities. |
| M3-E6 | Store/manager/IM/frontend tests cover incarnation/sequence CAS, barrier terminal ACK handling, FIFO continuation, IM receive time, offline stale, and exact query invalidation. |
| M3-E7 | Durable headed-browser evidence above plus all backend/frontend/build/lint/contract gates passed. |
| M3-E8 | Real app connection, official complete probe, three controlled stop/restart cycles, final single listener, and zero secret hits are live evidence. Limited/unknown use the explicitly identified production-store harness because the real test app is fully authorized. |
