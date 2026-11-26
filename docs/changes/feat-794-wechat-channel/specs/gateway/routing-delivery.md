# gateway/routing-delivery.md (delta for feat-794)

## MODIFIED Requirements

### Requirement: 当前会话的 Agent 图片与文件回复具有统一交付语义

Gateway MUST 将普通 assistant 回复中的可交付图片与文字按原顺序交付到当前聊天；Agent 向已有原生 IM 聊天或已绑定的外部私聊通道（如飞书、个人微信）以自身身份显式调用 `send_message` 时，可在 `local_images` 中传入绝对路径发送本地光栅图片（单图最多 10 MiB，静态图片且宽高各不超过 4096 像素）；向已有原生 IM 聊天调用 `send_message` 时，亦可在 `local_files` 中传入绝对路径发送通用本地文件（单文件最多 25 MiB、光栅图片最多 10 MiB，拒绝 0 字节文件），作为受保护附件随一条消息发送。卡片可依附件顺序引用同条消息的图片。支持本地 PNG/JPEG/WebP 产物和既有可获取受控图片。Agent 可直接引用获准读取并向目标发送的本地文件，不要求位于固定交付目录；附件引用本身不授予额外权限。显式发送沿用工具权限判断（含私有证据人工审批保护与公开过程卡片本机路径脱敏），普通图片回复执行同等发送权限判断。普通回复每气泡最多五个不同来源，显式发送中的已有附件、`local_images` 与 `local_files` 按 `attachments → local_images → local_files` 顺序合计最多五个位置，重复位置也计入上限，同组内重复路径不重复上传，均支持 `receipt_of` 回执查询恢复。

#### Scenario: 本地产物跨机器查看
- **WHEN** 用户请求 Agent 展示其通过工具准备的本地图片
- **THEN** 原聊天可以直接查看图片和说明，无需用户访问运行机器。

#### Scenario: 图片语法不绕过权限
- **WHEN** 回复引用无权读取或未准备为可交付产物的文件
- **THEN** 图片不发送，失败反馈给 Agent 按现有权限规则处理，用户正文不出现内部失败占位。

#### Scenario: 图文投递保持入口路由
- **WHEN** 飞书或个人微信触发的 run 产生中间或最终图文回复（含显式 `send_message(local_images)`）
- **THEN** 原外部聊天和内部影子会话收到等价图文内容
- **WHEN** 内部 IM 影子会话触发同类回复
- **THEN** 只在内部 IM 显示，不回写飞书或个人微信。

#### Scenario: IM 离线不阻塞飞书或微信图片
- **GIVEN** 飞书或个人微信通道可用、中心 IM 暂不可用
- **WHEN** 普通或全局 Agent 在外部会话产生图片回复，随后 IM 恢复
- **THEN** 外部聊天先收到图文，节点本机暂存已验权图片并在 IM 恢复后幂等补齐相同图片的历史，不重复创建气泡。

#### Scenario: 局部图片失败
- **WHEN** 图片不可读、格式不支持、超限或上传失败
- **THEN** 该候选在发布前被拦截，具体失败对象、原因和修正方向返回 Agent；Agent 可修正后重新交付，用户不会收到内部错误占位或声称全部图片已发出的不完整成品。

#### Scenario: 普通文本和示例保持原语义
- **WHEN** Agent 回复纯文字或代码中的 Markdown 图片示例
- **THEN** 保持原有文字，示例不触发文件读取或图片发送。

#### Scenario: Agent 向已有聊天显式发送图片
- **GIVEN** Agent 已有可投递的原生 IM 聊天目标或外部私聊目标
- **WHEN** Agent 通过 `send_message` 发送其准备的本地图片及说明
- **THEN** 目标会话与有读取资格的原生/影子会话成员可直接查看图片，刷新后仍可回看；有效公司成员可读公开群图片，私密群/私聊非成员与其他无资格者持同一 URL 仍不能读取
- **AND** 同次投递重试复用原快照与上传回执，已知过时的群候选不准备外发资源；资源准备后提交前再次复核，过时草稿不公开，已准备资源不冒充已送达消息。

#### Scenario: 卡片和附件对应同一批图片
- **WHEN** Agent 显式提交本地图片及引用这些图片的解释卡片
- **THEN** 图片以指定顺序随消息交付，重复引用同一来源时只准备一次，公开正文和发送过程不披露本地路径

#### Scenario: PA 显式发送图片
- **WHEN** PA 向可发言的原生 IM 群发送本地图片
- **THEN** 现有外发审核覆盖实际图片和受众，待审核图片合计最多 20 MiB。审核能看到卡片引用的实际图片位置及公开群的非成员可读范围。审核通过且发送前的受众复核一致时才向目标群交付
- **WHEN** PA 向已绑定的主人原生私聊或主人飞书/微信外部单聊发送本地图片
- **THEN** 按本人私聊权限直接投递至目标单聊并同步影子会话附件

#### Scenario: 提交状态未知
- **WHEN** Agent 在发图回执丢失后以相同目标和 `receipt_of` 查询原操作
- **THEN** 已确认时返回原消息回执，未确认时保留真实状态，查询不重复发布消息

#### Scenario: 发送本地图片需要人工确认
- **WHEN** 本地图片发送的权限判定要求转人工且当前权限卡无法提供私有的待发证据
- **THEN** Agent 得到未发送状态和原因，群友不会收到可在不知晓待发对象时放行的权限卡或包含本地路径的通知

### Requirement: Agent 可通过短标识下载受保护会话附件

产品根主 Agent 可使用 `download_attachment(attachment_id)`（`attachment_id` 为 `<= 8` 字符的 `a_xxxxxx` 引用，来自 `inbox`、`read_messages`、`search_messages` 或 SingleThread 入站消息）将当前仍有权读取的原生 Nano IM 附件，或本节点已验权入站持久化的当前 Agent 外部通道附件（如微信入站通用文件、视频或未转写语音音频）下载到受控本地目录（`<workspace>/.nano-downloads/<attachment_id>-<sanitized_name>`，无 workspace 时落 `<nodeHome>/downloads/<agentId>/`），返回 `{ attachment_id, local_path, file_name, content_type, byte_size }`。

#### Scenario: 跨节点文件下载、本机外部通道入站附件落盘、文件名保留与幂等覆写
- **WHEN** 节点 B 的根主 Agent 调用 `download_attachment(attachment_id)` 下载同一会话中节点 A 发送的原生通用文件或光栅图片，或本节点根主 Agent 下载本机外部通道已验权入站的附件
- **THEN** 原生 IM 附件由宿主持当前 Gateway 凭据向 IM Server 发起实时鉴权流式下载（上限 25 MiB、超时 60 秒），本机已验权外部通道附件直接从当前 Agent 归属的受保护外部存储读取（即使中心 IM 暂不可达亦可用），均保留清理后的原始文件名与扩展名（无扩展名时按 MIME 兜底），经临时文件原子重命名落盘并逐字节还原原文件；重复下载同一 `attachment_id` 幂等覆盖同一路径，不留半截临时文件。
- **AND** 对不属于当前 Agent 的 `external:` 标识、任意外部网页 URL 或已失权会话附件一律拒绝下载并清理临时文件；下载路径始终受限于受控目录，防止路径穿越。

#### Scenario: SingleThread 接收非图与图片附件不崩溃
- **WHEN** SingleThread Agent 收到含通用非图附件（如 `.csv`、`.zip`、`.svg`、`.pdf`、`.wav`、`.mp4`）或光栅图片的入站消息
- **THEN** 非光栅附件渲染为带文件名、MIME 与短 `attachment_id` 的文本条目（当 `download_attachment` 在当前工具集可用时附带调用提示），不再因非图片 MIME 抛错中断；原生光栅图片与已验权外部通道光栅图片保留内联多模态图片块并在前附带 `[Image attachment_id=<a_xxxxxx> (<name>)]` 标签。

### Requirement: PA 为每条真人消息固定模型侧发生时间与实际入口

Gateway 对来自内置 Web IM 或外部 Channel 的真人消息，在不改变用户可见正文的前提下，为送入 Agent 的每条新 user message 固定一个稀疏 context envelope。时间优先采用 Channel 提供的消息发生时间；来源没有合法时间时，采用 Gateway 同步接受该消息时一次固定的接收时间；已知用户时区时，两者都按该消息发生时固定的用户时区呈现为带 offset 的 ISO 时间；未获得用户时区时保留明确 UTC，不猜测用户所在地。入口按该条消息实际经过的 Channel 标为 `Web IM`、`Feishu` 或 `WeChat`，不从共享 shadow conversation 推断，也不附加 Direct/Group、Bot ID、chat ID、host 或 IP。

同一消息在 group buffer、normal submit、active steer、retry 和 history replay 中复用同一个固定 envelope；本 requirement 不改变 active steer 的接受、消费、持久化、失败处理或恢复语义。群聊继续保留既有 `[sender]`；模型侧新增 context 不写入 IM message body。PA 顶层会话的 system prompt 只保留稳定 timezone，不再把 session 创建时刻称为当前时间；动态时间只随新真人 user message 追加。Heartbeat、cron、subagent 与内部通知不获得真人消息 envelope；没有选择该行为的 Coding CLI 保持既有 prompt/message semantics。

#### Scenario: 长会话中的新消息各自保留发生时间
- **GIVEN** 用户在同一 PA 会话的不同时间先后发送两条真人消息
- **WHEN** 后一条消息进入 Agent context
- **THEN** 两条消息各自携带固定的发生时间，Agent 可判断先后与时段
- **AND** system prompt 不把会话创建时刻继续表述为当前时间

#### Scenario: 来源时间优先且缺失时固定 Gateway 接收时间
- **GIVEN** 一条消息带有合法 Channel occurrence time，另一条没有合法来源时间
- **WHEN** Gateway 为两条消息建立 model context
- **THEN** 第一条采用 Channel occurrence time，第二条采用各自进入 Gateway 时一次固定的 receipt time
- **AND** 后续 buffer、retry 或 replay 不重新读取当前时钟

#### Scenario: 飞书历史补拉沿用消息原发生时间
- **GIVEN** Gateway 在一条飞书群触发消息前通过 provider history API 补拉到先前漏收的真人消息，且该历史消息带合法 create time
- **WHEN** 补拉消息进入 group buffer 并随触发消息提供给 Agent
- **THEN** 该消息采用 provider create time，而不是本次补拉或触发发生的时间

#### Scenario: 同一 shadow context 按逐消息实际入口标注
- **GIVEN** 飞书或个人微信聊天与 Web IM shadow conversation 共享同一 DSH session
- **WHEN** 用户先从飞书或个人微信发送消息，随后从 Web IM 继续
- **THEN** Agent 看到前一条来自 `Feishu` 或 `WeChat`、后一条来自 `Web IM`
- **AND** 两条消息都不因 conversation 的外部来源属性而被标成同一入口

#### Scenario: 群聊延续 sender 语义但不重复 chat type
- **GIVEN** Web IM 或飞书群聊中有多名参与者发送消息
- **WHEN** buffered 与当前消息一起进入 Agent context
- **THEN** 每条新消息同时保留实际 Channel、固定时间与既有 `[sender]`
- **AND** envelope 不额外输出 Direct/Group 或内部 routing identity
