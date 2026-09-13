---
name: improve-codebase-architecture
description: "Use only when explicitly asked to scan architecture for module-deepening opportunities and produce a visual candidate report; not for implementing a refactor."
disable-model-invocation: true
---

# Improve Codebase Architecture

Find concrete architectural friction and propose candidates with evidence of better locality, simpler interfaces or stronger tests. Ground candidates in the reviewed code and existing decisions; preserve project terminology. Use [codebase-design](../codebase-design/SKILL.md) when interface/dependency analysis is needed.

Exploration depth and tools are task-dependent. Do not require an Explore agent, a full-repository scan or candidate quotas. Only reopen an existing architectural decision when actual friction justifies it, and state the conflict.

## Report and handoff

Write an independent HTML snapshot under `docs/research/architecture-reviews/`, named `architecture-review-<YYYYMMDD-HHMMSS>-<short-sha|no-git>.html`; avoid overwriting collisions. Include generation time, repository, full commit, branch and tracked/untracked state; dirty state means the commit alone is not the full snapshot.

For each candidate show files, concrete problem, proposed change, benefits, before/after visual and recommendation strength (`Strong | Worth exploring | Speculative`). End with the best-supported recommendation. Use [HTML-REPORT.md](HTML-REPORT.md) for rendering and metadata; do not create a separate ledger or status system.

Open the report and give its absolute path. After the user selects a candidate, hand off its source report/revision, files, friction, intended benefit and unresolved constraints to the project/user-selected change flow. This skill does not implement the refactor or preempt its interface design.
