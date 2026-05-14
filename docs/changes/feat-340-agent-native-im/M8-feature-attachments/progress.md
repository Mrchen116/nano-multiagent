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

## R2 — attachments hook + 原子组件 (use-attachment-upload / attachment-chip / attachment-dropzone)

- Context: design.md 决策 8 + Milestone 表 M8 指定 `src/IM/frontend/src/features/chat/attachments/` 是新目录(与 v2 平级),不挂在 `features/chat/v2/components/` 下——因为 attachments 是横切能力,Message bubble 渲染端和 composer 上传端都要复用,放进 `attachments/` 更符合架构意图。
- Decision: 三个独立模块:
  - `use-attachment-upload.ts`:导出 `uploadOneAttachment(file)` (一次性函数,非 hook;mutation 生命周期由调用方 `useMutation` 管;hook 抽象在这里多此一举)和 `AttachmentUploadError` 类(`code: "unsupportedType" | "tooLarge" | "network"`)。415/413 转 typed error,让上游用 i18n 友好弹 toast。请求路径:`POST /im/v1/uploads?file_name=...`,body 直传 `File`,`Content-Type: <file.type || octet-stream>`,走 `authFetch` 复用 Bearer + refresh。
  - `attachment-chip.tsx`:`AttachmentChip({ attachment, onRemove? })`,图片(`content_type` startsWith `image/`)渲染 `<img src=url>` + `<button aria-label="Remove X">`;非图片渲染 `<a href=url target=_blank>file_name</a>` + 同样的 remove。`onRemove` 缺省时不渲染 remove 按钮——给 bubble 复用(只读)用。
  - `attachment-dropzone.tsx`:薄包装 `<div>`,`onDragOver/Enter/Leave/Drop`,emit `onAdd(files)`;`data-dragging` 属性留给 CSS。
- Rationale: 不把 dropzone + chip + hook 揉成一个大 `AttachmentComposerWidget`,因为 chip 还要在 MessageBubble 用——分原子组件让 v2 与 attachments 两个目录都能消费。`authFetch` 已在 buildHeaders 留了 `body && !(body instanceof FormData)` 的判断,会自动跳过覆盖 binary `Content-Type`,我显式塞 `Content-Type: file.type` 确保后端白名单能拿到准确 MIME(decision 8 白名单按 MIME 不按 extension)。
- Evidence:
  - Tests: `npx vitest run src/features/chat/attachments` → 11/11 pass(upload 4 + chip 4 + dropzone 3)。
  - 全局:`npx vitest run` → 192→195 pass,无回归。
- Rollback: 删 `src/IM/frontend/src/features/chat/attachments/` 整目录。
- Commits: C1=b7b69f72(测试)合并提交;C2=(本提交前一个)
- Next: R3 + R4 — MessagePane composer 接入 dropzone + chip 列表 + bubble 渲染 attachments。

## R3 + R4 — MessagePane 接 dropzone + chip 列表 + onSend 携带 attachments + bubble 渲染附件

- Context: R3 (composer 集成 dropzone + chip 列表) 与 R4 (bubble 渲染 attachments) 都改 `message-pane.tsx` 一个文件,且 R3 的 chip 组件已经在 R2 写好,合并 R3/R4 一次提交比拆开更清晰(避免 R4 改回 R3 已写过的 import 行)。
- Decision:
  - 扩展 `MessagePane` 签名:`onSend(text: string, attachments: Attachment[])`,新增可选 `uploadAttachment?: (file: File) => Promise<Attachment>`(测试 seam,默认 `uploadOneAttachment`)。
  - 状态:`pending: Attachment[]` 与 `draft` 并列;`commit()` 在 trimmed text 或 attachments 至少一个非空时 fire,然后两个都清。Send 按钮 disabled 条件改成 `!draft.trim() && pending.length === 0`(以前是只判 draft)。
  - `<AttachmentDropzone>` 包整个 composer(chip 条 + textarea + send 按钮 + help),不只包 textarea——拖到 chip 条或 send 按钮上也要识别,否则用户体验割裂。
  - `handleAdd`:**顺序** await 上传,失败的 file 默默丢掉(不挂 pending),错误冒泡留给上游 toast(本期 chat-workspace-page 没接 toast,留 follow-up)。
  - bubble 内当 `message.attachments.length > 0` 时渲染一组 `<AttachmentChip attachment={att} />`(无 onRemove → read-only chip)。bubble content 若为空字符串就不渲染 `<div className="chat-bubble-content">`,空气泡 + 只显示附件的情形也合理。
- Rationale:
  - 顺序上传(非 `Promise.all`)防止 5 个大文件并发把 `/im/v1/uploads` 吃满,也保证 chip 顺序与拖入顺序一致(对话经验非常依赖确定顺序)。
  - `uploadAttachment` 注入 prop 让 vitest 可以稳定打桩,不必 stub 全局 fetch——这是 hermes-agent style 的测试缝技巧,比 `vi.mock` 模块替换更稳定。
  - bubble 在 `content` 为空时跳过文本 div,是因为 backend `/im/v1/uploads` + `POST /messages` `content=""` 已经被 integration test (test_uploads_expose_im_hosted_paths_for_message_attachments) 跑过,产品上"纯附件无文字消息"是合法形态。
- Evidence:
  - Tests: `message-pane.test.tsx` 5→9 (新增 4:dropzone 上传 chip 渲染 / Send 携带 attachments / chip × 移除 / bubble 渲染图片+PDF)。
  - tsc:`npx tsc -b` 仅剩 pre-existing `account-page.test.tsx` 错误(与本 milestone 无关)。
  - 全局:vitest 195 pass。
- Rollback: revert C2 `735af93e` 回到 R2 完成状态。
- Commits: C1=1110d080, C2=735af93e, C3=(本提交)
- Next: R5 — chat-workspace-page 接通(passing attachments through createMessage)。

## R5 — chat-workspace-page 接通 + integration test 端到端

- Context: M4 写好的 chat-workspace-page 用 `onSend={(text) => sendMutation.mutate(text)}`,现在 MessagePane 改成 `onSend(text, attachments)`,workspace 层需要传通。同时 `chat-api.ts` 的 `CreateMessageRequest.attachments` 类型用 `{ url; content_type?; file_name? }[]` 与 `Attachment` 的 `string | null` 不兼容,tsc 会报错,需要一并对齐。
- Decision:
  - `sendMutation` 的 `mutationFn` 改成接 `{ text, attachments }`,内部传 `createMessage({ conversationId, content: text, attachments })`。
  - `chat-api.ts` 的 `CreateMessageRequest.attachments` 改成 `Attachment[]`(复用 chat-types 中的 canonical 类型)。
  - integration test 新增一个 case:模拟拖文件 → 上传 → chip → type 文字 → Send → 断言 POST body.attachments 含 uploaded url,且 chip 在 send 后清除。test 用真实 `fireEvent.drop` 注入 `DataTransfer`,fetchSpy mock 处理 `/im/v1/uploads`(返回 201 + json),mock `/messages` POST 时把 `body.attachments` 透传回去。
- Rationale: 这一 R 是 contract 收紧 + 入口验证。改 `chat-api.ts` 类型既消除 tsc warning 也确保未来重构时 `Attachment` 是单一来源——避免 chat-api 自己又长出一个对应字段定义,与 chat-types 漂移。integration test 是 §0.3 要求的"真实入口测试":React Router + react-query + 真实 fetch wrap 路径,不只是 reducer 单测。
- Evidence:
  - Tests: `chat-workspace.integration.test.tsx` 4/4 pass(原 3 + 新 1);全局 vitest 196/196 pass;tsc 无新增错误。
  - 入口路径:`fireEvent.drop` → dropzone → upload-attachment helper → fetch `/im/v1/uploads` mock → chip render → user.click Send → sendMutation → createMessage → fetch POST `/im/v1/conversations/c1/messages` mock,断言 body.attachments 完整一致。
- Rollback: revert C2 `08c82973` 即可回到 R3/R4 完成状态(workspace 仍使用旧 onSend(text) 签名,但 MessagePane 已新签名——这会让 workspace 无法编译;实际 rollback 时应一起 revert)。
- Commits: C1=0ac2cb13, C2=08c82973, C3=(本提交)
- Next: M8 退出标准达成,准备合并到 unit 分支。
