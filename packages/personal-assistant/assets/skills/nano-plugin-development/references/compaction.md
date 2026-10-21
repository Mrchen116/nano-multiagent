# Compaction

Use `plugin_manager` with `action: describe_api` and `topic: compaction` to locate the installed `dsh-compaction` and `dsh-compaction-basic` READMEs and public declarations. They describe the supported APIs, configuration and summary behavior. When changing summary content, read the basic backend's "Auxiliary summarizer request" section, including its final instruction, before choosing an implementation.

In Nano Global Mode, human chat messages arrive through Inbox tool results. Filtering only `role: user` can miss those messages and select harness guidance instead. A deterministic extractor must distinguish human messages in the Inbox data; verify the requested business facts in the actual checkpoint, not just a section heading.

Nano's workspace preset can supply an isolated `compaction` service. Automatic and manual compaction use it; disabling the selected engine restores the next active preset engine or Nano's original summary path. Use native isolate/group rules and the existing workspace overlay. Package updates follow the lifecycle in [bundle.md](bundle.md).

In Nano, manual `/compact` is a user command in the chat, not an Agent tool. Report what is installed and checked, then finish the turn so the user can trigger it while the Agent is idle. Do not reconstruct host control with shell or RPC calls, or inspect other sessions to obtain evidence.

Keep native defaults for ordinary tasks. Report unobserved paths as unobserved; installation or a no-op is not completed compaction. Scale checks to the current request as described in [verification.md](verification.md).

## Agent-managed context

[`dsh-agent-context`](https://github.com/Mrchen116/dsh-agent-context) is Nano's default compaction bundle for existing and new Agents, including Personal and child Agents. Nano ships a fixed prebuilt release tarball through its runtime dependency lock; users do not need a per-workspace installation. Use the existing `list_bundles` and `set_bundle` controls to inspect or disable it. A shipped bundle is updated with Nano, not replaced by installing another copy into the workspace. Do not install a floating branch, add its source as a Nano submodule, disable the Host compaction row, or edit the Host agent preset roster. The bundle owns an isolated `compaction` service in this workspace; Nano's existing plugin lifecycle supplies activation and fallback.

The bundle contributes `notes`, `history`, `new_context` and `get_context_remaining`. Follow their live schemas. `new_context` takes no handoff text: save a checkpoint with `notes` first. Fresh windows keep effective instructions and runtime state, with a short notes index; old conversation tails and note bodies are recovered explicitly. `history` reads only records outside the active context and preserves original message/tool provenance. Notes and history are scoped to the current execution session, not a shared workspace knowledge base, and do not grant authorization for subsequent actions.

Verify the four tools and an actual continuation across a window boundary. Keep “package installed”, “bundle applied”, and “task continued correctly” separate. Check `get_context_remaining` when planning a long task; estimates are not exact provider usage. Disabling the bundle restores the original summary compaction path for future work without deleting its saved notes or the session log. Re-enabling can recover those records; it does not reconstruct the previous active conversation automatically. Package replacement still follows the restart requirement above.

The four context tools remain available with an empty business tool selection and Auto off, because they only manage the current execution session. They do not grant business tool access or authority from recovered content. Explicit downstream denials still apply. Workspace disable choices persist across restart; toggling one workspace does not change another. Disable the default bundle before selecting another compaction engine.
