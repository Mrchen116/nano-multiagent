# refactor-460-M1: realtime-runtime — Tasks

> 对齐: ../design.md v1

## 目标

Web IM 单标签页只保留一个 owner-scoped user-stream lifecycle；所有实时消费者共享一致的鉴权、resume、reconnect、recovery 与账号隔离语义，且现有用户旅程不改变。

## 退出标准

- [ ] auth session interface 覆盖 fresh token、<=30s/expired refresh、HTTP/WS single-flight、retry/signed_out、stale-result guard。
- [ ] runtime 覆盖单 socket/多 subscriber、resume/ping/backoff、readiness、generation、cursor、resync/recovery、subscriber isolation、last-unsubscribe。
- [ ] Chat/toast/desktop notification/Nodes/Agents 全部迁移到唯一 runtime；legacy stream 与 `v2/chat-stream.ts` 无生产调用方并删除其实现/测试。
- [ ] token refresh 不清 cache；logout/account switch 清 QueryClient。
- [ ] ownership contract、相关 Vitest、`npm run build` 通过。
- [ ] 真 Web IM + Gateway + 浏览器完成 live-critical 签收；包含 expired access + valid refresh 的断网重连恢复，证据落入 `M1-realtime-runtime/evidence/`。

## 测试策略

- 被测行为（来自退出标准）：auth freshness/单飞/竞态；runtime 单连接生命周期与恢复；五类消费者领域行为；账号切换 cache 隔离；生产源码唯一 socket owner；真浏览器实时消息/通知/状态/重连。
- 已有测试在：`features/auth/auth-fetch.test.ts`、`app/App.test.tsx`、各消费者现有测试（扩展/迁移）；无合适 runtime 测试，新建 `src/realtime/user-stream/user-stream.test.ts`，理由：新的公开订阅 interface 与独立 lifecycle 状态机没有既有归属文件；新建 `features/auth/auth-session.test.ts`，理由：freshness interface 是 auth transport 的新 observable contract；新建 `tests/contract/test_im_frontend_user_stream_ownership.py`，理由：现有仓库尚无该 ownership contract。
- 落层/目录/marker：前端 Vitest 随源码共置（unit/integration）；`tests/contract/`，marker：无；真浏览器为一次性 e2e 签收证据，不新增常规套件。
- 可选依赖 importorskip：无（浏览器签收使用项目已有 Playwright 环境，不进入 pytest 收集）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`M1-realtime-runtime/evidence/` 下截图、浏览器/network/console 摘要与真栈日志摘录；不提交临时驱动脚本。

用户路径分类：`critical-path`（不改变 UI/视觉，但改变 Chat、通知、状态的实时数据链路）。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 真浏览器登录、打开 Chat，验证实时消息与状态 |
| loading | N/A：不改变既有页面 loading 展示 |
| empty | N/A：不改变空态 |
| error | 断网/IM 重启后恢复；refresh 暂时失败由 interface 测试覆盖 |
| disabled | 通知开关关闭时不弹系统通知 |
| submitting | N/A：不改变提交交互 |
| permission denied | 浏览器通知未授权时不弹系统通知 |
| long content | N/A：不改变消息渲染 |
| missing/nullable data | 非法/缺 event id frame 不推进 cursor；status frame 可无 event id |
| mobile viewport | 抽检移动端 Chat 实时更新 |
| desktop viewport | 完整 live-critical 签收 |
| dark mode（如项目支持） | N/A：本产品当前无独立 dark mode 契约 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| auth token freshness 与账号切换竞态 | auth session interface Vitest | 是 |
| socket resume/reconnect/cursor/recovery | runtime interface Vitest | 是 |
| 当前会话、toast、通知、Node/Agent 状态迁移 | 现有消费者 regression + 真浏览器 | 是（行为）+ 否（一次性证据） |
| expired access + valid refresh 后断网恢复 | 真栈浏览器注入过期 JWT、恢复并观察用户可见新事件 | 否，一次性证据 |
| 生产第二 socket owner 回流 | Python architecture contract | 是 |

Prototype / Reference Contract：N/A（design 明确不改变 UI/交互/视觉且不产 prototype）。

## Roadpoints

### R1 — Auth session freshness coordinator

- 状态：DONE
- 步骤：先写 interface 红测；实现 JWT freshness、共享 refresh single-flight、retry/signed_out 与 stale-result guard；让 `authFetch` 共用 coordinator。
- 验证：auth session/auth fetch Vitest；网络/5xx 不清 session、refresh 401 才清、A→B 延迟结果不覆盖 B。

### R2 — 单一 user-stream lifecycle

- 状态：DONE
- 步骤：先写 runtime interface 红测；实现单 socket/多 subscriber、generation、resume/ping/backoff、cursor、resync/recovery、readiness 与隔离。
- 验证：runtime Vitest 覆盖 design M1 worker 退出标准全部 lifecycle 分支。

### R3 — 消费者迁移与真栈签收

- 状态：DOING
- 步骤：迁移 Chat/toast/notifier/Nodes/Agents；AppProviders session cache reset；删除两套旧 stream；补 ownership contract；完成相关回归、build 与真栈浏览器签收。
- 验证：相关/全量 Vitest、production build、Python contract；`evidence/` 中逐条映射用户可见 Chat/toast/notification/status/reconnect/account isolation，含 expired access + valid refresh。
