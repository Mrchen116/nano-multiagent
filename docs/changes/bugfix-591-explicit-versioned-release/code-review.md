# Code review

- review_mode: full
- validated_at: `56d5d604baf37268e3c61ccc4bbf021023ad4922`
- executed_base: `68aeae7509ba2498b6be74c611bd36052dbed114`
- reviewed_at: 2026-10-13
- result: changes requested — 1 CONFIRMED finding

## Scope and evidence

Reviewed the complete 12-file unit diff, the publishing workflow and CLI, the unchanged candidate builder, IM manifest routes, shell installer, deployment instructions, and the three affected existing test files. The worktree was clean at the frozen implementation HEAD before this report was added.

Reused the matching frozen-tree validation: 27 focused tests (`/tmp/bugfix591-green.log`), full build and typecheck (`/tmp/bugfix591-build.log`, `/tmp/bugfix591-typecheck.log`), 74 files / 255 TypeScript tests (`/tmp/bugfix591-tests.log`), 56 Python tests (`/tmp/bugfix591-python.log`), Ruff and documentation integrity (`/tmp/bugfix591-ruff.log`, `/tmp/bugfix591-docs.log`). No Release was created and no production state was changed. Download/publish fixtures are not real GitHub acceptance evidence.

## Findings

```json
[
  {
    "file": ".github/workflows/node-release.yml",
    "line": 51,
    "summary": "[P2] Keep the versioned publisher independent of the selected source checkout",
    "failure_scenario": "Dispatch the new workflow with version=0.2.0 and commit=8b023da56a5b45579b8a0a68463d953cf24d580c (the deployed source). actions/checkout restores that commit's old scripts/publish-node-release.mjs, which ignores RELEASE_VERSION and calls gh release create node-8b023... with title Nano Node 8b023...; its manifest still uses the SHA and lacks source_commit. Since that production SHA already has a Release, the real run fails as a duplicate instead of publishing v0.2.0. Selecting another pre-fix source without a Release would create another SHA-named release. The documented interface permits choosing a CI-passed fixed source commit, so checking the input before checkout does not enforce the promised versioned publication policy. Execute the reviewed versioned publisher independently of the source checkout, or reject an unsupported publisher before any upload.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

Independent offline reproduction: extracted the actual publisher from `8b023da56a5b45579b8a0a68463d953cf24d580c`, set `RELEASE_VERSION=0.2.0`, and replaced every git/gh/curl child with local executable fixtures. Exit status was 0; captured Release arguments and the promoted manifest retained SHA naming. Evidence: `/tmp/bugfix591-review-old-source.log`. The existing tests always execute the new publisher directly, so their passing result does not cover workflow checkout of an older publisher.
