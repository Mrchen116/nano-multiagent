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
