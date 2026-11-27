# feat-794: 微信外部通道（WeChat Channel） — Design Review

## Round 1

### Metadata

- **reviewer**: independent `change-design-reviewer` subagent (`0bb26799-e1a2-471a-886e-babcb831ed1e`, 组合 `agent-context-review` 与 `frontend-experience-review` 设计模式)
- **target**: `docs/changes/feat-794-wechat-channel/`（`spec.md`、`design.md`、`prototype.html`、`specs/gateway/{external-channels,spec,routing-delivery}.md`、`specs/im/agents-nodes.md`、`M1-wechat-binding-and-text-channel/`、`M2-wechat-rich-media-forwards-and-approvals/`），对照开发基线 `origin/develop`（`3fafe61c545e89aee6ff6977ed3d082c21a23de2`）
- **review_mode**: `full`
- **mode_reason**: 首轮 Gate 2 独立设计审查，无历史 `design-review.md`，对现状断言、架构边界、关键决定、用户澄清约束、Agent Context 消费链、前端原型与双端体验、delta-spec 及里程碑执行完整核查。
- **started_at**: `2026-11-26T19:24:34+09:00`
- **completed_at**: `2026-11-26T19:39:10+09:00`
- **duration**: `14m36s`

### Verdict

**Issues Found** — `3 CRITICAL / 5 WARNING`（另有 `2 Recommendations`）

### Coverage 与证据

1. **跨包架构、职责归属与复用判断（对照 `origin/develop:SPEC.md` 及 `tests/contract/test_runtime_dependency_contract.py`）**
   - **合理的架构选择**：将 iLink 长轮询、二维码状态轮询、AES-128-ECB 流式加解密、有界 `<appmsg>`/`<recordinfo>` 解析与本地引用缓存收敛在 `@nano/channels` + `apps/node`，中心 `apps/im-server` 仅负责鉴权、经 `node.wechat.setup.request` 转发节点设置状态并在同一事务内通过 `sealChannelSecret` 公钥密封落库，遵守了“中心不直连外部平台、浏览器零接触明文凭据、节点离线可凭本地密文缓存自治”的核心红线；异步扫码轮询复用 `ModelSetup` 的后台状态机模式，避免阻塞 10 秒 WS RPC；通用文件下载复用 `feat-786` 的 `download_attachment` 短引用机制，方向正确。
   - **实际组装入口核查发现的断链**：从真实产品入口逐一核对 `apps/node/src/main.ts`、`apps/im-server/src/{messaging,schema.sql,db,personal-agent,personal-actions,channels}.ts` 及 `packages/personal-assistant/src/{managed-channels,external,single-thread,global-agent,personal-assistant,attention,inbox,store}.ts` 后，确认方案遗漏了 PA 外部入站的 `messaging.ts` 鉴权与 `owner_direct_agent_messages` 视图迁移（`R1-C1`），出站图片在 `GlobalAgent` / `PersonalAssistant` / `SingleThread` / `ExternalChannels` 之间未打通图片字节传递与离线落盘（`R1-C2`），以及工具审批混淆了 `SingleThread` 与 `Global / PA` 的运行时分流（`R1-C3`）。
2. **需求与用户约束核对（`spec.md` Q1 / Q2 及 5 条 Requirement）**
   - Q1（Web 完整扫码/验证码绑定与管理；原生 iOS 状态展示与启停/重连/删除、清理飞书硬编码）及范围非目标（不做 `<persona-context>` 注入、不盲抓任意公网 URL）在方案目标层面对齐，但原生 iOS 的 `+ 添加通道` 入口交互尚未闭合（`R1-W4`）。
   - Q2（PR 前隔离真栈 + 本机可控 `e2e-wechat-twin` 全链路门禁 + 提 PR 前用户真机实扫隔离预览）已体现在审查安排与 Runbook 中，但 `e2e-up.sh` 后台守护进程的环境变量持久化需补齐以防重启漏向公网（`R1-W3`）。
   - 上游协议核查（对照 `tencent-openclaw-weixin-main/src/{auth/login-qr.ts,messaging/partial-quote.ts,api/types.ts}`）：发现局部选中引用 `partial_text` 实为子串出现次数序号而非 UTF-16 下标区间，且重绑 `local_token_list` 会触发无新 token 的 `binded_redirect` 状态（`R1-W1`）。
3. **Agent Context 专项审查（`agent-context-review` 设计模式）**
   - **静态前缀缓存**：不改系统提示词段，不引入 `<persona-context>`，可保持 `verify-context-cache-prefix` 稳定。
   - **入站内容语义**：独立图片不塞 `[图片]` 占位词、非光栅附件投影为 `<= 8` 字符 `a_xxxxxx` 引用、卡片与合并转发转可读文本的取舍合理。
   - **发现的 Context 缺陷**：`packages/personal-assistant/src/single-thread.ts:371` 将所有非 `'feishu'` 通道消息硬编码标注为 `source: Web IM`，且第 312 行仅对 `'feishu'` 注入主人 `roleAccountId`（`R1-W2`）；此外合并转发第三方言论的指令隔离与审批口令防误触可进一步加固（`R1-R1`）。
4. **前端体验与原型专项审查（`frontend-experience-review` 设计模式）**
   - 已核查现有基线代码 `src/IM/frontend/src/features/settings/agents/{agent-channels-panel.tsx,channel-provider-registry.ts}`、`src/IM/ios/NanoIM/Features/{Agents/AgentChannelsView.swift,Me/ModelServicesView.swift}`、作者提供的 4 张截图（`qr-wait-desktop-728.png`、`qr-wait-mobile-390.png`、`pin-code-desktop-728.png`、`revoked-desktop-728.png`），并使用 `html_preview` 在 `728px` 与 `390px` 独立渲染核查了 `prototype.html` 全部 7 个状态（`picker`、`qr_wait`、`qr_scanned`、`pin_code`、`qr_expired`、`connected`、`revoked`）。
   - **积极面**：沿用现有 `.im-channel-card` 与居中弹窗 / 窄屏底部抽屉（含 `.chat-modal-sheet-handle`）符合 Crewden 既有设置页秩序，无多余页面跳转。
   - **体验与证据问题**：作者的 `pin-code-desktop-728.png` 实际渲染成了二维码等待态（证据失真），`prototype.html` 缺少数字验证码校验失败/重试/提交中反馈，`-14` 失效卡片中无效的「重连」与主恢复动作「重新扫码」并列同权重易误导操作，iOS `+ 添加通道` 入口行为未定义（`R1-W4`）。
5. **契约层增量（`delta-spec`）与里程碑核查**
   - 核实 `origin/develop` canonical 基线：`docs/specs/gateway/external-channels.md` 现为 `17` 条 Requirement（`+2 ADDED` → `19`，与 `specs/gateway/spec.md` 一致），`docs/specs/im/agents-nodes.md` 现为 `56` 条（仅 `MODIFIED` 保持 `56` 不变），`specs/gateway/routing-delivery.md` 保留了 `Agent 可通过短标识下载受保护会话附件` 原有 2 个 Scenario。
   - 发现 `routing-delivery.md` 漏改出站 `local_images` 适用范围、`agents-nodes.md` 漏写微信禁传明文凭据契约、`external-channels.md` 写死内部错误码 `-14` 且漏定义微信运行信息页脚（`R1-W5`），以及 `M1` 依赖 `M2` 才安装的 `qrcode` 包导致里程碑倒置（`R1-W3`）。
   - 无一次性生产人工迁移需求（无需 `deployment-prompt.md`，但需在 `apps/im-server/src/db.ts` 补齐幂等代码内视图迁移，见 `R1-C1`）。

### 历史问题闭环

N/A（Round 1 首轮审查）。

---

### Issues

#### `R1-C1` [CRITICAL] IM Server 遗漏了 PA 外部入站鉴权入口（`messaging.ts`）与 `owner_direct_agent_messages` 视图迁移（`schema.sql` / `db.ts`），导致 PA 微信主路径 `403` 拒绝且 `owner_only` 准入失效

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`：「现状分析 > 涉及范围」（第 22-24 行）、「一次性部署迁移」（第 304-306 行）、「Milestones > M1」（第 330 行）
  - 关联基线代码（`origin/develop`）：`apps/im-server/src/messaging.ts:416-439, 603`、`apps/im-server/src/schema.sql:550-576`、`apps/im-server/src/db.ts:86-138`、`apps/im-server/src/collaboration.ts:39-47`
- **证据**:
  1. **PA 唯一外部入站端点硬编码 `config_json.app_id`**：`ExternalChannels.mirrorAdmitted`（`packages/personal-assistant/src/external.ts:188, 475`）将 PA 外部消息投递至 `POST /im/v1/conversations/:conversation_id/external-incoming`。在 `apps/im-server/src/messaging.ts:420-422` 中，`incomingExternalSource` 写死：
     `String(c.external_chat_id).startsWith(\`${row.provider}:${JSON.parse(row.config_json).app_id}:${c.type==='group'?'group':'dm'}:\`)`。
     微信通道的 `config_json` 为 `{ bot_id, owner_user_id, base_url }`（不含 `app_id`），`JSON.parse(row.config_json).app_id` 为 `undefined`，所有 PA 微信入站请求都会在 `incomingExternalSource` 直接抛出 `403 incoming_source_not_verified`。
  2. **普通 Agent 影子消息丢失 `provider_facts`**：同一文件 `apps/im-server/src/messaging.ts:603` 写死 `c.external_source === 'feishu'` 时才提取并持久化 `provider_facts`（含 `source_time`、`replied_to_bot`、`scope_skipped` 等），微信影子消息会被静默丢弃 `provider_facts`。
  3. **`owner_direct_agent_messages` SQLite 视图写死飞书且存量库不会自动刷新视图**：`apps/im-server/src/schema.sql:562-565` 将外部本人私聊判定写死为 `c.external_source='feishu'`、`ch.provider='feishu'`、`json_extract(ch.config_json,'$.app_id')` 与 `json_extract(ch.provider_runtime_json,'$.owner_open_id')`。该视图直接决定 `personal_observation_event` 触发器（`schema.sql:575`）在 `owner_only` 下是否入队，以及 `ownerDirect()` / `chatAllowed()` / `PersonalAgents.sourceFacts`（`personal-agent.ts:150`）中的 `owner_direct` 真值。由于 `schema.sql:550` 使用 `CREATE VIEW IF NOT EXISTS`，若不在 `apps/im-server/src/db.ts` 增加幂等 `schema_migrations` 重建该视图（`DROP VIEW IF EXISTS owner_direct_agent_messages; CREATE VIEW ...`），任何已有 SQLite 数据库升级后仍会沿用旧飞书视图。
- **未修后果**: 按当前 M1 范围实施后，Personal Agent 无法接收任何微信消息（全量 `403`），普通 Agent 与 PA 的 `owner_direct` 判定失效，`collaboration_scope = 'owner_only'` 时主人微信消息被当作非本人消息拦截。
- **修改方向**: 将 `apps/im-server/src/messaging.ts`、`apps/im-server/src/schema.sql` 与 `apps/im-server/src/db.ts` 纳入 M1 范围；抽取统一的 provider 会话前缀/主人匹配辅助函数覆盖 `feishu`（`config_json.app_id` + `provider_runtime_json.owner_open_id`）与 `wechat`（`config_json.bot_id` + `config_json.owner_user_id`），并在 `db.ts` 增加幂等视图重建迁移。

---

#### `R1-C2` [CRITICAL] 出站图片交付链路在 `SingleThread`、`GlobalAgent`、`PersonalAssistant` 与 `ExternalChannels` 之间未闭合

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`：「现状分析 > 涉及范围」（第 18 行）、「关键决策 5」（第 130 行）、「接口与数据流 > 3」（第 222 行）、「Milestones」（第 330-331 行）
  - 关联基线代码（`origin/develop`）：`packages/personal-assistant/src/global-agent.ts:1100, 1142-1158`、`packages/personal-assistant/src/personal-assistant.ts:480-491`、`apps/im-server/src/personal-actions.ts:143-144`、`apps/node/src/screenshot-upload.ts:19-60`、`apps/node/src/main.ts:497-505`、`packages/dsh-integration/src/policy/approval.ts:116-118`
- **证据**:
  1. **本地生成图片在现行架构中的真实出口未打通**：LLM 在普通回复文本中不会直接输出数 MB 的 `data:image/...;base64` 字符串，而是调用 `send_message(..., local_images=[absPath])` 发送工具生成的图表或截图。但在现行组装中：
     - `SingleThread`（`apps/node/src/main.ts:497-505`）并未接入 `uploadScreenshot` / `send_message` 本地图片上传能力，且 `packages/dsh-integration/src/policy/approval.ts:116-118` 在 `interactive` 审批路由下一旦 `send_message(local_images)` 触发审批升级会直接 `deny`（返回 `privateScreenshotApproval`）；
     - `GlobalAgent`（`global-agent.ts:1142-1145`）若仅放开第 1100 行 `info?.channel !== 'web'`，会把 `conversationId: reviewConversation`（值为 `external:<agent_id>:wechat:...`）传给 `uploadScreenshot`（`apps/node/src/screenshot-upload.ts:25`），向 IM 请求 `/im/v1/conversations/external%3A.../images` 导致 `404`；且当中心 IM 离线或 `shadowId` 尚未建立时，`uploadScreenshot` 直接因 HTTP 不可达失败，破坏外部通道离线自治；
     - `PersonalAssistant.sendMessage`（`personal-assistant.ts:480-491`）在 `deliveryTarget.startsWith('external:')` 分支直接早退只发 `text`，跳过了 `prepareLocalAttachments` 且未传递 `attachments`；同时 `apps/im-server/src/personal-actions.ts:143-144` 写死 `if(args.transport && !args.content.trim()) fail(422,'external_text_required')` 与 `if(args.transport && args.attachments?.length) fail(409,'external_attachment_adapter_unavailable')`。
  2. **`@nano/channels` 无法从 `ChatAttachment.url` 读取图片字节**：`ChatAttachment` 仅包含 IM 相对路径 `/im/v1/conversations/<id>/images/<img_id>`，而 `WeChatConnection` 位于无 IM 凭据的 `@nano/channels` 包内，无法自行拉取字节做 AES-128-ECB 加密上传。
- **未修后果**: `spec.md` 第 67、148-151 行要求的“Agent 回复附带生成的图片在微信中作为真实图片消息展示，同时内部 IM 影子会话完整保留回复文本与图片”在 PA、Global 离线/未同步影子会话以及 SingleThread 场景下无法工作或直接报错。
- **修改方向**: 在 `design.md` 明确闭合本机图片字节到外部通道与影子会话的双写数据流：例如对目标为 `external:` 私聊的 `local_images`（及 SingleThread / Global / PA 统一支持的出站图片路径），先在节点本机校验并读取图片字节缓存至 `ExternalStore`（支持离线先通过 `WeChatConnection` 上传微信 CDN 发出，待 IM 在线且 `shadowId` 就绪后幂等上传至 `/im/v1/conversations/<shadowId>/images` 补齐影子会话消息附件），并同步打通 `personal-assistant.ts`、`personal-actions.ts` 与 `approval.ts`（主人私聊 `local_images` 审批边界）。

---

#### `R1-C3` [CRITICAL] 工具权限审批未区分 `SingleThread` 与 `Global / PA` 的真实运行时审批架构，且缺少轮次中止/结束对未决文本审批的清理机制

- **位置**:
  - `docs/changes/feat-794-wechat-channel/spec.md`（第 70、163-167 行）；`design.md`（第 41、132-134、228-231、288 行）；`specs/gateway/external-channels.md`（第 30-43 行）
  - 关联基线代码（`origin/develop`）：`packages/dsh-integration/src/policy/approval.ts:83-90`、`packages/personal-assistant/src/single-thread.ts:79-82, 518-526`、`packages/personal-assistant/src/external.ts:484-493`、`apps/node/src/main.ts:475`
- **证据**:
  1. **Global 与 PA 在架构上不产生 `permission_request` 卡片**：在 `packages/dsh-integration/src/policy/approval.ts:88` 中，`if (config.mode === 'global') return 'return_to_agent'`——所有 `global` 模式 Agent（含全部 Personal Agent 与普通 Global Agent）遇到受控操作时走 `return_to_agent` 由主模型在对话中向用户确认，**不会**发出 `approval.request` / `permission_request` 事件；仅 `single_thread` 模式才会经 `SingleThread.approval` 生成内部 IM 审批卡并回调 `SingleThread.permission`（`apps/node/src/main.ts:475` `permission: payload => product.permission(payload)`，且 `external.ts:486` 显式跳过 `personalAgent`）。虽然 `specs/gateway/external-channels.md` 第 32 行写了“单会话运行”，但 `spec.md` 第 163-167 行及 `design.md` 第 288 行（Stage 4 旅程要求在普通 Agent 与 PA 上验收双端审批卡互斥）未指明这一模式边界，会导致实施或独立验收在 PA / Global Agent 上无法触发审批卡而卡死。
  2. **待决审批在轮次中止或异常结束时缺少收敛清理**：在 `SingleThread` 下，若微信会话存在 `settled === 0` 的待决审批，而用户随后在微信发送 `/stop`、`/new`、在内部 IM 取消运行或触发 Agent 停用，DSH 已取消该审批但未必下发 `permission_resolved`；若 `ExternalStore.approvals` 仍保留 `settled = 0`，后续用户正常发送 `"1"` 或 `"同意"` 时会被入站拦截器误判为审批口令并调用 `SingleThread.permission`，抛出 `Permission is no longer pending` 吞掉正常聊天消息。
- **未修后果**: 下游测试与 Stage 4 验收对 Global / PA 的审批预期与运行时真实行为冲突；`SingleThread` 在 `/stop`、`/new` 或失败后残留僵尸待决审批拦截正常消息。
- **修改方向**: 在 `design.md`（并核对 `spec.md` / `specs/gateway/external-channels.md` 表述一致性）明确：原生 `permission_request` 审批卡与微信文本口令双向互斥适用于产出交互审批卡的 `single_thread` 会话，而 `global` / PA 保持既有 `return_to_agent` 自然语言对话确认机制；同时规定在收到 `/stop`、`/new`、`run_terminal_reconcile` / 轮次终结或 Agent 停用时，原子将所属会话未结算的 `ExternalStore.approvals` 标记为已失效/已结束。

---

#### `R1-W1` [WARNING] 托管通道生命周期（`ManagedChannels`）、删除清理、扫码重绑状态机与局部引用解析存在四处协议/状态断链

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`（第 113-116、158-165、175、218-221、301 行）
  - 关联基线与参考代码：`packages/personal-assistant/src/managed-channels.ts:20, 77, 100-123, 140-143, 184-185`；上游参考 `@tencent-weixin/openclaw-weixin` 的 `src/auth/login-qr.ts:86-95, 299-305, 600-659` 与 `src/messaging/partial-quote.ts:10-62`
- **证据**:
  1. **`ManagedChannels` 的 `stop()` / `drop()` 当前为同步 `void`**：`managed-channels.ts:20, 77, 102, 140-143` 中 `instance.runtime.stop()` 不返回 `Promise`，`reconnect` 与 `apply` 调用 `this.drop(id)` 后立即同步进入 `await instance.runtime.start()`。若不将 `Runtime.stop(): Promise<void>` 及 `drop` / `apply` / `reconnect` / `purgeAgent` / `revoke` / `stop` 全部改为异步串行等待在途 `getupdates` 退出，“先停后起”单轮询保证无法兑现。
  2. **先停用（或 `-14` 失败停止）再删除通道会漏清本地 SQLite 缓存**：通道停用（`enabled: false`）时 `ManagedChannels` 已将其从 `this.instances` 移除（此时需保留游标与引用缓存供重新启用）；当用户随后删除该已停用通道时，`this.instances.get(id)` 为空，`drop(id)` 直接返回，而 `managed-channels.ts:122` 处理 `manifest.removals` 时没有任何 `purgeChannel(channelId)` 回调去清理 `<nodeHome>/wechat-state/<channel_id>.sqlite3` 与引用索引，违反 `spec.md` 第 95、157 行清理要求。
  3. **扫码重绑的 `local_token_list` 与上游真实状态枚举未闭合**：① `node.wechat.setup.request` 的 `start` 分支（第 161 行）仅传 `{ action: 'start', agent_id }`，未传 `editing_channel_id`，且若 `-14` 已清空动态缓存则拿不到旧 token；② 对照上游 `login-qr.ts:299-305, 634-645`，传入有效 `local_token_list` 重扫已绑定机器人时，iLink 可能返回 `status: "binded_redirect"` 且**不下发新 `bot_token`**（依赖沿用本地原有效凭据），此外上游还存在 `scaned_but_redirect`（切换 `redirect_host` 时必须校验主机名仍匹配 `*.weixin.qq.com` 防 SSRF）、`confirmed_but_need_verifycode` 与 `verify_code_blocked` 状态，`design.md` 需明确这些状态的收敛处理（或不在无本地可恢复明文 token 时盲传已失效 `local_token_list`）。
  4. **`partial_text` 局部引用算法与上游真实协议不符**：`design.md` 第 220 行将 `partial_text` 写成“`startindex/endindex` UTF-16 区间”，但上游协议（`api/types.ts:144-150`、`partial-quote.ts:10-62`）中 `partial_text` 结构为 `{ start: string, end: string, startindex: number, endindex: number, quotemd5: string }`，`startindex` / `endindex` 实际是起止边界子串 `start` / `end` 的 **0-based 第 N 次出现序号（occurrence index，且 `endindex` 存在全文计数与 `start` 后相对计数两种客户端变体，需用 `quotemd5` 消歧）**。按 UTF-16 字符下标切片会直接截错所有局部引用。
- **未修后果**: 新旧 poller 并发抢游标、停用后删除通道在磁盘永久残留用户近期私聊引用记录、重绑触发 `binded_redirect` 或 `verify_code_blocked` 失败，以及局部文字引用还原内容错乱。

---

#### `R1-W2` [WARNING] `packages/personal-assistant` 与 `apps/node` 仍有多处硬编码 `'feishu'` 分支未纳入修改范围，引发模型来源误标、记忆归属缺失、Global 表情回执抛错与影子标题不一致

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`（第 16-21、118、236-238、330 行）
  - 关联基线代码（`origin/develop`）：`packages/personal-assistant/src/single-thread.ts:195, 312, 371-373`、`attention.ts:18, 53-58`、`store.ts:626`、`inbox.ts:378-386`、`global-agent.ts:60, 218-231, 1101, 1157, 1547`、`external.ts:148, 340, 359, 388, 545`、`apps/node/src/configuration.ts:26`、`apps/node/src/main.ts:472`
- **证据**:
  1. **Agent Context 误标与记忆归属丢失**：`single-thread.ts:371` 构造 `contextEnvelope` 时写死 `source: ${input.metadata.channel === 'feishu' ? 'Feishu' : 'Web IM'}`，微信消息进入模型会被标成 `source: Web IM`；第 312 行写死 `input.metadata.channel === 'feishu' && input.metadata.owner_user_id === binding.ownerId` 才传 `{ roleAccountId: binding.ownerId }`，导致微信主人私聊缺失 DSH 记忆层的主人账号归属。
  2. **准入、时间戳与定时恢复硬编码 `'feishu'`**：`attention.ts:18` 的 `ownerDirect` 兜底与第 53-58 行 `sourceInstant` 仅识别 `meta.channel === 'feishu'`；`store.ts:626` 对所有 `external:` 会话的定时/系统消息写死 `channel: 'feishu'`。
  3. **Global 回执队列误调飞书表情 API 与卡片校验遗漏**：`external.ts:148` 对普通 Global Agent 设置 `agent_receipt = true`，`inbox.ts:385` 按 `id LIKE 'external:%'` 排入回执队列并触发 `ExternalChannels.showReceipt`（`external.ts:388`），后者调用飞书专属 `CRY`/`Get` 表情反应并在返回 `undefined` 时直接 `throw new Error('Feishu returned no reaction identity')`，导致微信 Global 会话后台回执无限退避报错；同时 `global-agent.ts:1101, 1157` 仅拦截 `'feishu' | 'external'` 的无正文交互卡，漏掉了 `'wechat'`。
  4. **运行信息页脚、未知发送文案与影子会话标题不一致**：
     - `external.ts:359` 在开启 `runtimeFooter` 时调用 `runtimeCard()` 生成飞书卡片 JSON（`main.ts:472` 亦只读 `platforms.feishu.runtime_footer`），未定义微信通道如何按纯文本尾注兑现 `external-channels.md` 的运行信息页脚契约；
     - `external.ts:340` 写死 `"飞书发送结果未知，未自动重发。"`；
     - `spec.md` 第 19、64、101、173 行与 `specs/gateway/external-channels.md` 第 9、19 行规定影子会话标题为 `<Agent 名> · wechat`，而 `design.md` 第 118 行沿用了 `external.ts:545` 的 `<agent_id> · wechat`（当 `agent_id` 为内部 ID 而非 `display_name` 时与契约不一致，需明确优先取 Agent 配置显示名或统一契约口径）。
- **未修后果**: SingleThread 模型误以为用户在 Web IM 发言、丢失主人记忆身份；Global Agent 处理微信消息后回执队列持续抛错；开启运行信息页脚时出站异常；未知发送提示错写“飞书”。

---

#### `R1-W3` [WARNING] Milestone 依赖倒置（`M1` 代码依赖 `M2` 才引入的 `qrcode`）且新增二进制/WASM 依赖打包及 `e2e-up.sh` 守护进程环境透传未闭合

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`（第 14、310-322、330-331 行）
  - 关联基线代码（`origin/develop`）：`packages/channels/package.json`、`pnpm-lock.yaml`、`scripts/e2e-up.sh:272, 368`、`apps/node/src/release.ts`
- **证据**:
  1. **M1 与 M2 依赖倒置**：`M1-wechat-binding-and-text-channel` 包含 `packages/channels/src/wechat/login.ts` 并要求 Web 端跑通二维码渲染（`qr_svg`），`design.md` 第 14 行指定使用 `qrcode` 生成 SVG；但 `origin/develop` 的 `pnpm-lock.yaml` 并未安装 `qrcode`，而 `packages/channels/package.json（qrcode、silk-wasm、sharp）` 被排在了 `M2`（第 331 行），导致 M1 无法在不修改 `package.json` / `pnpm-lock.yaml` 的情况下独立编译通过。
  2. **跨平台发布与按需加载风险**：`@nano/channels` 被 `apps/node` 在 macOS / Windows 节点与桌面端直接加载。新增 `sharp`（平台原生 addon）与 `silk-wasm`（含 `.wasm` 资源读取）后，需明确 M1/M2 的 `package.json` + `pnpm-lock.yaml` 归属、动态按需加载（避免未启用微信通道时因原生/WASM 初始化异常阻塞整个节点启动）及构建校验。
  3. **隔离 E2E 守护进程环境变量持久化**：`scripts/e2e-up.sh:272, 368` 生成 `.gateway-config.yaml`（含 `gateway.environment`）并通过 `cli.js start` 拉起独立后台守护进程。若仅在命令行前缀传 `NANO_WECHAT_E2E_BASE_URL` 而不写入 `.gateway-config.yaml` 的 `gateway.environment`（及 `.e2e-ports.env`），测试中途执行节点重启或 `--resume` 时会丢失该变量并误连公网微信服务。
- **未修后果**: M1 实施即遭遇缺包阻塞或跨里程碑越界改动；E2E 重启场景存在泄漏请求至真实上游的风险。

---

#### `R1-W4` [WARNING] 前端原型走查证据失真，且数字验证码失败态、`-14` 失效卡片操作权重与原生 iOS 添加入口未收口

- **位置**:
  - `docs/changes/feat-794-wechat-channel/design.md`（「前端原型」第 241-280 行）；`prototype.html`（第 472-637 行）
  - 作者走查截图：`scratch/prototype-screenshots/pin-code-desktop-728.png`、`revoked-desktop-728.png`
  - 关联基线代码（`origin/develop`）：`src/IM/ios/NanoIM/Features/Agents/AgentChannelsView.swift:27, 65, 160-185`
- **证据**:
  1. **走查截图失真（证据缺口）**：核查作者引用的 `pin-code-desktop-728.png` 发现，因 `prototype.html` 第 635 行默认回退 `"qr_wait"`，截图顶部控制栏同时高亮了 `2. 待扫码` 与 `4. 数字验证码`，而弹窗内部实际仍停留在二维码画面，并未验证验证码输入框视觉效果；窄屏 `390px` 仅保存了 `qr_wait` 一张截图，未覆盖双通道卡片与验证码抽屉态。
  2. **数字验证码错误与提交态缺失**：本轮在 `728px` 与 `390px` 独立渲染 `pin_code` 状态确认，`prototype.html` 虽声明了 `.alert-error` 样式但从未在验证码视图中使用，未表达 `spec.md` 第 82-85 行要求的“提交的数字验证码未通过校验时显示明确原因并允许重试或重新扫码”（含提交中禁用重复点击与多次输错触发 `verify_code_blocked` 自动换码提示）。
  3. **`-14` 登录失效卡片按钮权重与可执行性冲突**：在 `revoked` 卡片（`728px` 与 `390px`）中，`[重新扫码] [重连] [停用] [删除]` 四个同级次要按钮并排展示，而底部错误文案提示“请点击「重新扫码」恢复绑定”。既然 `-14` 代表令牌已被微信永久吊销，保留可点击的同级「重连」会诱导用户做无效重试；应禁用或收起 `wechat_token_revoked` 下的「重连」，并突出「重新扫码」的主恢复操作权重。
  4. **原生 iOS `+ 添加通道` 与空态引导未定义**：`AgentChannelsView.swift:27` 当前写死 `.disabled(channels.contains { $0.provider == "feishu" })` 且点击直接进入飞书专属 `AgentChannelEditor`。`design.md` 仅说明了已绑定微信行的展示，未说明当用户在 iOS 端点击 `+ 添加通道`（或处于无通道空态）时，如何防止直接落入无 provider 选择的飞书表单、如何向想绑定微信的用户清晰提示“微信通道请前往电脑或网页端扫码添加”，以及如何在“已有微信但未加飞书”时保持飞书可添加、“飞书已添加”时不误开放第二个飞书表单。
- **未修后果**: 原型 `must-match` 缺少验证码报错态对照依据；用户在 `-14` 失效卡片误点「重连」挫败；iOS 端点击 `+ 添加通道` 仍呈现纯飞书创建界面造成困惑。

---

#### `R1-W5` [WARNING] `delta-spec` 遗漏 `routing-delivery.md` 出站本地图片条款同步、微信凭据 REST 写入限制，并在长青契约正文绑定内部错误码

- **位置**:
  - `docs/changes/feat-794-wechat-channel/specs/gateway/routing-delivery.md`
  - `docs/changes/feat-794-wechat-channel/specs/gateway/external-channels.md`（第 48、91 行）
  - `docs/changes/feat-794-wechat-channel/specs/im/agents-nodes.md`（第 5-45 行）
  - `docs/changes/feat-794-wechat-channel/design.md`（第 147、291-297 行）
- **证据**:
  1. **`routing-delivery.md` 未同步修改出站本地图片条款**：`origin/develop:docs/specs/gateway/routing-delivery.md` 的 `Requirement: 当前会话的 Agent 图片与文件回复具有统一交付语义` 当前写明“Agent 向已有原生 IM 聊天以自身身份显式调用 `send_message` 时，可在 `local_images` 中传入绝对路径发送本地光栅图片”，且 `Scenario: 图文投递保持入口路由` / `IM 离线不阻塞飞书图片` 仅写飞书。既然 `design.md` 决策 5 将 `send_message(..., local_images)` 扩展到了 `wechat` / `feishu` 私聊，必须同步在 `specs/gateway/routing-delivery.md` 用 `MODIFIED` 更新该 Requirement 的适用条件与微信图文/离线恢复 Scenario，否则归并后同一包内契约自相矛盾。
  2. **`im/agents-nodes.md` 遗漏微信禁传明文凭据的接口保证**：`design.md` 第 147 行规定微信通道仅允许经节点扫码 `setup` 建立/重绑凭据、`PATCH` 仅允许 `credentials: { mode: 'keep' }` 切换 `enabled`（拒绝客户端直接 `POST/PATCH` 明文微信 token），该安全保证对客户端调用方直接可观察，应补入 `specs/im/agents-nodes.md` 的 `Agent 通道页统一管理外部 channel 与安全凭据` 对应 Scenario。
  3. **`gateway/external-channels.md` 条款细节与既有区域协同**：第 48、91 行在长青契约中写死了协议内部数值 `（如状态码 -14）`，宜改为外部可观察语义（“微信上游明确返回连接凭据已失效或已在别处重新绑定”），将 `-14` 保留在 `design.md`；同时需核对 canonical `external-channels.md` 末尾既有 `Requirement: PA 飞书主人私聊身份与交付`（第 543 行）与运行信息页脚条款在引入微信后的表述衔接，避免同一文件内前后范围冲突。
- **未修后果**: 归并后 `routing-delivery.md` 仍声明 `send_message(local_images)` 仅限原生 IM 聊天，与微信出站图片实现冲突；REST 明文提交拦截缺乏契约锚点。

---

### Recommendations

- **`R1-R1`（Agent Context 防注入与审批口令防误触加固）**：合并转发聊天记录（`<recordinfo>`）内含第三方群友或外部联系人的任意文本，而外层消息来自扫码主人本人（`is_owner: true`）。建议：① 在展开合并转发与引用片段时，将主人当轮附加评语与转发/引用块明确分层标记（注明转发块内发言者为外部被转发原文而非主人本轮直接指令，辅助根模型与 `pa.review` 准确区分）；② 微信文本审批口令正则（`允许`/`1`/`拒绝`/`2`）仅在入站消息为**不含 `<appmsg>` 转发块且不含 `ref_msg` 的纯文本单条目**时触发，避免用户转发一段恰好写着“同意”的聊天记录误触发工具权限批准。
- **`R1-R2`（iOS 通道契约测试复用 `AgentContractsTests.swift`）**：`src/IM/ios/Tests/AgentContractsTests.swift` 已有 `AgentChannel` 与 `removal` 的解码测试基线，M1 worker 可直接在该测试集中补充 `wechat` 在线、`wechat_token_revoked` 失效与 `bot_id_suffix` 删除回执断言，并将 iOS 通道分组/按钮可见性抽为纯值计算属性单测，低成本覆盖 iOS `may-adapt` 行为。

### Author Resolutions

- **`R1-C1`**: `accepted` — 已将 `apps/im-server/src/messaging.ts`（第 420 行 `incomingExternalSource` 与第 603 行 `provider_facts` 保留）、`apps/im-server/src/schema.sql`（`owner_direct_agent_messages` 视图）与 `apps/im-server/src/db.ts`（幂等 `schema_migrations` `owner-direct-wechat-view-v1` 执行 `DROP VIEW IF EXISTS` + `CREATE VIEW`）纳入 `design.md`（「涉及范围」、「关键决策 3」、「接口与数据流 1」、「一次性部署迁移」及 `M1` 范围与退出标准），统一兼容 `feishu`（`app_id` + `owner_open_id`）与 `wechat`（`bot_id` + `owner_user_id`）。
- **`R1-C2`**: `accepted` — 已在 `design.md`（「关键决策 5」、「接口与数据流 3」及 `M2`）闭合出站图片双阶段数据流：对发往 `wechat` / `feishu` 私聊的 `send_message(..., local_images)` 与内联 `data:image/...`（覆盖 `SingleThread`、`GlobalAgent` 及 `PA` 主人外部私聊），先由 `ExternalChannels.stageOutboundImage` 在节点本机校验并持久化图片字节至 `ExternalStore.images`（`external:out:${operationId}:${index}`），不依赖 IM 在线即可直接传字节给 `WeChatConnection.send` 上传微信 CDN 发出，待 IM 在线且 `shadowId` 就绪后在 `ExternalChannels.flush()` 幂等上传至 `/im/v1/conversations/${shadowId}/images?screenshot=1` 补齐影子附件；同步更新 `personal-assistant.ts` 与 `personal-actions.ts`（放行 `ownerConversation` 外部私聊图片提案，保持非主人会话与 `dsh-integration` `ask` 私有证据拦截不变）。
- **`R1-C3`**: `accepted` — 已在 `design.md`（「关键决策 6」、「接口与数据流 4」、「本次审查安排」、「Runbook」及 `M2`）与 `specs/gateway/external-channels.md` 明确区分运行时审批架构：`Global` 与 `PA` 保持既有 `return_to_agent` 对话内确认（不产审批卡），标准审批卡片与微信纯文本审批口令互斥适用于产出 `permission_request` 的 `SingleThread` 会话（Stage 4 旅程明确同时使用 `single_thread` 测试 Agent 与 daily `PA` 分别覆盖）；同时规定在 `/stop`、`/new`、轮次终态或 Agent 停用时原子将所属会话未决 `approvals` 置为已取消，杜绝残留状态误吞后续 `"1"` / `"同意"` 普通消息。
- **`R1-W1`**: `accepted` — 已在 `design.md`（「涉及范围」、「关键决策 1/2/6」、「接口与数据流 2/3」及 `M1/M2`）修复全部四处断链：① `ManagedChannels` 的 `Runtime.stop()` 及 `apply/reconnect/drop/revoke/stop` 全面改为异步 `await` 等待在途 `getupdates` 完全退出；② 新增 `purgeChannel({ channelId, agentId, provider })` 在 `manifest.removals` 与 `purgeAgent` 中无条件清理已停用或失效通道遗留的 `<nodeHome>/wechat-state/<channel_id>.sqlite3`；③ `node.wechat.setup.request` 的 `start` 补齐 `editing_channel_id`，完整定义 `scaned_but_redirect`（`*.weixin.qq.com` 校验防 SSRF）、`confirmed_but_need_verifycode`、`verify_code_blocked` 与 `binded_redirect`（无有效本地旧令牌时自动以空 `local_token_list` 重新申请新二维码）收敛逻辑；④ `partial_text` 改为按 `start`/`end` 0-based 子串出现序号计算全文与相对双候选并用 `quotemd5` 消歧。
- **`R1-W2`**: `accepted` — 已将 `single-thread.ts`（`source: 'WeChat'` 与主人 `roleAccountId`）、`attention.ts`、`store.ts`（按 `external:<agentId>:<provider>:` 解析真实 `channel`）、`global-agent.ts`（拦截 `'wechat'` 无文本交互卡）、`configuration.ts` 与 `external.ts`（仅 `supportsReactions` 通道启用 `agent_receipt` 表情、微信使用纯文本运行信息页脚、provider 化未知发送提示、统一 `${agentId} · wechat` 影子标题口径）全部纳入 `design.md` 与 `M1` 范围。
- **`R1-W3`**: `accepted` — 已将 `packages/channels/package.json` 与 `pnpm-lock.yaml`（`qrcode`、`silk-wasm`、`sharp`）统一前移至 `M1` 锁定，明确 `sharp` 与 `silk-wasm` 采用函数内按需动态 `import()`，并将 `scripts/e2e-up.sh` 纳入 `M1` 以将 `NANO_WECHAT_E2E_BASE_URL` 持久化写入隔离 `.gateway-config.yaml`（`gateway.environment`）及 `.e2e-ports.env`。
- **`R1-W4`**: `accepted` — 已更新 `prototype.html` 与 `design.md`：新增 `pin_error` 验证码错误重试态与非数字/空值提交禁用逻辑；在 `revoked` 登录失效卡片隐藏无效「重连」并将「重新扫码」设为主按钮（双通道均添加时禁用顶部 `+ 添加通道`）；明确原生 iOS `AgentChannelsView.swift` 点击 `+` 提供飞书/微信分流（选择微信展示网页/桌面端扫码绑定引导）；并通过 `window.__INITIAL_SCENE__` 重新实际渲染保存 `728px` 与 `390px` 全部代表性截图。
- **`R1-W5`**: `accepted` — 已更新 `specs/gateway/routing-delivery.md`（补齐 `MODIFIED Requirement: 当前会话的 Agent 图片与文件回复具有统一交付语义`）、`specs/im/agents-nodes.md`（补齐禁止客户端经普通 REST 接口直传明文微信凭据与 iOS 添加引导契约）及 `specs/gateway/external-channels.md`（去除正文内部错误码 `-14` 硬编码、明确微信纯文本运行信息页脚并同步 `MODIFIED Requirement: PA 飞书主人私聊身份与交付`）。
- **`R1-R1`**: `accepted` — 已采纳并写入 `design.md` 与 `specs/gateway/external-channels.md`：合并转发与引用块增加明确的非本轮直接指令分层提示，且微信文本审批口令仅在单条纯文本（无 `<appmsg>` 转发、无无关 `ref_msg`）时匹配。
- **`R1-R2`**: `accepted` — 已将 `src/IM/ios/Tests/AgentContractsTests.swift` 纳入 `M1` 文件范围与 `[worker]` 退出标准。


---

## Round 2

### Metadata

- **reviewer**: independent `change-design-reviewer` subagent (`0bb26799-e1a2-471a-886e-babcb831ed1e`, 组合 `agent-context-review` 与 `frontend-experience-review` 设计模式)
- **target**: `docs/changes/feat-794-wechat-channel/`（本轮修订的 `design.md`、`prototype.html`、`specs/gateway/{external-channels,routing-delivery}.md`、`specs/im/agents-nodes.md`，及未变动的 `spec.md`、`specs/gateway/spec.md`、里程碑骨架），对照开发基线 `origin/develop`（`3fafe61c545e89aee6ff6977ed3d082c21a23de2`）
- **review_mode**: `delta`
- **mode_reason**: `spec.md` 用户需求与澄清约束、跨包职责边界及 `specs/gateway/spec.md` 索引计数未变；本轮改动均为围绕 Round 1 检出问题（`3 CRITICAL / 5 WARNING / 2 Recommendations`）的有界设计闭合、原型状态修订、delta-spec 补齐与 `M1/M2` 依赖前移，故采用 `delta` 模式逐项核查全部变更及其波及范围（含受波及的 `node-rpc` 输入扩展与里程碑边界）。
- **retained_from**: `Round 1`（`spec.md` 需求与 Q1/Q2 澄清结论、中心不直连外部平台与公钥密封离线自治架构、静态系统提示词零改动、以及 `specs/gateway/spec.md` `External Channels` 计数 `17 -> 19` 未发生变化，沿用 Round 1 核实证据）
- **started_at**: `2026-11-26T19:54:47+09:00`
- **completed_at**: `2026-11-26T19:58:35+09:00`
- **duration**: `3m48s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING`（另有 `1 Recommendation`）

### Coverage 与证据（Delta 变更与波及范围）

1. **IM Server 入站鉴权、PA 主人私聊与存量库视图迁移波及核查（对应 `R1-C1`）**
   - 对照 `origin/develop:apps/im-server/src/{messaging.ts,personal-agent.ts,personal-actions.ts,schema.sql,db.ts}` 复核 `design.md` 第 24-27、121-124、147-159 行：统一抽取 `matchesExternalChannel(row, chat)` 兼容 `feishu`（`config.app_id` + `runtime.owner_open_id`）与 `wechat`（`config.bot_id` + `config.owner_user_id`），同时覆盖 `messaging.ts:420-422`（`incomingExternalSource`，且与第 `430` 行 `:dm:${b.sender_source_id}` 后缀校验完全吻合）、第 `603` 行 `provider_facts` 保留、`personal-agent.ts` 与 `personal-actions.ts`。
   - `db.ts` 新增幂等 `schema_migrations`（`owner-direct-wechat-view-v1`）执行 `DROP VIEW IF EXISTS owner_direct_agent_messages; CREATE VIEW ...`；SQLite 触发器 `personal_observation_event` 在触发时按名称动态解析视图，因此存量数据库启动即自动获得覆盖飞书与微信本人单聊的新视图，无需人工部署迁移文件（`deployment-prompt.md` 维持不创建正确）。
2. **出站本地图片双阶段投递全链路核查（对应 `R1-C2`）**
   - 对照 `origin/develop:apps/node/src/main.ts:553`（`SingleThread` 与 `GlobalAgent` 共用 `globalProduct.call` 处理 `send_message`）、`global-agent.ts:1087-1158`、`personal-assistant.ts:480-596` 与 `personal-actions.ts:143-166` 复核 `design.md` 第 19-20、132、224 行：发往 `wechat` / `feishu` 私聊的图片先经 `ExternalChannels.stageOutboundImage` 在节点本机校验并持久化至 `ExternalStore.images`（`external:out:${operationId}:${index}`），直接把字节交给 `WeChatConnection.send` 上传微信 CDN 发出（不向 `/im/v1/conversations/external:...` 发错误请求，且支持 IM 离线自治）；待 IM 在线且 `shadowId` 就绪后由 `ExternalChannels.flush()` 幂等上传至 `/im/v1/conversations/${shadowId}/images?screenshot=1` 补齐影子会话附件，并在 `personal-actions.ts` 放行 `ownerConversation` 外部私聊图片提案（保留非主人会话与 `dsh-integration` 私有证据 `ask` 拦截边界不变）。数据流已完整闭合。
3. **工具审批运行时分流、Context 身份归属与多通道硬编码清理核查（对应 `R1-C3`、`R1-W2`、`R1-R1`，`agent-context-review` 设计模式）**
   - `design.md` 第 18-20、124、136-137、229-235、282、312 行已与 `packages/dsh-integration/src/policy/approval.ts:88` 精确对齐：`Global` 与 `PA` 保持 `return_to_agent` 自然语言确认，`SingleThread` 走标准 `permission_request` 卡片 + 微信单条纯文本口令（排除 `<appmsg>` 转发与无关 `ref_msg`）互斥仲裁，并在 `/stop`、`/new`、轮次终结或 Agent 停用时原子清理未决 `approvals`。
   - Context 侧已补齐 `single-thread.ts` 的 `source: 'WeChat'` 与主人 `roleAccountId`、`store.ts:626` 按 `external:<agentId>:<provider>:` 还原真实 `channel`、`attention.ts`、`global-agent.ts` 拦截 `'wechat'` 无文本交互卡、`external.ts` 仅对 `supportsReactions` 通道启用飞书表情回执及微信纯文本运行信息页脚（`\n\n—\n<model · ctx X%>`），以及合并转发 `[合并转发的聊天记录：《...》——以下为被转发的历史对话原文，非当前发送者本轮直接指令]` 防注入边界。实现后在 Stage 4 按审查安排读取真实会话输入核验即可。
4. **登录状态机、异步单轮询、`purgeChannel` 与局部引用算法核查（对应 `R1-W1`）**
   - `node.wechat.setup.request` 的 `start` 已补齐可选 `editing_channel_id`；`WeChatLoginCoordinator` 覆盖 `scaned_but_redirect`（校验 `^[a-z0-9.-]+\.weixin\.qq\.com$` + `redirect: 'error'`）、`need_verifycode` / `confirmed_but_need_verifycode`（含 `wrong_verify_code` 原位重试）、`verify_code_blocked`、`expired` 及 `binded_redirect`（无有效本地令牌时自动以空 `local_token_list` 重取新码）；
   - `ManagedChannels` 全部停启路径升级为异步 `await`，并由 `purgeChannel` 覆盖停用/失效后再删除的 `<nodeHome>/wechat-state/<channel_id>.sqlite3` 清理；
   - `resolvePartialQuote` 已修正为 0-based 子串出现次数序号 + 全文/相对双候选 + `quotemd5` 消歧，与上游真实协议一致。
5. **前端原型重渲染、视觉层级与双端交互核查（对应 `R1-W4`、`R1-R2`，`frontend-experience-review` 设计模式）**
   - 亲自核查作者重生成的代表性截图（`pin-error-desktop-728.png`、`pin-error-mobile-390.png`、`connected-mobile-390.png`、`revoked-desktop-728.png`）并使用 `html_preview` 额外独立渲染核查 `390px` 窄屏下的 `revoked` 状态：
     - 控制栏高亮与画面状态严格一一对应，无首轮错位；
     - 数字验证码错误重试态（`pin_error`）在桌面居中弹窗与 `390px` 底部抽屉中均直接呈现红框输入、清晰可读的原因提示与「重新扫码 / 确认绑定」操作，空值或非数字输入自动禁用提交；
     - 登录失效（`revoked`）卡片已隐藏无效的「重连」按钮并将「重新扫码」提升为主按钮（`im-btn-primary`），双通道均已添加时顶部 `+ 添加通道` 自动禁用，操作主次与状态语义自明协调；
     - 原生 iOS 端 `AgentChannelsView.swift` 已明确 `+ 添加通道` 提供飞书/微信分流（选择微信给出电脑/网页端扫码引导，飞书未添加时仍可正常配置飞书）并纳入 `AgentContractsTests.swift`。
6. **`delta-spec` 与 Milestone 边界复核（对应 `R1-W3`、`R1-W5`）**
   - 逐文件程序化比对 `origin/develop` canonical 标题与 Scenario：
     - `specs/gateway/external-channels.md`：`2 ADDED` + `3 MODIFIED`（精确匹配 `IM 托管的外部 channel 可热调和并离线自治`、`自动获取消息附件不访问任意网络目标`、`PA 飞书主人私聊身份与交付`），去除内部 `-14` 字面量，补齐微信纯文本运行信息页脚与单会话审批分流，总数 `17 + 2 = 19` 与 `specs/gateway/spec.md` 一致；
     - `specs/gateway/routing-delivery.md`：`2 MODIFIED`（精确匹配 `当前会话的 Agent 图片与文件回复具有统一交付语义` 并完整保留全部 11 个既有 Scenario 扩展外部私聊 `local_images` 与离线暂存恢复；精确匹配 `Agent 可通过短标识下载受保护会话附件` 并保留原有 2 个 Scenario），总数保持 `26` 不变；
     - `specs/im/agents-nodes.md`：`1 MODIFIED`（精确匹配标题并保留全部既有 Scenario，补齐禁 REST 明文直传微信凭据与 iOS 添加引导），总数保持 `56` 不变。
   - `M1` 已前移纳入 `packages/channels/package.json`、`pnpm-lock.yaml`（`sharp` 与 `silk-wasm` 函数内动态 `import()`）及 `scripts/e2e-up.sh`（持久化 `NANO_WECHAT_E2E_BASE_URL` 至 `.gateway-config.yaml` 与 `.e2e-ports.env`），`M1` 与 `M2` 均可独立构建并闭环验证。

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核实证据 | 状态 |
|---|---|---|---|
| `R1-C1` | `accepted` — 将 `messaging.ts`、`schema.sql` 与 `db.ts` 幂等视图迁移纳入 `design.md` 及 `M1` | `design.md` 第 24-27、123、156-158、300、324 行已补齐 `matchesExternalChannel`、`provider_facts` 与 `owner-direct-wechat-view-v1` 视图重建，闭合 PA `external-incoming` 与 `owner_only` 链路 | `closed` |
| `R1-C2` | `accepted` — 设计 `stageOutboundImage` 本机暂存 → 微信直发 → `flush()` 影子会话幂等补传双阶段出站图片流 | `design.md` 第 19-20、26、132、224、325 行及 `specs/gateway/routing-delivery.md` 第 5-59 行已打通 `SingleThread`、`GlobalAgent` 与 `PA` 主人外部私聊的离线/在线发图闭环 | `closed` |
| `R1-C3` | `accepted` — 明确 `SingleThread` 卡片/口令互斥与 `Global/PA` `return_to_agent` 分流，补齐中止清理 | `design.md` 第 19、137、229-231、282、312、325 行与 `specs/gateway/external-channels.md` 第 30-45 行已明确模式边界、Stage 4 双角色覆盖与未决审批自动失效 | `closed` |
| `R1-W1` | `accepted` — `ManagedChannels` 异步停启、`purgeChannel`、`editing_channel_id`/完整登录状态机、`partial_text` 子串序号 + MD5 | `design.md` 第 18、109-120、163-170、220-221、324-325 行及 `specs/gateway/external-channels.md` 第 50、64-68 行均已完整收口 | `closed` |
| `R1-W2` | `accepted` — 清理 `single-thread`、`attention`、`store`、`global-agent`、`configuration`、`external` 硬编码 `'feishu'` | `design.md` 第 19-22、49、124、223、234、324 行已逐文件落实 `source: 'WeChat'`、主人 `roleAccountId`、`supportsReactions` 门禁与纯文本运行页脚 | `closed` |
| `R1-W3` | `accepted` — `package.json`/`pnpm-lock.yaml` 前移至 `M1`、动态 `import()`、`e2e-up.sh` 环境持久化 | `design.md` 第 14-15、30、143、295、311、324 行已消除里程碑依赖倒置与守护进程重启漏公网风险 | `closed` |
| `R1-W4` | `accepted` — 更新 `prototype.html`（`pin_error`、`revoked` 主按钮、重渲染双端截图）与 iOS 添加分流设计 | 核实 `prototype.html` 第 545-621 行、更新后的 `728px`/`390px` 截图及本轮独立 `390px` `revoked` 渲染画面，以及 `design.md` 第 241-273 行，视觉与操作层级清晰闭合 | `closed` |
| `R1-W5` | `accepted` — 更新 `routing-delivery.md`、`agents-nodes.md` 与 `external-channels.md` | 核实三份 delta-spec 标题与 canonical 100% 精确匹配，完整保留既有 Scenario 并补齐外部私聊 `local_images`、禁 REST 明文凭据及无错误码字面量约束 | `closed` |
| `R1-R1` | `accepted` — 合并转发防注入边界提示与纯文本单条目审批匹配 | 已落实于 `design.md` 第 127、137、214、231 行与 `specs/gateway/external-channels.md` 第 24、36 行 | `closed` |
| `R1-R2` | `accepted` — 纳入 `AgentContractsTests.swift` | 已落实于 `design.md` 第 29、260、324 行 | `closed` |

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R2-R1`（Stage 5 契约归并提示）**：`specs/gateway/external-channels.md` 中 `MODIFIED Requirement: PA 飞书主人私聊身份与交付` 为精确锚定 canonical 原标题保留了旧名；Stage 5 归并至 `docs/specs/gateway/external-channels.md` 时可原地将该条标题同步泛化为 `PA 外部主人私聊身份与交付`（保持 `External Channels` 总数 `19` 条不变并通过 `./scripts/docs-check`）。

### Author Resolutions

- **`R2-R1`**: `accepted` — 同意该建议；设计期保持原 canonical 标题以便锚定比对，不额外改动受审设计文件；在 Stage 5 归并 `docs/specs/gateway/external-channels.md` 时核验全仓锚点引用后同步泛化标题并运行 `./scripts/docs-check`。
