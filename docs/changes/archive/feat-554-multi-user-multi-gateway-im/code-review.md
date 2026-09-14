# Code Review — feat-554

## Full review, round 1

- `executed_base`: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- `validated_at`: `1f14e77db`
- `review_mode`: `full`; `diff_range`: `94338a2a7...1f14e77db`
- Independent finder: `/root/code_finder`; independent candidate verifier: `/root/code_candidates_verify`. Neither edited implementation.

| Finding | Independent confirmation | Disposition |
|---|---|---|
| P2 ordinary human direct title showed receiver's own name | Alice and Carol each contact Bob: Bob saw two chats named Bob; explicitly renamed Project note remained shared | Fix viewer projection only for uncustomized ordinary human directs |
| P3 public Agent rail lost node alias | Actual Nodes PATCH saved Office Laptop, but Contacts returned Raw MacBook; React AgentRow rendered raw name | Preserve existing alias as the public device label |

No other confirmed findings survived full coverage. Optional speculative changes were not requested.

## Patch and closure, round 2

- `validated_at`: `a62b98d45991b47a0a874403e6625c58142cdd6a`
- `executed_base`: unchanged
- `review_mode`: `patch + closure`; `fix_delta_range`: `1f14e77db..a62b98d45`
- Includes migration Markdown calibration, the two fixes, and product review's missing mobile Policies entry.

Finder independently reviewed the entire narrow delta; surviving findings: `[]`. Both original findings are closed. Independent candidate verifier performed fresh HTTP checks: Bob's list/detail/sync showed Alice or Carol, explicit shared rename remained, special direct_key=NULL titles remained unchanged. Fork/distill creation paths retain their titles; 13 related tests passed. Actual node alias save was returned to both owner and another account; clearing alias restored raw node name. AgentRow renders the label on desktop/mobile; 14 existing row tests passed. Mobile Policies uses its actual registered route, existing English/Chinese strings and a separate icon row; the 3 MePage tests passed.

The source delta does not alter membership, credentials, permission routing or PA execution. Full review's unaffected findings and coverage are retained through this patch. Product acceptance remains a separate gate; this report does not claim browser product acceptance or production migration.

## Native IM boundary patch, round 3

- `validated_at`: `086467a12489dbfbe53423b25ce0ee5ca6f2edec`
- `executed_base`: unchanged
- `review_mode`: `patch`; `diff_range`: `9b4ed2e93..086467a12`

Independent finder reviewed both changed files and returned `[]`. Native relay decoding supplies the conversation ID in `external_chat_id` and its durable user-message anchor in `ingress.im_relay.im_message_id`; the patch uses these when building the runtime-change outbox entry. External shadow references and pending-saga promotion remain unchanged. The finder inspected runtime application/outbox ordering and independently ran the four focused admission cases, all passed. No new candidate required candidate verification. Full and prior closure conclusions remain retained outside this defined delta. The product-visible divider still requires the independent live targeted acceptance.

## Explicit images and distillation text, round 4

- `validated_at`: `513ee21637917dabe16f2f2080136ed63510f7d9`
- `executed_base`: unchanged
- `review_mode`: `patch`; `diff_range`: `4e93dbaae..513ee2163`

Independent finder found one P2: explicit dispatch newly interpreted a protected image reference from the same chat as a local file and replaced it with a source failure. Independent candidate verifier reproduced the actual old/new handler difference with the real ReplyImages service. The concrete trigger is a later send whose input includes an existing hosted URL. The initial suggestion that SendMessageTool returns the projected text to the model was disproved: the public tool response omits text, so that explanation is not used as evidence. No other candidate survived this patch review; the bilingual distillation error change had no finding.

## Hosted-reference closure and test layout, round 5

- `validated_at`: `c3046c6a2`
- `executed_base`: unchanged
- `review_mode`: `patch + closure`; `diff_range`: `513ee2163..c3046c6a2`

`274ad07bc` preserves a strictly matched current-chat hosted image receipt while continuing to snapshot and upload local images in the same message. Other-chat and malformed references remain rejected; browser resource access still checks membership. External projection does not send IM private URLs and reports a local image failure when no exportable snapshot exists. Stable-call retry and local/provider receipts remain intact. Two SDK regression cases failed before the fix and passed after it; 76 relevant implementation tests passed.

The final test-layout commit `c3046c6a2` splits the external-channel case from the native file to satisfy the repository's new-test-file size contract. All test/helper AST bodies are unchanged; the focused contract and image run passed 14 tests. Independent finder inspected the complete final patch, including discovery/imports after the split, and independently ran 29 tests. Findings: `[]`; the P2 is closed. All earlier full and patch conclusions are retained outside these explicit deltas. This report does not substitute for the separately recorded product and implementation-verifier gates.


## Public profile presentation patch, round 6

- `validated_at`: `255903e3ef4771cde484d2606decf4d119d444e7`
- `executed_base`: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- `review_mode`: `patch`; `diff_range`: `a7610b283..255903e3e`

Independent finder reviewed the public profile JSX, removal of the separate public CSS layout, the existing owner-page comparison and the updated Work label expectation. Result: `[]`; no candidate required a separate candidate-verification pass. Existing full/patch findings remain closed outside this presentation-only delta. Public identity lookup, ownership decision, message creation and Work access retain their existing implementations; the separate product reviewer owns visual and actual-entrypoint acceptance.


## Person avatar consistency patch, round 7

- `validated_at`: `320b39c96c6be1c7f4d247cca405a0dd058168fd`
- `executed_base`: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- `review_mode`: `patch`; `diff_range`: `0256a531d..320b39c96`

Independent finder reviewed the shared person-peer selection, viewer identity wiring, sidebar/header/message palette use and the rendered cross-surface regressions. Result: `[]`; no candidate required independent confirmation. Earlier full and patch conclusions remain retained outside this frontend presentation delta. Product acceptance is recorded independently; this code verdict is not a browser-verification claim.


## Chat creation and contact layout patch, round 8

- `validated_at`: `692e5180e8d0584fbe9b79eb914b3082d78a526a`
- `executed_base`: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- `review_mode`: `patch`; `diff_range`: `e8eaf5df7..692e5180e`

Independent finder reviewed the two-action menu, unchanged callback wiring, scoped contact-layout rules, localization and menu interaction regressions: `[]`. No candidate required confirmation; all earlier unaffected gate evidence remains retained. No adjacent-page scan or new full review was performed.
