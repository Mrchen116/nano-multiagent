# Independent code review

- Unit: `bugfix-594`
- Mode: `full`
- Executed base: `6eba6d476ca767628430c31a42f88570015b9a1c`
- Reviewed / validated implementation: `8987bec46` (review covered its identical working-tree implementation before commit)
- Reviewer: independent `gpt-6.1-sol`, high reasoning; no implementation edits
- Findings: `[]`

Reviewed all bugfix-594 changes, the actual apps/node → GlobalAgent → ExternalChannels/IM lookup and delivery callers, native send_message dispatch, and the new regression tests. Web member shape matches the IM response. Feishu shadow conversations retain the feishu channel and require the current app's ownerOpenId and actual DM source ID for the exemption. Mixed native agent_id arguments enter only native internal communication and cannot switch to public delivery. Generic allowlists cannot skip public recipient review; pre-existing tool restrictions retain precedence.

Reused focused 3-file / 33-test evidence and inspected cross-package authority boundaries. No concrete regression was found. Product source did not change after review; later edits only add the review report, archive the unit, and adjust relative document links. The full local suite and real model replay are recorded in the evidence document; this review does not establish production delivery acceptance.
