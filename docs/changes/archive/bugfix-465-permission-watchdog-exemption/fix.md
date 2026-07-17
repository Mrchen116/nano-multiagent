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

在 `src/personal_assistant/gateway/inbound_pipeline.py` 的 `_await_terminal_run_async` 中：

- 引入局部变量 `current_timeout`，初始值为 `self._run_idle_timeout_seconds`。
- `asyncio.wait_for(anext(stream), timeout=current_timeout)` 替代固定 timeout。
- 当收到 `permission_request` 事件时，将 `current_timeout` 设为 `None`，使看门狗在该 run 等待人工决策期间完全暂停。
- 当收到 `permission_resolved` 事件时，将 `current_timeout` 恢复为 `self._run_idle_timeout_seconds`，让决策后的正常活性检测继续生效。
- 非权限等待的 run 仍按原 idle timeout 检测，保留 bugfix-417 对内部卡死/断连的防护。

同时更新 `tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py`：

- `test_permission_pending_survives_without_heartbeat`：推送 `permission_request` 后等待超过 idle 窗口，再推送 `permission_resolved` 与完成事件，断言 run 不被 reap 且正常完成。
- `test_permission_resolved_restores_watchdog`：同上先等待，再仅推送 `permission_resolved` 而不继续产生事件，断言看门狗恢复后 run 被 reap。
- `test_post_decision_stall_is_reaped`：在 `permission_resolved` 之后工具再次挂死，断言仍被 reap。

Commits: `b8e3addfc` (`fix(bugfix-465/M1-fix): 权限等待期间完全豁免 idle 看门狗`)

## 验证

### 1. 单元测试与契约测试

```bash
pytest -xvs tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py
pytest -m "not e2e" tests/unit/personal_assistant tests/contract
```

结果：`tests/unit/personal_assistant/` 770 通过，`tests/contract/` 169 通过。

### 2. 真实入口验证（真 IM + 真 Gateway）

复现路径：

1. 在 worktree 内启动真 IM + 真 Gateway：`bash scripts/e2e-up.sh --wt <worktree>`。
2. 以用户 `nano` 登录，向 `default-agent` 直聊发送触发 write 工具的消息（`~/.gitconfig` 为危险 basename，必触发 `permission.request`）。
3. 等待前端收到 `permission.request` 事件后，**故意等待 125 秒**，超过默认 120 秒 idle 看门狗窗口。
4. 再提交 `allow_once` 审批。

修前行为：
- 在 `bugfix-465` 之前，因为审批等待期间没有 `run_heartbeat`，idle 看门狗会在 120 秒时将 run 判定为 stalled 并 `cancel(run_id)`；后续审批 resolve 不会触发工具执行，run 以中断结束。

修后行为：
- 在 worktree 当前代码下，等待 125 秒后 resolve 审批，run 继续执行，write 工具成功写出 `.gitconfig` 文件，会话最终收到 `message.completed`。

验证脚本输出（已手动运行并 stop stack）：

```
logged in user_id=...
using agent_id=default-agent
conversation_id=...
sent trigger message, waiting for permission.request
got permission.request request_id=... message_id=...
pausing 125s to exceed idle timeout (120s)...
resolving permission with allow_once
got permission.resolved
got message.completed
PASS: run survived the parked wait; approved tool wrote .../.gateway-workspace/default-agent/.gitconfig
```

该真实入口验证证明：审批等待期间 run 被完全豁免于 idle 看门狗，用户离开后回来仍可正常审批；`permission_resolved` 后工具继续执行，run 正常收口。

### 3. 回归项

- 非权限等待的 run 仍会在 idle 超时后被 reap（`test_idle_watchdog_still_fires_without_permission_request`）。
- `permission_resolved` 后工具再次挂死仍会被 reap（`test_permission_resolved_restores_watchdog`、`test_post_decision_stall_is_reaped`）。
- 用户 `/stop` 触发的 `cancelled` 仍正常返回，不破坏 bugfix-417-fix2 行为。
