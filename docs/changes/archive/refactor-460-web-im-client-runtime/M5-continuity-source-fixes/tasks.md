# refactor-460-M5: continuity-source-fixes — Tasks

> 对齐：../design.md（Round 3 verification 与独立 code review 追加）

## 目标

关闭 M4 后仍存在的连续性源头缺口：同一持久事件不得同时跨 replay/live 两条路径；冷启动与 epoch resync 失败不得跳过权威状态；一次连接内可发生多次独立 recovery；steer 后的新泡拥有独立可见性；external shadow 入站消息可提示；通知 lifecycle 只有一个状态 owner。

## 退出标准

- [x] replay 在稳定上界内分页，连接记录 delivered high-water，排队 live 广播不会重发已回放 event。
- [x] cursor=0 baseline 完成后触发一次权威 recovery，覆盖初始 REST snapshot 与 sync 之间的事件。
- [x] epoch resync 的 `/sync` 失败会关闭当前 generation、退避重连并允许下一 generation 重试；成功后低 event id 可继续进入。
- [x] recovery 只合并同时在途请求，完成后同一 socket generation 的后续独立损坏仍可再次 recovery。
- [x] 已知 canonical payload 在 cursor advance 和所有 subscriber fan-out 之前统一验证；异常帧不污染通知/导航状态。
- [x] `roll_bubble` 重置 bubble-local visibility/discard 状态，steer 新泡的自然静默不会继承旧泡正文。
- [x] external shadow 的实际 `message.sent`→`message.created` 生产形状可产生 toast 与本地未读，且不扩展 wire/REST schema。
- [x] app toast 是唯一 completion accumulator owner；desktop notifier 只消费 candidate，不再重复订阅/hydrate/reduce/persist。
- [x] 全量 frontend/backend/contracts/e2e-critical 与隔离浏览器真栈验收通过；证据落在 `evidence/`。

## 测试策略

- Python：`tests/im_service/unit/test_user_stream.py` 确定性阻塞 replay，并把同一 persisted event 排队到 live；Gateway lifecycle 测试验证 bubble-local reset；messages integration 保留 external 实际事件序列。
- Frontend：runtime fake socket 覆盖 cold baseline、resync failure/new epoch、独立 recovery、pre-fanout validation；toast 测试使用真实 external producer shape；notifier/App 测试证明单一协调器。
- 门禁：先 focused pytest/Vitest/build/ruff，再跑 64-file frontend 全量、`pytest -m "not e2e"`、contracts、`scripts/e2e-critical.sh`；浏览器只使用隔离的 Codex/Playwright 环境，禁止用户 Chrome、Computer Use 与 macOS System Settings。

## Roadpoints

### R1 — replay/live 稳定快照与 per-connection high-water（DONE）

- 在 user handoff 内固定 replay cutoff；repository 查询增加内部 `up_to_event_id` 上界。
- registry 记录每条 socket 已覆盖的 event id，live 广播跳过 `event_id <= delivered_through`。
- 501 条回放 + 同 event 排队广播的确定性回归从 `[1..501, 501]` 收敛为 `[1..501]`。

### R2 — 浏览器 recovery 与预分发校验（DONE）

- cold baseline 在 socket open 后触发权威 recovery。
- resync 只有成功后才标记 handled；失败失效当前 generation 并退避重连。
- recovery gate 从 generation sticky 改为 in-flight promise coalescing。
- canonical validation 上移到 shared runtime，Chat mapper 复用同一 validator。

### R3 — bubble / external / notification owner（DONE）

- bubble roll 清理 `visible_reply_committed` 与 `discard_current_bubble`。
- 前端消费 REST 已有 `external_source` 身份，以 canonical `message.created` 的完整正文/发送者产生提示。
- toast hook 统一 completion state；desktop notifier 改为 candidate 展示器。

### R4 — 全量与真栈收口（DONE）

- 跑全量静态、unit/integration/contract/e2e-critical。
- 使用隔离浏览器验证 cold/reconnect、external message、steer silence 与普通回复回归。
- 隔离浏览器发现并修复“新建 external 会话首条消息先于会话缓存到达”的真实竞态；以权威 conversations 查询完成语义分类。
- 独立 verifier/code review/product reviewer 只读复核在 M5 并入 unit 分支后执行，不再委派实现修改。
