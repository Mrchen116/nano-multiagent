# feat-340-M31: fix-agent-reply-ime-mention-highlight — Tasks

> 对齐: ../design.md v1 (Changelog 2026-05-14 M31 行)

## 目标

M29/M30 完成后用户实际使用发现的 8 个 bug，覆盖 agent 回复链路、token 统计、未读计数、IME 输入、@mention 高亮与路由。

## 问题清单

| ID | 现象 | 范围 |
|---|---|---|
| R1 | Arch 不回复（SSE 竞态：run 完成后才订阅 SSE，事件全部错过） | `inbound_pipeline.py` |
| R2 | Arch 不回复（`realtime_stream` hook 未注册，kernel 不发事件） | `personal_assistant/hooks/communication_context.py` |
| R3 | Token chip context_window 显示为 prompt+completion，非模型限制 | `runtime.py` → `loop.py` → `realtime_stream.py` → `main.py` → `gateway_handler.py` → `token-chip.tsx` |
| R4 | 自己发的消息触发左侧未读徽标 +1 | `repositories.py` create_message |
| R5 | Agent 列表状态点始终灰色（前端双查询竞态） | `agents.py` list_agents + `AgentSummaryResponse` |
| R6 | 中文 IME 输入后 Enter 发送两条消息 | `message-pane.tsx` handleKeyDown |
| R7 | Mention picker 开启时 Enter 键直接发送 @ 而非选中候选 | `message-pane.tsx` handleKeyDown |
| R8 | @xxx mention 文字未高亮蓝色 | `message-pane.tsx` + `global.css`（mirror div 方案） |
| R9 | 群聊 @display_name（如"架构"）不触发 agent 回复 | `relay_service.py` _resolve_mention_to_agent_ids |

## 退出标准

- [ ] R1+R2: 在私聊发消息给 Arch，Arch 在 30s 内回复（无论消息处理快慢）
- [ ] R3: Token chip 显示合理的 context_window（约 200k），进度条不从 50%+ 开始
- [ ] R4: 自己发的消息不增加左侧 sidebar 未读徽标
- [ ] R5: Gateway 在线时 agent 列表状态点显示绿色
- [ ] R6: 中文 IME（macOS 搜狗/系统输入法）输入后 Enter 只发一条消息
- [ ] R7: 群聊输入 `@` 打开 picker 后，Enter 键选中高亮候选而非发送
- [ ] R8: 群聊/私聊输入框中 `@xxx` 文字显示蓝色，其余文字正常色
- [ ] R9: 群聊发送 `@架构 你好吗`，Arch 回复（display_name → agent_id 映射正确）
- [ ] `npm run build` 干净通过

## 已完成的修改文件

### 后端

| 文件 | 修改内容 |
|---|---|
| `src/personal_assistant/gateway/inbound_pipeline.py` | 提前捕获 `anchor_sequence`，作为 `Last-Event-ID` 传入 `stream_session`，消除 SSE 竞态（R1） |
| `src/agent/products/personal_assistant/hooks/communication_context.py` | `DEFAULT_HOOK_MODULES` 追加 `realtime_stream`（R2） |
| `src/agent/core/agent/runtime.py` | `hook_metadata["context_window"] = self._compaction_settings.context_window`（R3） |
| `src/agent/core/agent/loop.py` | `turn_end_payload` 中从 `active_hook_ctx.metadata` 读取并透传 `context_window`（R3） |
| `src/agent/platform/hooks/builtins/realtime_stream.py` | `on_turn_end` 透传 `context_window` 到 SSE 事件（R3） |
| `src/personal_assistant/main.py` | `turn_end` 事件处理中透传 `context_window` 到 token_usage_payload（R3） |
| `src/IM/ws/gateway_handler.py` | `_parse_token_usage` 从事件取真实 `context_window`，不再用 total 替代（R3） |
| `src/IM/infra/repositories.py` | `create_message` 判断 sender == conversation owner，是则不 +1 unread_count（R4） |
| `src/IM/api/routes/agents.py` | `list_agents` join node status，`AgentSummaryResponse` 新增 `node_status` 字段（R5） |
| `src/IM/application/relay_service.py` | 新增 `_resolve_mention_to_agent_ids`，按 display_name 查表解析到真实 agent_id（R9） |

### 前端

| 文件 | 修改内容 |
|---|---|
| `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` | `handleKeyDown` 加 `isComposing` 守卫（R6）；picker 开启时 Enter 不发送（R7）；mirror div + `buildMirrorNodes` 实现 @mention 蓝色高亮（R8） |
| `src/IM/frontend/src/features/chat/v2/components/token-chip.tsx` | `hasWindow = context_window > 0` 守卫，无窗口时隐藏进度条（R3 前端） |
| `src/IM/frontend/src/styles/global.css` | `.chat-composer-highlight-wrapper/mirror/input` + `.chat-composer-mention-highlight` 样式（R8） |
