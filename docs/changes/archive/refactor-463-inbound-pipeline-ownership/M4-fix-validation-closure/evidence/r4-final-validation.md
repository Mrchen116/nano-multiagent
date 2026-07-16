# R4 — 最终门禁与四条真栈证据

日期：2026-07-15（Asia/Shanghai）

## Deep module closure

- `main.py` 不再实现 cron accepted→running→terminal、stream delivery 或 awareness；composition 只构造 `CronRunner`、`CronRunStreamDelivery`、`CronExecutionService` 并注册。
- `CronExecutionService` 使用自己的 `CronJobStore` / `CronRunsStore` 完成 submit、delivery、terminal persistence 与 awareness；`CronRunner` 只暴露公开 collaborator 方法。
- heartbeat 与 cron 共用 `gateway/runtime_delivery/stream.py` 的 owner-direct stream primitive。
- `sync_agent()` 与 `reconcile_all_agents()` 都调用同一个 `_decode_mirror_agent_config()`；durable local 与 live catalog 分别比较，无变化时既不重写 YAML，也不 publish/invalidate revision。
- background subscriber shutdown 区分“已经 dequeue、正在交给 callback 的 accepted event”和“没有任何 accepted callback 的 idle stream”：前者按共享 deadline 完成，后者在一个短 handoff grace 后取消，不再耗尽整个 Gateway shutdown deadline。
- `git diff --check` 通过；M1/M3 evidence trailing whitespace 与 `shadow_sync.py` EOF whitespace 已清理。

## 动态 `custom_prompt`

隔离栈由 `scripts/e2e-up.sh` 启动，真 IM + 真 Gateway + 真 LLM：

1. PATCH `default-agent.custom_prompt` 为要求包含 `PROMPTA2B165F3E`，公开 GET 返回同值；新直聊回复为 `Confirmed... PROMPTA2B165F3E`，`delivery_status=completed`。
2. 再 PATCH 为 `PROMPTB39B18315`；同一 conversation 下一轮回复包含 B，新 conversation 首轮也包含 B，二者均 `completed`。
3. 全程只使用当前公开字段 `custom_prompt`，没有恢复废弃 `system_prompt` 覆盖语义。

## 真 `send_message`

- 随机哨兵：`DISPATCH9E13EA6ECE`。
- `default-agent` session 的真实 tool call：`send_message(to=plato, text=DISPATCH9E13EA6ECE)`。
- tool output：`ok=true, target=plato`。
- IM SQLite durable 对账：agent-agent conversation `928b3ee7edfa44b38b6737ec61357339` 的哨兵消息为 `delivery_status=completed`；目标 `plato` 已产生后续回复。
- session metadata 的 dispatch URL 为实际监听地址 `http://127.0.0.1:63865/internal/dispatch`。

## 两条 accepted work + SIGTERM

首次真栈复验没有被静默记成通过：虽然两个 relay task 都落了 `failed(run was aborted)`，第二个 steer bubble 仍是空 `running`。事件序列证明 terminal reconcile 已生成，但 `IMConnectionManager.send_json()` 只排队一帧并等待逐帧 ack；Gateway 随后关闭 transport，后续 failure receipt 与 bubble finalization 尚未被 IM 确认就丢失。

修复后在真 IM/Gateway 上发送同一 conversation 的两条消息，第一条要求前台 `sleep 45`，第二条在 active run 期间被同一 `run_id` 接纳，随后向 Gateway PID 发 SIGTERM：

- conversation：`e0e4d286f76949a6a13ead6e71a6e084`。
- relay task `4288474c34cb4a16b3f2a00c4bc2b458` → `failed / run was aborted`。
- relay task `9884523b207a453ab10d879674e54233` → `failed / run was aborted`。
- 两个 user message 均为 `failed`；已完成的前一 bubble 为 `completed`，新开的空 bubble 为 `failed`；该 conversation 的 `running` 行数为 0。
- Gateway 在 outbound ack queue drain 完成后退出；用户 `/stop` 的既有 `completed` 语义由兼容回归继续守护。

## IM disconnect / reconnect

命令：`PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-resilience.sh`

- A1 initial node online。
- kill IM 后 Gateway 存活；同 DB 重启 IM 后 A2 自动恢复 online，无需重启 Gateway。
- Gateway-before-IM 场景 B1 存活；IM 后启动后 B2 自动 online。
- 终态：`RESILIENCE E2E PASS`。

## Round 1 strict signoff closure

### Foreground terminal 与 background seal

- 红测使用 real `BackgroundSubscriptionManager` + `SessionRunCoordinator` public dispatch：首次 foreground run 已从 Kernel 得到 `completed` 后 manager 被 seal；旧实现从 terminal 路径调用普通 `ensure()`，抛出 `RuntimeError` 并把成功 run 改成 failed。
- manager 新增 `ensure_after_foreground_terminal()` typed collaboration API，返回 `ForegroundTerminalSubscriptionOutcome`。已有 subscriber 仍幂等，未 seal 时照常启动；shutdown seal 对新 session 返回 `SHUTDOWN_SKIPPED`，普通 `ensure()` 仍明确拒绝新 admission。
- coordinator 只在 foreground terminal 路径使用该 API；没有异常字符串匹配或宽泛 `RuntimeError` 吞错。永久回归证明生命周期严格为 `accepted → running → completed`。

### Threadsafe root registration window

- 红测用真实线程在 event loop 阻塞期间完成 `run_coroutine_threadsafe()` submission，使 drain 的首个快照稳定观察到 proxy、但尚未观察到 loop task；旧实现取消 proxy 后先返回 `TimeoutError`，此时底层 task 的 `CancelledError` cleanup 尚未完成。
- dispatcher 为每个跨线程 root 建立 `ConcurrentFuture[asyncio.Task]` registration acknowledgement。deadline 到达后先取消 snapshot 中的 proxy，再等待 queued callback 登记真实 loop task，并无 deadline 地等待该 task 完成 cancellation cleanup，最后才返回 timeout。
- 已启动 task 继续沿原 `_thread_loop_roots` 路径 drain；registration 在真实 task done callback 中清理，不留下 inbound root。

TDD commits：C1 `ae9babdd2`（3 个稳定红测）；C2 `2f39e034f`。

## 最终门禁与清理

- 聚焦 cron/config/contract：`39 passed`。
- personal-assistant 单测：`809 passed`（cron/config owner 初始实现后）。
- subscriber shutdown 聚焦回归：`16 passed`，同时覆盖 stop 前已 dequeue 的事件不丢失，以及 idle stream 不产生 deadline warning。
- Round 1 foreground/background 终态聚焦：`25 passed`。
- Round 1 dispatcher/shutdown resource graph 聚焦：`11 passed`。
- inbound ownership / PA main-package / test-size contracts：`19 passed`。
- 最终 `ruff check src tests`：passed。
- 最终 `git diff --check`：passed。
- 最终 `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal`：`3390 passed, 1 skipped`。
- `scripts/e2e-down.sh` 已执行；worktree 下无 `.im.pid`、`.gateway.pid`、`.gateway-state.json`、`.e2e-ports.env`、`.e2e-jwt-secret`、`.gateway-config.yaml`，无本 worktree IM/Gateway 残留进程。
