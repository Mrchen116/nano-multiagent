# Arm A base-repository receipt

This receipt records the eight formal `counterfactual-latest-base-v1` materializations. It contains stable content/Git identities only; no temporary directory or host-specific output path is retained.

The common construction is:

```text
Code@B + ProductClaims@B + DocsFramework@F + Workflow@W
```

All outputs use one parentless `main` commit authored by `Repository Bootstrap <repository@invalid>` at `946684800 +0000`, with message `initial repository`. The canonical `.git` envelope and each HEAD tree were checked by the shared validator.

| Case | Recipe SHA-256 | Content manifest | Root commit | Root tree | Docs mode |
|---|---|---|---|---|---|
| H01 | `d697babd...` | `8cc1ef93...` | `8d22680d...` | `340d117b...` | DP1 exact B move/link rewrite plus neutral navigation and a hash-bound W lifecycle-index slice |
| H02 | `f9cac53a...` | `f79a953b...` | `9fd64cf1...` | `27a34d88...` | preserve exact |
| H03 | `0546d75e...` | `c322a409...` | `6fced581...` | `48f7d7a9...` | preserve exact; `AGENTS.md` is W-owned |
| H04 | `3723e9c8...` | `5197e701...` | `c3e539ab...` | `18d71efb...` | preserve exact |
| H05 | `486c4ed2...` | `887e9363...` | `8068e9a7...` | `3ed2ff0e...` | preserve exact |
| H07 | `8f718353...` | `887e9363...` | `8068e9a7...` | `3ed2ff0e...` | preserve exact |
| P01 | `0b038d2f...` | `afcb5907...` | `6241a68f...` | `10c83e83...` | preserve exact |
| P02 | `ab020418...` | `afcb5907...` | `6241a68f...` | `10c83e83...` | preserve exact |

For every case, the scrub receipt proves:

- all outer treatment roots and undeclared instruction roots were removed;
- all direct pre-existing active change units and `docs/changes/retired/**` were removed;
- `drop_noncompleted_cross_references_v1` was independently derived from B; every completed archive unit that referenced a direct active/retired unit was removed as one whole root, and only the remaining B-consistent archive history was preserved;
- the final tree contains only the lifecycle index plus optional completed archive under `docs/changes/`;
- `docs/changes/feat-397-spec-design-agent-team` was absent and a case-insensitive `feat-397` scan across every path and text blob returned no hit;
- target atoms, case controls, symlinks and benchmark/treatment labels were absent.

The frozen archive-lineage root counts are H01 `3`, H02 `9`, H03 `8`, H04 `10`, H05 `10`, H07 `10`, P01 `8`, and P02 `8`. Their full root-list hashes and the common `path_and_text_all_eight_roots` leak assertion are recorded in the machine-readable receipt; the materializer receipts also retain each root's referenced B-noncompleted unit ids and presence result.

H01 additionally records one task-blind `drop_proposed_control` class: all ten preregistered obsolete root-control/proposal paths were present and removed. It proves that `docs/specs/CONTRIBUTING.md` is an exact move of B `docs/SPEC_GUIDE.md`, and that B `docs/specs/README.md` differs only by the two registered link replacements. Its composed `AGENTS.md` keeps B architecture boundaries while presenting natural current-repository/W workflow routing without baseline, cutoff, arm or benchmark language. Its change index binds the full F source hash and the output hash for the framework/lifecycle slice ending after `## 唯一定位`; per-file assertions confirm the later evidence/migration sections and their broken B-world links are absent, while both retained workflow links resolve.

The complete machine-readable hashes, scrub counts, projection/arm manifest identities and source archive identities are in [base-repository-A.json](base-repository-A.json).

Reproduce and verify all eight roots from the repository root:

```bash
.venv/bin/python \
  evals/spec_design_alignment/validate_dataset.py \
  --verify-base-repositories
```

This receipt covers arm A only. It does not claim suite readiness: A+USER remains blocked on `frozen_cross_fitted_profile`; B remains blocked on both `executable_agent_team_bundle` and `frozen_cross_fitted_profile`.
