# Delivery — feat-554

## Final synchronization and retained gates

Final fetch on 2026-09-14 found `origin/main` unchanged at `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`, also the current merge-base. There is no new main delta to integrate or conflict resolution to validate. This is an observed base comparison, not a conclusion inferred from conflict-free merging.

At the ordinary-gate handoff, `effective_base` is that same SHA and `effective_through` is `fc114a19bbc1c80704f144b0e8c85f5d1b058e84`. The original execution snapshots remain unchanged:

| Gate | Actually validated at | Result and retained scope |
|---|---|---|
| Independent product acceptance | `513ee21637917dabe16f2f2080136ed63510f7d9` | Pass, 18 implementation-period scenarios. Later `274ad07bc` only repairs current-chat hosted-reference reuse; its new SDK regressions, 76 related tests, independent code closure and verifier analysis establish that the previously exercised local image, browser and collaboration paths remain valid. The receipt-reuse branch is not claimed as a later live product run. |
| Independent implementation verifier | `274ad07bc61bb0f17eb9bee8708f1f37bec83ebd` | Pass, critical/warning/suggestion all zero; full coverage retained with targeted closure. The subsequent test split and reports do not change product behavior. |
| Independent code review | `c3046c6a2` | Pass, no surviving findings; original full coverage plus bounded patch and independently confirmed finding closure. Subsequent changes to this handoff are reports only. |

Every gate's original `executed_base` is `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`. See [acceptance](acceptance.md), [verification](verification.md) and [code review](code-review.md) for actual snapshots and evidence. The PR records the final effective SHA after corrected-delta verification and mechanical documentation merge/archive; no final-head SHA is substituted for the versions actually executed.

## Contract correction

After ordinary gates passed, the delta adds the actual external sender identity in place of two obsolete “you” promises, the supported explicit image entrypoint for existing conversations, and viewer-specific default human-direct titles. The independent corrected-delta check additionally closed two document mismatches: configuration-boundary visibility follows chat membership, and reserved runtime usernames cannot be registered as people. It preserves the applicable original scenarios.

Corrected-delta `validated_at` is `a16f6d37c75ed62ed04335ce6592bdacdafb69b0`; outcome **aligned**, report commit `ec99b1809077b58b21f7737cf073127f486361a0`. All eight target areas were then mechanically merged: 15 MODIFIED, 11 ADDED and 5 REMOVED operations. A structural comparison verified exact corrected bodies, only the required link rebasing, and preservation of every unrelated requirement. IM Purpose, area summaries/counts and alignment markers were synchronized. The root `SPEC.md` import boundaries and its general multi-user isolation description remain accurate and unchanged.

The last fetch before canonical merge again found the same main SHA. The changes since ordinary gates are contract corrections/reports and mechanical documentation operations; product source stays `274ad07bc` and test behavior stays `c3046c6a2`. All ordinary conclusions remain effective; corrected-delta is an additional independent gate, not a replacement for them.

## Validation and cleanup

- Full local Python partitions: **1882 + 1977 = 3859 passed**. Frontend: **753 passed in 80 files**; TypeScript/Vite build passed. The required critical dependency-audit gate passed, with no dependency change.
- Source Ruff, format and whitespace checks passed. Merged documentation integrity passed with 251 maintained sources and 73 required routes. After archive, documentation integrity passed with 233 maintained sources and the same 73 routes; the archive checker, all 156 contract tests, Ruff/format and whitespace checks passed. Required remote CI is checked on the Ready PR.
- Reviewer closed its five browser sessions; root closed its own session. Root verified and stopped only task-owned A1/A2/C1/IM PIDs 41363/41365/41367/57800, removed the isolated runtime/data/Skill root and its 60 local screenshot/evidence cache files. The 510 daily Skill files exactly match their pre-run hashes. Both temporary missing-source tests restored the original hash before cleanup.
- The independent verifier removed its own worktree. Root's delivery worktree is retained only through PR/CI handoff and then removed by root. Main and unrelated worktrees are preserved. The original prototype at `http://127.0.0.1:18554/prototype.html` still returned 200 after stopping the dedicated test stack.

Private runtime paths and screenshot names in earlier reports describe evidence actually observed during acceptance; those disposable files are not committed or retained as production state. No test configuration, token, database, PID, build artifact or generated Skill enters the PR.

## Archive handoff

The complete 19-file unit is under `docs/changes/archive/feat-554-multi-user-multi-gateway-im`; only its former empty milestone placeholder was retired after implementation evidence existed. A path-set comparison confirms no unit artifact was lost, all relative document links resolve, and the prototype bytes are unchanged by archive. The canonical merge commit is `78a260048`; the archive change rebases relative links and records these checks, without changing implementation or test behavior. The final PR head is the ultimate `effective_through` for the retained ordinary and corrected-delta gates, with the original execution snapshots preserved above and in their reports.

## Deployment boundary

This delivery prepares a reviewable PR. It does not merge, deploy, convert a live database or alter daily services. [migration-prompt.md](migration-prompt.md) is the only legacy-data conversion deliverable; no new migration program, startup backfill, dual-write or old-public-URL compatibility path was added. Ordinary txt attachments retain the pre-existing Agent input limitation documented as SF1 in acceptance; browser upload/download/history/fork paths passed.


## User preview follow-up: public profile consistency

The restored user preview exposed a visual gap between colleague Agent profiles and the original owner detail page. `255903e3ef4771cde484d2606decf4d119d444e7` reuses the original page's header, avatar sizing, tab styling, action styling and centered cards. This is a correction within feat-554's existing UI-preservation requirement. The public/management eligibility rules, returned data, message creation and Work APIs do not change; no canonical or delta-spec correction is needed.

- Independent product acceptance Round 3 validates the affected public-profile, owner-page comparison, 390/767/768 navigation, English/Chinese, Work and ordinary-chat entrypoints at `255903e3e`: pass, zero blocking/major. The original 18-scenario execution evidence remains at its original snapshots. SF2 records a minor 4px phone overflow also visible on the unchanged owner detail page; it is not represented as fixed by this patch.
- Independent code review Round 6 validates `a7610b283..255903e3e`: `[]`. There was no candidate requiring independent confirmation. Earlier full/closure coverage remains valid outside this bounded JSX/CSS/test-label delta.
- The implementation verifier at `274ad07bc` and corrected-delta verdict at `a16f6d37` retain their unchanged functional/contract scope. The patch preserves all data-loading, ownership and mutation paths and removes only the abandoned public layout styles; the existing public-entrypoint tests and targeted independent product review cover the affected presentation. No protocol, permission, persistence, Gateway, shared execution, migration or deployment code changed, so those gates are not rerun as a new full implementation audit.
- All 753 frontend tests / 80 files and TypeScript/Vite build passed for the new source. Documentation integrity and archived-unit checks passed. Full Python and dependency-audit evidence is retained because Python and manifests/lockfiles did not change. Required remote checks are followed on PR #297.

A fresh `git fetch origin main` again found `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`, so `effective_base` remains unchanged. The new product/code execution snapshot is `255903e3ef4771cde484d2606decf4d119d444e7`; following commits only append these reports. The Ready PR records the final `effective_through` without replacing any gate's historical `validated_at`.

The old full-acceptance runtime remains cleaned as previously documented. A separate preview was subsequently restored at `.worktrees/unit-feat-554/.e2e-preview` for the user's explicit request and is now retained, serving `http://127.0.0.1:54719` with the updated frontend. Its IM and three Gateways were not restarted by this UI repair. Root and independent reviewer closed only their own verification browser sessions. Worktree, local screenshots, temporary configuration and data remain for user feedback and are not committed; cleanup is deferred until the user finishes the requested experience.


## User preview follow-up: person avatar colors

`320b39c96c6be1c7f4d247cca405a0dd058168fd` closes the user's report that 小李 had different avatar colors in the chat sidebar and message pane. Those surfaces now use the palette already used by contacts and mentions, with the other human participant as the direct-chat avatar identity. This corrects the existing unified-avatar requirement; no new product or access rule is introduced.

The two rendered regression cases failed on the original fixed sidebar color, then passed across both viewer identities, an edited chat title, and group messages. All 116 affected tests and all 755 frontend tests / 81 files passed. TypeScript/Vite build, documentation integrity and archived-unit checks passed. The preview serves the resulting `index-D3V5Y4tm.js`; CSS is unchanged. Independent code review Round 7 returns `[]` on `0256a531d..320b39c96`.

The original implementation-verifier and corrected-delta evidence remain valid for their unchanged data-loading, membership, protocol, persistence and Gateway scope. This delta only selects an avatar name/color in existing frontend views, wires the already available viewer identity into the sidebar, and verifies rendered consistency. The existing unified-avatar current requirement already covers the correction, so no canonical rewrite or migration deliverable is needed. The independent targeted browser result below owns the affected visual scope; older scenario executions are not relabeled as fresh runs.

A fresh fetch still resolves `origin/main` to `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`; `effective_base` is unchanged. The product source snapshot is `320b39c96c6be1c7f4d247cca405a0dd058168fd`; subsequent commits append reports only. The Ready PR records the final effective-through SHA and required remote CI. The temporary IM and three Gateways remain running for the user's requested experience; no private runtime data, screenshot or build artifact is committed.

Independent product acceptance Round 4 passed the affected avatar comparisons on desktop and 390px mobile: sidebar, header, existing direct/group messages, contacts and mention candidates use matching colors. The phone contact display was checked by opening contacts on desktop before resizing; the reviewer separately observed an existing overlapping New chat / Group control at 390px and does not claim that phone entrypoint passed. This adjacent layout issue is recorded separately, not treated as a new avatar failure or an excuse to broaden the requested review.


## User preview follow-up: creation controls and contacts

The user subsequently asked to repair the overlapping/duplicated plus controls and contact-name alignment. `692e5180e8d0584fbe9b79eb914b3082d78a526a` supplies one icon menu for the same two creation actions and a left-aligned, full-width contact list with a single header row. The existing chat/group flows, API calls, identity rules and canonical contracts are unchanged, so the implementation-verifier/corrected-delta evidence retains that scope. Independent code review Round 8 returns `[]`; Round 5 in acceptance.md records only the affected real desktop/mobile pages and SF3 closure. All 756 frontend tests / 81 files and the new build passed. The temporary preview remains available for the user, and the changes are included in the existing Ready PR #297 without merging or deploying.
