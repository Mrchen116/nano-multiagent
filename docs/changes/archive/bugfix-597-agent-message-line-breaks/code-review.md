# bugfix-597 Code Review

## Round 1 — full

- Reviewer: independent `review_agent_line_breaks`, `gpt-6.1-sol/high`.
- validated_at: `762d4a463a74260174fef73b78423030ad5c85cc`.
- executed_base: `737b73880bf9fcd20f41eaaa0f3b0820bc35bff2`.
- Scope: complete implementation diff (message rendering, package and lock, component tests, current Web UX spec).
- Result: one CONFIRMED P2; ordinary line breaks, explicit hard breaks and code content otherwise passed independent plugin reproduction. Existing test evidence reused.

### Finding and resolution

`<mention type="user" target_id="a-coder"/>\n第一行\n第二行` forms a type-7 HTML block. The old mention plugin retains the following prose as HTML nodes, so remark-breaks does not process those newlines. The implementation owner reproduced this in the existing mention component test, converted the literal prose portions into text nodes, kept root-level mention blocks within a paragraph, and moved remark-breaks after mention conversion. Message component regression and build pass after the repair. Closure review follows below.

## Integration validity

Main advanced from `737b73880` to `0b2bab6cf` with only feat-596 design/spec/prototype evidence changes. Rebase retained the implementation tree; no changed runtime or Web dependency files invalidate the existing backend, tooling or Web evidence. The mention repair changes Web source, so Web tests/build and focused independent review are rerun; backend and Python evidence remain valid.

## Round 2 — closure and patch

- Reviewer: same independent `review_agent_line_breaks`, `gpt-6.1-sol/high`.
- validated_at: `c8cc3798f9ea71d919dc9c4a839e1ab51fb25450`.
- executed_base: `0b2bab6cf30ebad2fd1ee0915019913d529deea1`.
- Scope: R1 finding closure and the changed mention conversion, plugin order, regression test and IM spec index; unrelated main design documents excluded.
- Result: `[]`, Approved. R1 finding closed. Independent reproduction confirms one paragraph containing the mention and two line breaks; inline mention, quote/list line breaks, escaped script/event-bearing HTML, code indentation/blank lines and explicit hard breaks retain their expected behavior. Component/build evidence reused.
- Owner verification: the repaired frontend full suite also completed successfully (92 files, 862 tests).

The only remaining unit changes are validation notes and archive movement; they do not alter the reviewed product tree. Final integration base and effective version are recorded in the PR validation summary.

### Final sync

Main then advanced to `0e0c567978a89b33248cf1c342fb3311df45025b` (bugfix-595 onboarding/auth layout and its documentation). Its CSS additions are scoped to authentication/onboarding, with no chat/Markdown selectors or runtime dependency changes. The three reviewed chat implementation/test files are byte-identical to R2; code review and browser evidence are retained. The final integrated frontend suite/build and docs checks are run again; backend/tooling evidence remains valid. The final PR base is this commit.
