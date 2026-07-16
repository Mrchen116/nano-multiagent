# bugfix-465: permission-watchdog-exemption

## Relations

- Related: bugfix-417-timeout-tool-wedges-session

## 原始报告

> 工具审批卡片怎么能受这个120秒约束呢？
>
> 用户走去干别的事情，5分钟回来，他还是应该可以审批。
>
> 如果用户关了IM页面，再打开，难道会有差异吗？
>
> 需要直接把审批等待从看门狗超时里完全豁免。

## 现象 / 复现

1. 用户在 IM 会话里触发了一条需要权限确认的工具调用（如 bash 命令）。
2. 内核 park 在权限等待状态，向 Gateway 发 `permission_request` 事件，IM 前端展示审批卡片。
3. 用户暂时离开（关闭 IM 页面或离开电脑），未在 120 秒内点击 approve / reject。
4. Gateway 的 idle 看门狗在 120 秒内未收到新的 `run_heartbeat` 或业务事件，判定该 run 失去活性，调用 `cancel(run_id)`。
5. 该轮 run 以 `stalled`（已中断）结束，IM 里的审批卡片失效；用户回来后无法继续审批，任务丢失。

## 根因

`bugfix-417`（特别是 `M3-watchdog-liveness`）的本意就是区分“内部卡死”和“活着但安静”：

- 当时把 `inbound_pipeline.py` 里的 `awaiting_permission` 特例分支删掉，改成靠 `run_heartbeat` 维持 run 活性。
- 设计文档里明确 Requirement: **等权限确认不被误杀**。

但实现上把心搏当成了“审批 run 还活着”的**唯一证据**。实际运行中，心搏链路（内核 ticker → `kernel.stream` → Gateway 消费 → observer 转发 → IM 投递）可能因事件循环、observer 处理、SSE/WebSocket 投递等原因延迟或丢失。一旦 120 秒窗口内没心搏到达，看门狗就把“等待用户决策”误判成“运行失去活性”，导致审批卡片被错误地置为失效状态。

这违反了 `bugfix-417` 的原始意图，也违反了用户视角的基本预期：审批等待是“等人”，不是“内部卡死”，不应被看门狗时间窗口限制。

修复必须保住的不变量：
- 看门狗仍然要收“真不再前进的 run”（内部死锁、崩溃、断连）。
- 等审批的 run 必须完全豁免于 idle 看门狗超时，让用户可以离开、关页面、再回来继续审批。

## 修复

<!-- 改了什么 + commits。worker 完成后回填。 -->

## 验证

<!-- 修前能复现 → 修后不能；相关功能回归正常。worker 完成后回填。 -->
