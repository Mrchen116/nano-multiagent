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
