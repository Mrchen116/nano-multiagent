# Code Review: bugfix-567-inbound-attachments

## Round 1 — full

- `executed_base`: `c5f1d5620c6323821a430fc3d53feefeb180fd89`
- `validated_at`: `30dac3b37a5f8a4c28059f003299f119f661c859`
- `review_mode`: `full`; `diff_range`: `origin/main..30dac3b37`

```json
[
  {
    "file": "src/personal_assistant/gateway/inbound_attachments.py",
    "line": 57,
    "summary": "Historical failed data-image descriptions include the complete base64 payload in model text.",
    "failure_scenario": "An unmentioned group message from Feishu stores a valid but oversized or corrupt `data:image/...;base64,...` attachment. During the later mention-triggered projection, SessionRunCoordinator records the failed image via `unread_attachment_text`, which JSON-serializes the original `url`. The model receives the full payload as text (a 5 MiB-plus image becomes roughly 6.7 MiB of base64), rather than only the required unread source/failure fact; this can exhaust context and is not an honest bounded source reference.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/gateway/global_run_coordinator.py",
    "line": 559,
    "summary": "Global mode drops valid Feishu images when their kernel input uses attachment-index placeholders.",
    "failure_scenario": "Feishu emits `kernel_input_parts` such as `{\"type\": \"image\", \"attachment_index\": 0}` alongside the resolved data-image attachment. `_content` treats that placeholder as a populated image list, skips resolving the attachment, then emits nothing because the placeholder has neither `source` nor `image_url`; the image is also excluded from ordinary-file output. A direct `_content` reproduction with the real Feishu shape returned only the text part, so a mixed global message does not deliver its valid image to Inbox/model as the unit requires.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Round 2 — closure

- `executed_base`: `c5f1d5620c6323821a430fc3d53feefeb180fd89`
- `validated_at`: `800f4dfe3ef818dbbf4db0fd2e1ca322dbdf8089`
- `review_mode`: `closure`; `fix_delta_range`: `30dac3b37..800f4dfe3`

The inline-data description now replaces any `data:` source with a bounded inline-source marker before it becomes a history failure text part (`inbound_attachments.py:57-72`). The public pipeline regression uses a 6,990,658-character oversized data URL and verifies that the submitted text remains below 2,000 characters (`test_gateway_image_inbound.py:308-350`).

Global input projection now resolves each valid `attachment_index` exactly once into an Inbox image source at its ordered location, preserves neighbouring provider text, and still emits ordinary-file descriptions (`global_run_coordinator.py:558-625`). The global integration regression supplies the actual Feishu-shaped ordered parts and asserts an image block in the LLM tool content (`test_global_gateway_runtime.py:283-400`).

Both Round 1 findings are closed. The independent closure result is:

```json
[]
```
