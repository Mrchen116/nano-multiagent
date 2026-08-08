# Claude Code live experiment playbook

Use this reference only after source and official-doc lanes have identified a concrete unknown.

## Cost ladder

Run the first level that can distinguish the hypothesis, then stop:

| Level | Main / children | Shape | Use |
|---|---|---|---|
| L0 | none | inspect source, docs, CLI help, existing traces | always first |
| L1 | Luna / Luna | one request or one child, no tools | activation, prompt, lifecycle |
| L2 | Luna / Luna | two children, trivial outputs | parallel ordering or barrier semantics |
| L3 | Luna / Luna | one child, one read-only tool | child authority and tool propagation |
| L4 | user-approved | only the minimum larger shape | behavior that cannot be inferred below |

Record actual tokens. A “no-tool” child can still be expensive because its system prompt, tool schemas, skills, and repository attachments are input tokens.

## Controlled environment

Prefer a clean temporary directory for feature mechanics. If repository instructions are part of the hypothesis, use the target repository but record its commit and dirty state. Never modify or clean unrelated user changes.

Use the proxy configuration already authorized by the user. A representative low-cost override is:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:4000"
export ANTHROPIC_AUTH_TOKEN="token"
unset ANTHROPIC_API_KEY
export ANTHROPIC_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_SONNET_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_OPUS_MODEL="codexOAuth:gpt-5.6-luna"
export ANTHROPIC_DEFAULT_FABLE_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_SUBAGENT_MODEL="codexOAuth:gpt-5.6-luna"
export CLAUDE_CODE_EFFORT_LEVEL=low
```

Do not copy placeholder credentials into a committed file or assume they are valid outside the user's configured environment.

## Experiment record

Capture this structure in `research.md`:

```text
claim:
baseline:
  claude_version:
  repository_commit:
  working_tree:
  main_model:
  child_model:
  effort:
method:
  human_input_or_print_mode:
  exact_prompt:
  stop_condition:
result:
  session_id:
  proxy_locator:
  transcript_locator:
  generated_artifact_locator:
  status:
  tokens:
  duration:
observation:
limit:
```

For an official-doc negative result, add a separate search record with `official_entry_points`, `queries`, `version_or_date_range`, `accessed_at`, and `rejected_near_matches`. Bound the conclusion to that recorded scope.

## Trace reading order

1. Find `*-req-anthropic_messages.json` files in the proxy session.
2. Identify the main request by the target tool in `tools[]`.
3. Read its `system`, `messages`, `metadata`, `model`, and effort field.
4. Hash and extract the target tool description/schema.
5. Match the tool use to the Claude Code conversation transcript.
6. Inspect generated script/state/journal artifacts under the session directory.
7. Identify child requests using billing metadata, system identity, task text, or timing.
8. Match completion notifications back to the main transcript.

Do not infer ordering from filenames alone when timestamps collide; use tool IDs, task IDs, run IDs, and journal events.

## Prompt evidence rules

- Quote only the smallest exact fragment needed to establish behavior.
- State whether text came from `system`, a tool description, a generated script, a child task, or a notification.
- Treat repository instructions and skills appended to the request as separate context, not part of Claude Code's vendor prompt.
- Hash large prompt/tool blocks so future captures can be compared without copying them into Git.
- Redact authorization values and any personal or repository-sensitive content.

## Contradiction handling

Use this order instead of averaging evidence:

1. Public normative behavior: current official docs.
2. Installed-version observation: live trace for the exact CLI version.
3. Implementation landing: pinned source baseline.
4. Reimplementation details not exposed by any lane: explicit inference.

A source stub and a working installed binary are not contradictory: they mean the source reconstruction does not contain the shipped implementation. A `--help` omission and documented runtime behavior may mean help text lag; test before deciding.
