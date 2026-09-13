---
name: codebase-design
description: "Use when deciding a module interface, responsibility boundary, dependency seam or test surface; not for routine implementation or general code review."
---

# Codebase Design

Design modules that hide substantial behavior behind a small interface. Preserve project domain names and architectural boundaries; use the vocabulary below to clarify relationships, without policing synonyms.

- **Interface** includes everything callers must know: types, invariants, ordering, errors, configuration and performance.
- **Depth** is useful behavior relative to that cognitive surface, not a line-count ratio.
- **Seam** is where behavior can vary; an **adapter** supplies a concrete implementation there.
- **Leverage** measures what callers gain; **locality** keeps related changes, bugs and verification together.

Favor interfaces callers and tests can both use. An abstraction earns its place when removing it would spread necessary complexity across callers. Keep private seams private; introduce adapters for actual dependency variation or test isolation, not hypothetical extensibility.

For dependency categories and replacement tests, read [DEEPENING.md](DEEPENING.md). When the user needs to compare substantively different interface choices, read [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md); do not require competing designs for routine decisions.

Complete with a proposed interface, concrete usage, hidden responsibilities, relevant invariants, dependency/test strategy and trade-offs. Integrate these into the caller's existing design artifact rather than creating another process. For expanded terminology and examples, see [vocabulary](references/vocabulary.md).
