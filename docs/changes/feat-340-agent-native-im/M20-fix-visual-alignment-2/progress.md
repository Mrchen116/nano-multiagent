# feat-340-M20 — Progress

fix-visual-alignment-2 (post-acceptance fix round 12-bis) — 8 issues (4 major + 4 minor) visual alignment fix. Last round before escalate.

> Task list: `tasks.md`; R12-bis evidence: `../acceptance-r12-evidence/actual-redo/*.png`; prototype: `../attachments/prototype/project/im-{chat,settings,extra,mypage,components}-page.jsx`.

## R0 — Baseline & Plan

- Context: R12-bis reviewer verdict after deploy fix: 0 精 / 5 近 / 4 偏 / 0 零, 8 issues (4 major + 4 minor). M19 worker self-claimed 9/9 精 but was on stale dist. This is round 7, last fix-implementation before escalate.
- Decision: 7 roadpoints: R1 Agents rail → R2 Nodes Save → R3 Account overflow + display_name → R4 Display Name helper + Agents mobile title → R5 Mobile Me subtitles → R6 Avatar rounded-full audit → R7 Build + deploy + playwright + self-review.
- Rationale: Major issues first (R1-R3), minor polish next (R4-R6), deploy verification last (R7). Each roadpoint TDD C1+C2+C3.
- Evidence: Baseline tests 52 files / 293 tests GREEN.
- Rollback: `git checkout f7bc01e6 -- docs/changes/feat-340-agent-native-im/M20-fix-visual-alignment-2/`
- Commits: (this section)

<!-- R1 ~ R7 filled per roadpoint -->
