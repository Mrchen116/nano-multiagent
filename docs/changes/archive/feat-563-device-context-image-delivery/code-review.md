# Code Review

- Review mode: full
- Base / executed_base: `0014ee0b0`
- Final reviewed tree / validated_at: `5a03c6151`; full review through `270677318`, followed by independent delta reviews of `270677318..8b99f43eb` and `0da448358..5a03c6151`.
- effective_base: `0014ee0b0`; final sync retained the same origin/main base.
- Final delta evidence: [verification Round 4](verification.md#round-4--delta-verification-and-code-review-closure), 16 tests passed, no surviving candidates.
- Independent finder: `review_finder_563`; initial candidates independently confirmed by `runtime_563`.
- Verdict: PASS; final surviving candidates: `[]`.

## Confirmed findings and closure

| Finding | Direct evidence | Resolution |
|---|---|---|
| Pending/partial image publications had no recovery consumer | Kernel ends the incomplete run; old ledger only held state, with no replay envelope or scanner | Exact native/explicit/provider payloads persisted before sending; existing Gateway recovery drains them with original identities, skips confirmed channels, and stops expired provider replays |
| Shadow replay could reread the original file under a different key | Delete source after `run:candidate:*` preparation; `run:bubble:*` reconciliation failed with `file_not_found` | Shadow output aliases the authorized candidate manifest; online and unanchored offline integration tests prove original bytes survive source deletion |

Final independent review retained full-diff coverage and rechecked recovery, unresolved same-text deduplication, offline publication, lifecycle suppression, and bounded/escaped diagnostics. No additional concrete candidates remained. The provider replay cutoff follows the official [Feishu SDK UUID contract](https://larksuite.github.io/oapi-sdk-java/com/lark/oapi/service/im/v1/model/CreateMessageReqBody.Builder.html).

## Post-PR correction

Remote CI exposed initial-bubble allocation racing between managed output and the regular event stream. Independent [verification Round 5](verification.md) reviewed the shared start/ACK lock and both deterministic regressions; 18 relevant tests passed and no surviving code-review candidates remained. Earlier full-diff findings remain closed.
