# Real-model failure boundary: external LLM proxy

- Product acceptance R2: nano tree `800f4dfe3`, Gateway PID 13964, isolated IM :55354.
- Failed session: `sess_f5a92d256fbb504c`; input `4f49220c1907450380ff41a8fe09e4d5`; output `73b6ebd71c6a4ddcb870bcc622694215` in `c_lheq3l87`. Model replied that only an image placeholder was available.
- Local proxy evidence: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-19_13-25-12_997_sess_f5a92d256fbb504c/2026-09-19_13-25-23_923-req-anthropic_messages.json`. This is the actual request sent from nano to proxy, not a constructed unit fixture.
- Actual wire: `messages[4].content[0]` is a tool_result with `[text, image]`. Image source is base64 image/png, decoded size 1595 bytes, SHA-256 `9633971832d60fbcfb65405ac59d0ed1134b921a5fe76269fb78a0e3b62aa800`. Visual inspection of decoded bytes confirms a red rectangle on white background, matching uploaded source.
- External repository: `/Users/czj/Repos/LLM_PROXY`, HEAD `016f32eb7c44f58d8429d833f8973c8cc43ba337` (read-only investigation).
- `src/bridge/anthropic_codex.py` calls `anthropic_messages_to_openai_chat_messages`; it delegates to `proxy_converters.anthropic_messages_to_openai`.
- Actual converter at `proxy_converters.py:178-183` reduces `tool_result.content` through `_extract_text_from_blocks`, discarding nested image blocks. Replayed the saved request with that repo's `.venv/bin/python` and real converter: inbox read result `call_YjWfPGkFCDNDaFdxcx6zYgkP` becomes a string containing `image_index` and no image payload. The preceding inbox check likewise remains expected text.
- Conclusion: the observed global Web IM real-model failure occurs after the nano provider boundary, in external Anthropic→Codex conversion. The newly corrected Feishu attachment_index bug is separate. Do not claim R2 product pass or attribute this external loss to the indexed-image fix.
- No secrets or full payloads are copied here. No external code or shared proxy process was modified during diagnosis. Cross-repository repair scope is awaiting user clarification.

## 2026-09-21 contract correction

The loss boundary above remains correct: the original converter discarded the nested image before building a Responses item. The later claim that Codex OAuth required moving that image into a following user message was incorrect. Local Codex source and corrected proxy replay show the native contract is a structured `function_call_output.output` containing ordered `input_text`/`input_image` items; API-key and OAuth routes share that request model. Product Rounds 3/4 had reached the old proxy at `:4000`, so their failures did not establish a Codex tool-output limitation.
