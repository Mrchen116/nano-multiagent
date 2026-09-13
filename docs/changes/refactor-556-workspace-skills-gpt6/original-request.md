Audit and optimize all local Skills in this workspace for GPT-6-class models.

Your goal is NOT to add more instructions. The goal is to remove unnecessary scaffolding, reduce context overhead, improve Skill triggering, and give a stronger model more freedom to reason and execute autonomously.

## Scope

Recursively discover and inspect:

* every `SKILL.md` in this workspace
* files referenced by those Skills
* `references/`, `scripts/`, `assets/`, templates, examples, and helper docs belonging to each Skill
* relevant `AGENTS.md` / `AGENTS.override.md` only when they affect how a Skill is triggered or executed

Do not assume a fixed directory layout. Discover the actual structure first.

## Core optimization principles

Optimize the Skills for a stronger model such as GPT-6.

### 1. Remove weak-model scaffolding

Identify instructions that mainly existed because older/weaker models needed hand-holding, for example:

* always make a detailed plan first
* think step by step
* repeatedly remind yourself of the goal
* always inspect X before doing anything
* always read every document
* always search before editing
* always run the entire test suite
* verify the same thing multiple times
* overly detailed sequences of obvious reasoning steps
* repetitive reminders already handled well by the model
* instructions compensating for specific historical model failures

Delete or simplify them unless they encode a real project requirement.

Prefer:

`goal + constraints + completion criteria`

over:

`long mandatory reasoning procedure`.

### 2. Narrow Skill triggering

For every Skill, inspect its frontmatter/name/description.

Descriptions should answer only:

* what capability this Skill provides
* when it should actually be activated

Avoid broad domain descriptions that cause false-positive triggering.

Bad:

> Use this Skill whenever working with databases, storage, SQL, persistence, or backend code.

Better:

> Use this Skill when creating, modifying, reviewing, or validating a database schema migration.

Make each Skill's trigger boundary as precise as possible.

### 3. Turn SKILL.md into a concise router

`SKILL.md` should contain only information that is useful in most invocations:

* purpose
* trigger boundary
* important invariants
* high-level workflow when genuinely necessary
* completion criteria
* pointers to additional resources

Move detailed knowledge into progressively disclosed files.

Prefer:

```text
SKILL.md
├── references/
│   ├── architecture.md
│   ├── edge-cases.md
│   └── examples.md
├── scripts/
└── assets/
```

The root Skill should tell the agent WHEN a reference is useful rather than forcing it to read everything.

Example:

```text
For schema compatibility rules, read references/schema.md.
For release-specific behavior, read references/release.md.
Do not load these files unless relevant to the current task.
```

### 4. Preserve real invariants

Do NOT delete instructions merely because they are restrictive.

Keep requirements that represent genuine:

* safety boundaries
* product requirements
* architectural invariants
* compatibility requirements
* data integrity requirements
* repository conventions
* irreversible-operation safeguards
* user-defined workflow requirements

Separate these from model-behavior workarounds.

### 5. Prefer outcome constraints over process micromanagement

Replace unnecessary process rules such as:

```text
1. inspect
2. think
3. write a plan
4. inspect again
5. implement
6. review
7. test
8. review tests
```

with clear completion conditions such as:

```text
Complete the requested change.
Preserve the documented invariants.
Run verification appropriate to the affected area.
Fix regressions caused by the change.
Stop when the requested behavior and relevant checks pass.
```

Let the model decide the exact implementation path.

### 6. Avoid unconditional context loading

Remove instructions like:

```text
Before every task, read A.md, B.md, C.md and D.md.
```

Replace them with conditional routing:

```text
Read A.md when modifying X.
Read B.md when dealing with Y.
```

Optimize for minimum necessary context.

### 7. Prefer deterministic tools over prose procedures

If a Skill contains a long textual procedure for something that can be reliably encoded in a script:

* move the deterministic logic into `scripts/`
* let the Skill invoke or reference the script
* keep judgment/reasoning tasks with the model

Do not create scripts merely to replace simple instructions.

### 8. Remove duplication and contradictions

Across Skills, identify:

* duplicated generic instructions
* contradictory rules
* multiple Skills claiming the same trigger
* copied boilerplate
* repository-wide rules incorrectly duplicated into individual Skills

Consolidate them where appropriate.

Avoid creating a giant shared instruction file that every Skill must load.

## Execution

Do not stop at recommendations.

First inspect the workspace and build a mental model of the current Skills.

Then directly edit the Skills and their supporting files.

You may:

* rewrite `SKILL.md`
* shorten descriptions
* split large Skill documents
* move detailed material into `references/`
* simplify workflows
* remove obsolete instructions
* consolidate duplicated material
* improve filenames and internal routing
* add small supporting reference files when this materially improves progressive disclosure

Do NOT change application source code unless required to maintain an existing Skill-owned script.

Do NOT change the semantic capability of a Skill without a strong reason.

## Special rule

Be conservative about deleting domain knowledge and aggressive about deleting model micromanagement.

When uncertain whether something is:

A. a real domain/project constraint

or

B. scaffolding for weaker models

prefer preserving it, but rewrite it more clearly and concisely.

## Final validation

After editing:

1. Re-read every changed `SKILL.md`.
2. Check that its trigger is narrow and unambiguous.
3. Check that a normal invocation does not load unnecessary context.
4. Check that critical invariants were preserved.
5. Check that references are discoverable from the root Skill.
6. Check that there are no broken file links.
7. Check that Skills do not unnecessarily prescribe the model's reasoning process.
8. Check for overlapping Skill triggers.

Then report:

* Skills changed
* approximate before/after size for each `SKILL.md`
* important instructions removed
* information moved into references
* trigger descriptions narrowed
* genuine constraints deliberately preserved
* any remaining questionable legacy instructions that need human judgment

The desired end state is:

**thin cognitive scaffolding, precise activation boundaries, progressive disclosure, strong project invariants, explicit completion criteria, and maximum reasonable autonomy for GPT-6.**
