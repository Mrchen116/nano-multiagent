# H05 private rubric — Agent workspace root selection

Keep this directory out of candidate exports. The historical URL is unavailable and supplies no evidence beyond the public brief.

## 1. Decision handling and user burden

D01-D04 are the smallest material owner-choice bundle: default/custom semantics, immutability, filesystem rules and uniqueness scope. They should be presented together with recommendations, not as a long serial questionnaire. D05 expects a grounded commercial interaction proposal. D06-D09 are architecture facts the Agent must derive; asking the owner which host resolves paths or whether forbidden imports are acceptable is negative burden. D10 is a bounded no-migration default.

## 2. Spec oracle

A strong spec makes new-Agent creation testable for managed default and custom roots, defines immutable post-create behavior, parent/target validation, existing-directory warning, same-node uniqueness and cross-node independence, and exposes honest success/conflict/error outcomes. The UI shows the effective default path and makes custom entry discoverable without large mode cards. Existing Agents are unchanged.

Changing only the form, enabling post-create relocation, or using global path-string uniqueness is critical. Requiring a particular label or pixel layout is not.

## 3. Design oracle

The selected Gateway owns expansion, normalization, filesystem checks, directory creation and node-local reservation. IM forwards opaque values and persists Gateway-returned canonical path plus default provenance; it does not inspect its own host filesystem or import PA/agent. The design closes create-operation failure/compensation and covers capability/default data, profile persistence, API projection, UI and tests.

Equivalent transactional arrangements pass. Penalize frontend-only validation, check-then-write races, provenance inferred on the wrong host, or an unrequested relocation subsystem.

## 4. Hidden downstream probes

Probe default creation, absent target with existing parent, missing parent, existing directory warning, file target, duplicate same-node allocation, same path string on two nodes, Gateway failure/IM persistence failure, immutable detail/API behavior, desktop/mobile UI, and package import contracts.

## 5. Verdict

Report decision handling, user burden, spec, design, downstream feasibility and cost separately. Semantic correctness outranks reproduction of historical field/component names.
