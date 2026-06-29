# feat-445-M1: fork-branch — Tasks

> 对齐: ../design.md v2.5

## 目标

用户在单聊里某条「已完成的 agent 回复」上点 fork → 自动进入一个与同一 agent 的新单聊，里面带着从会话起点到该条回复（含）的完整气泡历史，且 agent 带着「源在该点的上下文记忆」继续对话（与源体验逐字一致）。原会话不变、两线独立。agent 离线时 fork 不可用且明确提示。一个 run 产出多条 agent 气泡时，每条都能各自精确 fork。

## 退出标准

- [x] kernel `fork_session(up_to=message_id)` 真实化：复用现有 boundary-aware materialize（截断到 M）+ 现成已测 `_fork_locked`，新旧会话独立、保真保留 reasoning/工具。（R2）
- [x] **分支≡源在 M 守护测试三组全绿**：① 源已压缩、fork boundary 后 → summary+boundary..M；② 源已压缩、fork boundary 前老消息 → 应用 M 前 boundary 后到 M 的视图；③ 源未压缩 → 到 M 全部 turn。（R2 test_fork_session.py）
- [x] relay 把逐气泡 kernel `message_id` 落到 IM 消息行（含一 run 多气泡，每泡各自正确）；单测锁定。（R1 + R6 序列化到前端）
- [x] gateway fork RPC handler：binding 定位源 session → kernel.fork_session(up_to) → bind 新会话；单测绿。（R3）
- [x] IM `fork_conversation`：建会话 + 复制 0..M 展示历史 + 在线校验 + 失败回滚 + 旧气泡无 message_id 拒 fork；单测绿。（R4）
- [x] 前端 fork 按钮（agent 已完成 + 单聊 + 在线 + 有 kernel message_id 才出现）+ forkMutation + 跳转 + 成功 toast(4s)；vitest + 真实浏览器验收。（R5 + R6 浏览器截图）
- [x] live 端到端真栈：浏览器点 fork → 新会话带记忆、可追问；离线禁用；两线独立。（R6 API e2e + playwright；多气泡 fork 机制由 R1/R2 单测锁定，详见 progress R6）
- [x] `pytest -m "not e2e"` 全树不回归；前端 `npm run test` 相关用例绿。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. kernel as-of-M materialize 截断正确（三种压缩态）→ 分支模型视图 = 源在 M 的视图。
  2. fork 新旧会话独立、re-stamp、保真 reasoning/工具（沿用现有 test_fork_session.py，扩 up_to 场景）。
  3. relay 落 kernel message_id 到 IM 行，逐气泡正确（含 roll 多气泡）。
  4. gateway fork RPC handler 端到端单测（binding→fork→bind）。
  5. IM fork_conversation 编排（建会话/复制/在线校验/回滚/旧气泡拒绝）。
  6. 前端 fork 按钮可见性逻辑（4 个 gate）+ forkMutation。
- 已有测试在：`tests/unit/test_fork_session.py`（扩展 up_to / 压缩态三组）；`tests/unit/test_session_store*.py`（store.load up_to 截断，新建或扩展）；gateway observer 测试（扩展或新建 `tests/unit/test_gateway_relay_kernel_message_id.py`）；IM service 测试（新建 `tests/unit/test_im_fork_conversation.py`）；前端 `src/IM/frontend/src/features/chat/v2/__tests__/`（fork 按钮 + mutation）。
- 落层/目录/marker：tests/unit/（kernel/gateway/IM 进程内单测，无 marker）；tests/e2e/ 或 scripts/ 临时脚本（live 验证，e2e marker / 临时不进套件）；前端 vitest。
- 可选依赖 importorskip：无（live 验证用真栈脚本，不进 pytest 套件）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：live e2e 截图（fork 按钮、新会话带记忆、离线禁用、多气泡 fork）放 ACCEPTANCE/ 或 progress 记录路径。

### 前端 UI 部分

用户路径分类：
- fork 按钮 + 跳转新会话（含历史完整、可继续对话）= `critical-path`（核心业务路径，须可重复 regression + 真实浏览器验收）
- fork 成功 toast / 按钮 hover 视觉 = `visual-only`（截图验证）
- agent 离线置灰 + 提示 = `normal-ui`（浏览器临时验收）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | agent 已完成回复 hover 出 fork 按钮（截图 + vitest） |
| loading | fork 进行中按钮 disabled / spinner（截图） |
| empty | N/A（fork 入口挂在已有消息上） |
| error | fork 失败 toast「fork 失败，请重试」（手动触发 + 截图） |
| disabled | agent 离线置灰 + tip「该 agent 当前不可用，暂时无法 fork」（截图 + vitest） |
| submitting | 同 loading |
| permission denied | N/A |
| long content | 长 agent 回复气泡上 fork 按钮锚定不溢出（截图） |
| missing/nullable data | 无 kernel message_id 的旧气泡 → 无 fork 按钮（vitest） |
| mobile viewport | 375 宽下 fork 按钮可达（截图） |
| desktop viewport | 1440 宽（截图） |
| dark mode | N/A（项目未支持） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| fork 按钮可见性 4-gate（agent/completed/direct/online/有id） | vitest + 浏览器截图 | 是(vitest) |
| fork → 新会话带记忆、可追问 | live e2e 真栈 | 是(临时脚本 + 截图证据) |
| 一 run 多气泡分别 fork 精确 | live e2e + kernel/gateway 单测 | 是 |
| 离线禁用 + 提示 | vitest + 浏览器截图 | 是(vitest) |
| 成功 toast 4s 淡出 / 按钮 hover 视觉 | 浏览器截图对照 prototype | 否 |

## Roadpoints

### R1 — relay 落逐气泡 [DONE] kernel message_id 到 IM 消息行（决策 4 地基）

- 步骤: gateway `message_completed` 帧（turn_end `main.py:3700` + `_roll_bubble:3252`）带上该气泡的 kernel message_id（turn_end 用 `ctx["kernel_message_id"]`；roll 用进入时旧气泡的 kernel id，沿 token_usage 同款「气泡终结元数据」precedent）；IM `Message` 模型加 `kernel_message_id` 字段 + DB 列迁移 + repo write/read + `event_bridge.on_message_completed`/`update_runtime_state` 落库；`_handle_streaming_delta` message_completed 取出转发。
- 验证: gateway observer 单测——喂一 run 多 assistant_message（不同 message_id 触发 roll），断言每个气泡 message_completed 帧带各自 kernel id；IM 持久化往返单测——`update_runtime_state(kernel_message_id=...)` 写入、`_message_from_row` 读回、fork 复制路径透传。

### R2 — kernel fork_session [DONE](up_to=M)：as-of-M 截断 + 复用 _fork_locked

- 步骤: `jsonl_store.load` 加 `up_to: str|None`——读完 raw_lines 后定位 `type==turn and uuid==up_to` 的行，截断到该行（含），找不到 raise（不静默回落）；`manager.load` 透传 up_to；`runtime.fork_session` 加 `up_to`——有 up_to 时 flush writer + 从 JSONL 重 materialize（不用过期内存缓存）→ 交 `_fork_locked`（无 up_to 时保留现有 cache-first，不破 5 个现有测试）；`kernel.fork_session` 加 up_to 并委托 runtime（替换现有 stub）。
- 验证: 分支≡源在 M 三组守护测试（压缩后/压缩前/未压缩）；扩 test_fork_session.py 的 up_to 截断 + 独立性 + reasoning 保真。

### R3 — gateway fork RPC [DONE] handler（session.fork.request → result）

- 步骤: `im_connection.py` 新增 `session.fork.request` dispatch（仿 capabilities.resolve/agent.create）；注入 provider 回调：由 source_conversation_id+agent_id 经 `session_keys` binding 定位源 session_id → `kernel.fork_session(source, up_to=message_id, workspace_root=agent.workspace_root)` → `bind_conversation_session(new_conv → new_session)` → 回 `session.fork.result{ok,new_session_id}`；失败回 `{ok:false,error}`。
- 验证: handler 单测——预置 binding，断言 fork 调用入参（up_to）、新 binding 落库、result 帧形态；源缺 binding / fork 抛错 → ok:false。

### R4 — IM fork 编排 [DONE]（service + route + WS RPC + 在线校验 + 回滚）

- 步骤: `web_im_service.fork_conversation(actor, source_conversation_id, fork_message_id)`——校验归属/direct-agent 类型/消息为 agent+completed/该行有 kernel_message_id（旧气泡无 → 400）/agent node 在线（否则 409）；建新会话(title=agent名) + 复制 0..fork_message_id 展示消息（含 kernel_message_id 透传）；`gateway_handler.request_fork_session` 发 WS RPC 等回包（超时/失败 → 删新会话回滚 → 502/409）；`api/routes/web_im.py` 加 `POST /conversations/{id}/fork`。
- 验证: IM service 单测（用 fake gateway_handler）——建会话+复制到 M+在线校验+RPC 失败回滚+旧气泡无 message_id 拒绝+跨租 404。

### R5 — 前端 fork 按钮 [DONE] + mutation + toast + 跳转

- 步骤: `chat-types.ts` Message 加 `kernel_message_id?`；`chat-api.ts` 加 `forkConversation`；`message-pane.tsx` MessageBubble 加 fork 按钮（gate: isAgent && completed && isDirectChat && agentOnline && kernel_message_id；离线显置灰 + tip）+ `.chat-bubble-card` position:relative + global.css `.chat-bubble-fork`/`.fork-tip`（照 prototype）；`chat-workspace-page.tsx` forkMutation（双缓存失效 + navigate）+ 成功 toast（复用 InAppToast，4s）。
- 验证: vitest——按钮可见性 4-gate + 旧气泡无按钮 + 离线置灰；真实浏览器截图（default/loading/disabled/long/mobile/desktop）对照 prototype。

### R6 — live 端到端真栈验收 [DONE]

- 步骤: e2e-up.sh 起 IM+Gateway+proxy（ephemeral 端口、config 隔离、auto-bind）；浏览器走查 design Runbook 六条：① hover fork→跳新会话历史完整可追问且 agent 记得；② 用户/生成中消息无入口；③ 离线禁用+提示；④ 原会话不变两线独立；⑤ fork 中间某条 fork 点后不带；⑥ 一 run 多气泡分别 fork 精确到对应那条。
- 验证: 真栈截图 + log 证据进 progress Evidence；env 受阻按 §0.11 报 BLOCKED 不降级。
