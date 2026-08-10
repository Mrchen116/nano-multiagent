# bugfix-525-M1 — Progress

## Baseline

- Context: finalized Full incident/design/design-review and all delta-specs read at unit head `4fae135b6`; prior commits through `dbc21ad5b` are investigation evidence, not final lifecycle design.
- Decision: preserve useful Kernel privacy/side-effect tests, then replace the generic-fork assumption and add the missing production Gateway persistent route.
- Evidence:
  - Tests: pre-change focused matrix `82 passed, 2 warnings in 6.96s`.
  - Command: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH PYTHONPATH=src pytest -q tests/unit/test_background_hook_fork.py tests/unit/test_self_improvement_hook.py tests/unit/personal_assistant/test_background_session_events.py tests/unit/personal_assistant/test_background_subscription_manager.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/integration/test_self_evolution_output_visibility.py`.
  - Production symptom (read-only, raw logs not committed): Kernel session `sess_5f9eeb9f7479dd13`; LLM session dir `/Users/czj/Repos/LLM_PROXY/logs/session/2026-08-09_20-27-23_509_sess_5f9eeb9f7479dd13/`; request `2026-08-10_09-41-03_357-req-anthropic_messages.json`; response `2026-08-10_09-41-09_400-non-stream-res-anthropic_messages.json`; screenshot `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ea146fbc-d9d7-41d9-aded-947376fc38e4.png`.
- Rollback: N/A (baseline only).
- Commits: pending plan commit.

## R1 — 显式 fork event policy 与 Kernel 业务事件标记

- Context: `make_fork_conversation()` 是所有 background hook 共用能力，旧 investigation 实现把 self-evolution filter 固定为通用默认，既破坏普通 caller 事件继承，也缺少 Gateway 可识别 source。
- Decision: callable 新增默认 `inherit` 的显式 policy；仅 self-improvement 传 `self_evolution`。该 policy 只替换 session publisher，过滤 raw assistant/tool/turn，并在白名单 `skill_created` 的复制 payload 上添加 `source=self_evolution`；未知值在执行 fork 前拒绝。
- Rationale: 业务 caller 选择身份，fork seam 在事件离开 side-chain 前统一分类；不改变 parent model、tools、permission、workspace 或 background run origin。
- Evidence:
  - Tests (red): focused suite `5 failed, 21 passed`，分别命中 default inherit、policy 参数/拒绝、hook 显式选择与 source 缺失。
  - Tests (green): `26 passed in 2.65s` — `tests/unit/test_background_hook_fork.py tests/unit/test_self_improvement_hook.py tests/integration/test_self_evolution_output_visibility.py`。
  - Quality: targeted Ruff passed；`git diff --check` passed。
  - Entry: public Kernel integration 真实执行 `memory(add)` / `skill_manage(create)`；raw assistant/tool 不进 parent stream、durable 文件 side effect 保留、skill event 带 source。
  - Frontend State Matrix / Browser QA / Visual / Prototype: N/A。
- Rollback: revert R1 commit restores the prior implicit generic filter (but reopens generic visibility and unmarked-event defects).
- Commits: `d8d9a34d5`.

## R2 — Gateway persistent 单 owner 路由

- Context: foreground stream terminal 后 per-run `RunDeliveryContext` 会消失；persistent subscriber 已负责 late review/ordinary background output，但此前只过滤 `self_evolution_review`，无法把 marked Skill 送到 config sync。
- Decision: subscriber 只把 `source=self_evolution` 的 `skill_created` 交给独立窄 callback；manager 以首次 subscription request 的 `agent_id` 在线程中调用同步 handler，即使没有 reply context 也建立 subscriber。per-run observer 对 marked event fail-closed 跳过，未标记 ordinary event 保持原 handler。
- Rationale: 一个 session 一个 persistent owner 同时覆盖 terminal 前重放、terminal 后 live、后续 turn already-active 和 reconnect cursor；没有固定 terminal watermark，也没有扩大到任意 raw event。
- Evidence:
  - Tests (red): `6 failed, 32 passed`，命中 subscriber/manager 缺 callback 和 observer 双 owner。
  - Tests (green): `47 passed in 3.52s` — subscriber、manager、observer、foreground-terminal coordinator focused matrix。
  - Lifecycle: fast event 先入 stream 后订阅与 slow event 订阅后到达均路由一次；后续 turn 返回 `already_active` 且仍只有原 stream；reconnect anchor 从 `None` 推进到已处理 sequence `8`；普通 background assistant relay 与普通 unmarked skill handler 既有测试保持绿。
  - Quality: targeted Ruff passed。
  - Entry / Frontend / Browser / Visual / Prototype: N/A（R3 负责 production composition 跨层入口）。
- Rollback: revert R2 commit restores per-run-only skill ownership and reopens post-terminal activation loss；ordinary background route is otherwise unchanged.
- Commits: `0c11747e5`.

## R3 — Production composition 到 config-sync 的跨层闭环

- Context: 单有 Kernel source event 与 manager callback 仍不能证明 production composition 会把 `IMAgentConfigSync.handle_skill_created()` 注入 persistent owner；这正是 patch review 发现的生命周期断点。
- Decision: composition 解析一次现有 handler，并同时注入按 source 分工的 per-run observer 与 persistent manager。integration 用 gate 把真实 Skill review 固定在 foreground terminal 后，再从 run start anchor 建立 manager subscription，观察真实 Agent catalog revision 和 Skill 文件。
- Rationale: shared handler 避免第二套 config mutation；真实 Kernel fork + production manager + actual IMAgentConfigSync 结果穿透故障 seam，composition unit 单独守住接线。
- Evidence:
  - Tests (red): composition + integration pair `1 failed, 1 passed`；唯一失败为 manager 缺 `skill_created_handler` wiring。
  - Tests (green): pair `2 passed in 4.24s`；完整受影响矩阵 `111 passed, 2 warnings in 9.73s`。
  - Product seam: real `skill_manage(create)` 在 foreground terminal 后产生 marked event；manager 使用 request.agent_id 调真实 config sync，default-discovery mode 与空 names 保持不变，catalog revision 前进且新 Skill 文件内容精确落盘。
  - Existing convergence: `test_gateway_im_config_sync.py` agent/global、default/explicit（含显式空）既有 handler tests 在完整矩阵保持绿；composition test 证明 production persistent owner 拿到同一 `IMAgentConfigSync` bound method。
  - Lifecycle matrix: fast/slow、later-turn already-active、reconnect cursor/replay、ordinary background Agent output、ordinary foreground skill owner、real memory add、structured review owner 均由 R1-R3 focused matrix覆盖。
  - Quality: targeted Ruff passed；`git diff --check` passed。
  - Frontend / Browser / Visual / Prototype: N/A。
- Rollback: revert R3 commit removes persistent production wiring and reopens post-terminal Skill activation loss while lower-level source routing remains dormant.
- Commits: `755a824c0`.

## R4 — 比例验证与真实入口

- Context: closure 需要证明完整仓门禁、测试资产不腐烂，以及真实 IM/Gateway 进程上的用户可见边界；runtime 必须隔离并清理。
- Decision: Gateway lifecycle integration 从 501 行的 Kernel visibility 文件拆到独立 behavior owner，共享 controlled structural LLM driver；随后重跑完整门禁。在 persistent owned shell 中用 worktree-local config/ports 启动真 IM + Gateway，设 memory nudge=1，跑 self-evolution 与 ordinary background bash 两条黑盒旅程。
- Rationale: 文件拆分遵守 400 行 contract 且对应两个不同 failure seam；真实栈只验证进程/IM/product delivery，模型分支确定性继续由永久 integration regression 承担。
- Evidence:
  - Full test first pass: `3192 passed, 26 deselected, 1 failed`；唯一失败为新 integration 文件 501 行超 soft cap，非产品失败。
  - Split regression: `5 passed in 3.89s`（两个 integration owners + naming/size contract）；文件为 249 / 179 行，共享 helper 118 行。
  - Full test final: `3193 passed, 26 deselected, 22 warnings in 271.95s` with `pytest -q -m "not e2e"`。
  - Quality: repository `ruff check .` passed；project-venv `./scripts/docs-check` passed（224 Markdown / 67 routes）；`git diff --check` passed。
  - Live self-evolution: isolated node `wt-bugfix-525-M1-46251`, IM `127.0.0.1:58387`, conversation `2fdc4f10df4e4ab997e1a94542501bab`, Kernel session `sess_09d6d00488c054a6`. REST history contained two normal Agent replies and exactly one system message `· background self-evolution review: memory updated` with `system_notice.kind=self_evolution_review`; no `Saved:`, `Nothing to save.`, review prompt, or side-chain tool/turn bubble. Workspace `USER.md` gained the reproducible-evidence preference.
  - Live ordinary background: conversation `3085409f4ad447159d110c3095618b92`; background bash sentinel `BG525D0AD977D` arrived in a second Agent message (`agent_message_count=2`), proving ordinary background output remains visible.
  - Runtime locators before cleanup: `.im.log`, `.gateway.log`, `data/im_service.sqlite3`, `.gateway-workspace/e2e/.nanoassistant/sessions/sess_09d6d00488c054a6.jsonl`. Raw runtime/log/config/secret files were not staged.
  - Cleanup: `e2e-down.sh` succeeded; PID files, generated Gateway config/JWT/channel credentials removed; port `58387` had no listener; persistent owner shell exited. Task-created non-ignored receipt was deleted.
  - Limit: live journey used isolated internal Web IM and repository LLM proxy, not dedicated Feishu credentials. Feishu-shaped/external delivery remains covered by the same Gateway routing tests in the full suite; production symptom evidence remains the read-only locator in Baseline.
  - Frontend State Matrix / Browser QA / Visual / Prototype: N/A（后端投递语义；真实 REST/DB/进程入口已验证）。
- Rollback: revert R4 test/evidence commit only removes harness split/evidence; product rollback is R1-R3 commits in reverse order.
- Commits: `a7f67ff66`.

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| None | — | — | — |

## Code-review fix loop @ `830c0aa67`

### Baseline

- Clean/synced branch: `milestone/bugfix-525-review-fix1` from `origin/unit/bugfix-525` at `830c0aa67b60638df10630823bf7af12665b5556`.
- Full non-E2E first run: `3192 passed, 1 failed, 28 deselected, 22 warnings in 1192.20s`; host load average exceeded `70`, and the only failure was `tests/integration/test_self_evolution_gateway_skill_sync.py::test_post_terminal_skill_create_reaches_gateway_config_sync` exceeding its 5-second catalog-revision wait.
- Systematic-debugging recheck: the exact failed test passed once with `-vv`, then passed `5/5` additional sequential runs (`1.62–1.95s`). Combined with prior full-green evidence on the same code, orchestrator approved treating the first result as host-load timeout rather than a stable branch regression. If it recurs after the fix under reasonable load, investigation must resume rather than reusing this exception.
- Plan: R5 adds one stable final-state concurrency regression in the existing config-sync test owner, then serializes the complete skill-created reconciliation boundary with the shared `RLock`; no caller-specific locks and no event-policy/schema changes.

### R5 — 并发 Skill 配置调和

- Context: foreground observer 与每 session persistent subscriber 会在不同 worker thread 调用同一 `IMAgentConfigSync.handle_skill_created()`；旧实现没有共享锁，两次整表 PATCH 可读到同一 optimistic profile version。
- Decision: 复用 `IMAgentConfigSync._operation_lock` 串行化一次 skill-created 的完整验证、read/merge/patch/publish 边界。锁位于共享调和 owner，不在 foreground/persistent 调用方各自建锁；既有 `RLock` 保持同线程可重入，并与 config operation 的配置发布互斥。
- Rationale: 第二个事件在第一个发布后重新读取 profile，所以 merge 基于新 version/list；不改网络错误重试、event source 或 selection-mode 规则。
- Evidence:
  - Red: 两个 thread 先后创建 `skill-a` / `skill-b` 并发读 version 1；旧实现只剩 `['old-skill', 'skill-b']`，另一 PATCH 409 后被既有 handler 记录，focused 结果 `1 failed` 。
  - Green: 同一回归结束为 `['old-skill', 'skill-a', 'skill-b']`；新回归 + restart/path tests `4 passed in 2.56s`，最终调度收紧后单测 `1 passed in 1.57s`。
  - Affected: config-sync/manager/subscriber/composition/observer/Kernel integration + test contract `84 passed, 2 warnings in 13.71s`；共享 config-operation lock suites `16 passed in 1.65s`。
  - Entry: M2 外部 cwd 真栈 runner 继续经 production Gateway persistent owner 完成真 Skill create/config sync/new-session use，`2 passed in 63.70s`。
  - Pre-rebase full non-E2E before the wait stabilizer: `3197 passed, 29 deselected, 22 warnings in 324.74s`; the baseline catalog-revision timeout did not recur in that run.
  - Quality: repository `ruff check .` passed; `scripts/docs-check` passed (`228` maintained Markdown / `67` routes); `git diff --check` and runner shell syntax passed.
  - Frontend State Matrix / Browser QA / Visual / Prototype: N/A（无展示面变更）。
- Rollback: revert the code-review implementation commit to restore the pre-review concurrency behavior.
- Commits: `b77497ae6`.
- Next: M2 harness fixes and final gates.

### Post-rebase gate debugging — config-sync completion wait

- Trigger: the post-rebase full suite reproduced the same integration failure: `3196 passed, 1 failed, 29 deselected, 22 warnings in 379.64s`; failure remained the 5-second catalog-revision wait.
- Boundary evidence: the exact test passed `6/6` during baseline diagnosis and `5/5` after the implementation; the whole `tests/integration` ordering passed `46/46`. The failure only appeared under the complete suite. Both traces stopped in `_wait_for_catalog_revision()` at `await asyncio.sleep(0)` while the production callback was dispatched with `asyncio.to_thread`.
- Root cause: the integration regression used a zero-delay hot poll to infer completion of a real worker-thread callback. Under whole-suite CPU contention that poll could consume the event-loop/GIL budget until its arbitrary five-second timeout, reporting a missing catalog update before the actual callback completion boundary was observed.
- Fix: keep the real `BackgroundSubscriptionManager -> asyncio.to_thread -> IMAgentConfigSync.handle_skill_created` path, but wrap the real handler to signal an `asyncio.Event` via `loop.call_soon_threadsafe()` after it returns. The test waits on that completion boundary and then independently asserts catalog revision/mode/Skill file state; timeout stays five seconds.
- Verification: stabilized exact test `5/5` (`1.52–1.87s`); final whole non-E2E on the exact tree `3197 passed, 29 deselected, 22 warnings in 391.28s`. The target passed at its former 18% failure position.
- Commits: `a59f488bc`.
