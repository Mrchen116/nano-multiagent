# feat-340-M8: feature-attachments — Tasks

> 对齐: ../design.md (Milestone 表 M8 行 + 决策 8)

## 目标

桌面拖入图片/PDF 到 chat composer → chip 出现 (缩略图 / 文件 icon + 文件名 + 叉号删除) → Send → 消息气泡渲染附件 (图片缩略 / 文档链接);后端 `/im/v1/uploads` 加 MIME 白名单 + 单文件 10 MB + 单消息 5 个上限;tool / relay 路径继续拿到附件 URL (路径 M2/M4 已就绪)。

## 退出标准

- [ ] 后端 `/im/v1/uploads` MIME 白名单 (`image/*` / `application/pdf` / `text/plain` / `text/markdown` / `application/json`) 之外 → 415
- [ ] 后端 `/im/v1/uploads` body 超 10 MB → 413
- [ ] `POST /conversations/{id}/messages` attachments > 5 → 400
- [ ] 前端 `features/chat/attachments/` 新建:`useAttachmentUpload` hook + `AttachmentChip` + `AttachmentDropzone`
- [ ] `MessagePane` composer 接 dropzone:拖入图片/PDF → chip 出现 → Send 携带 attachments → 清空
- [ ] `MessageBubble` 渲染 `attachments`:图片缩略图 (`<img>`) / 非图片 chip (文件名 + 下载 link)
- [ ] vitest 整页 integration 测试:拖入文件 → chip → Send 调 `createMessage` 含 attachments → 气泡渲染

## 测试策略

- **后端** (pytest, `tests/im_service/integration/test_messages_api.py` 增量):
  - 405 路径:`text/plain` 仍允许 (white-list);`application/x-sh` → 415
  - 413 路径:11 MB body → 413
  - 400 路径:6 个 attachments → 400
- **前端** (vitest):
  - `useAttachmentUpload` 单测:upload 成功路径返回 `AttachmentPayload`;415 / 413 抛错带 i18n key
  - `AttachmentChip` 单测:图片显示缩略图 (URL = props.url),非图片显示 file_name + 叉号删除
  - `AttachmentDropzone` 单测:拖入 → onAdd(files)
  - `MessagePane` 测:dropzone 状态 + composer Send 把 attachments 传给 onSend
  - `MessageBubble` 测:渲染图片附件 `<img>`,渲染 PDF 附件 `<a>` 带 file_name
  - integration 改写 chat-workspace test:模拟拖文件 → chip 出现 → Send → POST 含 attachments
- **入口验证**:vitest integration 模拟拖+发,后端 contract test 用 TestClient post 真实 binary。

## Roadpoints

### R1 — 后端 uploads 白名单 + size 限制 + 消息 attachments 上限

- 步骤:
  - 在 `src/IM/api/routes/messages.py` `create_upload`:校验 `Content-Type` 在白名单 → 415;校验 body size ≤ 10 MB → 413
  - 在 `create_message`:校验 `len(payload.attachments) <= 5` → 400 (走 `map_message_write_error`)
- 验证:
  - 新增 4 个 integration test
- 状态: DONE

### R2 — 前端 attachments hook + 原子组件 (useAttachmentUpload / AttachmentChip / AttachmentDropzone)

- 步骤:
  - `src/IM/frontend/src/features/chat/attachments/use-attachment-upload.ts`:接 `authFetch` POST `/im/v1/uploads`,返回 `{ upload(file) → Promise<Attachment> }`,415/413 转 i18n 错误码
  - `src/IM/frontend/src/features/chat/attachments/attachment-chip.tsx`:图片缩略 / 文件 icon + name + onRemove
  - `src/IM/frontend/src/features/chat/attachments/attachment-dropzone.tsx`:`onDragOver` / `onDrop` 包装容器,emit `files`
- 验证:vitest unit 9 tests
- 状态: TODO

### R3 — MessagePane composer 接 dropzone + chip 列表 + onSend 携带

- 步骤:
  - 在 `message-pane.tsx`:textarea 外包 `AttachmentDropzone`,状态 `pendingAttachments: Attachment[]`,handleSubmit 把 attachments 传给 `onSend(text, attachments)`;chip 列表渲染在 composer 上方
  - 兼容现有 `onSend(text)` 签名:扩展为 `onSend(text: string, attachments?: Attachment[])`
- 验证:vitest 增加 message-pane 测试
- 状态: TODO

### R4 — MessageBubble 渲染 attachments

- 步骤:
  - `message-pane.tsx` `MessageBubble`:`message.attachments` 中 `content_type` 以 `image/` 开头 → `<img>` 缩略;否则 `<a>` 含 file_name
- 验证:vitest 单测
- 状态: TODO

### R5 — chat-workspace-page 接通 + integration test

- 步骤:
  - `chat-workspace-page.tsx` 把 `onSend` 改成 `(text, attachments)` 传给 `createMessage({ ..., attachments })`
  - integration test 增量:模拟 fetch upload + send → 验证 chip + attachments POST payload
- 验证:vitest integration 跑通
- 状态: TODO
