# refactor-463-M6: 修复 run / relay 终态所有权 — Tasks

> 对齐: `../design.md`（2026-07-16 Round 3 M6）

## 目标

让 Gateway 在 steer 与 terminal 竞态、无效跨会话投递、permission 等待和单次 inbound root 失败后仍维持唯一 run / stream / relay 生命周期 owner；后续同会话与新会话消息无需重启即可得到回复或明确终态。

## 退出标准

- [x] public `agent.sdk` 提供只尝试 steer、失败绝不创建 run 的原子 seam；既有 `submit(steer=True)` 消费者保持兼容。
- [x] terminal observer 竞态下 fallback 只创建一个新 run，不遗留 orphan run、重复历史或第二次 submit 副作用。
- [ ] IM 拒绝一个 Gateway 出站帧时，当前 waiter 得到明确失败、队列继续 flush，节点在线时后续同/新会话可继续投递。
- [ ] pending permission 完全暂停 run idle watchdog；`permission_resolved` 后恢复命名 timeout。
- [ ] `/stop`、shutdown、follower/queue 和 inbound root failure 不破坏后续 admission 或资源收敛。
- [ ] focused tests、ruff、`pytest -m "not e2e"` 与真实 IM + Gateway + LLM 恢复旅程通过。

## 测试策略

- 被测行为（来自退出标准）：`try_steer` 的 no-create 契约；真实 Kernel terminal race 只产生一个 fallback run；`type=error` 结束对应 ack future 并放行后继帧；permission pending/resolved watchdog；单个 inbound root failure 后继续 admission；stop/shutdown drain。
- 已有测试在：`tests/contract/test_kernel_sdk_behavior_contract.py`、`tests/unit/personal_assistant/test_session_run_coordinator_admission.py`、`tests/unit/personal_assistant/test_session_run_coordinator_terminal.py`、`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`（扩展）；真实 reviewer 故障新增一个小型 IM connection regression 文件，避免继续扩大已有 1,400+ 行文件。
- 落层/目录/marker：`tests/contract/`、`tests/unit/personal_assistant/`、`tests/integration/personal_assistant/`，marker：无；真实产品恢复旅程使用现有 worktree e2e 脚本，一次性证据不入套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：ephemeral 高位端口的真实 IM + Gateway + LLM 会话，先触发无效 `send_message`，再在同会话与新会话发消息并核对 DB lifecycle / completed reply；同时验证 `/stop` 与 clean shutdown。

UI 状态矩阵：N/A（非前端 milestone）。

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| steer terminal race 创建 orphan run | public SDK contract + real Kernel/coordinator race test | 是 |
| error frame 永久堵塞出站队列 | connection queue regression + 真实无效 send_message 后恢复 | 是 + 临时真实旅程 |
| permission 等待被 idle watchdog 误杀 | coordinator terminal tests | 是 |
| root failure 污染后续 admission / shutdown | dispatcher/coordinator focused tests + 真实同/新会话 | 是 + 临时真实旅程 |

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — public try-steer seam 与唯一 fallback run

- 步骤：先用 public SDK contract 与真实 Kernel/coordinator terminal gate 写红测；新增 no-create `try_steer`，让 coordinator 只在明确拒绝 steer 后排队一次 normal submit，并更新测试 fake 对齐 public contract。
- 验证：contract + admission focused tests；核对 run ids、LLM 调用、历史与 terminal lifecycle 均无重复。

### R2 — relay error 终态与后续队列恢复

- 步骤：用 reviewer 留存 DB/session 证据重现 invalid `agent.message` error 未结束 ack future；写红测后让 error 响应携带被拒绝的 message type，并由 IM connection 原子 reject 当前 frame、完成 waiter、继续 flush 后继帧。
- 验证：IM handler protocol、connection queue、internal dispatch/inbound dispatcher focused tests；真实无效 send_message 后同/新会话无需重启恢复。

### R3 — permission watchdog 与整体资源收敛

- 步骤：写 pending permission / resolved timeout 红测；在 coordinator 的 terminal stream owner 内切换命名 watchdog；补跑 follower、`/stop`、shutdown、dispatcher failure tests 与全量门禁。
- 验证：terminal/stop/shutdown focused tests、ruff、non-e2e、真实 `/stop` 与 clean shutdown。
