# M1 implementation record

## Scope

- Added core `WorkspaceLayout` and immutable `WorkspaceExecutionScope`.
- Moved workspace tools and hooks from build-time discovery to a cached SDK
  capability resolver keyed by canonical workspace root.
- Each turn now carries its selected scope through hook dispatch, tool execution,
  slash skills, background forks, compaction prompt construction and tool-result
  compression; the shared engine and LLM client graph remain shared.
- Added optional `build_kernel(global_config_root=...)`.  Omission passes no
  deployment-global config to auto-mode; the selected workspace config is always
  supplied.
- Routed bash policy and background output through the current scope.  The output
  port now receives an explicit output root rather than deriving `.nano` itself.

## Intentional details

- The shared hook registry clones registrations but shares extension state.  This
  retains the session-event publisher binding while preventing workspace hook
  registrations from leaking between Agent workspaces.
- The shared tool base reuses built-in/native/global instances.  Only a scope's
  execution context and workspace-loaded tool objects are new.
- Scope discovery is first-use cached.  Filesystem changes therefore take effect
  on the normal product restart, rather than during an active process.

## Verification

- Baseline before M1: 146 passed in 1.39s.
- Focused M1 suite: 33 passed (`test_workspace_execution_scope`, workspace tool
  override, SDK contracts and bash engine).
- Cross-channel foreground/background suite: 5 passed; background output is
  asserted under `.nanocode/background-tasks`, with no `.nano` fallback.
- `ruff check` passed for all changed M1 source and test files.
- The broader adapter suite has one known sandbox-only failure: its child shell
  invokes `/bin/ps`, which macOS sandboxing denies.  The same command directly
  reports `Operation not permitted`; this is unrelated to output-root behavior.
