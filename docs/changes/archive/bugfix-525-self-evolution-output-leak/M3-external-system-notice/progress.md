# bugfix-525-M3 — Progress

## Readback 与基线

- Baseline: `68707b70363282feb2a238aacbe0ed48c18b18cb`，`milestone/bugfix-525-M3` 从 synced `origin/unit/bugfix-525` 创建；worktree 初始 clean。
- Readback: 完整读取 current `incident.md`、`design.md`、全部 M3 delta-spec、canonical Kernel/Gateway/CLI specs、`AGENTS.md`、coding/testing/evidence/worktree runtime 规范，以及 design 范围内生产实现和既有测试。
- Scope: true update receipt、opaque trace propagation、manager per-run route、existing external sender 双投、CLI projection、专用 Feishu 验收；不重开 M1 raw event policy/Skill owner，不改 IM schema/UI 或普通 background Agent 输出。
- Baseline gate: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3203 passed, 28 warnings in 235.59s`。

## R1 — 真实更新回执与 Kernel trace

- Context: 旧 hook 用“本轮 review 了什么”代替“什么真实写成功”，因此 no-save/read/failure 也发布 updated notice；`RunRecord.trace_id` 未进入 `TurnRequest`/HookContext。
- Decision: 按 call id 关联 `TurnResult.tool_calls/tool_results`，只认可批准的八类 mutating action、无 `error` 且 structured `success` 不为 false；仅非空真实目标发布兼容投影和 `originating_trace_id`。同一 trace 由 registry 经 `TurnRequest` 进入当前 turn HookContext。
- Rationale: 写入事实由工具结果拥有，review 范围不能证明 side effect；opaque run trace 是既有跨层 correlation seam，不引入 channel 数据。
- Evidence:
  - Tests: 红测 `7 failed, 1 passed`，分别缺 updated targets/trace、no-write gate 与 TurnRequest trace；Green focused/affected `39 passed in 5.87s`。
  - Entry: public Kernel integration 真实执行 `memory(add)`、`skill_manage(create)`，持久文件存在、raw assistant/tool/turn 私有，review event 携带 submit 的 exact trace 与真实 target。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_self_evolution_output_visibility.py`；更高真栈在 R4/R5。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `b577820a7`。
- Commits: `b577820a7`。
- Next: R2 manager/coordinator per-run route 生命周期。

## R2 — 精确 per-run route 生命周期

- Context: persistent subscriber 跨多轮长驻，原实现捕获首次 `request.reply_context`；共享 Kernel session 在飞书/shadow 交替与 review overlap 时会串到旧目标。
- Decision: manager 维护最多 4096 项 `trace_id -> ReplyContext` oldest-first 表，notice 只按 `originating_trace_id` 原子消费一次；缺失/重放 fail-closed。coordinator 在同步 submit 前注册并传同一随机 trace，submit 抛错立即撤销。
- Rationale: 本轮 admission 是路由事实 owner；注册先于 submit 覆盖 fast review，消费后删除同时避免 replay 重复。未触发 review 的 route 只由固定容量淘汰，不读取首次或 latest binding 猜测。
- Evidence:
  - Tests: 红测 `5 failed`（manager 无 route API、submit 未传 trace/未撤销）；Green manager/coordinator/SDK affected `28 passed in 6.91s`。
  - Entry: coordinator public dispatch 测试从真实 binding 构造 ReplyContext，观察 register 在 Kernel submit 前、trace 完全相同，失败路径 route 为空。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 新建语义 owner `test_background_subscription_routes.py` 与 `test_session_run_coordinator_notice_routes.py`；真实 Kernel/Gateway overlap 在 R4。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `66d791976`。
- Commits: `66d791976`。
- Next: R3 复用现有 external sender，实现 structured notice 双出口和独立 best-effort。

## R3 — structured notice 双出口与 composition

- Context: 原 callback 只向 shadow IM 发送 reviewed 范围提示，没有根据本轮 trigger-source 向原外部 chat 回执，也没有以真实 `updated_targets` 作为用户可见门禁。
- Decision: 仅对 exact `self_evolution_review` + 非空 `updated_targets` 处理；复用 composition 既有 external sender/OutboundRouter，同一 stable event identity 作 external `reply_dedupe_key` 与 shadow `idempotency_key`，两路各自 best-effort。
- Rationale: ReplyContext 来自 R2 的 exact trace route，因此 external metadata 不读 latest binding；复用 sender 保留既有 adapter/dedupe 契约，不新增 outbox。
- Evidence:
  - Tests: Red `11 failed`（callback 尚无 external seam）；Green delivery/composition `17 passed in 14.75s`。
  - Entry: production `compose_gateway()` 将 `_send_external_reply` 注入 session event callback，不新建 adapter。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_self_evolution_notice_delivery.py` 覆盖 Feishu/IM source switching、replay identity、两路失败独立、空更新/未知 notice fail-closed。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `e918d4662`。
- Commits: `e918d4662`。
- Next: R4 CLI 投影与真实 Kernel/Gateway overlap。

## R4 — CLI、跨层与真栈 fixture

- Context: CLI 对空 review 会生成泛化的 `self-evolution updated`；既有 Kernel 与 Gateway 测试分别保护写入/同步，但未真实证明重叠 review 仍按 trace 回到各自触发源。M2 no-save journey 的旧预期还把 review 执行当成 update notice。
- Decision: CLI 以 authoritative `updated_targets` 投影 memory/skills/both，空目标返回无行；新增一个 public Kernel + production manager/callback 交错回归，用两个结构化 Skill review 使 later IM 回执先到，再释放 earlier Feishu review；将 no-save 真栈改为稳定负面观察。
- Rationale: 这一层同时跨过真实 fork/tool write/session stream/manager trace route/delivery callback，不依赖私有 prompt 文案。CLI 不再把兼容 reviewed 字段当成写入事实。
- Evidence:
  - Tests: Red CLI `1 failed`（空回执误显示）；Green affected `52 passed in 23.51s`。
  - Entry: `test_overlapping_real_reviews_use_their_own_gateway_trace_routes` 真实创建两个 Skill，后 trace 的 IM structured notice 先到，先 trace 释放后只向原 Feishu target + 对应 shadow 回执。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-self-evolution.sh` → `2 passed in 97.48s`；no-save 无 notice/raw leak，Skill create + subscriber replay + allowlist/new-session use 保持通过；runtime `.e2e-self-evolution.jThNYm` 已由 trap 清理。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `18c80ed8e`。
- Commits: `18c80ed8e`。
- Next: R5 专用 Feishu profile 验收与 canonical/gates。

## R5 — 专用 Feishu 验收与收尾门禁

- Context: exact `e2e-up --feishu` 首次稳定失败在 `feishu worker did not initialize`；只读 import-time 与进程栈证据表明 macOS spawn child 在 `_worker_bootstrap` 前重导入主模块/lark SDK，原实现把启动预算耦合到 2 秒 shutdown join，经 `max(5, ...)` 实际只等 5 秒。
- Decision: 经 orchestrator 明确裁决，给 `FeishuWorkerRuntime` 增加独立 30 秒 `startup_timeout`，完整 ready wait 使用它，stop/join 继续使用原 `join_timeout`。另提供 worktree-local acceptance harness：production Gateway 仅增加 INFO lifecycle wrapper，受控 fixture 用 request state、role/tool-call/result 结构与 control tag 驱动；每场景通过本 worktree session-binding 行删除创建新 Kernel session，不改 IM 数据或用户配置。
- Rationale: startup import 与退出回收是不同生命周期边界；最窄修复不加 retry/兼容路径。固定外部 chat 会保留历史消息，harness 因此只接受发送前 message-id window 之后且带本轮 control tag 的回复，避免旧文本假阳；subscriber/Gateway/Feishu 生产链路本身不被伪造。
- Evidence:
  - TDD: startup 红测观察 wait 参数为 `[5.0]`、期望 `[30.0]`；修复后 exact regression + 两个真实 spawn lifecycle tests `3 passed, 2 warnings in 29.42s`。acceptance harness 的 request-state、post-send message window、session reset 与 online-heartbeat 判据在实现时逐项红/绿，并由最终真栈整体运行验证；按 testing policy 不把一次性脚本私有 helper 作为永久 unit seam。
  - Identity/entry: dedicated env/profile 的 env、non-default、verified、App/Bot match guard 全通过；`e2e-up --feishu` 成功，`e2e-feishu-probe.py` 输出 `Feishu E2E ingress probe passed`。
  - Product journey: 同一持久 shell 中依次执行 exact `e2e-up --feishu`、probe、完整 journey、down；probe 输出 `Feishu E2E ingress probe passed`，journey nonce `bugfix525-m3-c2b69dd4f41b`。no-save 与真实失败均前台完成且飞书/shadow 两端无任何 notice/raw；真实 `skill_manage(create)` 产生飞书 exact-one 普通 skills notice + shadow exact-one structured skills notice，唯一 Skill `deterministic-review-c2b69dd4f41b` 文件/explicit allowlist 已更新；shadow IM 真实 `memory(add)` 只产生 shadow memory notice，飞书 notice 计数仍为一。完整 message ids 见 `evidence/feishu-self-evolution.md`。
  - Cleanup: `e2e-down.sh --wt "$PWD"` 后 IM PID stopped、Gateway PID stopped、IM port closed、listener lock removed、fixture stopped；运行时 config/log/PID/LLM record 未提交。
  - Regression stability: 第一次 post-change full 在 host load > 70 时为 `1 failed, 3192 passed`，目标失败独立复核 `6/6` 通过；负载回落后的第二次 full 暴露同一 `test_backpressure_retry_budget_reaps_final_listener` 超时（`1 failed, 3224 passed`）。systematic-debugging 追到测试把前三次纯 retry 计数重复成真实 macOS spawn，并在共享 75 秒预算外叠加每次 30 秒私有限额，导致全量并发时尚未进入 retry/reap 断言便失败。重写为前三次既有同步 status adapter + 最终一次真实 listener 回收，并直接使用生产 `startup_timeout` 后，worker 两文件 `16 passed in 106.62s`，目标用例约 7 秒；最终 full `3225 passed, 28 warnings in 162.65s`。
  - Startup deadline closure: rebase 后的集成 full 又在另一条双 listener 测试中观察到 `multiprocessing.Event.wait(30)` 于约 6 秒提前返回 `False`，旧实现直接误判初始化超时。经 orchestrator 批准，在同一 30 秒总预算内改为 monotonic deadline loop，并在 child 已退出时提前失败；确定性红测“首次 early False、随后 ready”修前失败、修后通过，双 listener isolation 连续 `5/5`、worker affected `16/16`。最终 full `3225 passed, 28 warnings in 81.93s`，未增加 retry/backoff 或 timeout。
  - Acceptance repeatability: 一次重跑在 external skill receipt 等待超时；边界证据显示 review 的真实固定名 Skill 已由上一轮创建，第二次 `create` 没有新写入，因此 production true-receipt 正确静默。fixture 改为由 control state 提供 nonce 唯一 Skill 名，raw marker 同时收紧为任意 `Saved:`；修复后上述最终真栈通过，未修改生产路由。
  - Quality gates: affected routing/config-sync/CLI/worker 矩阵 `90 passed`；fixture 最终改动后 M2 critical-path journeys `2 passed in 46.14s` 且 runtime 清理；final non-E2E `3225 passed, 28 warnings in 81.93s`；repository `ruff check .`、6 个 R5 Python 文件 `ruff format --check`、docs-check（244 Markdown / 67 routes）、`git diff --check`、shell syntax 与 acceptance Python compile 全绿。repository-wide format-check 另指出三个早期 R1 文件不符合 formatter，但 lint 与本 R5 changed-file format gate 均通过，未为收尾制造无关格式 diff。
  - Canonical: M3 Kernel/Gateway/CLI delta 已归并 current specs；design Changelog 记录 approved startup side finding。
- Rollback: revert R5 commit；worker stop/join 行为未变，若只回退 acceptance harness 不影响 M3 产品事件语义。
- Commits: `b711df6b8`（production startup boundary + repeatable dedicated Feishu acceptance）、`eec562e4e`（canonical/progress/evidence）；deadline-loop closure 见后续 fix commit。
- Next: final gates 后 commit/merge/push unit 并移除 milestone worktree/runtime。

## Promotion Candidates

None.

## Code review F1-F5 closure readback

- Pre-fix head: `16397bbad69978198a89ad8bb3ea87e8d8b2ab59`；从 clean/synced `unit/bugfix-525` 创建独立 `milestone/bugfix-525-M3-fix-cr` worktree，未修改 root checkout。
- Baseline: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3235 passed, 28 warnings in 133.50s`。
- F1 scope: source-marked self-evolution `skill_created` 继续只由 persistent manager 处理；owner-direct heartbeat/cron 在共用 stream 开始时按 run anchor admission subscriber，foreground 保留 terminal replay/dedupe，不恢复任何 raw side-chain event。
- F2/F5 scope: external notice 的同步 sender 移出 Gateway event loop，同时兼容 awaitable；subscriber 三个既有分类只共享 callback shutdown envelope，不改变分类优先级、callback 或日志文字。
- F3 scope: `ensure_agent_skills_enabled` 与 `handle_skill_created` 的共享 GET/merge/full PATCH seam 使用同一既有 `threading.RLock`，不改变错误语义或 selection mode。
- F4 scope: Feishu worker startup 仍使用同一 30 秒 monotonic 总预算，只将单次 Event wait 改成短有界 slice 以观察 pre-ready child exit；不增加 retry/backoff，不改变 stop join timeout。
- Process: 预计超过 3 个文件/100 行，按 `change-impl-worker` 从 reviewer fast-lane 升回 main process，新增 R9-R13 并逐项 TDD；core event policy 与 receipt action allowlist 两项已 refuted，不修改。

## R9 — Code review：全 origin 的 Skill 唯一 owner

- Context: foreground terminal 会启动 persistent subscriber，但 cron 独立 session、heartbeat fallback session 与 Gateway restart 后尚无 foreground terminal 的 session 没有该 owner；per-run observer 又按批准契约跳过 marked Skill，造成 early/late Skill 文件存在却未进入 explicit allowlist/catalog。
- Decision: heartbeat/cron 共用 `stream_run_to_completion` 在 per-run observer 前按本 run anchor 调用 manager `ensure`；marked Skill 仍只由 persistent subscriber 处理，foreground terminal ensure 继续作为 replay/dedupe seam。若 owner-direct 先以无 route 建 subscriber，manager 只允许其后采用第一个非空 ordinary-background reply route，既不覆盖既有 route，也不影响 notice 的 per-trace route。
- TDD: 红测 `3 failed`（共用 stream 无 manager admission 参数、composition 未接线）；补 ordinary background route 后红测稳定超时。Green focused `19 passed, 2 warnings in 2.80s`，覆盖 cron early、heartbeat terminal-late、active foreground dedupe、per-run observer skip 和 heartbeat-first 后 ordinary background Agent 结果仍可见。
- Affected: heartbeat/cron/composition/manager/observer 矩阵 `43 passed, 2 warnings in 4.10s`（ordinary-route guard 后由 focused 复核）；未改变 raw assistant/tool/turn、structured notice、ordinary realtime Skill 或 background Agent event 分类。
- Status: DONE。Next: R10 同步 external sender offload 与三类 callback shutdown envelope。

## R10 — Code review：异步通知与 subscriber callback 生命周期

- Context: persistent subscriber callback 在 Gateway event loop 中直接调用 production external sender；OutboundRouter/Feishu REST 与同步 retry sleep 会阻塞整个 loop。另三类 subscriber callback 复制同一 shutdown idle envelope，后续修改容易破坏某一分类的 drain 语义。
- Decision: 只把 external sender 的同步调用交给 `asyncio.to_thread`，返回值若为任意 awaitable 仍回到 loop await；external/shadow 继续各自 best-effort。subscriber 抽模块内 `_invoke_callback`，三个 if/elif 分类优先级、callback、三条 warning 文案和 `CancelledError` 传播保持不变。
- TDD: event-loop 红测修前观察 sender 与 loop 同线程并失败；三类 callback in-flight close 先作绿 characterization。实现后 notice/subscriber/manager/external affected `47 passed, 2 warnings in 3.49s`，同步 sender 在线程运行且 10ms loop tick 先于 100ms sender 完成，async sender 与 shadow delivery 均保留。
- Status: DONE。Next: R11 ensure-vs-handle 的共享 Skill config mutation 串行化。

## R11 — Code review：共享 Skill config mutation 串行化

- Context: `handle_skill_created` 已持有 `_operation_lock`，但 Feishu activation 的 `ensure_agent_skills_enabled` 经同一 GET/merge/full PATCH helper 时没有锁；两线程可同时读取 profile version V，后一方 409 被既有 best-effort 错误处理吞掉并丢失一个 Skill。
- Decision: `_enable_skills_for_agent` 作为两条入口共享的 mutation seam 持有既有 `threading.RLock`，完整覆盖 selection gate、GET、merge、PATCH 与 publish；`handle_skill_created` 的 global multi-agent 外层锁保留并依赖 RLock 重入，不增加 retry 或改变异常语义。
- TDD: 红测确定性暂停 self-evolution 的首个 GET，让 Feishu activation 抢先 PATCH，修前最终只保留 managed Skill 且旧版本 PATCH 409。修后 focused/config-sync integration `6 passed in 1.70s`，最终 explicit allowlist 按顺序同时包含 `self-evolved-skill` 与 `managed-feishu-skill`；既有两个 skill-created 并发、empty/default discovery 与 agent scope 均通过。
- Status: DONE。Next: R12 Feishu pre-ready child liveness-aware deadline。

## R12 — Code review：Feishu pre-ready child fail-fast

- Systematic debugging: current `start()` 在每轮把完整 remaining（默认近 30 秒）交给 `multiprocessing.Event.wait`；pre-ready spawn/bootstrap/import-main child 退出不会 set Event，monitor threads 又只在 ready 后启动，因此 `is_alive()` 到总预算结束才有机会运行。根因是 wait 粒度遮蔽 child liveness，不是 timeout 太短或 transport retry。
- Decision: 保留同一 monotonic startup deadline 与 30 秒默认预算，仅把单次 wait 限为 50ms，False 后立即检查 child；不增加 retry/backoff，不改变 stop 的 join/terminate/kill timeout。controlled delayed-ready test 前五个 slice 各真实等待后返回 early False，随后仍可观察原 Event ready 并成功。
- TDD: 真实 spawn child 在 `_worker_bootstrap` 前退出，修前耗满 5.00 秒并失败 `<4s` 断言；修后快速失败且已 reap。完整 worker `10 passed, 2 warnings in 25.24s`；two-listener isolation 连续三次 + channel lifecycle affected `8 passed, 2 warnings in 13.49s`。
- Status: DONE。Next: R13 cross-layer/full/quality gates 与归并清理。

## R13 — Code review closure gates

- Real integration: `tests/integration/test_self_evolution_gateway_skill_sync.py` 现在以真实 public Kernel `RunOrigin.CRON` 提交受控 Skill create，owner-direct shared stream 在 observer 前启动 production manager，foreground terminal 后才释放 review；真实 Skill 文件写入并经 persistent subscriber/to-thread config-sync 更新 catalog，随后 foreground terminal ensure 返回 `already_active`。Exact proof `1 passed in 10.24s`。
- Focused: F1 manager/stream/composition/observer `19 passed`；F2/F5 notice/subscriber/manager/external `47 passed`；F3 config race/integration `6 passed`；F4 worker `10 passed`，listener isolation 三次 + lifecycle affected `8 passed`。
- Full non-E2E: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → 最终代码 `3245 passed, 28 warnings in 63.03s`。
- Quality: repository `ruff check .`；18 个 changed Python files `ruff format --check`；`/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` → 245 Markdown / 67 required routes；`git diff 16397bbad69978198a89ad8bb3ea87e8d8b2ab59 --check` 全绿。`./scripts/docs-check` 首次由系统 Python 启动且缺 PyYAML，改用仓库 `.venv` 执行同一 checker 后通过，不是 repository failure。
- Product contract: 不改 approved event policy、用户可见 schema/文案、external route 或 receipt action allowlist；ordinary background Agent 输出由 heartbeat-first route-upgrade regression 明确保留。因不改变 Feishu/CLI 产品表现，未重复专用外部 journey；scheduler/heartbeat 生命周期变化由上述真实 Kernel cron integration 收口。
- Status: DONE。Next: final full/quality snapshot 后提交、push、merge/push unit，并清理 milestone worktree/branch。

## Round 4 reviewer-fix readback

- Pre-fix head: `a26fc6975853b5e7183f531df39bbc547a4ea4d7`（包含 reviewer 的 `Round 4 — FAIL` regression commit），从 clean/synced `unit/bugfix-525` 创建独立 `milestone/bugfix-525-M3-fix-r4` worktree；该回归提交保留在 fix 历史中。
- Scope readback: R4-I1 只解决专用 Feishu acceptance 中 `probe` 通过后 route-anchor ingress 超时及成功/失败 runtime 清理；R4-I2 只增加受控 LLM + public Coding CLI/PTY 的真实产品验收入口。M3 已批准的 event classification、route owner、external schema 与用户可见文案不变。
- Process: 该 reviewer fix 涉及两个产品入口、预计超过 3 个文件/100 行，依 `change-impl-worker` 从 fast-lane 升回 main process，新增 R6-R8 并执行完整 TDD/验收/门禁；R4-I1 必须先走 `systematic-debugging` 复现和边界定位。
- Baseline: 最新 unit 相比上次 final-green 只新增 reviewer regression 文档；复用 M3 R5 的 `3225 passed, 28 warnings in 81.93s` 作为代码基线，并在 fix 后重新运行 full non-E2E。

## R6 — Round 4 飞书 route-anchor 稳定性闭环

- Context: reviewer 两个 fresh stack 均观察到 dedicated identity、`e2e-up --feishu`、ingress probe 成功，而紧接着的 journey route anchor 没有到达受控 LLM；另有失败后 `.feishu-self-evolution-llm.jsonl`、`config-apply-receipts-v1.json` 残留。
- Diagnosis: fresh stack 的无间隔 `up -> probe -> journey` 稳定复现 `timed out waiting for route anchor ingress`。probe 与 route anchor 均由同一 verified profile 以 user 身份发送到同一 P2P chat/connector，provider message id 分别唯一；production `external_shadow_sagas` 同时存在两条 canonical inbound，replacement worker 日志也已 `connected`，因此 identity、chat form、dedupe window 与 listener transport 均未丢消息。失败边界中 route anchor 已创建真实 Kernel run，但 LLM HTTP 指向 `http://127.0.0.1:4000`，controlled fixture JSONL 为 0；worktree config 同时被恢复为 production provider。
- Root cause: probe 只等 saga mirror，不等真实 foreground terminal。journey 在旧 Gateway drain probe run 前改写 config；旧进程仍持有 production-valued immutable config snapshot，可在退出期间持久化 Agent config 并覆盖该外部 rewrite，replacement 因而读到 production LLM。较慢的人工首轮偶然让 probe run 先结束，所以曾通过。
- Decision: 不改变 timeout/retry/production routing；`_restart_gateway` 先等旧 Gateway 完全退出，再在同一 startup 边界内把生成 config 指向 fixture，然后启动 replacement。journey `finally` 删除自身 JSONL，public `e2e-down` 删除 config operation receipts 与同名 JSONL；两者均为 worktree runtime。补确定性回归模拟旧 Gateway 在 SIGTERM drain 时恢复 production provider，证明 replacement spawn 前最终 provider 必为 fixture，并覆盖 success/failure cleanup。
- Evidence:
  - TDD: focused red `4 failed`（restart API/ordering、journey success/failure JSONL、down receipts），green `7 passed in 0.53s`（含 probe guards）。
  - True stack repeat 1: nonce `bugfix525-m3-17e2b4813bd6`，route anchor `om_x100b68ab538f9ca8c4c88343f1a372f`，status 0；journey 后 record absent、down 后 receipts absent。
  - True stack repeat 2: fresh IM/Gateway，nonce `bugfix525-m3-5c484c3fdc68`，route anchor `om_x100b68ab6bdc88a8de7ee3b1b0d4da4`，status 0；相同 cleanup 断言通过。
- Status: DONE。Next: R7 真实 Coding CLI/PTY 验收入口。

## R7 — 真实 Coding CLI / PTY 产品验收入口

- Context: reviewer 需要无需读取源码或把 integration test 当产品证据的真实终端入口。既有 CLI consumer contract test 只能证明 formatter，不能证明 public CLI、真实 background hook、写入工具与 REPL idle consumer 连成一条路径。
- Decision: 新增 worktree-local runner，以 `sys.executable -m coding_cli.main` 启动真实 PTY，复用现有 OpenAI-compatible fixture；每个 case 使用隔离 HOME/workspace/config。fixture 仅按 scenario request state、message roles 与 tool-call/result id 路由，不匹配 self-improvement 私有 prompt。memory/no-save/failure 用一个受控前台 seed 建立 turn counter；both 的 seed skill-only no-save review 完成后再发目标轮，消除 background/foreground overlap，不靠 sleep 或增加 timeout。
- Evidence:
  - TDD: seed/target structural routing 红测 `4 failed, 2 passed`，实现后 `6 passed`；targeted real PTY memory 与 both 均通过。
  - Product command: `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-cli-self-evolution.py --wt "$PWD" --transcript docs/changes/bugfix-525-self-evolution-output-leak/M3-external-system-notice/evidence/coding-cli-self-evolution.txt`。
  - Product result: nonce `4e566550ff`；memory、skills、both 各显示 exact-one `... updated` line并真实生成对应 memory/Skill 文件；no-save、read-only、failure 均为 `update_count=0`。六场景前台完成，raw `Saved:`/`Nothing to save.`/failure/traceback 均不可见。
  - Evidence locator: `evidence/coding-cli-self-evolution.txt` 保存精简真实终端输出与逐 case 断言；stdout 报告 `runtime_cleaned=true`，运行后不存在 `.e2e-cli-self-evolution.*`。
  - Affected regression: hook/CLI/Gateway/Feishu harness 矩阵 `119 passed, 2 warnings in 22.54s`；共享 fixture 的 M2 critical path `2 passed in 44.91s` 且 runtime trap 清理。
- Status: DONE。Next: R8 最终 Feishu 复核与质量门禁。

## R8 — Round 4 收尾门禁

- Product acceptance: 最终代码上只执行一轮专用 Feishu exact `e2e-up --feishu -> probe -> journey -> down`，probe 通过，journey nonce `bugfix525-m3-e9c4121c554c` status 0；同一轮后的 PID、listener lock、fixture JSONL、config receipts 与临时 runtime 均不存在。真实 Coding CLI 六场景最终 journey nonce `4e566550ff`，stdout `runtime_cleaned=true`，证据见本 milestone 两个 evidence 文件。
- Focused/affected: structural fixture tests `6 passed`；hook/CLI/Gateway/Feishu harness 矩阵 `119 passed, 2 warnings in 22.54s`；共享 M2 critical paths `2 passed in 44.91s` 并清理 runtime。
- Full: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal --durations=20 --durations-min=0.5` → `3235 passed, 28 warnings in 79.64s`。
- Quality: repository `ruff check .`、3 个 Round 4 Python 文件 `ruff format --check`、docs-check（245 Markdown / 67 routes）、`git diff --check`、acceptance Python compile 与相关 shell syntax 均通过。
- Commits: `abc4f2d0d`（R4-I1 route-anchor restart ordering/cleanup）、`cc939a7c7`（R4-I2 deterministic Coding CLI/PTY acceptance + evidence）；本 gate 记录由后续 documentation commit 收口。
- Status: DONE。milestone commit/push 后按 worker protocol merge/push `unit/bugfix-525`，随后移除 fix worktree/branch；不改变 M3 production event classification、route owner 或用户可见 schema。

## Reopened PR #264 closure（2026-08-11）

- Context: 用户授权把真飞书验收暴露的 ordinary background sender event-loop 阻塞，以及 `e2e-up.sh` 把 IM readiness timeout 误称为 startup failure 的问题直接纳入同一 PR。另一个 worktree 曾使用同一专用 Bot，但 lock owner/time-line 已排除其与本次 no-lock timeout 重叠；不能把 timeout 归因为 Bot contention。
- Scope: 只改 shared external-delivery await boundary、E2E IM readiness diagnostics、Feishu worker bootstrap message 与对应 existing-test owners；不重复 `bugfix-533` / PR #271 的 lazy-import 修复，也不改变 self-evolution 用户通知、trace/route owner 或 config-sync 契约。
- Root-cause evidence before code:
  - `build_bg_reply_sender()` 在 async subscriber callback 内直接调用 composition 的同步 `_send_external_reply()`；该路径进入 `OutboundRouter` 和 Feishu REST retry/backoff，因此会占住 Gateway event loop。self-evolution notice 已以 `asyncio.to_thread` 规避相同风险，形成可运行对照。
  - `scripts/e2e-up.sh` 固定 `30 × sleep 0.2` 后仅再次 probe `/openapi.json`，没有检查 `.im.pid` liveness，随后报 `IM failed to start`。已观察到两次 child 在脚本退出后成功 ready，故该文案是 timeout 假阴性而非进程启动事实。
  - dedicated Feishu lock 的 active-owner 分支在 IM 启动前明确报 `dedicated Feishu E2E listener is already owned by ...`；此次无该输出，且实际 Bot 使用时间与失败窗口不重叠，不能归因为 lock contention。
  - Feishu worker ready Event 在 `_worker_bootstrap` 进入 SDK/WebSocket 前设置；原 `did not initialize` 表述不应暗示 Bot 冲突或 WebSocket 连接完成。
- Next: R14 写红测并以单一 shared helper 收口 sender threading；R15 再做 script black-box red/green 与 dedicated no-message `up -> probe -> down` evidence。

### R14 — ordinary background 外发非阻塞

- Context: ordinary background sender 是 persistent Gateway subscriber 的 async callback，却直接同步调用 composition `_send_external_reply()`；Feishu REST 的 retry/backoff 会阻塞 event loop。self-evolution notice 已有相同的 `to_thread` 语义，两个路径若各自维护易再漂移。
- Decision: 在 `runtime_delivery.background` 建立一个模块内 shared helper，统一以 `asyncio.to_thread` 调用 external sender；若调用结果是任意 awaitable，则回到原 Gateway loop await。两个调用方保留原来的顺序、metadata/dedupe 与各自 external failure logging；IM delivery 仍在 external best-effort 失败后继续。
- TDD: 新增 blocking sync sender 红测，修前 task 在 loop 中等待 sender 超时后已结束；另加入 async sender loop affinity 与 external failure→shadow IM regression。修后 delivery/subscriber affected suite `50 passed, 2 warnings in 2.32s`，sync sender thread id 与 loop 不同且 task 仍 pending 时 loop 可继续执行。
- Entry: production ordinary background 仍从 `build_bg_reply_sender()` 经 composition `_send_external_reply()` 到 `OutboundRouter`；本修只改变该 synchronous call 的 execution context，不改变 Feishu 文案、顺序或 dedupe key。
- Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A。
- Rollback: revert this roadpoint commit.
- Next: R15 script black-box readiness red/green and Feishu bootstrap diagnostic wording.

### R15 — E2E IM readiness 与 Feishu bootstrap 诊断

- Context: `e2e-up.sh` 先前以固定 `30 × 0.2s` probe 等待 IM，之后只按 HTTP 未就绪写 `IM failed to start`；slow-but-alive child 与已退出 child 都被压成同一假阴性。Feishu worker ready Event 是 bootstrap handoff，不表示 SDK WebSocket 或 Bot 已连接。
- Diagnosis: black-box wrapper 分别控制真实 `python -m uvicorn` child 的 delayed/alive 与 immediate-exit 行为。修前 early-exit 输出 generic `IM failed to start`；1 秒 deadline override 被完全忽略、延迟 child 最终仍成功，直接证明固定 6 秒脚本预算和诊断分类是根因。专用 Bot lock 已在 IM 启动前的独立 branch 报 owner，且本次无 lock/时间重叠，故未归因给 listener contention。
- Decision: `NANO_MULTIAGENT_E2E_IM_READINESS_TIMEOUT_SECONDS` 是 E2E launcher 唯一、默认 30 秒的正整数预算；loop 持续 probe `/openapi.json`，每次失败后先检查 IM PID，再判 deadline。child exit 报 `IM process exited during startup`；alive deadline 报 `IM readiness timed out after <n>s`；两者均保留 `.im.log`，由原 `e2e-down.sh` 回收。Feishu worker 保留现有 30 秒 monotonic deadline、50ms liveness slices 与 stop/join 语义，只把 two error strings 收紧为 `bootstrap readiness timed out` / `exited before bootstrap readiness`。
- TDD: script black-box 红测为 `1 passed, 2 failed in 23.43s`：exit 仍被称 generic failure，1 秒 override 不生效。Green: slow-alive / child-exit / alive-deadline 三条 `3 passed in 7.74s`；worker runtime `11 passed, 2 warnings in 23.56s`。每个 failing branch 保留 `.im.log`，test finally 走 public `e2e-down.sh` 并确认 PID file/child 无残留。
- Entry: 使用非 default 专用 profile 做一次真实、无消息的 `e2e-up.sh --wt "$PWD" --feishu -> GET /openapi.json -> e2e-down.sh`；profile `feishu`、stack ready，之后 IM/Gateway PID、ports env、isolated config、credentials/manifest 与 listener lock 均不存在。未运行 `e2e-feishu-probe.py`，因为 probe 本身会向 Feishu 发送文本；本轮只验启动/清理，不增加测试聊天消息。
- Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A。
- Rollback: revert this roadpoint commit.
- Next: run affected and full non-E2E quality gates, then merge this branch into `unit/bugfix-525`.

### R16 — rearchive reopened PR closure

- Context: GitHub CI requires a `unit/*` PR's one change directory be archived before it runs Python checks. The reopened PR correctly moved the unit active for its implementation window, but this closure is now complete and the active location caused CI to stop at that guard.
- Decision: after the R14/R15 merge at `0fefe9415`, use one whole-directory `git mv` back to `docs/changes/archive/`; do not duplicate, delete, or rewrite the historical incident/design/evidence.
- Evidence: `scripts/check_change_unit_archived.py --head-ref unit/bugfix-525`, docs-check and diff-check run after the move. The dedicated Feishu runtime, lock, milestone worktree and temporary branch were already cleaned before rearchive.
- Rollback: revert the archive commit to resume a further open-PR closure deliberately.
- Next: CI should now execute actual Python/Frontend checks instead of failing at archive admission.
