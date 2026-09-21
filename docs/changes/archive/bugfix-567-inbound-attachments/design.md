# bugfix-567: 入站附件修复 — 技术方案

对齐：[incident.md](incident.md)。Full，单 M1，无客户端界面变更。

## Changelog

- 2026-09-21 (M1): 依据本地 Codex 源码和真实请求校正 provider 契约：工具图片保留在 `function_call_output.output` 内容数组；撤销额外 user 图片消息的误判设计。
- 2026-09-20 (M1): 真实 global 验收定位到 LLM_PROXY 将 Anthropic `tool_result.content` 扁平化为文字；补入跨仓 provider 转换修复和真实链路复验，交 R3 delta 审查。
- 2026-09-19 (M1): 静态审查确认 global 会把 Feishu attachment_index 占位当作已解析图片并丢弃；补齐 global 索引解析/图文顺序。历史失败描述不得包含 data URL payload。交 R2 审查。

## 现状分析

### 涉及范围

WebRelay 仅传递描述；ImageAttachmentResolver 拥有受保护下载、大小和图片字节校验；SessionRunCoordinator 拥有单会话输入投影及 submit/steer；GlobalRunCoordinator 拥有全局 Inbox 输入；GroupContextStore 拥有群背景消息 SQLite 缓冲。Nano 通过 Anthropic Messages 请求 LLM_PROXY；代理再将请求转换为 OpenAI Chat 中间形态及 Codex Responses payload。

### 既有约束

PA 仅使用 agent.sdk；不新增内核 block 类型。图片下载沿用原 node credential + agent_id 权限检查。当前消息异常图片停止本轮，不能静默让模型回答图片问题。普通文件不自动下载/解析，不把来源引用当作授权或保证可读取的链接。

### 可复用能力

沿用 ImageAttachmentResolver 校验/下载器、单会话 transition 锁、GlobalRunCoordinator 现有普通 attachment 描述和 Inbox 消费协议。GroupContextStore 增加无损 snapshot 和按快照上界消费；不加通用队列、lease、重试后台或表结构迁移。现有 drain 接口供原调用兼容，生产投影改用 snapshot。LLM_PROXY 复用已有 Anthropic 图片转换和 Responses 结构化工具输出转换，仅补通两者之间的 `tool_result` 路径。

### 相关历史

#298 来自 feat-554 验收且旧基线已存在。全局 Agent 的附件描述与单会话图文处理已经分化。本次以 main `09cd75bd5` 为实现调查基线，不改近期 bugfix-566 飞书输出交付。

## 架构总览与关键决策

1. **共享附件分类，不扩展文件解析能力。** Gateway 内新增窄的附件语义 helper，统一 MIME 去空白/小写处理。明确 image/* 或 data:image 为图片；明确非图片 MIME 为普通文件；缺失/通用 octet-stream MIME 时按已知图片扩展名或既有 IM /images/ 入口识别，其余为普通文件。文件内容未读取是显式事实。类型判断不代替字节校验。
2. **单会话附件逐项投影，保留原附件索引。** ImageAttachmentResolver 仅接收图片，下载与大小/内容校验不变。普通文件变为 text 描述（文件名、类型、来源、内容尚未读取），不送 SDK 未支持的 attachment block。按原索引映射图片结果，Feishu kernel_input_parts 的图文顺序不得因筛掉文件发生错位。global 沿用其 attachment block，不迁移 Inbox 协议；其 kernel_input_parts 的 image attachment_index 必须按原附件索引解析成 Inbox image source，text/image 顺序保留。已有自包含 image source/image_url 沿用，避免重复追加同一图片。无 ordered parts 时按正文和附件顺序投影。普通文件描述追加且明确未读取。
3. **当前与历史失败分开。** 当前消息任何图片失败仍返回现有本轮错误；全组缓冲不消费。历史图片逐项失败只投影为未读取说明（含来源与原因），保留同条文字和其他有效图片，允许新请求正常处理。失败描述对 data URL 只保留内联来源标记，绝不把 Base64 payload 作为文字传入。该历史描述被接受仅表示失败事实已传入，不声称图片内容被读取；不引入自动重试，用户重发/查历史遵循既有入口。全局模式原有失败图片可重读语义保留。
4. **接收成功才消费缓冲。** snapshot 返回有序行及最后 row id；投影携带 buf_key 和上界。submit 返回有效接收记录或 try_steer 接受且确认 run identity 后，在同一 transition 临界区消费该 buf_key 的 id <= 上界；任何准备/接收异常不消费。后来 append 的 id 更大，不受影响。不声称跨 SQLite 与内核事务的崩溃 exactly-once。
5. **群 steer 退回 FIFO 时重新取快照。** 拒绝 steer 不拥有输入，群请求不复用包含尚未消费背景的 prebuilt projection；真正出队时重建，避免其间被另一已接受输入消费的历史再次进入。非群路径保留原 prebuilt 优化。重复下载的取舍优先于重复上下文，不新增缓存/租约。
6. **仅在 Codex Responses 路径保留嵌套工具图片。** LLM_PROXY 的 Anthropic → OpenAI Chat 共享转换器也服务普通 Chat 上游，而 Chat `tool` 消息没有图片内容契约，因此默认继续抽取文字。只有 Anthropic → Codex Responses 适配显式启用结构保真：先把 `tool_result.content` 的 text/image 按序变为内部 OpenAI-shaped text/image_url blocks，再把它们按序转换为同一个 `function_call_output.output` 中的 `input_text`/`input_image`。本地 Codex 的 `ViewImageOutput`、Responses 请求模型和请求回归测试均使用这一形态，API key 与 ChatGPT OAuth 无图片表示差异。base64 与 URL 图片均覆盖；普通 Chat 和纯文本工具结果保持原字符串形态。

## 接口与数据流

- Gateway 附件 helper：`is_image_attachment(descriptor)`；普通文件/失败历史图片生成明确未读取的 text 描述。作用仅为共享类型语义与投影，不持有网络/存储状态。
- GroupContextStore：`snapshot_with_metadata(buf_key)` 返回带 row id 的行；`consume_through(buf_key, row_id)` 删除该 key 已接受快照范围。现有 append 不变，利用 SQLite 自增 id，无迁移。
- `_MessagePartsProjection` 增加默认空的缓冲消费 receipt；_build_message_parts 只准备输入，成功 admission 后消费。正常群 snapshot、current 失败、submit 异常、steer 成功、steer 退回 FIFO 均有公开 seam 测试。
- 图片逐项解析与索引映射由 SessionRunCoordinator 的输入投影负责；resolver 保持图片职责。不在渠道层偷放文件下载，避免绕过 Agent 身份。
- LLM_PROXY 的 Anthropic → Codex 调用显式要求共享 Anthropic → OpenAI-shaped 边界保留嵌套 image source；OpenAI Chat → Codex Responses 边界把有序文字和图片写入同一个 `function_call_output.output` 内容数组。普通 OpenAI Chat 调用不启用该内部结构，Nano 不感知 provider 专用 payload。

## 契约层增量

[specs/gateway/relay-protocol.md](specs/gateway/relay-protocol.md) → `docs/specs/gateway/relay-protocol.md`。global 基本普通文件契约已有，保留其图片重读/持久消费语义，无需改 global-agent canonical。

## 风险与回退

- MIME 缺失/通用类型识别可能影响旧描述：用 data URL、已有图片 URL 和缺失 MIME 样例保护；未知文件不猜测为损坏图片。
- Feishu 索引、排队、steer 与 buffer 交叉：保留真实 SDK seam 输入断言，更新旧调用次数断言为用户输入不重复。
- 普通文件不会自动被读取，描述明确这一限制且不嵌入认证信息。
- 回退为分别 revert Nano 与 LLM_PROXY 的本 unit 代码；无数据库迁移。只回退任一侧都会重新暴露对应附件或 provider 图像缺口。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Gateway | `./scripts/e2e-down.sh --wt "$PWD"` | `./scripts/e2e-up.sh --wt "$PWD"` | source `.e2e-ports.env` 后访问 `$IM_URL/openapi.json`，确认 Gateway 注册 |

**Review 驱动方式**：端到端真栈；不改客户端，使用 Web IM 客户端同一登录、上传、聊天、消息查询 HTTP API。运行配置、数据、端口、node 和 workspace 按 worktree-runtime 隔离；用仓库默认真实 LLM 代理，若默认模型无视觉能力，仅在隔离配置选择现有视觉模型。不得用 fake LLM 替代验收。

**验收前置**：本机 `.venv` 依赖、在独立端口运行本 unit 的 LLM_PROXY worktree（复用本机凭据但不提交或输出凭据）；隔离 Gateway 配置只指向该代理。default config 提供测试 Agent，按需在隔离副本配置 single_thread 与 global。停止和端口释放由服务创建者确认。产品 reviewer 独立观察 TXT+文字、混合图片+文件、群历史文件/失败图片、新请求与当前坏图片错误/随后恢复；global 混合图片必须由真实模型正确识别。权限与超大图片沿用自动化保护并核对覆盖。无法访问真实代理时记录具体 blocker，不以单测签产品通过。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-fix | 附件投影、消费及 provider 图像保真修复 | 无 | 串行 | Nano Gateway 附件/两个 coordinator/group store；LLM_PROXY Anthropic tool_result 转换；相关 tests；delta | [reviewer] incident 的文件、混合、群历史、当前坏图片旅程与恢复在真实 Nano → LLM_PROXY → Codex 入口成立。[worker] 类型参数化、索引保真、当前/历史错误、拒绝提交保留、后到消息、steer/FIFO 不重复、global 基本类型及 base64/URL 嵌套工具图片转换回归通过；普通 Chat 与纯文本工具结果保持字符串，图片校验和成员保护原测试仍通过。 |
