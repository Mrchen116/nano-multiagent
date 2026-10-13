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

## Closure review

- review_mode: closure
- finding_origin_head: `56d5d604baf37268e3c61ccc4bbf021023ad4922`
- validated_at: `ac40e9ed99d12110844c73b53ef581214a35c802`
- executed_base: `68aeae7509ba2498b6be74c611bd36052dbed114`
- reviewed_at: 2026-10-13
- result: passed — focus finding closed; no surviving findings

Reviewed only the finding repair in `56d5d604b..ac40e9ed9`: the workflow preserves its own revision's publisher in `RUNNER_TEMP` before checking out the selected source, invokes that external publisher, and the publisher resolves the candidate and Git checks from the selected checkout's working directory. The existing CLI tests now execute an external copy and enforce the Git child process working directory. Reused their 8 passing tests from `/tmp/bugfix591-publisher-fix.log`. Prior full-review coverage and unaffected validation remain applicable; this is not a new full review.

The focus finding **Keep the versioned publisher independent of the selected source checkout** is **closed**. Independently repeated the original offline scenario with source commit `8b023da56a5b45579b8a0a68463d953cf24d580c`, its actual old publisher still present in the source tree, the original SHA-format candidate, and the repaired publisher copied outside the source tree. With `RELEASE_VERSION=0.2.0`, the external publisher exited 0, called `gh release create v0.2.0 --title "Nano Node v0.2.0" --target 8b023da56...`, and promoted a manifest with `version=0.2.0`, the matching `source_commit`, and the verified original package checksum. Every git/gh/curl child was a local fixture; no real Release or production mutation occurred. Evidence: `/tmp/bugfix591-review-closure.log`.

```json
[]
```
