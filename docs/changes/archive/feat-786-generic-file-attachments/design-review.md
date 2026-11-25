# Design Review — feat-786-generic-file-attachments

## Round 1

### Metadata

- **Reviewer**: Antigravity (`change-design-reviewer` subagent `c8869a00-c644-49e5-b812-47f943c309a2`)
- **Review Target**: `docs/changes/feat-786-generic-file-attachments/design.md`（对齐 `spec.md v1`）
- **review_mode**: `full`
- **mode_reason**: Gate 2 首次独立审查（Round 1 必须执行 full mode，全面核对现状断言、关键决策、生产接线、用户约束、Agent Context / 前端影响、delta-spec 与 milestone）。
- **started_at**: `2026-11-25T11:58:02+09:00`
- **completed_at**: `2026-11-25T12:04:14+09:00`
- **duration**: `6m12s`

### Verdict

**Issues Found** — `3 CRITICAL` / `2 WARNING` / `3 Recommendations`

---

### Coverage 与证据

- **现状与生产接线核实**：逐一对照实际组装入口与运行代码：
  - IM Server：`apps/im-server/src/media.ts`、`messaging.ts`、`personal-actions.ts`、`personal-images.ts`、`personal-agent.ts`、`personal-input-context.ts`、`work.ts`、`server.ts`、`gateway.ts`
  - Node Host：`apps/node/src/main.ts`、`screenshot-upload.ts`、`im-http.ts`
  - Personal Assistant：`packages/personal-assistant/src/global-agent.ts`、`personal-assistant.ts`、`single-thread.ts`、`tool-references.ts`、`inbox.ts`、`screenshot-delivery.ts`、`presentation.ts`、`store.ts`
  - DSH Integration & Contracts：`packages/dsh-integration/src/message-arguments.ts`、`global-mode.ts`、`agent-config.ts`、`capabilities.ts`、`personal-security.ts`、`policy/approval.ts`、`policy/file-approval.ts`、`policy/sources.ts`、`packages/product-contracts/src/chat.ts`、`chat-codec.ts`、`capabilities.ts`
  - Web 前端：`src/IM/frontend/src/features/chat/attachments/attachment-chip.tsx`、`attachment-link.tsx`、`use-attachment-upload.ts`、`interactive/interactive-card.tsx`、`components/conversation-tool-card.tsx`、`components/message-pane.tsx`、`i18n/{en,zh}.json`
- **需求覆盖与用户约束**：
  - 用户确认的格式放开 + 下载强隔离头（`Content-Disposition: attachment` + `X-Content-Type-Options: nosniff` + `Content-Security-Policy: default-src 'none'; sandbox`）、分层大小上限（通用 `25 MiB` / 位图 `10 MiB` / 静图 `≤ 4096×4096`）、0 字节拒绝、5 附件上限、单人 `1 GiB` / 全服 `10 GiB` 配额、30/min 与并发 2 路限流、以及基于 `codex/feat-780` 独立建分支均与 `spec.md` 一致。
  - **缺口**：PA 暂存上传与外发审阅链路（`R1-C1`）、`download_attachment` 跨模式权限与路由（`R1-C2`）、`local_files` 脱敏/回执/超时与路由幂等（`R1-C3`）、PA 输入审阅附件边界（`R1-W1`）存在会直接导致实现走偏或验收失败的未收口点。
- **架构判断（职责、依赖方向与复用）**：
  - **依赖方向合法**：保持 `apps/node` 经 `@nano/dsh-integration/client` 隔离、`PA/Channels/IM` 不 import DSH、共享契约下沉 `packages/product-contracts`（如 `isRasterImageMime`），无违背 `AGENTS.md` 架构红线。
  - **复用策略合理**：直接复用 `media.ts` 流式落盘与 `attachment_storage` 配额模型、`messaging.ts:publicationAttachments` 持久化结构、`tool_references` SQLite 短 ID 表以及 `screenshot-delivery.ts` 幂等上传模式，无需新增数据库表或第二套存储服务（`一次性部署迁移: 无` 判断成立）。
  - **职责错位需修正**：`design.md:15` 将下载能力描述为"注入 `GlobalAgent` / `SingleThread`"，而实际生产装配（`apps/node/src/main.ts:530-540`）中 SingleThread 与 Global 的全部 `product.call` 均由 `GlobalAgent.call()` 统一分发；应保持单一调用入口在 `GlobalAgent`，避免在 `SingleThread` 复制一套 `product.call` 路由。
- **专项能力检查（Agent Context & 前端体验 & 原型边界）**：
  - **原型边界**：本 unit 前端改动仅收口位图判断（SVG 走既有文件芯片而非内联图片）与超限 i18n 文案，无新增页面、布局重构或待对齐视觉交互决策，**不需要 `prototype.html`**，未见遗漏也未多余生成。
  - **Agent Context（设计阶段审查）**：
    - `nano-product-identity` 同步覆盖 `local_files` 与 `download_attachment` 不新增系统段、不破坏前缀缓存方向正确；
    - **已确认设计缺陷**：`personal-security.ts:224` 仍写着 `"Local paths are not uploads; no upload tool is provided."` 未同步（见 `R1-C1`）；`url` 与 `attachment_id` 在工具输出中的共存关系未明（见 `R1-C2`）；SingleThread 图片附件未提供 `attachment_id`（见 `R1-C2`）；`presentation.ts` 未对 `local_files` 脱敏（见 `R1-C3`）。
  - **前端安全与体验**：`attachment-chip.tsx` 与 `interactive-card.tsx` 已纳入，但遗漏了 Work 视图 `conversation-tool-card.tsx:63` 对 `image/*` 的直接 `<img>` 渲染（见 `R1-W2`）。
- **delta-spec 与 Milestone**：
  - `docs/specs/im/conversations-messages.md`、`docs/specs/gateway/routing-delivery.md` 两个既有 Requirement 标题锚定准确，但 `docs/specs/gateway/global-agent.md` 缺少具体 Requirement 锚点，且未评估对 `conversations-messages.md:522`（草稿上传失败反馈）与 `personal-agent.md:202`（PA 披露审核）既有条款的联动影响（见 `R1-W2`）。
  - Milestone M1 退出标准可观测，审查安排覆盖 `change-code-review`、`agent-context-review` 与隔离实栈验证（单 milestone 粒度偏粗，作为可选建议列于 `R1-R1`）。

---

### 历史问题闭环

Round 1，无历史问题。

---

### Issues

#### `R1-C1` [CRITICAL] PA 外发 `local_files` 的暂存会话作用域、快照结构、UTF-8 校验与系统提示冲突均未闭合

- **具体位置**：`design.md` 架构总览（L42-67）、关键决策 1 & 3（L74-85）、接口与数据流（L92-138）
- **证据**：
  1. **PA 写入非主人群直接 403**：`apps/im-server/src/messaging.ts:120-125` 规定，当 `personal_agent_bindings` 存在且 `mode === "write"` 时，若目标会话不是 `ownerConversation`，直接 `fail(403, "personal_reviewed_delivery_required")`。因此现有 `packages/personal-assistant/src/personal-assistant.ts:245-251` 发送 `local_images` 时，先经 `pa.action.status({ prepare_screenshot: true })` 预检目标会话可写，再把文件**上传暂存到 `config.personal!.conversationId`**（主人私聊），经独立披露审核通过后再在 `apps/im-server/src/personal-actions.ts:264-271` 复制到 `op.conversation_id`。`design.md` 全文未区分 PA 暂存上传与普通 Agent 直接向目标会话上传，也未说明 `personal-assistant.ts:175, 180, 183, 195, 226, 245-258, 273-284, 314-322` 对 `local_files`（含 `prepare_screenshot` 预检复用/扩展、外部渠道/incident/owner-representation 拒绝、`unknown` 回执查询）的完整接线。
  2. **`personal-actions.ts` / `personal-images.ts` / `personal-security.ts` 存在致命 `image: true` 与 `startsWith('image/')` 耦合**：
     - `apps/im-server/src/personal-actions.ts:50` 对所有非 `textual` 附件硬编码了 `{ image: true, ... }`，而 `personal-actions.ts:205-210`（`prepareChecked`）会先用 `b.conversation_id` 调 `this.attachments(...)` 并把快照送进 `decodePersonalImages`；
     - `apps/im-server/src/personal-images.ts:6` 与 `packages/dsh-integration/src/personal-security.ts:88` 均仍使用 `content_type.startsWith('image/')`（后者还按 `row.image === true` 筛选），两者都**不在** `design.md:77` 的 `isRasterImageMime` 替换清单中。
     - 结果：PA 外发 `.svg` 时会在 `decodePersonalImages` 触发 `sharp` 解码报 `422 attachment_image_unsupported`（而非 `409 attachment_content_review_unavailable`）；非文本二进制或 `> 256 KiB` 文本若被标成 `image: true`，会在 `personal-actions.ts:213` 被 base64 读入并在 `personalReviewImages` 崩溃。
  3. **缺少严格 UTF-8 校验**：`apps/im-server/src/personal-actions.ts:46,50` 仅按 `content_type` 列表判定并用 `bytes.toString('utf8')`（对非法 UTF-8 字节静默替换为 `U+FFFD`）。若不明确要求 `byte_size <= 256 * 1024`、无 NUL 字节且通过 `new TextDecoder('utf-8', { fatal: true })` 严格解码，伪造 `.csv`/`.txt` 的二进制文件将绕过 `409 attachment_content_review_unavailable`。
  4. **PA 系统提示词直接矛盾**：`packages/dsh-integration/src/personal-security.ts:224` 当前仍指示 PA：`"Local paths are not uploads; no upload tool is provided."`。`design.md` 仅提及更新 `nano-product-identity`，未同步 `personal-security.ts:224`。
- **未修后果**：PA 向非主人群发送任意 `local_files` 直接 `403`；发送 `.svg`/`.zip`/超大文本时错误码错乱或崩溃；伪装后缀二进制绕过披露审阅；PA 收到自相矛盾的提示词导致拒用 `local_files`。

---

#### `R1-C2` [CRITICAL] `download_attachment` 的工具白名单/子 Agent 隔离、宿主路由与 `url`/`attachment_id` 兼容契约未闭合

- **具体位置**：`design.md` 现状分析（L15-17）、关键决策 4（L86-88）、接口与数据流（L103-138）
- **证据**：
  1. **能力过滤与子 Agent 隔离多处缺失**：
     - `packages/dsh-integration/src/agent-config.ts:125` 在 `single_thread` 模式下把 `GlobalMode` 挂在 **preset** 上，子 Agent 会自动继承其中注册的工具。必须同步更新 `packages/dsh-integration/src/capabilities.ts:82` 的 `disabled.push(...)`（补充 `'download_attachment'`）以及 `packages/personal-assistant/src/global-agent.ts:691` 的 `call.sessionId !== call.rootSessionId` 守卫，但 `design.md` 未提及这两处。
     - `packages/product-contracts/src/capabilities.ts:59`（`fixedTools`）与 `packages/dsh-integration/src/capabilities.ts:91`（Global scope-local 工具从 `tools.restrict({ allow })` 排除的列表 `['inbox', 'conversations', 'read_messages', 'search_messages', 'threads', 'delegate_worker']`）未纳入设计。现有所有通过 `apps/im-server/src/personal-agent.ts:500` 创建的 PA 以及带显式 `toolAllowlist` 的 Global Agent 均不含 `download_attachment`；不同步 `fixedTools` 和 `capabilities.ts:91` 会导致存量 PA/Global 无法获得 `download_attachment` 或触犯 DSH 本地工具掩码规则。同时，对于带显式 `toolAllowlist` 的 `single_thread` Agent（参照 `packages/dsh-integration/tests/capabilities.test.ts:24`），设计需明确 `download_attachment` 是跟随默认工具目录受 `toolAllowlist` 控制，还是与 `fixedTools` 的边界一致。
  2. **宿主路由与无 workspace 回退路径的依赖注入缺失**：
     - `apps/node/src/main.ts:530-540` 中，所有 `product.call`（包括 SingleThread 发起的 `conversations` / `read_messages` / `send_message`）均经 `globalProduct.call(call)` 执行，而非 `SingleThread`。`design.md:15` 写"注入 `GlobalAgent` / `SingleThread`"与真实架构不符；且 `GlobalAgent` 的 `Options`（`packages/personal-assistant/src/global-agent.ts:17-26`）目前既没有 `downloadAttachment` 回调也没有 `nodeHome`，需明确下载目录解析（`<workspace>/.nano-downloads/` vs `<nodeHome>/downloads/<agentId>/`）由哪一层负责注入。
  3. **`url` 与 `attachment_id` 共存契约未明（高风险破坏既有链路）**：
     - 以下四处生产逻辑强依赖 `inbox(read)` / `read_messages` / `search_messages` 投影后的附件对象继续包含 `url`：
       - `packages/personal-assistant/src/inbox.ts:774-780`（`imageSources` 从已投影的 `reads.body` 读取 `part.url!`）；
       - `packages/dsh-integration/src/global-mode.ts:119-126`（从投影结果读取 `part.url` 调 `inbox.image`）；
       - `src/IM/frontend/src/features/chat/components/conversation-tool-card.tsx:63`（Work UI 渲染 `content.url`）；
       - `apps/im-server/src/personal-actions.ts:37` 与 `packages/dsh-integration/src/personal-security.ts:224`（PA 转发原附件依赖 `/im/v1/conversations/...` URL）。
     - `design.md:109` 仅写"投影出 `≤ 8` 字符 `attachment_id` 及 `file_name`、`content_type`"，未明确规定**保留 `url` 同时新增 `attachment_id`**，以及 `id-length-contract.test.ts` 对 `attachment_id`（而非 `url`）做 `≤ 8` 校验。
  4. **`external:` 附件与 SingleThread 图片附件下载边界未定义**：
     - `apps/node/src/main.ts:439` 显示消息附件 `url` 可能是外部通道的 `external:...`；`design.md` 未说明 `download_attachment` 遇到 `external:` URL 时如何失败/提示，也未说明是否只对 `/im/v1/conversations/:id/(images|attachments)/:rid` 生效。
     - `spec.md:71-74` 要求 SingleThread 收到"文件或图片附件"均可通过短 `attachment_id` 下载，而 `design.md:110` 仅对 SingleThread **非图片**附件输出 `attachment_id`，若 SingleThread 收到图片附件需要落盘处理（如脚本分析），模型无法获知该图片的 `attachment_id`。
- **未修后果**：存量 PA/Global 无法使用 `download_attachment`；SingleThread 子 Agent 越权继承工具；若实施者移除 `url` 将直接击穿 `inbox.image`、Work UI 与 PA 转发；外部附件或 SingleThread 图片下载出现未定义失败。

---

#### `R1-C3` [CRITICAL] `send_message(local_files)` 存在本机路径泄露到过程卡片、`receipt_of` 失效、25 MiB 传输超时与 `/attachments` 幂等键缺口

- **具体位置**：`design.md` 关键决策 3（L82-84）、接口与数据流（L92-115）、风险与回退（L157）
- **证据**：
  1. **本机绝对路径泄露给群成员**：`packages/personal-assistant/src/presentation.ts:29-40`（`screenshotProcess`）目前只拦截带 `local_images`（或 `raw`）的 `send_message` 调用并做参数脱敏；其他 `send_message` 调用的 `input` 会原样进入聊天过程卡片。`design.md` 未将 `presentation.ts` 纳入修改，会导致 `send_message(local_files=["/Users/.../report.csv"])` 在群内过程卡片直接暴露发送方本机绝对路径，违反 `spec.md:56` 与 `docs/specs/gateway/routing-delivery.md:53`。
  2. **`receipt_of` 恢复对 `local_files` 必抛错，且缺少 `local_images` + `local_files` 拼接顺序与内部消息互斥约束**：
     - `packages/personal-assistant/src/global-agent.ts:1049` 硬编码 `if (!Array.isArray(body?.local_images)) throw new Error('No screenshot operation for this Agent and target')`，导致 `local_files` 不确定回执无法用 `receipt_of` 查询恢复（违反 `spec.md:57`）；`global-agent.ts:1101`（`recoverPublications`）也需同步识别 `body.local_files`。
     - `packages/dsh-integration/src/global-mode.ts:99,107` 仅在 `agent_id/message` 内部发送分支排除了 `local_images`、`receipt_of` 等字段，未排除 `local_files`。
     - `design.md:82` 未规定同一调用同时传入 `attachments`、`local_images`、`local_files` 时的确定性顺序（应明确为 `attachments → local_images → local_files`，保证互动卡片 1-based `AttachmentImage` 下标不被 `local_files` 偏移）。
  3. **25 MiB 上传/下载会被 10s/15s 硬超时切断**：
     - `apps/node/src/im-http.ts:16`（`requestIm`）固定了 `AbortSignal.timeout(10000)`（10 秒）；
     - `apps/im-server/src/server.ts:74`（Fastify 实例）固定了 `requestTimeout: 15000`（15 秒）。
     - 公网传输 `25 MiB` 文件在 1–2 MB/s 带宽下耗时 12–25s，会在客户端 10s 或服务端 15s 被强行中断，使 `apps/im-server/src/media.ts:194` 的 60s 流式超时失效；此外 `downloadAttachment` 读取二进制响应体，不能复用返回 `response.json()` 的 `requestIm`，需明确其独立超时与流式下载实现。
  4. **`media.ts` `/attachments` 路由幂等键与保留前缀缺口**：
     - `apps/im-server/src/media.ts:163-168` 仅在 `isImage`（路径以 `/images` 结尾）时要求 `Idempotency-Key`，否则自动生成 `upload:${randomUUID()}`，且仅保护了 `screenshot:` 保留前缀。复用该 handler 实现 `POST /im/v1/conversations/:conversation_id/attachments` 时，设计需明确：`isFile` 分支强制 `p.kind === 'gateway'`、`q.file === '1'`、必须提供 `Idempotency-Key`，并在非 `file=1` 路径禁止使用 `file:` 前缀。
- **未修后果**：群过程卡片泄露 Agent 本机绝对路径；`local_files` 断网重试无法用 `receipt_of` 恢复；大文件在公网环境频繁超时失败；Gateway 通用文件上传幂等键失效或被普通上传伪造冲突。

---

#### `R1-W1` [WARNING] PA 参与群接收非主人/他机 Agent 文件附件受现有输入审查（`personal-security.ts:143`）fail-closed 拦截，设计未明确边界

- **具体位置**：`design.md` 关键决策 3 & 4（L82-88）、接口与数据流（L105-115），对照 `spec.md:28, 70-74`
- **证据**：
  - `packages/personal-assistant/src/personal-assistant.ts:88-99` 对非主人发往 PA 参与群的消息执行独立输入审查；
  - `apps/im-server/src/personal-input-context.ts:32` 传入 `current: evidence(current)`，携带 `original.attachments`（`personal-agent.ts:190`）；
  - `packages/dsh-integration/src/personal-security.ts:143` 明确 fail-closed：
    `if (Array.isArray(source.current.attachments) && source.current.attachments.length) throw new Error('Input review attachment projection is unavailable');`
  - 这意味着：在 PA 参与的群里，任何同事或其他节点 Agent 发送带附件的消息都会触发 `review_unavailable`，**无法进入 PA 的 `inbox`**（PA 仅能在主人私聊、观察者会话，或经 `read_messages`/`search_messages` 看到附件）。但 `spec.md:28,72` 将"PA 通过 `inbox` 看到他人或另一台机器 Agent 发出的文件附件并下载"写进了验收场景，`design.md` 未作任何说明。
- **未修后果**：PA 跨节点接收群文件验收将必现 `review_unavailable` 失败；若实施者未有设计指导而盲目移除 `personal-security.ts:143`，会破坏 PA 防附件 prompt injection 的既有安全基线。设计需明确选择并对齐 `spec.md`：要么保持输入审查 fail-closed 边界并明确 PA 对他人群附件的获取路径（主人私聊/观察者/历史读取），要么为输入审查设计明确的附件安全投影方案。

---

#### `R1-W2` [WARNING] Work UI 遗漏 `image/*` 内联渲染风险，且 `delta-spec` 锚点与既有条款衔接不完整

- **具体位置**：`design.md` 现状分析（L18）、关键决策 1（L77）、契约层增量（L149-154）
- **证据**：
  1. **前端遗漏点**：`src/IM/frontend/src/features/chat/components/conversation-tool-card.tsx:63` 仍以 `content.type === "attachment" && text(content.content_type).startsWith("image/")` 条件直接渲染 `<img src={text(content.url)} />`；`design.md:18,77` 仅列了 `attachment-chip.tsx` 与 `interactive-card.tsx`，漏掉了 `conversation-tool-card.tsx`（另 `packages/product-contracts/src/chat.ts:102` 与 `src/IM/frontend/src/features/chat/components/message-pane.tsx:1581` 的引用摘要文案也使用 `startsWith('image/')` 建议一并收口）。
  2. **`delta-spec` 锚定与条款衔接缺口**：
     - `design.md:153` 对 `docs/specs/gateway/global-agent.md` 仅写 `MODIFIED`，未锚定具体 canonical Requirement 标题（实际应分别锚定至 `Global 主 Agent 专属产品聊天工具` 与 `Global 的话题按一等 target 独立收发，未关注的话题不进 Inbox` 等具体条目）；
     - `design.md:151` 将 `/im/v1/uploads` 放开为任意文件并把未知 MIME 归一化为 `application/octet-stream` 后，`docs/specs/im/conversations-messages.md:522`（`上传与实时资源具有累计边界` — Scenario `当前聊天草稿中的附件失败反馈` L532 "不支持的格式与无法识别的图片内容分别说明"）的适用条件发生变化（未知扩展名不再触发 415），需说明该条款如何收窄或继续仅适用于图片/特定校验；
     - PA 外发披露审核新增可审阅 UTF-8 文本类附件（`≤ 256 KiB`），应核对并说明是否同步更新 `docs/specs/gateway/personal-agent.md:202`（`披露审核实际消费待发图片`）的对应外发附件条款。
- **未修后果**：Work 视图展示含 `.svg` 的聊天工具记录时仍会尝试内联加载 `<img src="...svg">`；归并 canonical specs 时缺少明确锚点，或与 `conversations-messages.md` / `personal-agent.md` 既有场景语义冲突。

---

### Recommendations

- **`R1-R1`（可选，拆细里程碑）**：当前单个 `M1` 横跨 6 个包、前端和 specs，建议拆分为 `M1`（IM Server 通用附件/安全头/PA 披露审阅 + Web 安全收口）与 `M2`（Node 传输 + PA/ToolReferences/SingleThread + DSH 工具/审批/提示词 + 隔离实栈验证），便于先锁定服务端契约再推进 Agent 侧闭环。
- **`R1-R2`（可选，细节加固）**：`media.ts` 生成 `Content-Disposition: attachment; filename="<ascii>"; filename*=UTF-8''<utf8>` 时，应对 `<ascii>` 显式剔除 `"`、`\`、`\r`、`\n` 及控制字符防止响应头注入；Node 侧 `.nano-downloads/<attachment_id>-<sanitized_name>` 重复下载同一 `attachment_id` 时建议明确幂等覆盖或复用（原子临时文件 + rename），避免重复落盘或半截文件残留。
- **`R1-R3`（可选，评测与策略一致性）**：确认 `download_attachment` 加入 `safeTools` 后不纳入 `packages/dsh-integration/src/policy/sources.ts:44`（`hostResults`，避免被当成人工授权来源），并核对 `packages/dsh-integration/src/evaluation/runtime.ts:64` 是否需要同步放行 `download_attachment` 以免影响评测集运行。


### Author Resolutions (Round 1 → Round 2)

- **`R1-C1` [RESOLVED]**: 已在 `design.md` 补全 PA `local_files` 暂存上传至 `config.personal!.conversationId` + `pa.action.status` 预检 + 审核后 commit 复制链路；`personal-images.ts`、`personal-actions.ts`、`personal-security.ts` 全部收口至 `isRasterImageMime`（非文本非位图改为 `file: true` 不再误标 `image: true`）；`personal-actions.ts` 文本审阅增加严格 UTF-8（`TextDecoder('utf-8', { fatal: true })`）、无 NUL 与 `≤ 256 KiB` 门禁；同步更新 `personal-security.ts:224` 系统提示词。
- **`R1-C2` [RESOLVED]**: 已在 `design.md` 明确将 `download_attachment` 加入 `product-contracts/src/capabilities.ts`（`fixedTools`）、`dsh-integration/src/capabilities.ts`（子 Agent `disabled` + Global scope-local 过滤）及 `global-agent.ts:691` 根守卫，并明确 SingleThread 的 `toolAllowlist` 语义；将下载注入收口至单一入口 `GlobalAgent`（经 `apps/node/src/main.ts` 注入）；明确保留 `url` 同时新增 `≤ 8` 字符 `attachment_id`（`external:` URL 明确报错拒绝）；SingleThread 原生图片入站同时提供短 `attachment_id` 标签。
- **`R1-C3` [RESOLVED]**: 已将 `presentation.ts` 纳入 `local_files` 过程卡片路径脱敏；扩展 `global-agent.ts` `screenshotReceipt` / `recoverPublications` 支持 `local_files`；`global-mode.ts` 内部消息排除 `local_files`；明确组合顺序 `attachments → local_images → local_files`；放宽 Fastify `requestTimeout` 至 `65s`、`im-http.ts` 支持 `timeoutMs: 60000`、`downloadAttachment` 用独立二进制流式 `fetch`（60s）；明确 `media.ts` `/attachments` 的 `gateway`、`file=1`、`Idempotency-Key` 与保留 `file:` 前缀规则。
- **`R1-W1` [RESOLVED]**: 已同步更新 `spec.md` 与 `design.md`，明确保持 `personal-security.ts:143` 对 PA 参与群非主人附件的 fail-closed 输入审查边界不变，PA 通过主人私聊、观察会话或 `read_messages`/`search_messages` 获取可见附件。
- **`R1-W2` [RESOLVED]**: 已将 `conversation-tool-card.tsx`、`product-contracts/src/chat.ts`、`message-pane.tsx` 纳入 `isRasterImageMime` 收口清单；已为 `global-agent.md`、`conversations-messages.md`、`routing-delivery.md`、`personal-agent.md` 全部补齐精确 canonical Requirement 锚点及联动条款说明。
- **`R1-R1..R3` [NOTED]**: 采纳 `R1-R2`（`Content-Disposition` ASCII 清理 + 重复下载幂等覆盖）与 `R1-R3`（`download_attachment` 不入 `hostResults`、核对 `evaluation/runtime.ts`）；保持单 `M1` 一体化交付（符合单 milestone 默认约定，减少跨步交接摩擦）。


---

## Round 2

### Metadata

- **Reviewer**: Antigravity (`change-design-reviewer` subagent `c8869a00-c644-49e5-b812-47f943c309a2`)
- **Review Target**: `docs/changes/feat-786-generic-file-attachments/design.md`（对齐 `spec.md v2`）
- **review_mode**: `delta`
- **mode_reason**: 本轮改动为有界修订（关闭 Round 1 的全部 3 CRITICAL / 2 WARNING 及采纳 `R1-R2`/`R1-R3`，并同步收口 `spec.md` 中 PA 输入审查边界与 SingleThread 原生图片 `attachment_id` 说明），未改变核心目标、依赖红线或数据库结构；因此以 `delta` 模式完整核实历史问题闭环与波及面，未受影响项引用 Round 1 证据。
- **started_at**: `2026-11-25T12:09:17+09:00`
- **completed_at**: `2026-11-25T12:10:02+09:00`
- **duration**: `45s`

### Verdict

**Approved** — `0 CRITICAL` / `0 WARNING` / `0 Recommendations`

---

### Coverage 与证据

- **本轮变化与波及面核查**：
  - **PA 外发暂存、快照与披露门禁**：核对 `design.md`（L13, 20, 26, 56, 86, 94, 127, 140）与 `apps/im-server/src/messaging.ts:120-125`、`personal-actions.ts:46-50, 79, 205-215, 264-271`、`personal-images.ts:6`、`packages/personal-assistant/src/personal-assistant.ts:245-251`、`packages/dsh-integration/src/personal-security.ts:88, 224`——PA 经 `pa.action.status` 预检并暂存至 `config.personal!.conversationId`，快照清晰三分（`{ text }` 严格 UTF-8 + 无 NUL + `≤ 256 KiB`、`{ image: true }` 静态光栅位图、`{ file: true }` 不可审阅文件对非主人会话 `409`），`isRasterImageMime` 全量收口且 `personal-security.ts:224` 提示词同步更新，无残余矛盾。
  - **`download_attachment` 权限、路由、短 ID 与入站兼容**：核对 `design.md`（L11, 14-16, 21, 25, 67-68, 98-101, 123-126）与 `packages/product-contracts/src/capabilities.ts:59`、`packages/dsh-integration/src/capabilities.ts:82, 91`、`packages/personal-assistant/src/global-agent.ts:691`、`apps/node/src/main.ts:530-540`、`packages/personal-assistant/src/inbox.ts:774-780`、`single-thread.ts:398-406`——能力掩码与子 Agent 隔离完整闭合；单一入口归属 `GlobalAgent.call()`；附件对象保留 `url` 并附加 `≤ 8` 字符 `attachment_id`，同时拒绝 `external:` 原生下载；SingleThread 兼容非图附件且为原生图片附带 `attachment_id` 标签（保持 `attachmentSources` 1:1 对齐）。
  - **`send_message(local_files)` 脱敏、回执、超时与幂等**：核对 `design.md`（L12, 14, 17-19, 24, 90, 93, 95, 108-115, 181-182）与 `presentation.ts:29-40`、`global-agent.ts:1049, 1101`、`global-mode.ts:99, 107`、`im-http.ts:16`、`server.ts:74`、`media.ts:163-168`——路径脱敏、`receipt_of`/`recoverPublications`、`attachments → local_images → local_files` 固定顺序、65s/60s 传输超时、`/attachments` 的 `gateway`+`file=1`+`Idempotency-Key`+`file:` 保留前缀均已闭合。
  - **PA 输入审查安全边界与前端/delta-spec 同步**：核对 `spec.md`（L28, 70-75）、`design.md`（L28, 34, 86, 102, 166-177）与 `personal-security.ts:143`、`conversation-tool-card.tsx:63` 及 4 份 canonical specs——`spec.md` 与 `design.md` 一致保持输入审查 fail-closed 基线；Work UI `conversation-tool-card.tsx` 等全部位图判定收口至 `isRasterImageMime`；全部 8 处 canonical Requirement 锚点均逐字核实存在且场景衔接一致。
- **未受影响项**：
  - `retained_from: Round 1` — 整体包边界与架构红线合规性、数据库零迁移（`一次性部署迁移: 无`）、前端无需 `prototype.html` 的原型边界判断、`media.ts` 既有配额/限流/原子写盘复用能力与 Runbook 隔离测试栈驱动方式均未发生实质变化，沿用 Round 1 核查结论。

---

### 历史问题闭环

| 原 Issue ID | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| `R1-C1` | 补全 PA 暂存至 `config.personal!.conversationId` + `pa.action.status` 预检 + commit 复制；全量收口 `isRasterImageMime` 并三分快照（`text`/`image`/`file`）；严格 UTF-8 + 无 NUL + `≤ 256 KiB`；更新 `personal-security.ts:224` 提示词 | `design.md` L13, 20, 26, 56, 86, 94, 127, 140 完整落地上述四项，与 `messaging.ts:120-125`、`personal-actions.ts:46-50, 79, 205-215`、`personal-images.ts:6`、`personal-security.ts:88, 224` 生产接线一致 | **closed** |
| `R1-C2` | 纳入 `fixedTools`、`capabilities.ts` 子 Agent `disabled` 与 Global scope-local 列表、`global-agent.ts:691` 根守卫及 SingleThread `toolAllowlist` 语义；单入口注入 `GlobalAgent`；保留 `url` + 新增 `attachment_id` 并明确 `external:` 拒绝与 SingleThread 图片 `attachment_id` | `design.md` L11, 14-16, 21, 25, 67-68, 98-101, 123-126 与 `spec.md` L70-74 完整覆盖全部 4 项子问题，与 `main.ts:530-540`、`capabilities.ts:82,91`、`inbox.ts:774-780` 闭合 | **closed** |
| `R1-C3` | 纳入 `presentation.ts` 路径脱敏、`global-agent.ts` `receipt_of`/`recoverPublications`、`global-mode.ts` 内部消息互斥、固定拼接顺序、Fastify 65s / Node 60s 超时与独立流式下载、以及 `media.ts` `/attachments` 幂等键与 `file:` 前缀保护 | `design.md` L12, 14, 17-19, 24, 90, 93, 95, 108-115, 181-182 全部明确并互相闭环，无未决缺口 | **closed** |
| `R1-W1` | 同步 `spec.md` 与 `design.md`，保持 `personal-security.ts:143` PA 参与群非主人附件输入审查 fail-closed 边界不变，明确 PA 经主人私聊、观察会话或 `read_messages`/`search_messages` 获取附件 | `spec.md` L28, 72, 75 与 `design.md` L26, 34, 102, 177 前后一致，既保住防注入安全基线又消除验收冲突 | **closed** |
| `R1-W2` | 将 `conversation-tool-card.tsx`、`product-contracts/src/chat.ts`、`message-pane.tsx` 纳入 `isRasterImageMime`；补齐 4 份 canonical specs 的精确 Requirement 锚点及联动条款 | `design.md` L11, 28, 86, 166-177 全部补齐；经核对 `conversations-messages.md:496, 522`、`routing-delivery.md:14, 585`、`global-agent.md:330, 436`、`personal-agent.md:202` 标题逐字匹配 | **closed** |

---

### Issues

无（`0 CRITICAL` / `0 WARNING`）。

---

### Recommendations

无新增建议（Round 1 的 `R1-R2` 与 `R1-R3` 已被作者采纳并纳入 `design.md` L27, 85, 98, 101, 115, 182；`R1-R1` 保留单 M1 交付属合理工程权衡）。
