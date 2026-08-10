# H01 private rubric — Web IM message content interactions

Keep this directory out of candidate exports. Freeze this rubric and the inventory before viewing any arm output. The historical unit is evidence about missed risks and one successful design, not a wording, feature-list, component, symbol or algorithm gold.

## 1. Decision handling first

H01 has no preregistered H decision and no P decision. D01-D06 are cutoff facts or explicit brief constraints; asking the owner to locate code, restate the two bugs or choose whether browser safety applies is burden rather than alignment.

D07 is the one material value fork: which nearby interactions and discovery surfaces form a coherent final scope. It passes when the artifact makes the candidate list, alternatives, trade-offs and recommendation visible in the promised unified review. The brief explicitly asks for a final design, so do not fail an arm merely because it did not interrupt authoring for another round of questions. Fail D07 when scope expands silently, a material option is hidden, or the final design still contains incompatible branches.

A newly discovered proposal to delete user data, widen URL/HTML trust, change a public/backend contract or violate package boundaries would create a new H and must pause only the dependent branch. Ordinary compliance with existing constraints is not an H.

## 2. User burden and personalization

- D01-D06 require zero user questions. The repository and public brief contain the needed evidence.
- D07 should be one consolidated recommendation in the final review artifact, not serial questions about toolbar, right-click, long-press, mobile layout, copy format and feedback.
- The current brief already states commercial quality, restraint and a final-design mandate. Do not award personalization credit for repeating those instructions, and do not classify them again as P.
- For A+USER/B, exclude all target-lineage profile evidence. Personalization credit requires independent cross-case evidence and must yield a concrete improvement beyond the brief.

Penalize asking whether partial selection should copy only the selection, whether an external link should preserve the chat, where the handlers live, or whether existing fork semantics should be retained. A concise statement of assumptions and a bounded final recommendation is not counted as a user question.

## 3. Spec oracle

The two reported outcomes are mandatory:

- A user can select part of a message and copy that selection through the ordinary browser/OS paths claimed by the scope. Message-level actions do not steal a selection or interactive descendant.
- An external web link opens without replacing the current chat and uses a safe browser navigation contract. Relative, same-origin, hash and unsupported targets have a documented, internally consistent rule.

The rest is judged against the candidate's own justified scope:

- The candidate list groups nearby problems by user job and explains why each item is kept, deferred or rejected. A focused two-fix design can pass if it convincingly closes the interaction family; a broader bundle can also pass if it remains coherent and bounded.
- If whole-message copy remains or is redesigned, its payload boundary and rich-content behavior are testable. No particular historical DOM serializer or whitespace format is mandatory.
- If code-block copy, message actions, copy feedback or touch-specific surfaces are selected, their success/failure, keyboard/touch accessibility, localization and interaction with native selection are independently testable.
- Existing actions such as fork keep their product eligibility unless the artifact explicitly scopes and justifies a separate change.
- Scope and non-goals keep unrelated message capabilities and backend changes out unless evidence supports the expansion.

Missing either reported outcome is critical. Missing a candidate-selected behavior or leaving it as “good UX” without observable acceptance is major. Do not mark omission of a historical companion feature as a defect by itself.

## 4. Design oracle

A strong design demonstrates these qualities without being forced into the historical structure:

1. It traces the production route to the message bubble, Markdown renderer, styles and existing tests, then names the smallest implementation seams for the selected scope.
2. It defines browser-versus-product ownership from observable event targets and selection state. Any reliable, cross-browser approach can receive full credit; exact historical pointer/caret heuristics are not required.
3. It applies one consistent link-navigation and safety rule at the existing render extension point, or justifies an equivalent local seam.
4. If multiple message-action surfaces are selected, action eligibility and labels cannot drift between pointer, keyboard and touch presentations. A single surface can also pass if it is discoverable and does not steal native gestures.
5. If a product copy action is selected, its source boundary, normalization and async result ownership are explicit enough to prevent metadata leakage and stale feedback. Raw Markdown, rendered DOM projection or another method may pass when its trade-offs and fixtures match the spec.
6. It covers state transitions such as conversation/message changes only to the degree asynchronous actions in the chosen scope require; historical coordinator names and all historical race machinery are not mandatory.
7. Milestones and tests follow the chosen behavior, stay within architecture boundaries absent contrary evidence, and include real-browser checks for the input modes claimed by the spec.

Award full design credit to a materially different mechanism when it proves the same selected behaviors and constraints. Penalize copied historical topology that does not fit the candidate's own spec.

## 5. Hidden downstream probes

Every implementation-oriented probe set must include:

- selection spanning text nodes, shortcut copy, and context actions inside versus outside the selection;
- link click/context behavior for external, same-origin/relative and unsupported targets;
- pointer, keyboard and any touch behavior explicitly promised by the spec;
- package/import and focused frontend regression checks.

Add probes conditionally:

- For whole-message copy: rich blocks, named/bare links, exclusion of message chrome, multiple code blocks and preserved code-internal blank lines.
- For code-block copy: exact block payload, multiple blocks, keyboard activation and failure feedback.
- For multiple action surfaces: equivalent eligibility/disabled reasons, focus entry/return and native-gesture coexistence.
- For async notices or sheets: message/conversation changes and older completion unable to overwrite newer state.

Held-out acceptance found whitespace, fenced-code and internal-blank-line defects in the historical implementation. Use those as robustness probes only when the candidate selects the affected behavior; reproducing every historical probe is not a prerequisite for a narrower valid design.

## 6. Evidence and verdict

First run deterministic snapshot, path and leak checks, then use two blind semantic judges. Report decision handling, user burden, personalization, spec, design, downstream and cost separately as `win`, `tie`, `loss` or `insufficient evidence`, with concrete findings. Do not compute a total score and do not combine this historical regression with prospective pilots or clean holdouts.
