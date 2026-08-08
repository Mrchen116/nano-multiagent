---
name: reverse-engineer-claude-code
description: Reverse-engineer a current Claude Code feature to a reproducible behavioral and implementation contract by triangulating the pinned local source baseline, current official documentation, minimal live Claude Code traces through LLM Proxy, and—when those leave material ambiguity—read-only analysis of the installed package or binary. Use when asked to understand, reproduce, port, or compare a Claude Code feature, system prompt, tool contract, agent orchestration behavior, persistence model, permission flow, or hidden runtime implementation—especially when the local open-source reconstruction is older or contains stubs.
---

# Reverse Engineer Claude Code

Reconstruct behavior from three primary evidence lanes, with installed-package/binary analysis as an escalation lane. Keep vendor facts, direct observations, and implementation inferences separate so another engineer can reproduce both the investigation and the resulting design.

## Non-negotiable defaults

- Use `codexOAuth:gpt-5.6-luna` for the main Claude Code process and every subagent unless the user explicitly authorizes another model.
- Start with `CLAUDE_CODE_EFFORT_LEVEL=low`, one agent, no tool calls, and one variable under test.
- Treat live model calls as a budgeted experiment. Do not scale fan-out merely to demonstrate that fan-out exists.
- Keep the experiment read-only unless the feature itself cannot be distinguished without a write and the user authorized that write.
- Never commit raw proxy requests, full prompts, tokens, cookies, local configs, or session transcripts. Record locators and redacted excerpts.
- Use current official Anthropic documentation for public contract claims. Community posts are discovery aids, not authority.
- Analyze only the user's locally installed package/binary, read-only. Do not patch executables, bypass licensing or protections, or extract unrelated secrets.

Read [`references/experiment-playbook.md`](references/experiment-playbook.md) before running a live experiment or writing the final reconstruction.

## Workflow

### 1. Frame a discriminating question

Turn the request into a claim that one observation can confirm or reject, for example:

- What exact condition activates the feature?
- Is orchestration selected by the model, the CLI, or both?
- What tool schema and prompt layer instruct the model?
- Does a tool call block, return a task handle, or emit a later notification?
- Which state is durable, and what does resume reuse?
- Which permissions are inherited by child agents?

Do not begin with a broad demonstration. Maintain a hypothesis table with `claim`, `lane`, `observation`, `confidence`, and `remaining unknown`.

### 2. Pin the local source lane

Record both repositories before interpreting code:

```bash
git -C <nano-repo> rev-parse HEAD
git -C <claude-code-repo> rev-parse HEAD
git -C <claude-code-repo> status --short --branch
```

If the upstream checkout is dirty, inspect the committed baseline with `git show HEAD:<path>` and label working-tree-only content separately. Search for:

1. feature gates, registration, command wiring, settings, and permission UI;
2. the target tool implementation or generated stubs;
3. adjacent complete primitives such as agent execution, query loops, task state, notifications, and streaming tool scheduling;
4. tests and schemas that expose behavior even when implementation is absent.

An empty stub proves only the landing seam. It does not prove the feature is client-only, server-only, or absent from the installed binary.

### 3. Establish the official contract

Search the current official Claude Code documentation and release notes. Record the URL, access date, applicable CLI version, activation rules, limits, permissions, persistence, model selection, and documented failure behavior.

If no official contract is found, record a reproducible negative search: official entry points searched, exact queries/keywords, version or date range, access date, and any near matches rejected. Say "not found in this search scope," not "undocumented."

When the installed CLI and docs disagree, report the discrepancy and test the narrow behavior. Do not silently choose one. CLI `--help` text may lag hidden or newly released settings.

### 4. Run the smallest live trace

Verify the proxy health and installed CLI version. Export the user's proxy settings, then force both levels to Luna:

```bash
export ANTHROPIC_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_SUBAGENT_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_EFFORT_LEVEL=low
```

For features activated only by human input, use an interactive terminal. Do not substitute `claude -p` unless the official contract says non-human origins are equivalent. Give the experiment an explicit stop condition and capture:

- Claude Code session ID and version;
- proxy session directory;
- request model, effort, system blocks, messages, tools, and metadata;
- exact target tool schema and description;
- generated scripts or plans;
- task/run state, journal events, and notification shape;
- child request prompt stack and tool set;
- final result, token count, duration, and errors.

Summarize proxy requests with:

```bash
python3 .claude/skills/reverse-engineer-claude-code/scripts/inspect_anthropic_session.py \
  <proxy-session-directory> --tool Workflow
```

Use `--show-system` or `--show-last-message` only when exact text is necessary; those modes can expose repository context and must not be committed verbatim.

### 5. Escalate to installed package or binary analysis

Use this lane only when source, official docs, and existing traces leave a material implementation question unresolved. Read [`references/binary-analysis-playbook.md`](references/binary-analysis-playbook.md) before acting.

Start with package metadata, wrappers, hashes, signing, linked runtimes, and exact feature strings. For a bundled JavaScript/native executable, recover and inspect the embedded JavaScript call site before considering native disassembly. A runtime or parser string merely present in the binary is not evidence the feature uses it; connect the feature-specific validation/compile/execute call chain.

Record installed version, absolute binary path, SHA-256, file format, signer, runtime/compiler markers, relevant byte offsets or extracted function fragments, and the limit of the analysis. Label these claims **Binary observations**, distinct from the older local source baseline and live behavior.

### 6. Reconstruct the prompt stack

Keep these layers distinct:

1. base CLI system prompt;
2. feature activation attachment or system reminder;
3. target tool description and input schema;
4. main-model-authored script or task prompt;
5. child-agent system prompt and workflow-specific addendum;
6. asynchronous task notification returned to the main conversation.

Short observed fragments may be quoted and labeled with a trace locator. For a usable reimplementation, write a separate **authored surrogate prompt** that preserves semantics without claiming to be the vendor's complete hidden prompt.

### 7. Produce the implementation contract

The deliverable must cover:

- activation and eligibility;
- public and model-facing inputs;
- scheduling and concurrency;
- child context and tool authority;
- permissions and approval boundaries;
- persistence, journal, notifications, and resume;
- errors, cancellation, and partial results;
- saved or bundled entry points;
- cost controls and model routing;
- source landing seams and reusable adjacent components;
- unknowns and the next cheapest experiment that would resolve each one.

Label every material statement as one of:

- **Official fact** — current first-party documentation;
- **Source observation** — pinned local commit;
- **Runtime observation** — identified trace/session;
- **Binary observation** — read-only evidence from an identified installed package hash and call site;
- **Inference** — synthesis needed to implement compatible behavior.

## Stop conditions

Stop experimenting when the official contract, source seams, and one runtime trace converge on the requested behavior. Run another experiment only if it changes an implementation decision or resolves a material contradiction. Ask before increasing model tier, agent count, or write scope.

## Deliverables

For a substantial investigation, create a dated research snapshot containing:

- `README.md` — status, scope, baselines, current owner, and artifact map;
- `research.md` — evidence ledger, exact locators, observations, and limitations;
- a reader-facing article — operating model, prompt stack, runtime state machine, and reimplementation blueprint.

Link the package from its research index. Do not promote reverse-engineered behavior into current product specs until it is adopted and implemented.
