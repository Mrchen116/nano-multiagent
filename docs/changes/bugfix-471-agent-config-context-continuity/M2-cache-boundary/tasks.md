# bugfix-471-M2: cache-boundary — Tasks

> 对齐: ../design.md

## 目标

在聊天实际首次采用新的有效 Agent 运行配置时，持久化并展示一条锚定在该用户消息之前的非消息型缓存分界线；该边界在 IM、Gateway、外部 Feishu shadow 与 Web IM 历史/live 状态中一致恢复。

## 退出标准

- [ ] 配置实际首次采用时，固定文案 divider 位于首条用户消息前；reload、reconnect、older-page prepend 后位置稳定。
- [ ] divider 不是消息气泡，无头像、发送者、状态或菜单；1440、1280、375 viewport 不破坏原聊天布局。
- [ ] 休眠聊天、连续修改、纯展示修改、保存失败与 fork 都遵循 design.md 的边界语义。
- [ ] 外部 shadow 在 IM 离线与 Gateway restart 后可恢复锚定消息、回复与唯一 divider；Feishu 使用 app_id + event.message_id。
- [ ] M2-C5、M2-C6 的回归测试，以及 `npm run test && npm run build`、`pytest -m "not e2e"` 全绿，并留下 durable browser/live evidence。

## 测试策略

- 被测行为（来自退出标准）：anchor divider 的 IM 幂等持久化、分页/fork/user-stream replay；Gateway outbox 的 ACK/reconnect/restart 与 shadow saga；Feishu typed identity；前端 REST reset、older prepend、live/reconnect 的有序幂等渲染。
- 已有测试在：`tests/im_service/{unit,integration,contract}/test_*messages*`、`test_*event*`、`test_fork_*`、`tests/unit/personal_assistant/test_gateway_shadow_sync.py`、`test_inbound_shadow_identity_guard.py`、`test_feishu_adapter.py`、`src/IM/frontend/src/features/chat/{chat-stream-reducer.test.ts,chat-workspace.integration.test.tsx,components/message-pane.test.tsx}`（扩展）；新建文件仅限持久 outbox/saga 无适合归属时。
- 落层/目录/marker：纯行为在 `tests/unit/` / `tests/im_service/unit/`，HTTP/跨模块在 `tests/im_service/integration/`，真实浏览器/真 Gateway/Feishu 在 `tests/e2e/`，marker：e2e。
- 可选依赖 importorskip：浏览器验收使用现有 Playwright 体系，缺失时 importorskip；永久 Python/前端回归测试无新增可选依赖。
- 本 milestone 产生的一次性验收证据（不进套件）：`evidence/` 下的 desktop 1440/1280/mobile 375 截图、reload/reconnect/prepend/fork 录屏或截图、真实 Feishu shadow 与 IM 离线/Gateway restart 旅程日志。

## 前端计划

用户路径分类：critical-path + bug-regression。

| 状态 | 覆盖计划 |
|---|---|
| default | 首次配置切换后的 anchor divider |
| loading | 历史初载与 older-page prepend |
| empty | N/A：无 anchor 消息不能有 divider |
| error | 保存失败、IM error ACK 不生成 divider |
| disabled | N/A：divider 无交互控件 |
| submitting | 发首条采用新配置消息时 live divider 到达 |
| permission denied | N/A：分界线不涉及权限 |
| long content | divider 文案自然换行且不横向溢出 |
| missing/nullable data | live divider 先到、anchor 后到；旧历史无 divider |
| mobile viewport | 375 真浏览器截图 |
| desktop viewport | 1440 与 1280 真浏览器截图 |
| dark mode（如项目支持） | N/A：当前产品不提供聊天深色模式 |

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| API timeline anchor、分页与 fork | IM repository/HTTP/contract regression | 是 |
| WS late/replay 与 REST reset/prepend 合流 | reducer/workspace integration regression + reconnect 浏览器验收 | 是 |
| divider 非消息视觉语义 | MessagePane component regression + 三 viewport screenshot | 是（交互语义） |
| 外部 shadow crash/restart 恢复 | gateway/Feishu 回归 + 真 Feishu shadow journey | 是 |

## Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| prototype.html `.boundary` | must-match：固定文案、首条采用新配置用户消息前，desktop 1440/1280/mobile 375 | `evidence/` 三 viewport 截图与 progress Prototype Comparison | worker |
| MessagePane | must-match：独立 timeline entry，无 avatar/bubble/sender/time/menu/status | component regression + screenshot DOM/视觉核对 | worker |
| history + live stream | must-match：reload/reconnect/older-page prepend 锚定稳定 | reducer/workspace regression + 真浏览器流程 | worker |
| chat design tokens | may-adapt：低于正文视觉层级 | screenshot 对照 | worker |
| sidebar/messages/composer | out-of-scope：不改版 | screenshot 对照 | worker |

## Roadpoints

### R1 — IM typed timeline 与配置边界协议（TODO）

- 步骤：增加 durable `agent_config_changed` entry、Gateway ACK 协议、owner/idempotency、分页/fork/user-stream 读写链路。
- 验证：IM repository/HTTP/WS/contract 覆盖 anchor、late arrival、replay、pagination 和 fork。

### R2 — Gateway outbox 与外部 shadow saga（TODO）

- 步骤：将 actual-applied intent 写入 durable outbox；扩展 external typed identity、Feishu mapping、shadow anchor/response 的可恢复幂等流程。
- 验证：断线/ACK/restart/重复重放、typed identity 缺失与 Feishu mapping 回归；真 Feishu shadow 恢复旅程。

### R3 — Web IM timeline union 与真实浏览器验收（TODO）

- 步骤：以 typed timeline 替代 messages-only reducer/render，增加无消息语义的 divider 并保持 reset/prepend/live/reconnect 有序幂等。
- 验证：Vitest regression、build、desktop 1440/1280/mobile 375、reload/reconnect/older-page prepend/fork 真浏览器 evidence。
