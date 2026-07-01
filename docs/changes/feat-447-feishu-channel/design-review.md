# Design 评审: feat-447-feishu-channel

**结论**: Issues Found

**核实台账**(逐条核过的承重原子;结论附证据,不是打勾):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `ChannelAdapter` / `InboundMessage` 是 channel 入站唯一归一化边界 | 从 FeishuAdapter/WebRelayAdapter 正向追到 ChannelRegistry/InboundPipeline | 成立: `ChannelAdapter.start(on_inbound)` 是 adapter 入口,`InboundMessage` 带 `channel_name/external_chat_id/metadata` (`src/personal_assistant/channels/base.py:9`, `src/personal_assistant/channels/base.py:73`); Feishu/WebRelay 均 callback 到 pipeline (`src/personal_assistant/channels/feishu_adapter.py:241`, `src/personal_assistant/channels/web_relay_adapter.py:206`) |
| 现状: FeishuAdapter/FeishuClient 已实现基础收发 | 核 start/send/parse 路径 | 成立: FeishuAdapter start 创建 FeishuClient,send 走 REST,DM/group @ 生成 InboundMessage (`src/personal_assistant/channels/feishu_adapter.py:75`, `src/personal_assistant/channels/feishu_adapter.py:86`, `src/personal_assistant/channels/feishu_adapter.py:223`, `src/personal_assistant/channels/feishu_adapter.py:244`) |
| 现状: 未 @ 群消息当前只进 GroupContextStore | 核 FeishuAdapter 分支和 Pipeline 门控 | 成立且暴露设计冲突: FeishuAdapter 未 @ 分支只 `_buffer_group_message` 不调用 `_on_inbound` (`src/personal_assistant/channels/feishu_adapter.py:164`, `src/personal_assistant/channels/feishu_adapter.py:167`, `src/personal_assistant/channels/feishu_adapter.py:279`); InboundPipeline 也会对 `should_process=False` 的 group message append buffer (`src/personal_assistant/gateway/inbound_pipeline.py:267`) |
| 现状: InboundPipeline 是真实运行路径 | 从 main wiring 追生产装配 | 成立: `build_runtime` 构造 InboundPipeline 并注入 registry/outbound/run_queue/session_store/group_context_store (`src/personal_assistant/main.py:2377`) |
| 现状: OutboundRouter 只按 ReplyContext 原路发送 | 核 send_text | 成立: `send_text` 根据 `reply_context.channel_name` 找 adapter 并 `channel.send` (`src/personal_assistant/gateway/outbound_router.py:29`) |
| 现状: session key 默认按 channel + external_chat_id + agent_id | 核 session_keys | 成立: `build_session_key` 返回 `{message.channel_name}:{message.external_chat_id}:{agent_id}` (`src/personal_assistant/gateway/session_keys.py:407`) |
| 现状: IM conversation/message 当前无 external/sender_display_name 字段 | 核 domain/db/repo/API | 成立: Conversation dataclass 无 external 字段 (`src/IM/domain/models.py:133`), messages schema 无 `sender_display_name` 列 (`src/IM/infra/db.py:114`), Message dataclass 无该字段 (`src/IM/domain/models.py:268`) |
| 现状: IM route 文件为 `web_im.py`,不是 `conversations.py` | 核实际 route 文件 | 不成立: design 涉及范围写 `src/IM/api/routes/conversations.py`,实际 conversation routes 在 `src/IM/api/routes/web_im.py:1`; worker 按文档路径找会浪费时间但可由 rg 自救 |
| 现状: IM 数据面身份由 token 决定 | 核 canonical spec | 成立: canonical IM spec 明确数据面路由请求主体身份取自 token,不接受 `?user_id=` 等信任锚 (`docs/specs/im/spec.md:47`) |
| 决策 1: 飞书事件连接选 WebSocket | 核 spec 驱动/现状约束 | 成立: NAT 本机 gateway 约束来自顶点架构,FeishuClient 用 WSClient 主动连接 (`SPEC.md:65`, `src/personal_assistant/channels/feishu_client.py:151`) |
| 决策 2: 多 Bot 配置为 `channels` entry,`name=feishu:<agent_id>` | 核 spec 驱动/现状 | 成立: spec Q2 要一个 Bot 对应一个 Agent (`docs/changes/feat-447-feishu-channel/spec.md:13`); config/parser/main 已按 `name.startswith("feishu:")` 装配 (`src/personal_assistant/config/local_store.py:899`, `src/personal_assistant/main.py:3031`) |
| 决策 3: 云文档走 feishu-cli | 核 spec 驱动 | 成立: spec 要用户身份云文档操作且不做评论/wiki/bitable (`docs/changes/feat-447-feishu-channel/spec.md:73`, `docs/changes/feat-447-feishu-channel/spec.md:238`); design 将自建 doc tools 拒绝掉 |
| 决策 4: Session key 选 `feishu:<agent_id>:dm/group:<id>` | 核与现状 session_keys/跨入口要求 | 不成立: 现有 `build_session_key` 是 `{channel_name}:{external_chat_id}:{agent_id}` (`src/personal_assistant/gateway/session_keys.py:407`); IM relay 入口的 `external_chat_id` 是 IM `conversation_id` (`src/personal_assistant/channels/web_relay_adapter.py:246`),未定义如何映射回同一飞书 key,无法保证 spec 的跨入口同 session |
| 决策 5: 群聊未 @ history buffer 复用 GroupContextStore | 核现状/职责唯一性 | 部分成立但与决策 6 冲突: 复用能力存在 (`src/personal_assistant/gateway/group_context_store.py`),但未 @ 消息若为同步而送入 Pipeline,FeishuAdapter 与 Pipeline 都可能 append,导致下一次 @ 时上下文重复 |
| 决策 6: 外部 channel 用户消息同步到 IM,按触发源路由回复 | 核数据流闭合 | 不成立: 早期 IM 同步落在 `InboundPipeline.handle_inbound`,但未 @ 飞书消息当前不会进入 Pipeline (`src/personal_assistant/channels/feishu_adapter.py:167`); trigger_source 只写入 metadata 设想,现有 OutboundRouter 不看它 (`src/personal_assistant/gateway/outbound_router.py:29`) |
| 决策 7: IM 会话加 `external_source/external_chat_id` | 核现状/contract | 成立: 这是对 IM 新增外部会话身份的合理落点; current schema 无该字段 (`src/IM/infra/db.py:35`) |
| 决策 8: messages 加 `sender_display_name` | 核显示名路径 | 成立: 现有消息 sender display_name 来自 users join (`src/IM/infra/repositories.py:1262`),外部成员不建 IM user 时确需持久化 display name |
| 决策 9: 新增 `POST /im/v1/conversations/external/find-or-create` | 核幂等与身份信任 | 部分不成立: 专用幂等接口合理;但 Request 里包含 `owner_id` (`docs/changes/feat-447-feishu-channel/design.md:300`)违反 canonical token 身份锚 (`docs/specs/im/spec.md:47`) |
| 决策 10: run 级 `trigger_source` + conversation metadata 回环路由 | 核 session/reply_context 数据流 | 不成立: design 没拍死 `trigger_source=im` 时如何更新同一 session binding 的 `reply_context` 为 `web_relay` 或如何阻止 `feishu` binding 原路发回;当前 binding 每次按当前 message 重绑但 session key 不共用 (`src/personal_assistant/gateway/session_keys.py:420`, `src/personal_assistant/gateway/session_keys.py:423`) |
| 决策 11: ownerOpenId 显式配置 | 核配置 schema | 有歧义: 当前 feishu settings 只校验 `appId/appSecret/botOpenId` (`src/personal_assistant/config/local_store.py:909`); design 未精确定义 `ownerOpenId` 放在每个 channel settings、node、还是 im_service |
| 决策 12: IM 群聊影子会话自动注入 @agent | 核 relay metadata | 有落点但未闭合: InboundPipeline 可用 `@agent` 文本通过 group gate (`src/personal_assistant/gateway/inbound_pipeline.py:852`),但现有 `create_message` 调 `enqueue_relay_all` 未传 `conversation_type` (`src/IM/api/routes/messages.py:358`),WebRelayAdapter 只能靠 metadata 判断 group (`src/personal_assistant/channels/web_relay_adapter.py:227`) |
| spec: 飞书 1:1 私聊对话 | 对照 design 决策/现状 | 覆盖: 决策 1/2/M1 覆盖 (`docs/changes/feat-447-feishu-channel/design.md:108`, `docs/changes/feat-447-feishu-channel/design.md:116`) |
| spec: 飞书群聊 @Bot / 未 @ / @所有人 | 对照 design 决策/现状 | 部分覆盖: 决策 5 覆盖 history buffer,FeishuAdapter 过滤 @所有人 (`src/personal_assistant/channels/feishu_adapter.py:287`);但未 @ 同步到 IM 与 buffer 职责冲突未拍死 |
| spec: 多 Agent 路由 | 对照 design 决策/现状 | 覆盖: 决策 2 + channel name 规则覆盖 (`docs/changes/feat-447-feishu-channel/spec.md:115`) |
| spec: 外部 1:1 独立会话/用户消息/agent 回复/IM 回复不回写/跨入口连续 | 对照 design 决策和 session/reply path | 不完整: 独立会话字段/API覆盖;跨入口同 session 与不回写飞书的数据流未闭合,见决策 4/10 |
| spec: 外部群聊独立 group/多 agent/发送者名字/owner 显示「你」/未 @ 同步/ALWAYS 全量同步 | 对照 design 决策和现状 | 不完整: group 影子会话和 sender_display_name 有设计;未 @ 同步存在 adapter/pipeline double-buffer 或漏同步二选一; ownerOpenId 配置位置未拍死 |
| spec: IM 离线时飞书不中断 | 对照 design 风险/决策 | 覆盖: 决策 6 明确 best-effort,风险表要求短超时和异常捕获 (`docs/changes/feat-447-feishu-channel/design.md:153`, `docs/changes/feat-447-feishu-channel/design.md:331`) |
| spec: 飞书云文档用户身份操作 | 对照 design/M2 | 覆盖: 决策 3 + M2 历史 milestone 覆盖 (`docs/changes/feat-447-feishu-channel/design.md:124`, `docs/changes/feat-447-feishu-channel/design.md:352`) |
| 非目标: wiki/bitable/comment/drive高级/富文本/编辑删除回写/外部成员建真实用户 | 对照 design | 未发现越界;设计拒绝自建 doc tools/外部成员建用户/完整双向镜像 (`docs/changes/feat-447-feishu-channel/design.md:129`, `docs/changes/feat-447-feishu-channel/design.md:172`, `docs/changes/feat-447-feishu-channel/design.md:151`) |
| delta gateway: ADDED 飞书 channel 消息收发/多 Bot | 核 canonical 锚 | 成立: canonical 已有相同 requirement,若本 unit 已合入历史则可视为历史 delta;对当前 M7 无新增风险 |
| delta gateway: ADDED 外部 channel 用户消息同步到内部 IM | 核 canonical 锚/用法 | 不成立: canonical gateway 现有 requirement 写明「MVP 阶段仅同步 Agent 回复，用户原始消息不写入内部 IM」(`docs/specs/gateway/spec.md:688`);本 delta 改既有契约却写 ADDED (`docs/changes/feat-447-feishu-channel/specs/gateway/spec.md:39`),收尾归并会新旧并存 |
| delta gateway: ADDED 按触发源路由 agent 回复/IM 离线/会话隔离 | 核 THEN 可观察 | 基本成立: THEN 为用户/IM 可观察结果,未写内部函数调用 (`docs/changes/feat-447-feishu-channel/specs/gateway/spec.md:58`) |
| delta im: ADDED 外部 channel 影子会话/消息写入/元数据回环/现有行为不变 | 核 canonical 锚/THEN 可观察 | 基本成立: canonical IM 现无外部会话 requirement,ADDED 合理;THEN 以 HTTP/WS/history 可观察结果表达 (`docs/changes/feat-447-feishu-channel/specs/im/spec.md:5`) |
| M1-M6 历史 milestone | 核是否当前要派工 | 可接受但应标历史: 已有 progress/tasks,退出标准未两轨化但不应再派新 worker;当前风险在 M7 |
| M7 external-channel-full-sync | 核垂直/范围/退出标准 | 部分成立: 是端到端垂直 slice,有 reviewer/worker 两轨;但范围同时跨 IM + Gateway + FeishuAdapter,且依赖上述未拍死边界,worker 会被迫猜 session/reply/buffer owner |

**架构进攻**(四角度逐个走,每条发现带具体长远代价;某角度无发现也写「走完无存活发现」):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 外部 channel 会话身份 + owner_id | `external_source/external_chat_id` 放 IM conversation 合理;但 `owner_id` 放请求体是错归属,身份应由 IM auth token/current_user 派生。长期代价是外部 channel find-or-create 变成可伪造 owner 的新数据面入口,与 IM 多租隔离 contract 对冲 |
| 归属 | 未 @ 群消息同步与 GroupContextStore | 职责跨 FeishuAdapter 与 InboundPipeline 重叠: adapter 已 buffer,Pipeline 对 dropped group 也 buffer。长期代价是每新增一个外部 channel 都要重新猜「sync-only 入站」该不该进入 pipeline,重复上下文或漏同步会反复出现 |
| 该不该存在 | 新 `trigger_source` 标记 | 标记本身需要存在;但只加标记不改变 session binding/reply_context 是浅层补丁。长期代价是 worker 可能只把 flag 穿透完,实际回复仍由旧 `ReplyContext` 发回飞书 |
| 该不该存在 | 专用 external find-or-create API | 通过幂等键集中在 IM 创建会话是必要抽象;删除测试显示让 Gateway 查后创会引入竞态,保留合理 |
| 深还是浅 | `sender_display_name` 列 | 不是浅封装;它补足外部成员不建 IM user 的历史显示缺口。无存活问题 |
| 深还是浅 | session key 决策 | 当前决策太浅: 写了字符串格式,没定义 Feishu 入口和 WebRelay 入口如何归一到同一个 key。长期代价是上下文连续性只在各自入口内成立,跨入口场景验收必炸 |
| 治本还是补丁 | Gateway 回复路由 | `trigger_source` + metadata 若不重塑 reply target,是在现有 OutboundRouter 上打补丁。长期代价是未来 Slack/TG 同步会继续围绕「同一 session 多出口」追加特例,出站路由规则分散 |

**Issues**(按 CRITICAL > WARNING 排序):

- [CRITICAL] [delta-spec / gateway]: `specs/gateway/spec.md` 把「外部 channel 用户消息同步到内部 IM」写成 ADDED,但 canonical gateway spec 现有「飞书对话同步到内部 IM」明确说“仅同步 Agent 回复，用户原始消息不写入内部 IM”(`docs/specs/gateway/spec.md:688`)。不改会导致收尾归并后同一行为新旧两条并存,orchestrator/worker 无法判断到底要不要同步用户原始消息。应改为 MODIFIED 既有 requirement,或 REMOVED 旧 MVP 条目 + ADDED 新通用外部 channel 条目。
- [CRITICAL] [决策 5/6 / 未 @ 群消息]: design 要“未 @ 的群聊上下文消息同步到内部 IM”,但同步落点写在 `InboundPipeline.handle_inbound` 早期;当前 FeishuAdapter 未 @ 分支只 `_buffer_group_message` 不进 Pipeline(`src/personal_assistant/channels/feishu_adapter.py:167`)。若 worker 为了同步把未 @ 消息也送进 Pipeline,Pipeline 又会 append GroupContextStore(`src/personal_assistant/gateway/inbound_pipeline.py:267`),造成下一次 @ 时上下文重复;若不送,则漏同步。必须拍死单一 owner: either adapter 只生成 sync-only inbound 且不再本地 buffer,或新增独立 IM sync hook 且 Pipeline 不再二次 buffer。
- [CRITICAL] [决策 4/10 / 跨入口 session 复用]: spec 要 IM 影子会话和飞书原对话复用同一 kernel session,但现状 session key 是 `{channel_name}:{external_chat_id}:{agent_id}`(`src/personal_assistant/gateway/session_keys.py:407`),WebRelay 的 `external_chat_id` 是 IM conversation_id(`src/personal_assistant/channels/web_relay_adapter.py:246`),飞书入口是 `feishu:<app_id>:dm/group:<id>`(`src/personal_assistant/channels/feishu_adapter.py:229`)。design 未定义 IM relay 如何归一到飞书 session key,worker 按字面实现会产生两个 kernel session,上下文连续验收失败。
- [CRITICAL] [决策 10 / 回复不回写飞书]: design 说 IM 触发的影子会话回复只留在 IM,但现有出站只看 binding 的 `ReplyContext.channel_name` 原路发送(`src/personal_assistant/gateway/outbound_router.py:29`)。如果复用飞书 binding,IM 触发回复会回写飞书;如果用 WebRelay binding,又无法复用飞书 session。必须明确“同一 kernel session 多 reply target”的绑定/路由模型,例如 session identity 与 per-run reply_context 分离。
- [CRITICAL] [决策 9 / IM API 身份边界]: 新接口 request 示例包含 `owner_id`(`docs/changes/feat-447-feishu-channel/design.md:300`),但 IM canonical 规定数据面身份取自 Bearer token,不接受请求参数作为信任锚(`docs/specs/im/spec.md:47`)。worker 若按 request 体实现 owner_id,会打破多租隔离。应改成 owner_id 只由 `current_user.owner_id` 派生,request 不含 owner_id。
- [WARNING] [决策 11 / config schema]: `ownerOpenId` 只说“Gateway config 中显式配置”,但没拍死字段路径。当前 feishu channel settings 已有 `appId/appSecret/botOpenId` 校验(`src/personal_assistant/config/local_store.py:909`),worker 可能放到 node/global/channel 任一位置,导致多 Bot owner 显示「你」不一致。建议明确为 `channels[].settings.ownerOpenId` 并加 local_store 校验/示例。
- [WARNING] [涉及范围 / 路径]: design 写 `src/IM/api/routes/conversations.py`,实际是 `src/IM/api/routes/web_im.py`。这不会改变架构,但会让 M7 worker 先按错路径探索,建议修正。
- [WARNING] [决策 12 / IM group relay metadata]: design 要 IM 群聊影子会话自动注入 @agent,但现有 create_message route 调 `enqueue_relay_all` 没传 `conversation_type`(`src/IM/api/routes/messages.py:358`),WebRelayAdapter 只能从 metadata 判断 group(`src/personal_assistant/channels/web_relay_adapter.py:227`)。建议在 design 明确 M7 必须把 conversation.type 放入 relay metadata,否则 group shadow 消息可能按 direct 路径走。

**Recommendations**(不阻断门禁,作者自行取舍):

- 把 M7 拆成“身份/会话归一模型先行小节”再写实现范围: `shadow_conversation_id` 只用于 IM 展示,`external_session_key` 用于 kernel session,`reply_context` per-run 决定出口。
- 在 design 的数据结构段新增 `sync_only` 或 `should_process` 语义,专门表达“写 IM 但不触发 kernel”的外部消息,避免复用 group mention gate 的副作用。
- delta-spec 的 gateway canonical 归并方案最好直接写出被替换标题: `MODIFIED Requirement: 飞书对话同步到内部 IM`。
