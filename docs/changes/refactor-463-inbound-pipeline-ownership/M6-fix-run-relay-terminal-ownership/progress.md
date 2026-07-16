# refactor-463-M6 — Progress

## R1 — public try-steer seam 与唯一 fallback run

- Context: Gateway marker 在 terminal observer 完成前仍表示 active，但真实 Kernel run 已可能 terminal。旧代码调用 `submit(steer=True)`；Kernel 在无法注入时会自行创建新 run，coordinator 随后又把同一输入排入自己的 FIFO，形成 orphan run + 第二次 submit。测试 fake 原先把 lost steer 伪装成“旧 run id + injected=False”，没有模拟 public SDK 的 create-on-fallback 语义。
- Decision: 在 public `agent.sdk.Kernel` 增加 `try_steer()` inject-only seam；返回 `None` 明确保证不创建 run。`submit(steer=True)` 内部复用该 seam 后仍保留“拒绝时创建普通 run”的既有兼容行为。Gateway coordinator 只调用 `try_steer()`，失败后由其唯一 FIFO owner 创建一个 normal run；测试 fake 同步到该 public contract。
- Rationale: normal admission 与 per-session FIFO 属于 Gateway coordinator，Kernel 只回答 active run 能否原子接收 steer。把“尝试注入”和“创建 fallback”拆开后，两层不再同时拥有 fallback run。
- Evidence:
  - Tests: `pytest -q` 覆盖 2 个 public SDK contract、既有 submit-steer compatibility、完整 admission 文件和真实 Kernel integration，共 `11 passed in 1.36s`。
  - Entry: `tests/integration/test_session_run_coordinator_real_kernel.py` 在真实 Kernel terminal、Gateway observer 仍阻塞的确定性窗口发第二条同会话消息；修复前实际产生 3 次 LLM request，修复后只有 2 次且第二条输入只进入一次。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: public contract、controlled coordinator regression 与 real Kernel/coordinator integration 均已落库；真实 IM 产品旅程统一在 R2/R3 执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `4f759badf` 恢复 Gateway 调用 `submit(steer=True)`；这会重新引入 terminal window 的 orphan/duplicate run。
- Commits: `c697a8eac`（C1 red tests），`4f759badf`（C2 implementation）。

## R2 — relay error 终态与后续队列恢复

- Context: 待实施。

## R3 — permission watchdog 与整体资源收敛

- Context: 待实施。
