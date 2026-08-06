# bugfix-508: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `0e79d9b4a264703807c25f25ec121a8b000c5f11` (`origin/main`)
- Head: 本 unit 的未提交工作树，随后以本 unit commit 固化。
- Commits: 实现前无本 unit commit。
- Included dirty files: slash 面板、双语文案、群聊控制门控、按 Agent 的节点投递及对应测试。
- 受影响模块：`src/IM/frontend` 的聊天 composer；`IM` 的 group relay 投递；`personal_assistant.gateway.inbound_pipeline` 的群聊准入。

## 最终结构

### 组件与职责

- `SlashPicker` 的内置候选从仅 `/stop` 扩为 `/stop`、`/new`、`/compact`；群聊的 `/new` 使用专门说明文案。
- `InboundPipeline._should_process()` 保留 MENTION 群聊的默认门控，但将内置 Web IM 的精确裸 `/new` 作为全群控制例外；reply / mention 仍只操作目标 Agent，`ALWAYS` 不放宽 `/compact`。
- IM group relay 为每个参与 Agent 创建独立 relay，并按该 Agent 配置的 node 投递；每个 relay 带自己的 `agent_id`，因此无需增加广播协议或共享 session。

### 调用链与数据流

1. 用户在 Web IM 群聊发送 `/new`；IM group relay fan-out 为每个参与 Agent 产生一条 relay，并推送到该 Agent 所在 node。
2. 每条 relay 进入其 node 的 `WebRelayAdapter`，带同一群聊、不同 `agent_id` 与空 `mentioned_agent_ids`。
3. `InboundPipeline` 解析精确控制命令；群聊准入接受裸 `/new`，并为当前 relay 的 Agent 调用既有 `SessionRunCoordinator.new_session()`。
4. 每个 Agent 的 session binding 独立替换，控制确认沿既有 Web relay 投递回原群，因此用户看到每个 Agent 一条确认。

### 状态、数据与兼容性

- `/new` 仍保留原聊天的可见历史；只替换后续调用的 Kernel session binding。
- 群聊裸 `/new` 不是共享 session，也不是一个聚合事务：每个 Agent 以原有的独立 relay、重放 identity 与失败语义处理。
- 精确匹配限制保留：`/new` 之外带额外文字仍是普通消息；`/compact` 及 `/compact <关注点>` 仍需 mention/reply 指向 Agent。外部 IM 群聊继续要求明确 Bot 目标。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 复用 group relay fan-out，并按 Agent node 推送 | IM 已按 Agent 分发群消息；补齐每条 relay 自己的 node，避免跨节点群聊漏掉 Agent，同时不新增共享状态。 | `src/IM/application/relay_service.py`、`src/IM/api/routes/messages.py` |
| 群聊面板说明全体作用域 | 否则可发现的裸命令会掩盖其影响范围。 | `src/IM/frontend/src/features/chat/components/slash-picker.tsx` |
| 保持 `/compact` 的明确目标要求 | 压缩不可逆且用户未要求放宽；避免把本次 `/new` 取舍外溢。 | `src/personal_assistant/gateway/inbound_pipeline.py` |

## 失败路径、风险与回滚

- 单个 Agent 的新会话发布失败时，既有 `new_session` 失败语义保留原 binding；其他 Agent 的独立结果不被伪装成成功。跨 node 的 relay 仍分别投递，互不阻塞。
- 群内会出现每个 Agent 的确认气泡，这是全体重开已完成的可见证据，不合并为无来源的单一系统提示。
- 若需回滚，撤销本 unit commit 即恢复原 slash 面板与群聊 mention gate；不涉及数据迁移。

## 与初始意图的差异

最初只修复“面板未展示 `/new`”。实际浏览器检查发现 Web IM 群聊面板会填写当时不被 MENTION 策略接纳的裸 `/new`；用户随后明确将其定为“全部重开”，因此同一 unit 同时完成该用户可见行为。

## 验证定位

- 用户验收：用户授权 Agent 自行快速实际界面检查后继续收尾。
- 自动化测试：`tests/unit/personal_assistant/test_gateway_stop_command.py`；`tests/unit/IM/test_messages_broadcast.py`；`src/IM/frontend/src/features/chat/components/slash-picker.test.tsx`；`src/IM/frontend/src/features/chat/components/message-pane.test.tsx`。
- 运行证据：隔离 IM/Gateway E2E 两 Agent 群聊中发送 `/new`，`e2e` 与 `e2e-peer` 各显示“已开始新会话”。

## Canonical 文档影响

- Delta-spec：`specs/IM/web-chat-ux.md`、`specs/gateway/routing-delivery.md`。
- 归并目标：对应 IM Web Chat UX、Gateway Routing and Delivery current specs。
