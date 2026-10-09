# Code review R2 closure

- Mode: closure; finding_origin_head `7987f40bc`.
- Reviewed head: `55defc67096df2255bf54be421619496d869c3f0`.
- Scope: R1 eight findings and their fixes only. No new full review, UI control, service startup, implementation changes, or commits.
- Result: seven closed; one superseded by a confirmed regression in the revocation fix. R2 has one surviving P1 and the code review gate remains open.

| R1 item | Result | Fixed-head evidence |
|---|---|---|
| 1 Cursor-free membership/removal frame | superseded | Control frames now run before cursor guard; history/send publication checks revokedChats while the chat remains marked revoked. Original missing-cursor defect is fixed. The fix also treats ordinary rename/add/create notifications as revocation and never schedules permission re-read; see R2 finding at ChatStore.swift:82. |
| 2 Selected Agent group command target | closed | ConversationView uses ChatText.command with group.agent_id; sendMessage invokes ChatText.wire with actual participants. The selected Agent becomes a structured real-member user_id mention, so /new is targeted. |
| 3 More-than-one-page reconnect history gap | closed | loadChat walks next_before_message_id backward until existing history overlaps, then merges the full bridge and retains the earlier cursor. Regression covers m1...m60 plus m62...m121 and obtains every m1...m121. |
| 4 Pending configuration error code | closed | AgentConfigView, AgentCreateView, and agentError inspect APIError.code == config_apply_pending. Session already extracts detail.code into that field. |
| 5 Skill opaque key / namespace | closed | Skill selection invokes ChatText.skill(skill.name), resulting in /skill:name. skill_key remains identity only. |
| 6 Prefix-collision mention identity | closed | ChatText.wire matches whitespace-bounded exact Agent IDs and emits member user_id tags. ChatText.display resolves received tags to names. planner/planner2 regression verifies only u_two is mentioned and no @planner remains. |
| 7 Unsaved heartbeat/cron preview | closed | previewPayload explicitly sends heartbeat_enabled and cron_enabled from current draft features; both node and existing-Agent preview calls reuse it. |
| 8 Foreground banner navigation | closed | ChatBanner stores conversationID; RootTabs opens that target. UUID-scoped dismissal does not clear a later banner. Existing notification floor still excludes replay. |

## Evidence reused

- Read the R1 red log `/tmp/nano-feat578-chat-red.log`: cursor-free revocation and 61-message gap failed against the reviewed implementation.
- Read `/tmp/nano-feat578-xctest-r2.log`: **TEST SUCCEEDED**, 10 XCTest plus 10 Swift Testing tests. This includes the repaired ChatState, ChatText, and preview contracts.
- Simulator xcresult: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_01-51-11-+0800.xcresult`.
- Fixed-head diff restores default simulator signing and Debug ONLY_ACTIVE_ARCH=YES; documented live login and actual test evidence are applicable build-fix evidence. No new defect was inferred from the declared incomplete UI/physical-device gates.
- R2 regression is directly grounded in the fixed client branch plus actual backend notification callers (`web_im.py` creation, rename, add-member). It is not a claim of newly executed simulator UI acceptance.

No product or final verification acceptance is granted by this closure report.
