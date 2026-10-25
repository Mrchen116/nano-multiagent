# Delivery and retained gates

- Implementation frozen at `2f9765d3f`; includes the bounded Linux CI PTY cleanup-order correction.
- Final synchronization: `origin/main` remains `5b09dbe82292e0b5005d70b5561a74df1885d8f1`; no incoming delta or conflicts.
- Gate 2: independent full design review Approved, 0 CRITICAL/0 WARNING (`design-review.md`, reviewed author tree `f00653f1a`; accepted at `5b09dbe82`).
- Code review: full review plus bounded fixes through `2f9765d3f`, final findings `[]`.
- Verification: local implementation and corrected delta aligned through `2f9765d3f`, 0 confirmed issues; fixed Linux CI pending at the report snapshot.
- Product: independent real Web R1/R2/R3, final PASS at `6769c89cb`; earlier failures remain recorded with their closure.
- Context and test provenance/limits are in `implementation.md` and the independent reports; no final whole-suite local success is invented from partial reruns.

The final documentation commit merges the already verified shared-runtime scenario into the current Gateway spec, preserves the architecture correction, archives this whole unit and fixes the incident's sibling-unit link. These changes do not alter behavior, design decisions, test inputs or the model Context. All gates are retained for that final integrated tree. The PR records its exact head as `effective_through`, and the unchanged main SHA as `effective_base`, alongside each actual `validated_at`.

The first remote CI passed frontend and 735/736 backend tests, but exposed a Linux PTY cancellation race. The self-contained correction at `2f9765d3f` closes owned terminals through public DSH APIs before cancelling remaining Jobs. Independent code review and verification inspected this bounded delta, retained the unaffected Web/Context/design conclusions, and accepted all seven affected native tests passing locally. Remote Linux confirmation remains an explicit delivery gate; the PR records the eventual result rather than treating the earlier run as successful. Subsequent report-only commits retain these source gates.

The obsolete feat-657 split-process migration is explicitly withdrawn in its archived design and deployment prompt. Existing production remains untouched; no deployment or release is authorized by this PR. The ordinary shared home and PA homes continue unchanged.

All task-owned real test services were stopped using e2e-down; the dedicated rollback660 simulator was deleted after confirming it was Shutdown. Local evidence is preserved under `/Users/czj/.codex/reports/bugfix-660/`. The development worktree remains for PR review and is removed only after confirmed merge under the repository cleanup rules.
