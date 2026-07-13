# refactor-460-M4: replay-and-notification-closure — Tasks

> 对齐: ../design.md（2026-07-13 Round 2 追加）

## 目标

关闭 Round 2 暴露的 replay/live 连续性与通知生命周期缺口：自然静默即使产生过 tool/thinking 也整泡撤回；事件恢复不双投、不截断、不跨 epoch 丢失；冷启动与 reload gap 的通知语义正确；同一回复在应用内与桌面通知各自只提醒一次。

## 退出标准

- [ ] direct Web 成功 run 没有任何可见正文时，不论此前是否产生 tool/thinking，都发 tombstone 并在线/刷新后删除整条 Agent row/parts；bare `NO_REPLY`、普通 tool+可见正文、非 Web delivery 不回退。
- [ ] WebSocket replay 与 live 注册无缝交接，同一持久事件不双投、不乱序；客户端不再 dispatch `event_id <= cursor` 的重复帧。
- [ ] 501–2000 条可恢复 backlog 完整 drain 或明确 resync，不被 500 batch 静默截断。
- [ ] cursor 高于当前 event store max 时服务端明确 epoch resync，客户端允许该原因下的 cursor 回落并触发权威 recovery。
- [ ] 新标签页 cursor=0 的历史 replay 更新 timeline/cache 但不产生新 app/desktop 提醒；reload 跨越 created/completed 后，后续 live completion 仍有完整通知身份。
- [ ] canonical completion 与 relay receipt 共享稳定 run identity，同一回复一次提醒；非 canonical `message_created` 通知 alias 退役。
- [ ] app toast 与 desktop notifier 复用一个纯消息生命周期 accumulator，但各自保留 current/self、visibility/preference/permission 展示策略。
- [ ] repository/bridge 只有一个 post-commit notify owner；合法普通/tombstone event exactly-once，构造 API 不允许同一事件双发布。
- [ ] Chat wire→domain mapper 窄验证 canonical payload；异常/旧 payload 不击穿 reducer，且触发权威 recovery。
- [ ] cursor 首次/user 切换 hydrate 后热路径只读 memory；storage 失败熔断，后续事件不重复抛异常/洪泛日志。
- [ ] Chat recovery 去除不可达 rejection 扫描或显式传播失败，不掩盖四类权威 refetch。
- [ ] 定向并发/分页/epoch/通知/lifecycle 回归、全量 Vitest/build、ruff、`pytest -m "not e2e"`、e2e-critical 与真实 Gateway/IM/LLM 双浏览器旅程通过，证据落在 `evidence/`。

## 范围扩展记录

- systematic-debugging 反向追踪证明 natural silence 的语义 owner 是 Gateway run lifecycle：当前 observer 只对 exact protocol token 标记 discard，先有 process、最终成功但正文为空会落到 `message_completed`；IM 无法区分协议静默与合法 tool-only completion，不能按空正文猜测。
- orchestrator 明确授权把最小 `personal_assistant/gateway/runtime_delivery/{observer.py,context.py}` 纳入 M4；仍属于 Round 2 direct Web 静默不变性。worker 不改 `design.md`，由 orchestrator 合入后校正范围表。

## 测试策略

- 被测行为（来自退出标准）：natural silence process rollback；replay/live 交接、分页、epoch；冷启动/reload gap/dual-source 通知；unique post-commit notify；canonical payload validation/recovery；cursor hydrate/fuse；真实双浏览器在线 toast/unread 与 history replay suppression。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`、`test_heartbeat_im_delivery.py`、`tests/im_service/unit/test_user_stream.py`、`test_event_bridge.py`、`test_event_repository*.py`、`frontend/src/realtime/user-stream/user-stream.test.ts`、`features/chat/chat-stream-reducer.test.ts`、`hooks/use-global-message-toast.test.tsx`、`features/notifications/agent-completion-notifier.test.tsx`（优先扩展）。新建共享 accumulator 源码对应同目录测试文件，理由：toast/notifier 现有测试已因重复 accumulator 分叉，纯生命周期需要单一最低层回归。
- 落层/目录/marker：Python/Frontend 纯逻辑与组件落既有 unit/Vitest，marker 无；真进程/真 LLM/真浏览器落 `tests/e2e/critical_paths` 或一次性 reviewer-style evidence，e2e marker 由目录配置保持。
- 可选依赖 importorskip：既有 e2e fixture 管理可选 live 环境；新增一次性 Playwright CLI 不进 pytest 套件。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时诊断脚本、WS frame dump、Playwright session；最终截图与验收报告持久化到 `M4-replay-and-notification-closure/evidence/`。

## 前端实施计划

- 用户路径分类：`critical-path` + `bug-regression`（实时 Chat、全局提醒、桌面通知、断线恢复）。无视觉重设计，当前 Web IM 为 reference。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 在线非当前会话 completion 的 toast/unread/preview/order；普通当前会话过程 |
| loading | 初始 replay 与 recovery refetch 期间不误提醒、不清空当前 UI |
| empty | natural/bare silence 后整泡消失，reload 无 Agent row |
| error | malformed canonical frame 触发 recovery；storage failure 熔断且 UI 连续 |
| disabled | notification preference/permission disabled 仍不弹桌面通知 |
| submitting | N/A：不改变发送/绑定提交交互 |
| permission denied | 桌面 notification permission denied gate 保持 |
| long content | notification preview 继续截断，普通长回复不变 |
| missing/nullable data | reload-gap completion、旧/异常 payload、nullable tombstone id |
| mobile viewport | Chat 自然静默、普通可见回复与列表回归 |
| desktop viewport | 双浏览器 A/B toast/unread、cold replay、reconnect/reload |
| dark mode（如项目支持） | N/A：项目未声明 dark mode 契约 |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| process 后静默仍留空泡 | Gateway lifecycle + FK repository regression；真 LLM/UI/reload | 回归是；截图是 durable evidence |
| replay/live 双投/乱序 | 阻塞 handoff 的确定性 async test + frontend duplicate cursor test | 是 |
| backlog/epoch | 501+ owner event drain 与 cursor-ahead server/client tests | 是 |
| cold replay/reload gap/dual source | shared accumulator + hook/notifier integration tests | 是 |
| 在线双浏览器无 toast/unread | 两 clean browser、同账号、A/B 会话真旅程 | 自动化最低层 + durable evidence |
| storage/malformed payload | runtime fake storage + canonical mapper/recovery integration | 是 |

### Prototype / Reference Contract

N/A：design 明确不改变 UI/交互/视觉，未提供 prototype/reference；以 current desktop/mobile Web IM 为基线。

## Roadpoints

### R1 — direct Web 静默终态归属（TODO）

- 步骤：先以真实 two-browser/NO_REPLY 基线取证；红测覆盖 process→无可见完成、bare token、普通 tool+正文、非 Web；在 Gateway lifecycle owner 记录是否已有可见回复并在 terminal chokepoint 选择 discard/completed。
- 验证：Gateway observer/context + real IM handler/repository focused tests；真 Gateway/LLM/UI/reload 静默旅程并入 R4。

### R2 — IM replay/live 无缝交接与唯一发布（TODO）

- 步骤：确定性复现 live 进入 registry 与 replay 的竞态、500 截断、cursor-ahead epoch、bridge/repository 双 notify；实现 per-user handoff、完整 drain/明确 resync、replay provenance、self-contained completion/run identity 与 repository-owned post-commit publish。
- 验证：IM user stream/repository/event bridge/gateway handler focused tests，普通/tombstone/relay/external exactly-once 回归。

### R3 — 浏览器 cursor 与 domain recovery 连续性（TODO）

- 步骤：红测重复 event id、epoch reset、storage 热路径洪泛、malformed canonical payload；实现一次 hydrate + memory hot path + storage failure fuse、重复帧丢弃、epoch cursor replace、domain recovery signal，并清理 Chat recovery 不可达 rejection 扫描。
- 验证：runtime/reducer/workspace 定向 Vitest 与 production build。

### R4 — 共享通知生命周期与全量真栈收口（TODO）

- 步骤：用两个 clean browser 先确定性复现 Round 2 在线缺口；红测 cold replay、reload gap、canonical+relay、current/self/account switch；抽取共享纯 accumulator，toast/notifier 仅保留展示策略，删除 alias，并在非当前 tab 维护可见未读反馈。
- 验证：accumulator/toast/notifier/App/Chat integration；全量 frontend/backend/contracts/e2e-critical；真 Gateway/IM/LLM + 双浏览器证明两项 Round 2 问题、历史不重放、reload/reconnect 与 ordinary/external/heartbeat 回归。
