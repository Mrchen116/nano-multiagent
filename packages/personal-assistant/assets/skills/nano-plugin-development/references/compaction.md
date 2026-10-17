# Compaction

Use `plugin_manager` with `action: describe_api` and `topic: compaction` to locate the installed `dsh-compaction` and `dsh-compaction-basic` READMEs and public declarations. They describe the supported APIs, configuration and summary behavior. When changing summary content, read the basic backend's "Auxiliary summarizer request" section, including its final instruction, before choosing an implementation.

Nano's workspace preset can supply an isolated `compaction` service. Automatic and manual compaction use it; disabling restores Nano's default path. Use native isolate/group rules and the existing workspace overlay. Package updates follow the lifecycle in [bundle.md](bundle.md).

In Nano, manual `/compact` is a user command in the chat, not an Agent tool. Report what is installed and checked, then finish the turn so the user can trigger it while the Agent is idle. Do not reconstruct host control with shell or RPC calls, or inspect other sessions to obtain evidence.

Keep native defaults for ordinary tasks. Report unobserved paths as unobserved; installation or a no-op is not completed compaction. Scale checks to the current request as described in [verification.md](verification.md).
