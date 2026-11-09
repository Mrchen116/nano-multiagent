---
name: verify-context-cache-prefix
description: Run the TLC model for the Global and Personal Agent root prompt prefix after tool returns, configuration changes, pruning and window rollover.
---

# Verify the context cache prefix

Use this check when changing request assembly, tool result projection, configuration application, or native context window handling for a Global or Personal Agent root. Unexpected changes to previously sent context can force the provider to process the changed prefix again.

## Run

With Java 11 or newer and the [TLC v1.7.4 release jar](https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar), run from the repository root:

```sh
TLA2TOOLS=/absolute/path/to/tla2tools.jar python3 .agents/skills/verify-context-cache-prefix/check.py
```

For a counterexample or chart, use pstack's `/statechart` with `ContextCachePrefix.tla` and `ContextCachePrefix.cfg` in a scratch directory. Replay its actions against the corresponding source and request capture below before calling a model finding a product bug.

## Property

`NoSilentPrefixRewrite` compares consecutive model requests. The previous message sequence must stay a prefix, adjusted only at the exact result position replaced by a prune or at a committed window rollover. Explicit tool selection and persona changes permit changes only to their respective request fields. A configuration change does not authorize rewriting message history. After each request, the check forgets the permissions granted by earlier changes.

The model explores one root at a time with the Global or PA identity, at most four emitted requests and two sequential tool calls, one configuration update, one replacement of an eligible tool result, and one successful native rollover. Message entries carry identity and a symbolic payload kind. Prune eligibility and rollover pressure are abstracted as possible events at a safe boundary. The model groups the publication of a replacement persona into one step and allows the asynchronous configuration stages to interleave with request handling after the initial idle gate.

The model covers one fixed provider route and its logical content. It leaves out provider serialization, cache markers, token budgets, cache reads, retries, concurrent tool batches, process restart, third-party plugins and other context-changing events. These bounds belong to this model and do not define the product contract.

## Code and replay

Last checked against source commit `d286fa11e` and its lockfile, with DSH `0.2.1-alpha.1` and `dsh-agent-context` `0.3.0-rc.9`. On a covered change, inspect the owning code and replay the relevant requests before advancing the sync commit.

| Model actions | Source and corresponding evidence |
|---|---|
| `UserInput`, `StartTool`, `ToolReturn`, `FinishReply`, `EmitRequest` | DSH `dsh-agent-loop` records the assistant tool call and durable `tool/result`, then builds the next model request from the session surface. [Nano's pre-step hook](../../../packages/dsh-integration/src/context-order.ts) reorders the incoming environment batch. [Global and PA fork wire fixture](../../../packages/dsh-integration/tests/fork-prefix-provider.test.ts) captures the root request before and after tool results, and across subsequent turns. |
| `RestrictSelection`, `BeginIdleConfigApply`, `ApplyPersona`, `ApplyTools` | [Configuration apply handler](../../../packages/dsh-integration/src/index.ts) restricts choices before waiting for idle. [ConfigurationScopes](../../../packages/dsh-integration/src/agent-config.ts) and [ToolSelection](../../../packages/dsh-integration/src/capabilities.ts) publish persona and tool changes. [Configuration tests](../../../packages/dsh-integration/tests/capabilities.test.ts) observe the immediate restriction and deferred persona update. [Context order wire fixture](../../../packages/dsh-integration/tests/context-order-provider.test.ts) observes a new persona and retained history. |
| `PruneToolResult` | The pinned `dsh-agent-context` calls the host pruner in `prunePressure()`. DSH records a `compaction/prune` and replaces the selected `tool/result` surface. [Short ID fixture](../../../packages/dsh-integration/tests/context-short-ids.test.ts) exercises the native pruner and observes the shorter tool result and recovery of the original. |
| `RollWindow` | The pinned `dsh-agent-context` validates the paired range and replaces it in `commitRollover()`. [Context revalidation wire fixture](../../../packages/dsh-integration/tests/context-revalidation-provider.test.ts) runs a real native reset and observes its durable event and the next request. |

The fixtures for configuration, pruning and rollover provide evidence for individual actions at different boundaries. They do not execute the entire modeled interleaving matrix separately for both identities.

To check sensitivity, in a scratch copy change `ToolReturn` so that it overwrites the first history entry before appending the result. With the unchanged invariant, TLC should reach `UserInput → EmitRequest → StartTool → ToolReturn → EmitRequest` and report a message prefix violation.

On the recorded baseline, TLC exhausted 9,032 distinct states. The scratch mutation produced the five-step counterexample with each identity checked separately. Replacing the old user text in a copy of the captured post-tool HTTP request also failed the existing wire prefix assertion for both identities.
