# feat-515-M1 — Progress

## Baseline

- Branch: `milestone/feat-515-M1` at `a5e64e4fa0565179417ed96056838ce40a69ebc6`.
- Python: related Gateway/IM ownership, protocol, create, DB and config contract tests — 91 passed, 2 dependency deprecation warnings.
- Frontend: `agent-create.test.tsx` + `im-agent-config-api.test.ts` — 21 passed.
- Prototype: `../prototype.html`; four `must-match` rows copied into `tasks.md`.

## R1 — Gateway 本地 workspace creation boundary

- Context: 既有 handler 在校验前直接 `ensure_workspace_defaults()`，没有 existing-directory 确认、canonical ownership 或来源持久化；新建前 preview root 由 IM 主机派生。
- Decision: Gateway handler 现以本地 config + 文件系统为创建边界，先 canonicalize/查占用/查 parent 与 target，再按确认状态初始化；错误返回 typed outcome。`AgentWorkspaceConfig` 持久化 `workspace_is_default` 并随 register 上报；preview 通过同一节点 factory 只解析不创建。
- Rationale: 路径语义、ownership 与 runtime 都属于选中节点；IM 与浏览器不具备可靠的远端文件系统视角。
- Evidence:
  - Tests: 新增/扩展 Gateway creation/protocol/YAML/register 测试；focused suite 79 passed, 2 dependency deprecation warnings。
  - Entry: Gateway 的公开 `handle_agent_create` seam 覆盖 default/custom、missing/unusable parent、non-directory、confirmation、initialization failure、canonical collision 与 node-scoped ownership；真 HTTP/WS 入口留 R2/R5。
  - Frontend State Matrix: N/A（R3）。
  - Browser QA: N/A（R5）。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_workspace_creation.py`、`test_gateway_workspace_creation_protocol.py`、`config/test_workspace_provenance.py`；79 passed 汇总包含受影响旧 Gateway 测试。
  - Visual/Interaction: N/A（R5）。
  - Prototype Comparison: N/A（R5）。
- Rollback: revert `f542787d8`。
- Commits: `f542787d8`
- Next: R2 structured IM outcome、opaque mirror/provenance、migration/register 和 HTTP 契约。

## R2 — WS/HTTP structured outcome 与 opaque IM mirror

- Status: TODO

## R3 — Workspace 创建 UI 与 i18n

- Status: TODO

## R4 — 回归矩阵与质量门禁

- Status: TODO

## R5 — 隔离真栈与浏览器原型对照

- Status: TODO

## Promotion Candidates

None.
