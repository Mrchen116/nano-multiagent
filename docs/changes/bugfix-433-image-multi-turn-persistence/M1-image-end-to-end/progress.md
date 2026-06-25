# bugfix-433-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — 当前轮图片送达 provider

- Context: 断点1（render_user_text 把 image 丢成占位符 + build_chat_messages 只收 user_text）+ 断点3（两 mapper user 分支不发图）。当前轮图片从未到达 provider。
- Decision:
  - `state.render_user_content_parts(parts)`：任一 part 是 image → 返回规范块列表 `[{type:text},{type:image,image_url:data-url}]`；全文本 → None（守 content:str 路径）。`render_user_text` 文本投影**保持原样**（占位符不变，给 content:str fallback / 检索 / 日志）。
  - `build_chat_messages` 加 `user_parts` 参数：当前 user 有图 → content:list；历史侧新增 `_history_content`：`Message.parts` 含 image → list content。
  - loop 调用透传 `render_user_content_parts(state.input_parts)`。
  - `types.Message` 加 `parts` 字段（权威多模态表示，content 降为纯文本投影）。
  - 两 mapper user 分支：content 为 list → 逐块映射（anthropic 新增 `_map_user_content_blocks` 复用 `_to_anthropic_image_part`；openai 复用 `_normalize_tool_output_parts`）。
- Rationale: `LLMMessage.content` 已支持 `str|list[dict]`，顺势用；无图走 str 分支 = 纯文本零扰动（不变量1）。决策2+3 照 design。
- 决策偏差（非 design 偏差，仅 roadpoint 顺序）：把 `_message_to_entry` 写 parts + `_to_message` 读 parts 这两处持久化往返从 R2 **提前到 R1**。原因：加 `Message.parts` 字段当场触发 `test_session_persistence_fidelity` 的 field-conservation guard（要求每个新字段分类 PERSISTED/NOT_PERSISTED 且 PERSISTED 必须真往返）——R1 的 C2 gate 要全绿，就必须同时把往返写好。这是「加持久化字段即连带写其持久化」的内聚边界，非范围扩张。R2 改为：端到端往返测试 + entries.message_from_turn_entry 读 parts + runtime user_msg 携带 parts。
- Evidence:
  - Tests: `tests/unit/test_build_chat_messages_images.py`（6）+ `tests/unit/platform/llm/test_user_image_mapping.py`（4）全绿；守护 `test_core_types_contract` + `test_session_persistence_fidelity` 更新后绿。
  - 全量：`pytest tests/unit tests/contract tests/integration -m "not e2e"` = 2527 passed；ruff check + format clean。
  - Entry: 真实入口（用户发图当轮可见）的端到端验证在 R3 进程内往返 + reviewer 真栈，R1 只到「图片块进 LLMMessage / mapper 输出 provider 形态」单测层。
  - Frontend State Matrix: N/A（无前端）
  - Browser QA: N/A
  - E2E/Regression: R1 单测落库回归；端到端往返见 R2/R3。
  - Visual/Interaction: N/A
- Rollback: 回退到 C3=plan commit（图片不可见，纯文本路径不动）。
- Commits: C1=test red, C2=feat, C3=本次 docs。
- Next: R2 持久化回放——runtime user_msg 携带结构化 parts、entries.message_from_turn_entry 同步读 parts、端到端往返单测（发图→落盘→重建→下轮含 image）。

## R2 — 持久化回放（跨轮可见 + 消除双轨）

- Context: 断点2——user turn 落盘只存渲染后文本（占位符），回放 `_to_message` 不读 parts，图片单轮可见也跨轮丢失；parts 写而不读的悬空双轨。R1 已把 `_message_to_entry`/`_to_message` 的 store 主路径写好（因 guard 连带），R2 补齐 user_msg 实际携带 parts + 第二回放路径。
- Decision:
  - `runtime` user_msg 构造：`render_user_content_parts(input_parts)` → `Message.parts`（有图才落，无图 None 不写 parts 键）。这是图片真正进入持久化的源头。
  - `entries.message_from_turn_entry`：读 `entry.data["parts"]` → `Message.parts`，与 `jsonl_store._to_message` 对齐（两条回放路径都还原图片，不依赖走哪条）。
- Rationale: 决策4——parts 升为权威多模态表示，content:str 降为纯文本投影，回放消费 parts，双轨从「写而不读」变「写且读、一致」。两条回放路径必须同步，否则 append 返回值/entry-based reload 走到时图片仍丢。
- Evidence:
  - Tests: `TestImagePartsRoundTrip`（3）——经真 `JsonlSessionStore.load` 往返 + `build_chat_messages` 回放含 image 块；entries 第二路径读 parts；纯文本无 parts 键。全绿。
  - Entry: 端到端「发图→落盘→重建→下轮含 image」经真 store 往返已验（非全 mock）；真 runtime submit→真栈在 R3 进程内 + reviewer。
  - 全量：`pytest -m "not e2e"` = 2530 passed；ruff clean。重锚 contract 白名单（runtime.py .nano 行 202→208，纯行移位，非新硬编码）。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: R2 往返单测落库；进程级真 submit 往返见 R3。
- Rollback: 回退到 R2 C1 commit（图片当前轮可见但跨轮丢——半程态）。
- Commits: C1=test red, C2=feat, C3=本次 docs。
- Next: R3——gateway 入站 IM HTTP URL 下载转 base64（决策1）、决策5 异常图失败 outbound-only 回发、M246 多图展开携带 parts（CRITICAL-1）、main.py 注入真 fetcher、进程内往返。
