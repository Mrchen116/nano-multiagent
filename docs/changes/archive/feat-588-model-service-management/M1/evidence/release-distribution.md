# Installation release distribution evidence

## Claim and baseline

Implemented S9 / M1 F,G in the shared `codex/feat-588-model-services` worktree, starting at `e2e7aae53bd33a3257f33616d0311f1070d1e97a` (PR337 plus origin/main `6275f271d`). This is implementation and isolated regression evidence; no GitHub Release was published and no production service was deployed.

## Observable behavior

- IM accepts only a complete manifest whose full 40-character source SHA matches the fixed `Mrchen116/nano-multiagent` HTTPS Release URL. It serves the script and manifest without a local archive. The legacy archive route returns an empty `302` with `no-store`, to that same URL.
- The script fetches one manifest from its server-configured IM origin, downloads the pinned GitHub asset directly, checks SHA-256 before extraction/promotion, and keeps prior releases/configuration after failure. No latest lookup or IM package fallback exists.
- `build-node-release.mjs` reuses the runtime allowlist and produces `manifest.candidate.json`. It does not promote that candidate to the deployable `manifest.json`.
- `publish-node-release.mjs` checks the candidate against the clean checkout, local package bytes and public repository, creates a fixed Release without overwrite, downloads that asset using curl with config disabled and HTTPS redirects, compares its bytes, then atomically promotes `manifest.json`. Existing deployable metadata survives failed anonymous download/hash verification.

## Test ownership and results

Existing `apps/im-server/tests/onboarding.test.ts` installation coverage was rewritten/extended for manifest-only availability, server origin injection, immutable URL/redirect behavior, rollback to the previous manifest, and malformed metadata. Its owner/transfer coverage was retained. Existing `apps/node/tests/installer.test.ts` runtime extraction coverage was retained and extended for direct download, repeated installation and failure preservation. Existing `bootstrap.test.ts` retains actual Node identity/configuration preservation coverage. The new `apps/node/tests/node-release.test.ts` owns the separate publishing-command boundary: uploaded bytes, anonymous verification, manifest promotion and refusal to overwrite an existing Release. All run under the normal `pnpm test` backend gate.

- Initial failing verification: `pnpm exec vitest run apps/im-server/tests/onboarding.test.ts` produced 2 failures / 7 passes: old implementation returned 503 for a complete manifest without a local archive.
- Final focused command: `pnpm exec vitest run apps/im-server/tests/onboarding.test.ts apps/node/tests/installer.test.ts apps/node/tests/bootstrap.test.ts apps/node/tests/node-release.test.ts` — 4 files, 18 tests passed.
- `pnpm --filter @nano/im-server typecheck` — passed.
- `bash -n apps/im-server/assets/install.sh`, `node --check scripts/build-node-release.mjs`, `node --check scripts/publish-node-release.mjs`, `git diff --check` — passed.
- `node scripts/build-node-release.mjs` — produced one candidate archive. Direct SHA-256 comparison matched its manifest; archive inventory contained 931 entries and no `.env`, `node_modules`, `.git`, `config.yaml`, database or log entries. This local candidate used the already-built shared worktree outputs; final release must use the clean fixed-commit workflow.

The installer tests replace curl only in each isolated child process PATH, accepting exactly the expected IM manifest and pinned GitHub asset URL. The publishing tests similarly replace git/gh/curl commands and never contact GitHub. These fixtures prove local behavior, not public download availability. Temporary test roots are removed; no real config or node service is modified.

## Release and deployment handoff

When publication is explicitly authorized, manually dispatch `.github/workflows/node-release.yml` with the reviewed full source commit SHA. It checks out that commit, installs frozen dependencies, runs the existing `pnpm build` once, typechecks/tests, and runs `node scripts/publish-node-release.mjs`. Only after anonymous hash verification does it upload the artifact `node-manifest-<full SHA>`, containing the deployable `manifest.json`.

A release at `node-<full SHA>` is never overwritten. If publishing succeeds but later verification fails, the public Release may already exist; the job leaves the prior local manifest unchanged, and rerunning publication refuses that existing Release. Resolve that publication explicitly without replacing its asset; do not deploy the candidate manifest.

Deploy the verified artifact together with the matching IM build, to its configured `IM_NODE_RELEASE_DIR` (default `dist/node-release`). IM needs only `manifest.json`; package bytes remain on GitHub. A rollback must restore the earlier matching IM build and verified manifest together. The workflow does not deploy or change an online manifest itself.

## Limits

Actual anonymous download from a newly published Release, real installer binding, browser acceptance and production rollback are not established by these command fixtures. Actual Release publication and its anonymous hash evidence belong to the authorized release operation. Existing bootstrap tests establish identity preservation locally; the installer shell fixture's fake setup executable establishes invocation/origin and file preservation only.
