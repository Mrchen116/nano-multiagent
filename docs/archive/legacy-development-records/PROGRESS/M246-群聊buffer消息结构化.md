# PROGRESS: M246 — 群聊 buffer 消息结构化

## 整体决策

- GroupContextStore.drain() 返回 `list[tuple[str, str]]` (sender, text)
- InboundPipeline 在 gateway 层完成 `[sender] text` 格式化，内核收到的仍是普通 text parts
- Runtime 将 parts 列表每个 part 作为独立 user message 追加 history（而非 \n join）
- parts 长度=1 时单 user message 行为不变（向后兼容）
- Communication Context 增加 message_format 说明行（仅群聊）

---

## Roadpoint 记录

### R1 — GroupContextStore 存储 sender 字段
- Context: 需要在 buffer 中记录消息的发送者 ID，以便 pipeline 格式化 [sender] text 前缀。现有 schema 无 sender 列。
- Decision: 新增 `sender TEXT NOT NULL DEFAULT ''` 列；`append()` 新增 `sender=""` 默认参数；`drain()` 返回 `list[tuple[str,str]]`；旧 DB 通过 `ALTER TABLE` migration 自动升级。
- Rationale: 默认空字符串保持向后兼容；migration 在 `_init_db` 中检测列存在性后执行，不破坏已有数据。
- Evidence:
  - Tests: 589 passed
  - Entry: `store.append("k","msg",sender="u"); assert store.drain("k") == [("u","msg")]`
- Rollback: 回退到 commit 94098d3（plan 提交）
- Commits: C1=7fe3a6e, C2=ea0e116, C3=（本次）
- Next: R2 已合并到同一 C2

### R2 — InboundPipeline: drain 后格式化为独立 parts
- Context: drain() 返回 tuple 后需要 pipeline 格式化为 `[sender] text`，且群聊当前消息也需要前缀，直聊不加。
- Decision: `_format_sender_text(sender, text)` 模块级函数；pipeline 在 `_run()` 内用 external_user_id 存 buffer，drain 后格式化 buffered_texts + current_text。
- Rationale: 格式化逻辑放在 gateway 层（inbound_pipeline.py），内核不感知 sender，符合架构分层要求。
- Evidence:
  - Tests: 589 passed
  - Entry: `store.drain(buf_key)` → `[("alice","hello")]` → pipeline → `texts=["[alice] hello","[bob] @agent go"]`
- Rollback: 回退到 7fe3a6e（R1 C1）
- Commits: C1=7fe3a6e, C2=ea0e116, C3=（本次）
- Next: R3

### R3 — Runtime: 多 parts → 多 user message
- Context: kernel 收到 N 条 parts（格式化后的群聊消息）后，runtime 需要将每条作为独立 user message 注入 LLM history，而非 `\n` join。
- Decision: `runtime.run()` 中若 `len(input_parts) > 1`，将 `parts[0..N-2]` 作为 `Message(role="user")` 注入 history，`parts[-1]` 作为当前 user_text。单 part 路径不变。
- Rationale: 最小改动，保持 `build_prompt_messages` 接口不变；history 注入在 runtime 层完成，loop 不感知多 part 语义。
- Evidence:
  - Tests: 589 passed
  - Entry: `run(session, [{"type":"text","text":"a"},{"type":"text","text":"b"}])` → LLM 收到 2 条 user messages
- Rollback: 回退到 471eeb9（R2 test commit）
- Commits: C1=0671f97, C2=8fd45bb, C3=（本次）
- Next: R4

### R4 — Communication Context 增加 message_format 说明
- Context: 群聊中 LLM 需要知道消息格式约定 `[sender_id] message_text`，以便正确解析发送者。
- Decision: `_build_communication_context_block` 在 `conversation_type="group"` 时追加 `"- message_format: [sender_id] message_text"` 行。直聊不加。
- Rationale: 最小侵入；仅产品层 hook 修改，内核不感知。
- Evidence:
  - Tests: 589 passed
  - Entry: `_build_block(conversation_type="group")` → block contains `message_format`
- Rollback: 回退到 8fd45bb（R3 C2）
- Commits: C1=9738cdc, C2=3e15dc9, C3=（本次）
- Next: 合并到 main
