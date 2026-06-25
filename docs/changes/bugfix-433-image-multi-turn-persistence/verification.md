# Verification Report: bugfix-433

> Round 1 — 2026-06-25

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 9/9 tasks complete；Spec 全 5 条 requirement 有实现 |
| Correctness | 8/8 scenarios 有实现 + 测试覆盖；全套 unit/contract 测试 2537 passed |
| Coherence | 5 条 design 决策 + 2 条 CRITICAL 全部遵守；1 条 WARNING（delta-spec 归并缺失） |

1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 9/9 complete**（`M1-image-end-to-end/tasks.md` 全部打 `[x]`）

**Spec requirement 覆盖：**

| Requirement | 实现状态 |
|---|---|
| 用户发的图片当前轮即可被 agent 看到 | covered |
| 图片在多轮对话中跨轮保留 | covered |
| 纯文本会话行为不受影响 | covered |
| 异常图片明确告知用户，不静默隐藏 | covered |
| submit / append_message 两条入口能力对等（内核层图片通道统一） | covered（design 决策4 消除双轨） |

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 单轮发图即问 — 当前轮 agent 看到图片 | `state.py:106-136` render_user_content_parts；`loop.py:236` user_parts 透传；`prompting.py:100-103` content:list | `test_build_chat_messages_images.py::test_current_user_with_image_yields_list_content` | covered |
| 单轮发多张图 — 全部送达 | `runtime.py:552-576` M246 展开；extra image part 携带 parts 而非 render_user_text | `test_agent_runtime.py::test_multiple_image_parts_all_reach_provider` | covered |
| 上一轮发图，下一轮文字追问仍可见 | `runtime.py:538` user_msg.parts 写盘；`jsonl_store.py:754-775` _to_message 读 parts；`prompting.py:107-113` _history_content 回放 image block | `test_agent_runtime.py::test_image_survives_persist_reload_and_replays_to_provider`；`test_session_persistence_fidelity.py::TestImagePartsRoundTrip` | covered |
| 不含图片的多轮文字对话 — 零回归 | `render_user_content_parts` 无 image 时返回 None；`_message_to_entry` 仅 parts 非空才写 entry["parts"] | `test_build_chat_messages_images.py::test_current_user_without_image_keeps_str_content`；`test_pure_text_user_turn_has_no_parts_key_in_jsonl` | covered |
| 发送异常/超大/损坏图片 — 明确告知不调模型 | `inbound_pipeline.py:870-910` _reply_image_failure；经 _bg_reply_sender outbound 回发；不 submit；三条固化文案 `inbound_pipeline.py:98-105` | `test_gateway_image_inbound.py::test_download_failure_stops_turn_with_fixed_message`；`test_oversize_image_stops_turn_with_fixed_message`；`test_corrupt_image_stops_turn_with_fixed_message` | covered |
| Anthropic mapper user 分支支持 content:list image 块 | `anthropic/mapper.py:151-152` + `_map_user_content_blocks:195-222` | `test_user_image_mapping.py::test_anthropic_user_branch_maps_image_block_to_base64_source` | covered |
| OpenAI-compat mapper user 分支支持 content:list image 块 | `openai_compat/mapper.py:108-109` + `_normalize_tool_output_parts:230+` | `test_user_image_mapping.py::test_openai_user_branch_maps_image_block_to_image_url` | covered |
| gateway inbound 把 IM HTTP URL 下载转 base64 data URL | `inbound_pipeline.py:815-868` _resolve_image_parts；`main.py:3953-3974` _build_attachment_fetcher 注入 | `test_gateway_image_inbound.py::test_inbound_downloads_attachment_to_base64_data_url` | covered |

**固化文案一字不差核对：**

| 类型 | design 决策5 | 实现 `inbound_pipeline.py:99-104` | 一致 |
|---|---|---|---|
| download | `这张图片没能加载，我没有收到它，无法据此回复。请重新发送图片试试。` | 同上 | ✓ |
| oversize | `这张图片太大了，超出可接收的大小，我没能收到它，无法据此回复。请压缩或换一张更小的图片后重新发送。` | 同上（跨行拼接后一致） | ✓ |
| corrupt | `这张图片我无法识别，没能收到它，无法据此回复。请确认图片有效后重新发送。` | 同上 | ✓ |

**CRITICAL-1（M246 多图全送达）：** `runtime.py:555-572` 展开时 image part 构造携带 `parts=tuple(blocks)` 而非 render_user_text 占位符，`test_multiple_image_parts_all_reach_provider` 验证 img1/img2 均出现在 LLM 请求 user messages 中，img1 不丢失。✓

**CRITICAL-2（失败 outbound-only，不写 kernel 历史）：** `inbound_pipeline.py:870-910` `_reply_image_failure` 调用 `_deliver_stop_ack`（走 `_bg_reply_sender` WS 路径），直接 return `PipelineResult(run_id="")` 不调用 `kernel.submit`，session 历史天然干净。`test_gateway_image_inbound.py` 三个失败测试断言 `kernel.send_calls == []`。✓

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策1：图片在 gateway 入站把 IM HTTP URL 下载转 base64 data URL | 是 | `inbound_pipeline.py:815-868` _resolve_image_parts；`main.py:2448-2449` _build_attachment_fetcher 注入 |
| 决策2：build_chat_messages 新增 user_parts；有图时 content:list，无图时 content:str（不变量1） | 是 | `prompting.py:48-104`；loop.py:236 透传 user_parts；runtime.py:532 render_user_content_parts |
| 决策3：两 provider mapper user 分支支持 content:list image 块，复用既有 image 转换 | 是 | `anthropic/mapper.py:151-152,195-222`；`openai_compat/mapper.py:108-109,230+` |
| 决策4：Message 增 parts 字段；_message_to_entry 新增 parts 写出；_to_message + entries.message_from_turn_entry 两路均读 parts | 是 | `types.py:41`；`runtime.py:2192-2193`；`jsonl_store.py:758-774`；`entries.py:136-151` |
| 决策5：失败走 gateway outbound（_bg_reply_sender），不 submit，不写 kernel 历史；固化文案三条一字不差 | 是 | `inbound_pipeline.py:870-910`；固化文案字符串完全匹配 |
| CRITICAL-1：M246 展开 image part 携带结构化 parts（多图全送达，不只末图存活） | 是 | `runtime.py:555-572`；`test_multiple_image_parts_all_reach_provider` 验证 |
| CRITICAL-2：失败 outbound-only，不写 kernel session 历史 | 是 | `inbound_pipeline.py:886,903-910`；测试断言 `send_calls == []` |

**架构自洽性（§4.3）：**
- 图片 IO（下载）在 gateway 入站边界（`inbound_pipeline.py`），`core` 全程只见 data URL，满足 `core 不 IO` 约束。
- gateway 只 import `agent.sdk`，未反向 import `agent.core` / `agent.platform`。
- 失败路径在 gateway 闭合，不进 core（无 core/runtime 中途回退）。

---

## Issues

### CRITICAL

无。

### WARNING

**W1：delta-spec 归并缺失**

design.md `契约层增量` 节明确要求：
- `docs/specs/kernel/spec.md`：新增「经 submit/append_message 携带 image part 的消息，图片送达模型且随会话历史保留、后续 turn 仍可见」行为契约。
- `docs/specs/gateway/spec.md`：新增「用户经 IM 发送图片，agent 当轮即可看到、后续轮追问仍可见」以及异常图片明确告知的用户可见行为。

当前两份 spec 均未更新（kernel spec grep image/multimodal 0 matches；gateway spec 无当前轮/跨轮/异常图告知条目）。

**修复**：在 `docs/specs/kernel/spec.md` 的适当 Requirement 下补一条 Scenario（参照 design 决策4 + incident 验收标准），在 `docs/specs/gateway/spec.md` 的 `通道中继去重并把多媒体附件透传给内核` Requirement 下补三条 Scenario（当轮可见、跨轮追问可见、异常图明确告知）。这是 design 要求的收尾归并，实现已正确，spec 作为长青行为记录须对齐。

### SUGGESTION

无。

---

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

# Round 2 — 2026-06-25

> 复核范围：fix1（bf2cd70 前 diff 10f30ad1..bf2cd70 src/），8 项改动。

## Round 2 Summary

| 维度 | 结果 |
|---|---|
| Correctness | fix1 全部改动正确，与 design 决策不冲突 |
| No regression | round 1 已验主路径（决策4 两路 parts、CRITICAL-1/2）均未破坏 |
| Test suite | 2546 passed（+9 新测试） |

All fix1 changes correct. Round 1 WARNING（delta-spec 归并）仍待收尾。

## fix1 改动逐项核对

| 改动 | 文件:行 | 正确性 |
|---|---|---|
| #1/#2 PNG/JPEG/GIF/WEBP 结构校验（stdlib-only，无 Pillow） | `inbound_pipeline.py:1351-1396` | 正确；pyproject + import 均 0 matches |
| #3 render 条件对齐 `image_url is not None` | `state.py:128` | 正确；修复 url=None 时误走 list 分支 |
| #4 entries 空 parts 不写（对齐 _message_to_entry） | `entries.py:111-114` | 正确；消除两写路径结构差异 |
| #5 `build_prompt_messages` 透传 `user_parts` | `prompting.py:150-154` | 正确；补上 public API 缺失的图片通道 |
| #6 mime 优先 detected over client content_type | `inbound_pipeline.py:858` | 正确；`detected_mime or mime` 回退逻辑 |
| #7 M246 extra parent 锚 `user_msg.message_id` | `runtime.py:556-563` | 正确；修正 parent 链错序，blocks 构造不变 |
| #8 抽 `parse_parts` 共用两回放路径 | `entries.py:124-135`；`jsonl_store.py:766` | 正确；行为等价，round 1 测试仍通过 |

---

# Round 3 — 2026-06-25

> 复核范围：fix2 scope B（1532c74d..72813954）+ fix3 trivial（72813954..a3a48e3f），HEAD a3a48e3f。

## Round 3 Summary

| 维度 | 结果 |
|---|---|
| Correctness | fix2/fix3 全部改动正确，与 design 决策不冲突 |
| No regression | round 1/2 已验主路径均未破坏 |
| Test suite | 2550 passed（+4 新测试覆盖 fix2/fix3） |

All fix2+fix3 changes correct. Round 1 WARNING（delta-spec 归并）仍待收尾。

## fix2 scope B 逐项核对（prompting.py）

**strip 逻辑正确性：**

`_image_turns_to_strip_after_error`（`prompting.py:126-149`）：对每条 `is_provider_error` 消息向前走，找最近含 image parts 的 user turn 加入 strip set；跳过堆叠 error marker；遇到 assistant 或无 image 的 user turn 即停。`image_strip_ids` 在过滤 `is_provider_error` 前计算（`prompting.py:74`），信号不被提前丢弃。逻辑正确。

**scope 真限 image：**

`_history_content` 第一行 guard（`prompting.py:161`）：`if not _message_has_image_parts(message): return message.content`——纯文本 user turn（`parts=None`）直接走此分支，`strip_image` 参数无效。`test_pure_text_turn_with_provider_error_unchanged` 验证通过。

**不过度 strip：**

`strip_image` 仅当 `message.message_id in image_strip_ids` 时为 True（`prompting.py:101`）。正常成功的图片 turn 后跟 assistant 正常回复，不被 error 信号覆盖。`test_image_turn_without_error_keeps_image` 验证通过。

**strip 后 text 保留、fallback 正确：**

`strip_image=True` 时收集 `type==text` blocks；有则返回 list；全无 text 时 fallback 到 `message.content`（str 投影）。保证 content 非空。

**JSONL 不动：** strip 仅在重放层（`build_chat_messages`），`_message_to_entry` / `_to_message` / `parse_parts` 均未修改，JSONL `parts` 字段不变。

## fix3 trivial 逐项核对（inbound_pipeline.py）

**PNG 最小长度 28→45 修正：** 正确算法：signature(8) + IHDR chunk(4+4+13+4=25) + IEND chunk(4+4+0+4=12) = 45 字节。`test_png_shorter_than_minimum_complete_length_is_rejected` 验证 44 字节被拒、真实 PNG 通过。

**`detected_mime or mime` 死代码简化：** `_detect_image_mime` 非 None 才到此行（None 已早返回 `"corrupt"`），`or mime` 永不执行，直接使用 `detected_mime` 正确，无行为变化。

**已知限制注释：** 仅信息补充，不改逻辑，损坏图拦截路径不变。
