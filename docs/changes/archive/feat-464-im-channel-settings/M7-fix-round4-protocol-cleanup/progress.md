# M7 — Progress

实现基线：`fb8308ae8ca6fb980fb748b9fb74140385edb8b5`。Baseline focused backend `37 passed`；focused frontend `13 passed`。

## Scope decision — 旧配置迁移移出 M7

- 用户明确不考虑旧 `config.yaml` 或历史 backup 的后向兼容、自动迁移与清理；原 M7 item 4 已停止且未产生代码/测试改动。
- 本 milestone 的安全边界仅验证 IM 通道页新建/更新不会向 `config.yaml` 写入 App Secret；既有旧配置与历史 backup 为 out-of-scope。

## R1 — Status wire owner 与 coalescing race

- Context: 旧队列用 `PendingFrame.sent` 表示发送状态，但该字段只在 awaited `websocket.send()` 返回后才置 true；send yield 期间新 status 会把正在发送的旧 frame 从 deque 删除，随后旧 result 对着新队首无法关联，FIFO 永久卡住。
- Decision: 将未发送 pending deque 与单一 `BusinessFrameOwner` 分开；flush 在进入 wire send 前先 pop 并建立 `sending` owner，send 成功后只把同 owner 转为 `awaiting_result`。ACK/result/error 直接消费 owner，不再通过可被 coalesce 的 deque 队首猜测。
- Rationale: wire 因果归属必须在第一次可能 yield 前确定；pending queue 只拥有真正未发送 frame，coalescing 因而天然无法触碰 in-flight/sent-unacked frame，也无需堆叠 `sent` flag 分支。
- Evidence:
  - Tests: C1 deterministic await-send-yield regression 稳定失败为只发送 `status-old`；C2 后 status ownership/protocol/connection/resilience focused suite `42 passed`，focused Ruff passed。
  - Entry: 公共 `send_json(channel.status)` 在真实 websocket `send` yield 时并发收到 seq3；seq2 result 只释放 seq2，随后 seq3 上 wire并由自身 result 释放。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_status_frame_ownership.py::test_status_coalescing_cannot_remove_frame_after_wire_send_begins`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 C1/C2/C3；会恢复 send yield 期间 active status 被 pending coalesce 删除的竞态。
- Commits: C1=`12e1599d2`，C2=`f81b1499e`，C3=本提交。

## R2 — 断线 incarnation supersede 与 control correlation

- Context: 旧连接一建立即并行发送 register 与业务队首，generic error 只能靠业务 deque 猜测归属；heartbeat 又绕过业务 FIFO 直接写 socket。register/heartbeat 的 error 因而可能弹掉 report/status/message，且断线重排会让旧 runtime incarnation status 抢在新 incarnation 前重放。
- Decision: wire owner 扩展为 `control|business` 两条 lane 共用的单响应槽；register ack 前只允许 control flush，ack 后启动 heartbeat、执行 on-connected convergence 并开放业务。heartbeat 也排入 control lane、使用自身 future；control error 断开当前 socket且不消费业务。断线时 control 终止、业务重排，若 pending 已有同 channel 不同 incarnation status 则把旧 owner 标为 superseded 而不重放。
- Rationale: IM websocket 的响应因果是单槽串行协议；显式 lane 与 owner 能让无 request metadata 的 generic error 仍有唯一归属。register ack gate 同时确保 node identity 被 IM 接受后才发送 node-scoped business；status 的 incarnation supersede 则把重连语义收敛为只恢复当前 runtime。
- Evidence:
  - Tests: C1 two-socket/register/heartbeat regressions 在旧实现稳定失败；C2 focused backend suite（status ownership/control correlation/status protocol/connection behavior/resilience/reconcile callback/channel reconcile/bootstrap）全绿，Ruff 全绿。
  - Entry: 第一条 socket 的 register error 或 heartbeat error 后显式断开；第二条 socket 先只发 register，ack 后按原 FIFO 发送 `node.report`、current `channel.status`、`agent.message`，message waiter 由自身 ack 唤醒。旧 incarnation 的 late result 对新 owner 为 no-op。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_gateway_status_frame_ownership.py::test_disconnect_replays_only_current_status_incarnation`、`test_gateway_control_frame_correlation.py::{test_register_error_never_rejects_buffered_business_fifo,test_heartbeat_error_rejects_only_heartbeat_control_owner}`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 C1/C2/C3；会恢复 register ack 前业务并发、heartbeat 绕过 owner 以及旧 incarnation 重放风险。
- Commits: C1=`b2d5310c4`，C2=`47723f6d1`，C3=本提交。

## R3 — Removal 自动成功清理旧反馈

- Context: retry mutation 的 generic 临时错误仅存为全局字符串；即使响应丢失后 Gateway 实际完成删除、polling 把 removal receipt 收敛为不存在，空态仍会展示过期 alert。offline waiting 视觉上虽由 resource existence 派生隐藏，底层 notice state 也未被主动释放。
- Decision: request error 增加可选 removal owner；只有 removal retry generic error 绑定具体 channel id，其他表单/生命周期错误保持无 owner。query data 每次变化时检查 owner 对应 removal 是否仍存在；receipt 消失即清除该 error，同时主动清除同 id 的 waiting notice。
- Rationale: retry HTTP 结果不是删除最终事实，durable removal receipt 才是权威状态。让瞬时反馈绑定 receipt 生命周期，可在 response-lost 与后台自动成功并存时自然收敛，又不会误清理无关表单或连接错误。
- Evidence:
  - Tests: C1 permanent Vitest 在旧实现稳定失败为空态仍保留 `temporary gateway failure: response lost`；C2 新回归 + 原 panel 13 tests 共 `14 passed`。
  - Entry: online failed removal 点击 retry，mutation 返回 temporary response-lost error；随后 production query cache 更新为 `[]`，页面进入通用 empty state并移除 request alert。既有 offline waiting 回归继续验证 resource 消失后 notice/alert 均为空。
  - Frontend State Matrix: error、waiting、empty、missing resource。
  - Browser QA: 延至 R4。
  - E2E/Regression: `agent-channels-removal-recovery.test.tsx::clears a lost retry response once polling confirms the receipt disappeared` 与 `agent-channels-panel.test.tsx::waits locally for an offline removal retry and clears the notice on success`。
  - Visual/Interaction: 延至 R4。
  - Prototype Comparison: 延至 R4。
- Rollback: 回退 R3 C1/C2/C3；会恢复 response-lost 后 receipt 已消失但全局 alert 仍残留的空态矛盾。
- Commits: C1=`ad5c95d94`，C2=`ee8024b14`，C3=本提交。

## R4 — Targeted browser 与一次性全量门禁

- Context: 永久 Vitest 已证明 query cache 变空时会清理旧反馈，但仍需在 production bundle、真实 IM/Gateway 删除链路和浏览器 polling 下验证 response-lost 最终态；全量回归同时暴露旧测试仍把 `connect_once()` 当成 register 已 ACK，以及 heartbeat send timeout 被内层 cancellation 抢先记录成笼统错误的问题。
- Decision: 使用 production SQLite store 只预置一个 `retryable_failed` removal receipt，页面通过真实 HTTP retry；路由先让请求真实到达 Gateway，再只丢弃浏览器响应，随后所有 channel polling 恢复真实网络。同步把旧连接测试推进到显式 register ACK 边界；heartbeat timeout 由外层 timeout owner 负责断线与精确归因，并消费已完成 future 的异常。
- Rationale: 先执行后丢响应复现的是用户真正会遇到的“服务端已成功、客户端只看到网络失败”，而不是 mock 成功；最终资源列表与 DOM 同时为空才能证明 durable receipt 是唯一事实源。timeout owner 单点负责取消则避免同一次 liveness failure 被内外两层竞态归因。
- Evidence:
  - Tests: backend `3473 passed, 1 skipped, 20 deselected`；frontend `68 files / 627 tests passed`；production build PASS；Ruff `src tests` PASS；`test_channel_status_protocol.py` 396 行且 size contract 随 full backend PASS。
  - Entry: 真实 retry POST 已由 IM/Gateway 完成，浏览器侧被注入 `net::ERR_FAILED`；后续真实 GET polling 返回空数组，API 最终 channel resources=`0`。
  - Frontend State Matrix: failed removal → retry submitting → response lost error → polling empty；最终 `empty=1, alerts=0, waiting=0, retryButtons=0`。
  - Browser QA: production bundle，1440×1000；除预期注入的单次 retry resource error 外无 console render error。
  - E2E/Regression: deterministic backend、永久 Vitest、production browser 三层均完成；secret/diff/process gate PASS，隔离 IM/Gateway/Playwright 资源已清理。
  - Visual/Interaction: `evidence/output/playwright/m7-removal-response-lost-auto-empty.png`，SHA-256 `3ad0e8443826bbaa80f4e5ba17a430cdc068498ee6d3766e4888357d74f13061`。
  - Prototype Comparison: `#channel-deleting` 的反馈生命周期与 receipt 对齐；receipt 消失后匹配 `#channels-empty`，不展示 Web IM。
- Rollback: 回退 R4 实现提交会恢复 heartbeat send timeout 的笼统 cancellation 归因及旧测试对 register 边界的错误假设；浏览器/聚合证据文档可独立回退，不影响产品代码。
- Commits: implementation/test maintenance=`1a8106935`，evidence/docs=本提交。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-deleting` | retry error/waiting 只随 receipt 存在 | 真实 retry 已执行但响应丢失；receipt polling 消失时旧反馈同步消失 | 1440×1000 / failed→empty | pass | 无偏差 |
| `prototype.html#channels-empty` | 收敛后只显示空态，无旧 alert/notice | 截图 DOM：empty=1，alerts/waiting/retryButtons=0，且不展示 Web IM | 1440×1000 / empty | pass | 无偏差 |
