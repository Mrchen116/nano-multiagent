# feat-794: 微信外部通道（WeChat Channel） — 技术方案

> 对齐: spec.md v1

## Changelog

## 现状分析

### 涉及范围

基于最新 `origin/develop`（`3fafe61c5`）逐模块核查，本单元涉及范围如下：

- **`packages/product-contracts/src/node-rpc.ts`**：集中定义 IM → Node 的强类型 WS RPC 命令表（`nodeCommands`）。新增 `node.wechat.setup.request`（对应回包 `node.wechat.setup.result`），承载节点侧个人微信二维码获取（含可选 `editing_channel_id`）、长轮询状态查询、手机数字验证码提交与取消操作。
- **`packages/channels/package.json` 及 `packages/channels/src/`（新增 `wechat/` 子模块并从 `index.ts` 导出）**：
  - 在 `M1` 一次性完成 `qrcode`（及 `@types/qrcode`）、`silk-wasm`、`sharp`（复用仓内已锁定的 `0.35.5`）依赖声明，其中 `sharp` 与 `silk-wasm` 在媒体处理函数内采用动态按需 `import()` 加载，确保未启用微信通道或纯文本收发时零原生/WASM 初始化开销；
  - 实现腾讯官方 iLink Bot 协议客户端、AES-128-ECB 流式限额加解密、矢量二维码 SVG 生成、`WeChatLoginCoordinator` 完整扫码/重定向/验证码状态机、`<appmsg>` / `<recordinfo>` 有界无实体 XML 解析、双层语音（转写优先 + `PCM`/`SILK` 转 `WAV` 兜底）、原图 EXIF 方向修正与合规缩放、局部子串出现序号引用缓存 `WeChatQuoteStore`、出站 Markdown 净化与 3,500 码点围栏安全分段、正在输入状态与异步“先停后起”单轮询 `WeChatConnection`。
- **`packages/personal-assistant/src/{managed-channels,external,external-store,single-thread,global-agent,personal-assistant,attention,store}.ts`**：
  - `ManagedChannels`：将 `provider` 扩展为 `'feishu' | 'wechat'`；把 `Runtime.stop(): Promise<void> | void`、`drop`、`apply`、`reconnect`、`purgeAgent`、`revoke`、`stop` 全面升级为异步串行等待在途 `getupdates` 完全退出；在 `manifest.removals` 与 `purgeAgent` 中新增 `purgeChannel({ channelId, agentId, provider })` 回调，确保即使通道已先停用或报错不在 `this.instances` 中，删除时仍彻底清理本地 `<nodeHome>/wechat-state/<channel_id>.sqlite3`；
  - `ExternalChannels` & `ExternalStore`：按 `${provider}:${agentId}` 复合键隔离连接；泛化影子会话创建与查询、运行信息页脚（飞书卡片 vs 微信纯文本尾注）、未知发送提示文案；仅在 `connection.supportsReactions === true`（飞书）时启用 `agent_receipt` 与表情反应（避免微信 Global 会话调用飞书表情抛错）；新增出站本地图片暂存（`stageOutboundImage`）与影子会话重连幂等补传、入站非光栅附件缓存，以及 `SingleThread` 微信文本工具审批口令前置拦截、互斥结算与 `/stop` / `/new` / 轮次终结自动清理未决审批；
  - `single-thread.ts`、`attention.ts`、`store.ts`、`global-agent.ts`、`personal-assistant.ts`：清理全部硬编码 `'feishu'` 分支——修正 `single-thread.ts:371` 模型 `contextEnvelope` 来源标注为 `'WeChat'`、第 `312` 行向微信主人私聊注入 `{ roleAccountId: binding.ownerId }`；扩展 `attention.ts` 与 `store.ts:626`（按 `external:<agentId>:<provider>:` 解析真实 `channel`）；在 `global-agent.ts:1100-1101, 1142, 1157` 与 `personal-assistant.ts:480-491, 584` 打通 `wechat` / `feishu` 私聊出站 `local_images` 本地暂存与无文本交互卡拦截。
- **`apps/node/src/{main,configuration,file-transfer}.ts`**：
  - `main.ts` 装配 `WeChatLoginCoordinator`、`ManagedChannels`（含飞书与微信工厂及 `purgeChannel`）、`ExternalChannels`（含按平台解析的 `runtimeFooter` 与 `stageOutboundImage`）、`handlers['node.wechat.setup.request']` 及 `updater` 忙碌门禁；`configuration.ts` 支持 `display.platforms.wechat.runtime_footer`；
  - `file-transfer.ts` 的 `downloadAttachment` 扩展支持读取本节点 `ExternalChannels` 已验权持久化的当前 `agentId` 归属 `external:` 附件，保障在线与离线均可执行 `download_attachment`。
- **`apps/im-server/src/{channels,messaging,personal-agent,personal-actions,schema.sql,db}.ts`**：
  - `channels.ts` 扩展 `wechat` 配置校验、身份指纹、删除回执摘要、禁止客户端直传明文 `wechat` 凭据守卫，以及 `POST /im/v1/agents/:agent_id/channels/wechat/setup` 端点；
  - `messaging.ts`（第 `420-422` 行 PA 唯一入站端点 `incomingExternalSource` 与第 `603` 行 `provider_facts` 保留）、`personal-agent.ts`（`externalChannel`、`ownerConversation`、`sourceFacts`、`batchConversationMeta`）、`personal-actions.ts`（`transport` 及主人外部私聊图片附件放行）统一通过共享辅助函数兼容 `feishu`（`app_id` + `owner_open_id`）与 `wechat`（`bot_id` + `owner_user_id`）；
  - `schema.sql` 更新 `owner_direct_agent_messages` 视图覆盖 `feishu` 与 `wechat` 主人私聊，并在 `db.ts` 新增幂等 `schema_migrations`（`owner-direct-wechat-view-v1`）执行 `DROP VIEW IF EXISTS owner_direct_agent_messages; CREATE VIEW ...`，确保已有 SQLite 库自动升级该视图及依赖它的 `personal_observation_event` 触发器。
- **`src/IM/frontend/src/features/settings/agents/{channel-provider-registry,agent-channels-panel,im-agent-config-api}.ts*`、`i18n/{zh,en}.json`**：扩展 `wechat` 提供商描述、交互式二维码/数字验证码（含校验失败重试与提交锁）弹窗、重新扫码主恢复按钮（在 `wechat_token_revoked` 下隐藏无效的「重连」按钮）。
- **`src/IM/ios/NanoIM/Features/Agents/{AgentChannelsView,AgentChannelModels}.swift` 及 `src/IM/ios/Tests/AgentContractsTests.swift`**：`+ 添加通道` 改为提供商选择（支持添加未占用的飞书，选择微信时给出网页/桌面端扫码绑定引导），已绑定微信分组展示掩码账号与状态并支持启停/重连/删除，移除非飞书行的飞书编辑表单与权限外链。
- **`scripts/e2e-wechat-twin.mjs`（新增）与 `scripts/e2e-up.sh`**：提供隔离可控 iLink + CDN 测试桩，并在 `e2e-up.sh` 中将 `NANO_WECHAT_E2E_BASE_URL` 持久化写入隔离 `.gateway-config.yaml` 的 `gateway.environment` 与 `.e2e-ports.env`。

### 既有约束

- **跨包依赖红线（[SPEC.md](../../../SPEC.md) & `test_runtime_dependency_contract.py`）**：`apps/im-server` 与 `packages/channels` 仅依赖 `packages/product-contracts`；IM Server 绝不直连外部微信服务，所有二维码轮询、消息长轮询与媒体加解密均在节点（`apps/node` + `packages/channels`）运行。
- **凭据零回显与离线自治**：`bot_token` 仅以节点通道公钥封装的 `X25519-HKDF-SHA256-AES-256-GCM` 信封落库于 `agent_channels.credential_envelope_json` 并同步到节点 `channels.sqlite3`；绝不写入 `config.yaml`、日志或浏览器可读响应，且禁止客户端经普通 REST `POST/PATCH` 直传明文微信令牌。
- **防 SSRF 与受控媒体边界（[external-channels.md](../../specs/gateway/external-channels.md)）**：通道层仅访问严格匹配 `https://*.weixin.qq.com` 的官方地址（含 `scaned_but_redirect` 域名校验，统一 `redirect: 'error'`，仅隔离环境显式配置 `NANO_WECHAT_E2E_BASE_URL=http://127.0.0.1:<port>` 时允许本地测试桩 origin），**绝不在通道入站预处理或出站渲染阶段自动抓取公众号文章或任意外部 URL**。
- **范围收敛红线**：不引入 `<persona-context>` 提示词段注入，不改动跨会话记忆归档架构，不改变根主 Agent 静态系统提示词前缀缓存（`verify-context-cache-prefix`），不改变 `Global / PA` 既有 `return_to_agent` 审批路由。

### 可复用能力

- **复用 `ChannelKey` 与 `sealChannelSecret`**：直接封装 `{ bot_token }`，共享现有通道 manifest 同步与删除回执状态机。
- **复用 `ModelSetup` 异步后台任务 + 短轮询模式**：避免阻塞 10 秒 `node-rpc` 超时窗口。
- **复用 `feat-786` 通用文件上传与短引用 `download_attachment`**：打通微信 PDF/Office/代码/视频与无转写 `WAV` 语音在影子会话与工作区受控目录的落盘读取。
- **复用仓内已锁定的 `sharp@0.35.5`**：按需动态加载完成原图 EXIF 旋转修正与 `<= 10 MiB / 4096px` 尺寸收敛。
- **复用 `SingleThread.permission` 与 `dsh-integration` `approval.answer` 仲裁源**：为 `single_thread` 会话提供微信文本审批与内部 IM 审批卡片的单一真值互斥。

### 相关历史

- `feat-447` / `feat-464` / `feat-501`：建立外部通道影子会话（标题按现有实现约定为 `${agentId} · ${provider}`）、IM 托管密文 manifest、触发源路由与 `/new` `/stop` `/compact` 跨端控制。
- `feat-503`：确立外部通道隔离 E2E 不触碰个人配置与生产机器人的准则。
- `refactor-783`：建立 `packages/product-contracts/src/node-rpc.ts` 双端强类型命令表。
- `feat-786`：建立通用文件上传与 `download_attachment` 短引用，当时显式留白了外部通道非图附件适配。
- `feat-790` / `feat-791`：Desktop 客户端复用 `src/IM/frontend/`，Web 通道页增量同步生效于 Desktop。

## 架构总览

下图展示新增个人微信通道后的跨包静态结构与职责边界：IM Server 仅负责鉴权、幂等视图维护、转发轻量扫码状态与公钥密封期望配置；Node 与 `@nano/channels` 独占持有 iLink 长轮询、AES 媒体加解密、出站图片本机暂存与本地受保护状态。

```mermaid
flowchart LR
  subgraph Clients["客户端 (Web / Desktop / iOS)"]
    WebUI["Web & Desktop 通道页\n(扫码 / 验证码 / 重新扫码)"]
    IOSUI["原生 iOS 通道页\n(添加引导 / 状态查看 / 启停 / 重连 / 删除)"]
  end

  subgraph Center["apps/im-server"]
    IMChan["ChannelService & WeChat Setup API\n(公钥密封凭据 · 禁明文直传)"]
    IMAuth["messaging.ts + PersonalAgents/Actions\n+ owner_direct_agent_messages 视图迁移"]
    IMMedia["Media & Shadow Conversations\n(<agentId> · wechat)"]
  end

  subgraph Contracts["packages/product-contracts"]
    NodeRPC["node-rpc.ts\n(node.wechat.setup.request)"]
  end

  subgraph NodeHost["apps/node + packages/personal-assistant"]
    LoginCoord["WeChatLoginCoordinator"]
    Managed["ManagedChannels\n(异步先停后起 · purgeChannel)"]
    Ext["ExternalChannels & ExternalStore\n(复合键 · 图片双阶段投递 · 审批互斥)"]
    FileXfer["file-transfer.ts\n(download_attachment 兼容本机 external:)"]
  end

  subgraph WeChatPkg["packages/channels/src/wechat"]
    WConn["WeChatConnection\n(单轮询 · owner 门禁 · -14 止损)"]
    WCodec["iLink Client + AES-128-ECB\nXML 卡片/合并转发 · 双层语音 · QuoteStore"]
  end

  subgraph Upstream["微信官方服务 / 隔离测试桩"]
    ILink["ilinkai.weixin.qq.com & novac2c CDN\n(或本机 e2e-wechat-twin)"]
  end

  WebUI --> IMChan
  IOSUI --> IMChan
  IMChan -. "WS RPC (node-rpc)" .-> LoginCoord
  IMChan -. "channel.reconcile (密文信封)" .-> Managed
  LoginCoord --> WCodec
  Managed --> WConn
  WConn <--> Ext
  WConn --> WCodec
  WCodec <--> ILink
  Ext <--> IMMedia
  Ext <--> IMAuth
  FileXfer --> Ext
```

## 关键决策

1. **节点执行完整扫码/重定向/验证码状态机，确认后在 IM Server 事务内直接公钥密封落库，全程拒绝浏览器接触或提交明文令牌。**
   - **理由**：完整对齐上游 `get_bot_qrcode` / `get_qrcode_status` 状态集：
     - `wait` → `waiting_scan`；`scaned` → `scanned`；
     - `scaned_but_redirect` → 严格校验 `redirect_host` 匹配 `^[a-z0-9.-]+\.weixin\.qq\.com$` 后切换轮询 HTTPS 域名（防 SSRF）；
     - `need_verifycode` / `confirmed_but_need_verifycode` → `need_verify_code`（若刚提交过 `verify_code` 仍返回该状态则标记 `error_code: 'wrong_verify_code'` 供前端原位提示重试而不丢弃会话）；
     - `verify_code_blocked` → 终止当前码并返回 `failed (verify_code_blocked)` 提示重新取码；
     - `expired` → 节点自动换新二维码最多 3 次，超限返回 `expired` 供手动刷新；
     - `binded_redirect`（重绑传入 `local_token_list` 时上游不发新 token）→ 仅当 `editing_channel_id` 对应当前节点仍持有未失效的本地令牌时直接沿用原凭据完成确认；若旧令牌已失效或缺失，节点自动以空 `local_token_list` 重新申请全新二维码，确保必定拿到新 `bot_token`；
     - `confirmed` → 节点通过内部 WS 回包一次性向 IM 返回 `{ bot_token, bot_id, owner_user_id, base_url }`，IM 在同一事务中调用 `sealChannelSecret` 写入 `agent_channels` 并剥离明文返回 `AgentChannelView`，同时在普通 `POST/PATCH /channels` 拒绝客户端直传 `wechat` 明文凭据。

2. **异步串行“先停后起”单轮询与 `purgeChannel` 全路径清理，杜绝双轮询互抢与停用后删除残留。**
   - **理由**：将 `ManagedChannels` 的 `Runtime.stop()` 改为返回 `Promise<void>`，`apply`、`reconnect`、`drop`、`revoke`、`stop` 均 `await` 旧 `WeChatConnection` 中断在途 `AbortController` 并完全退出循环后才启动新实例。收到 `errcode === -14` 或 `ret === -14` 时立即退出轮询、清除该通道动态游标与引用表并上报 `status_code: 'wechat_token_revoked'`。在 `manifest.removals` 与 `purgeAgent` 中统一调用 `purgeChannel({ channelId, agentId, provider })`，保证“先停用或 `-14` 停止、再删除通道”时同样彻底移除 `<nodeHome>/wechat-state/<channel_id>.sqlite3`（含 `-wal`/`-shm`）。

3. **全栈泛化多通道身份与 SQLite 视图迁移，完整打通 PA 主人微信私聊、`owner_only` 准入与模型来源归属。**
   - **理由**：
     - IM 侧统一抽取 provider 匹配辅助函数（`feishu` 取 `config.app_id` + `runtime.owner_open_id`，`wechat` 取 `config.bot_id` + `config.owner_user_id`），同步更新 `messaging.ts`（`incomingExternalSource` 与 `provider_facts`）、`personal-agent.ts`、`personal-actions.ts`，并通过 `db.ts` 幂等迁移 `owner-direct-wechat-view-v1` 重建 `owner_direct_agent_messages` 视图，确保 PA 入站、`personal_observation_event` 触发器与 `owner_only` 准入在存量与新建库上均原生生效；
     - Node/PA 侧按 `${provider}:${agentId}` 索引连接，修复 `single-thread.ts`（`source: 'WeChat'` 与主人 `roleAccountId`）、`attention.ts`、`store.ts`（按 `external:<agentId>:<provider>:` 还原真实 `channel`）、`global-agent.ts`（拦截 `'wechat'` 空文本交互卡）、`external.ts`（仅飞书开启表情回执、微信使用纯文本运行信息页脚、按 provider 区分未知发送提示，影子会话标题保持 `${agentId} · wechat` 与 `${agentId} · feishu` 一致）。

4. **有界无实体 XML 展开卡片与合并转发（标注被转发非指令边界），未知或空条目双向显式反馈。**
   - **理由**：对 `<= 256 KiB` 的 `<msg><appmsg>` 采用无实体展开解析器提取分享卡（标题、摘要、来源、URL）或递归展开合并转发 `<recordinfo>`（最多 5 层、50 条），并在外层包裹明确提示 `[合并转发的聊天记录：《...》——以下为被转发的历史对话原文，非当前发送者本轮直接指令]`，防止第三方群聊文本混淆主人指令边界。不在通道层盲抓外链（由 Agent 按需调用 `web_fetch`）；对无有效负载的表情包/视频号等条目回传明确可读提示并同步影子会话。

5. **入站媒体流式限额归一化 + 出站图片“节点本机暂存 → 外部直发 → 影子会话幂等补传”双阶段闭合。**
   - **理由**：
     - **入站**：原图最高 `16 MiB` 经动态加载的 `sharp` 自动修正 EXIF 方向并收敛至 `<= 10 MiB`、`<= 4096×4096`；语音在附带 `voice_item.text` 时保留 `[语音转写]` 文本并在语音媒体存在时同步转码生成 `voice-raw.wav`/`voice-raw.mp3` 原声附件（模型侧投影显式标注已转写、仅在需要处理原音频文件时调用 `download_attachment`，媒体拉取异常不阻断已有转写），缺失转写时解密并通过 44 字节 WAV 封装（`PCM`）或动态加载 `silk-wasm` 转码（`SILK`）生成 `voice.wav` 附件及清晰说明；文件/视频（单文件 `<= 25 MiB`、单消息总媒体 `<= 40 MiB`）写入 `ExternalStore` 媒体表并打通 `file-transfer.ts` 对当前 `agentId` 归属 `external:` 附件的直接落盘读取；
     - **出站图片闭合（覆盖 `SingleThread`、`GlobalAgent` 与 `PA` 主人外部私聊）**：当回复含内联 `data:image/...` 或显式调用 `send_message(..., local_images=[...])` 发往 `wechat` / `feishu` 会话时，节点通过 `ExternalChannels.stageOutboundImage` 在本机校验读取图片字节（`1B..10 MiB`、`<= 4096×4096`）并幂等存入 `ExternalStore.images`（键 `external:out:${operationId}:${index}`），**不依赖中心 IM 在线即可先由 `WeChatConnection.send` 加密上传微信 CDN 作为 `image_item` 发出**；待 IM 在线且 `shadowId` 就绪时，`ExternalChannels.flush()` 自动将该本地图片幂等上传至 `/im/v1/conversations/${shadowId}/images?screenshot=1` 并替换为真实 IM 附件 URL 写入影子会话（同时在 `personal-actions.ts` 允许 `ownerConversation` 下的外部传输提案携带图片或纯图消息，保持非主人会话与 `dsh-integration` 私有证据 `ask` 拦截边界不变）。

6. **局部引用采用上游子串出现序号 + MD5 消歧算法；工具审批严格区分 `SingleThread` 卡片互斥与 `Global / PA` 对话内确认，并在轮次终结时自动清理未决项。**
   - **理由**：
     - **局部引用（`partial_text`）**：严格遵循 iLink 真实语义——`startindex` / `endindex` 为子串 `start` / `end` 的 0-based 第 N 次出现序号（同时计算全文计数与 `start` 后相对计数两个候选，存在 `quotemd5` 时用 MD5 精确校验消歧），失配时回退整条缓存或 `ref_msg.title`；
     - **模式分流与僵尸审批清理**：在 Nano 运行时中，`Global` 与 `PA` 采用 `return_to_agent` 自然语言对话确认（不生成 `permission_request` 卡片），仅 `SingleThread` 生成内部 IM 审批卡片。对 `SingleThread` 微信会话：仅当入站消息为**不含 `<appmsg>` 转发块且不含非审批消息 `ref_msg` 的单条纯文本**且精确匹配允许/拒绝口令时才触发 `SingleThread.permission` 仲裁，与内部 IM 卡片先到生效、后到回执“已处理”；一旦会话发生 `/stop`、`/new`、轮次终结/丢弃或 Agent 停用，立即将该会话未决 `approvals` 置为已取消，杜绝残留状态误吞后续 `"1"` 或 `"同意"` 消息。

7. **双端体验细节收口：Web 强化验证码错误重试与失效卡片主恢复动作，原生 iOS 提供清晰的提供商选择与网页扫码引导。**
   - **理由**：在 `wechat_token_revoked` 状态下隐藏无效的「重连」按钮并将「重新扫码」提升为主按钮；验证码输入支持格式校验、提交中防重及错误原位提示重试；原生 iOS 点击 `+ 添加通道` 弹出「飞书 / 微信」选择（飞书未添加时进入飞书配置，选择微信时弹出清晰说明引导在电脑或网页端扫码绑定），彻底消除写死飞书的问题。

8. **双层验收与隔离守护进程环境持久化。**
   - **理由**：`e2e-up.sh` 将 `NANO_WECHAT_E2E_BASE_URL` 写入隔离 `.gateway-config.yaml` 的 `gateway.environment` 与 `.e2e-ports.env`，确保节点守护进程重启仍锁定本地测试桩；通过自动化与 Stage 4 独立审查后、提 PR 前拉起真实微信上游隔离预览由用户真机扫码实测。

## 接口与数据流

### 1. IM Server 通道管理、扫码设置与 PA 主人鉴权（`apps/im-server/src/{channels,messaging,personal-agent,personal-actions,schema.sql,db}.ts`）

- **Provider 配置与明文写入守卫**：
  - `provider === 'wechat'`：`config` 为 `{ bot_id: string, owner_user_id: string, base_url: string }`；身份指纹 `sha256("wechat\0" + bot_id + "\0" + owner_user_id)`；删除摘要 `{ bot_id_suffix: bot_id.slice(-6), owner_user_id_suffix: owner_user_id.slice(-4) }`。
  - 普通 `POST /im/v1/agents/:agent_id/channels` 对 `provider === 'wechat'` 直接返回 `422 channel_interactive_setup_required`；`PATCH .../channels/:channel_id` 对 `wechat` 仅允许 `credentials: { mode: 'keep' }` 且 `config` 不变（用于启停切换），拒绝任何客户端直传明文凭据。
- **扫码绑定设置端点 `POST /im/v1/agents/:agent_id/channels/wechat/setup`**：
  - 校验 `owner` 权限、节点在线、`node_credential_keys` 已注册；新建时若已有 `wechat` 通道在 `start` 返回 `409 channel_provider_already_exists`；重绑传 `editing_channel_id` + `channel_revision` 时做乐观锁校验。
  - 请求体：`{ action: 'start' | 'status' | 'verify_code' | 'cancel', setup_id?: string, code?: string, editing_channel_id?: string, channel_revision?: number }`。
  - 响应体：`{ setup_id: string, state: 'waiting_scan' | 'scanned' | 'need_verify_code' | 'confirmed' | 'expired' | 'failed' | 'cancelled', qr_svg?: string, expires_at?: string, error_code?: string, message?: string, channel?: AgentChannelView }`（`confirmed` 时事务内密封 `bot_token` 落库并下发 `channel.reconcile`，绝不返回明文 `bot_token`）。
- **PA 外部入站与 `owner_direct_agent_messages` 视图迁移**：
  - 抽取 `matchesExternalChannel(row, chat)`：对 `feishu` 匹配 `feishu:${config.app_id}:${group|dm}:`（主人为 `runtime.owner_open_id`），对 `wechat` 匹配 `wechat:${config.bot_id}:dm:${config.owner_user_id}`（主人为 `config.owner_user_id`），复用于 `messaging.ts:incomingExternalSource`、`personal-agent.ts` 与 `personal-actions.ts:transport`；`messaging.ts` 在 `c.external_source === 'feishu' || c.external_source === 'wechat'` 时统一保留 `provider_facts`。
  - `schema.sql` 与 `db.ts`（`owner-direct-wechat-view-v1`）同步更新 `owner_direct_agent_messages` 视图，将 `wechat` 本人单聊纳入 `owner_direct` 真值与 `personal_observation_event` 触发器。

### 2. IM → Node 强类型 WS RPC（`packages/product-contracts/src/node-rpc.ts`）

在 `nodeCommands` 中新增 `'node.wechat.setup.request'`（响应 `'node.wechat.setup.result'`）：
- 输入 schema（`z.discriminatedUnion('action', ...)`）：
  - `{ action: 'start', agent_id: id, editing_channel_id?: id }`
  - `{ action: 'status', agent_id: id, setup_id: id }`
  - `{ action: 'verify_code', agent_id: id, setup_id: id, code: z.string().regex(/^\d{1,12}$/) }`
  - `{ action: 'cancel', agent_id: id, setup_id: id }`
- 输出 schema：
  - `{ setup_id: id, state: z.enum(['waiting_scan', 'scanned', 'need_verify_code', 'confirmed', 'expired', 'failed', 'cancelled']), qr_svg?: text, expires_at?: text, error_code?: text, message?: text, binding?: z.object({ bot_token: id, bot_id: id, owner_user_id: id, base_url: id }).optional() }`。

```mermaid
sequenceDiagram
  participant Web as Web 通道页
  participant IM as IM Server (channels.ts)
  participant Node as Node (WeChatLoginCoordinator + ManagedChannels)
  participant iLink as 微信 iLink / 本地测试桩

  Web->>IM: POST /im/v1/agents/:id/channels/wechat/setup {action:"start", editing_channel_id?}
  IM->>Node: WS node.wechat.setup.request {action:"start", agent_id, editing_channel_id?}
  Node->>iLink: POST /ilink/bot/get_bot_qrcode?bot_type=3 {local_token_list}
  iLink-->>Node: {qrcode, qrcode_img_content}
  Node-->>IM: node.wechat.setup.result {setup_id, state:"waiting_scan", qr_svg}
  IM-->>Web: 200 {setup_id, state:"waiting_scan", qr_svg}

  loop 后台长轮询（含 scaned_but_redirect 域名校验 / binded_redirect 收敛）与前端 1.5s 查询
    Node->>iLink: GET /ilink/bot/get_qrcode_status?qrcode=...
    Web->>IM: POST .../wechat/setup {action:"status", setup_id}
    IM->>Node: WS node.wechat.setup.request {action:"status", setup_id}
    alt 手机要求数字验证码 (need_verifycode / confirmed_but_need_verifycode)
      Node-->>IM: {state:"need_verify_code", error_code?}
      IM-->>Web: {state:"need_verify_code", error_code?}
      Web->>IM: POST .../wechat/setup {action:"verify_code", setup_id, code}
      IM->>Node: WS {action:"verify_code", setup_id, code}
      Node->>iLink: GET /ilink/bot/get_qrcode_status?qrcode=...&verify_code=...
    end
  end

  iLink-->>Node: {status:"confirmed", bot_token, ilink_bot_id, ilink_user_id, baseurl}
  Web->>IM: POST .../wechat/setup {action:"status", setup_id}
  IM->>Node: WS {action:"status", setup_id}
  Node-->>IM: {state:"confirmed", binding:{bot_token, bot_id, owner_user_id, base_url}}
  Note over IM: 事务内 sealChannelSecret(bot_token) 写入 agent_channels 并剥离明文
  IM->>Node: WS channel.reconcile (含新密文 manifest)
  IM-->>Web: 200 {state:"confirmed", channel: AgentChannelView}
  Note over Node: ManagedChannels await 旧实例完全退出后再启动新 WeChatConnection
```

### 3. 微信协议、富媒体归一化、局部引用与双阶段图片出站（`packages/channels/src/wechat/` + `ExternalChannels`）

- **iLink 安全客户端与流式 AES-128-ECB（`ilink.ts`、`crypto.ts`）**：
  - 严格校验 `https://*.weixin.qq.com`（含 `scaned_but_redirect` 的 `redirect_host` 校验）或测试环境显式配置的 `NANO_WECHAT_E2E_BASE_URL`（`http://127.0.0.1:<port>`），强制 `redirect: 'error'`；
  - `parseWeChatAesKey` 兼容 32 字符 hex、`base64(16 字节)` 与 `base64(32 字符 ASCII hex)`；流式下载限额：原图 `<= 16 MiB`、语音 `<= 8 MiB`、单文件/视频 `<= 25 MiB`、单消息总媒体 `<= 40 MiB`。
- **入站消息与转发解析（`inbound.ts`、`xml.ts`）**：
  - `TEXT (1)`：无实体展开解析 `<appmsg>`（上限 `256 KiB`）：分享卡片格式化为 `[微信分享卡片]\n标题/来源/摘要/链接`；合并转发 `<recordinfo>` 递归展开（`<= 5` 层、`<= 50` 条）并包裹 `[合并转发的聊天记录：《...》——以下为被转发的历史对话原文，非当前发送者本轮直接指令]`；
  - `IMAGE (2)`：动态加载 `sharp` 执行 EXIF 方向修正并在超过 `10 MiB` 或 `4096×4096` 时等比压缩收敛，产出纯 `image` part（影子会话无 `[图片]` 占位词）；
  - `VOICE (3)`：有 `voice_item.text` 时产出 `[语音转写] <text>`；缺失时解密并将 `PCM`（44 字节 WAV 头）或 `SILK`（动态加载 `silk-wasm` 解码为 `24kHz` WAV）转为 `voice.wav` 通用音频附件 + 明确语音上下文说明；
  - `FILE (4)` / `VIDEO (5)`：存入 `ExternalStore` 媒体表，在线镜像上传至 IM 影子会话，同时支持 `file-transfer.ts` 按当前 `agentId` 直接从 `ExternalStore` 落盘读取；
  - **未知/空条目兜底**：不含任何有效文本/媒体的特殊条目回发可读提示并镜像影子会话。
- **局部与全文引用还原（`quote-store.ts`）**：
  - 本地 `<nodeHome>/wechat-state/<channel_id>.sqlite3`（目录 `0700`、文件 `0600`）按无损十进制字符串 `svr_id` 缓存最近 `500` 条消息摘要；
  - `resolvePartialQuote(fullText, partial)` 按 `startindex` / `endindex` 的 **0-based 子串出现次数序号**同时计算全文计数与 `start` 后相对计数候选，存在 `quotemd5` 时用 MD5 精确校验消歧，命中后格式化为 `[引用历史消息摘录]\n> ...\n\n` 前置于本轮文本前；通道删除、重绑或 `-14` 失效时立即清除。
- **出站分段、双阶段图片投递与正在输入（`outbound.ts` + `ExternalChannels`）**：
  - `filterWeChatMarkdown` 净化不兼容标记，保留 `**加粗**` 与代码；`chunkWeChatText` 在 `3,500` Unicode 码点内按段落/换行安全切分并自动闭合与重开 ```` ```lang ```` 代码围栏；启用运行信息页脚时仅在最终外部回复末尾追加 `\n\n—\n<model · ctx X%>`；
  - **出站图片双阶段投递**：无论来自回复内联 `data:image/...` 还是 `send_message(..., local_images)`，节点先经 `stageOutboundImage` 将校验后的图片字节持久化至 `ExternalStore.images`（`external:out:${operationId}:${index}`），立即由 `WeChatConnection.send` 经 `getuploadurl` → AES-128-ECB → CDN `POST` → `sendmessage(image_item)` 发往微信（支持 IM 离线自治）；随后在 `ExternalChannels.flush()` 同步影子会话时幂等上传至 `/im/v1/conversations/${shadowId}/images?screenshot=1` 补齐影子附件；
  - 运行期间维持 `getconfig` + `sendtyping(status=1)` 4 秒续期，结束/中止/报错时在 `finally` 发送 `sendtyping(status=2)`。

### 4. 工具权限审批模式分流与 Agent Context 工程核查

- **审批模式分流与单会话双端互斥**：
  - `Global` 与 `PA` 维持 `dsh-integration/src/policy/approval.ts` 既有的 `return_to_agent` 路由（不生成审批卡，由 Agent 在对话中自然确认）；
  - `SingleThread` 产生 `permission_request` 时，内部 IM 影子会话渲染标准审批卡，微信收到可读说明与口令提示。仅当绑定者发来**单条纯文本（无 `<appmsg>` 转发、无无关 `ref_msg`）**且精确匹配允许（`允许|同意|批准|allow|yes|1`）或拒绝（`拒绝|不同意|deny|no|2` + 可选原因）时，前置拦截调用 `SingleThread.permission`；内部 IM 先处理时同步向微信发送简短完成提示，重复口令回执“该工具审批已处理，无需重复确认”；收到 `/stop`、`/new`、轮次终态或 Agent 停用时立即清理该会话未决审批。
- **Agent Context Engineering 核查**：
  - **Consumer**：SingleThread、普通 Global 与 PA 根主会话模型；
  - **Context Lifecycle（Before → After）**：系统提示词静态前缀零改动（保持 `verify-context-cache-prefix` 稳定）；`SingleThread` 微信入站 `contextEnvelope` 准确标注 `source: WeChat` 并携带主人 `roleAccountId`；`RelayInput.metadata.channel`、`store.ts` 定时/心跳系统输入与 `conversations(info/describe)` 统一输出 `channel: 'wechat'`；合并转发与引用块显式标明被转发历史非本轮直接指令；独立原图无 `[图片]` 占位词；非图附件统一生成 `<= 8` 字符 `a_xxxxxx` 引用供 `download_attachment` 在线/离线落盘。

## 前端原型

- **要通过原型判断的设计决定**：Web 端外部通道页如何在既有框架内清晰呈现「多通道选择 → 微信待扫码 → 已扫码待确认 → 手机数字验证码输入与输错原位重试 → 二维码过期刷新 → 双通道并存卡片 / 登录失效重绑主操作」，以及原生 iOS 如何清晰引导添加与管理。
- **原型入口**：[`prototype.html`](prototype.html)（原生 iOS 端按规范跳过 HTML 原型，在下方明确完整交互状态与测试投影）。
- **用户目标与体验方案**：
  - **Web / Desktop**：沿用 `.im-channel-card` 与 `.chat-modal`（窄屏 `.chat-modal-bottom-sheet` + 顶部拖拽横条）。验证码阶段提供等宽数字输入、非数字/空值禁用提交及校验失败红色提示框（支持原位改数重试或一键重新扫码）；当微信通道处于 `wechat_token_revoked` 失效态时，**隐藏无效的「重连」按钮并将「重新扫码」提升为主按钮（`im-btn-primary`）**，消除误操作。
  - **原生 iOS（`AgentChannelsView.swift`）**：右上角 `+ 添加通道` 在飞书未添加或微信未添加时保持可点（仅节点离线或双通道均已添加时禁用），点击弹出提供商选择（飞书未添加时可进入 `AgentChannelEditor`，已添加标为“已添加”；点击微信弹出原生说明页引导前往电脑或网页版 Crewden 扫码绑定）。列表中「微信」分组展示掩码绑定账号与连接/离线状态，支持启用/停用、重连（`wechat_token_revoked` 时隐藏重连并提示网页端重扫）、删除与删除重试，彻底移除非飞书行的飞书字段、编辑表单与 `open.feishu.cn` 外链。
- **呈现方式与覆盖范围**：现有 Agent 设置「外部通道」页签背景 + 8 个可连续操作状态（选择通道、待扫码、已扫码待确认、数字验证码、验证码错误重试、二维码过期、双通道已连接、登录失效重绑）。
- **交互边界**：外框顶部深色横条为「交互原型 · 仅演示状态切换」，下方白色面板为真实产品交互结构。

### 现有 UX grounding

| 当前产品入口 | 画面与操作基线 | 沿用或改善的体验及原因 | 本次设计 |
|---|---|---|---|
| Web 助手设置「外部通道」页签（[`agent-channels-panel.tsx`](../../../src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx)、[`channel-provider-registry.ts`](../../../src/IM/frontend/src/features/settings/agents/channel-provider-registry.ts)） | 顶部说明 + `+ 添加通道`；`.im-channel-card` 展示图标、状态胶囊、掩码标识与操作组；`.chat-modal` 承载弹窗（窄屏底部抽屉） | 复用既有卡片密度与离线只读锁；针对扫码与失效恢复优化操作权重，避免把无效「重连」与「重新扫码」并列 | Provider 选择器支持飞书与微信独立占用；扫码弹窗支持二维码/已扫码/验证码（含错误提示）/过期四态；登录失效卡隐藏「重连」并高亮「重新扫码」 |
| 原生 iOS 外部通道页（[`AgentChannelsView.swift`](../../../src/IM/ios/NanoIM/Features/Agents/AgentChannelsView.swift)）与模型服务页（[`ModelServicesView.swift`](../../../src/IM/ios/NanoIM/Features/Me/ModelServicesView.swift)） | `AgentChannelsView` 当前硬编码飞书表单与外链；`ModelServicesView` 对交互式登录隐藏表单编辑、保留状态查看与移除 | 消除非飞书通道错误字段与外链，同时闭合移动端点击 `+ 添加通道` 时的微信绑定预期 | `+` 提供飞书/微信分流（微信展示网页端扫码引导）；已绑定微信行展示掩码标识与状态，支持启停/重连/删除，无飞书专属残留 |

### 原型对齐契约

| 原型区域 / 状态 | 对齐级别 | 产品入口 | 必验 viewport / 状态 | 下游验收投影 |
|---|---|---|---|---|
| 通道选择器双通道并存与占用禁用态 | `must-match` | Web `/settings/agents/:id`（外部通道 → 添加通道） | Desktop `1280×800` & Mobile `390×844`；无通道、已有飞书未加微信、双通道均已添加（`+ 添加通道` 禁用） | M1 `[reviewer]` & `[worker]` |
| 微信扫码弹窗五态流转（待扫码 / 已扫码待确认 / 数字验证码输入 / 验证码错误重试 / 过期刷新与取消） | `must-match` | Web `/settings/agents/:id`（微信绑定 / 重新扫码弹窗） | Desktop `1280×800`（居中弹窗）& Mobile `390×844`（底部抽屉带拖拽条）；含空值禁用提交、验证码输错原位提示重试与中途取消 | M1 `[reviewer]` & `[worker]` |
| 微信已连接卡片与登录失效重绑主操作卡片 | `must-match` | Web `/settings/agents/:id`（外部通道列表） | Desktop `1280×800` & Mobile `390×844`；`connected`、`failed (wechat_token_revoked)`（隐藏重连、主按钮显示重新扫码）、`disabled`、`offline` | M1 `[reviewer]` & `[worker]` |
| 原生 iOS 添加通道引导、微信状态卡片与启停/重连/删除适配 | `may-adapt` | iOS `AgentChannelsView`（助手 → 外部通道） | SwiftUI 编译与 `AgentContractsTests.swift` 契约/视图逻辑单测（验证提供商添加引导、无飞书硬编码残留、失效隐藏重连及管理请求） | M1 `[worker]` |
| 外层深色演示切换控制栏 | `out-of-scope` | 仅存在于 `prototype.html` | 真实产品不渲染该控制栏 | N/A |

### 原型走查

- **实际渲染与走查范围**：使用 `html_preview` 在桌面宽度（`728px`）与手机窄屏宽度（`390px`）逐一实际渲染并目视核查了待扫码、数字验证码正常与输错重试、双通道已连接、登录失效重绑全部关键状态，控制台零报错。
- **代表性截图定位（保存在当前会话 `scratch/prototype-screenshots/`，不提交仓库）**：
  - 桌面与窄屏待扫码态：`qr-wait-desktop-728.png`、`qr-wait-mobile-390.png`
  - 桌面与窄屏数字验证码错误重试态：`pin-error-desktop-728.png`、`pin-error-mobile-390.png`
  - 桌面登录失效重绑与窄屏双通道卡片态：`revoked-desktop-728.png`、`connected-mobile-390.png`
- **体验判断与修正**：
  1. 修正了首轮 `[hidden]` 覆盖、窄屏抽屉顶部横条及 `window.__INITIAL_SCENE__` 预览注入问题，核实验证码输入框、红色错误提示与底部按钮在 `728px` 与 `390px` 下均清晰居中且不截断；
  2. 在登录失效（`revoked`）卡片中隐藏了不可自愈的「重连」按钮并将「重新扫码」设为主按钮（同时在双通道均已添加时禁用顶部 `+ 添加通道`），阅读路径与恢复动作一目了然。
- **未验证项**：无。

## 本次审查安排

| 必须回答的问题 / 对应目标 | 能力与使用阶段 | 证据方法、范围与已有定位 |
|---|---|---|
| 跨包依赖边界、公钥密封与禁明文直传、异步先停后起与 `purgeChannel`、PA 入站与 `owner_direct_agent_messages` 视图迁移、图片双阶段投递、审批分流互斥与 delta-spec 准确性 | `change-code-review`（Stage 4 独立代码与契约审查） | 全量 `git diff origin/develop...HEAD` 审查 + `tests/contract/test_runtime_dependency_contract.py` + 各包单元与集成测试 |
| `SingleThread` `source: WeChat` 与主人 `roleAccountId`、合并转发/引用防注入边界、独立图片无占位词、短 `attachment_id` 投影及静态提示词前缀缓存零退化 | `agent-context-review`（Stage 4 专项审查） | 核查 `inbound.ts`、`external.ts`、`single-thread.ts`、`inbox.ts` 模型输入构造 + `fork-prefix-provider.test.ts` + 隔离真栈真实 LLM 会话日志 locator |
| Web 扫码/验证码（含输错重试）/过期/失效重绑界面在桌面与 `390px` 窄屏下的可读性、操作权重与原型对齐 | `frontend-experience-review`（Stage 4 界面体验审查） | 隔离真栈真实 Web 入口（`1280×800` 与 `390×844`）实测全部 `must-match` 状态与交互 |
| 端到端真实产品旅程（Web 扫码/验证码绑定 → 普通 `single_thread` Agent 含双端工具审批互斥 + `PA` 主人微信私聊与提醒 → 文本/分享卡/合并转发/双层语音/原图/文件视频/局部引用/图文分段出站）及用户真机实扫 | `product-journey-review`（Stage 4 独立产品旅程审查）+ **提 PR 前用户真机微信扫码实测** | ① 独立 reviewer 在 `e2e-up.sh --profile daily`（另建或启用一个 `single_thread` 测试 Agent 覆盖审批卡片互斥，并用 daily `PA` 覆盖主人私聊与提醒）+ 本机 `e2e-wechat-twin` 完成全链路验收；② 提交 PR 前拉起直连真实微信上游的隔离预览环境，交用户真机微信扫码实测 |

## 契约层增量 (delta-spec)

- **Gateway 外部通道契约**：[`docs/specs/gateway/external-channels.md`](../../specs/gateway/external-channels.md) → 见 [`specs/gateway/external-channels.md`](specs/gateway/external-channels.md)（新增个人微信通道收发与单会话文本审批 2 条 Requirement；修改托管通道热调和、受控附件源及 PA 主人外部单聊 3 条 Requirement，无内部错误码硬编码）。
- **Gateway 包入口索引**：[`docs/specs/gateway/spec.md`](../../specs/gateway/spec.md) → 见 [`specs/gateway/spec.md`](specs/gateway/spec.md)（更新 `External Channels` 覆盖说明并将 Requirement 数由 `17` 更新为 `19`）。
- **Gateway 路由与投递契约**：[`docs/specs/gateway/routing-delivery.md`](../../specs/gateway/routing-delivery.md) → 见 [`specs/gateway/routing-delivery.md`](specs/gateway/routing-delivery.md)（修改 `当前会话的 Agent 图片与文件回复具有统一交付语义` 放开外部私聊 `local_images` 与离线暂存同步，修改 `Agent 可通过短标识下载受保护会话附件` 支持本机已验权 `external:` 入站附件落盘；Requirement 总数保持 `26` 不变）。
- **IM 通道管理契约**：[`docs/specs/im/agents-nodes.md`](../../specs/im/agents-nodes.md) → 见 [`specs/im/agents-nodes.md`](specs/im/agents-nodes.md)（修改 Agent 通道页统一管理条款，纳入 `wechat`、Web 扫码零明文回显、禁 REST 明文直传及原生 iOS 添加引导与状态管理；Requirement 总数保持 `56` 不变，`docs/specs/im/spec.md` 为 `no spec delta`）。
- **IM 会话与消息回执契约**：[`docs/specs/im/conversations-messages.md`](../../specs/im/conversations-messages.md) → 见 [`specs/im/conversations-messages.md`](specs/im/conversations-messages.md)（修改 `真人发送的普通聊天消息提供逐人回执`，覆盖主人 1:1 外部私聊影子会话向 Global Agent / Personal Agent 的待送达 → 已送达 → 已读回执推进，保持群旁观、非主人与 SingleThread 边界不变；Requirement 总数不变，`docs/specs/im/spec.md` 为 `no spec delta`）。
- **其他领域（`gateway/personal-agent.md`、`im/personal-agent.md`、`im/ios-client.md`、`im/desktop-client.md`）**：`no spec delta`——现有条款已通过通用外部通道与管理页面契约覆盖。

## 风险与回退

- **上游微信客户端灰度差异风险**：通过「有 `<appmsg>` / `<recordinfo>` 负载完整展开 + 无有效负载条目双向返回可读提示（绝不静默丢弃）」兜底。
- **原生/WASM 依赖跨平台加载风险**：`sharp` 为仓内已验证依赖，`silk-wasm` 为纯 WASM 包；两者均在微信媒体处理函数内按需动态 `import()`，不阻塞节点主进程与其它通道启动。
- **回退方案**：新增表/列与 `owner_direct_agent_messages` 视图向后兼容既有飞书逻辑；如需回退，停用或删除微信通道后切回旧版本代码即可恢复运行，内部 IM 历史会话完整保留。

## 一次性部署迁移

无外部人工部署迁移（无需 `deployment-prompt.md`；IM SQLite 的 `owner_direct_agent_messages` 视图更新由 `apps/im-server/src/db.ts` 启动时幂等 `schema_migrations` 自动完成）。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node + DSH 真栈（自动持久化微信桩环境变量） | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | `NANO_WECHAT_E2E_BASE_URL="http://127.0.0.1:$WECHAT_TWIN_PORT" ./scripts/e2e-up.sh --profile daily --wt "$WT_ROOT"` | `source "$WT_ROOT/.e2e-ports.env" && curl -fsS "$IM_URL/openapi.json" >/dev/null` |
| 本机微信 iLink + CDN 测试桩（`e2e-wechat-twin`） | `kill "$(cat "$WT_ROOT/wechat-twin.pid")"`（或随 `e2e-down.sh` 回收） | `node scripts/e2e-wechat-twin.mjs --port "$WECHAT_TWIN_PORT" --state "$WT_ROOT/wechat-twin.json"` | `curl -fsS "http://127.0.0.1:$WECHAT_TWIN_PORT/__admin/health"` |

- **Review 驱动方式**：
  1. 在受审 worktree 执行 `python3 scripts/dev_host.py check` 与 `pnpm build && pnpm typecheck`。
  2. 先启动 `e2e-wechat-twin.mjs`，再带 `NANO_WECHAT_E2E_BASE_URL` 运行 `./scripts/e2e-up.sh --profile daily --wt "$WT_ROOT"`（脚本将该地址写入隔离 `.gateway-config.yaml` 的 `gateway.environment` 与 `.e2e-ports.env`，重启守护进程亦不会漏向公网）。
  3. 在真实浏览器（`1280×800` 与 `390×844`）登录 `nano`：在 daily `PA` 上验收扫码/验证码绑定、主人微信私聊、富内容收发与定时提醒；新建或使用一个 `single_thread` 普通 Agent 绑定微信通道，验收单会话双端工具审批卡片与微信文本口令互斥及 `/stop` `/new` `/compact` 同步。
  4. 结束后运行 `./scripts/e2e-down.sh --wt "$WT_ROOT"` 回收全部进程与临时目录。
- **验收前置**：
  - **自动化测试与 Stage 4 独立审查**：无外部账号前置（由用户在 `spec.md` Q2 授权使用本机 `e2e-wechat-twin` 完成全链路真栈验收）。
  - **提交 PR 前真人扫码门禁**：按用户 Q2 要求，在 Stage 4 通过后拉起不设 `NANO_WECHAT_E2E_BASE_URL` 的隔离预览环境，由用户本人手机微信现场扫码并实测收发通过后，再执行归档与创建 PR。

## Milestones

采用两个纵向可独立端到端验证的里程碑顺序推进：M1 一次性锁定依赖并打通扫码绑定、全栈多通道底座（含 IM 视图迁移与 PA 入站）、双端通道管理与文本私聊闭环；M2 在稳定底座上闭合富媒体加解密、卡片/合并转发、局部引用、双阶段出站图片与单会话文本审批互斥。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| `M1-wechat-binding-and-text-channel` | 微信扫码绑定、多通道托管底座与基础双向对话闭环 | 无 | 顺序 1 | `packages/channels/package.json` & `pnpm-lock.yaml`（`qrcode`、`silk-wasm`、`sharp`）；`packages/product-contracts/src/node-rpc.ts`；`packages/channels/src/wechat/{ilink,crypto,login,outbound,connection,index}.ts`；`packages/personal-assistant/src/{managed-channels,external,external-store,single-thread,global-agent,personal-assistant,attention,store}.ts`；`apps/node/src/{main,configuration}.ts`；`apps/im-server/src/{channels,messaging,personal-agent,personal-actions,schema.sql,db}.ts`；`src/IM/frontend/src/features/settings/agents/*` & `i18n`；`src/IM/ios/NanoIM/Features/Agents/{AgentChannelsView,AgentChannelModels}.swift` & `src/IM/ios/Tests/AgentContractsTests.swift`；`scripts/{e2e-wechat-twin.mjs,e2e-up.sh}` 及对应测试 | **[reviewer]** ① Web 端在普通 Agent 与 PA 外部通道页可与飞书并存添加微信通道，完整走通待扫码、已扫码待确认、数字验证码输入与输错重试、过期刷新、中途取消、连接成功与失效重绑（隐藏无效重连、突出重新扫码），桌面与 `390px` 窄屏兑现 `prototype.html` 全部 `must-match` 项，无明文令牌回显且禁止 REST 直传明文微信凭据；② 原生 iOS 端添加入口支持飞书与微信引导分流，已绑定微信准确展示状态与启停/重连/删除且无飞书残留；③ 绑定者微信文本私聊在普通 Agent 与 PA（含存量库升级后的 `owner_direct` 与 `owner_only` 模式）均自动建立并同步 `${agentId} · wechat` 影子会话，`SingleThread` 模型可见 `source: WeChat` 与主人记忆归属，Global 会话不触发飞书表情报错，触发源路由、离线恢复追平、正在输入状态、纯文本运行信息页脚、3,500 字围栏安全分段及 `/new` `/stop` `/compact` 同步生效。<br>**[worker]** `node-rpc` 单测、iLink 全部登录分支（含 `scaned_but_redirect` 域名校验、`binded_redirect`、`verify_code_blocked`）/异步单轮询先停后起/`purgeChannel` 停用后删除清理/`-14` 止损/Markdown 分段单测、IM `channels` + `messaging` + `db.ts` 视图迁移 + PA 主人微信私聊单测、Web 测试与构建、`check:ios-runtime` 与 `AgentContractsTests.swift` 通过；保存桌面与 `390px` 窄屏真实页面对照证据。 |
| `M2-wechat-rich-media-forwards-and-approvals` | 富媒体加解密、卡片/合并转发展开、引用还原、图片双阶段出站与单会话文本审批互斥 | `M1-wechat-binding-and-text-channel` | 顺序 2 | `packages/channels/src/wechat/{xml,inbound,quote-store,outbound,connection}.ts`；`packages/personal-assistant/src/{external,external-store,global-agent,personal-assistant}.ts`；`apps/node/src/{main,file-transfer}.ts`；`apps/im-server/src/personal-actions.ts`；全链路单元/集成/真栈 E2E 测试 | **[reviewer]** ① 微信发送链接、公众号/网页分享卡片与合并转发聊天记录时，影子会话与 Agent 准确呈现卡片摘要或带非指令边界提示的递归展开对话（Agent 通过受控工具读公开正文，通道不盲抓外链），收到空负载/不支持特殊卡片时双端收到明确可读提示；② 有转写语音直接识别，无转写语音自动解密转 `24kHz WAV` 处理或给出明确反馈；16 MiB 内原图方向修正收敛后作为影子会话纯图片附件展示（无 `[图片]` 占位词）并支持看图作答；合规文档/代码/压缩包/视频可由 `download_attachment` 在线及离线读取（超限明确提示）；③ Agent 回复内联图片及显式 `send_message(local_images)`（含 IM 离线先发微信、恢复后补齐影子附件）在普通 Agent 与 PA 主人私聊中均作为真实微信图片送达；④ 全文引用与局部选中文字引用（子串出现序号 + MD5 消歧）准确还原上下文并在删除/解绑时清除本地 `0600` 缓存；⑤ `SingleThread` 微信纯文本审批口令与内部 IM 影子会话审批卡双向同步、先到生效、重复幂等互斥，且 `/stop` `/new` 或终结后不残留未决审批误吞正常消息。<br>**[worker]** AES-128-ECB 三种密钥编码与流式限额单测、`<appmsg>`/`<recordinfo>` 递归与防注入包裹单测、`PCM`/`SILK` 转 `WAV` 与 `sharp` 原图收敛单测、`partial_text` 双模式 `quotemd5` 消歧与 `0600` 清理单测、`file-transfer.ts` 本机 `external:` 下载单测、出站图片离线暂存与影子补传单测、`SingleThread` 双端审批竞争及中止清理单测、`fork-prefix-provider.test.ts`、`test_runtime_dependency_contract.py` 及隔离真栈 E2E 全部通过。 |
