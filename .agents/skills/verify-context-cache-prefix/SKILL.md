---
name: verify-context-cache-prefix
description: Model-check and replay cache prefix changes for Global and Personal Agent root requests, including recovery and adapter effects.
---

# Verify the context cache prefix

Use this check when changing the inputs to consecutive Global or PA root requests, how DSH replays them, or how a provider adapter serializes them.

## Run

With Java 11 or newer and the [TLC v1.7.4 release jar](https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar), run from the repository root:

```sh
TLA2TOOLS=/absolute/path/to/tla2tools.jar python3 .agents/skills/verify-context-cache-prefix/check.py
```

The default run checks `baseline`, `mixed`, and `image` and exits nonzero if the property fails. Pass one case name to rerun it or `--agent Global` or `--agent PA` to isolate an identity. To render a trace, use pstack's `/statechart` with the module and its scenario configuration in scratch space.

Replay the key traces through the actual DSH runtime and Anthropic Messages serializer, to an isolated local server:

```sh
pnpm exec vitest run packages/dsh-integration/tests/context-cache-prefix-provider.test.ts
```

The replay checks successive requests with images within the default route budget.

## Property and bounds

`NoSilentPrefixRewrite` requires the old ordered message content to be a prefix of the next request and checks the system, tool and route fields against their expected values. An explicit configuration apply or plugin registration grants only its modeled header change; a different route does not exempt message changes. Native pruning permits replacement of the selected result only. A committed rollover installs the expected new baseline; legacy summary replacement retains the tail outside its committed range. No PA event, parallel tool result, failed attempt, ordinary restart or route change grants a history rewrite.

Image requests are in scope when all Base64 image data in the assembled request, including historical images, totals at most 20 MiB before recovery. Within this budget the existing image blocks must stay in the prefix. Requests that trigger DSH image offload by exceeding that budget are outside this property.

The root model enumerates both identities. `baseline` allows four model requests, four calls in batches of one or two, and two distinct change or recovery events. `mixed` allows three requests, two calls, and four distinct change or recovery events. `image` allows three requests, two calls, and two distinct change or recovery events, with image input enabled. Payload identity and ordered schema shape are symbolic, and the image case assumes its assembled requests fit the budget. Each change or recovery event class is used at most once per run. Independent tools can settle in either order, with success, error or abort. Intermediate durable writes before the batch is complete are collapsed because the next request waits for the exchange. The model assumes a durable restart at a quiescent boundary, and abstracts pressure eligibility and the safe cut of an already committed rebuild. One incoming environment batch stands for Skill, runtime, and other ordinary injected inputs. A PA state notice has its own next-turn admission. The model does not interpret arbitrary installed plugin code or prove every production adapter implements the same projection. For a new writer or adapter, map its effects to a modeled transition and replay its actual output before treating it as verified. The wire replay ignores `cache_control` annotations. Cache hit policy and proxy/provider behavior beyond the captured endpoint are outside the property.

## Code and replay

Last checked against product source `e11661f18` and its lockfile: DSH `0.2.1-alpha.1`, dsh-agent-context `0.3.0-rc.9`, pi-ai `0.87.1`. Product source is unchanged from `d286fa11e` (only the initial model and skill changed). Inspect the owning code and replay relevant requests before advancing this reference.

| Path | Implementation and evidence |
|---|---|
| User and environment input, tools, errors and retries | [ContextOrder](../../../packages/dsh-integration/src/context-order.ts) orders new inputs; DSH `dsh-agent-loop` prepares calls, commits ready results in assistant order, synthesizes results for skipped calls and waits for the batch before building the next request. Native `dsh-llm-retry` retries the current step. The [wire replay](../../../packages/dsh-integration/tests/context-cache-prefix-provider.test.ts) checks a real HTTP 529 retry, two concurrent tools (one fails), their serialized result order, and the next turn for both identities. |
| PA source policy, membership and security notices | [GlobalAgent](../../../packages/personal-assistant/src/global-agent.ts) refreshes memory source eligibility and submits surfaced policy/membership/security notices as `personal-state` followups; the [personal_sources tool](../../../packages/dsh-integration/src/personal-security.ts) stops later access without erasing previously read context. The wire replay exercises admission of a PA followup, not the upstream IM event producers. |
| Configuration, route, plugin publication | [Configuration apply](../../../packages/dsh-integration/src/index.ts) restricts choices before waiting for idle; [ConfigurationScopes](../../../packages/dsh-integration/src/agent-config.ts), [model policy](../../../packages/dsh-integration/src/model-policy.ts), [fallback](../../../packages/dsh-integration/src/model-fallback.ts) and [workspace plugins](../../../packages/dsh-integration/src/workspace-tools.ts) publish individual changes. [Context order wire replay](../../../packages/dsh-integration/tests/context-order-provider.test.ts) checks persona update with history retained. The plugin action stands for an authorized catalog change; plugin code can own other writers, which need their own audit. |
| Same-configuration restart | [Root fork replay](../../../packages/dsh-integration/tests/fork-prefix-provider.test.ts) shuts down and reopens the runtime and compares consecutive root requests. |
| Prune, reset and summary | Native dsh-agent-context `prunePressure()` and `commitRollover()` select the exact surface edit; [short IDs](../../../packages/dsh-integration/tests/context-short-ids.test.ts) and [native reset](../../../packages/dsh-integration/tests/context-revalidation-provider.test.ts) exercise those boundaries. [NanoCompaction](../../../packages/dsh-integration/src/compaction.ts) delegates legacy summary replacement to DSH BasicCompactionEngine. |
| Image bytes | DSH `dsh-llm-pi-ai` uses a 20 MiB default budget for all Base64 image data in a request. The [wire replay](../../../packages/dsh-integration/tests/context-cache-prefix-provider.test.ts) sends two images on consecutive turns and compares the complete previous request prefix, including the first image. |

## Results

- The original model passed at 9,032 distinct states. The expanded text/recovery state space exhausted 4,528,782 states (`baseline`) and 2,869,740 (`mixed`), with no invariant violations. Scratch fault modes independently rewrote an old message during a parallel batch or PA event, changed the system prompt at restart, and published the wrong tool list during config apply. All were rejected by TLC.
- The earlier over-budget replay observed DSH replacing an already sent image with a text reference. The current property excludes this recovery case. The `image` case exhausted 525,033 distinct states with no invariant violations. In a scratch copy, rewriting the first image when a second one arrived caused TLC to reject the next request.
