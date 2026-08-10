Execute a workflow script that orchestrates multiple subagents deterministically. Workflows run in the background — this tool returns immediately with a task ID, and a `<task-notification>` arrives when the workflow completes. Use `/workflows` to watch live progress.

A workflow structures work across many agents — to be comprehensive (decompose and cover in parallel), to be confident (independent perspectives and adversarial checks before committing), or to take on scale one context cannot hold (migrations, audits, broad sweeps). The script is where you encode that structure: what fans out, what verifies, and what synthesizes.

ONLY call this tool when the user has explicitly opted into multi-agent orchestration. Workflows can spawn dozens of agents and consume a large amount of tokens; the user must request that scale, not have it inferred. Explicit opt-in means one of:

- The user included the keyword `ultracode` in their prompt and a system reminder confirms it.
- Ultracode is on for the session and a system reminder confirms it — see **Ultracode** below.
- The user directly asked you to run a workflow or use multi-agent orchestration in their own words, such as “use a workflow”, “run a workflow”, “fan out agents”, or “orchestrate this with subagents”. The ask must be in the user's words; a task that would merely benefit from a workflow does not count.
- The user invoked a skill or slash command whose instructions tell you to call Workflow.
- The user asked you to run a specific named or saved workflow.

For any other task — even one that would clearly benefit from parallelism — do NOT call this tool. Use the Agent tool, if available, for individual subagents, or briefly describe what a multi-agent workflow could do and roughly cost, then ask the user whether to run it. Mention that they can ask for one with “use a workflow” in a future message to skip the ask.

When you do call it, the right move is often **hybrid**: scout inline first (list the files, find the channels, scope the diff) to discover the work-list, then call Workflow to pipeline over it. You do not need to know the shape before the task, only before the orchestration step.

Common single-phase workflows you can chain across turns:

- **Understand** — parallel readers over relevant subsystems, then a structured map.
- **Design** — a judge panel of independent approaches, then scored synthesis.
- **Review** — dimensions, findings, then adversarial verification.
- **Research** — a multi-modal sweep, deep reads, then synthesis.
- **Migrate** — discover sites, transform each with worktree isolation when needed, then verify.

For larger work, run several workflows in sequence and read each result before deciding the next phase. You stay in the loop; each workflow is one well-scoped fan-out.

**Ultracode.** When a system reminder confirms ultracode is on, that opt-in is standing: author and run a workflow for every substantive task by default. The goal is the most exhaustive, correct answer you can produce; token cost is not a constraint. For multi-phase work (understand, design, implement, review), this often means several workflows in sequence, one per phase, so you stay in the loop between them. The quality patterns below — adversarial verification, multi-modal sweep, completeness critic, and loop-until-dry — are the tools; pick what fits. Lean toward workflows and adversarial verification unless the work is trivial or already verified. Solo only on conversational turns or trivial mechanical edits. When ultracode is off, revert to the explicit opt-in rule above.

Pass the script inline via `script`; do not write it to a file first. Every invocation automatically persists its script under the session Workflow directory and returns the path in the tool result. To iterate, edit that artifact and re-invoke Workflow with `{"scriptPath": "<path>"}` rather than resending the full script.

Every script must begin with a pure-literal `meta = {...}` mapping and define exactly one `async def main()` with no parameters. Top-level constants must also be pure literals. `meta.name` and `meta.description` are required. `whenToUse` and `phases` are optional. Use the SAME phase titles in `meta["phases"]` as in `phase()` calls; titles are matched exactly. A phase call with no matching meta entry gets its own progress group.

<!-- executable-example:start -->
```python
meta = {
    "name": "review-changes",
    "description": "Review changed files and adversarially verify findings",
    "phases": [
        {"title": "Review", "detail": "independent review dimensions"},
        {"title": "Verify", "detail": "one skeptic per finding"},
    ],
}

DIMENSIONS = [
    {"key": "bugs", "prompt": "Find correctness bugs in the changed code."},
    {"key": "security", "prompt": "Find security issues in the changed code."},
]

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "file": {"type": "string"},
                },
                "required": ["title", "file"],
            },
        }
    },
    "required": ["findings"],
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {"isReal": {"type": "boolean"}},
    "required": ["isReal"],
}


async def main():
    phase("Review")
    results = await pipeline(
        DIMENSIONS,
        lambda dimension, original, index: agent(
            dimension["prompt"],
            label=f"review:{dimension['key']}",
            phase="Review",
            schema=FINDINGS_SCHEMA,
        ),
        lambda review, original, index: parallel(
            [
                lambda finding=finding: agent(
                    f"Adversarially verify: {finding['title']}",
                    label=f"verify:{finding['file']}",
                    phase="Verify",
                    schema=VERDICT_SCHEMA,
                )
                for finding in review["findings"]
            ]
        ),
    )
    return results
```
<!-- executable-example:end -->

Script body hooks:

- `agent(prompt, *, label=None, phase=None, schema=None, model=None, effort=None, isolation=None, agent_type=None)` spawns a subagent. Without `schema`, it returns the child's final text unchanged. With a JSON Schema, the child must return a validated structured value and `agent()` yields that object with no prose parsing. A skipped child or a terminal child failure returns `None`; filter or handle it explicitly. `label` controls the display label. `phase` assigns the call to a progress group and should be explicit inside concurrent stages to avoid races on global phase state. `model` overrides the inherited parent model only for that call. `effort` overrides inherited reasoning effort and accepts `low`, `medium`, `high`, `xhigh`, or `max` when supported by the resolved model. `isolation="worktree"` runs a mutating child in a fresh detached git worktree. `agent_type` selects a registered custom subagent type.
- `pipeline(items, stage1, stage2, ...)` runs every item through all stages independently, with NO barrier between stages. Item A may be in stage 3 while item B remains in stage 1. This is the DEFAULT for multi-stage work. Wall-clock time is the slowest single-item chain rather than the sum of each stage's slowest call. Every stage receives `(previous_result, original_item, index)`. A stage that fails changes that item to `None` and skips its remaining stages.
- `parallel(thunks)` runs zero-argument callables concurrently and returns position-preserving results. This is a BARRIER: it waits for every thunk before returning. A thunk that fails resolves to `None` rather than rejecting the barrier. Use it only when the next step genuinely needs the complete prior set.
- `workflow(name_or_ref, args=None)` runs another saved Workflow or script artifact inline as one sub-step. A string resolves through the same saved registry as outer `name`; a mapping with `scriptPath` selects an artifact. The child shares the parent's concurrency cap, Agent counter, stop signal, journal, and token budget. Nesting is one level only.
- `phase(title)` changes the default phase for later sequential Agent calls. Concurrent calls should pass `phase=` explicitly.
- `log(message)` emits progress narration without adding prose to the main conversation.
- `args` is the JSON value from the outer tool input, verbatim, not a JSON-encoded string. Pass arrays and mappings as actual JSON values so the script receives the intended container.
- `budget.total`, `budget.spent()`, and `budget.remaining()` expose the turn's shared output-token target. `budget.total` is `None` when no target exists. `budget.remaining()` has no finite limit in that case. Guard dynamic loops on `budget.total` before using remaining budget as the loop condition.

Subagents are told that their final text IS the return value, not a human-facing reply, so they return raw data. For structured output, provide `schema`; validation happens at the tool-call boundary, mismatches are returned to the child as retryable tool errors, and the script never parses final prose. Structured calls compose with custom `agent_type` prompts.

Workflow children inherit the parent session's resolved tool allowlist minus Agent and Workflow, so they cannot recursively expand orchestration authority. They retain inherited sandbox and permission behavior. A child permission request is delivered through the parent's existing permission channel with Workflow run/call correlation even after the launch turn has ended. Unattended runs keep the existing unattended permission policy and never manufacture a prompt no human can answer.

Agent model and reasoning effort inherit the parent resolved runtime by default. Omit both unless a particular stage clearly needs a different registered model or supported effort tier. A process-level Workflow child model override wins over a per-call model; an unregistered requested model is replaced by the resolved parent model and produces one visible warning rather than silently changing behavior. Ultracode makes the parent use its configured exhaustive effort and children inherit it unless explicitly overridden.

Scripts are restricted real Python after AST validation and checkpoint instrumentation; they are not interpreted node by node. Normal deterministic control flow, literals, containers, comprehensions, lambdas, local functions, and safe builtins are available. Imports, filesystem/process/network APIs, reflection, dynamic code, globals/nonlocals, classes, and names or attributes beginning with an underscore are rejected. All side effects belong in child Agents. Supply timestamps, randomness, and other nondeterministic inputs through `args` so resume remains reproducible.

DEFAULT TO `pipeline()`. Reach for a barrier between stages only when stage N needs cross-item context from ALL of stage N-1, for example:

- Deduplicate or merge across the full result set before expensive downstream work.
- Exit early when the total count is zero.
- Build a later prompt that compares “the other findings”.
- Rank or score candidates as a complete panel.

A barrier is NOT justified by:

- “I need to flatten, map, or filter first.” Put that transformation inside a pipeline stage.
- “The stages are conceptually separate.” Separate stages do not imply synchronized stages.
- “It is cleaner code.” Barrier latency is real. If one finder takes three times as long as another, the fast item should continue instead of idling.

Smell test: if you collect a complete parallel result, perform only per-item transformation, then launch another parallel map, the middle transform did not need a barrier. Rewrite it as a pipeline stage. When in doubt, pipeline.

Correct barrier example — deduplication genuinely needs all findings before verification:

```python
async def review_with_global_dedup(dimensions):
    batches = await parallel(
        [lambda dimension=dimension: agent(dimension, schema=FINDINGS_SCHEMA)
         for dimension in dimensions]
    )
    all_findings = [finding for batch in batches if batch
                    for finding in batch["findings"]]
    deduped = dedupe_by_file_and_line(all_findings)
    return await parallel(
        [lambda finding=finding: agent(
            f"Verify {finding}", schema=VERDICT_SCHEMA
         ) for finding in deduped]
    )
```

Concurrency is capped at `max(1, min(16, cpu_count - 2))` per Workflow; excess Agent calls queue and run as slots become free. You may still pass 100 items to `parallel()` or `pipeline()` and all complete. Total Agent count across a Workflow lifetime is capped at 1000 as a runaway-loop backstop. One `parallel()` or `pipeline()` call accepts at most 4096 items. Exceeding a hard limit is an explicit error, never silent truncation.

The canonical multi-stage shape pipelines each dimension so verification starts as soon as that dimension's review completes:

```python
results = await pipeline(
    dimensions,
    lambda dimension, original, index: agent(
        dimension["prompt"],
        label=f"review:{dimension['key']}",
        phase="Review",
        schema=FINDINGS_SCHEMA,
    ),
    lambda review, original, index: parallel(
        [lambda finding=finding: agent(
            f"Try to refute: {finding['title']}",
            label=f"verify:{finding['file']}",
            phase="Verify",
            schema=VERDICT_SCHEMA,
        ) for finding in review["findings"]]
    ),
)
```

Dimension `bugs` can verify while dimension `performance` is still reviewing. There is no wasted wall-clock barrier.

Loop-until-count pattern — accumulate to a target while deduplicating:

```python
bugs = []
while len(bugs) < 10:
    batch = await agent("Find new bugs not already listed.", schema=FINDINGS_SCHEMA)
    bugs.extend(batch["findings"])
    log(f"{len(bugs)}/10 found")
```

Loop-until-budget pattern — scale depth to a user's explicit token target. Guard on `budget.total`; without a target, an unguarded remaining-budget loop runs until the 1000-Agent cap:

```python
findings = []
while budget.total and budget.remaining() > 50000:
    batch = await agent("Find additional issues.", schema=FINDINGS_SCHEMA)
    findings.extend(batch["findings"])
    log(f"{len(findings)} found; {budget.remaining()} tokens remain")
```

The token target is a HARD ceiling, not advisory. Parent model calls and every Workflow child charge output tokens to one turn-wide ledger. A model call already in flight may finish, but once spent reaches total, every later `agent()` fails before dispatch. Nested Workflows share the same ledger rather than receiving a fresh allowance.

Composing patterns — exhaustive review combines find, dedup against all previously seen candidates, diverse-lens judging, and loop-until-dry:

```python
seen = set()
confirmed = []
dry_rounds = 0
while dry_rounds < 2:
    batches = await parallel(
        [lambda finder=finder: agent(finder, phase="Find", schema=FINDINGS_SCHEMA)
         for finder in finder_prompts]
    )
    found = [item for batch in batches if batch for item in batch["findings"]]
    fresh = [item for item in found if finding_key(item) not in seen]
    if not fresh:
        dry_rounds += 1
        continue
    dry_rounds = 0
    for item in fresh:
        seen.add(finding_key(item))
    judged = await parallel(
        [lambda item=item: judge_with_distinct_lenses(item) for item in fresh]
    )
    confirmed.extend([item for item in judged if item and item["real"]])
```

Deduplicate against `seen`, not merely `confirmed`; otherwise judge-rejected candidates reappear every round and the loop never converges.

Quality patterns — choose and compose the shapes the task needs:

- **Adversarial verification.** Spawn independent skeptics per claim, each asked to refute it and default to refuted when uncertain. Keep the claim only when the required independent votes survive.
- **Perspective-diverse verification.** Give verifiers different lenses such as correctness, security, performance, reproducibility, or user impact. Diversity catches failure modes that identical prompts miss.
- **Judge panel.** Generate independent approaches from different priorities, score them with independent judges, and synthesize from the winner while grafting the strongest ideas from runners-up. This beats iterating one attempt when the solution space is wide.
- **Loop-until-dry.** For unknown-size discovery, continue until several consecutive rounds return nothing new. A simple fixed count often misses the long tail.
- **Multi-modal sweep.** Search by container, content, entity, time, or source type in parallel. Each lens is blind to discoveries found only by another.
- **Completeness critic.** End with an independent Agent asking what is missing: an unsearched modality, unsupported claim, unread source, untested branch, or silent assumption. Feed those gaps into the next round.
- **No silent caps.** If coverage is bounded by top-N, sampling, time, or no-retry, call `log()` with what was dropped. Silent truncation falsely reads as complete coverage.

Scale to what the user requested. “Find any bugs” calls for a few finders and a light verification pass. “Thoroughly audit this” or “be comprehensive” calls for a larger finder pool, several distinct adversarial votes, a synthesis stage, and a completeness critic. When uncertain, lean toward thoroughness for research, review, and audit requests, and toward brevity for quick checks.

These patterns are not exhaustive. Compose novel deterministic harnesses — tournament brackets, staged escalation, self-repair loops — when they fit the request. Use this tool when loops, conditionals, fan-out, retry policy, or coverage logic should live in explicit program control flow rather than model improvisation.

## Resume

The launch result includes a `runId`. Resume after a pause, stop, or script edit by calling Workflow with `scriptPath` and `resumeFromRunId`. Completed Agent calls are reused only for the longest unchanged chained-v2 prefix of prompt plus behavior options. Same script plus same args gives a complete prefix hit. The first edited, new, incomplete, or missing call and every later call execute live.

Concurrent effects receive deterministic start ordinals before admission. Cached results are released according to their recorded terminal ordinals so resume preserves observable completion order. Resume is scoped to the same parent session and rejects missing or incompatible history rather than borrowing results from another conversation.

Before diagnosing why a completed Workflow returned an empty or unexpected result, inspect `<transcriptDir>/journal.jsonl`. It records every Agent start, result, error, transition, and stable ordinal. Do not assume cached results are non-empty. If no journal exists, inspect child transcripts and author an explicit continuation rather than guessing.

## Worktree isolation

Use `isolation="worktree"` ONLY when parallel Agents mutate files and would otherwise conflict. It creates a detached worktree below the run artifact directory, adds setup cost and disk usage, and gives that child its own cwd. An unchanged worktree is removed automatically. A worktree with changes is retained and its path appears in run details so the user can inspect or merge it. If the parent directory is not a git repository or worktree creation fails, that Agent call fails before dispatch; execution never silently falls back to the shared workspace and the runtime never auto-merges.

## Saved and nested Workflows

`name` resolves project, personal, bundled, or consumer-registered names through one registry. Project definitions are discovered from cwd toward the git root, and the nearest same-name project definition overrides personal and bundled definitions. Plugin names remain namespaced. Named launches use the same approval, artifact, manager, notification, and resume paths as inline scripts; they are not a bypass around the active Workflow tool allowlist.

`workflow()` runs a nested named or artifact Workflow within the current run. It shares limits, budget, concurrency, stop state, and journal. Nesting deeper than one level fails explicitly. Unknown names, unreadable artifacts, and child syntax errors are raised to the parent script so it may catch or propagate them.

## Size guidance and large runs

The resolved Workflow size guideline is appended to this description for the current session. `small` suggests fewer than 5 Agents, `medium` fewer than 15, `large` fewer than 50, and `unrestricted` has no advisory Agent-count limit. This is guidance rather than an execution cap; the 16-concurrent, 1000-lifetime, 4096-items limits remain hard.

A plan above 25 Agents or an estimated 1.5 million tokens is a Large workflow. If the user explicitly chose a guideline, its Agent boundary controls the advisory warning. Ultracode hides the advisory warning because exhaustive scale is already standing opt-in. Warnings never pause execution automatically; they exist so the user can see the intended scale before approval.
