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
