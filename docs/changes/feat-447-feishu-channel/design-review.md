# feat-447 Design Review

**结论**: Issues Found

本轮按当前最新 `design.md` 重审，重点放在进攻侧。上一版 review 中的 GroupContextStore external key、`config_agent_id`、`run_context_store accepted callback` 三条已经被当前 design 吸收，不再作为存活阻塞项。

**核实台账**(逐条核过的承重原子;结论附证据,不是打勾):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: Gateway/IM/agent 依赖边界 | 核顶点架构 | 成立: IM 不调用 agent,Gateway 经 `agent.sdk` 持有内核(`SPEC.md:147`, `SPEC.md:155`) |
| 现状: FeishuAdapter/FeishuClient 是飞书生产入口 | 从 channel 装配追入站 | 成立: design 指向 `channels/feishu/client.py`/`channels/feishu/adapter.py`;现代码已有 Feishu event -> InboundMessage metadata 路径(`src/personal_assistant/channels/feishu/adapter.py`) |
| 现状: Session key 可按 metadata external identity 覆盖 | 核当前实现 | 成立: `build_session_key` 已优先读 `metadata["external_source"]` / `metadata["external_chat_id"]`(`src/personal_assistant/gateway/session_keys.py:422`) |
| 现状: GroupContextStore key 可复用 external identity | 核当前实现 | 成立: `_group_buf_key_for_agent` 已优先用 `build_external_session_key`(`src/personal_assistant/gateway/inbound_pipeline.py:642`) |
| 现状: IM conversation schema 复用 `config_agent_id` | 核 DB/repo | 成立: schema 与索引均使用 `config_agent_id`(`src/IM/infra/db.py:46`, `src/IM/infra/db.py:332`) |
| 现状: IM 配置同步中 skills 以 IM mirror 为准 | 核 canonical + sync code | 成立: canonical 写明除 workspace_root 外 `skills` 等以 IM 镜像同步(`docs/specs/gateway/spec.md:216`);`sync_agent`/`reconcile_all_agents` 均直接从 `payload["skills"]` 构造 agent config(`src/personal_assistant/main.py:400`, `src/personal_assistant/main.py:644`) |
| 现状: PA 全局 skill root 是 `~/.nanoassistant/skills` | 核 product factory | 成立: `PA_SKILL_SEARCH_ROOTS` 包含 `Path("~/.nanoassistant/skills")`(`src/personal_assistant/product.py:50`) |
| 决策 1: 飞书事件连接方式选 WebSocket | 核 spec/架构约束 | 成立: 本机 Gateway 在 NAT 后主动连出;WebSocket 方向合理(`SPEC.md:55`) |
| 决策 2: 多 Bot 配置模型 `feishu:<agent_id>` | 核 spec 驱动 | 成立: spec 明确一个飞书 Bot 对应一个 Agent(`spec.md:13`) |
| 决策 3/13: `feishu-doc` 内置 skill + 启动安装 + 自动启用 | 核数据流闭合 | 部分不成立: 安装到 `~/.nanoassistant/skills` 与 resolver 对齐;但“自动补入 agent.skills 并写本地 config”会被 IM mirror skills 覆盖,见 Issue 1 |
| 决策 4/5: external session identity + external group buffer identity | 核旧 review 三条 | 成立: design 明确 session key 和 buffer key 均用 `external_source:external_chat_id:agent_id`(`design.md:162`, `design.md:184`) |
| 决策 6/9/10: shadow conversation + trigger_source + accepted callback | 核 run_id 时机 | 成立: design 明确先写 metadata/turn context,accepted 后 seed run_context_store(`design.md:197`, `design.md:493`) |
| 决策 7: IM 影子会话字段 | 核字段名 | 成立: design 明确 agent 维度复用 `config_agent_id`,不新增第二套 agent id(`design.md:208`) |
| 决策 11: ownerOpenId | 核配置路径 | 成立: design 明确 `channels[].settings.ownerOpenId`(`design.md:247`) |
| 决策 12: 影子 group gate 前注入 mention | 核门控顺序 | 成立: design 明确必须在 `_should_process` 前注入(`design.md:256`) |
| 决策 14: 外部 channel 回复镜像边界 | 核 milestone/delta 承接 | 不成立: design 引入 `ExternalReplyMirror` 和 M11 语义(`design.md:272`, `design.md:409`),但 milestone 表没有 M11,actual gateway delta-spec 也没有该 requirement |
| 决策 15: 外部同步用户消息 live insert | 核 milestone/delta 承接 | 不成立: design 写必须广播 canonical `message.created`(`design.md:288`, `design.md:473`),但 actual IM delta-spec 只有 4 个 requirement,没有“实时出现/message.created”条目(`specs/im/spec.md:5`, `specs/im/spec.md:24`, `specs/im/spec.md:38`, `specs/im/spec.md:52`) |
| spec: 飞书 1:1 / 群聊 / 多 Agent | 覆盖? | 覆盖: 决策 1/2/5 和历史 M1-M6 覆盖(`design.md:569`) |
| spec: 外部 channel 同步到 IM / 跨入口上下文 | 覆盖? | 覆盖: 决策 4-12 + M7 覆盖,旧 review 三条已修正(`design.md:299`, `design.md:575`) |
| spec: 飞书云文档操作 | 覆盖? | 部分不成立: skill 安装路径覆盖;但 Feishu-bound agent allowlist 的长期启用机制与 IM config source-of-truth 冲突,会让运行态仍看不到 `feishu-doc` |
| 非目标: 不建外部成员真实 IM 用户 | 越界? | 未越界,但留下显示身份歧义: design 只新增 `sender_display_name`,没有拍死外部非 owner 消息的 `sender_user_id/is_mine` 语义 |
| delta im | 核 actual 文件与 design 摘要 | 不成立: design 摘要列出“外部 channel 用户消息实时出现”(`design.md:509`),actual `specs/im/spec.md` 不存在该 requirement |
| delta gateway | 核 canonical 锚 + actual 文件 | 不成立: actual gateway delta 没有“外部 channel 可见回复镜像”;且 `按触发源路由` 以 ADDED 写入,实际修改 canonical “会话键按通道生成”的既有契约(`docs/specs/gateway/spec.md:155`) |
| Milestone M7-M10 | 核垂直切片/两轨退出 | 基本成立: M7/M10 有 reviewer/worker 两轨;但 M11 被 design 引用却没有 milestone 行 |

**架构进攻**(重点):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | `feishu-doc` 自动启用写本地 config | 不完整: PA runtime 的 skills 不是纯本地权威,IM config sync 会用 mirror 覆盖内存配置;只写本地 config 会形成“启动看似补了,同步后一轮又丢”的隐性振荡 |
| 归属 | `ExternalReplyMirror` | 方向可接受: 外部 channel 回写属于 Gateway 出站层,不应下沉 kernel 或 IM;但必须作为 milestone 和 gateway delta-spec 的一等行为,不能只留在 design 叙述里 |
| 归属 | `message.created` live insert | 正确归属在 IM user-stream/event 层;它是浏览器可观察 contract,不能只写在 Gateway design 摘要中 |
| 该不该存在 | `external/find-or-create` API | 保留合理: 删除后 Gateway 查后创会有竞态;IM 集中幂等创建更深 |
| 该不该存在 | `ExternalReplyMirror` 新组件 | 保留有理由: terminal `reply_text` 无法表达多 assistant 气泡;删除后复杂度会回到 Pipeline terminal fallback 并继续漏中间可见回复 |
| 深还是浅 | `sender_display_name` 单列 | 偏浅: 只解决名字,没解决外部非 owner 是否应按“非我”渲染/统计;长期代价是前端 layout、unread、toast 继续把 Alice 当 owner 或让 worker临时打补丁 |
| 深还是浅 | delta-spec 摘要 vs actual delta 文件 | 不成立: design 摘要已更新,actual delta 没更新;这是文档系统的浅同步,会让收尾归并漏掉外部回复镜像和 live insert |
| 治本还是补丁 | M10 自动补 allowlist | 当前是补丁: 绕过了 IM profile 权威,没有说明是否回写 IM profile、在 config sync 后重新注入,或改为 effective product skill overlay |
| 治本还是补丁 | M11 文档落点 | 当前不是完整切片: 决策/风险/runbook 都写 M11,但 Milestones 到 M10 结束,orchestrator 无法派工 |

**Issues**(按 CRITICAL > WARNING 排序):

- [CRITICAL] [决策 13 / M10 skill 启用]: `feishu-doc` 自动启用只写本地 config,但 Gateway 同步 agent 时 `skills` 以 IM mirror 为准(`docs/specs/gateway/spec.md:216`, `src/personal_assistant/main.py:400`, `src/personal_assistant/main.py:644`)。不改的话,显式 skills allowlist 的 Feishu agent 启动时可能短暂被补入,随后 `sync_agent` / reconnect reconcile 又用 IM profile 覆盖掉,真实 run 仍看不到 `feishu-doc`。设计需要拍死一个权威路径:更新 IM profile、在每次 sync 后注入 effective mandatory skill,或把 Feishu product skill overlay 独立于用户 allowlist。
- [CRITICAL] [决策 14/15 / Milestones]: design 新增 M11 级行为(外部可见回复镜像、外部用户消息 live `message.created`)并在风险/runbook 中引用 M11,但 Milestones 表只有 M1-M10(`design.md:533`, `design.md:567`, `design.md:570`)。不改的话 orchestrator 不会派 worker 实施这些新增决策,reviewer 却会按 runbook 验收,形成“设计要求存在但任务系统不可达”的断裂。
- [CRITICAL] [delta-spec / im+gateway]: `design.md` 声称 im delta 包含“外部 channel 用户消息实时出现”(`design.md:509`),gateway delta 包含“外部 channel 可见回复镜像”(`design.md:515`),但 actual delta 文件没有这两个 requirement(`specs/im/spec.md:5`, `specs/gateway/spec.md:95`)。不改的话收尾归并不会把两个新增用户可观察行为写进 canonical,后续 verifier/reviewer 也没有契约锚。
- [CRITICAL] [delta-spec / gateway canonical 锚]: “按触发源路由 agent 回复”改变了 canonical gateway 的会话键口径:旧契约写“会话键按通道与群聊/直聊维度生成”(`docs/specs/gateway/spec.md:157`),delta 只以 ADDED 写 `external_source + external_chat_id + agent_id`(`specs/gateway/spec.md:41`)。不改的话归并后同一 Gateway spec 会同时要求“按通道生成 key”和“外部 shadow 跨 web_relay/feishu 共用 key”,契约自相矛盾。应 MODIFIED 精确锚定既有“会话映射持久化”requirement,保留普通 channel 原语义并增加 external-channel 例外。
- [WARNING] [外部发送者身份 / IM 显示模型]: design 只新增 `sender_display_name`,但非目标又禁止给外部成员建真实 IM 用户。当前 IM message 创建要求合法 `sender_user_id`,前端用 `is_mine` 决定左右布局;如果 worker 用 owner_user_id 写 Alice/Bob,名字能显示但消息会被当成 owner 自己。建议 design 拍死外部非 owner 消息的 `sender_user_id/is_mine` 语义:新增外部 sender 影子字段、前端按 sender_display_name+external metadata 渲染,或明确接受“仅名字正确,布局不区分”。

**Recommendations**(不阻断门禁,作者自行取舍):

- 把 M11 拆成一个明确 milestone,范围至少覆盖 Gateway mirror、Feishu reaction lifecycle、IM event payload、前端 reducer live insert、delta-spec 更新。
- M10 不要只“写本地 config”。更稳的架构是 product-level effective skill overlay:Feishu-bound agent 的运行态 resolver 永远额外包含 `feishu-doc`,同时 IM profile 是否持久展示另走同步。
- `design-review.md` 当前已按最新 `design.md` 重写;旧三条 review 不再是存活 issue。
