# feat-583 Design Review

## Round 1

### Metadata

- reviewer target: `/root/trajectory_design_gate2`，独立 `change-design-reviewer`；未参与受审方案编写。
- review_mode: `full`
- mode_reason: 首轮无历史报告；按 Gate 2 覆盖需求、现状、核心接口、权限、原型、delta 和唯一 M1。
- started_at: `2026-10-12T11:47:40+08:00`（首个已记录的墙钟点；前期只读阅读未单独计时）。
- completed_at: `2026-10-12T11:51:37+08:00`
- duration: 可核计时段 3 分 57 秒；总耗时因前期未记录起点而不作精确声明。
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-581`；branch `unit/refactor-581`；HEAD `58738724034bc580591c3b37f028a6d905660b0e`。
- upstream: 官方 DSH clean checkout `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；同时核对本仓安装的 `0.2.1-alpha.1` 发布包，不以 upstream 源文件存在代替 published export 可用。
- 审查写入范围仅本报告；未改设计、代码、分支、服务或配置，未运行真实 LLM。

受审文件 SHA256 与派发冻结值一致：

| 文件 | SHA256 |
|---|---|
| `spec.md` | `f5dd7b8488248db6bdbfa865408497314222f1e214228e430144ece47613aed4` |
| `design.md` | `c3f1638277eb7d35315614dad5ef04d67d2dc03ff313111385e2c7edca093da5` |
| `prototype.html` | `0132069e39e33b179b2d8307c3d12d574bd7c428100f181ff24058eabe8b88e3` |
| `specs/im/agent-work.md` | `d5d0c850251226f96528697265f435ad4d4bc5b86bce8d4d99cd0919b4fffadf` |
| `specs/gateway/relay-protocol.md` | `c8e0256c0c01764424af0570f06f3d619538b4579e6d6398fe8bc50000d255e0` |

### Verdict

**Issues Found — 1 CRITICAL / 1 WARNING。Gate 2 未通过。**

Work 内按需进入、共享只读权限和独立官方 renderer 的总体分工成立；但直接复用官方 cold `follow` 会恢复 Agent，与只读承诺冲突，观察传输的失败隔离也未在现有共用队列上闭合。两项必须先修订设计，不能仅留作实施时探索。

### Coverage 与证据

**需求与现状。** 阅读 `spec.md` 的原话、澄清、U1–U5、R1–R5 与非目标；需求限定为本轮设计、Web、只读、切换后现场读取。核对 current `docs/specs/im/agent-work.md`、`docs/specs/gateway/relay-protocol.md` 与 `SPEC.md`。实际装配入口为 `apps/im-server/src/server.ts` 的路由/socket 注册、`apps/im-server/src/gateway.ts` 的认证节点连接、`apps/node/src/main.ts` 的 `WebRelayConnection` / `RuntimeSupervisor`、integration `NanoRuntime` 构造与 `initialize`/`session.ensure`/`submit`。方案指向的是现有生产装配，而非仅测试存在的旁路。

**职责、依赖与复用。** 原始轨迹由 integration 使用官方公开能力读取；IM 拥有真人资格和聊天媒体授权；Node 拥有本机产品绑定、连接和子进程生命周期；独立 browser viewer 拥有官方客户端装配及渲染。这个划分保留了 PA 产品路由，不需要 PA 理解原生 wire events，也没有第二套 Agent Loop。React 18/19 与样式通过 iframe 隔离合理；D2 已明确提出仅 browser/client 的窄依赖例外，并把 `SPEC.md` 与 runtime dependency contract 的更新放入 M1。静态 viewer 包比在业务前端散布 DSH imports 更易维持边界。

**原生接入可行性。** 独立检查 upstream `packages/api/session-controller/src/{index,history,types,control}.ts` 及 client Session/transport，`packages/client/{modules,connection,ui-trajectory,ui-conversation,ui-session}` 的公共装配。安装包的 trajectory `/client` 实际为 `window.__ModuleLoader__.load({id,factory})`，公开声明只有 plugin `apply/inject` 等，确非独立 React 组件；`ClientModuleSystem` 与 `ClientTransportHooks.rpc` / `ClientConnectionRpc.call/open` 在实际发布声明中存在。trajectory 注册 `conversation.view/trajectory`，复用 Session history 与 uiConversation image service 的方向正确。Connection 的 Remote readiness 需要载体处理官方 `$events` opening；设计已有“只读 carrier 提供 readiness、不转发任意 Host Remote events”的边界，可以在 viewer 装配时兑现，不应把原 Host 的操作员事件流透传进来。完整 renderer 未实现，故本轮只确认公共装配路径与接口证据，不宣称嵌入或真实分页已成功。cold `follow` 的副作用另见 R1-C1。

**归属与权限。** `Work.session(root,id)` 查询 `agent_work_sessions` 的 root/session，登记约束 node、scope、parent；Work routes 的 profile 默认不要求 owner，而权限决定才要求 owner，支持设计的 active 非 owner 查看。NodeStore 的 global binding 来自 `global:<agentId>`，initialize 传可信 bindings，原生 inspect/header 和 subagent projection 可复核真实父关系。D4 不接受浏览器传来的 parent/address，且锁定 node Connection/epoch，责任正确。账号撤销已有 `closeUser`/`closeSession`、`browserValid` 和定期检查入口，新观察集合必须纳入这些入口，设计与 E2/E4 已要求。

**附件来源。** current media read 经 `messaging.principal/access` 检查 conversation membership；官方 `session/attachment` 仅证明图片在会话日志中被引用，并返回 base64 字节，不证明当前真人可读原聊天。D5 新增来源元数据而非复制字节有实际必要。检查 integration `submit` 的 `admitPromptContent`、`global-mode.ts` 的 `inbox.image`/`inbox.prepare` 与 PA `InboxStore.imageReferences/prepareRead`，这些点能取得可信原消息/聊天信息及 admitted attachment 对应关系。来源证明与 IM 授权先于字节读取，无法证明的历史图片拒绝预览，符合既有边界；模型声明或路径不能成为来源证明。该来源映射尚未实现，不作运行验收结论。

**生命周期与载体。** scope 固定、generation 清空旧内容、AbortController 仅关闭读取、离开销毁 iframe/socket、迟到帧按 observer/request/node Connection 丢弃、版本失配拒绝解码均有明确归属。无需新增永久 watcher。现有 stdio/relay 不能直接提供设计声称的观察级背压与失败隔离，见 R1-W1。

**原型与 UX。** 独立查看当前 Work 实际截图 `output/feat-583-design/current-work.jpg`（1280×720），对照 `AgentWorkPanel` 的 status、usage、主轮次、关联执行与响应式选择行为；保留页内 Work 导航、卡片层级、主轮次顺序，新增分段切换属于局部增量。独立 CUA 打开专用原型 tab，实际看画面并走通工作记录→主原生→子执行→输入/输出→返回，检查 768 中间宽度、390×844 手机检查器/离线/中断/空态/资格失效和首次加载。原型正文明确标记固定数据与官方组件占位，未把原型内手写 ledger 当作最终 renderer；未发现拥挤、遮挡或额外导航会使实施走偏的问题。作者的 1280×900 与390×844代表图在同一忽略目录；审查仅操作自己的临时 tab，完成后已关闭并恢复 viewport。`must-match` 三项均映射 V1–V3 与 E1–E3；官方颜色/具体排版允许适配，演示控制明确 out-of-scope。

**Delta 与 M1。** 两份 delta 分别锚定正确 canonical target，均为 ADDED Requirements，没有以 MODIFIED 误删现有 Scenario；IM delta 使用真人查看视角，Gateway delta 使用 IM/节点接口消费者视角，保留聊天附件权限和只读约束。单个 `M1-work-native-trajectory` 空骨架符合尚未实施状态；M1 是完整纵向切片，覆盖 viewer、frontend、IM/Node/integration、架构与契约，不存在机械按层并行冲突。V1–V3 与 E1–E5覆盖主要需求；实现前须修订 R1-C1/R1-W1 涉及的 APIs、数据流和 E2/E4/E5证据，不能将不成立的机制直接交给 worker。

**验收前置与边界。** 核对 `config/e2e/gateway.yaml`、`scripts/e2e-up.sh`/`e2e-down.sh` 与 IM e2e helpers：隔离身份、绑定、端口、workspace、config 和独立 runtime 有现成入口；integration tests 已有真实 DSH 进程配 fixture `llm/stream` 的手段。未来 reviewer 需要真实 Web/DSH，不以 mock 代替原生 renderer，桌面/手机 viewport 足够；本期不需要物理 iPhone、飞书或私人附件。Runbook 仅操作本 unit 栈，现有 final-review 不成为未来验收环境。本轮未启动上述服务、未调用 LLM、未提前做实现验收。

### 历史问题闭环

无历史 Round 或 Author Resolution；本轮为首次 full review。

### Issues

#### R1-C1 — 官方 cold follow 会激活普通主 Agent，直接读取方案违背只读契约

- 位置：`design.md:33`、D3 `design.md:88`/`:93`、读取流程 `design.md:148`、E2 `design.md:261`。
- 证据：锁定 upstream `packages/api/session-controller/src/history.ts:204`–`:211` 在 opening snapshot 后对 `address.kind === 'session' && source.source === 'prepared'` 调用 `this.promote`；`src/index.ts:208`–`:218` 随后执行 `agents.resolveObservedAgent`，`src/agent.ts` 的该路径调用 `ctx.agents.resume`。实际发布包 `packages/dsh-integration/node_modules/@deepseek-ai/dsh-api-session-controller/lib/index.js:1523`–`:1531`、`:2922`–`:2933` 保留相同行为。公开 `SessionFollowRequest` 无只读/禁止 promotion 参数，`nativeOpen:false` 仅控制本机文件打开，不控制 Agent 激活。
- 未修后果：按设计对 live/cold 主会话统一调用官方 follow，即使本仓没有显式调用 `agent()`、`session.ensure` 或 `resolveAgent()`，纯查看仍会恢复 cold Agent。active 非 owner 的查看也能触发该恢复；违反 R4.2/R5 及 Gateway delta 的“不因读取激活 Agent”。E2/E4“不激活、不启动模型”的要求将与实现基础机制冲突。
- 必要修订：明确 ordinary cold 与已有 live 的读取分流，选择已发布 public API 可兑现的非激活 cold opening/后续观察方式，写清与官方 SessionEventStream 的 snapshot、分页 cut、Assistant baseline 和后续 live 切换的衔接。若 cold 不调用原生 follow，必须使协议和验收反映这项差异；不能通过 private import、patch/fork 或 hand-written renderer 掩盖。补上真实 cold 主会话查看前后未创建/恢复 Agent 的可核证据。不是要求现在实施，而是先收口当前设计所依赖的错误事实。

#### R1-W1 — 共用 relay/stdio 队列没有方案声称的观察级背压与失败隔离

- 位置：D6 `design.md:115`；接口 `design.md:140`–`:149`；E5 `design.md:264`。
- 证据：当前 `packages/dsh-integration/src/rpc.ts:54`–`:70` 的 notification 返回 void，`output.write` 的背压结果未被等待；Node 本地限制一个转发批次并不能限制 integration 持续产生的通知。`packages/channels/src/index.ts:165`–`:195` 的所有业务 frame 共用唯一 `active` ACK 队列，等待超时会 `disconnect` 整条节点连接；它并非每个 observer 独立的发送确认。IM `apps/im-server/src/gateway.ts:918`–`:930` 的过大/积压处理也直接关闭设备 socket。设计新增 frame 列表未定义从 consumer 到 integration 的 credit/ACK/拉取关系或观察自身的超时取消路径。
- 未修后果：直接“复用现有背压”，要么 integration→Node 仍无界排队，要么把慢 observer 的等待放进共用 business ACK 队列，拖住业务帧并最终关闭节点 WS。这与 Gateway delta“慢查看者只使该观察失败、不阻塞正常消息”和 E5 保证冲突，且可能放大本期明确不修的节点恢复问题。
- 必要修订：选定最小的观察级有界传输方式，说明 integration 何时允许继续迭代、哪个接收点确认消费、积压/超时由谁 abort observer；IM 对观察过大或慢客户端应在进入共用设备队列/上限前让该 observer 有界失败。明确正常业务 ACK 队列不等待浏览器消费，增加慢查看者时正常业务帧仍交付、节点连接仍存活的定向证据。不要求通用大对象分片协议或新的基础设施。

### Recommendations

无额外阻断以外的改造建议。修订后按真实波及范围复审；核心 cold 读取路径发生变化，不能仅作文字 closure。

### Author Resolutions

- **R1-C1 — accepted。** 已从锁定源码及发布声明确认 `follow` opening 后的普通 prepared promotion；`nativeOpen:false` 不能禁止它。修订 `design.md` 的能力表、D3、接口／时序及 E2：冷会话用公开 `sessionQuery.observeSession` 的不可变 cut 和官方 `page` 形成公开 snapshot DTO，不访问内部 encoder；确认冷会话的 Assistant baseline 为 revision 0。已挂载读取保留官方 follow，并在消费第一帧后验证同一个 Session 仍挂载；失配关闭 iterator，不进入 prepared promotion。正常业务将冷会话挂载后用新的物理 generation 重开，避免官方 `RemoteJournalStream` 同流多 opening 错误。新增真实 cold registry、分页、disposal、冷转已挂载和资源释放证据要求。spec／delta 的非激活承诺未改变；尚未实施或宣称验证成功。
- **R1-W1 — accepted。** 已核实 `RpcPeer.notify` 不等待 writer、设备业务 ACK 串行且超时关闭整条连接，不能称为观察背压。修订 `design.md` 的架构图、D6、接口与 E5：设备 WS 仅协商有期限、固定 scope 的观察配对，Node 对既有 IM 地址建立独立出站观察 WS；观察数据不进入业务 ACK/processing 队列。stdio 改为 `trajectory.next` 有界批次 response，集成本地最多两个 1 MiB 批次、积压 5 秒或溢出只 abort observer，空闲长拉取单独处理。临时 socket 单独检查发送预算，大小越界在发送前失败。增加停消费时同时证明正常业务交付、心跳和设备连接存活的 E5 场景；未新增通用大对象分片或改写业务 transport。

## Round 2

### Metadata

- reviewer target: `/root/trajectory_design_gate2`，独立 `change-design-reviewer`；本轮仍未参与方案编写。
- review_mode: `full`
- mode_reason: 虽然需求和 UI 未变，D3 的核心冷读取路径与 D6 的共享传输接口发生实质变化；不能仅凭 accepted resolutions 作 closure。本轮复核新读取、观察配对和流控机制，并检查对权限、生命周期、delta 与 M1 的波及。
- started_at: `2026-10-12T11:58:21+08:00`
- completed_at: `2026-10-12T12:02:05+08:00`
- duration: 3 分 44 秒。
- checkout / branch / HEAD: 与 Round 1 相同；上游仍为 `5badb15009ae1756c3afe0ae0cef1faafc290ccc`，实际安装发布包仍为 `0.2.1-alpha.1`。
- 受审 `design.md` SHA256: `320d513ef60f645d0d2a37a3c7760f178de539273a8cfba41c18867bfca0f754`。本轮重新计算 spec、prototype 和两份 delta 的 SHA256，均与 Round 1 冻结值相同；单 M1 仍为空骨架。
- 仅追加本报告；未修改其他产物或代码，未启动／重启服务，未调用真实 LLM。R1 专用原型 tab 已关闭、viewport 已恢复，本轮未再操作浏览器。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

两项历史问题在设计层闭合。修订依赖的非激活读取及客户端 generation 能力具有真实公开接口依据；观察传输现在明确隔离业务 ACK，并有端到端消费约束与失败边界。此结论是设计可实施性审查，不代表原生嵌入、冷转实时或慢查看者场景已经实现或跑通。

### Coverage 与证据

**需求、现状与产品范围。** `retained_from: Round 1`：未变化的 spec、current Work 权限、原型及两份 delta 沿用 R1 的独立来源和视觉证据。重新检查 design 全文，仍限于 Web Work 内切换、只读、现场 Gateway 读取；没有新增 IM 原始轨迹持久化、节点业务端口或原生管理权。实际装配仍是 IM `createServer`／Gateway、Node `WebRelayConnection`／`RuntimeSupervisor` 与 integration `NanoRuntime`，未改成只存在于测试的组装入口。

**冷读取公开可行性。** 核对实际发布包 `@deepseek-ai/dsh-session-query/package.json` 的根 exports、`lib/types/index.d.ts` 的 `observeSession` 与 `lib/types/observation.d.ts`：调用返回 caller-owned lease，公开 `source/header/cursor/projections/retain/[Symbol.dispose]`，支持取消及 projectionMode。发布实现 `lib/index.js:348`–`:396` 先检查 live registry，冷路径使用 `sessions.prepare`，不发布 Session 或恢复 Agent；`:448`–`:511` 保留同一 cut 和 exact projections。upstream `packages/session-query/session-query/src/observation.ts:98`–`:161`、`:243`–`:325` 与此一致。因此不读取 `observation.events`，仅取公开 metadata，再让官方 page 产生 records，是可用的 public seam，不需要 private encoder。

官方 `SessionHistoryController.page`（upstream `packages/api/session-controller/src/history.ts:77`–`:111`）按 `throughSeq` 和请求窗口调用原生 paginate/pageRecords，且 `sourceFor` 不促进 Agent。公开 `SessionFollowFrame`／`SessionPageRequest`（`src/types.ts:471`–`:491`、`:552`–`:563`）足以表达新 opening。原生 `wireHeader` 实际只有 `{ ...header }`（`history.ts:430`–`:432`）；projectionBlock 为原 snapshot 的 `asOfSeq/values`，无额外秘密转换。D3 要求 header 原值、projection 与 cut 一致，并仅在确认未挂载时使用 Assistant revision 0，能够保持客户端 opening 契约。观察期间若正常业务挂载，应走新 generation；不能把可能已变成 live 的 observation 当冷 baseline 直接继续。

**已挂载与 generation 生命周期。** 官方 follow 的 promotion 位于第一帧 `yield` 之后，故 D3 的第一帧后 registry 同一对象复核、失配 `iterator.return()`，可在继续迭代前避开 prepared promotion。公共 `session/created`、`session/disposed` 与 `agent/created`／`agent/disposed` 在实际发布声明存在；官方 Session Controller 本身也用这些 availability 事件（upstream `src/index.ts:174`–`:186`）。监听先装再复核符合冷转挂载所需的顺序。官方客户端 `SessionEventStream` 将一次 snapshot 转成 `opened`，并校验 opt-in Assistant baseline 与后续 revision（`src/client/transport.ts:172`–`:218`）；公开 `ConnectionHandle.reconnect`／generation source 提供新物理载体生命周期。新设计明确不同物理 generation 重开，未向同一流塞第二个 snapshot，也未自行实现 cursor 或 compact 算法。E2 已覆盖真实 cold 主会话 registry、无模型／工具调用、挂载转换、disposal 与资源归零，运行证明仍留在实施阶段。

**观察传输、责任和复杂度。** D6、接口与时序现将设备 WS 限于 prepare/close；独立 Node 出站 WS 以 60 秒一次性票据绑定 observer 和现有 Connection/owner/epoch，不注册或替换设备。IM 负责配对、真人授权及失效关闭，Node 负责本机 binding、设备／runtime 生命周期，integration 负责原生 iterator 和有界队列，viewer 负责原生消费后的 next。归属闭合，PA 与 IM 仍不理解 native event。

当前 `RpcPeer` 的 line handler 不串行等待其他 handler（`packages/dsh-integration/src/rpc.ts:23`–`:25`、`:73`–`:106`），可承载有限 next response，20 秒空闲长拉取不会占住一个全局业务处理锁。设计不再用不等待 writer 的连续 notifications；每 stream 一次在途 next、至多两批且每批 ≤1 MiB，满后新帧／单帧超限／待取 5 秒时 abort observer，保证慢消费不会把无限原生输出移到 stdio。临时 socket 在发送前检查响应大小及独立 bufferedAmount；不会触发旧设备处理路径的积压关闭。原设备授权或代际丢失、浏览器关闭、runtime 退出时撤销所有附属读取，不能让一次性票据建立永久独立设备身份。这里新增的临时连接与有限拉取有 R1 所证的运行必要性；不需要为此增加通用分片、持久操作队列或第二套流协议解码。E5 已加入停止真实浏览器消费时业务、心跳和设备连接同时存活的证据，以及超大帧、票据和设备换代场景。

**权限、附件与依赖。** `retained_from: Round 1`，相关决定未变：Work 查询与 Node binding／原生父链双重复核；active 非 owner 可读，管理与审批仍属 owner；附件来源从可信 input／Inbox 准入形成，聊天授权先于字节读取，无来源图片拒绝。新票据与观察 socket 不扩大这些权限，认证失效清理覆盖附属连接。browser viewer 仍是 DSH client-only 窄例外，Host/runtime 依赖仍由 integration 独占，product-contracts 只持产品身份和 JSON 载体；不新增上游补丁、private import 或复制源码。

**原型、delta、单 M1 与前置。** `retained_from: Round 1`：未变化的真实 Work 截图、桌面／手机原型画面和交互路径足够支撑原有 UX 判断，本轮 backend 载体变化不引入新可见操作。must-match 仍对应 V1–V3／E1–E3；两份 ADDED delta 的 canonical target、消费者视角及现有 Scenario 保持正确。M1 仍是一个完整纵向切片，E2/E5 变化补足新机制的验证，没有新增按层并行或可独立假交付的阶段。原生 public bundle 实际装配、locale/theme、分页、packed/compact 内容及 teardown 仍须先在 M1 的真实锁定发布包中成立；Runbook 的隔离 runtime、身份／附件准备与 fixture 和真实 LLM 证据区分继续有效。未把静态 prototype 或源码核对当作实现验收。

### 历史问题闭环

| Issue | Author Resolution | 本轮闭环证据 | 状态 |
|---|---|---|---|
| R1-C1 | accepted；cold 改用 observeSession + page，live follow 第一帧后复核，同流不重复 opening | 公布根 exports 与 lease DTO、page 非激活路径、yield 后 promotion 顺序、公开 availability 与客户端 generation；D3／接口／E2 已一致 | **closed** |
| R1-W1 | accepted；观察独立出站 WS，有限 next response 与有界队列，业务 ACK 不等观察消费 | D6 与接口完整定义配对、信用、积压 abort 和失效回收；RpcPeer 并发 handler 能承载该有限请求；E5 要求业务／心跳／设备仍存活 | **closed** |

### Issues

无新增 CRITICAL 或 WARNING；没有仍待关闭的历史问题。

### Recommendations

**R2-R1（非阻断）— 将 viewer 的 iframe header 配置纳入第一条真实装配验证。** 当前 IM `apps/im-server/src/server.ts:104`–`:124` 为响应设置 `X-Frame-Options: DENY`，HTML CSP 为 `frame-ancestors 'none'`；新同源 viewer HTML 不能直接沿用这两个禁止嵌入的值。D2 的 iframe 入口实施时应在专用静态 viewer 路由配置所需的窄范围嵌入策略，并保留主应用页面的既有策略。这是兑现已明确 iframe 装配的具体接线提醒，E3 的真实嵌入验证能直接发现，未改变本轮设计结论，也不要求增加新通用安全框架。

### Author Resolutions

- **R2-R1 — accepted（实施接线提醒）。** 已核实现有通用响应头确实禁止嵌入。将专用 viewer 路由的实际响应头与真实 iframe 加载作为 D2／E3 首条装配验证的检查点，只允许既定父页面嵌入 viewer，保留主应用页面策略。此处明确已有 iframe 方案的接线位置，不新增查看权限或变更既定架构；不为该提醒再开审查循环。
- Author 已核实 R2 的公开接口与历史闭环证据，无实质异议。受审 spec／design／prototype／delta／骨架在 R2 后未改变；仅本报告追加 resolutions，保留 Approved 结论。
- 交付位置：本功能依赖尚未合入 main 的 refactor-581，现有源码链接和契约以迁移 checkout 为基线。此次仅在该迁移分支提交本 unit 的设计产物；不将这些未实施文档与尚未合入的产品源码拆散推到 main，不改用户 primary checkout 的既有工作。

## Round 3

### Metadata

- reviewer target: `/root/trajectory_design_gate2`，独立 `change-design-reviewer`；未参与本轮需求／设计修订及 probe 编写。
- review_mode: `full`
- mode_reason: 用户新增原生信息与交互保真要求，R3.4/R3.5、前端 must-match 和最终测试服务交付条件均发生实质变化；按 skill 使用 full。未变化的只读 transport、权限和 observer 方案引用 R2 的已核证据，不机械重复运行验证。
- started_at: `2026-10-12T12:58:25+08:00`
- completed_at: `2026-10-12T13:01:48+08:00`
- duration: 3 分 23 秒。
- checkout: `/Users/czj/.codex/worktrees/native-dsh-trajectory/nano-multiagent`；branch `codex/feat-583-native-dsh-trajectory`；HEAD `1128a2b6e30911e4658ed0d935dfff6b1424c740`。
- 上游基线：DSH `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；probe 实际发布物 `0.2.1-alpha.1`，React/React DOM `18.3.1`。
- 本轮仅追加本报告，未改冻结产物、产品代码、配置或运行服务，未提交，未调用真实 LLM。

受审 SHA256：

| 文件 | SHA256 |
|---|---|
| `spec.md` | `8c5d947d53c56d60e60b66ff523eb7abddf04006dfa40af75620bf7946e7c857` |
| `design.md` | `cc56c3f0b56f32b01e77d14526a87f0abb4585088ebc807b4098ccdb2086f6b6` |
| `prototype.html` | `924adc59fd474a607e7922c64367c567708234e93d43034e78ed27df1f2280cd` |
| `specs/im/agent-work.md` | `8da6413cefe50f19d979f9a02c0e187562349f99c8168d345c0efa133dba6706` |
| `specs/gateway/relay-protocol.md` | `c8e0256c0c01764424af0570f06f3d619538b4579e6d6398fe8bc50000d255e0` |

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

新设计已把“使用官方组件、保留其完整信息和交互”变成可逐项验收的要求。旧手写轨迹主体及其宽松 may-adapt 判断不再作为保真依据；本轮确认的公开组件装配可行性也不等于真实 Gateway 产品链已验收。

### Coverage 与证据

**需求与现状。** 阅读用户补充原话、完整 spec、四份 dirty 文档 diff、单 M1 和前两轮报告。R3.4/R3.5 明确时长、轮次、调用、搜索、三轨选择联动、完整模型可见输入、仅工具调用助手、历史 Schema／提示词与类型化检查器；未知历史不得用当前配置补造，桌面／窄屏均须可完整检查。新增要求符合用户对初版缺失信息的纠正，没有将查看扩展成执行控制。新 HEAD 相比 R2 基线 `587387240` 的产品目录／SPEC／架构测试没有变化，提交仅承接既有设计；实际 IM、Node 和 integration 装配入口仍有效。

**原生保真与数据职责。** 独立检查 upstream `packages/client/ui-trajectory/src/client/index.ts`：官方插件确实注册 message、request-header、assistant、tool、compaction definitions，通过 `uiConversation.binding(...).target('trajectory')` 取得 snapshot，注册 `conversation.view/trajectory` 和 `conversation.trajectory.images`；loadOlder、imageUrl 与原生 Session binding 由官方服务衔接。D2.1 直接使用这条数据与呈现链，避免从丢失系统／上下文和完整 request header 的 Work projection 重建，责任合理；Nano 只拥有宿主与只读载体，不拥有第二份 trajectory renderer。

源码 `TrajectoryToolbar.tsx` 的实际控件为时长切换、轮次折叠、调用折叠和搜索；`TrajectoryView.tsx` 管理对应状态、搜索、历史和选中，`timeline.ts`／`TrajectoryTimeline.tsx` 拥有输入／模型／工具 lanes、区间与缩放。隐藏的 actual-time 开关不被误写成用户必须看到的第五项控件。`TrajectoryTable.tsx:972`–`:1006` 按真实记录类型选择原文／来源、系统提示词、工具参数／结果／Schema／计时；请求检查器另有选项、用量和计时。snapshot builder 保留当时 request-header、callSchemas 与持久 Assistant 事实；D2.1 的“适用字段、未知保持未知”与官方行为一致，没有要求伪造历史。Table CSS 的可伸缩侧栏及 `max-width:760px` 覆盖式详情支持所述响应式方式。宿主给定高度和 `--dsh-composer-height:0px` 是不挂 composer 时必要的尺寸适配，不改变原生信息模型。

**发布物和真实组件证据。** 阅读 `output/feat-583-probe/{README.md,boot.jsx,controller-fixture.js,build.mjs,closure.json,artifact-provenance.json,browser-evidence.json}`。最终 boot 通过公开 `ClientModuleSystem` 执行官方 closure bundles、完整 `ui-conversation.apply`、官方 Session Controller／RemoteStream／SessionBinding／uiSession，并只挂 trajectory slot；只读 fileUpload、workspace navigation、configForms 属于装配边界，没有替代原生 event window 或 definitions。独立计算 probe 的 trajectory、ui-conversation、ui-attachment、api-session-controller 四个 client bundle SHA256，均与本机实际安装的同版本发布物一致，不能把早期 constructor 变体当最终完整接法。

独立查看 `native-controller-overview.png`、`native-tool-inspector.png`、`native-full-conversation-inspector.png`、`native-assistant-timing.png`、`native-image-inspector.png`：真实原生紧凑表格包含系统、用户、上下文、助手与工具，四项工具条和三轨都在；工具详情实际包含 Schema 和 950ms 计时，助手详情实际显示总时长、首 token 延迟、生成和吞吐量，图片详情使用完整中文标签。官方 attachment 插件确实注册 trajectory image slot；完整 conversation apply 保留其 locale 字典，D2.1 已要求附件、语言包和主题生效。这些证据足以确认公开嵌入方向，不证明真实 Node 归属、附件授权、live settlement 或重连故障已经通过。当前 format 4 的 compact stream 位于 event 内，实施沿用官方客户端处理；E3 中 packed/compact 是需核对的内容语义，不是新增旧版解包器的授权。

**宿主原型与旧证据处置。** 本轮不沿用 R1 对手写轨迹主体的视觉放行。修订 prototype 明确仅呈现 Work 内切换、执行选择、读取状态与挂载区，内部没有假原生表格或检查器，符合最小呈现范围。独立 view_image 查看本轮真实渲染的 `output/feat-583-design/host-desktop.png`（1280×900）、`host-mobile-offline.png` 与 `host-mobile-expired.png`（390×844），确认原页导航、主次、子执行归属、离线重试和失效清除说明可读，无遮挡或范围混淆。宿主结构与 R1 已核的 current Work 风格一致；不把示例状态控件或大块占位文案带进产品。

交互证据来源明确：root 本轮 CUA 走通原生切换、手机选择子执行→离线→资格失效→返回工作记录，返回后 tab selected 且三条主轮次与子入口仍在；本 reviewer 核对截图与 prototype 的对应状态／handler。当前 reviewer CUA 的 IAB 不可用、Chrome inventory fetch 失败，因此未冒称自己重放这些点击。视觉结论来自实际画面，交互结论由本轮操作记录与源码相互支持；原生内部逐控件、历史和实时交互仍由 V3/E3 在真实实现中验收。root 已恢复 viewport 并关闭其临时 tab；本 reviewer 未成功创建 tab 或改变 viewport，无需额外清理用户浏览器。

**核心边界与历史机制。** `retained_from: Round 2`：D3 的非激活 cold observeSession + official page、live follow 第一帧复核、新物理 generation；D4 的 Work／Node binding／原生父链验证；D5 的可信附件来源及先授权后读字节；D6 的独立出站观察 WS、一次性 scope/Connection/owner/epoch 票据、有限 next response 与有界队列均未变化。新 fidelity 要求不需要放宽 whitelist、审批、账号或附件边界，不增加 IM 原始轨迹存储，不开放节点业务端口。DSH Host/runtime 仍由 integration 独占，viewer 仅依赖公开 browser/client；PA、IM 和 Node 对 native payload 仍保持不透明。R2 的源证据和新 diff 一致，完整官方 conversation.apply 初始化 input shell 不等于挂载发送 UI，写操作仍须由既定 transport／integration 双白名单拒绝。

**Delta、M1 与最终验收。** IM delta 在正确 ADDED Requirement 下新增保真 Scenario，保留原有场景；Gateway delta 未变，仍表达消费者所需的只读、生命周期、慢观察隔离和附件边界。单 M1 未拆层或增加并行冲突，V3／E3 已从“相似外形”升级为 D2.1 全能力逐项操作与真实日志核对，并覆盖 locale/image slot、历史 Schema、原始内容和系统变化。V1/V2、E1/E2/E4/E5 继续覆盖宿主、按需、cold 非激活、权限和观察隔离，实施前置可用。

用户最终看真实测试服务的要求在设计末尾已收口：验收后保留隔离体验栈，交付 URL、账号、node identity、PID/cwd、构建版本与清理命令；上方 e2e-down 是后续清理入口，不能在最终交付前关闭该体验栈。Runbook 要求真实 Web→IM→Node→DSH 与真实原生记录，probe 只证明客户端公开装配，fixture 成功不冒称真实 LLM。未实现的 Gateway E2E 是 M1 必做工作，并非本轮设计缺陷。

### 历史问题闭环

| Issue | 本轮证据与 Author Resolution | 状态 |
|---|---|---|
| R1-C1 | `retained_from: Round 2`；核心冷／live 读取设计未变，新 fidelity 不重新引入 cold follow promotion | **closed** |
| R1-W1 | `retained_from: Round 2`；独立观察通道、有限拉取、超限 abort 与 E5 保持 | **closed** |
| R2-R1（建议） | Author accepted，专用 viewer header／真实 iframe 装配留在 D2/E3 验证；不扩大主应用嵌入策略 | **accepted，非阻断** |

### Issues

无新增 CRITICAL 或 WARNING；无未闭合阻断问题。

### Recommendations

无新增改造建议。实施与产品验收直接按 D2.1／V3／E3 的完整能力表核对；不要再用宿主 prototype、早期 probe 变体或旧手画主体替代最终真实服务上的官方轨迹效果。
