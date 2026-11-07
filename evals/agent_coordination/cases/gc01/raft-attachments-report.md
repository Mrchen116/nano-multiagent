Raft 附件调研完成。只读检查源码，未启动服务、未改文件。以下是图片、普通附件、HTML 和 Markdown 的调研结果，尚未进入设计或实施。

## 一句话结论
RAFT 是「**两步引用**」：Agent 先用 `raft attachment upload --path <本地文件> --target <#chan|dm:@peer>` 上传拿 `attachment_id`，再用 `message send --attachment-id` 绑定到消息。**模型从不传字节**（不传 base64、不传 multipart），只传本机绝对路径；服务端凭证由 daemon 的 origin-bound 本地代理 broker，Agent 只持代理令牌。附件是消息子资源，不可编辑/改名/单独删除。

## 链路分步要点（file:line）
1. 能力告知：daemon 系统提示 `packages/daemon/src/drivers/__snapshots__/systemPrompt/common.md:24`；Agent 手册 `manual/agent-knowledge/attachment.md:32,55-57`。
2. CLI 序列：`cli/src/commands/attachment/upload.ts:241-360` → capabilities(`:276`) → resolve-channel(`:294`) → 按 10MiB 阈值分流(`:301-303`)。
3. 小文件：一次性 multipart 到服务端 `POST /internal/agent-api/upload`（`server/src/routes/internalAgentApi.ts:5276-5370`，必须有 channelId、`canAgentPostToChannel`、归档/计费/配额门）。
4. 大文件：`POST /attachment-upload-sessions` 拿 presigned PUT（绑 Content-Type + `If-None-Match:*`，TTL 15min，`attachmentUploadSessionService.ts:48,307-311`）→ 客户端直传 → `complete` 里 `HEAD` 校验 **size 与 contentType 必须与声明一致**（`:450`），不一致置 failed 并删对象。**没有分片/断点续传**（注释里的 "chunked form" 与实现不符）。
5. 落库：`attachmentUploadWriterService.ts:74-188`（先写 transfer intent 再 PUT，缩略图 WebP 320、SVG 栅格化、失败不影响原件）。
6. 挂载：`attachmentLinkingService.ts:132-238`——必须同一 uploader、不可重复绑定、重复 id 拒绝、上传后 1 小时未发即过期(410)；无每消息附件数上限，但**正文必填非空**，纯附件发不出去。
7. 读取：父消息所在频道成员校验（`routes/attachments.ts:709-736`）+ 300s presigned GET（`:61`）；批量取 URL 上限 50。

## 差异表最关键的 3 条（我们缺哪一层）
1. **Agent 工具层缺"本地路径→上传→attachment id"这一步**。RAFT 把字节搬运留在受信本地进程，服务端只收 multipart 或 presigned PUT；我们 `send_message` 只认已上传 URL，本地路径被静默丢弃——最坏的不是"不支持"，而是"既没成功也没失败"。RAFT 用 4 个显式错误码（`attachment_not_found / already_linked / duplicate / expired`）替代静默。
2. **前端预览层**：RAFT 的 md 是**附件预览里渲染成富文本**（后端只回原始字符串 `providers/markdown.ts:5-35`，前端 react-markdown + rehype-sanitize），HTML 是沙箱 iframe 内联（不是下载、不是新窗口）。我们 chip 只对 `image/*` 出图，其它一律文件链接 → 缺口不止"发不出"，还有"发得进去也看不了"。
3. **隔离基础设施层**：HTML 安全靠两层——`sandbox="allow-scripts"`（绝不给 `allow-same-origin`，`SandboxedPreviewFrame.tsx:1-30`）+ 响应头 CSP `default-src 'none'; sandbox allow-scripts; connect-src 'none'`（`attachments.ts:612-636`），而且 HTML 走**专用流式端点**（不 302 到对象存储，`:1362-1457`）+ 300s 绑定 actor 的 JWT。RAFT 注释明确写"treat every HTML attachment as hostile, whether human or agent"——**不区分可信来源**。它还自认 CSP 放行了 https 外带（`:620-623`），这点我们不该跟。

## 你增补的类型矩阵要点
- **三层都无 allowlist**：上传只校验 `type/subtype` 语法（`attachments.ts:202`）+ magic-byte 嗅探优先于客户端声明（`:430-447`）；DDL 的 `mime_type` 无 CHECK；API schema 只有 1..255 长度。所以 `text/html` 本来就收。
- 上限：单文件 **50MB 免费 / 200MB Pro**（`shared/src/index.ts:3957-3964`），单次 multipart 10 个文件，**每条消息附件数无上限**；预览另有更小 cap（md 128KiB、CSV 5MiB、XLSX 10MiB、PDF 只读 4 字节判签名）。
- PDF 走 **CrossOriginPdfFrame**：Chromium 在 sandbox 里根本不渲染 PDF，只能改用"URL 必须与 App 不同源"的渲染期校验（`CrossOriginPdfFrame.tsx:33-41`）——这条对我们很重要，别以为加了 sandbox 就安全。
- Markdown 相对路径图片：**没找到任何重写逻辑**（推断：会解析到 App origin，基本坏图）；外部 https 图可加载。
- 产物概念是 4 套互不通：普通附件 / `AgentWorkspace`（浏览 Agent 机器文件，不写 attachments 表）/ Wiki（已退役 `0286_retire_wiki.sql`）/ **Raft Artifacts 是外部 App（artifact-share），实现不在本仓**。另有 `announcement_image_assets` 专门的"Agent 产出图片"表带孤儿回收——说明 RAFT 对可迭代产物另建表，不塞进附件。

## 给 Nano 的三个关键决定（供范围对齐）
① 上传与发消息拆两步、用不透明 id 连接（零基础设施，最能直接解决静默丢弃）；② 渲染安全靠 iframe sandbox + 响应头 CSP，不靠 sanitize 字符串（纯前端可做）；③ 大文件 presigned + HEAD 校验——**这一条依赖对象存储/签名 URL，我们现在大概率没有，抄不了**，只能停在 multipart + 更小上限（RAFT 自己的 legacy 通道就是 90MiB 安全值）。
风险最高的是 HTML 同源 XSS（Nano 是 IM+Web 同源部署，误加 `allow-same-origin` 就等于把 cookie/localStorage 交出去）；其次是"只放宽 allowlist 不做预览层"，会得到比不支持更糟的"下载一个文件"。

## 没找到/未验证
未跑任何服务；未追到 `attachment_object_charges` 的写入点；`attachments.width/height` 当前上传路径未写入；无消息编辑/删除 API；无病毒扫描；无 content_hash 去重（同文件重传=新对象）；**未找到"仅可信来源才渲染 HTML"的分支**（代码明确拒绝这种区分）；Raft Artifacts 实现不在本仓，只读了手册描述；Slack bridge 附件通道只确认存在未展开。
另：`attachmentLinkingService` 只校验 uploader、**不校验附件 channel 与消息 channel 相同**，所以"在 A 频道上传、id 发到 B 频道"在代码层可行（可见性随后由 B 频道决定）——不构成越权读，但与手册"tied to that channel scope"不完全一致。
