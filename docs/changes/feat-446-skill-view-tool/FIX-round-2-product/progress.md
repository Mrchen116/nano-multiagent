# feat-446-fix-r2-product — Progress

## Fast-lane note

- Reviewer feedback loop fix. 省略 §0.4 三提交，理由：本轮是单点前端产品修复，范围收敛在 F2 distill 选择/预检路径与对应回归测试，可由单个可回退提交承载。

## R1 — Distill selection and preflight guardrails

- Context: Round 2 acceptance `R2-I3` showed that the F2 entry was reachable but still product-broken: right-clicking a `No transcript` row entered distill mode with the disabled row checked, the primary action could appear usable with zero eligible inputs, and execution-agent validation only checked the distiller skill even though the actual flow also needs `skill_view`.
- Decision: Centralize distill eligibility in a shared helper, drive the sidebar primary-button state from eligible selections instead of raw ids, surface an inline recoverable notice when the user targets an ineligible conversation, and extend the execution-agent preflight to require both `conversation-skill-distiller` and `skill_view` enablement before creating the draft conversation.
- Rationale: The acceptance failure was caused by state drift between three frontend checks that were meant to describe the same product rule. Reusing one eligibility predicate removes that drift, and the stricter preflight prevents the UI from creating a conversation that cannot execute the prefilling contract.
- Evidence:
  - Tests:
    - `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/chat-workspace.integration.test.tsx` → 39 passed.
    - `npm run build` → passed.
  - Entry:
    - Distill mode now refuses to preselect an ineligible conversation when entered from the context menu.
    - Execution-agent preflight now blocks both missing-distiller and missing-`skill_view` cases before `POST /im/v1/conversations`.
  - Frontend State Matrix:
    - default: normal conversation list still renders unchanged outside distill mode.
    - disabled: `running` and `No transcript` rows stay disabled and unchecked.
    - error: inline recoverable notice appears when no eligible conversation is selected; modal error appears when the execution agent lacks the required skill/tool.
    - submitting: unchanged; `Start distillation` still disables while pending.
    - missing/nullable data: rows missing `source_agent_id` or `source_jsonl_path` are treated identically to `No transcript`.
    - mobile viewport: N/A in this round.
    - desktop viewport: covered in browser smoke below.
  - Browser QA:
    - Isolated stack started via `./scripts/e2e-up.sh` in a persistent shell because non-persistent shells still tear the IM process down after startup.
    - Real browser smoke against `http://127.0.0.1:60295/chat`:
      1. Log in as `nano / nano1234`.
      2. Seed a no-transcript direct conversation via REST.
      3. Right-click `Distill smoke no transcript` → `Distill to skill`.
      4. Verify the action bar shows `Cancel` + disabled `Distill to skill`, the inline notice says `Select at least one finished conversation with a transcript.`, and the row checkbox is disabled and unchecked with `No transcript`.
  - E2E/Regression:
    - `src/IM/frontend/src/features/chat/v2/components/conversation-sidebar.test.tsx`
    - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`
  - Visual/Interaction:
    - Playwright page snapshot after the context-menu flow showed `Cancel` + disabled `Distill to skill`, an inline `Select at least one finished conversation with a transcript.` alert, and a disabled unchecked `No transcript` checkbox for the seeded conversation.
- Rollback: Revert the single fast-lane commit for `feat-446-fix-r2-product`.
- Commits: single fast-lane milestone commit on `milestone/feat-446-fix-r2-product`
- Next: merge the milestone branch into `unit/feat-446`, push, then remove the milestone worktree and branch.
