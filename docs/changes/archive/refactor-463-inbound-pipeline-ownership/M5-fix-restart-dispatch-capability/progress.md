# refactor-463-M5 — Progress

## 启动基线

- Context: verification Round 2 确认 Gateway restart 正确复用持久 binding/session/history，但旧 session metadata 仍保存前一进程随机 dispatch 端口；`SendMessageTool` 因而访问已退出 listener。
- Baseline: send-message / listener / binder / restart 现有聚焦回归 `19 passed, 2 e2e deselected, 2 warnings`。
- Boundary: endpoint 是 process-scoped live capability；不得刷新/删除 durable session，不改变 binding、history JSONL、IM/schema 或固定端口。

## R1 — 注入 live endpoint provider 并锁定 restart/reuse 交叉行为

- Context: 新 session 的 metadata URL 只证明首次 admission 正确；它不能代表重启后本进程的 listener。tool 若只读 durable metadata，会把“session continuity”和“dispatch continuity”变成互斥行为。
- Decision: `InternalDispatchEndpoint` 在 PA Kernel 之前构造，`current_url` 经 `build_pa_kernel()` 注入 `SendMessageTool`。tool 每次 `run()` 重新调用 provider；provider 已注入但返回空时明确 fail-fast，绝不回退 metadata。只有未注入 provider 的 standalone tool 继续读 metadata。
- Rationale: process owner 是唯一能判断 listener 未 ready / active / cleared 的实时事实源；provider 是 D7 允许的 lifecycle seam，不修改 durable session，也没有全局 singleton、环境变量或 mutable setter。
- Evidence:
  - C1 `54e549fea`: provider 轮换、clear 不回退、production composition wiring，以及 persistent binding + 真 Kernel + 双实际 HTTP listener 交叉回归共 4 个稳定失败。
  - C2 `7c2432f6b`: 上述交叉回归通过；端口 A 仍保持监听但收到 0 请求，真实 Kernel 中的 `SendMessageTool` 只 POST B；复用 session id，LLM request 仍包含重启前历史哨兵，Kernel metadata 刻意保持 stale A 以证明 live override。
  - Focused: tool/composition/integration/binder/listener/build-runtime/capability baseline `35 passed, 2 warnings`；相关 `ruff` 与 `git diff --check` passed。
- Rollback: 回退 C2 恢复 metadata-only 工具解析；未迁移任何 schema/history/binding 数据。
- Commits: C1=`54e549fea`; C2=`7c2432f6b`; C3=本次 docs commit。
- Next: R2 走隔离真 Gateway restart + 同 conversation 真 `send_message`，落 durable evidence 后跑最终全量门禁并清理服务。

## R2 — 真重启签收与全量门禁

- Context: R1 交付了注入 provider 的实现与一个进程内隔离集成回归（真实两个本地 HTTP listener + 真 Kernel + 真 binder），但 reviewer 侧的验收标准要求"Gateway 重启后原 conversation/session/history 续接，随后 `send_message` 只访问新进程 endpoint 并完成目标投递"这一行为在**真实 IM + 真实 Gateway 进程 + 真实 LLM** 全链路下也成立——单测/集成测试不能替代这一步（skill §0.3）。
- Decision: 用 worktree 隔离端口起一套真栈（IM `51401` + Gateway，config 为主 config 的本地隔离副本），走三阶段脚本化旅程：① 端口 A 创建并持久化 session，真实 `send_message` 成功投递给 `plato`；② 对 Gateway 发 `SIGTERM`（非 `SIGKILL`）优雅退出，独立确认端口 A 连接被拒绝（彻底死亡）后，用同一份 config 重新启动 Gateway，绑定到不同端口 B；③ 在**同一个** IM 会话里对**同一个** Kernel session 再触发一次真实 `send_message`，确认历史/session id 不变、投递成功且被目标真实收到——而此时持久化 session metadata 仍是端口 A 的旧值（未被 reuse 分支刷新），证明投递只可能经由 R1 注入的 live provider 解析出当前端口 B。
- Rationale: 这是 D8 要求的"持久 session reuse + listener URL rotation + send_message"交叉行为在真实入口的复现，直接对应 verification Round 2 CRITICAL-1 描述的失败条件（`reused=True / current=:B / metadata=:A`）；用 IM SQLite `delivery_status=completed` + 目标 agent 真实回复作为用户可见结果的锚点，而非仅断言 HTTP 200 或工具 `ok=true`。
- Env note: 本沙箱环境里，脚本内 `cmd &` 派生的后台子进程会在脚本自身进程退出后被连带回收（不同于用户真实终端的常规行为）；改为把 IM / Gateway 分别作为独立长驻后台任务直接启动，配置派生/端口分配/workspace 预建仍手动执行了 `scripts/e2e-up.sh` 同一套隔离逻辑，未跳过任何隔离步骤，也未降级为 stub/单测顶替真栈签收。本地 LLM 代理（`127.0.0.1:4000`）此前未起，已按 `docs/可用LLM_API与联调说明.md` 补起（venv 需 Python ≥3.10，见 Rollback 备注），作为跨 unit 共享基础设施保留运行。
- Evidence:
  - Tests: `ruff check src tests` passed；`git diff --check` passed；`pytest -m "not e2e" -n 4 --dist worksteal` → `3394 passed, 1 skipped, 22 warnings`。
  - Entry: 真实入口验证——见下方 Live evidence，非仅单测通过。
  - Live evidence: `evidence/r2-live-restart-dispatch.md`。摘要：端口 A=`51661` 创建 session 并完成两次真实投递（`DISPATCHA7F3C21` / `RETRY`，IM SQLite `delivery_status=completed`，`plato` 真实回复）→ Gateway `SIGTERM` 优雅退出，独立确认 `curl` 到端口 A 得 `Connection refused` → 同 config 重启，端口 B=`57495`（`lsof` 确认，与 A 不同）→ 同一 `conversation_id` / 同一 Kernel `session_id`（`sess_d912248cce78406e`）续接，历史保留重启前全部轮次 → 真实 `send_message` 再次成功（`ok=true`），哨兵 `DISPATCHB9E1F44AFTER` 出现在 `plato` 会话且 `delivery_status=completed`，此时持久化 metadata 仍指向已死的端口 A——唯一可能路径是走了 live provider 解析出的 B。
  - Frontend State Matrix: N/A（无前端改动）。
  - Browser QA: N/A（后端/跨进程投递，走真实 HTTP + IM API + SQLite 对账,非浏览器入口）。
  - E2E/Regression: 永久回归已在 R1 落地（`tests/integration/test_send_message_restart_routing.py::test_restart_reuses_session_history_but_dispatches_only_to_new_listener`）；本 R2 为该回归对应行为在真实全链路下的一次性 live 签收，不另落新的自动化 e2e 用例（D8 的交叉回归诉求已由 R1 满足；本轮补的是 reviewer 要求的"真端到端"证据，属临时验收范畴，遵循 `docs/TESTING_GUIDE.md` 临时验收 ≠ 永久回归的边界）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A（无前端原型/reference 契约）。
- Rollback: 回退无代码变更（R2 未改代码，只加 evidence/docs）；若需重跑，`.venv` 需用 Python ≥3.10（LLM_PROXY 依赖 `anext()` builtin，Python 3.9 会报 `NameError`，本次已把 LLM_PROXY 的 `.venv` 从系统默认 3.9 重建为 miniforge 的 3.12）。
- Commits: C1=N/A（R2 无新增失败测试——是真栈 live 签收，非新代码）; C2=N/A; C3=本次 docs commit（本轮为 evidence + tasks/progress 文档收尾提交）。
- Next: M5 全部 roadpoint 完成，退出标准已全部满足，准备合入 `unit/refactor-463`。
