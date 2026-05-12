# feat-340-M20 — Tasks

## Goal
Fix R12-bis 8 issues (4 major + 4 minor) to reach 9/9 viewport "精" on deploy-fix verified build. Last fix-implementation round before escalate.

## Exit Criteria
- R12-bis-1: Agents detail 1440 viewport has left 240px agent rail (split layout, dark rail, click-to-switch)
- R12-bis-2: Nodes Save button is card-level small pill (not full-width teal), plus "+ New agent on node" button and "All saved" footer status text
- R12-bis-3: Account 375 viewport no horizontal overflow (Default chip + node_id mono truncate/wrap)
- R12-bis-4: Account user ID field shows display_name (not raw UUID)
- R12-bis-5: Agent Detail Display Name field has helper text "Shown in conversations and group chats"
- R12-bis-6: Mobile Me Nodes/Account rows have subtitles; remove "Enable desktop notifications" row
- R12-bis-7: Agents 375 viewport title centered
- R12-bis-8: All avatars rounded-full (audit: Account avatar, Conversation list avatar, Mobile Me avatar, v2 sidebar Avatar, agent-detail header avatar)

## Test Strategy
- Frontend visual-only changes. No new E2E. Update existing component tests for changed assertions.
- Browser QA: playwright screenshots of 9 viewports after build + deploy.
- Dist grep verification: each issue must leave at least one testid in bundle.

## Roadpoints
- **R1**: R12-bis-1 Agents detail desktop split layout (240px dark agent rail)
- **R2**: R12-bis-2 Nodes card-level Save pill + New agent button + All saved footer
- **R3**: R12-bis-3 Account 375 overflow fix + R12-bis-4 display_name fix
- **R4**: R12-bis-5 Display Name helper text + R12-bis-7 Agents mobile centered title
- **R5**: R12-bis-6 Mobile Me subtitles + remove notifications row
- **R6**: R12-bis-8 Avatar rounded-full audit + fix
- **R7**: Build + dist grep + deploy + playwright 9 viewport screenshots + self-review
