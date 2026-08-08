# feat-515-M1 real-stack and browser acceptance

Date: 2026-08-07 (Asia/Shanghai)

## Environment

- Checkout: isolated `feat-515-M1` worktree.
- IM: `http://127.0.0.1:60550`.
- Frontend: Vite at `http://127.0.0.1:60599`.
- Primary Gateway: `wt-feat-515-M1-98571`.
- Secondary Gateway: `wt-feat-515-M1-second`, with a separate config directory,
  lifecycle state, workspace base, node identity, and process.
- Browser: headed Chromium controlled through the Playwright CLI.
- Runtime config, credentials, databases, logs, and workspaces were temporary and
  are not part of this evidence commit.

## Results

| Claim | Baseline | Method | Result | Locator | Limit |
|---|---|---|---|---|---|
| The Workspace card follows Identity and precedes Behavior. | The prototype requires this exact information hierarchy. | Opened the real create page at 1440 x 1000 and inspected the accessibility tree and rendered page. | PASS: headings appeared in `Identity -> Workspace -> Behavior` order. | `create-desktop-default.png` | Visual evidence covers the English locale used for acceptance. |
| Default is selected initially and desktop presents the two choices side by side. | The prototype selects the node default path initially. | Loaded a fresh create form on the primary Gateway. | PASS: default radio was checked; custom was unchecked; no custom field was rendered. | `create-desktop-default.png` | None. |
| Custom mode explains the target node and preserves long-path layout. | The browser must not infer remote filesystem semantics. | Selected Custom path and inspected the 1440px render. | PASS: node-specific copy, parent requirement, confirmation rule, and wrapping remained inside the card. | `create-desktop-custom.png` | Filesystem validity is still decided by the Gateway. |
| The 390px layout stacks both choices and keeps the input inside the card. | The prototype requires a single-column narrow layout. | Resized the same real browser to 390 x 844, selected Custom path, and scrolled the Workspace card into view. | PASS: choices were stacked, the input fit the viewport, and Workspace still preceded Behavior. | `create-mobile-workspace.png`, `create-mobile-custom.png` | The fixed mobile navigation intentionally occupies the bottom edge. |
| An existing directory requires explicit confirmation with zero creation side effects. | The target contained `sentinel.txt` before the request. | Submitted `existing-path-agent` through the UI with `confirm_existing_workspace=false`; inspected browser network, SQLite, Gateway YAML, target files, and target path. | PASS: HTTP 409 with `workspace_confirmation_required`; no profile/config entry was written and the sentinel remained unchanged. | `create-existing-confirmation.png`; browser request 125 during the run | Browser request numbering is session-local; the stable response fields are recorded here. |
| Retrying the identical draft after checking confirmation succeeds without overwriting files. | The first request left the draft and target unchanged. | Checked the displayed acknowledgement and resubmitted in the browser. | PASS: HTTP 201 navigated to `/settings/agents/existing-path-agent`; SQLite and Gateway YAML stored the exact canonical root with provenance `false`; the sentinel content remained `pre-existing content`. | Runtime DB/YAML/file assertions recorded in this report | Temporary runtime data was removed after acceptance. |
| Default creation returns the Gateway canonical root and provenance. | Primary workspace base was the isolated `.gateway-workspace` directory. | Created `default-path-agent` through the UI without changing the default mode, then inspected SQLite, Gateway YAML, and filesystem. | PASS: root ended in `.gateway-workspace/default-path-agent`, provenance was `true`, and the directory was created. | Browser request 137 during the run | Temporary runtime data was removed after acceptance. |
| Stable path failures remain side-effect free. | Neither failure Agent existed before the request. | Called the real HTTP create endpoint against the primary Gateway and inspected profile/config/path state after each response. | PASS: missing parent returned HTTP 422 `workspace_parent_missing`; same-node reuse returned HTTP 409 `workspace_already_assigned` with `agent_id=existing-path-agent`; neither failure persisted a profile or config entry. | HTTP/API/DB/file assertions recorded in this report | Unit and integration suites cover the additional unusable-parent, non-directory, and initialization-failure branches. |
| Ownership is node-local, not global in IM. | Two isolated Gateway processes were online in one IM service. | Created `cross-node-second-agent` on the secondary Gateway using the exact root string already owned by `existing-path-agent` on the primary Gateway. | PASS: HTTP 201; SQLite contained both Agents with the same root and different `node_id` values; the secondary YAML stored its own assignment; the sentinel remained unchanged. | `create-dual-gateway.png` | Both Gateways ran on one physical host, but config, lifecycle state, workspace base, identity, process, and ownership index were isolated. |
| Existing detail remains provenance-neutral. | The reference contract forbids a new Default/Custom label on existing detail pages. | Opened the newly created custom Agent detail and inspected the accessibility tree. | PASS: `Workspace & Runtime` showed only the read-only root and existing runtime fields; no provenance label appeared. | Accessibility-tree assertion recorded in this report | No separate screenshot was needed because the observable contract is textual. |
| Browser runtime is clean after the expected recoverable 409. | The confirmation response is an expected application branch. | Reloaded after the journeys, inspected console messages and the network log. | PASS: final console check reported 0 errors and 0 warnings; network showed the expected 409 followed by 201 responses and successful follow-up reads. | Playwright console/network assertions recorded in this report | The initial expected 409 briefly appeared as a failed network request before reload. |

## Prototype comparison

| Prototype contract | Comparison |
|---|---|
| Workspace card between Identity and Behavior | Must-match satisfied on desktop and mobile. |
| Default/custom exclusive choice with default selected | Must-match satisfied. |
| Custom path copy identifies the selected node and confirmation rule | Must-match satisfied. |
| Existing-directory warning is prominent and requires a checkbox before retry | Must-match satisfied. |
| Existing design tokens and spacing may be adapted | Adapted to the current Agent settings card and form tokens without changing hierarchy. |

## Screenshot integrity

| File | Dimensions | SHA-256 |
|---|---:|---|
| `create-desktop-default.png` | 1440 x 1000 | `e5c6e79cf33538c42535a14dd5f1db43ba57e5c90727ad5b45b3f34455d2cffb` |
| `create-desktop-custom.png` | 1440 x 1000 | `58cdc2d5e5066110d32c6c89b42fd5ca18c16b9237a641603ba155f4691ec1a9` |
| `create-existing-confirmation.png` | 1440 x 1000 | `bb9439deefa319461d9dfb13c4d02214af0014a67d6e2cbea40602832939a68f` |
| `create-dual-gateway.png` | 1440 x 1000 | `df060de11177602a18916784121ab3b45e1e40e53dccc4747ba4542a341d69a8` |
| `create-mobile-custom.png` | 390 x 844 | `781f5c221c7f04d00e9b81cc952038db08623d865158bb4e5b9145ccac7a9880` |
| `create-mobile-workspace.png` | 390 x 844 | `a40a5950d92603bf6b6228080ad9288c247736d996346670f69d90a0c96dce37` |
