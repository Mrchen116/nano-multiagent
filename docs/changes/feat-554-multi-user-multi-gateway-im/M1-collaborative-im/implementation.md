# M1 implementation

## Scope and baseline

User selected `change-orchestrator-simple`. Worktree: `.worktrees/unit-feat-554`, branch `unit/feat-554`, initial `origin/main` / executed base `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`. Gate 2 Round 11 is Approved, 0/0; source unit files matched the reviewed hashes before copying. Approved artifacts were committed as `8df3c1e4d`; main checkout and its unrelated work remain untouched.

The single vertical milestone is implemented in this shared unit worktree with explicit file owners: frontend, conversation storage/API, PA data consumers, and root IM runtime/resources/permissions. These are implementation tasks, not additional milestones. Independent validation has not run yet. No migration program is created; actual old-data conversion and deployment remain outside this implementation run.

## Evidence recorded during implementation

- Gateway runtime token integration: a new HTTP/WebSocket regression failed on the missing registration token, then additionally exposed the unauthenticated policies route. Registration-scoped token rotation and human-only policy authentication now pass this test. No machine credential grants account/config access.
- Ordinary attachment regression failed because upload returned public `/im/uploads`; it now passes protected conversation resources, member download and refusal of a copied URL by a nonmember.
- PA task `0bbcc0591`: scoped red cases turned green; final affected 105 tests passed. Earlier broad PA run had 1302 passes and six old fixture signature failures; those fixtures were updated and affected tests rerun. This is automated evidence, not a real Gateway/model journey.
- Conversation task has reported new member/preference and ordinary-DM concurrency tests passing; frontend and remaining runtime work are still in progress. Final commands, commits and independent results will replace this interim status.

## Verification boundaries and remaining work

Complete integration and affected-test updates, run required local CI, then exercise the three-account/three-node browser and model journey. A local everyday Gateway is active; the shared user Skill root must not be changed by verification. Follow the reviewed runbook's actual-root isolation and cleanup requirement before starting any new Gateway.

After implementation: freeze a clean unit HEAD for independent product reviewer, verifier and code review; resolve only established blockers, final-sync, correct and verify deltas, merge canonical specs, archive the complete unit, publish a ready PR and wait for required CI. No automatic merge or deployment.
