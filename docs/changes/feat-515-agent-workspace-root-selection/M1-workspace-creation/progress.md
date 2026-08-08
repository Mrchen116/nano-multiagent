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

- Context: IM 过去会在本机 `expanduser().resolve()` Gateway 返回的 root，live snapshot 也能覆盖持久化 mirror；`agent.created` 只支持成功 payload，profile 没有 nullable provenance。
- Decision: `agent.created` waiter 透传 structured workspace error；HTTP 仅按稳定 code 映射 409/422，并在失败时不落 profile。SQLite 新增 nullable `workspace_is_default`，旧行保持 NULL/公开 false；register 只在 provenance 为空时补 seed。所有既有 Agent workspace RPC 使用不解析的持久化字符串，live snapshot 不再覆盖 root。节点级 preview 只转发 mode/id/custom root，由 Gateway 解析。
- Rationale: IM 可能与 Gateway 分属不同主机；路径 canonicalization、filesystem validation 和 provenance 都必须由目标节点持有，IM 只保留 opaque routing value。
- Evidence:
  - Tests: focused IM contract/integration/schema suite 34 passed；扩展风险套件先得到 509 passed/1 个旧 live-root 断言失败，按新 opaque mirror 契约改写该断言后单测回归通过。
  - Entry: 真 HTTP + Gateway WS correlation 覆盖 `workspace_confirmation_required` 顶层 409 且无 profile；API adapter 前端分支留 R3。
  - Frontend State Matrix: N/A（R3）。
  - Browser QA: N/A（R5）。
  - E2E/Regression: `test_workspace_root_mirror_contract.py` 覆盖 mirror/live/capabilities/prompt/cron/skills/heartbeat 的同一 opaque 字符串；register 测试覆盖 true/false、旧帧 NULL 与非 NULL 不覆盖。
  - Visual/Interaction: N/A（R5）。
  - Prototype Comparison: N/A（R5）。
- Rollback: revert `c1ee3b3bf`。
- Commits: `c1ee3b3bf`
- Next: R3 Workspace 创建卡、默认/custom payload、稳定错误码 UI 分支、确认重试与中英 i18n。

## R3 — Workspace 创建 UI 与 i18n

- Context: 创建页过去把 `workspace_root` 强制归一为 null；API error 只保留 status/detail，无法按 Gateway 稳定 code 呈现确认、占用和路径问题；preview 也没有传 workspace intent。
- Decision: 在 Identity 与 Behavior 之间加入默认选中的 Workspace 卡；custom 模式提交目标节点输入，客户端只检查空值，节点负责其余校验。`AgentConfigRequestError` 保留 `code`/`agent_id`；existing-directory 409 展示醒目确认区，勾选后用同一草稿重试并仅把 `confirm_existing_workspace` 改为 true。preview 同步传 mode/id/root。样式在 720px 下切单列，中英文文案完整。
- Rationale: 稳定 code 是交互分支契约，路径 detail 只是展示信息；确认必须可恢复且不能丢失表单草稿。创建页选择不改变既有详情页的只读 Workspace & Runtime 展示。
- Evidence:
  - Tests: targeted API/create Vitest 28 passed；frontend 全套 63 files / 611 tests passed（保留既有 act/user-stream stderr）；production `tsc -b && vite build` 成功，仅既有 chunk-size warning。
  - Entry: API adapter test 覆盖 code/agent_id 与 preview intent；创建页覆盖默认 null、custom root、空路径、confirmation retry、assigned Agent、卡片顺序与 preview default intent。
  - Frontend State Matrix: default/custom/empty/error/submitting/confirmation/mobile CSS 均落到组件或测试；offline/loading 沿用原页面门禁。
  - Browser QA: 真浏览器截图、console/network 与 390px 检查留 R5。
  - E2E/Regression: 全 frontend suite 611 passed；既有 Agent detail 测试包含在全套且实现文件未增加 default/custom 来源标签。
  - Visual/Interaction: `.im-workspace-*` 复用现有卡片 token，desktop 两列、窄屏单列，长路径 `overflow-wrap:anywhere`。
  - Prototype Comparison: Workspace 卡位置、二选一、字段说明与 existing notice 已实现；真实截图对照留 R5。
- Rollback: revert `c2bb68918`。
- Commits: `c2bb68918`
- Next: R4 全量风险门禁与 docs，然后 R5 隔离真栈/浏览器验收。

## R4 — 回归矩阵与质量门禁

- Context: R1-R3 改动同时跨 Gateway/IM/SQLite/React；新增 workspace 交互最初继续扩展了已超过 400 行的 `agent-create.test.tsx`，不符合测试文件结构约束。
- Decision: 将五条 Workspace 创建交互移到 204 行的 `agent-create-workspace.test.tsx`，原文件只保留原有创建/离开/能力行为和默认 payload 接线。全仓 Python、前端单 worker、ruff、build、docs 与 diff 门禁统一重跑。
- Rationale: 新行为拥有清晰语义 owner，且单 worker frontend 全套能规避当前机器高负载下默认并发的无关 5 秒 timeout，不掩盖真实失败。
- Evidence:
  - Tests: Python `pytest -m 'not e2e' -q` — 3035 passed, 24 deselected, 16 dependency warnings；frontend `--no-file-parallelism --maxWorkers=1` — 64 files / 611 tests passed。
  - Entry: Gateway/IM/HTTP/frontend 所有本 milestone focused owners 均包含在全套门禁。
  - Frontend State Matrix: targeted 28 passed，production build 成功；UI 真浏览器状态留 R5。
  - Browser QA: N/A（R5）。
  - E2E/Regression: `ruff check .`、`git diff --check` 通过；`scripts/docs-check` — 220 maintained Markdown sources / 66 required routes。
  - Visual/Interaction: N/A（R5）。
  - Prototype Comparison: N/A（R5）。
- Rollback: revert `0198d43c1`（测试结构）；R1-R3 功能 commit 分别见前述 roadpoint。
- Commits: `0198d43c1`
- Next: R5 隔离单/双 Gateway 真栈、desktop/390px 浏览器验收与证据落盘。

## R5 — 隔离真栈与浏览器原型对照

- Context: unit/integration 测试已覆盖协议和路径分支，但仍需证明真实 IM/Gateway/Vite/Chromium 组合、窄屏布局以及 node-local ownership 在两个进程中成立。
- Decision: 用 worktree runbook 启动端口隔离的 IM、主 Gateway 和 Vite；第二 Gateway 使用独立 config/runtime/workspace base/node identity/process 接入同一 IM。浏览器完成 default/custom、已有目录首次拒绝和确认重试，API 补测 missing parent、同节点冲突和跨节点同字符串 root；SQLite/YAML/文件系统逐项取证。
- Rationale: 浏览器证据验证用户可见状态和恢复式交互，双 Gateway 证据验证 ownership 位于节点而非 IM；二者不能由组件测试互相替代。
- Evidence:
  - Tests: 浏览器网络记录显示已有目录 `409 workspace_confirmation_required` 后相同草稿确认重试 `201`；default 创建 `201`；真实 API 得到 `422 workspace_parent_missing` 和 `409 workspace_already_assigned`。
  - Entry: 主节点 `wt-feat-515-M1-98571` 和第二节点 `wt-feat-515-M1-second` 同时 online；IM 为 `127.0.0.1:60550`，Vite 为 `127.0.0.1:60599`。
  - Frontend State Matrix: desktop default/custom、existing confirmation、dual-node selection、390px custom card 均完成真实 Chromium 验收。
  - Browser QA: 最终 console 为 0 errors / 0 warnings；network 含预期 409、随后 201 与成功 follow-up reads；既有详情只展示 read-only Workspace Root，无来源标签。
  - E2E/Regression: 首次 existing 请求后 profile/YAML 均无写入；确认后 root/provenance 为 exact canonical string/false，sentinel 未变；default root/provenance 为 Gateway base 下路径/true；missing/assigned 失败均无 profile/YAML/path 副作用。
  - Visual/Interaction: 1440 x 1000 和 390 x 844 截图与完整结果位于 `evidence/acceptance.md`；长路径不撑破卡片，窄屏模式卡单列。
  - Prototype Comparison: Identity -> Workspace -> Behavior、默认选中、custom 节点说明、existing warning/checkbox 四项 must-match 全部满足。
  - Dual Gateway: 第二节点以已由主节点 Agent 使用的同字符串 root 创建另一 Agent 得到 HTTP 201；SQLite 中两个不同 `node_id` 保留同一 root，两个 Gateway YAML 分别持有本地 assignment，sentinel 未变。
- Rollback: revert `d521f05d5`（durable evidence）；功能 rollback 见 R1-R4。
- Commits: `d521f05d5`
- Next: milestone 集成到 `unit/feat-515`，释放浏览器、双 Gateway、IM/Vite 与所有 worktree runtime 文件。

## Promotion Candidates

None.

## Round 1 correction — duplicate immutability and remote session-log authority

- Lineage:
  - Verification failure snapshot: `015711133dbd10e9932e806ad1fb904178527b80`, `CRITICAL-1`, `CRITICAL-2`, and `WARNING-1` in `../verification.md`.
  - Independent browser acceptance: `e813c45f10fc11a33f0e75358c810e1a0fe1aa5e`, which reproduced a second create changing `review_default_515` from its default root to `.review-duplicate-id-515`.
  - Follow-up code review added lost-response retry, prompt-preview correlation, concurrent local create, and ownerless provenance refresh cases to the same correction.
- Root causes:
  - HTTP create trusted client `owner_id`, ignored ownerless duplicates, and composed a non-atomic read with profile upsert; Gateway creation likewise had no Agent-ID guard.
  - `ConversationRepository` mixed durable IM projection with Gateway-local runtime discovery by recursively scanning and opening a mirrored workspace path.
  - Prompt-preview let resolver `ValueError` escape the Gateway receive loop, and register upsert preserved stale ownerless provenance instead of the latest Gateway result.
- Decisions:
  - The app owns one serialized create check/Gateway/store boundary; repository creation is insert-only; authenticated owner is authoritative. Gateway serializes its local check/publish boundary, treats same-ID/same-root as an idempotent recovery, and rejects divergent roots before initialization.
  - IM projects only `source_agent_id`; list/sync/detail ask the owning Gateway to resolve the session log using logical IDs. Only Gateway reads `.nanoassistant/sessions/**/*.jsonl`; the returned path remains opaque in IM.
  - Node preview converts invalid path resolution into the existing structured workspace error envelope, while ownerless register explicitly refreshes `workspace_is_default` from the node seed.
- Red-green evidence:
  - Initial focused baseline: `55 passed, 2 warnings`.
  - New tests first failed at the missing insert-only exception/API, then the complete correction matrix passed: `115 passed, 7 warnings`.
  - Expanded IM + affected Gateway suite: `442 passed, 22 warnings in 45.13s`.
  - Before rebase, the complete frontend suite passed with only existing test warnings.
  - After rebasing onto `e813c45f10fc11a33f0e75358c810e1a0fe1aa5e`, the focused correction set passed `107 passed, 8 warnings`; the full non-E2E Python gate passed `3049 passed, 24 deselected, 22 warnings in 126.90s`.
  - Final frontend workspace/API matrix: `22 passed`; `tsc -b` and production Vite build passed with only the existing chunk-size warning.
  - Changed-file Ruff, Python compile, documentation integrity, and `git diff --check`: passed.
- Test owners added or corrected:
  - `test_agent_create_immutability_contract.py`: authenticated ownership, four stable 422/no-write failures, duplicate/concurrent guard, and lost-response IM retry.
  - `test_gateway_workspace_creation_immutability.py`: Gateway divergent-root rejection, same-root recovery, and concurrent local serialization.
  - Session-log tests now cover repository non-dereference, IM control correlation, Gateway nested-log lookup, and HTTP list/sync projection through RPC.
- Runtime/cleanup: no production service, port, config, database, or workspace was touched. Frontend validation temporarily linked the main checkout's installed `node_modules` into this isolated worktree; the link, build output, and TypeScript build info were removed immediately after validation.
- Durable detail: `evidence/correction-round-1.md`.

## Round 2 correction — provenance coherence, opaque target roots, and distill/session boundaries

- Context: Round-2 verification found that an ownerless re-registration could refresh a non-NULL provenance while retaining the old root. It also identified IM-host POSIX validation, a lost-response gap after real registration, cross-node distillation selection, and serial JSONL scans on the Gateway receive owner.
- Decision: register and repository upsert now fill only NULL provenance. Successful Gateway roots are opaque outside the Gateway. A serialized claim finalizes only an ownerless seed with the same node/root/provenance and the Gateway's original display name. Transcript-capable conversation projections carry `source_node_id`, and the distill picker disables other-node paths. Gateway session-log scans run as bounded background tasks.
- Evidence: focused Python owners — 17 passed; Gateway connection behavior plus the new concurrency owner — 29 passed; frontend targeted owners — 69 passed; production frontend build passed. A real isolated IM/Gateway/Vite browser run submitted `C:\\Gateway Data\\windows_ui_round2`; it reached the target Gateway and rendered its node-side parent error, rather than a client-side POSIX syntax rejection.
- Browser cleanup: stopped the isolated IM/Gateway/Vite processes and confirmed both generated ports were released. Runtime files remain ignored and unstaged.
- Durable detail: `evidence/correction-round-2.md`.

## Round 3 correction — bound registration seeds and bounded Gateway log resolution

- Context: Round-3 verification found that a normal owner-bound `node.register` profile was indistinguishable from a completed profile, so a lost `agent.created` response could not safely recover. It also found that IM compared raw browser root text after Gateway canonicalization, Gateway scan background work could accumulate logical tasks past the IM timeout, and the create selector used a draft target root to classify a source as local.
- Decision: Only the first profile written by `node.register` carries a durable `registration_seed`; an atomic claim matches its owner, node, canonical root and provenance, then clears the marker. Gateway's returned display name must equal the original requested display identity. IM no longer compares raw input root text. Gateway uses a fixed four-worker executor, per-conversation coalescing, a 4.5-second logical expiry, and immediate null resolution when capacity is unavailable. The create selector receives no draft root, so only a persisted canonical profile root can classify a source as local.
- Rationale: Gateway is the only authority for target-host path interpretation, and a marker—not an owner-shape heuristic—separates an incomplete registration projection from a normal profile. A bounded physical executor and expired logical waiter state keep WebSocket receive work responsive without discarding a safe in-flight scan.
- Evidence: new recovery, overload/expiry, and selector regressions were red before implementation. The focused Python correction matrix then passed `43 passed, 7 warnings`; the targeted frontend Workspace suite passed `11 passed`. Final expanded gates and browser evidence are recorded in `evidence/correction-round-3.md`.
- Runtime/cleanup: no production service, port, config, database, or workspace is used; any browser acceptance stack is isolated to this worktree and is stopped after evidence capture.
- Durable detail: `evidence/correction-round-3.md`.
