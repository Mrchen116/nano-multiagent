# Design 评审：feat-469

**结论**：Approved

本轮逐条核完现状断言、5 个决策、spec 的用户场景 / Requirement / Scenario / 澄清 / 非目标、IM delta-spec 与单一 milestone，并从生产路由正向追到真实 composer、上传边界、页面级错误反馈及消息发送路径。未发现会让 worker 走偏、让 orchestrator 派错或让 delta-spec 无法归并的阻断项；方案可以进入 `change-orchestrator`。

## 核实台账

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状：`message-pane.tsx` 是生产 Chat composer | 从浏览器路由正向追 wiring | ✓ `/chat` 与 `/chat/:conversationId` 均装配 `ChatWorkspacePage`（`src/IM/frontend/src/app/router.tsx:29-32`），页面在真实 detail 分支装配 `MessagePane`（`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:1015-1049`），不是测试专用死实现。 |
| 现状：composer 持有草稿与 pending attachment | 核真实 state 与发送快照 | ✓ `MessagePane` 本地持有 `draft` / `pending`（`message-pane.tsx:171-175`），`commit()` 将 pending 快照交给 `onSend` 并仅在成功后清理已发送项（`message-pane.tsx:234-256`）。 |
| 现状：`handleAdd(files)` 顺序上传、成功逐项入 chip | 核实际控制流 | ✓ `for...of` 内逐个 `await uploadAttachment(file)`，成功后 append pending，失败项丢弃但继续循环（`message-pane.tsx:311-323`）；chip strip 直接渲染 pending（`message-pane.tsx:541-556`）。 |
| 现状：textarea 无 paste 入口 | 全前端搜索 + 核真实 JSX | ✓ 生产 textarea 只有 `onChange`、`onKeyDown`、`onScroll`（`message-pane.tsx:587-601`）；`src/IM/frontend/src` 中无 `onPaste` / `clipboardData` / `navigator.clipboard.read`。 |
| 现状：`use-attachment-upload.ts` 是单次附件上传网络边界 | 追调用与 HTTP 实现 | ✓ `MessagePane` 默认注入 `uploadOneAttachment`（`message-pane.tsx:6-8,169-170`），该函数是唯一直接调用 authenticated `/im/v1/uploads` 的前端附件 helper（`use-attachment-upload.ts:25-38`）。 |
| 现状：上传错误统一映射 415 / 413 / 其他 | 核错误分支 | ✓ 415→`unsupportedType`、413→`tooLarge`、其他非 2xx→`network`（`use-attachment-upload.ts:10-22,32-36`）。 |
| 现状：`AttachmentDropzone` 只转交文件、不拥有上传或 pending | 核组件 state / props | ✓ 该组件只持 `dragging`，drop 时 `onAdd(Array.from(files))`（`attachment-dropzone.tsx:3-8,17-18,38-45`）；无上传或附件状态。 |
| 现状：Chat workspace 是生产组装入口且已有发送失败 toast owner | 追 mutation→state→UI | ✓ `sendMutation.onError` 写入页面级 `sendError`（`chat-workspace-page.tsx:737-761`），页面顶部渲染可关闭的错误浮层（`chat-workspace-page.tsx:975-990`），并把发送状态 / 错误传入生产 `MessagePane`（`chat-workspace-page.tsx:1017-1030`）。 |
| 现状：现有测试覆盖附件 pending / 删除 / 发送冻结 | 核对应测试而非只看文件名 | ✓ drop→chip→send 在 `message-pane.test.tsx:1114-1150`，删除在 `1152-1180`，异步发送期间冻结增删在 `615-648`。 |
| 现状：workspace integration 覆盖上传→消息 payload | 核真实组装测试 | ✓ integration 从 drop 触发 `/uploads`，见 chip，再 POST message 并断言完整 attachments payload（`chat-workspace.integration.test.tsx:1142-1185`）。 |
| 现状：两份目标测试基线 120 tests passed | 现场运行设计给出的命令 | ✓ 2026-07-17 现场执行 `npm test -- src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace.integration.test.tsx`：2 files、120 tests 全绿（80 + 40）；有既存 React `act(...)` stderr 警告，但无失败。 |
| 约束：只改 IM 前端，不触碰三包与依赖方向 | 对顶点架构与范围交叉核对 | ✓ 顶点约束规定 IM 不 import agent、三产品互不 import（`SPEC.md:147-168`）；M1 文件范围只在 `src/IM/frontend`、i18n 与 unit 证据目录（`design.md:211-213`）。 |
| 约束：测试扩既有行为 owner，并做真浏览器验收 | 核 testing guide | ✓ guide 要求已有覆盖时优先扩展，并把真浏览器 / 真服务归为 e2e（`docs/TESTING_GUIDE.md:16-22,31-47`）；design 同时给出 Vitest regression 与 Chromium 真入口证据轨（`design.md:203-205,213`）。 |
| 约束：继续经 authenticated `/im/v1/uploads`，不绕类型 / 大小限制 | 追前后端真实边界 | ✓ helper 经 `authFetch` 发原始 File（`use-attachment-upload.ts:7,25-31`）；后端路由需要 `current_user`，先校验 MIME 白名单，再限制 10 MiB（`src/IM/api/routes/messages.py:269-303`）。 |
| 约束：事件式 paste，不依赖主动 Clipboard API | 核 Web Clipboard 标准与设计接口 | ✓ Clipboard Event API 明确通过 paste handler 的 `clipboardData` 同步访问事件携带数据；design 的 `handlePaste(ClipboardEvent)` 只读该对象（`design.md:60-66,104-108`），没有权限/API 旁路。参考：[W3C Clipboard API and events](https://www.w3.org/TR/clipboard-apis/#clipboard-event-api)。 |
| 约束：`dist/` 不提交，worker build + 真入口验收 | 核 repo 约定与 milestone | ✓ AGENTS.md 明确 `dist/` 是构建产物；M1 worker 退出包含 `npm run build` 和 Chromium evidence（`design.md:24,192,203-205,213`）。 |
| 可复用：drop 与 paste 可汇聚同一 `handleAdd` | 删除重复通路测试 | ✓ dropzone 已只需一个 `onAdd(files)`（`attachment-dropzone.tsx:38-45`），`handleAdd` 已集中顺序 / partial-success / pending append（`message-pane.tsx:311-323`）；paste 只需产出 `File[]`。 |
| 可复用：`uploadOneAttachment` + typed error | 核消费者需要的能力 | ✓ helper 同时提供上传结果和 `AttachmentUploadError.code`（`use-attachment-upload.ts:10-38`），足以支撑统一 server validation 与本地化映射，无需新上传 abstraction。 |
| 可复用：`AttachmentChip` | 核图片 / 删除能力 | ✓ image MIME 使用 64×64 preview，存在 `onRemove` 时呈现删除按钮（`attachment-chip.tsx:11-33`；`global.css:3305-3317`）。 |
| 可复用：页面顶部错误反馈面 | 核既有 owner 与语义兼容 | ✓ send / fork 的操作失败已由 `ChatWorkspacePage` state 驱动同一顶部危险色浮层（`chat-workspace-page.tsx:266,737-761,779-790,975-990`）；扩充为带 kind 的 composer error 不引入第二个子组件通知 owner。 |
| 历史：feat-340 M8 建立上传 / dropzone / chip / pending owner | 核归档 tasks/progress | ✓ M8 明确建立 `/uploads`、attachments 原子组件、`MessagePane` pending 与 workspace payload（`docs/changes/archive/feat-340-agent-native-im/M8-feature-attachments/tasks.md:5-17,45-73`）；progress 记录顺序上传和失败留给上游 toast（`.../progress.md:34-46`）。 |
| 历史：canonical Web Chat UX 尚无 paste，最窄 target 是该 area | 核入口索引与 area 内容 | ✓ IM spec 把输入 / 交互归到 `web-chat-ux.md`（`docs/specs/im/spec.md:19-35`）；现有 8 个 requirement 覆盖滚动、输入高度、消息菜单、蒸馏等但无 paste（`docs/specs/im/web-chat-ux.md:12-169`）。 |
| 历史：issue 的 picker 现状与 main 不一致，本 unit 不补 picker | 核 issue 原文与当前源码 | ✓ issue #202 确实提到 picker；当前 `src/IM/frontend/src` 无 `type="file"` / `showOpenFilePicker`，生产只装配 dropzone（`message-pane.tsx:541-617`）。design 将其识别为 drift 且遵守非目标。 |
| 判定：本 unit 不需要新附件模块 / 新公共抽象 | 对新增对象做删除测试 | ✓ 方案只新增组件内部 paste handler 与一个页面回调 seam，复用现有 ingestion / uploader / chip / toast owner（`design.md:43-56,104-111`）；没有新模块、factory、protocol 或跨包 interface。 |

### 关键决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 决策 1：只消费 paste 事件同步 `clipboardData` | 拍死 / spec 驱动 / 环境约束 | ✓ 选择、拒绝项和 fallback 风险均拍死（`design.md:60-66`）；直接覆盖 spec 的桌面快捷键场景与“不得主动读取 / 请求权限”非目标（`spec.md:54-60,98-101`），并符合 Clipboard Event API 的同步事件模型。 |
| 决策 2：含图片时附件语义独占；无图片放行默认行为 | 核混合 / 纯文本 / 非图片三路 | ✓ `preventDefault()` 条件被精确锁为“至少一张可用图片”（`design.md:68-74,142-154`），同时覆盖混合表示不污染 draft（`spec.md:62-66`）与纯文本 / 非图片不阻断（`spec.md:73-85`）。 |
| 决策 3：items 保序优先，files 仅 fallback | 核歧义与重复风险 | ✓ 主路径、fallback 触发条件、`getAsFile() = null` 与去重策略均已拍死（`design.md:76-82,142-154`）；两个 worker 不会分别选择“拼接两路”与“只读 files”而产生不兼容行为。 |
| 决策 4：paste/drop 共用 `handleAdd`，顺序 + partial success + send busy 不变量 | 核真实 seam 与既有状态 | ✓ 当前 `handleAdd` 已顺序 await、逐成功 append、逐失败继续（`message-pane.tsx:311-323`）；发送时 textarea / dropzone / remove 均受 `composerBusy` 或 ref gate（`message-pane.tsx:194,542,549-553,587-606`），现有冻结测试成立（`message-pane.test.tsx:615-648`）。 |
| 决策 5：附件失败回调到 Chat workspace typed toast | 核接口闭合与 owner | ✓ caller / callee / error mapping / unknown fallback / dismiss owner 均有定义（`design.md:92-111`），生产 wiring 在 M1 范围内同时修改 `MessagePane` 与 `ChatWorkspacePage`（`design.md:213`）；成功项由现有逐项 append 保留（`message-pane.tsx:311-323`）。 |
| 决策间自洽 | 两两扫数据流与依赖方向 | ✓ D1/D3 决定“如何取 File[]”，D2 决定“何时接管 paste”，D4 决定“如何进入 pending”，D5 决定“失败如何出站”；总览和 sequence 正好串成单向链（`design.md:41-56,113-154`），无反向依赖或两套 owner。 |

### spec 约束

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 用户场景 1：截图 paste→pending，可删、可加文字发送 | 核 design 落点 | ✓ D2/D4 + `AttachmentChip` / `onSend` 数据流覆盖（`design.md:68-90,121-140`）；M1-E1 明确验 chip、删除、发送（`design.md:213`）。 |
| 用户场景 2：纯文本原样；图片+文本只取图片 | 核默认行为边界 | ✓ D2 与流程图明确“有图 preventDefault、无图 native”（`design.md:68-82,142-154`）；M1-E2/E4 覆盖两侧（`design.md:213`）。 |
| 用户场景 3：多图保序；单项失败保留成功并反馈 | 核顺序 / partial success / retry 可达 | ✓ D3 保留 clipboard order，D4 顺序 append，D5 每项报错且不回滚成功项（`design.md:76-98`）；用户仍可再次 paste 重试，未新增专用 retry 控件。 |
| Requirement 1：聊天输入框支持图片进入待发附件 | 覆盖 / 不冲突 | ✓ D1-D4 完整覆盖；方案落点就是生产 textarea + existing ingestion（`design.md:60-90,104-108`）。 |
| Scenario：单张截图 | 可观察退出 | ✓ M1-E1 明确 chip 可见、可删、可发送；原型 `#composer-pasted-images` 为 must-match（`design.md:172-176,213`）。 |
| Scenario：图片同时有文本 / 网页表示 | 可观察退出 | ✓ D2 明确阻止默认文本插入；M1-E2 和原型 `#composer-mixed` 均要求 draft 不新增 URL/alt（`design.md:68-74,174-175,213`）。 |
| Scenario：一次多图 | 可观察退出 | ✓ D3+D4 保留 items/files 与上传 append 顺序；M1-E3 明确所有合规图片顺序呈现（`design.md:76-90,213`）。 |
| Requirement 2：普通文本粘贴不变 | 覆盖 / 不冲突 | ✓ handler 在最终无图片时不 `preventDefault()`（`design.md:82,107,136-153`），保住浏览器 selection / IME / undo owner（`design.md:168`）。 |
| Scenario：纯文本 | 可观察退出 | ✓ M1-E4 + worker preventDefault regression 覆盖（`design.md:190,213`）。 |
| Scenario：仅非图片文件 | 可观察退出 | ✓ filter 只取 `kind=file && type=image/*`，最终无图片则 native（`design.md:78-82,146-153`）；M1-E5 覆盖（`design.md:213`）。 |
| Requirement 3：共享限制与失败反馈 | 覆盖 / 不冲突 | ✓ 所有图片仍走 `uploadOneAttachment`→同一后端白名单 / 10 MiB 限制，D5 补齐当前被吞的失败反馈（`design.md:84-111`；`messages.py:269-303`）。 |
| Scenario：合规图片与其他入口相同待发态 | 可观察退出 | ✓ 两个入口都调用同一 `handleAdd`，都写同一 pending，并由同一 `AttachmentChip` 渲染（`design.md:43-53,84-90`）；M1-E6 覆盖（`design.md:213`）。 |
| Scenario：拒绝 / 上传失败，成功项保留 | 可观察退出 | ✓ D5 callback→typed toast，D4 每项独立 try/catch 保留先前成功（`design.md:92-111,121-135`）；M1-E7 覆盖（`design.md:213`）。 |
| 澄清：用户不介入、不提问 | 是否被 design 留成悬案 | ✓ design 无 TBD / 待用户决定；5 个关键决策、单 M1、runbook 均已自主拍死。 |
| 在范围：桌面 textarea 聚焦 Ctrl/Cmd+V | 范围是否收敛 | ✓ 接口限定 `ClipboardEvent<HTMLTextAreaElement>`，真实浏览器验收限定 desktop Chromium `/chat/:conversationId`（`design.md:104-108,203-205`）。 |
| 在范围：混合判定、多图顺序、现有附件一致性、文本/非图片回归 | 是否全投影到退出标准 | ✓ 分别投影 M1-E2/E3/E6/E4/E5，未藏进不可验散文（`design.md:213`）。 |
| 非目标：主动读取剪贴板 / 新权限 | 是否越界 | ✓ D1 明确拒绝 Clipboard API，只消费事件（`design.md:60-66`）。 |
| 非目标：新增或重做文件选择按钮 | 是否越界 | ✓ 现状已指出 main 无 picker 且“不补建该入口”（`design.md:37`）；M1 范围无 picker/component 视觉改造。 |
| 非目标：支持非图片剪贴板文件 | 是否越界 | ✓ D3 只过滤 `image/*`，M1-E5 要求非图片不入 pending（`design.md:78-82,213`）。 |
| 非目标：改变服务端格式 / 大小 / 消息附件协议 | 是否越界 | ✓ delta 与 milestone 均只触及 IM 前端；上传 / message server 文件不在范围（`design.md:180-185,211-213`）。 |
| 非目标：重做 composer 布局 | 是否越界 | ✓ 架构总览只在既有 textarea / chip / toast 中接线；原型明确消息列表与侧栏 out-of-scope、精确视觉 may-adapt（`design.md:161-178`）。 |

### delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 包级 delta 声明 | 核受影响包与 canonical target | ✓ 只有浏览器 Web IM 对外行为变化，因此仅 IM 有 delta；kernel / gateway / cli 显式 `no spec delta`（`design.md:180-185`）。target `docs/specs/im/web-chat-ux.md` 是输入交互的最窄 canonical area（`docs/specs/im/spec.md:23-35`）。 |
| ADDED Requirement：聊天输入框支持剪贴板图片 | 核 ADDED/MODIFIED 用法 | ✓ canonical 当前无 paste requirement，不是替换既有行为，使用 ADDED 正确（`docs/specs/im/web-chat-ux.md:12-169`；delta `specs/im/web-chat-ux.md:3-5`）。 |
| Delta Scenario：图片进入待发区 | 核 THEN 可观察与首文档覆盖 | ✓ THEN 只写顺序、可删除、可发送的 UI 结果，无内部函数 / 类名（delta `specs/im/web-chat-ux.md:7-10`）；涵盖 spec 单图 + 多图两条 Scenario。 |
| Delta Scenario：图片带文本 / 网页表示 | 核 THEN 可观察 | ✓ 图片显示且 draft 不插入伴随内容（delta `specs/im/web-chat-ux.md:12-15`），忠实覆盖 spec 混合场景。 |
| Delta Scenario：纯文本或非图片保持默认 | 核 THEN 可观察 | ✓ 合并两个“无图片”场景但未丢语义：浏览器原粘贴 + pending 不新增（delta `specs/im/web-chat-ux.md:17-20`）。 |
| Delta Scenario：拒绝 / 上传失败 | 核 THEN 可观察与 partial success | ✓ 明确反馈、失败不入 pending、成功保留（delta `specs/im/web-chat-ux.md:22-24`），未出现 HTTP 状态码或 callback 等实现红线。 |

### Milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| feat-469-M1 `clipboard-image-ingress` | 核拆分理由 / 范围 / 两轨退出 | ✓ 默认单 M1，改动集中同一 composer + page wiring，无横切拆分或并行文件冲突（`design.md:207-213`）。reviewer 轨逐项覆盖 spec 7 个 Scenario 与 prototype must-match；worker 轨覆盖 items/files、preventDefault、partial success、typed error、payload、目标 Vitest、build 与真 Chromium evidence，均可验。 |

## 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | paste filter / ingestion / toast 三段责任 | ✓ 走完无存活发现。paste 事件与浏览器数据形态留在 `MessagePane`；上传与 pending 继续由既有 composer ingestion 持有；页面级操作错误继续由 `ChatWorkspacePage` 呈现。组合后依赖仍是 page→component→attachment helper，没有 IM→Gateway/agent 或内层反向依赖（`design.md:41-56,100-111`）。 |
| 该不该存在 | `handlePaste`、`onAttachmentUploadError`，以及是否需要新 clipboard uploader | ✓ 走完无存活发现。删除 `handlePaste` 就没有产品入口；删除错误 callback 就只能继续静默或把页面 toast owner复制进子组件。方案没有新增 clipboard service / hook / factory，避免为单一同步事件预造抽象（`design.md:60-66,84-98`）。 |
| 深还是浅 | 复用 `handleAdd` / `uploadOneAttachment` / `AttachmentChip` 与现有 toast | ✓ 走完无存活发现。既有 seam 已隐藏 authenticated fetch、typed server error、顺序上传、partial success、pending 与发送快照；新增 handler 只做剪贴板特有筛选，接口显著小于被隐藏的完整附件链（`use-attachment-upload.ts:25-38`; `message-pane.tsx:234-256,311-323`）。 |
| 治本还是补丁 | issue #202 无 paste 入口 + 当前失败静默 | ✓ 走完无存活发现。方案从生产 textarea 接入 paste，并把历史遗留的 `catch { drop }` 接到真实页面反馈 owner；不是绕过 server validation、模拟 chip 或只补测试桩（`message-pane.tsx:311-323`; `design.md:56,92-111,191`）。 |

## Issues

- 无。

## Recommendations

- M1 worker 写测试前应留意两个目标文件当前分别为 2136 / 1721 行，而 `docs/TESTING_GUIDE.md:69-75` 把现存 2000+ 行文件称为反面教材。此项不阻断 design：已有附件行为确实在这两个文件中；但 worker 应优先把附件相关旧断言与新增 paste 断言按行为拆到语义命名文件（如 `message-pane-attachments.test.tsx`），或在 tasks 的测试策略里明确说明为何继续扩现有文件，避免机械放大维护债。
- `design.md:39` 的“未命中 `codebase-design`，不调整 interface seam / 职责边界”表述可更精确：决策 5 确实新增了 `MessagePane→ChatWorkspacePage` 错误回调 seam，并明确了错误 owner。独立删除测试确认该 seam 足够小且归属合理，所以不构成实施阻断；后续作者可把这句话改为“未新增模块或跨包公共 seam；局部组件回调按既有页面错误 owner 收口”。
