# Candidate Spec Author task envelope

Run exactly one spec phase for the supplied public brief. Use the repository's
single `.agents/skills/change-spec-author` Skill closure. Stop immediately when
you believe its Gate 1 first document is complete: do not run design, any
reviewer, implementation, deployment, or a GitHub operation. Do not access
outside the workspace or use network resources.

Ask the Owner one concrete question at a time when a material product judgment
cannot be grounded from the brief, repository, or optional task memory. The
runner will resume this same session with the Owner's reply. If
`.experiment/task-memory.md` exists, read it as fallible cross-case context:
validate applicability against this task and repository, never treat it as
owner truth, and do not copy its provenance into the first document. The same
envelope applies when the file is absent.

When a turn ends, return only the structured status object. For `needs_owner`,
put the one question in `owner_message` and leave `first_doc_path` empty. For
`gate1_complete`, leave `owner_message` empty and return the relative first-doc
path. Return `blocked` only for a real environmental or contract blocker.
