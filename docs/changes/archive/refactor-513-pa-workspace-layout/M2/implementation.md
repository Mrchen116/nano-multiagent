# M2 implementation record

## Scope

- PA now uses `~/.nanoassistant/config.yaml` as its only default local config
  location and `~/.nanoassistant/workspaces/<agent_id>` for managed Agent
  workspaces.
- `build_pa_kernel()` selects `.nanoassistant` as both the workspace config
  dirname and the explicit product global config root.
- PA-owned workspace state is contained below `<workspace>/.nanoassistant/`:
  memory, `HEARTBEAT.md`, cron data, chat-history JSONL, sessions and the
  kernel-managed capability directories.
- IM independently derives the same managed workspace default.  It continues
  to import neither PA nor Agent code.

## No compatibility path

- The runtime does not read, create, copy, move or synchronize
  `~/.nano-assistant`, `~/nano-assistant/workspace`, workspace-root
  `HEARTBEAT.md`, or workspace-root `chat_history`.
- Existing installations are handled only by the manual deployment runbook;
  this production code has no first-run migration branch.

## Verification

- PA/IM directory, heartbeat, chat-history, local-config and managed-workspace
  suite: 153 passed.
- Added direct factory wiring coverage for PA's workspace and global roots, and
  scoped chat-history coverage proving the kernel-provided config root wins.
- `ruff check` passed for all changed M2 source and test files.
- `git diff --check` passed.

## Delivery follow-up

- Updated the long-lived `prod-fleet-deploy` skill to use only the terminal
  `~/.nanoassistant/` config, secret, state and log paths.
- Added a first-deployment gate that routes unmigrated installations through
  `docs/operations/pa-workspace-layout-migration.md` before any routine or
  partial fleet restart.
- Audited maintained README, architecture, operations and current-spec
  documents: terminal paths and the one-time migration entry are synchronized.
  Old global/default paths remain only where they identify migration sources
  or preserve historical review evidence.
