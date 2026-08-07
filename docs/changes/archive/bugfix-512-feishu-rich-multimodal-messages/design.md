# bugfix-512: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `25dc9c818400ab66c99650316610b73ca5d2060f` (`origin/main` after final sync)
- Head: 本 unit 的未提交工作树，随后以本 unit commit 固化。
- Commits: 实现前无本 unit commit。
- Included dirty files: Feishu client/adapter、Gateway 图片解析与 shadow sync、Web IM 图片预览样式及对应测试。
- 受影响模块：`personal_assistant.channels.feishu`、`personal_assistant.gateway`、`IM/frontend`。

## 最终结构

### 组件与职责

- `FeishuClient` 负责飞书 provider wire：将 Agent Markdown 封装成 Post `md` 节点；识别 text/Post/image 入站结构；上传出站 Markdown 图片；按消息资源 API 下载入站图片。
- `FeishuMessageEvent.content_parts` 保存 provider 原始的 text/image 顺序；`text` 是内部 IM 展示投影，`image_keys` 是去重后的资源集合。
- `FeishuAdapter` 并行下载最多五张入站图片并生成共享 attachment；`kernel_input_parts` 只保存 text 与 attachment index，不复制二进制内容。下载失败或超限会留下稳定失败类型，不会伪装成空白用户输入。
- `IMShadowConversationSync` 把展示正文与 attachments 写入影子消息；find-or-create 和 reply context 不复制大体积入站图片元数据，recovery 所需的 canonical inbound 仍完整保留。
- `GroupContextStore` 除正文和发送者外，只持久化重建模型输入所需的 attachment / part projection，使未 @ 的群图片能在后续触发时进入模型上下文。
- `SessionRunCoordinator` 解析当前消息与群背景 attachment 后按 `kernel_input_parts` 重建 Kernel 多模态输入；没有有序元数据的既有通道仍使用“正文后追加图片”的兼容路径。飞书出站网络工作移到 asyncio loop 之外。
- Web IM 继续复用既有 attachment renderer，仅把收到的图片预览从固定小图裁剪改为气泡内最大 320px、保持原比例的预览。

### 调用链与数据流

#### Agent 回复到飞书

1. Agent 产生 Markdown 文本。
2. `FeishuClient.send_message()` 在代码段之外查找 Markdown 图片；同一来源只下载/上传一次，最多处理五个来源。data URL 或公共 HTTP(S) 图片经体积、签名和网络地址校验后上传为飞书 `image_key`。
3. 完整 Markdown 作为 Post 的 `md` 节点发送，飞书客户端负责渲染粗体、列表、链接、代码和已上传图片。

#### 飞书消息进入内部 IM 与 Kernel

1. Feishu event/history item 按 `message_type` 解析为有序 `FeishuContentPart`：text 保留段落与样式投影，image 保留 `image_key`。
2. Post 的展示正文在图片原位置投影 `[图片]`；standalone image 的展示正文为空。
3. adapter 并行下载每个可用图片资源，在读取超过 5 MiB 前停止，生成 data URL attachment，并记录 `image_key → attachment_index`；失败类型随入站消息继续进入统一预处理失败路径。
4. shadow sync 写入展示正文和 attachments：Web IM 直接预览图片。
5. run coordinator 校验/规范化 attachment data URL，再按 `kernel_input_parts` 构建 text/image parts；Post 保留交错顺序，standalone image 不人为增加 text part。

### 状态、数据与兼容性

- 既有纯 text 消息仍产生单一 text part；既有非 Feishu 通道不提供 `kernel_input_parts` 时继续走原 attachment 追加逻辑。
- 影子会话持久化的是展示正文与 attachment；Kernel transcript 持久化的是模型实际收到的有序多模态 parts，两者不共享占位符语义。
- 群聊历史把 image-only 消息视为有效背景消息；群背景 buffer 同时保存有序多模态 projection，不再因正文为空或仅缓冲 text 而丢图。
- 当前只接纳最多五张入站图片，与 Gateway 现有图片数量上限保持一致。
- 5 MiB 入站图片上限在飞书资源流读取时和 Kernel 解析时各自执行；无论是否配置 IM fetcher，self-contained data URL 都会验证体积和图片结构。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| Agent Markdown 发送为 Post `md`，不在本地自行渲染为纯文本 | 飞书 text 消息不渲染 Markdown；Post 是平台原生富文本载体。 | `src/personal_assistant/channels/feishu/client.py` |
| 同一个 provider payload保留一份有序内容部件，再派生展示投影和模型投影 | 用户明确要求内部 IM 与 LLM 输入分开；一份扁平 text 无法同时满足两种语义。 | `client.py`、`adapter.py`、`session_run_coordinator.py` |
| attachment 使用 data URL 跨 Gateway→IM 传递 | 资源下载发生在持有飞书凭据的 adapter；IM 不调用飞书，也不新增跨包依赖。 | `adapter.py`、`shadow_sync.py`、`image_attachments.py` |
| standalone image 的 IM 正文为空，Post 图片才有 `[图片]` 展示标记 | 独立图片直接预览最自然；Post 需要占位符保留图片在长文本中的位置。 | `client.py`、`shadow_sync.py` |
| LLM parts 不含 `[图片]`，严格按 provider 顺序重建 | 占位符是 UI 投影，不是模型内容；真实 image part 才能被视觉模型理解。 | `adapter.py`、`session_run_coordinator.py` |
| 出站远程图片只允许公共 HTTP(S)，并固定连接已验证的公网 IP | DNS 校验与实际连接使用同一地址，避免重绑定访问本机/内网；同时限制来源数、体积、签名和总连接时限。 | `client.py` |
| 失败图片不提交一个“空消息”给模型 | adapter 保留 `download/oversize` 类型；Gateway 在 submit 前给原飞书会话和内部 IM 返回可执行的失败说明。 | `adapter.py`、`session_run_coordinator.py`、`shadow_sync.py` |

## 失败路径、风险与回滚

- 入站图片下载、超限或结构校验失败时，本轮不提交模型，原飞书会话收到明确失败说明；内部 IM 的原用户消息保留可读正文，standalone 失败图片用 `[图片加载失败]` 避免形成不可见空消息。
- 出站 Markdown 图片不是受支持的 data URL 或公共 HTTP(S) raster 时，本轮发送按既有 channel 失败路径报告，不静默替换内容。
- Post 未知节点只保留可安全提取的文本；media/file 等非图片资源仍以附件文字标识显示，不在本 unit 扩展下载。
- data URL 会增大 canonical inbound 与群背景存储；reply context 和 find-or-create payload 不再重复它，且受最多五张和单图 5 MiB 限制。
- 群背景 SQLite 增加 `metadata_json` 列并在启动时自动迁移。回滚代码不会删除该列；旧代码会忽略额外列，因此无需数据清理。

## 与初始意图的差异

最初问题聚焦 Markdown 未渲染和 Post JSON 泄漏。用户随后要求覆盖普通消息、Post 内嵌图片、独立图片，并明确内部 IM 展示与 LLM 输入必须采用不同投影；最终实现据此扩展为完整的 Feishu 富文本与图片双向链路。Luna 视觉验证还确认：本 unit 已把图片正确送到 Kernel；视觉模型需使用支持图片的 provider 路径，该模型路由配置不属于本 unit 的代码修改。

## 验证定位

- 用户验收：2026-08-06 在专用 Feishu App、隔离 IM/Gateway 栈中查看 standalone image 与 Post embedded image 的飞书/内部 IM 成对视图后回复 “ok”。
- 自动化测试：Feishu event/history parser、Post 空白保持、Markdown Post/图片发送、代码段图片语法跳过、重复来源上传、固定公网地址、图片下载上限、adapter attachment/失败类型、shadow sync、群背景图片、Kernel 有序 parts 与 data URL resolver 的 unit tests。
- 运行证据：standalone image 的 IM `content="" + attachment`、Kernel `image`；Post 的 IM `text:[图片]:text + attachment`、Kernel `text → image → text`。Kernel session `sess_deaf7230a1a146f6` 使用 `codexOAuth:gpt-5.6-luna` 经 `openai_compat` 成功识别同一图片内容。

## Canonical 文档影响

- Delta-spec：`specs/gateway/external-channels.md`、`specs/im/web-chat-ux.md`。
- 归并目标：Gateway External Channels、IM Web Chat UX current specs；对应 package spec 的 Requirement 数量与对齐标记同步更新。
