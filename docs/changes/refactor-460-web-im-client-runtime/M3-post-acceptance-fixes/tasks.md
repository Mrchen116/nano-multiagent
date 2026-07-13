# refactor-460-M3: post-acceptance-fixes — Tasks

> 对齐: ../design.md（2026-07-13）与 Round 1 `verification.md` / `acceptance.md`

## 目标

关闭 Round 1 暴露的连续性、凭证、绑定、静默回复与在线提醒缺口，删除迁移后残留的重复 API/query 表面；不改变既有桌面/移动 Chat 交互。

## 退出标准

- [ ] Chat recovery 实际重读当前 messages、conversations、agents、nodes 四类权威快照并让页面收敛。
- [ ] 本地仍 fresh 但被服务端 401 拒绝的 access token 经同一 module-level single-flight 强制 refresh；网络/5xx、refresh 401 与 A→B guard 语义不回退。
- [ ] `sessionStorage` 读写失败时 user stream 仍可 resume/ping/分发，且标签页内 cursor 保持单调连续。
- [ ] bind reconciliation 使用真实 QueryClient 传播 refetch 失败，不失败导航；同 token 重试不二次 confirm，token A/B 的成功结果隔离。
- [ ] direct Web IM 的协议静默 token 在 Gateway 源头产生 `message_discarded`，在线撤销 provisional bubble 且刷新历史无消息；外部 channel/其他 delivery context 语义不变。
- [ ] 在线非当前会话 Agent reply 同步触发 toast、权威会话 refetch（未读/preview/排序）；当前会话与 self-authored user message 不误报。
- [ ] 删除未调用 mention API/私有 initials、Agent 详情重复 summary query；直聊继续使用 draft display name。
- [ ] canonical Chat JSON 调用复用 auth transport/error seam，保持既有用户可见错误文本；ownership contract 只约束 `/im/ws/user` 的唯一 owner。
- [ ] 定向测试、全量 Vitest/build、ownership contract、`pytest -m "not e2e"` 与受影响真栈旅程通过，证据持久化在 `evidence/`。

## 范围扩展记录

- Round 1 真栈证明 direct Web IM 的 `NO_REPLY` 被持久化。取证定位到 Gateway `RunDeliveryContext.visibility_policy` 将 direct Web IM 设为 `literal_text`；前端已正确消费 `message.discarded`，在 UI 过滤会掩盖历史错误。
- orchestrator 已明确授权 M3 做最窄 Gateway runtime-delivery policy + 测试修复，仅改变 direct Web IM 协议静默语义；不修改 `design.md`，由 orchestrator 合入后校正 M3 范围表。

## 测试策略

- 被测行为（来自退出标准）：四类 Chat recovery 权威收敛；fresh-but-rejected 401 强制单飞 refresh；storage throw 下实时流连续；真实 QueryClient bind 失败/重试/token 隔离；direct Web IM NO_REPLY tombstone；在线 Agent reply toast + 会话权威 refetch；dead API/重复 query/ownership guard 清理；共享 JSON error seam。
- 已有测试在：`features/auth/auth-session.test.ts` / `auth-fetch.test.ts`、`realtime/user-stream/user-stream.test.ts`、`features/chat/chat-workspace.integration.test.tsx`、`bind-confirm-page.test.tsx`、`chat-api.test.ts`、`hooks/use-global-message-toast.test.tsx`、`features/settings/agents/agent-detail-page.test.tsx`、`tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`、`tests/contract/test_im_frontend_user_stream_ownership.py`（全部扩展/改写，不新建行为测试文件）。
- 落层/目录/marker：frontend Vitest 与源码同目录，marker：无；Gateway 纯编排在 `tests/unit/personal_assistant/`，marker：无；architecture guard 在 `tests/contract/`，marker：无；真进程/真浏览器只作 milestone 验收证据。
- 可选依赖 importorskip：无；真栈复用仓库既有 e2e/Playwright 工具。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时浏览器驱动与诊断数据不提交；截图/报告持久化到 `M3-post-acceptance-fixes/evidence/`。

## 前端实施计划

- 用户路径分类：`critical-path`（Chat 恢复、在线非当前会话提醒、静默回复、绑定、长登录 token 恢复、Agent 详情直聊）；无视觉重设计，当前真实 Web IM 为基线。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 当前/非当前会话实时消息、Agent 详情直聊 |
| loading | recovery/refetch 与 bind reconciliation 期间保持既有页面/pending |
| empty | NO_REPLY 撤泡后不留空消息；空历史回归 |
| error | bind cache refetch 失败原页提示；Chat API 错误文案不变 |
| disabled | bind pending/缺 token 继续禁用 |
| submitting | bind confirm 不重复提交 |
| permission denied | 无新增权限行为；全量 Chat 回归 |
| long content | 无视觉变更；全量 Chat 回归 |
| missing/nullable data | storage 不可用、缺 sender metadata、缺 bind token |
| mobile viewport | 真栈移动 Chat 回归 |
| desktop viewport | 双浏览器在线 toast/unread 与 NO_REPLY/recovery |
| dark mode（如项目支持） | N/A：项目未声明 dark mode 契约 |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| resync 前移 cursor 后页面仍旧 | 实际调用 recovery callback，切换 REST snapshot，断言消息/Agent/Node/会话 UI 收敛 | 是 |
| fresh token 401 重放旧 token | auth transport 回归，断言一次 refresh + 新 token replay + 既有失败分类 | 是 |
| storage SecurityError 击穿 socket callback | production cursor adapter 测试 + runtime 分发/resume/ping 断言 | 是 |
| bind refetch 错误被 TanStack 吞掉 | 真实 QueryClient/queryFn 首次失败、同 token retry、token A→B | 是 |
| NO_REPLY 仍落库 | Gateway observer unit + 真栈发送/刷新历史 | 单元测试是；真栈证据否 |
| 在线 Agent reply 无 toast/未读 | canonical created→completed 事件序列 hook test + 双浏览器真栈 | hook 是；真栈证据否 |
| dead/duplicate surface 回流 | API/test 删除、query-count 行为断言、ownership contract | 是 |

### Prototype / Reference Contract

N/A：design 明确不改变 UI/交互/视觉，不产 prototype；以当前真实 Web IM 为基线。

## Roadpoints

### R1 — auth/runtime 与 Chat recovery 连续性

- 步骤：红测锁定 fresh-but-rejected 强制 refresh、storage throw 下 resume/dispatch、四类 Chat recovery 与收窄 ownership guard；实现共享 force-refresh entry、safe cursor adapter、settled recovery refetch/reset。
- 验证：auth/session/runtime/workspace 定向 Vitest、ownership contract、build。

### R2 — bind reconciliation 真实失败与 token 隔离

- 步骤：用真实 QueryClient/queryFn 建红测，覆盖首次 refetch 失败不导航、same-token retry 不 confirm、A→B 必须 confirm B；实现 `throwOnError` 与 token-scoped confirmed result。
- 验证：bind 页面定向集成测试、全量相关 frontend test。

### R3 — 静默回复、在线提醒与 canonical Chat API 收口

- 步骤：红测锁定 direct Web IM NO_REPLY discard、canonical agent created→completed toast/refetch、dead mention API 删除与共享 JSON error seam；在 Gateway 源头修 policy，补在线事件聚合，删除重复 helper/API。
- 验证：Gateway runtime delivery unit、toast/chat API/reducer/workspace 定向测试、真栈 NO_REPLY + 双浏览器提醒。

### R4 — Agent 详情去重与全量验收

- 步骤：红测证明详情页不为 Open chat 创建第二个 Agent summary query，并以 draft display name 创建直聊；删除重复 query/state/stale 叙事，完成全量门禁与桌面/移动真栈回归。
- 验证：Agent detail 定向测试；全量 Vitest/build/contract/non-e2e/e2e-critical；持久化 evidence。
