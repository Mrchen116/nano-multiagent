# M1 progress

## Baseline

2026-08-05: the focused Gateway session, shadow, and Kernel compaction suite
passed: `118 passed`.

2026-08-05: `/new` parsing, binding replacement, replay protection, active-run
suppression, and queued-turn invalidation are covered by focused tests.

2026-08-05: external control outcomes now persist an operation ledger entry and
delivery intent before materialization. Gateway drains that intent immediately
after cached external channels are ready and again on IM reconnect; a failed
external `/new` follows the same durable path. Focused Gateway/Feishu-shadow
coverage passed, including startup recovery and control acknowledgement identity.

2026-08-05: independent product acceptance passed the live Web IM private-chat
and two-Agent MENTION-group journeys. No usable Feishu Bot credentials existed
in the isolated environment, so live provider verification remains explicitly
inconclusive; unit tests cover its normalized Gateway and recovery paths.
