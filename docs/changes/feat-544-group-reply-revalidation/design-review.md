# feat-544 Design Review

## Round 1

- reviewer: `/root/feat_544_design_reviewer`（首次独立 reviewer）
- review_mode: `full`
- mode_reason: R1，完整检查五类承重原子及四个架构进攻角度。
- started_at: `2026-09-09T09:26:09+08:00`
- completed_at: `2026-09-09T09:29:49+08:00`
- duration: `220 秒（可核对计时区间）`
- timing_note: 开始读取输入前未记录时钟；started_at 是首次取得的时钟值，早于此的阅读取证未计入 duration，不能据此称为完整审查耗时。
- validated_at: main `382142c56ea36a4bd4ac2dabdff9565c6d198315` + 当前工作区 feat-544 文档；不是已实施代码验收。

### Verdict

**Issues Found — 1 CRITICAL / 0 WARNING。** 并发边界与职责划分可成立；IM delta 留下新旧 Process 空态规则冲突，需要修订后复审。没有启动实施、服务、分支或提交。

### Coverage

完整读取 spec.md（包括原始需求、后续澄清、S1–S7、8 个 Requirement / 21 个 Scenario、范围与非目标）、design.md（G1–G8、6 个决策、接口、Process 记录、原型契约、风险、runbook、M1）、三个 delta 和 prototype.html；确认 M1-impl 仅有空 .gitkeep。读项目路由、change-workflow、三个包 spec 入口与相关 canonical area。代码核实从 Gateway composition/product、SDK submit、runtime loop、IM WS execution 正向进入真实实现；没有拿 prototype 当真实产品旅程，也未将作者的模型依赖探测当本轮功能验收。

以下路径相对仓库根。证据描述的是本轮实际读到的源码与文档。

### 核实台账：现状、约束与复用

| 原子 | 核实结果与证据 |
|---|---|
| G1 门控/活动运行注入 | 成立。composition.py:643/679 实际装配 coordinator/pipeline；inbound_pipeline.py:132/171/350 门控、缓冲、ALWAYS 分支；session_run_coordinator.py:478 调 try_steer 并在 491 保存 pending_id。 |
| G2 SDK→runtime→loop/终态较晚 | 成立。src/agent/sdk/kernel.py:1773 调 registry.submit；core/runs/registry.py:271/282 创建 controller、调 executor；core/agent/runtime.py:256/1895 创建/执行 AgentLoop；loop.py:380 drain、493 附近 hooks/yield，638 才 terminal re-drain。 |
| G3 共享短锁/普通 drain | 成立。run_control.py:65–98 cancel/abort/publish 共用锁，123–144 enqueue 同锁；187–189 普通 drain 没有持该锁。设计把 revision 与 drain 一并原子化有必要。 |
| G4 provider/工具收口 | 成立。loop.py:519 起逐工具 add_tool、随后收早完成结果并推迟历史配对；openai_compat/client.py:168 聚合 text_buffer；anthropic/client.py:174–188 按 content_block_stop yield。 |
| G5 输出 stop 防护/observe 不是门禁 | 成立。runtime.py:1339–1359 observe 异常返回；1384–1387 assistant_message 的 publisher 只作 publish_if_active。把新鲜度判定放 loop/controller 避免 hook 吞错。 |
| G6 send_message 真出口/身份/presenter | 成立。product.py:432 注册真实工具；send_message.py:22–32 起始 detail 含 text，164 起 payload 有 session/agent/tool_call 身份但无轮次；composition.py:828 装 handler，internal_dispatch.py:174 附近 await manager.send_agent_message。 |
| G7 消费切段/count 关联 | 成立。coordinator.py:2513 在 stream 中附消费身份；3060–3106 用 user_message_count/message_count 切 follower；observer.py:1897–1973 在消费时 roll_bubble。 |
| G8 IM 存储/共享 seq/前端 Process | 成立。src/IM/app.py:347 装 EventBridge；ws/gateway/execution.py:310/367/374 路由正文/思考/工具；event_bridge.py:193–215 存 message_delta，294–312 存 thinking；repositories/messages.py:733–744 给过程 seq；tool-calls-panel.tsx:51–74 按 seq 混排。 |
| 包依赖约束 | design 把群判断/消息引用放 PA，通用控制放 agent，IM 只存展示；符合 AGENTS.md 架构红线和三个包 spec.md Purpose。 |
| 接受范围/排除入口 | design 决策 1、2 对齐 spec 澄清“保护范围以 Gateway 已按既有策略接收的新消息为准”；MENTION 缓冲不是缺陷。 |
| pending FIFO / 同-run / recovery | run_control.py:123–163、kernel/runs.md 的 steer/自动恢复 Requirements 已提供 identity、FIFO、非用户终止交接；design 决策 3 保留预算前检查与未消费交接。 |
| 复用消费切段及单次 usage | observer.py:61–159 现有 close/open/repoint；关闭旧块 token_usage=None，设计沿用真实 run 单次结算，片段不冒充 run。 |
| 不增房间版本服务/模型 | 首文档明确排除房间版本仲裁和远端未到消息一致性；controller 的两个 revision 是当前局部问题所需状态。 |
| current grounding 声明 | 新鲜度确实是新增能力；但 Process 空态会修改现有规则，不能仅以“没有新鲜度契约”推断全部是平行新增，见 R1-C1。 |

### 核实台账：六项决策与接口

| 原子 | 拍板、完整性、自洽及驱动核实 |
|---|---|
| D1 按 run opt-in | 布尔默认 False、可信 Gateway 路由、continuation/recovery 继承均拍死；对应 S6 / Open chat 排除，无产品语义下沉 core。 |
| D2 accepted/context revision | 同锁排 enqueue/commit 先后，fresh/stale/inactive、expected_run_id、同步窄 publisher 都明确；对应公开前检查且不冒充读过最新版本。不能以远端显示顺序扩大保证。 |
| D3 候选与同模型继续 | 明确正文块按原顺序、已执行工具合法配对、usage/预算计数、withheld 历史/compact 语义；S3/S5 要求能追到落点。预算不足前不消费，比已有 terminal drain 路径需要改动之处已写出。 |
| D4 同群工具 | ToolContext 可信轮次→HTTP→dispatcher→SDK；同群条件、锁内入队/锁外 ACK、held 正常结果及保留去重明确；匹配 S6。现有 handler 只注入 legacy kernel client，实施时需把 SDK seam 按文档接通，不能直接假设 shim 已有新方法。 |
| D5 草稿→消费→新段 | 指定精确 pending_ids、批次最后来源、双向定位、实际调用才显示复核、工具归属及无草稿不造记录；覆盖 S7。静默 token 不展示也不加许可。 |
| D6 typed Process | reply_process_json、seq/item_id、DTO/WS/history/sync/fork/空块保留职责明确，无独立草稿系统；但 canonical 空态更新遗漏，见 R1-C1。 |
| 提交接口闭合 | loop 和 Gateway 两个调用方共享 controller；同步 callback 不 await/IO/重入；session 不存在或 run 换代零副作用拒绝。避免旧 check-then-send 窗口。 |
| 事件闭合 | draft/consumption 可靠 stream、coordinator 关联来源、observer 负责投影；事件不借 message_delta 泄漏正文。pending 的 IM id 在 PA 保留，core 仅 opaque id。 |
| 持久化记录闭合 | draft/revalidation/handoff 数据、稳定 ID 与上/下段关系、来源丢失快照、已存记录可重放均定义；进程崩溃不恢复未发候选是明确非目标。 |

### 核实台账：spec 用户场景与澄清

| 原子 | design 覆盖证据 |
|---|---|
| S1 正常回复 | D2 fresh、D3 完整发布；M1 R1。 |
| S2 Agent 更新/补充/分歧 | D1 原门控、D3 同模型续轮、D5 保留静默许可；M1 R1。 |
| S3 真人文本/附件更正 | D3 保留原始新消息身份和图片、先 withheld 后续轮；W1 图片不丢。 |
| S4 原文可用/再次更新 | D2 每次提交重新比较，D3 无解释模板要求；M1 R1。 |
| S5 回复责任/预算/stop/new | D3 原终态/recovery、D5 原静默规则、M1 R2/W2。 |
| S6 来源和排除入口 | D1 当前普通群 opt-in、D4 同群工具、后台 continuation 继承；M1 R2。 |
| S7 过程与新段 | D5、D6、Process 三种记录、prototype must-match、M1 R3。 |
| 澄清 MENTION 与 ALWAYS | D1 不改 admission；与 inbound_pipeline.py:350 核实一致。 |
| 澄清 Open chat 为单聊 | D1 direct 不开；M1 R2 指定从 Agent 详情打开。 |
| 澄清非逐 token 现状 | G4 与 provider 代码核实，不把事件流等同逐字流；D3 仍明示整轮暂存。 |
| 澄清静默规则不变/撤回三次暂停 | D3/D5 不加暂停/强发/新静默出口。 |
| 澄清允许设计但未允许实施 | 本轮仅报告；design 的状态、unit branch 待 orchestrator 创建一致。 |
| 澄清 Process/后续工具位置 | D5 先草稿后切段；旧块不移动、后续工具在新块。 |
| 澄清真实草稿可见与交互确认 | D6 全文持久化；prototype draft 用 details 默认折叠。 |
| 当前群范围最终确认 | D1/D4 排除跨群目标复核，覆盖普通正文/同群工具/后台返回续跑。 |

### 核实台账：全部 Requirement / Scenario

| Requirement / Scenario 原子 | 覆盖证据 |
|---|---|
| 群聊发言公开前结合新消息 | D1–D3；范围为已接受消息。 |
| 没有新消息时正常发送 | D2 fresh，D3 完整发布。 |
| A 未提及 B 的更正影响回复 | D1 ALWAYS admission，D3 新消息同模型续轮。 |
| 真人更改输出要求 | D3 withheld + 原输入。 |
| 附件补充也被考虑 | D3 身份/图片保留；W1。 |
| 复核遵守原回复与静默规则 | D3/D5；不新增选择。 |
| 原本允许静默 | D5 process-only + 协议 token 过滤。 |
| 原本不允许静默 | D3 不增静默/暂停出口，M1 R2。 |
| 有不同意见仍能发言 | D3 继续原回复规则而非互斥禁言。 |
| 原结论适用可原文发送 | D3/D5；不要求复核套话。 |
| 复核期间又更正 | D2 每次 commit 复验，D5 再次采纳再切段。 |
| 草稿不提前公开 | D3 候选暂存、D4 工具提交、D6 非 message_delta。 |
| 长回复无旧正文闪现 | D3/D6 完整未发送 Process，M1 R1/R3。 |
| 同时完成后发衔接讨论 | D2 对已接受更新线性化；按最终澄清解释此 Scenario，未到本机的消息明确不承诺。 |
| 原有失败与停止 | D3 原终态、D4 网络失败区别 held。 |
| 无法复核时明确失败 | D3 原失败反馈且不强发旧稿；M1 R2。 |
| stop/new 不补旧稿 | D2 inactive 零副作用，D3 原控制；D6 已存 Process 保留。 |
| 来源一致且不扩大唤醒 | D1/D4。 |
| 工具发送/后台续跑 | D1 继承 opt-in，D4 SDK seam；M1 R2。 |
| 空闲 MENTION 不额外唤醒 | D1 保留 admission。 |
| 其他聊天/真人不被拖住 | 每 run 锁且不跨 await；D1 排除 direct/external。 |
| Open chat 单聊保持体验 | D1 默认 False，M1 R2。 |
| Agent 详情页打开单聊 | Runbook 指定真实入口回归。 |
| Process 保留真实未发送草稿 | D3 完整候选，D6 完整存储。 |
| 查看未发送草稿 | D6 默认折叠全文/历史；原型第 7 行 details。 |
| 复核与工作对应更新分段 | D5 精确 identity/批次切段。 |
| 复核/工具结果在更新下方 | D5/D6、M1 R3。 |
| 原文保留或原许可静默 | D5 新块正文或 process-only；M1 R3。 |
| 成批/再次更新 | D5 每批一次，Process item_id 重放幂等。 |

### 核实台账：非目标

| 原子 | 不越界证据 |
|---|---|
| 跨群/远端未到/房间仲裁 | D1 跨群不检查、D2 本机入队边界。 |
| 外部群/direct/CLI 行为变化 | D1 默认关闭；cli 显式 no spec delta。 |
| 通知箱/主持/轮流/任务认领/全局规划 | 未引入对应组件；只有现有 run 的提交检查。 |
| 新静默/冲突暂停/强发/审批/草稿编辑/崩溃恢复 | D3/D5 明确禁止；D6 仅可读草稿并说明崩溃恢复不保证。 |
| 消灭语义重复/事实错误 | 风险段接受原文仍可合理使用；无语义判官。 |
| 撤销工具/防重复执行 | D3 已启动工具照常收口，D4 不回滚其他工具。 |
| 撤回已公开消息/所有展示算更新 | D2 提交后不撤；D6 Process 不 fanout。 |

### 核实台账：delta-spec

| 条目 | canonical / 用法 / Scenario 核实 |
|---|---|
| kernel ADDED 消费者可启用输出前复核 | target runs.md 合适，默认 opt-in 新契约；五个 Scenario 分别覆盖新输入、fresh、产品工具、预算中断、默认关闭。THEN 是 SDK 消费者可观察的 stream/回调结果，无内部 helper 断言。 |
| gateway ADDED 内置当前群提交前复核 | target routing-delivery.md 合适；六个 Scenario 覆盖 ALWAYS、图片、fresh/后到、排除入口、后台、再次更新/显式控制。没有改 MENTION 唤醒规则。 |
| gateway MODIFIED 产品工具投递 | 精确匹配 canonical routing-delivery.md:372 的标题；原三 Scenario 保留，新增 held 情形。成功场景按本 Requirement 新增复核前置理解；网络错误与 held 有明确区别。 |
| im ADDED 真实草稿/复核分段 | 六个 Scenario 的 THEN 均用户可观察，target tool-timeline.md 合适；新记录本身可以 ADDED，但影响现有“无过程项”条件却未提供 MODIFIED，R1-C1。 |
| cli no delta | D1 默认关闭，M1 W2 要求默认行为回归；符合无产品变化。 |

### 核实台账：Milestone、原型与整体完整性

| 原子 | 核实结果与证据 |
|---|---|
| M1 impl | 单一垂直能力跨三个包，没有横切拆分或并行范围碰撞；M1-impl 仅 .gitkeep，没有提前 tasks/progress。 |
| M1 R1 | 对齐 S1–S4，明确文本/图片与旧正文不公开；可由真栈观察。 |
| M1 R2 | 对齐 S5–S6，工具/后台/控制/排除入口齐。 |
| M1 R3 | 对齐 S7 与 must-match，历史/窄屏/批次/全文可验。 |
| M1 R4 | fanout 和预算终态有具体消费者结果，不是“实现功能”。 |
| M1 W1 | SDK 实际 seam 两出口竞态、stop、hook 失败、输入保真。 |
| M1 W2 | provider 多块/并行工具/held/transcript/usage/默认行为。 |
| M1 W3 | 完整存储、唯一 seq/id、重放/空块/真实浏览器证据。 |
| M1 W4 | 边界、相关测试、Ruff/docs/build、归并原 Scenario、产物清洁。 |
| 原型 | 读到五个场景切换、details 全文默认折叠、旧/新段锚、再次更新；响应式 CSS 在 720px 切换。未渲染截图，作者也未伪称截图验收。 |
| 人读层 | 总览一句话、图、每个决策粗体结论能串起方案；细节放下层，未发现需 worker 猜核心拓扑之处。 |
| 风险/回退 | 连续更新成本、完整文本成本、两出口漂移、additive schema、崩溃边界均有应对或明确接受。 |
| runbook | 提供隔离 down/config/up、IM 健康、Gateway 日志健康地址、模型依赖前置与实际 UI 驱动；不要求动生产。属于后续验收计划，当前不执行。 |
| 文档结构 | 标题、对齐、待建 unit branch、空 Changelog、图、三个 delta、milestone 表齐；不存在 TBD。 |

### 架构进攻

| 角度 | 实际挑战与结果 |
|---|---|
| 归属 | 尝试把 revision 放 Gateway：会复制 pending 生命周期且普通内核输出仍有独立出口。放 controller 与既有 enqueue/abort 锁一致；群匹配、source id 仍在 PA；IM 不 import agent。未发现反向依赖。 |
| 该不该存在 | 删除两个 revision 只能查队列，无法把“模型已读批次”与当前 accepted 状态绑定；删除 draft Process 会违反 S7 全文历史。没有多态工厂、独立 draft service 或房间仲裁；增加状态均有场景必要性。 |
| 深还是浅 | 已独立 grep 出 RunController.publish_if_active、observer.roll_bubble、IM 共享 seq，方案均复用；新 SDK seam 隐藏锁/active lookup，比让 PA 知内部 registry/controller 深。typed Process 避免假工具计数，而非重复 Timeline。 |
| 治本还是补丁 | 同一提交锁同时覆盖 ordinary/send_message，截止点明确为本机不可变任务入队；没有先 GET revision 再异步发送或重试后永久放行。它正面解决已接受未消费输入窗口；远端发布顺序竞态是已确认非目标，不要求额外分布式锁。 |

### Issues

- **[R1-C1][CRITICAL] IM delta 缺少对既有 Process 空态 Requirement 的 MODIFIED。** 定位：`specs/im/tool-timeline.md` 只有 ADDED；design 决策 5/6 与 Process 最小记录允许无 thinking/tool/background、仅 revalidation/draft 的块。canonical `docs/specs/im/tool-timeline.md:187` 的 Requirement 下，`:216–218` 仍写“WHEN 助手回复本轮无思考、工具调用或后台返回 / THEN 不显示空的过程区域”。例如模型无 thinking/工具，第一轮正文被 held，第二轮按原许可静默：新契约要求保留可展开草稿/复核，旧契约按其 WHEN 却要求不显示 Process。**不改的具体后果：** worker 可按旧空态隐藏新过程，或收尾只并入 ADDED 留下相互冲突的 canonical 验收标准。补精确锚定标题的 MODIFIED，忠实保留原 Scenario（必要时仅扩展“无过程项”的 WHEN，把新 typed Process 也纳入判空）；其他原 Scenario 不应静默删除。

### Recommendations

- **[R1-R1] 原型终态文案应只表达运行事实。** prototype.html:17 的“新消息已覆盖本次需要提供的信息”和 :18 的“原文仍适用”是示例性解释；实施时不要根据 NO_REPLY 或字符串相等自动生成这种模型判断理由。可使用“复核结束 · 未发言”等可观测状态，只有真实可展示输出提供理由时才显示理由。design 决策 5 已禁止编造思考，因此此项不另立阻断问题。

### 后续

回 change-design-author 修 R1-C1，并核实 recommendation；修订后唤醒同一 reviewer，由 reviewer 根据实际 delta 选择复审深度。本 Round 写入后冻结，仅允许 author 在其末尾追加 Author Resolutions。

### Author Resolutions

- **R1-C1 — accepted。** 已核对 canonical `docs/specs/im/tool-timeline.md` 的同名 Requirement，确有按 thinking/tool/background 三类判空的旧 WHEN。`specs/im/tool-timeline.md` 增加精确标题的 MODIFIED，完整保留八个既有 Scenario，仅扩展“内部 Web IM 无过程项”的判空范围，并新增正文为空但草稿/复核/交接存在的保留 Scenario；与 design 决策 6、M1 R3/W3 对齐。未修改 current spec。
- **R1-R1 — accepted。** 原型 silent / unchanged 分支改为可观察的“本轮处理结束，未发送正文”与“复核结束，本段已发送正文”；不根据 NO_REPLY 或文本相等编造模型理由。交互结构、示例正文与产品静默许可均未改变。
- 受影响自检：delta 精确锚定和原 Scenario 保留、Process 空态与重放、原型状态措辞及 must-match/M1 投影一致；无新增架构边界或 milestone。


## Round 2

- reviewer: `/root/feat_544_design_reviewer`（复用 Round 1 reviewer）
- review_mode: `closure`
- mode_reason: 修订仅使 canonical 空态规则表达已在 D5/D6 拍定的 process-only 保留语义，并去除原型两处推测性判断文案；新增 Scenario 重述原有验收，没有新架构、接口、需求范围或 milestone。影响可封闭在 R1-C1/R1-R1。
- started_at: `2026-09-09T09:30:52+08:00`
- completed_at: `2026-09-09T09:31:35+08:00`
- duration: `43 秒`
- retained_from: Round 1 — 现状、D1–D6、首文档、其他 delta 与 M1 不变；本轮未改变两个输出出口、controller 同步提交边界或 Process 数据结构，原完整核实台账与架构进攻证据仍有效。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。** 两项历史意见均已闭合；本轮设计评审通过，不代表实施或真实产品验收已完成。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted；IM delta 增加 MODIFIED | 实际按 Requirement 精确标题提取 canonical 与 delta 的 Scenario 比较：原 8 项全部保留，7 项正文完全一致；仅“内部 Web IM 无过程项”的 WHEN 增加未发送草稿、复核、片段交接类型，THEN 保持原文。新增第 9 项“正文为空但草稿或复核记录存在”明确空正文仍保留气泡/过程、顺序、刷新与工具计数，吻合 D5/D6、M1 R3/W3。新 ADDED 与旧规则不再互相否定，外部显示规则及无思考行为保留。 | closed |
| R1-R1 | accepted；原型 silent/unchanged 改用运行事实 | 实读 prototype.html:17–18：silent 为“本轮处理结束，未发送正文”并限定示例原有静默许可；unchanged 为“复核结束，本段已发送正文”。不再推断新消息覆盖全部信息或声称模型判定原文适用。正文、分段链接与草稿 details 交互不变，符合 D5 禁止编造推理的要求。 | closed |

### Issues

无新增问题。

### Recommendations

无新增建议。`git diff --check -- docs/changes/feat-544-group-reply-revalidation` 通过；未启动服务或实施，也未声称浏览器视觉验收。

### 后续

可将这份已审设计交回作者完成 Gate 2 收口。后续启动实施仍遵守本会话授权边界；本轮只追加报告，没有更改受审产物或 commit。


## Round 3

- reviewer: `/root/feat_544_design_reviewer`（复用原 reviewer）
- review_mode: `closure`
- mode_reason: 仅两处页首状态改为指向权威产物，不改变需求、决策、接口或验收；无须重跑架构检查。
- started_at: `2026-09-09T09:32:13+08:00`
- completed_at: `2026-09-09T09:32:30+08:00`
- duration: `17 秒`
- retained_from: Round 1 完整台账及 Round 2 闭环 — 本次状态引用调整不触及旧问题的修复证据或任何行为契约。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

### 历史问题闭环与直接证据

- R1-C1 / R1-R1：保持 Round 2 的 closed；本次修订未涉及 IM delta 或原型。
- 实读 design.md:4：Gate 2 结论链接指向同目录存在的 design-review.md，且保留“本单尚未实施”；与 Round 2 Approved 及当前文档阶段一致。
- 实读 spec.md:3：技术方案链接指向同目录存在的 design.md，且保留“不作为实施或部署授权”；没有将完成设计误写成已经实现。

### Issues

无。

### Recommendations

无。只追加本轮报告，未更改其他产物、启动实施或 commit。
