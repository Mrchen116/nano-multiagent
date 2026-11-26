# M1 Verification Summary — `feat-791-plugin-tool-settings`

## 1. Automated Test & Build Verification

- **Workspace Build & Typecheck**:
  - `pnpm build` — passed across all 8 workspace packages and node installer candidate.
  - `pnpm typecheck` — passed across all workspace packages and `evals`.
  - `pnpm check:ios-runtime` — passed.
- **Backend & Contract Vitest Suites**:
  - `packages/product-contracts/tests/capabilities.test.ts` (13/13 passed): `plugin_management` Feature catalog metadata, pre-`feat-791` stateless continuity (allowing vs excluding `plugin_manager`, missing `nano-plugin-development` skill availability), standalone `cordis_inspect_*` selection after disabling `plugin_management`, plugin/fixed tool toast block reasons, and mode-scoped static `tool_allowlist` purification (`single_thread` preserving `send_message`, `legacy` memory preserving `memory`).
  - `packages/dsh-integration/tests/workspace-tools.test.ts` & `packages/dsh-integration/tests/capabilities.test.ts` & `packages/dsh-integration/tests/cordis-inspect-and-web.test.ts` (passed): post-`refresh()` `WorkspaceOwner` notification ordering, `plugin_bundle` / `plugin_title` attribution on `dsh-agent-context` and workspace plugin tools, `dsh-agent-context` disable unloading tools from runtime catalog, pre-`feat-791` runtime continuity, and busy withdrawal lock.
  - `apps/node/tests/capabilities.test.ts` & `apps/node/tests/configuration.test.ts` (18/18 passed): purified static `tool_allowlist` persistence alongside `dsh-agent-context` and workspace plugin tools, offline/display snapshot `plugin_management` continuity.
  - `apps/im-server/tests/agent-settings.test.ts`, `personal-agent.test.ts`, `personal-agent-creation.test.ts`, `plugins.test.ts`, `control.test.ts` (passed): `createAgent`, `patchAgentSettings`, `prompt-preview`, and PA creation continuity & static allowlist purification.
- **Web Frontend (`src/IM/frontend`)**:
  - `npm --prefix src/IM/frontend run test` (129/129 test files passed) & `npm --prefix src/IM/frontend run build` (passed): default-collapsed `PillSelector`, sibling `管理插件 →` action (`nestedButtons === 0`), 2s floating toast for plugin-provided and mode-fixed tools, real-time cross-section cache invalidation on immediate and `pending -> settled` plugin transitions, and symmetric dirty-baseline normalization.
- **Native iOS (`src/IM/ios`)**:
  - `xcodebuild -project src/IM/ios/NanoIM.xcodeproj -scheme NanoIM -destination "platform=iOS Simulator,id=1CE31893-672F-495A-B2B5-3ACF39A7A257" test` (41/41 tests in 7 suites passed): `CapabilitySelectionTests.pluginManagementContinuityPluginBlocksAndModeSanitization` and `AgentContractsTests.creationAndPreviewKeepGlobalToolsAndDiscoveryIntent`.
- **Python & Documentation Checks**:
  - `pytest tests/unit/test_e2e_catalog.py -q` (5/5 passed), `ruff check` & `ruff format --check` on modified Python files, `./scripts/docs-check` (passed).

## 2. Isolated Live E2E & Visual Acceptance (`/tmp/nano-e2e-791-after`, `--profile daily`)

- **Features & Default-Collapsed Tools (`1280x800` & `390x844`, `简体中文`)**:
  - `PA · 个人助手` -> `配置` tab displays **「插件开发与管理」** (`plugin_management`) enabled in the 2x3 `特性开关` grid.
  - `工具允许列表` renders collapsed by default (`aria-expanded="false"`, `已启用 47 / 52`) with a sibling `管理插件 →` `<button>` (`document.querySelectorAll('button button').length === 0`; on `390x844` mobile, toggle `16..217px` and action `286..368px` fit cleanly with 69px gap).
  - `/settings/agents/new` (`AgentCreatePage`) renders `工具允许列表` collapsed by default without `管理插件 →`.
- **100% Active Runtime Tools & 2s Guidance Toast**:
  - Expanding `工具允许列表` displays all 52 active runtime tools, including `cordis_inspect_list`, `cordis_inspect_query`, `new_context`, `get_context_remaining`, `notes`, and `history`.
  - Clicking `notes` keeps it enabled without layout jump and displays the 2s auto-fading floating toast `此工具由插件「dsh-agent-context」提供，请在「插件」页关闭`.
- **Real-Time Plugin Toggle Sync & Clean Save**:
  - Clicking `管理插件 →` opens `?view=plugins`; disabling `dsh-agent-context` and switching back to `配置` tab without reloading immediately updates `工具允许列表` to `已启用 43 / 48` and removes `new_context`, `get_context_remaining`, `notes`, and `history` with `无改动` and zero `missingTools` error.
  - Editing `描述` and clicking `保存 Agent` while `dsh-agent-context` is disabled saves cleanly (`已保存`, `v2 -> v3`).
  - Re-enabling `dsh-agent-context` in `插件` tab and returning to `配置` tab immediately restores `已启用 47 / 52` and all 4 tools.
  - Stack torn down cleanly via `./scripts/e2e-down.sh --wt /tmp/nano-e2e-791-after && rm -rf /tmp/nano-e2e-791-after`.
