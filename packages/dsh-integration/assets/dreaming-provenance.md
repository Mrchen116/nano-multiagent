# Dreaming prompt provenance

`src/knowledge/dreaming-prompts.ts` adapts OpenAI Codex Memory V2 at commit
`8fdf6472955749a731fd9e4b8ffc218e8e80c51d`. Copyright and license are retained in
[NOTICE](licenses/codex-memory/NOTICE) and [Apache-2.0 LICENSE](licenses/codex-memory/LICENSE).
These assets ship with the Node payload.

The extraction prompt retains the original task-history, evidence, preference-scope,
uncertainty, authorization and redaction guidance. Nano changes the consumer from a
Codex rollout to a trusted first-level task, supplies original inherited background
and own events directly, and returns the same two strings in the final JSON response.
The host parses and validates it after normal completion. The pinned DSH public API
does not expose provider-native JSON Schema output; Nano does not replace it with
another completion tool. Empty strings retain the original no-signal meaning. The host owns
scope, source versions, staging, receipts and persistence.

Consolidation adapts Codex's tests for grounding claims, preserving preference
scope and selecting knowledge that will help on a related future task. Nano uses
its own PA and expert Markdown layout, original Global dialogue, one current
summary per task and current source exclusions. It distinguishes omitted sources
from revoked sources, and private drafts from delivery. Normal model completion
leads to host validation and application of staged files. Model failure or
cancellation keeps staged changes and source progress unpublished.

The two responsibilities of integrating new knowledge and cleaning up existing
memory follow [memoryrepo's Dreaming instructions](https://github.com/supermemoryai/memoryrepo/blob/54f7ff3065df8af687dc5c04a4bb17d6611e5fd1/src/server/memory.ts#L68).
Its entry-page conventions inform the short `MEMORY.md` directly loaded in
ordinary requests. The [Anthropic Cookbook Organizer](https://github.com/anthropics/claude-cookbooks/blob/ce8b2629efe8b24048b127b4c79af1e9cbab93d4/managed_agents/example_data/memory_distill/prompts/organizer_system.md#L17)
informs the order for cross-page moves. Nano checks the live destination before
trimming the source page because it publishes staged files individually.

The relationship, interaction-reflection and proactive-preference dimensions were
checked against the original Muse descriptions collected at
`asgeirtj/system_prompts_leaks@1b6f936124b4eceb6e697a69da07519bea67feab`:
`Meta/muse-agent/docs/{memory,self_improvement}.md`, `AGENTS.md` and
`PROACTIVE_PREFERENCES.md`. Those are third-party published descriptions, not an
official released Dreaming implementation. Nano paraphrases their content dimensions;
it does not copy personal instances, create Muse's separate cards/schedulers, or
claim knowledge of its hidden runtime prompt.

Consolidation selects its focus using the bound Agent's PA or expert role and
supplies the confirmed workspace role agreement separately
as background data. The PA interaction-reflection wording remains. The expert
variant focuses on domain and project changes, environment conditions, verified
work lessons and collaboration. Both use the same evidence and proactive
communication rules.

The retained source snapshots, hashes, implementation comparison and exact prompt
diff are part of feat-676's review evidence. Runtime content and authority remain in
Nano's approved design and current package specs.
