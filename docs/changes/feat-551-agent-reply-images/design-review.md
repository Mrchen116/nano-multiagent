# Design Review: feat-551

## Round 1

### Metadata

- reviewer: `/root/feat551_design_review`
- review_mode: `full`
- mode_reason: R1，独立完整核对五类承重原子及四个架构进攻角度。
- started_at: `2026-09-10T16:06:44+08:00`
- completed_at: `2026-09-10T08:11:39Z`
- duration: `295s`
- baseline: `main@cdd615696`，只读检查现有 dirty/untracked；本轮只新增本报告。

### Verdict

Issues Found — 1 CRITICAL / 1 WARNING

整体选型成立：Gateway 固定快照，IM 私有会话资源，飞书使用 provider 图片资源，复用既有气泡与 shadow 恢复。阻断点是飞书慢上传与公开发送之间缺少实际可接线的可见性边界；上传回执返回链也需写清。不是要求逐行实现步骤，也不要求重新征求已经给出的文档授权。

### Coverage

完整读取 spec.md、design.md、三份 delta-spec、prototype.html 和 M1 目录；核对 Gateway/IM current spec 入口及对应 routing-delivery、external-channels、relay-protocol、conversations-messages、web-chat-ux 契约。检查代码从 composition/session composition 到 observer、router、Feishu adapter/client，以及 shadow 恢复、IM routes/app/WS/application、前端 Markdown/authFetch。没有执行产品实现、发送消息、启动服务或声称原型已经过浏览器视觉验收。

### 核实台账：现状断言

下列代码路径均相对仓库根目录，文档章节定位相对本 unit。

| 原子 | 核实动作与证据 | 结论 |
|---|---|---|
| 当前落点：product 当前会话直接输出 | product.py:181 的提示限制 send_message；gateway/session_composition.py:89 实际调用 prompt_for 组装 session runtime | 成立，产品提示在真实路径 |
| 当前落点：observer/context 气泡分发 | composition.py:528 注入 build_kernel_event_observer；observer.py:975 处理气泡，context.py:97 保存运行/气泡身份 | 成立 |
| 当前落点：router/saga/sync 投递与恢复 | composition.py:277 构造 router，453 构造带 saga store 的 sync；500 调 recover_pending；shadow_sync.py:447 重放 bubble/output | 成立，rich bubble 与旧 output 都是真实恢复面 |
| 当前落点：飞书网络/data、Post/card 共用准备 | adapter.py:160-177 的两分支；client.py:346、362、422 解析并上传，934 限 HTTP(S)/data | 成立 |
| 当前落点：IM 上传有鉴权、返回静态 URL | messages.py:390-417 接收原始 bytes，395 明示 URL tenant-agnostic，416 返回 /im/uploads | 成立 |
| 当前落点：公开 StaticFiles | app.py:428 挂载 uploads，未经过会话 owner 查询 | 成立，作者明确记录旧路径非私有 |
| 当前落点：完成帧能替换正文 | protocol.py:44、148 解出 final_content；execution.py:318、339 传给完成逻辑 | 成立 |
| 当前落点：前端 Markdown + attachment | message-pane.tsx:1499 独立附件区、1707 ReactMarkdown；attachment-chip.tsx:16 图片直接 img | 成立 |
| 当前落点：authFetch 认证/刷新 | auth-fetch.ts:23-34 取 Bearer、401 刷新并校验同一 user | 成立 |
| 约束：包依赖/内核库 | AGENTS.md 架构红线；Gateway product/session composition 使用 agent.sdk；IM 接收 HTTP/WS 协议 | 决策没有新增跨产品 import |
| 约束：IM 可离线、入口路由 | context.py:434 起仅外部 trigger 设置 reply channel；composition.py:440-459 仅配置 IM 时组装 sync；shadow_sync.py:447 恢复 | 成立 |
| 约束：既有 RunVisibilityLease | 全文搜索 personal_assistant 未发现该类型；实际状态及 await_visibility 在 context.py:119、281-324；observer.py:624、631 使用 store | 名称不是现有接口；影响见 R1-C1 |
| 约束：kernel transcript 不反写 | session_composition.py:89 组装 SDK runtime；observer.py 的渠道投影在 SDK 事件下游；本设计不改 kernel | 成立，保持原文与展示投影边界 |
| 约束：SDK 没有任意图片路径授权 API | agent/sdk/__init__.py、kernel.py 暴露工具 permission 回调/决策；未见独立 Markdown 文件授权入口 | exports 约定比声称自动继承工具授权准确 |
| 约束：owner 数据面 | messages.py:371 调 get_conversation_for_owner；web_im_service.py:142 转给会话仓库 | 成立，无需新增群成员 ACL |
| 复用：气泡 ID、完成帧、shadow 幂等 | shadow_saga.py:112-128 rich bubble 表及唯一键，685 分配 ordinal；shadow_sync.py:333 用 shadow_message_id PUT 并 acknowledge | 成立 |
| 复用：现有 Markdown 扫描上移 | client.py:895 跳过反引号代码/转义；934 读取来源；adapter.py:138 是 provider send | 可集中到 Gateway；不要求 provider import Gateway |
| 复用：公网固定 IP、超时、限额 | client.py:968 检查 is_global；985 固定连接地址、15 秒 deadline；1043 限 bytes；未跟随重定向 | 成立，保持“不放开内网下载” |
| 复用：SQLite/磁盘/会话认证 | IM/infra/db.py:13 schema、后续 ALTER TABLE 迁移；app.py:269 创建上传目录；messages.py:371 owner 查询 | 成立，独立私有目录合适 |
| 复用：纯文本和入站附件不改 | OutboundMessage 可选增量，product 仅增加交付约定；当前 attachment-chip 与 relay 附件通路不需改动 | 与范围一致 |
| 历史 grounding：bugfix-512 网络图能力 | 不仅依赖历史文档，实际 adapter/client 上述发送与读取路径验证 | 成立 |
| 历史 grounding：bugfix-497 恢复宿主 | shadow_sync.py:447-501 同时恢复 snapshot/output；composition.py:535 的旧 prepare 为 None、rich bubble record 为活跃注入 | 成立，实施需保住两出口 |
| 历史 grounding：feat-544 慢操作后复核 | 当前 observer 有 revalidate_output 与 visibility store；router.py:114-123 的后台发送不能凭取消终止 | 目标合理，但现有路径不能自动满足，见 R1-C1 |
| 历史 grounding：current 网络图/公开上传边界 | external-channels.md:59-61 既有可获取图片；messages.py:395 与 app.py:428 证明旧上传公开 | 作者已说明差异，未把旧资源宣称为私有 |

### 核实台账：决策

| 决策 | 完整性、拍板、自洽与驱动核对 | 结论 |
|---|---|---|
| D1 exports + Markdown | spec R1-S1 要“通过可用工具取得”，R5-S2 要“未准备为可交付产物的本地文件”不得自动发；design 拍死目录、普通文件、symlink、同 FD、语法边界 | 成立；不扩成任意路径授权 |
| D2 单 prepare/两 adapter | spec R2-S1 双投影、R4-S2 局部失败驱动统一快照；五来源/10 MiB 与 spec 一致；本地格式与网络已有 GIF 的兼容分开 | 成立；provider 回执出口见 R1-W1 |
| D3 持久快照/output_key | spec R3-S1/R3-S2 驱动持久 manifest；映射从 ordinal 到 kernel ID 不换身份，已有 saga bubble 可承载；未新增通用 native crash outbox | 基本成立；回执写入契约未闭合，见 R1-W1 |
| D4 IM 私有会话资源 | R5-S1 需要 owner GET；不复用公开 /im/uploads；fork 的新会话引用维持 current“完整气泡形态”且删除源后仍读 | 成立，API/错误/幂等拍死 |
| D5 局部失败/可见性/流式遮蔽 | R4-S1/S2 驱动占位与 final_content；所有结束出口已列入；但图示在 Gateway 检查后进入包含慢上传的 provider send | 部分不闭合，R1-C1 |
| D6 认证 fetch/放大 | R1-S2/R4-S1/R5-S1 驱动；同源固定路由避免 token 外送；卸载与换账号销毁 blob；保持现有菜单与原生选择 | 成立，未要求重做 UI |

### 核实台账：spec 约束

| 原子 | 设计对应证据 | 结论 |
|---|---|---|
| S1 自然穿插图片、无需再渠道发送 | D1/D2/D6，当前会话无需新 tool | 覆盖 |
| S2 双端/影子入口/群聊/中间回复/页脚 | D2、接线清单 observer 中间/最终、Feishu Post/card、保持 trigger_source | 覆盖；公开前复核问题另见 C1 |
| S3 跨设备/原图删除/节点重启/IM 离线恢复 | D3 持久快照及 receipt、D4 私有 URL、shadow recovery | 覆盖 |
| S4 局部失败/代码示例/入站回归 | D1 语法排除，D2 限额，D5 占位降级 | 覆盖 |
| S5 私密图片与文件权限 | D1 exports/文件读取约束、D4 owner GET | 覆盖 |
| R1-S1 本地 PNG/JPEG/WebP 跨机器查看 | D1/D2 复制至 exports、IM 保存 bytes、D6 按原比例 | 覆盖 |
| R1-S2 两图顺序与纯图/放大 | D2 template ordinal、D6 不合成正文与放大层 | 覆盖 |
| R2-S1 外部与影子、Post/card/中间 | 接线清单及主流程双投影，D2 provider adapter | 覆盖 |
| R2-S2 影子内部入口不回写 | 现状约束明确保留，context trigger-source 不变 | 覆盖 |
| R3-S1 历史不依赖原文件/节点 | D3 同一快照、D4 IM 独立持久目录 | 覆盖 |
| R3-S2 IM 暂停后恢复不重复气泡 | D3 output_key + 既有 saga 幂等；D4 资源唯一键 | 覆盖 |
| R4-S1 正文先读、原位 loading、不露路径 | D5 跨 delta 缓冲、pending scheme、完成帧替换 | 覆盖 |
| R4-S2 缺失/格式/10 MiB/五来源/上传失败 | D2 每来源准备一次、第六来源失败；D5 分渠道局部降级 | 覆盖 |
| R4-S3 纯文本/公网/代码/用户入站不回归 | D1 代码不处理，D2 保留网络 raster，D6 附件独立 | 覆盖 |
| R5-S1 无登录/跨 owner 不得读 | D4 401/404、D6 authFetch 路由约束 | 覆盖 |
| R5-S2 无权/非产物路径不得发送 | D1 只自动读 exports 普通文件、受控工具先复制 | 覆盖 |
| 澄清：按前轮已认可方向写文档 | Markdown、Gateway 准备、双端、持久化/失败/访问控制均在 D1-D6 | 一致 |
| 澄清：本次只到文档及审查 | 没有实施/部署要求；本轮只写报告 | 一致，不因缺机械逐条确认判失败 |
| 范围：普通 assistant 中间/最终、双 UI | 接线清单列完气泡关闭/terminal fallback、Post/card | 一致 |
| 范围：重复来源不重复上传保存 | D2 去重、D3 回执；实际返回接线需补 | R1-W1 |
| 非目标：新截图/生成工具 | D1 明确使用既有工具 | 未越界 |
| 非目标：视频/音频/通用文件平台 | D1/D2 仅图片 | 未越界 |
| 非目标：跨会话 send_message 新协议 | product 提示仍跨会话用既有 tool，新增协议限定普通气泡 | 未越界 |
| 非目标：旧公网附件迁移 | D4 保持旧 static uploads | 未越界 |
| 非目标：跨 Bot key 迁移 | D2/D3 Bot 隔离 | 未越界 |
| 非目标：模型历史重新注入视觉 | 保持 kernel 原文，投影在 Gateway 下游 | 未越界 |
| 非目标：重做聊天 UI | D6 只加 img renderer/状态/放大 | 未越界 |
| 恢复保证排除损盘/主动删除/未保存成功 | D3 只承诺持久 snapshot，风险段接受保留策略；未许诺 exactly-once | 一致 |

### 核实台账：delta-spec、milestone 与整体

| 原子 | 核实动作与证据 | 结论 |
|---|---|---|
| gateway routing-delivery ADDED 统一交付 | 逐核六 Scenario：本地、权限、路由、离线恢复、局部失败、普通文本；对照 current routing-delivery 的通用路由及 external-channels:50-82 旧飞书图文 | 是跨入口新增资源交付语义，未删除/反转旧 Scenario；全部 THEN 可观察 |
| im conversations-messages ADDED 托管资源 | 三 Scenario 分别对照 D3、D4、fork 接线；current:262 已要求保留气泡，web_im_service.py:448-537 实际复制历史并回滚失败 | 新资源类的并行约束，ADDED 可成立；不缩减原 fork 资格或场景 |
| im web-chat-ux ADDED 内联图片状态 | 四 Scenario 对照 D5/D6；current:378 是 attachment 预览而非 inline 托管资源 | ADDED 可成立，消费者为 Web IM 用户，THEN 无内部调用断言 |
| kernel/cli no spec delta | design 明示两个包不接图片投影，未新增 SDK API | 成立 |
| M1 reply-images | 范围覆盖所有生产接线含 fork、前端与测试；11 个 Scenario 都有 reviewer 退出；接口/API/wiring/build 为 worker 轨 | 单一垂直交付，不存在横切拆分或并行文件冲突 |
| M1 骨架 | M1-reply-images 只有空 .gitkeep | 设计阶段正确，不要求 tasks/progress |
| 上层可读性/图 | 总述“模型写 Markdown；Gateway 固定图片内容；IM 和飞书分别保存”连贯；顺序图和 D1-D6 一致 | 能读懂；顺序图需随 C1 修正上传/发送阶段 |
| 接口与数据流闭合 | IM upload→URL→final_content→authFetch 闭合；Feishu 回执只写为输入，没有返回所有者 | R1-W1 |
| 标题/分支/Changelog/命名 | 标题与 v1 对齐、codex/feat-551 待 orchestrator 创建、Changelog 空符合设计阶段；无 TBD | 成立，RunVisibilityLease 的事实问题已计入 C1 |
| 风险/回退 | 写明 async/offload、路径拒绝、回滚保留私有 GET/renderer、快照暂不 GC、provider ACK 不绝对一次 | 风险具体且不引入额外平台 |
| Runbook | scripts/e2e-up.sh:114、117 支持 --wt/--feishu，probe.py:216 支持 --wt；注明 build、停止、健康与隔离 | 可供实施期验收；没有本轮假装执行 |
| prototype | 源码具 ready/loading/error/only、原比例 SVG、dialog 关闭/焦点返回、移动媒体规则；must-match 和 out-of-scope 分开 | 设计状态齐；浏览器视觉验证留实施期，不把源码检查当真实产品证明 |

### 架构进攻

| 角度 | 主动检查 | 结论与长远代价 |
|---|---|---|
| 归属 | Gateway 控制源文件/快照，IM 控制 owner 资源，Feishu 控制 provider 上传；产品提示在 PA；没有向 kernel 注入渠道协议 | 主分层正确。例外是慢上传后的可见性责任悬空：若直接让 Feishu import Gateway store，会反向耦合；若不接则有晚发风险，见 C1 |
| 该不该存在 | 删除 ReplyImages 会迫使实时 IM、shadow recovery、Feishu 分别读源文件并处理快照/限额；删除私有 IM route 无法让 static uploads 检查会话权限；删除 message-image 则 blob 生命周期挤入主气泡 | 三个新增边界都有实际职责，不是为将来多态造层；未建议额外工厂/通用资产平台 |
| 深还是浅 | 独立搜索发现 client.py:895/934 已有解析/公网读取；D2 明确上移复用；shadow_saga/sync 已有恢复，被复用而非新造状态机 | 整体足够深。仅 receipts 有“字段存在但传回链缺失”，长期易诱发 adapter 私自持久化形成双 owner，见 W1 |
| 治本还是补丁 | 统一固定 bytes 解决原路径/节点依赖；独立受保护 route 正面解决公开静态目录不能 owner 鉴权；exports 明确交付范围，非随意放开文件读取 | 属于正面修复。C1 若仅在 prepare 前后加检查，仍留下 provider 上传期间的同类竞态，不能靠发送协程取消补救 |

### Issues

- [R1-C1][CRITICAL] [决策 5、Interface、生产接线及主流程] **必须拍死飞书慢上传结束与公开发送之间的可见性检查接口。** design:108 要求 prepare 后检查“当前 RunVisibilityLease”，主流程随后把“上传 bytes，发送 Post/card”合成一次 provider 调用；现有生产路径是 composition.py:344 → outbound_router.py:114 的 `shield(to_thread(channel.send))` → adapter.py:160-177 内准备图片并发送。上传尚未结束时取消 coroutine，不会停止已运行线程；且现有 ChannelAdapter.send 仅接 OutboundMessage（base.py:157），没有可见性输入。仓库现有的是 RunDeliveryContextStore 的 active/quiescing/revoked 状态（context.py:281-324），没有名为 RunVisibilityLease 的现成接口可直接套用。**不改的具体后果：worker 按图在 Gateway 快照后查一次状态，再复用同步 send；用户在飞书上传期间 /new，旧回复仍会在上传完成后公开，违背 D5 的明确承诺。** 请明确由谁先做 provider 上传、何时把上传结果交回 Gateway、谁在最终公开调用前复核当前状态，以及终态 context 清理后这份投递有效性如何保持；可以采用最小两阶段 adapter 边界或其他不引入反向依赖的具体方案，不需要逐行代码。已进入 provider 消息请求后的 ACK 不确定窗口仍可沿用既有语义。
- [R1-W1][WARNING] [决策 3、Interface 的 OutboundMessage.images] **飞书新上传回执写回 manifest 的链路未定义。** design:90 要持久化按 App ID 隔离的回执，129 只把“已有回执”作为 Gateway→adapter 的输入。当前 adapter.send 返回 None（base.py:157、adapter.py:138），image_key 只留在 client.py:447-457 的本次局部映射中。文档没有规定新增上传结果如何返回、由哪个 owner 提交 manifest，尤其“部分图片已上传但气泡发送失败”时的保存时点。**不改的具体后果：恢复/重入可能反复上传已完成资源，或 worker 让 provider 层私自碰 Gateway 存储，破坏单一快照所有者。** 与 C1 一起明确返回的逐来源成功/失败及 provider account 标识、持久化 owner/时点即可，不要求新增通用 outbox。

### Recommendations

- [R1-R1] 回 change-design-author 补齐上述两段边界，并同步 sequence diagram 与 wiring 验证项。复审重点是“上传未完时 /new，上传结束后不发送公开消息”以及“部分上传成功、发送失败后重入复用已保存 key”；普通功能、范围和 M1 不需重写。
- [R1-R2] 保留目前的 exports、私有 IM 资源、单 M1 与既有 shadow 恢复方案，不需要扩大到通用附件平台或新的 SDK 权限接口。

### Author Resolutions

- R1-C1 — accepted。核对 outbound_router.py:114 的 shield(to_thread(channel.send))、Feishu adapter.send 的上传与发送复合流程，以及 context.py 的 await_visibility 后确认问题成立。design 决策 5、Interface、生产接线、sequence diagram 和 wiring 验证已改为 prepare_images/receipt 持久化/send_prepared 两阶段；每次公开请求含重试经过 Gateway callback admission，使用真实 RunDeliveryContextStore 名称。终态 context 通过 pending-delivery 引用延迟删除，撤销仍即时可见；未尝试撤回已进入 provider 的请求。
- R1-W1 — accepted。原 send 返回 None 无法承担回执持久化。design 决策 3 与 Interface 新增逐来源 ProviderImagePreparation 返回值和 ReplyImages.record_provider_receipts，由 Gateway 在公开发送前事务保存；部分成功也保存，取消后收取已有上传结果；provider 不访问 Gateway 存储。
- R1-R1 — accepted，与 C1/W1 合并处理；复核场景已加入 wiring 验证。
- R1-R2 — accepted，保留原主方案、范围与单 M1，无新增通用附件平台或 SDK 权限接口。上述修订不改变 spec 用户场景。

## Round 2

### Metadata

- reviewer: `/root/feat551_design_review`
- review_mode: `delta`
- mode_reason: D3/D5 与相应接口、wiring、时序图发生有界语义变化；需求范围、图片资源归属、IM/UI 契约和 M1 未变。本轮把复核沿新增 gate/pending-context 的直接上游扩到现有 /new coordinator 与 task tracker，影响边界可枚举。
- started_at: `2026-09-10T16:13:50+08:00`
- completed_at: `2026-09-10T08:15:52Z`
- duration: `122s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

R1-W1 已关闭。R1-C1 的 provider 接口部分已补齐，但与现有 /new 的等待顺序及运行选择尚未接合：按当前修订实施会形成确定的循环等待，也不能撤销已经结束执行的待投递 run。归为一个 reset/投递生命周期问题 R2-C1，不要求重写主方案。

### Coverage

重新完整读取当前 design 与 Round 1 Author Resolutions，核实所有 changed atoms：真实 visibility store 名称、prepare_images 返回值、record_provider_receipts 写入 owner/时点、send_prepared 返回值、每次 message.create 的 gate、pending-delivery 引用、同步后的图与 wiring 测试。沿调用链另查 composition 的 reset callbacks、session_run_coordinator.new_session/正常终态、task_tracker 的 drain/cancel、runtime_delivery 的 take/discard、Feishu 重试循环。

retained_from: Round 1 — D1/D2/D4/D6、spec 的 S1-S5/11 个 Scenario/澄清与非目标、三份 delta-spec、原型、IM/frontend 现状、单 M1 和 runbook 没有改变；本次修订未使这些证据失效。M1 若为 R2-C1 扩入 coordinator，仍可保持单一垂直交付。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | 两阶段上传/发送；Gateway gate；pending context | design:112-118、142-145 明确拆分，client.py:557 的实际公开调用和重试可接 gate；但 composition.py:630-634 与 coordinator.py:725-755 的原控制顺序与新等待行为冲突 | 未关闭，剩余问题收敛为 R2-C1 |
| R1-W1 | 逐来源返回、Gateway 事务保存、取消也收结果 | design:90-94、142-144 指定 ProviderImagePreparation 的账号及逐来源结果，Gateway 在公开前保存；部分成功和发送失败后重入均有契约 | closed |
| R1-R1 | 同步图与验证 | design:172-178 现在是上传→返回→保存→admission；194 新增上传阻塞撤销、重试撤销、正常终态保留和 key 重用用例 | completed；还需加 R2-C1 的真实 reset 路径 |
| R1-R2 | 保持主架构与 M1 | exports、私有 IM 资源、单 M1 与原文一致 | completed |

### 本轮重查证据

| Changed atom | 核实动作与证据 | 结论 |
|---|---|---|
| 真实 visibility owner | context.py:312-322 的 await_visibility 确实等待 quiescing、拒绝 missing/revoked；design:28 改用 RunDeliveryContextStore | 现状命名已修正 |
| provider 两阶段 + 每次请求 gate | adapter.py:160-177 原来把上传和发送合在一起；client.py:523-607 的 Post/card 共用 create loop，557 是每次调用入口；design:112-116 明确绕开旧复合路径、重试也检查 | 接口本身可落地，没有 provider 反向 import |
| 回执持久化 | client.py:447-457 原来 image_key 是局部映射；design:90、142-144 现在明确返回、账号隔离、事务写入、局部成功与写入失败结果 | 闭合 |
| 取消中的 upload 结果所有权 | task_tracker.py:20-65 统一拥有 detached tasks，68-72 cancel_run 会 cancel；design:92 明确线程仍运行，需收结果后再结束引用 | 生命周期要求明确，worker 要在现有 tracker 里实现，非新增 outbox |
| 正常终态延迟清理 | stream.py:212 原来 take；lifecycle.py:173 原来 discard；design:118/153 改为执行结束标记及最后投递释放 | 可避免 gate 读不到 context；但仅保留 context 不足以让 /new 找到它 |
| /new 上游等待链 | composition.py:630-634 quiesce 后 await drain_run；task_tracker.py:74-78 drain 等全部任务；coordinator.py:728-735 等 quiesce 返回才 publish_reset | 与 quiescing gate 形成 R2-C1 的循环等待 |
| /new 目标选择 | coordinator.py:725-729 只读 _active_runs；1806-1810 正常关闭移除 active；提交 revoke 也只对 active 执行（752-758） | 已结束但 pending 的 context 不会被该入口撤销，R2-C1 |
| dedupe delivered/suppressed | design:116/144 要 suppressed 不提交 delivered；现有 router.py:99-127 拥有唯一 flight/outcome | 归属明确；不需新的去重 owner |
| wiring/图/M1 | design:153-155 与 172-178 同步两阶段；194 有受控阻塞上传测试；252 尚未列 session_run_coordinator | 需随 reset 接线修订范围与测试，而非只手动改 store 状态 |

### 本轮架构进攻

| 角度 | 检查 | 结论 |
|---|---|---|
| 归属 | before_publish 由 Gateway 建，provider 只调用；回执仅由 ReplyImages 落盘 | R1 的反向依赖风险关闭。reset 的运行集合仍应由现有 coordinator/context 共同接线，不能让 provider 管会话重置 |
| 该不该存在 | 两阶段和 pending 引用分别对应慢上传后的检查与终态后仍需撤销，不是为未来扩展预造接口 | 有必要；无需让其他 adapter 实现空壳方法 |
| 深还是浅 | provider preparation 返回足够信息，Gateway 集中持久化；检查 pending 引用能否单独提供 reset 能力 | 回执边界足够深；pending 引用当前仅延长存活，未覆盖实际 reset target 查询，不能单靠该字段满足承诺 |
| 治本还是补丁 | 沿 /new 真实上游查等待顺序，不只验证“手动调用 suppress 后 gate 返回 false” | 发现 R2-C1；只在底层加 gate 而不调整 quiesce/drain 会把晚发变成 reset 卡住，长期代价是会话控制与投递相互锁死 |

### Issues

- [R2-C1][CRITICAL] [决策 5 的 quiescing/pending-delivery、生产接线与 M1 范围] **新增 gate 必须与 /new 的等待规则和待投递运行选择一起设计。** 当前 composition.py:630-634 的 `_quiesce_run_delivery` 先将状态设为 quiescing，再等待 tracker.drain_run；coordinator.py:728-735 必须等该函数返回才 publish_reset，之后才 revoke/失败 restore。修订 design:114 又规定 quiescing gate 等待这个 reset 决定。因而当 /new 在图片上传时到达：reset 等投递 drain → 上传结束后的投递等 await_visibility → visibility 等 reset publish，形成没有释放方的等待环。这是现有调用顺序与新契约直接组合的结果，不是猜测网络异常。另一个同边界缺口是 design:118 仅保留 context，但 coordinator.py:725 只选择 `_active_runs`，正常终态在 1806-1810 已移除 active；于是 run 已结束、图片仍在上传时 /new 根本不 quiesce/revoke 它，后续 gate 仍允许公开。**不改的结果是前一种时序 /new 永久等待、后一种时序仍晚发旧回复。** 请拍死 reset 对“同一旧会话仍有待投递任务”的目标集合，以及 quiesce 只等待哪些已获准请求、哪些尚未 admission 的任务不能纳入 publish 前 drain；明确 publish 失败如何恢复、成功如何撤销，并把 coordinator/task_tracker 的必要接线列入 M1。现有 provider admission 后请求的 ACK 限制可以继续保留。

### Recommendations

- [R2-R1] 沿用两阶段 provider 与 receipt 契约；只修补 /new 的目标选择、quiesce/drain 规则及对应 M1 范围。验证应通过真实 coordinator.new_session 入口，覆盖“上传期间 /new 能完成且不晚发”“执行已结束但上传未完时 /new 能撤销”“reset 发布失败后允许旧投递恢复”，不能仅在测试里直接调用 store.suppress。

### Author Resolutions

- R2-C1 — accepted。核对 composition.py:630 的 quiesce→drain_run、coordinator.py:725 的 active-only 选择和 :1808 的终态移除，确认两种时序均成立。design 决策5新增 old session generation 的 active ∪ retained 目标集合，以及 quiesce→仅 drain admitted-publication→publish→revoke/restore 全集的顺序；uploads/receipts/gate/backoff 不进入 reset 前 drain。before/after_publish 成对登记/释放每次公开 I/O，正常关闭仍 drain 全部任务；store retained 索引、coordinator 目标和 task_tracker 在 Interface、生产接线及 M1 范围中显式覆盖。
- R2-R1 — accepted。验证面改用真实 coordinator.new_session 入口，覆盖上传中 reset、终态但上传未完、reset 发布失败恢复、已 admitted 请求与 backoff 撤销。主架构、spec、delta、prototype、milestone 数量不变。

## Round 3

### Metadata

- reviewer: `/root/feat551_design_review`
- review_mode: `delta`
- mode_reason: 本轮有界修改 reset 目标集合、admission 计数/等待顺序及相应接口、wiring、M1 范围；有语义变化，不能用 closure。仍在上一轮已查清的 coordinator/context/tracker/provider 投递链内，不改变需求或跨产品资源归属。
- started_at: `2026-09-10T16:18:10+08:00`
- completed_at: `2026-09-10T08:19:40Z`
- duration: `90s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

R2-C1 的两种失败时序均在设计契约上闭合：reset 不再等待尚未 admission 的上传或 gate；active 之外的 retained run 也被选入同代际 reset 目标。旧回执链修复仍保留。可以进入 change-orchestrator；本结论是设计可实施，不是实现已验证或已经真实发图。

### Coverage

读取当前 D5、Interface、生产接线、主流程及其 reset 说明、验证面、M1 和 R2 Author Resolutions；对照现有 composition.py:630-655、session_run_coordinator.py:725-758、runtime_delivery/task_tracker.py:68-94、context.py:312-322，验证改动正好覆盖原先等待环与 active-only 目标选择。沿用上一轮已核过的 provider create/retry 入口与正常终态 take/discard 路径。

retained_from: Round 1 + Round 2 — spec、delta-spec、prototype、D1-D4/D6 的资源/权限/格式/恢复方案不变；D3 的回执返回及持久化语义未被本轮修订推翻。单 M1 仍是同一个用户行为的垂直交付，只补入真实生命周期接线文件；其余完整台账及架构结论继续有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1：reset 与 gate 互等 | 只 drain admitted；uploads/receipts/gate/backoff 排除 | design:122-124、153、162 把 composition 原 quiesce→drain_run 替换为有限公开 I/O 集合；before 不等待 transition lock，after 在请求 finally 释放。reset 不等待决定本身，gate 可在 publish 后获 release | closed |
| R2-C1：终态后的 pending run 不被 reset 找到 | active ∪ retained；session_key/generation 登记 | design:118-122、152、161-162 明确 retained 索引直到投递结束才释放；coordinator 不再只取当前 _active_runs，并以 generation 拒绝迟到旧事件 | closed |
| R2-R1：真实入口验证及范围 | 新增 coordinator/task_tracker/stream/lifecycle 与 reset 场景 | design:205、263 明确真实 new_session 的上传中 reset、终态 pending reset、publish 失败恢复、admitted 请求等待与 backoff 撤销 | completed |
| R1-C1 | provider 上传后公开检查并保持生命周期 | R2 剩余 reset 集成已关闭；design:114、150-151 成对 before/after 与 provider 重试规则一致 | closed |
| R1-W1 | Gateway 持久化 provider preparation | design:142-149 的账号/逐来源返回、写回 owner 和公开前保存仍在 | closed，继承 Round 2 证据 |

### 本轮重查证据

| Changed atom | 核实与推演 | 结论 |
|---|---|---|
| reset 目标集合 | 当前 coordinator.py:725 原来仅 active；新 design:120/152 要枚举同 session generation 的 retained，与 active 取并集；正常终态的 active 移除不删除 retained 引用 | 消除 R2 漏撤销时序 |
| reset 成功/失败顺序 | 当前 publish 位于 quiesce 返回之后；design:122 现为 quiesce 全集→drain_admitted→publish→成功推进 generation/revoke 全集，失败 restore 全集 | 等待 gate 由成功/失败两个分支释放；没有遗漏失败恢复 |
| before/after 公开 I/O 登记 | design:114 在同一 loop turn 最终检查 state/generation 并登记，异步资格检查后重查；150-151 请求 finally 释放；不持有/等待 coordinator transition lock | 允许 reset 在持有 transition 时等待已有 I/O 结束，不构成 lock→gate→lock 环 |
| prepare/gate/backoff 与 admitted 区分 | task_tracker.py:74 原 drain 等所有 tasks；新 design:122-124 明确排除准备及等待任务，provider 每次 create 请求独立 finally 释放 | 上传不会阻塞 reset；重试 backoff 不持有 admission |
| 取消后结果保存与 shutdown | task_tracker.py:68 原 cancel_run 无差别取消；design:122/162 保留上传回执 finalizer，普通 close_and_drain 仍 drain 全部 | 没有通过丢失已运行线程所有权换取 reset 完成 |
| 其他可见写入 | design:124/162 明确既有文本、IM 公开 I/O 也登记，quiescing deferred coroutine 不登记；其他 adapter 无需空壳图片接口 | 原 reset 等“已获准输出”的语义得以保留，边界说明足够 |
| 图与实现范围 | design:199 补充 reset 交错说明；263 补齐 coordinator 和 runtime_delivery 的 context/observer/task_tracker/stream/lifecycle | 下游不会只改 provider/gate 而遗漏上游 reset |
| 验证退出 | design:205/263 从真实 new_session 驱动，检查 reset 能完成、旧图不发、失败恢复及已获准 I/O 顺序 | 用例能暴露 R2 的真实 wiring 缺陷；不要求本轮执行 |

### 本轮架构进攻

| 角度 | 核查结论 |
|---|---|
| 归属 | session generation 与 reset 决定仍归 Gateway coordinator/context；tracker 只拥有任务与 admitted 请求计数；provider 只调用不透明回调。不新增跨产品 import 或 provider 存储 owner |
| 该不该存在 | retained 集合解决已经结束执行但尚未交付的实际生命周期；admission 计数区别“公开请求已开始”和“任务仍在准备”，是消除确定等待环所必需。删除任一会重现 R2 问题，非假想扩展 |
| 深还是浅 | 新增方法提供明确可消费的 run 集合与等待完成条件；provider 无需理解 session/reset，coordinator 无需理解图片 bytes/key，接口隐藏了各自真实复杂度 |
| 治本还是补丁 | 修订同时调整真实 reset 目标、等待顺序、清理引用与取消 finalizer，没有靠 sleep、超时吞错或 context 副本掩盖问题。后续需要实施验证，但文档不再留下已知结构性缺口 |

### Issues

无。

### Recommendations

- [R3-R1] 按当前设计进入实施，并保留 design:205 所列真实 new_session 交错测试作为关键验证；不要以直接修改 store 状态的单测替代生产接线证明。
- [R3-R2] 作者已通报 Interface 表的枚举 `delivered | suppressed` 含未转义竖线，将在审查后改成 `delivered / suppressed`。这是保持原枚举含义的 Markdown 排版修正，不阻断本轮 Approved，也不需要为该纯格式修正另开语义复审。

### Author Resolutions

- R3-R1 — accepted。逐条复核本轮 closure 与真实 coordinator/context/tracker 路径，确认已覆盖既有 active-only 和 drain-all 两处缺口；保留真实 new_session 交错验证作为实施退出标准。
- R3-R2 — accepted。只将 Interface 表中该枚举的未转义竖线改为斜线，不改变返回值语义。spec、delta、prototype 与 M1 骨架未改。
- 作者检查：本次只有文档，无产品测试或真实发图声明。`git diff --check` 和原型脚本语法检查通过；全仓 docs-check 仅报既有研究索引中两个未跟踪目录链接。浏览器拒绝打开 file URL，未绕过，原型未做浏览器视觉验收。

## Round 4

### Metadata

- reviewer: `/root/feat551_design_review`
- review_mode: `closure`
- mode_reason: 仅核对 Round 3 已说明的 Interface 枚举 Markdown 格式修正，无架构、契约或范围变化。
- started_at: `2026-09-10T16:20:35+08:00`
- completed_at: `2026-09-10T08:20:52Z`
- duration: `17s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

当前受审版本与 Round 3 的接口语义一致；Approved 继续有效。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-R2 | 表格枚举中的竖线改为斜线 | design.md:150 为 `delivered / suppressed`；与 :116 的“返回 delivered 或 suppressed，只有 delivered 才完成已投递 outcome”一致。只修复 Markdown 分列，不改返回值或处理规则 | closed |

### Issues

无。

### Recommendations

无新增建议。按 Round 3 已批准方案及其验证退出标准进入实施即可。
