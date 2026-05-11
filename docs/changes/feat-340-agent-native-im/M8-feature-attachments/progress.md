# feat-340-M8 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — uploads 白名单 + size 限制 + attachments 上限

- Context: design.md 决策 8 锁:`POST /im/v1/uploads` 必须有 MIME 白名单 + 单文件 10 MB + 单消息 ≤ 5 个附件。M4 之前 `create_upload` 已实装 sanitize + 持久化路径,但完全没做内容类型校验和 size 校验,任何 binary 都会被吞下去,导致 agent 端可能被诱导消费 risky payload。
- Decision: 在 `src/IM/api/routes/messages.py` 的 router 文件顶部声明三组常量:`_UPLOAD_ALLOWED_PREFIXES=("image/",)`、`_UPLOAD_ALLOWED_EXACT={"application/pdf","text/plain","text/markdown","application/json"}`、`_UPLOAD_MAX_BYTES = 10 MB`、`_MESSAGE_MAX_ATTACHMENTS = 5`。在 `create_upload` 把 `Content-Type` 通过 `_is_allowed_upload_content_type` 校验 → 415 unsupported;`len(body) > 10 MB` → 413 oversized。在 `create_message` 入口前置检查 `len(payload.attachments) <= 5`,超过 → 400 "too many attachments"。
- Rationale: 白名单放路由文件内私有常量而非配置中心:design.md 写死本期常量,且 `settings_policies.max_attachment_size_mb` 是 owner 可调字段(运营层语义),与"agent 安全边界"语义不同——后者是 hard rule 不应被租户改。401/415/413/400 全部 HTTPException 大声失败(§0.2),不静默 truncate / 丢 attachment / 静默成功。MIME 校验放在落盘之前是为了避免 disk IO 浪费。
- Evidence:
  - Tests: `pytest tests/im_service/integration/test_messages_api.py` → 14/14 pass(新增 4 个,其中"text/markdown 已在白名单"在 C1 时直接 green,标 baseline 不算 Red→Green;另 3 个完整 Red→Green)。
  - 周边回归:`pytest tests/im_service/integration/test_messages_api.py tests/im_service/unit/test_relay_service.py tests/unit/personal_assistant/test_web_relay_adapter_attachments.py` → 39/39 pass。
  - 仓库其余 baseline 失败(`test_m136_group_chat_flow` / `test_m103_im_gateway_e2e` / `test_conversation_rename` 等)与本 milestone 无关:`git stash` 后失败相同,确认是 pre-existing。
  - Entry: TestClient 用 `application/x-sh` POST 直接被 415 拦下;11 MB body 被 413 拦下;6 个 attachments 被 400 拦下。这是真实 HTTP 入口路径,不是 mock。
- Rollback: revert C2 `849da6c4`(实现)+ C1 `b7b6d93d`(测试)。
- Commits: C1=b7b6d93d, C2=849da6c4, C3=(本提交)
- Next: R2 — 前端 `features/chat/attachments/` 三个原子组件 (useAttachmentUpload / AttachmentChip / AttachmentDropzone)。
