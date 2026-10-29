# Dreaming prompt provenance

`src/knowledge/dreaming-prompts.ts` adapts OpenAI Codex Memory V2 at commit
`8fdf6472955749a731fd9e4b8ffc218e8e80c51d`. Copyright and license are retained in
[NOTICE](licenses/codex-memory/NOTICE) and [Apache-2.0 LICENSE](licenses/codex-memory/LICENSE).
These assets ship with the Node payload.

The extraction prompt retains the original task-history, evidence, preference-scope,
uncertainty, authorization and redaction guidance. Nano changes the consumer from a
Codex rollout to a trusted first-level task, supplies original inherited background
and own events directly, and returns the same two strings through the restricted
`finish` tool. Empty strings retain the original no-signal meaning. The host owns
scope, source versions, staging, receipts and persistence.

The consolidation prompt retains the original grounded-claims paragraph, adapting
its preference destination to Nano's role documents. Codex's memory-folder layout,
raw-memory workspace protocol, per-thread storage and scheduler are not runtime
interfaces in Nano. The replacement sections specify the approved existing PA/expert
Markdown layout, one updated summary per task, original Global dialogue, current
source exclusions and the single Dreaming writer. They preserve the distinction
between omitted sources and revoked sources, and between private drafts and delivery.

The relationship, interaction-reflection and proactive-preference dimensions were
checked against the original Muse descriptions collected at
`asgeirtj/system_prompts_leaks@1b6f936124b4eceb6e697a69da07519bea67feab`:
`Meta/muse-agent/docs/{memory,self_improvement}.md`, `AGENTS.md` and
`PROACTIVE_PREFERENCES.md`. Those are third-party published descriptions, not an
official released Dreaming implementation. Nano paraphrases their content dimensions;
it does not copy personal instances, create Muse's separate cards/schedulers, or
claim knowledge of its hidden runtime prompt.

The retained source snapshots, hashes, implementation comparison and exact prompt
diff are part of feat-676's review evidence. Runtime content and authority remain in
Nano's approved design and current package specs.
