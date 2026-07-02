# feat-447-M11: external-live-parity — Tasks

> 对齐: `../design.md` Milestones 表 `feat-447-M11`。

## 目标

让外部 channel 的 live 体验与内部 IM shadow 会话一致：外部用户消息写入 IM 后无需刷新即可出现；飞书触发 run 时，IM shadow 中每个用户可见 assistant 文本气泡都按气泡完成边界回写飞书，terminal 不重复；IM shadow 入口触发的回复不回写飞书。

## 退出标准

- [ ] 外部 channel 同步用户消息写入 IM 后，打开的 IM shadow 会话无需刷新即可实时出现该用户消息，显示「你」或外部发送者名。
- [ ] 真实飞书 1:1 入站触发一个会产生中间 assistant 气泡的问题时，内部 IM shadow 中每个用户可见 assistant 文本气泡都必须在飞书收到对应消息；最终气泡不得重复。
- [ ] 从 IM shadow 入口触发的回复仍不得回写飞书。
- [x] 根因回归测试覆盖：外部 sync 用户消息写入后产生可被前端 reducer 插入的 canonical `message.created` payload（含 content/attachments/sender display name），`message.sent/delivered` 保持 delivery/progress 语义。
- [ ] 前端 reducer 对 `message.created` 去重并正确渲染 sender display name。
- [ ] Gateway external reply mirror 以 assistant 气泡完成为边界发送，跳过 thinking/tool-only/NO_REPLY，按 dedupe key 防 terminal 重复。
- [ ] Feishu THINKING reaction 只在 final/terminal 删除，中间 visible reply 不提前删除。
- [ ] 全量非 e2e 测试无回归，至少跑相关窄测 + `pytest -m "not e2e"` 或说明环境 blocker。
- [ ] live-critical 证据：真 Gateway + 真 IM + 真 Feishu/Lark 平台入站。使用 `lark-cli im +messages-send --as user` 发给本 worktree Gateway config 中 `channels[].name == "feishu:<agent_id>"` 的 `settings.appId` 对应 Bot。

## 测试策略

- 被测行为（来自退出标准）：
  - 外部 sync 用户消息写入 IM 后广播 canonical `message.created`，payload 足够前端直接插入，且 `message.sent/delivered` 保持 delivery/progress 语义。
  - 前端 reducer 对 `message.created` 按 `message_id` 去重，并优先使用 payload sender display name 渲染外部发送者。
  - Gateway 对外回复镜像按 assistant 可见气泡完成边界发送，跳过空文本、thinking/tool-only、`NO_REPLY`，terminal final send 按 dedupe key 不重复。
  - Feishu adapter 只在 final/terminal 阶段删除 THINKING reaction。
  - 真实 Feishu 入站能驱动真 Gateway/真 IM/真 Feishu 可见结果。
- 已有测试在：
  - `tests/im_service/unit/test_ws_event_types.py`（扩展 message.created payload shape）
  - `tests/im_service/unit/test_repositories_message.py` 或 `tests/im_service/integration/test_messages_api.py`（扩展外部写入 live event）
  - `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts`（扩展 reducer）
  - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` / `tests/unit/test_feishu_adapter_send.py`（扩展 mirror、dedupe、reaction lifecycle）
- 落层/目录/marker：
  - Backend/unit: `tests/im_service/unit/`, `tests/unit/`, marker 无
  - Backend/integration: `tests/im_service/integration/`, marker 无
  - Frontend unit: `src/IM/frontend/src/features/chat/v2/*.test.ts`, vitest
  - Live-critical 验收为一次性证据，不落永久 e2e
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree 内真 IM/Gateway/Feishu live run 的命令输出、日志 nonce、conversation/message id、飞书回复 message id 或时间戳，记录在 `progress.md`。

用户路径分类：`critical-path` + `bug-regression`。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | `message.created` 外部用户消息实时插入当前打开会话 |
| loading | N/A，本 milestone 不改 loading 视图 |
| empty | reducer 从空消息列表插入外部用户消息 |
| error | N/A，本 milestone 不改错误视图 |
| disabled | N/A |
| submitting | N/A，外部用户消息无浏览器提交态 |
| permission denied | N/A |
| long content | N/A，文本渲染路径不变 |
| missing/nullable data | `sender_display_name` 缺失时继续回退 `sendersById`/null |
| mobile viewport | live-critical 浏览器验收覆盖桌面；移动布局未改，N/A |
| desktop viewport | live-critical 浏览器验收覆盖打开 shadow 会话 |
| dark mode（如项目支持） | N/A，未改样式 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 外部用户消息写入后打开会话不刷新看不到 | repository/API/event payload 回归 + 真实 IM/Gateway/Feishu live | 是（回归）+ 一次性 live |
| 前端 live 插入显示 UUID 而不是外部名字 | reducer unit test | 是 |
| 飞书只收到 terminal 最后一段或最终重复 | Gateway mirror/dedupe unit test + live-critical | 是（回归）+ 一次性 live |
| 中间回复过早删除 THINKING reaction | FeishuAdapter send lifecycle unit test | 是 |
| IM shadow 入口误回写 Feishu | Gateway trigger_source/im test + live/日志证据 | 是 + 一次性 live |

## Roadpoints

### R1 — IM live `message.created` payload — DONE

- 步骤:
  - 扩展 `message.created` payload builder，包含 attachments 和 sender display name。
  - 外部/服务端写入用户消息后追加 canonical `message.created` conversation event，保留 `message.sent/delivered` delivery/progress 语义。
- 验证:
  - `pytest -q tests/im_service/unit/test_ws_event_types.py tests/im_service/unit/test_repositories_message.py tests/im_service/integration/test_messages_api.py`

### R2 — 前端 reducer display name 与去重

- 步骤:
  - 扩展 `WsEvent` 的 `message.created` 类型，接收 attachments 和 sender display name。
  - reducer 插入消息时使用 payload display name，按 `message_id` 去重，保持已有 optimistic echo 语义。
- 验证:
  - `cd src/IM/frontend && npm run test -- chat-stream-reducer.test.ts`

### R3 — Gateway external reply mirror 与 reaction lifecycle

- 步骤:
  - 在 Gateway kernel event observer wiring 中增加 external reply mirror。
  - 以 assistant 气泡完成为边界回写外部 channel，跳过 thinking/tool-only/空文本/`NO_REPLY`。
  - `OutboundRouter`/`OutboundMessage.metadata` 携带 `reply_phase` 与 `reply_dedupe_key`，terminal final send 去重。
  - Feishu THINKING reaction 只在 `reply_phase=final` 或 terminal 阶段删除。
- 验证:
  - `pytest -q tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/test_feishu_adapter_send.py tests/unit/test_feishu_adapter.py`

### R4 — live-critical 与全量门禁

- 步骤:
  - 用 worktree 高位端口启动真 IM + 真 Gateway，读取 worktree config 中 Feishu `appId`，确认 `lark-cli auth status --json --verify` appId 与 Bot open id 匹配。
  - 使用 `lark-cli im +messages-send --as user` 发给 Bot，记录 nonce、日志、IM conversation/message id、飞书回复 message id 或时间戳。
  - 跑相关窄测和全量非 e2e。
- 验证:
  - `pytest -m "not e2e"`
  - live evidence 写入 `progress.md`
