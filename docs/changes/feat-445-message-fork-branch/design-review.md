# Design 评审:feat-445-message-fork-branch

**评审者**:change-design-reviewer(独立视角,只读不改)
**对象**:`design.md` v2.2 + `spec.md` v1 + 三份 delta-spec(kernel/im/gateway)

**结论**:Issues Found(1 CRITICAL — 中央「无损权威」前提的 READ 路径不存在;2 WARNING)

---

## 核实台账(逐条核过的承重原子;结论附第一手证据)

### 现状断言

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| sdk `fork_session`(:790)是 stub,忽略 source 只建空 session | 读 sdk/kernel.py:790-808 | ✓ 成立。:807 仅 `session_service.create_session(workspace_root=...)`,完全不读 `session_id`,不调 runtime.fork_session |
| runtime `fork_session`(:1271)/`_fork_locked`(:1312)全保真线性复制、无 fork 点截断、`replace()` 保 reasoning | 读 runtime.py:1271-1372 | ✓ 成立。:1354 `replace(msg, message_id=…, parent_message_id=…)` 保留其余字段(含 reasoning);无任何 `up_to`/截断;复制整段 source_history |
| runtime.fork_session 热路径优先读内存 `_session_histories`(可能是压缩视图) | 读 runtime.py:1286-1299 + compact 写回点 :2040-2048 | ✓ 成立。:1286 `if source_session_id not in self._session_histories:` 命中即用缓存;compact 在 :2048 把缓存重置为 `[summary_msg]`→fork 已 compact 的活跃 session 会拿到摘要视图 |
| **manager.load(:95)= 无损全量,「绕开 list_turn_messages 的 compact skip」** | 读 manager.py:88-105 + 218、追到 store.load:164-231 | **✗ 不成立(CRITICAL)**。manager.load 与 list_turn_messages **调用同一个 `self._store.load`**(manager.py:100 / 218);store.load 在 :224-229 「Only keep turns after the latest compact_boundary」**统一跳过 compact 前的 turn**。无任何 raw/全量 load 路径(grep `include_compact`/`raw_load`/`ignore_boundary` 全空)。「绕开 compact skip」的能力**不存在** |
| jsonl_store append-only、compact 只追加 boundary+summary 不删老 turn | 读 jsonl_store.py:55、manager.py:226-260、store.load:191-196 | ✓ 存储层成立。store.load:191-196 逐行读入全部 raw_lines(含 compact 前 turn);**但 materialize 时 :224 主动丢弃它们**——「字节在盘上」≠「load 返回它们」 |
| realtime_stream.py:54 assistant_message payload 带 message_id/run_id/turn_id | 读 realtime_stream.py:50-63 | ✓ 成立。payload 同时含 `run_id`/`turn_id`/`message_id`(:54 `event.get("message_id")`) |
| IM `Message`(domain/models.py:268)无 kernel id 字段 | 读 models.py:267-296 | ✓ 成立。有 `id`(IM 自有)/`tool_calls`/`thinking`,无 kernel `message_id`/`run_id` |
| 每个 assistant_message → 一条 agent.text.message(一 run 多气泡) | 读 inbound_pipeline.py `_map_to_run_activity` ~:1493 | ✓ 成立。`if event_name == "assistant_message": return "agent.text.message"`,逐事件映射 |
| `_ensure_binding`(:696)复用分支 | 读 inbound_pipeline.py:696-710 | ✓ 成立。existing binding + workspace_root 匹配 → `bind(...existing.kernel_session_id...)` 复用;fork 预绑定可命中此分支 |
| im_connection.py:399 RPC dispatch(node.capabilities.resolve 同构) | 读 im_connection.py:398-417 | ✓ 成立。`if message_type == "node.capabilities.resolve": … send_json(request_id…)`,新 `session.fork.request` handler 可照搬 |
| gateway_handler.py waiters + wait_for | 读 gateway_handler.py:140-165 | ✓ 成立。`_cron_delete_waiters`/`_heartbeat_md_waiters` 等 `dict[str, Future]` + dispatch table;新 fork waiter 同构 |
| web_im_service create_conversation:33 / create_message:132 | grep 定位 | ✓ 成立 |
| 前端 MessageBubble:424、isAgent:436、deliveryStatus:444、无消息级操作按钮 | 读 message-pane.tsx:424-558 | ✓ 成立。:436/:444 确在;:510-558 仅 token/permission/elapsed 状态展示,无 fork/copy 等 hover 操作按钮——fork 按钮为净新增 |
| 当前无生产代码调用 fork_session | grep 全仓 `\.fork_session` | ✓ 成立。仅 test_fork_session.py 触达 runtime.fork_session;design 计划新接 sdk→runtime,为**加法接线**(design 已知 stub),可接受 |

### 决策

| 决策 | 四问 | 结论 + 证据 |
|---|---|---|
| 决策1 gateway raw 全量复制日志到 fork 点 | 拍死/spec驱动/自洽 | ⚠ 方向拍死、spec 驱动成立(Q2=A 上下文连续)。**但理由①②与「强制走 manager.load(raw)」对策建立在「manager.load 无损」错前提上**(见现状 ✗)。另:决策1·风险句「依据是 IM 消息携带的 run_id(feat-340-M2)」与决策4「IM 消息行不存任何 kernel id」**自相矛盾**(疑 v2.0 残留)→ WARNING |
| 决策2 IM 同步编排 + 一次 WS RPC 委托 | 拍死/spec驱动 | ✓ 拍死。spec 驱动成立(离线明确提示需同步,拒 lazy seeding 命中非目标);WS RPC 模式现状成立 |
| 决策3 历史两份表示(IM 展示副本 + gateway 日志副本) | 自洽/spec驱动 | ✓ 成立。跨机 + 保真职责清晰;两份同源同 fork 点对齐 |
| 决策4 relay 落逐气泡 message_id、按 message_id 截断 | 拍死/有据/根因 | ✓ 强决策。现状核查第一手成立(realtime_stream.py:54);拒绝 turn_id/序号/gateway 映射表均有据;粒度到 message 解决一 run 多气泡撞刀。**本 unit 最扎实的一条** |
| 决策5 在线校验前置 + 失败原子回滚 | spec驱动/数据流闭合 | ✓ 成立。spec 明令「不留无记忆空壳」;回滚=删新建会话(无外部引用) |
| 决策6 普通 direct-agent 单聊、title=agent 名 | spec驱动 | ✓ 成立。Q6 原话「所有 title=<agent 名>」;created_at 更新不被选 canonical,不污染主线 |

### spec 约束

| Requirement / 非目标 | 核实 | 结论 |
|---|---|---|
| 已完成 agent 回复才有 fork 入口(用户/生成中/群聊无) | design 落点 | ✓ 前端 isAgent+completed+单聊门控 + 决策5 |
| 带入 0→fork 点完整历史、之后不带 | 落点 | ✓ 决策1/3/4 + IM 展示复制 + kernel up_to 截断 |
| 完整气泡形态(工具/思考) | 落点 | ✓ 决策3(IM 复制 tool_calls/thinking)+ 决策1(replace 保 reasoning) |
| agent 记忆连续、可指代追问 | 落点 | ✓ 决策1 raw 全保真副本 |
| 自动进入 + 原会话独立两线 | 落点 | ✓ 决策2 + 前端跳转;fork 出独立 session |
| 列表名 agent 名 | 落点 | ✓ 决策6 |
| agent 离线 fork 不可用 + 明确提示 | 落点 | ✓ 决策5(前后端双校验 + 409) |
| 非目标:lazy seeding / 群聊 / 用户消息 fork / 分支命名 / 区间选择 | 是否越界 | ✓ 决策2 显式拒 lazy;其余均不做,无夹带越界 |

### delta-spec

| 条目 | 核实 | 结论 |
|---|---|---|
| kernel:MODIFIED「fork_session 复制无损历史到 fork 点」 | canonical 有无可锚既有条目 | ⚠ canonical 仅在生命周期清单(:98)/返回类型(:529)提及 `fork_session`,**无专门描述其行为的既有 Requirement** 可 MODIFIED 锚定。这其实是**净新增行为契约,应为 ADDED** → WARNING(收尾归并时 orchestrator 找不到可顶替的同名条目) |
| im:ADDED | 用法/可观察 | ✓ ADDED 正确(净新增用户能力);THEN 全用户可观察(「agent 表现出对历史的记忆」),无内部符号断言 |
| gateway:ADDED | 用法/消费者视角 | ✓ 正确;主语为 gateway(代码消费者),THEN 可观察 |
| cli:no spec delta | 显式注明 | ✓ 已注明不涉及 |

### milestone

| 原子 | 核实 | 结论 |
|---|---|---|
| 单 M1(relay→前端→IM→RPC→gateway→kernel 端到端) | 垂直 vs 横切 | ✓ 垂直切片,各层接口耦合无法真并行,单 M1 正确,未触发拆分硬条件 |
| 退出标准两轨 | [reviewer]/[worker] 齐、可验 | ✓ 两轨齐全;[reviewer] 引 spec 全 Scenario;[worker] 列具体单测(含 compact 非破坏守护测试、一 run 多气泡守护) |

---

## 架构进攻(四角度逐个走)

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | relay 把 kernel `message_id` 持久化到 IM 消息行 | ✓ 走完无存活发现。message_id 作为**不透明对齐 token**存储,IM 不解释它、原样回传 gateway,无 IM→kernel 反向依赖;跨机纪律(IM 不直读 gateway 日志)保持。优于「gateway 另维护映射表」(决策4拒绝③ 有据) |
| 该不该存在 | 新增 WS RPC 帧对 / message_id 持久化 / IM 展示副本复制 | ✓ 走完无存活发现。删除测试:① RPC 帧——IM 不能直达 kernel,删不掉;② message_id 持久化——删了就回退到不稳的序号/turn 对齐(决策4 已论证);③ 展示副本——跨机 + 展示/记忆职责分离,删了新会话无可回看历史。无多余间接层、无假想接缝 |
| 深还是浅 | runtime.fork_session 加 `up_to` 截断 | ⚠ `up_to` 是对既有全保真复制件的深扩展,本身合理。**但「强制走 manager.load 取 raw」并非浅扩展而是落在不存在的能力上**(见 CRITICAL):真实的「无损 materialize」需新建 store load 模式 + 处理跨 compact_boundary 的 parent 链重连,design 当作「flag 翻转」严重低估了深度 |
| 治本还是补丁 | 「fork 从权威无损日志复制」整体架构 | ✓ 架构方向治本(从权威而非展示副本复制,对多 channel 一视同仁),非补丁。「旧气泡无 message_id → 入口禁用不回填」是显式声明的合理降级,非掩盖症状 |

---

## Issues(按 CRITICAL > WARNING 排序)

- **[CRITICAL] [现状分析 / 决策1·理由①② / 风险「头号守护点」+「压缩视图」/ kernel delta Scenario「fork 取无损历史」]**:
  整套「fork 从无损权威日志复制」依赖一条**读路径**——design 指名 `manager.load`(:95)为「无损全量、绕开 compact skip」。**该能力不存在**:`manager.load` 与 `list_turn_messages` 调用同一个 `store.load`(manager.py:100/218),而 store.load 在 jsonl_store.py:**224-229 统一「Only keep turns after the latest compact_boundary」**,丢弃 compact 前的全部原始 turn;全仓无任何 raw/全量/ignore_boundary 读路径。
  **后果**:① 对**已 compact 的源会话**,worker 按 design「强制走 manager.load(raw)」拿到的仍是**摘要 + boundary 后 turn**,不是压缩前全量——直接违反 kernel delta「fork 取无损历史而非压缩视图」与 spec「完整气泡/完整记忆」;② design 自己列入 M1 退出标准的**头号守护测试**「compact 后 raw 仍取回压缩前全部 turn」,对 `manager.load` 写出来就是**红的**,而 design 没给出让它变绿的方案;③ 真正的修法不是「翻 flag」,而是**新建一条无损 materialize 能力**(读全部 turn 忽略 boundary + 重连跨 boundary 的 parent_uuid 链,因为 summary turn 的 parent 链在 boundary 处断开),M1 范围与 kernel 改动量(design 估 ~80 行)都被低估。
  **要求**:退回 design,把「无损读」从「复用 manager.load」修正为「新增 raw-materialize 能力(明确:新增 load 模式 / 参数 + 跨 compact_boundary parent 链处理)」,并在现状分析里把「存储 append-only 无损」与「load 路径会跳过 compact 前 turn」两件事分开陈述(当前把 manager.py:236-247 的 append-only **写**当成了无损**读**的依据)。

- **[WARNING] [决策1·风险句]**:「fork 点对齐……依据是 IM 消息携带的 `run_id`(feat-340-M2)」与决策4 + 现状(`Message` 模型无任何 kernel id 字段、`run_id` 只在 relay 事件瞬时流转)**直接矛盾**。疑为 v2.0「IM 当历史源」草案残留。worker 若先读决策1 可能误以为 IM 消息已带 run_id 锚点而少做「relay 落 message_id」前置链路。**修法**:删除/改写该句,统一指向决策4 的 message_id 持久化机制。

- **[WARNING] [kernel delta-spec]**:`fork_session` 行为契约写成 `## MODIFIED Requirements`,但 canonical kernel spec 中 **无专门描述 fork_session 行为的既有 Requirement** 可锚定(仅在生命周期方法清单 :98 与返回类型 :529 被提及)。这是**净新增行为契约,应为 ADDED**。**后果**:收尾归并时 orchestrator 按 MODIFIED 去找可顶替的同名既有条目会落空。**修法**:改为 ADDED,或在 delta 里注明「canonical 原仅声明方法存在、未定义其行为,本 unit 首次为其建立行为契约」。

---

## Recommendations(不阻断门禁,作者自行取舍)

- 架构总览句「唯一 channel 无关、覆盖该 agent **全部对话**的存储」措辞偏理想:每个 conversation 对应独立的 per-session JSONL(session_key=`channel:conversation_id:agent_id`),fork 复制的是**源 conversation 那一份** session 日志。不影响机制,但建议改为「覆盖该会话全部轮次的无损记录」以免读者误解为「一个 agent 一本大日志」。
- CRITICAL 修正后,建议在风险段把「头号守护点」从「compact 必须非破坏(存储层,现状已满足)」升级为「**无损 materialize 读路径必须能跨 compact_boundary 取回全量**(本 unit 新建,实施期头号验证点)」——前者现状已真,后者才是本 unit 真正要守的新行为。

---

> 复核范围:第一手追了 sdk/runtime/manager/jsonl_store/inbound_pipeline/im_connection/gateway_handler/realtime_stream/models/message-pane 的真实行号,未凭 design 替引的行。台账 ✗ 一条(manager.load 无损前提)升 CRITICAL;架构进攻三角度无存活发现、一角度(深/浅)与该 CRITICAL 同源。
