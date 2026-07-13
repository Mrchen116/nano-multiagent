# refactor-459-M2 — Progress

## 基线

- Context: M2 开始前确认 node/register/status/offline 与 M1 seam contract 的现有行为可用。
- Evidence: `pytest -q tests/contract/test_im_persistence_seam_contract.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_gateway_status_broadcast.py tests/im_service/unit/test_offline_guard.py tests/im_service/unit/test_nodes_metrics_repositories.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_gateway_websocket_api.py` → `76 passed`。

## R1 — GatewayNodePersistence interface 与 durable failure compatibility

- 状态：DONE
- Context: GatewayHandler 同时拥有 node/profile/user repository 构造、逐 agent 默认值与 preserve 规则、binding/stale SQL 以及 commit placement；简单改成外层 transaction 会改变 agent N 失败后的已提交数据。
- Decision: 新增 concrete `GatewayNodePersistence` 与 immutable `GatewayRegistrationResult` / `NodeTransition`。register 复用既有 repository write，并刻意保留“node commit → 每个 profile/user commit → binding pending → stale + final commit”的 sequencing；没有 `with connection`、`BEGIN` 或 lock。heartbeat/offline/stale scan 由同一 seam 返回 handler 所需 domain facts。
- Rationale: caller-oriented operation 隐藏跨表 schema/顺序，同时不虚构原子性。真实 SQLite trigger 在第二个 agent profile INSERT 注入 `RAISE(FAIL)`，验证的是数据库 durable rows，而非 mock 调用次数。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_gateway_node_persistence.py` → `7 passed`；目标 `ruff check`、`ruff format --check` 全绿。
  - Entry: R1 是 persistence interface；真实 Gateway WS 接线与广播在 R2/R3 验证。
  - Durable failure baseline（重构前 GatewayHandler，真实 SQLite trigger 在 `agent-b` INSERT 失败）：`nodes=[('node-1','online',2,'v1')]`；`profiles=[('agent-a', node_id=None, display_name='A', workspace_root='/a', is_stale=0)]`；`users=[('agent:agent-a','A')]`；`connection.in_transaction=False`。
  - Durable failure after（重构后 `GatewayNodePersistence.register`，同一 trigger / agent 顺序 / payload）：与 baseline 逐项完全相同；尤其 node 已提交、agent-a profile/user 已提交、agent-a binding 因 agent-b failure 所在 transaction 回滚而仍为 `NULL`，没有整次 register 回滚，也没有额外提交 binding。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化）。
  - E2E/Regression: `tests/im_service/unit/test_gateway_node_persistence.py` 使用真实临时 SQLite 覆盖 first register、re-register preserve、empty advertise、stale reconcile、heartbeat、offline no-op/error、stale cutoff 与 agent-N failure durable state。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `ac81fc57` 可移除 module 实现并保留失败 interface 测试。
- Commits: C1=`ac81fc57`；C2=`7bb94d7a`；C3=本次 docs commit。
- Next: R2 将 handler node lifecycle 改为只消费 typed outcome，并保持 WS ack/广播不变。

## R2 — Gateway handler node lifecycle 接线与广播不变

- 状态：DONE
- Context: handler 的 register/heartbeat/disconnect/timeout 既维护 websocket state 与广播，又直接构造 repositories 和执行跨表 SQL；相关旧测试还从 handler private repository 反查 connection。
- Decision: `GatewayHandler` 改为显式接收 `GatewayNodePersistence`，四条 lifecycle 路径只消费 `GatewayRegistrationResult` / `NodeTransition`；connection map、ack 与 status broadcast 仍由 handler 编排。app composition 直接构造 concrete module，旧测试改从 fixture connection 做 black-box storage assertion，不再读取 handler private persistence state。
- Rationale: typed outcome 只携带广播需要的 node snapshots 与 agent ids，protocol owner 不再知道 node/profile/user schema 或 commit placement；M3 conversation-delivery persistence leakage 不在本 roadpoint 范围。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_gateway_node_persistence.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_gateway_status_broadcast.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_gateway_websocket_api.py` → `73 passed`；目标 ruff check/format 全绿。
  - Entry: 真实 FastAPI Gateway WebSocket integration 覆盖 register/heartbeat ack 与 app composition；owner-scoped broadcast unit/integration 覆盖 online/degraded/offline frame shape、seq、agent ids 与跨 owner 隔离。真进程证据在 R3 收口。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化）。
  - E2E/Regression: handler/status/integration 测试保持旧断言不变，仅接线改为 concrete module；`73 passed`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `e5e94bf3` 可移除 handler 实现并保留失败接线测试。
- Commits: C1=`e5e94bf3`；C2=`d0776a13`；C3=本次 docs commit。
- Next: R3 把 timeout stale scan 收进 module、删除 M1 临时 seam 例外，并完成真入口/全量门禁。

## R3 — Timeout scan 与 seam contract 收口

- 状态：DONE
- Context: M1 为 stale-node scan 在 `user_stream.py` 保留了一处精确 private SQL 例外；M2 必须关闭它，并从真实 Gateway 进程验证 register/heartbeat/disconnect/timeout 的状态和 user-stream 广播，而非只依赖进程内测试。
- Decision: offline guard 改为调用 singleton `GatewayNodePersistence.stale_online_node_ids(cutoff)`；app 将同一 module 注入 handler 与 guard。seam contract 删除临时计数/SQL 文本例外，升级为 `user_stream.py` 整文件无 `._connection`、execute、commit，并禁止 handler 恢复 `_node_repository` / `AgentProfileRepository` node lifecycle。
- Rationale: timeout scan 是 node lifecycle persistence query，进入同一 caller-oriented seam 后，WS 文件只保留 cutoff、循环与调用 handler 的业务编排；静态 contract 让临时例外不可回流。
- Evidence:
  - Tests: targeted node/seam/register/status/offline/WS 集合 → `84 passed`；完整 `pytest -q tests/im_service -m 'not e2e'` → `421 passed, 1 skipped`；`ruff check .` 全绿；`ruff format --check .` → `777 files already formatted`。
  - Entry: 在独立 tmux 承载的 worktree 真栈执行 `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh`，IM=`127.0.0.1:49808`，真实 Gateway node=`wt-refactor-459-M2-47868`。register 后真实 DB 为 `status=online, agent_count=4`，四个 profiles 均绑定该 node；Gateway 配置的 30s heartbeat 使 `last_heartbeat_at` 从 `2026-07-11T10:50:56.208372Z` 推进到 `2026-07-11T10:51:26.210140Z`。
  - Entry disconnect: 真实 user WebSocket `/im/ws/user?token=...` 保持连接时 SIGTERM Gateway；收到 `node.status_changed {status:'offline', last_error:null, seq:1}`，真实 DB 同步为 offline/null。随后同配置真 Gateway 重启并重新 register 为 online。
  - Entry timeout: user WebSocket 保持连接，测试布置把真实 SQLite `last_heartbeat_at` 置于 cutoff 前，运行中的 app offline guard 触发；收到 `node.status_changed {status:'offline', last_error:'heartbeat_timeout', seq:11}`，真实 DB 同步为 offline/heartbeat_timeout。`e2e-down.sh` 后确认 milestone IM/Gateway PID 与 tmux session 均已清理。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化；通过浏览器实际使用的 user WebSocket 验收）。
  - E2E/Regression: 永久 regression 为 seam contract + 真实 SQLite module tests + FastAPI Gateway WS integration；本次真进程证据为临时验收，不增加一次性 test 文件。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `1e004c63` 可移除 timeout seam 实现并保留失败 contract/offline 测试。
- Commits: C1=`1e004c63`；C2=`fbad29de`；C3=本次 docs commit。
- Next: M2 已完成，rebase unit 分支后重复门禁并合入。

## Milestone 收口

- register failure injection 的重构前/后 durable rows 逐表一致，且 module 无 operation-level transaction/lock。
- M1 `user_stream.py` stale-node private SQL 临时例外已删除，seam contract 升级为整文件零例外。
- 真进程 register/heartbeat/disconnect/timeout 状态与 user-stream 广播全部跑通；环境未降级。
- Env caveat: `e2e-up.sh` 裸运行在 workspace 预建步骤使用 `/usr/bin/python3`，该解释器缺 PyYAML，报 `ModuleNotFoundError: No module named 'yaml'`；未修改超出 M2 范围的脚本，按项目约定把共享 `.venv/bin` 前置 PATH 后同一真栈完整通过。后台进程需由 tmux 保活，验收后已清理。
