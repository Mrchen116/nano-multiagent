# feat-446-fix-r2-product — Tasks

## Goal

Close Round 2 product issue `R2-I3` and the related frontend gating regressions by keeping F2 distill selection honest: disabled conversations must never be preselected, zero-eligible selection must surface a recoverable notice, and execution-agent preflight must require both `conversation-skill-distiller` and `skill_view`.

## Exit Criteria

- [x] Right-clicking a `running` / `No transcript` conversation does not preselect it in distill mode.
- [x] Distill mode shows a clear recoverable notice when no eligible conversation is selected.
- [x] Starting distillation requires both the distiller skill and `skill_view` for the execution agent before creating the new conversation.
- [x] Focused frontend tests cover the disabled-row, no-silent-no-op, and missing-`skill_view` cases.
- [x] Narrow frontend validation and browser evidence are recorded in `progress.md`.

## Test Strategy

- Behaviors under test: disabled rows stay unselected, no-op becomes visible notice, execution agent preflight rejects missing `skill_view`, and the existing missing-distiller guard still blocks conversation creation.
- Existing coverage extended in:
  - `src/IM/frontend/src/features/chat/v2/components/conversation-sidebar.test.tsx`
  - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`
- Validation commands:
  - `npm run test -- src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/chat-workspace.integration.test.tsx`
  - `npm run build`
- Browser evidence: Playwright smoke against the isolated worktree stack, confirming the inline notice + disabled unchecked row state after right-clicking a no-transcript conversation.
