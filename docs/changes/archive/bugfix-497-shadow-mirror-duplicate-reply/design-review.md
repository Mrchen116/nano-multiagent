# Design Review: bugfix-497

## Round 1

### Metadata

- reviewer: `/root/bugfix_497_design_review`
- review_mode: `full`
- mode_reason: `R1 恒为 full；逐条核对 incident、6 个决策、4 份 delta-spec、2 个 milestone、current specs 与生产入口，并完成全部四个架构进攻角度。评审期间作者移除了 external shadow 对 IM created_at 的 source override；本轮以 2026-08-04T12:25:55+08:00 后的当前文件为基线重新核实受影响原子。`
- started_at: `2026-08-04T12:21:16+08:00`
- completed_at: `2026-08-04T12:27:31+08:00`
- duration: `6m15s`

### Verdict

Changes Required — 5 CRITICAL / 1 WARNING

### Coverage

- 首文档：`incident.md` 全文（澄清 Q1–Q6、RCA、不变量、9 个验收 Scenario、范围与非目标）。
- 方案：`design.md` 全文（现状、决策 1–6、接口/数据流、风险/回退、Runbook、M1–M2）。
- delta-spec：`specs/gateway/external-channels.md`、`specs/gateway/relay-protocol.md`、`specs/im/conversations-messages.md`、`specs/im/gateway-relay.md`。
- current specs：`SPEC.md`；Gateway `external-channels.md`、`relay-protocol.md`；IM `conversations-messages.md`、`gateway-relay.md`、`tool-timeline.md`、`response-metrics.md`、`web-chat-ux.md`。
- 生产路径：Gateway composition → inbound pipeline → run context / observer → shadow saga/sync → connection-ready recovery；IM gateway protocol/execution → EventBridge → MessageRepository/API → owner user-stream → chat reducer/workspace。

### 现状断言核实台账

| ID | design 现状原子 | 本轮核实与证据 | 结论 |
|---|---|---|---|
| S1 | observer 同时翻译 live frame 并在外部回复边界准备 plain output；离线分支只保留正文 | 生产 wiring 把同一个 observer 注入 run coordinator，并注入 `shadow_output_prepare/mirror`（`src/personal_assistant/gateway/composition.py:424-458,476-486`）；observer 的 plain prepare 在 `_mirror_external_reply`（`observer.py:234-272`），离线分支只维护 `external_current_text/kernel_message_id` 且对 thinking/tool/turn_end 提前返回（`observer.py:362-391`）。 | 成立 |
| S2 | `shadow_saga.py` / `shadow_sync.py` 拥有本地 SQLite、稳定 caller key、user anchor 与 plain mirror | 现表与 key 在 `shadow_saga.py:75-159,267-386`；HTTP user anchor/plain Agent 写入和 pending replay 在 `shadow_sync.py:76-204,270-299,317-366`。 | 成立 |
| S3 | `ConnectionReadyCoordinator` 在注册/重连后调度 recovery，并重试瞬时失败 | composition 注入 `recover_pending`（`composition.py:514-525`）；coordinator 在 register-ready 后创建单 recovery task，并在异常时循环退避（`connection_ready.py:99-136`）。 | 成立 |
| S4 | IM execution/EventBridge 接收 turn/text/thinking/tool/terminal 并形成富气泡；turn_start 没有 durable shadow identity | parser 当前字段没有 `shadow_message_id/process_seq/authoritative elapsed`（`src/IM/ws/gateway/protocol.py:32-52,109-164`）；execution 路由到 EventBridge（`execution.py:171-349`）；EventBridge 建泡、写过程和终态（`src/IM/application/event_bridge.py:138-179,235-347`）。 | 成立 |
| S5 | MessageRepository 已做 conversation-scoped caller 幂等并持久化富字段；命中 key 只返回旧行 | create 先按 scoped key查行并直接 return（`src/IM/infra/repositories/messages.py:108-157`）；行包含 tool/thinking/token/elapsed/kernel id（`messages.py:201-325,446-595`）。 | 成立 |
| S6 | frontend 已渲染富字段；同 ID 的 `message.created` 被忽略且无 reconcile event | canonical event 集合没有 `message.reconciled`（`src/IM/frontend/src/realtime/user-stream/canonical-event.ts:9-24`）；reducer 对已存在 ID 直接 return（`chat-stream-reducer.ts:190-234`）。 | 成立 |
| S7 | `personal_assistant` 只经 `agent.sdk`，IM 不依赖 agent，双方走网络协议 | 顶层边界在 `SPEC.md:132-160`；design 未引入反向 import。 | 成立 |
| S8 | 外部回复不能等待 IM；恢复事实先 durable，user anchor 先于 Agent，配置边界等待 anchor | current inbound 在 run 前同步/持久 user saga（`inbound_pipeline.py:149-190`），observer 在 provider send 前 prepare output（`observer.py:247-270`），canonical 要求 IM 离线主路径继续（`docs/specs/gateway/relay-protocol.md:153-187`）。 | 成立 |
| S9 | 一个 run 可产生多个可见气泡，不能用文本或晚到 kernel id 作为主身份 | current roll 由新 assistant `message_id` / steer consume 驱动（`observer.py:50-127,585-664,1091-1135`）；当前 plain fallback 仍可能用 ordinal，但 design 改为 pre-live bubble ordinal，方向有事实基础。 | 成立 |
| S10 | 恢复只呈现终态，recording 不应冒充 completed | incident 明确终态不重演（`incident.md:35-37,174-178`）；current store 只恢复已准备 plain output，尚无 rich recording 状态，属于本 unit 正要补的缺口。 | 目标约束成立 |
| S11 | 只处理上线后新 bubble，不清理已写入旧重复消息 | 用户 Q6 与非目标只明确“不迁移/清理已经写入的重复 plain 气泡”（`incident.md:51-53,213-218`）。design 对已写历史的边界成立，但扩展到未交付 pending row 触发 R1-C2。 | 部分成立 |
| S12 | composition 有用户未提交修改，实施必须保留 | `git status` 显示 `src/personal_assistant/gateway/composition.py` 已修改；本评审未碰该文件。 | 成立 |
| S13 | 深化现有 `ExternalShadowSagaStore`，不另造 outbox | production 唯一 saga store 在 composition 创建并由 sync/recovery 共用（`composition.py:387-401,514-525`）。 | 成立 |
| S14 | 复用 `ConnectionReadyCoordinator` 为唯一 reconnect recovery owner | 生产仅在该 coordinator 注入 recovery（`composition.py:514-525`）；其 task 去重/取消旧 epoch 在 `connection_ready.py:113-121`。 | 成立 |
| S15 | 可复用 caller idempotency 让 live/reconcile 命中同一行 | Repository 已有 scoped 唯一查找 seam（`messages.py:108-157`），但 live `on_turn_start` 当前未传 caller key（`event_bridge.py:138-179`），正是 M1 合理改点。 | 成立 |
| S16 | EventBridge/repository 已拥有富投影与 post-commit 事件机制 | EventBridge 声明并实际把消息投影与 conversation event 同步（`event_bridge.py:1-15,58-69`）；MessageRepository 产出完整 created payload（`src/IM/infra/repositories/_message_projection.py:55-79`）。 | 成立 |
| S17 | 复用 chat reducer/upsert 与现有视觉组件 | reducer 已有按 durable ID 合并与 `created_at + id` 排序（`chat-stream-reducer.ts:45-129`），新完整快照事件可落在该 owner。 | 成立 |
| S18 | 不从 Kernel transcript 追溯、不保存 raw replay log | Gateway 的可用生产事实来自 sdk session events；`assistant_message` 带正文/思考、tool events 带展示投影、`turn_end` 带整轮 usage（`src/agent/platform/hooks/builtins/realtime_stream.py:35-115,166-185`）。终态 projection 足以恢复大部分字段，但 per-bubble token 事实不完整，见 R1-C1。 | 部分成立 |
| H1 | feat-447 的 live 富气泡/外部正文分工仍是 current 行为 | Gateway external-channel spec 仍规定外部只镜像可见正文（`docs/specs/gateway/external-channels.md:79-98`），IM 过程区仍仅内部展示（`docs/specs/im/tool-timeline.md:187-199`）。 | 成立 |
| H2 | bugfix-471 durable saga 是当前直接前身 | current canonical 的 stable provider identity、crash replay、stable output identity 均在 `docs/specs/gateway/relay-protocol.md:153-187`；代码表/恢复路径吻合。 | 成立 |
| H3 | bugfix-491 要求 pending recovery 继续 | design 自身在 `design.md:43` 承认该约束，current `recover_pending()` 仍消费 `pending_outputs()`（`shadow_sync.py:317-366`）。决策 6 与此冲突，见 R1-C2。 | 成立但方案违反 |
| H4 | bugfix-496 listener 生命周期与本实现无依赖 | 本方案未改 Feishu listener owner，只在 runbook 要求真实 Feishu 独占 listener；生产改点均位于 shared delivery/IM seam。 | 成立 |

### 决策核实台账

| 决策 | 拍板 / 歧义 / 自洽 / 驱动 | 核实结论 |
|---|---|---|
| D1 durable rich snapshot | owner 与状态机已拍死，复用真实 saga seam，删除测试证明这不是只搬复杂度；但“每个 bubble 的 token”没有可用 source fact。 | 架构方向成立；R1-C1 阻断完整性。 |
| D2 pre-live stable `shadow_message_id` | 不依赖正文/kernel id，且 conversation-scoped caller seam 真实存在；与多 bubble roll 兼容。 | 成立。 |
| D3 live + ordered ACK barrier | 当前 Gateway 对 business frame 单线串行，ACK 释放 head（`src/personal_assistant/ws/im_connection.py:1358-1446`），因此 `message_completed` ACK 可以充当此前 frame 的 durable 屏障；外部 send 在独立路径，不必等待 IM。 | 成立。 |
| D4 atomic reconcile + full event | IM 拥有消息事务和 owner user-stream，归属合理；created_at 自检修订后与 current 前端排序一致。但 event wire 同时写“历史同形”与按 `message_id` upsert，见 R1-W1；source elapsed 还缺 canonical metrics delta，见 R1-C5。 | 部分成立。 |
| D5 terminal-only recovery | 复用唯一 reconnect owner，`recording/ready/reconciled/discarded` 分离清楚；同 key 可覆盖 commit-before-local-mark。 | 成立。 |
| D6 legacy rows 不迁移且不再消费 | “不迁移已写重复历史”有 incident 驱动；“停止消费未交付 pending output”没有，且反向违反必须保住的 pending recovery。 | 不成立，R1-C2。 |

决策对偶扫描未发现 D1–D5 之间的依赖方向冲突；D6 与“既有约束/相关历史”和 D5 的 pending 语义直接冲突。

### Incident 约束核实台账

| ID | incident 原子 | design 落点与结论 |
|---|---|---|
| Q1 | 全程离线也完整恢复富时间线 | D1/D4/D5 覆盖 durable snapshot 与 terminal reconcile；per-bubble token source 未闭合（R1-C1）。 |
| Q2 | 恢复显示最终历史，不重演流式过程 | D4 的完整 terminal event、不派生 delta/running 动画覆盖。 |
| Q3 | 中途断线补全原 bubble，不替换/新增 | D2 同 identity + D4 原子 reconcile 覆盖。 |
| Q4 | 所有使用 shadow 的 external channel 共享语义 | shared observer/store 属于通用路径，但 missing-stable-identity delta 明确降级为无 durable recovery，冲突见 R1-C3。 |
| Q5 | 自动恢复，打开页面无需刷新 | D5 reconnect owner + D4 replayable `message.reconciled` 覆盖。 |
| Q6 | 已写入历史的旧重复 plain bubble 不处理 | D6 的“不改旧消息”覆盖；停止消费未写入 pending 超出该澄清，见 R1-C2。 |
| I1 | IM 暂时离线/Gateway restart/recovery 不阻塞外部主回复 | D1 先 durable、D3 网络 side effect 后置、D5 异步 recovery 覆盖。 |
| I2 | 多 bubble 各自保留正文、思考、工具、token、耗时、终态 | identity/过程/elapsed/terminal 覆盖；token 只有 run 终态聚合事实，见 R1-C1。 |
| I3 | live/recovery 指向同一 bubble，重复恢复仍唯一 | D2/D4/D5 覆盖。 |
| I4 | 全程离线仍完整还原 | D1/D4/D5 覆盖，但受 R1-C1 与 R1-C3 限制。 |
| I5 | 中途断线原位补全 | D2/D3/D4 覆盖。 |
| I6 | 外部/IM 入口上下文、回复去向、群语义不变 | 方案只改 external-trigger shadow delivery；current trigger source / conversation identity 不变（`docs/specs/gateway/external-channels.md:59-77`）。 |
| A1 | 在线单富气泡唯一完整 | M1-C1 + D2/D3 覆盖。 |
| A2 | 同 run 多 bubble 依次唯一且字段归属正确 | bubble ordinal/process seq 覆盖顺序与归属；per-bubble token 未决（R1-C1）。 |
| A3 | 刷新在线历史一致 | 单 IM row + repository projection 覆盖。 |
| A4 | IM 离线时外部仍正常回复且不受拖延 | D3 + M2-C1 覆盖。 |
| A5 | IM 恢复后自动补完整历史 | D1/D4/D5 + M2-C1 覆盖，受 R1-C1/R1-C3 限制。 |
| A6 | 恢复直接呈 terminal 历史 | D4 与 delta-spec 覆盖。 |
| A7 | partial live 原 message id 补全 | D2/D4 + M2-C2 覆盖。 |
| A8 | 打开页面实时收敛、刷新一致 | `message.reconciled` + reducer + M2-C2/M2-C5 覆盖；wire 字段需消歧（R1-W1）。 |
| A9 | 飞书三旅程验证通用行为且回复去向不变 | runbook 1–3 + M2-C3 覆盖；通用契约仍受 R1-C3 限制。 |
| N1 | 不迁移/合并/删除已存在 duplicate plain bubbles | D6 保留旧数据，覆盖。 |
| N2 | 不重演打字/动画/等待 | D4 覆盖。 |
| N3 | 不改变外部平台收到的 thinking/tool/system event | 方案只改 Web IM shadow 投影，覆盖。 |
| N4 | 不改变普通 Web IM、触发路由、群聊、权限语义 | optional shadow fields + current fallback 覆盖；无普通消息结构改造。 |
| N5 | 不处理 Feishu listener orphan | 方案未包含 listener 改点，覆盖。 |

### Delta-spec 核实台账

| Delta 条目 | canonical 锚点 / 用法 / Scenario / 消费者可观察性 | 结论 |
|---|---|---|
| Gateway `external-channels.md` MODIFIED「IM 离线时飞书对话不阻塞」 | 精确命中 canonical 同名条目（`docs/specs/gateway/external-channels.md:204-218`），保留 1:1 与群聊两个原 Scenario 并加强恢复结果。 | 成立。 |
| Gateway `relay-protocol.md` MODIFIED「外部 channel 影子镜像以稳定事件身份可恢复补写」 | 精确命中 canonical `docs/specs/gateway/relay-protocol.md:153-187`，但没有保留原「Agent 镜像使用稳定输出身份」Scenario；另与 incident 的全 external-channel 语义有 missing-identity 冲突。 | R1-C4、R1-C3。 |
| IM `conversations-messages.md` ADDED「外部 channel Agent 富消息按稳定来源身份原位调和」 | 是真正新增的 IM 消费者契约，THEN 均为消息 id/历史/浏览器可观察结果，落在最窄消息 area。 | 成立。 |
| IM `gateway-relay.md` ADDED「外部 shadow live frame 携带稳定消息身份与源时间线事实」 | 是新增 wire 消费者契约，覆盖 idempotent turn_start、source seq 与 source elapsed；但 source elapsed 同时修改了 `response-metrics.md` 的 universal 起止口径，未提供对应 MODIFIED delta。 | R1-C5。 |

### Milestone 核实台账

| Milestone | 拆分、范围与两轨退出 | 结论 |
|---|---|---|
| M1 live-mirror-identity | 是在线可观察的端到端纵向切片，Gateway + IM 同时改，非按层横切；M1-C1 reviewer 轨与 M1-C2/C3 worker 轨齐。 | 拆分成立；M1-C1 的多 bubble token 表述受 R1-C1 阻断。 |
| M2 rich-shadow-recovery | 建立在 identity seam 上，覆盖 store/IM/frontend/reconnect/三旅程，reviewer 与 worker 两轨齐；与 M1 串行且显式依赖，不宣称并行无交集。 | 拆分成立；受 R1-C1/R1-C3/R1-C5/R1-W1 阻断。 |

多 milestone 命中“跨多个 owner、超过单 worker 合理窗口且需先验证 identity 再验证完整恢复”的举证；两步均有独立用户价值，不属于 backend/frontend 或 implementation/test 横切。

### 整体判断

- 上层综述、Before/After 与两张图能直观看出“Gateway durable snapshot 是恢复事实，live 与 reconcile 共享一条 IM identity”，没有被取证细节淹没。
- 主数据流从 Kernel session event 到 Gateway store、WS/HTTP、IM row、owner user-stream、browser reducer 闭合；作者的 created_at 自检修订与 current `compareMessages(created_at,id)` 排序规则一致，消除了全离线 Agent 排到迟建 user anchor 前的风险。
- 风险/回退覆盖 ACK 竞态、elapsed 双口径、partial reconnect、SQLite 写放大与回退分层；legacy pending 风险的“接受”缺少 incident 授权，已升级为 R1-C2。
- 常驻 IM/Gateway/前端均给了可执行的隔离重启、健康检查和真实飞书旅程；未发现模板残留、TBD、命名漂移或空退出标准。

### 架构进攻

| 角度 | 主动攻击与证据 | 结论 |
|---|---|---|
| 归属 | durable external source facts 当前已经由 Gateway-local saga 持有（`composition.py:387-401`），中心消息/事件由 IM repository/EventBridge 持有（`event_bridge.py:58-69`），browser merge 由 chat reducer 持有（`chat-stream-reducer.ts:45-149`）。把 snapshot/identity/reconcile 分别放回这三个 owner，依赖仍是 Gateway↔IM 协议，不触碰 `SPEC.md:157-160` 红线。 | 归属最自然，未发现反向依赖；source elapsed 的长期契约归属漏在 metrics area，R1-C5。 |
| 该不该存在 | 删除新 `shadow_message_id` 会回到 live 与 HTTP 两 writer 身份分裂；删除 durable snapshot 会让全离线富恢复无事实来源；删除 reconcile endpoint 会迫使 caller 逐字段拼 HTTP/WS patch。三者均实质集中 identity、projection、atomicity，不是为未来多态预造的 wrapper。 | 新增 seam 均有必要；未发现多余 factory/Protocol/第二 outbox。 |
| 深还是浅 | `record/pending_snapshots/acknowledge` 把表结构、ordinal、seq、state/ACK 隐藏在 store 后，接口显著小于内部复杂度；IM endpoint 隐藏 get-or-create + full-row transaction + event publish。独立 grep 未发现可复用的 existing rich terminal reconcile；current create 只命中 key后返回旧行（`messages.py:124-157`）。 | 是 deep module；event projection 的 `id/message_id` 接缝还没拍死，R1-W1。 |
| 治本还是补丁 | 共享 pre-live identity 正面消除 duplicate 的双 writer 根因，durable rich snapshot 同时解决全离线降质，不是禁用 live 或删除 recovery。相反，停止消费 legacy pending 只是把既有恢复债冻结为永久缺失，长期会留下“升级前已 durable、升级后永不投递”的状态分叉。 | 核心方案治本；D6 的 pending 处理是行为回退，R1-C2。 |

### Issues

- [R1-C1][CRITICAL] [决策 1 / 决策 3 / M1 / M2]: design 要求“每个逻辑气泡”都保存并恢复 token，但当前允许的 Gateway session-event seam 只在 `turn_end` 给出整轮累计 usage；`assistant_message` 不带 usage（`src/agent/platform/hooks/builtins/realtime_stream.py:35-64,166-185`），当前多气泡 roll 收旧泡时明确发送 `token_usage=None`（`src/personal_assistant/gateway/runtime_delivery/observer.py:87-99`），只有 run 最终泡在 `turn_end` 得到整轮 aggregate（`observer.py:803-855`）。design 同时写 `kernel: no spec delta`、不用 Kernel transcript，也没有拍板 aggregate 应只归最终泡、按 LLM round 拆分、还是新增 sdk event fact。因此 worker 无法从现有事实实现 incident `incident.md:145-149` 的“每条气泡各自 token”，两个实现者会产出不同指标语义；不先解决会让 M1-C1/M2-C1 无法按文档验收。
- [R1-C2][CRITICAL] [决策 6 / 风险与回退]: Q6 只授权不迁移或清理“已经写入 Web IM 历史”的旧 duplicate bubble（`incident.md:51-53,213-215`），incident 同时明确必须保住 bugfix-491 的 pending replay，不能靠跳过 pending 消重（`incident.md:100-102`）。current recovery 会继续消费所有未确认 `external_shadow_outputs`（`src/personal_assistant/gateway/shadow_sync.py:362-366`），但 D6 改成部署后永不消费这些未交付 row。它们不是“既有重复历史”，而是尚未完成的 durable obligation；不改会使升级前已经承诺可恢复的 Agent 回复永久缺失，并让 design 自己的“不能跳过 pending”现状约束失真。
- [R1-C3][CRITICAL] [incident Q4 / 决策 2 / Gateway relay delta]: incident 把“唯一富消息 + 完整离线恢复”定义为所有使用 shadow conversation 的 external channel 通用语义（`incident.md:43-45,196-203,207-212`），但 delta 保留“adapter 缺 stable event id 时仍可 live shadow、却不创建 durable shadow sync”的降级。current 代码确实会在 saga `prepare()` 返回 `None` 后继续建 live shadow conversation/user message（`src/personal_assistant/gateway/shadow_saga.py:166-170`; `shadow_sync.py:93-200`），而 D2 的 `shadow_message_id` 又必须以 `saga_id` 生成。结果是同样使用 shadow conversation 的 adapter 因 identity 缺失无法获得本 unit 的 recovery 保证，直接缩小 Q4 范围。需要在 design/spec 层拍死：要么所有 shadow-capable external adapter 必须提供 stable identity，要么首文档明确接受该例外；worker 不能自行改产品范围。
- [R1-C4][CRITICAL] [delta-spec `gateway/relay-protocol.md`]: 该文件以 MODIFIED 替换 canonical 同名 Requirement，却静默删除了原 Scenario「Agent 镜像使用稳定输出身份」及其两项保证：final 与其他 output 的 identity 规则、正文变化/provider response id 不改变 source identity（current `docs/specs/gateway/relay-protocol.md:183-187`）。`docs/specs/CONTRIBUTING.md:133-154` 要求 MODIFIED 写替换后的完整条目；归并当前 delta 会让仍需保住的 caller crash/retry 身份契约从 canonical 消失。即使新 bubble ordinal 方案意图 supersede，也必须把原 Scenario 忠实改写进新 identity 语义，不能让 orchestrator 在归并时无声删约束。
- [R1-C5][CRITICAL] [delta-spec / 决策 4]: external shadow 现在改为 Gateway source start/finish 计算 authoritative elapsed，IM 原样持久化；这修改了 current `response-metrics.md` 的 universal 契约——当前明确规定所有 Agent `elapsed_ms` 都是 IM `message.created_at` 到 IM 收尾时刻的差（`docs/specs/im/response-metrics.md:14-30`），生产 `EventBridge` 也确实按 IM `now-created_at` 计算（`src/IM/application/event_bridge.py:297-345`）。新增 `im/gateway-relay.md` 只描述 wire 字段，不能防止 canonical metrics area 在归并后同时宣称相反口径。缺少对 `docs/specs/im/response-metrics.md` 的精确 MODIFIED delta 会使收尾 canonical 自相矛盾，并让 worker/reviewer不知道 external shadow elapsed 应按哪条验收。
- [R1-W1][WARNING] [决策 4 / IM wire interface]: `message.reconciled` 被定义成“与历史读取的完整消息 projection 同形”，但下一句要求 reducer 按 `message_id` upsert。current `MessageResponse` 的主键字段是 `id`（`src/IM/api/routes/messages.py:123-146`），current canonical user-stream event 的主键字段是 `message_id`（`src/IM/frontend/src/realtime/user-stream/canonical-event.ts:73-89`）。如果 backend worker按历史同形发 `id`，frontend worker按 event 约定读 `message_id`，打开页面不会实时收敛；如果两边另加转换，文档又没说明 owner。请把 event payload 精确拍成一种 wire shape（例如 canonical event envelope 使用 `message_id`，内部由 `MessageResponse.id` 显式投影），消除跨端猜测。

### Recommendations

- [R1-R1] 先决定多 bubble token 的真实产品口径，并让 source event / kernel delta / incident 与 milestone 使用同一口径；不要让 worker在实现时临时分摊整轮 usage。
- [R1-R2] 将 legacy “已写重复历史”与“未交付 pending obligation”分开；后者继续可恢复，或由首文档显式授权新的终止语义。
- [R1-R3] 对 external adapter 的 stable identity 设准入契约，或回到 incident 明确通用语义的例外边界。
- [R1-R4] 修全 Gateway MODIFIED Scenario，并增加 IM `response-metrics.md` delta，再进入实施。
- [R1-R5] 在 wire interface 中给出 `message.reconciled` 的唯一字段命名与 history→event 投影规则。

### Author Resolutions

| Issue | Resolution |
|---|---|
| R1-C1 | 接受。incident、决策 1、delta-spec、Runbook 与 M1/M2 已统一为 current online 口径：中间气泡 `token_usage=null`，最终气泡承载 `turn_end` 的整轮累计 usage；不新增 Kernel delta，不推算或分摊不存在的逐气泡 usage。 |
| R1-C2 | 接受。决策 6 改为区分“已写 IM 历史”与“未交付 obligation”：前者不迁移/清理，升级前 legacy pending 继续现有 plain replay 直至 ACK；上线后新 bubble 只写富快照。 |
| R1-C3 | 接受。typed provider-stable event identity 改为进入 shadow conversation 同步的准入条件；缺失身份时外部 run/reply 继续，但跳过全部 shadow 写入并暴露 contract failure，不形成无法兑现完整恢复的降级 shadow 历史。 |
| R1-C4 | 接受。Gateway MODIFIED requirement 已恢复并重写“Agent 镜像使用稳定输出身份”Scenario，以持久 bubble ordinal 统一 final/中间气泡，保留正文变化与晚到 provider/Kernel id 不改变身份的约束。 |
| R1-C5 | 接受。新增 `specs/im/response-metrics.md` 的精确 MODIFIED delta：普通消息沿用 IM `created_at → terminal`，external shadow 使用 Gateway source begin/terminal 的权威 elapsed，live/recovery 同值。 |
| R1-W1 | 接受。`message.reconciled` wire 主键固定为 `message_id`；IM event builder 显式执行 `MessageResponse.id → message_id`，前端只按 `message_id` upsert，事件不重复发送 `id`。 |

## Round 2

### Metadata

- reviewer: `/root/bugfix_497_design_review`
- review_mode: `delta`
- mode_reason: `作者修订集中在 R1 六项问题及其可枚举的 incident/design/delta-spec/milestone 原子；核心 owner、稳定消息身份、terminal snapshot 数据流与两阶段 milestone 拆分未变化，因此复用 Round 1 完整台账，重查历史问题闭环、上下游波及及受影响架构角度。`
- started_at: `2026-08-04T12:38:04+08:00`
- completed_at: `2026-08-04T12:40:27+08:00`
- duration: `2m23s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 历史问题：逐条重查 R1-C1 至 R1-C5、R1-W1 的 Author Resolution 与当前落点。
- changed atoms：incident token 语义；design 决策 1/2/4/6、风险、Runbook、M1/M2；Gateway relay MODIFIED；新增 IM response-metrics MODIFIED；IM conversations/reconcile wire。
- 生产与 canonical 证据：Kernel/Gateway token source、legacy pending recovery、typed provider identity/Feishu mapping、Gateway 原稳定输出身份 Scenario、IM elapsed current behavior、REST/event 主键 shape。
- retained_from: Round 1 — stable bubble identity、durable rich snapshot、ACK 屏障、terminal-only recovery、组件 owner、主数据流及 milestone 拆分均未改变，本轮修订没有使其证据失效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 中间 bubble `token_usage=null`，最终 bubble 保存 `turn_end` 整轮 aggregate，不新增 Kernel delta或分摊。 | current `assistant_message` 不含 usage，只有 `turn_end` 带整轮 usage（`src/agent/platform/hooks/builtins/realtime_stream.py:35-64,166-185`）；current roll 对中间泡发送 `token_usage=None`，最终泡才投影整轮 usage（`src/personal_assistant/gateway/runtime_delivery/observer.py:87-99,803-855`）。incident `:37,107,128,149,171`、design `:27,74-76`、Gateway/IM delta 与 M1/M2 现已统一使用该口径。 | closed |
| R1-C2 | 已写 legacy 历史不迁移；升级前 pending output 继续 plain replay 至 ACK，新 bubble 只走富快照。 | current obligation owner 仍在 `recover_pending()` 消费 `pending_outputs()`（`src/personal_assistant/gateway/shadow_sync.py:317-366`）；design `:30,138-142,209` 明确两代写入/消费边界，M2-C4 要求覆盖 legacy retry，既不伪装富恢复也不冻结 bugfix-491 obligation。 | closed |
| R1-C3 | provider-stable event identity 成为全部 shadow sync 的准入条件；缺失时只继续外部主回复。 | typed identity 已存在于 `InboundMessage.external_event_identity`（`src/personal_assistant/channels/base.py:9-19,23-46`），Feishu 两条生产入站均以 app id + message id 提供它（`src/personal_assistant/channels/feishu/adapter.py:371-383,432-442`）。design `:29,84-90` 与 Gateway delta `:7-9,44-48` 现在要求在 shadow conversation/user/Agent/config-boundary 之前整体拒绝，修正了 current `shadow_sync.py:76-200` 在 saga 缺失后仍可能建 shadow 的降级分叉；M2-C3 给出跨 adapter contract 退出标准。 | closed |
| R1-C4 | 恢复并按 bubble ordinal 重写稳定输出身份 Scenario。 | current canonical 原 Scenario 位于 `docs/specs/gateway/relay-protocol.md:183-187`；MODIFIED delta `specs/gateway/relay-protocol.md:50-54` 完整保留“同一 source identity”“正文/provider response id 不改变身份”，并把 final/中间输出统一为持久 ordinal，符合 MODIFIED 全条替换规则。 | closed |
| R1-C5 | 新增 response-metrics 精确 MODIFIED delta，区分普通与 external shadow elapsed。 | canonical 同名 Requirement 当前只允许 IM `created_at → completion`（`docs/specs/im/response-metrics.md:14-30`），生产也按该差值计算（`src/IM/application/event_bridge.py:297-345`）。新 delta `specs/im/response-metrics.md:7-29` 精确锚定同名条目，保留普通消息与历史/进行中三个既有 Scenario，并新增 source elapsed Scenario；design `:112,158,196-200,203-210` 已接入同一口径。 | closed |
| R1-W1 | canonical event 只发 `message_id`，由 builder 显式执行 `MessageResponse.id → message_id`。 | current REST projection 主键为 `id`（`src/IM/api/routes/messages.py:123-146`），current user-stream message 主键为 `message_id`（`src/IM/frontend/src/realtime/user-stream/canonical-event.ts:73-100`）。design `:104-114,156-160`、IM messages delta `:27-31` 与 M2-C5 明确唯一转换 owner、wire shape 和 reducer key，不再要求两端猜测。 | closed |

### Changed atoms 与波及链

| 修订原子 | 上下游波及核实 | 结论 |
|---|---|---|
| token 在线同口径投影 | Kernel source fact → observer roll/final → durable snapshot → reconcile/history → incident Scenario 与 M1/M2 退出标准全部使用“中间 null、最终 aggregate”。没有新增不存在的数据源，也没有 consumer 仍要求逐泡非空 usage。 | 自洽。 |
| legacy 与新富快照分代 | 既有 SQLite pending output 保持原 caller key/plain writer；新 run 只进 rich snapshot；同一 reconnect owner 先履行既有 obligation，再处理 ready snapshot。风险与 worker 测试都覆盖代际边界。 | 自洽。 |
| stable identity admission | adapter typed identity → Gateway shadow admission → saga/user anchor/bubble/config boundary 共用准入；缺失时 shadow target 不形成，但 session run 与 external reply 不依赖该 target。通用产品语义因此只对真正进入 shadow path 的 adapter 成立。 | 自洽。 |
| elapsed 与 reconcile wire canonicalization | Gateway source elapsed 同时进入 live terminal 与 recovery snapshot；IM metrics MODIFIED 负责长期口径。IM 内部 `MessageResponse.id` 只在 event builder 边界转换为 `message_id`，browser reducer 与 replay 使用同一 key。 | 自洽。 |

### 受影响的架构进攻

| 角度 | 本轮攻击与结论 |
|---|---|
| 归属 | stable identity 准入留在 Gateway external inbound/shadow owner；elapsed 的例外契约落到 IM metrics canonical；REST→event 字段转换由 IM event builder 持有。三项均在事实生产者或协议 owner 内，没有把 adapter/浏览器细节反推到 Kernel，也未形成跨包 import。 |
| 深还是浅 | legacy plain drainage 沿用现有 `pending_outputs()`，新富恢复继续隐藏在 saga store 的 `record/pending_snapshots/acknowledge` 接口后；这是有边界的兼容义务，不是第二套长期 outbox。`message.reconciled` 只在一个 builder seam 做字段投影，没有让两端重复适配。 |
| 治本还是补丁 | identity admission 从源头禁止“可 live shadow 但不可 durable recovery”的半能力；legacy pending 继续消费则保住已承诺事实，同时禁止新数据再进入旧表，状态分叉会随 ACK 排空而收敛。两项修订均移除了 R1 指出的根因级矛盾，没有以跳过、清理或伪造数据掩盖。 |

“该不该存在”沿用 Round 1：本轮没有新增模块、factory、Protocol 或恢复 owner，原删除测试结论未失效。

### Issues

- 无。

### Recommendations

- 无阻断建议；当前 design 可进入 `change-orchestrator` 实施。
