# M130 Acceptance Review

## Scope
- Milestone: M130 — IM/Gateway 产品级总复验
- Review target: `/Users/czj/Repos/nano-multiagent/.worktrees/M130`
- Review date: 2026-03-13
- Review mode: product-manager-style acceptance review
- Focus: reassess whether the current IM + Gateway experience is now product-grade usable on the normal user path, while checking whether the earlier blocking/major concerns from the broader failing review have been credibly closed.

## Materials Reviewed
- Requirements anchor:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/docs/需求.md`
- Prior failing review baseline:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/ACCEPTANCE/IM-gateway-product-review.md`
- Current user-facing path docs:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/README.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/docs/operator-runbook.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/src/IM/frontend/README.md`
- Current evidence and closure artifacts:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M126-api-roundtrip.json`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M126-browser-evidence.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M127-browser-evidence.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M128-browser-evidence.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M129-startup-default-path-productization.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/M120-acceptance.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/m125-browser-evidence.json`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/ACCEPTANCE/m125-im-api-evidence.json`
- Supporting test/evidence sources used to judge credibility:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/tests/acceptance/test_im_gateway_real_acceptance.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/tests/e2e/test_personal_assistant_main_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/tests/im_service/integration/test_account_binding_api.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M130/tests/im_service/integration/test_gateway_websocket_api.py`

## User Journeys Exercised or Judged
1. First-run default path as documented: start IM, start Gateway, complete bind if prompted, open Web IM, send first message.
2. Binding and ownership path: bind start -> bind confirm -> user `owned_node_ids` reflects node ownership.
3. Main chat path: default conversation available, composer readiness determined by bind/online state, message can complete roundtrip through Gateway.
4. Conversation discoverability path: user can understand different conversation types and available chat targets from the Web IM list and detail header.
5. Failure paths: unbound, bound-but-offline, and unavailable-on-send all present one unified `Chat unavailable` pattern with actionable next steps.

## Passes
1. **Startup/default path is now materially clearer for a normal user.**
   - `README.md` and `docs/operator-runbook.md` align on one primary path instead of operator-first API assembly.
   - IM ready signal, Gateway ready signal, and next-step guidance are spelled out in user-facing terms.
   - `src/IM/frontend/README.md` clearly marks the dev server as a development-only path, not the product entry path.

2. **The earlier binding/ownership blocker is credibly closed.**
   - `ACCEPTANCE/M126-api-roundtrip.json` shows `me.owned_node_ids == ["node-1"]` and `nodes[0].owner_id` set to the same user.
   - `tests/im_service/integration/test_account_binding_api.py` directly verifies bind start/confirm and the resulting owned-node relationship.
   - This is a substantive correction versus the earlier failing evidence pack where ownership stayed empty.

3. **The earlier “full roundtrip not proven” blocker is closed enough for product judgment.**
   - `ACCEPTANCE/M126-api-roundtrip.json` records a complete bind -> relay -> gateway -> receipt chain and includes `adapter_outbound == ["assistant:hello from web im"]`, `pipeline.reply_text == "assistant:hello from web im"`, and completed relay status.
   - `tests/acceptance/test_im_gateway_real_acceptance.py` verifies the same chain and asserts the assistant reply text that is routed back through the Web IM relay path.
   - While this is still stronger on system evidence than on fresh browser automation, it is enough to show the product now has a credible agent-reply loop rather than only a user-send completion marker.

4. **Conversation discoverability is sufficiently improved for main-path product judgment.**
   - `src/IM/frontend/README.md` now describes distinct direct agent chat, agent-to-agent chat, and group chat list semantics.
   - `ACCEPTANCE/M127-browser-evidence.md` shows browser-visible assertions for list legend, kind labels, target labels, and detail-header target context.
   - This addresses the earlier concern that the experience looked like a single seeded demo chat with no target-discovery explanation.

5. **Failure UX is now sufficiently unified for key failure-path judgment.**
   - `README.md`, `docs/operator-runbook.md`, and `src/IM/frontend/README.md` consistently describe pre-send disabled composer behavior for unbound and offline states, and draft-preserving failure feedback for unavailable-on-send.
   - `ACCEPTANCE/M128-browser-evidence.md` documents focused browser-visible assertions for all three cases under one `Chat unavailable` model.
   - `tests/im_service/integration/test_gateway_websocket_api.py` further shows server-side actionable failure events (`relay.failed`, `conversation.notice`) when the target node is unavailable.

6. **Recent startup/productization closure is backed by more than doc edits.**
   - `ACCEPTANCE/M129-startup-default-path-productization.md` cites aligned doc updates plus Python acceptance/integration coverage and frontend tests/build, which together make the current default path more trustworthy than the original M120 evidence pack alone.

## Issues
### Minor 1: Fresh browser-level end-to-end evidence is still weaker than the API/test evidence
- Severity: Minor
- The new acceptance basis relies on a mix of realistic acceptance tests, integration tests, and browser-visible frontend assertions rather than a fresh real-browser, real-process artifact that visibly captures the full reply loop in the shipped product UI.
- This does not block acceptance because the combined evidence now closes the earlier functional uncertainty, but it remains the thinnest part of the evidence package.

### Minor 2: The broader product requirements are only partially covered beyond the reviewed main path
- Severity: Minor
- `docs/需求.md` includes broader product ambitions such as richer conversation visibility and group workflows.
- Current reviewed material is sufficient for judging the present IM + Gateway default path product-grade usable, but it is not a full proof that every broader future-facing collaboration requirement is fully productized end to end.
- This is acceptable for M130 because the milestone goal is a total re-review of IM + Gateway product usability, centered on the normal user path and key failure paths, not a full closure audit of every higher-order collaboration capability.

## Retest Focus
1. If a future audit wants stronger evidence quality, add one canonical real-browser, real-process capture that visibly shows: bind state clarity, selected route/target clarity, a user send, and the assistant reply rendered in the shipped Web IM UI.
2. In the next product review, spot-check whether multi-conversation and group-chat discovery remain understandable when backed by real data rather than seeded/demo-oriented fixtures.

## Final Verdict
- Final verdict: Acceptable
- Blocking issues: 0
- Major issues: 0
- Minor issues: 2

The product is now acceptable as product-grade usable for the reviewed IM + Gateway scope.

Reasoning:
- The previously failing areas that mattered most to normal-user product judgment—startup/default-path clarity, binding ownership trust, conversation discoverability, unified failure UX, and credible end-to-end roundtrip proof—now have enough aligned documentation and evidence to pass a strict product-manager acceptance bar.
- Remaining concerns are about evidence quality depth and broader coverage breadth, not about a blocking or major usability break in the current main path.
