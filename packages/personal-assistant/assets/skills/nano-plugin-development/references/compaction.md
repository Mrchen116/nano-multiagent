# Compaction

Query `compaction` and read the installed `dsh-compaction-basic` README and public declarations. Prefer the existing `BasicCompactionEngine` and its configuration. For a custom summary, use its public `summarize` hook and preserve native transactions, cancellation and tool pairing; do not replace session history yourself.

Nano's workspace preset can supply an isolated `compaction` service. Automatic and manual compaction use it; disabling restores Nano's default path. Use the native isolate/group rules and the existing workspace overlay. Installing a replacement package still follows the normal restart requirement.

In Nano, manual `/compact` is a user command in the chat, not an Agent tool. Finish the current turn, report what is installed and checked, and let the user trigger it before continuing verification. Do not reconstruct host control with shell or RPC calls, or inspect other sessions to obtain evidence.

Keep normal native thresholds and retention defaults for ordinary tasks. Verify the requested summary behavior with useful test history and manual compaction, then continue the conversation. If automatic compaction has not occurred, say it was not observed. Do not lower thresholds repeatedly or start a stress test just to force a success claim. A no-op or a discovered engine is not a completed compaction.
