# feat-625: Auto 审核失败的有界恢复 — 技术方案

> 对齐: [spec.md](spec.md)，本次重新交办首文档 commit `d72e220f1d21827c65e046f704c13837ea39d7c2`（末次历史授权措辞修正见本设计分支）。产品 grounding 为 `304c59412e8316ef3ea7df9d904a9a450ca618a2`；本稿是待独立 Gate 2 的事前设计，不是 as-built 或已验收能力。

## Changelog

## 现状分析

### 涉及范围

本次重新交办在新 workspace 核实 `HEAD = origin/main = 304c59412e8316ef3ea7df9d904a9a450ca618a2`，开始时 main 干净，`git ls-remote origin refs/heads/main` 核实同 SHA；此后 main 只有本次首文档提交。没有读取旧群、旧子会话、旧分支或旧运行数据。仓库自带625文档和报告只作历史材料；本稿实质更新后旧 R4 Approved 不再适用，需新的独立审查。没有新增 worktree，设计分支 `design/feat-625-r2-361` 持续复用本 checkout，不写产品代码。

| 当前路径 | 实际职责与本次影响 |
|---|---|
| `packages/dsh-integration/src/index.ts:137–145,208–212,466,570` | 生产安装 attribution、CC/Codex/NanoApproval；`session.observe` 返回 durable approval entries；PA disclosure 使用同 Codex service 的独立入口。Node 当前 shared-host/owner lifecycle 经 integration 接入，不另建服务或切回旧装配。 |
| `src/policy/approval.ts:103–150` | downstream/fastpath、模型选择、策略派发、取消、审计、计数/fallback；try 前 message context、try 内 inherited 准备尚无统一边界，异常 String 丢结构化 facts。这里拥有一次普通待审工具动作的恢复 controller；免审和原 fallback 不进入恢复。 |
| `src/policy/classifier.ts:13–38` / `cc.ts` | CC workspace fastpath、30/60秒两阶段或 legacy 30秒单阶段，无失败恢复；stage1异常不进stage2。已按声明选择 effort。controller 恢复当前失败阶段，保留有效阶段结果，不重复实现已有能力。 |
| `src/policy/codex.ts:47–203` / `codex-context.ts` / `codex-inspection.ts` | tool/disclosure 分开缓存的原生 reviewer、full/delta/fork、一次 context rebuild，共享90秒。`codex-inspection.ts:59–65` 已用单次 `execFile` + SIGKILL 杀掉阻塞FS，不退回进程内FS。625仅为 tool 路径增加 action 恢复，保留 disclosure 当前严格parser/预算/缓存隔离。 |
| `src/policy/types.ts` / `audit.ts:4–19` | Nano `nano_approval` domain v1 已有call/model/耗时/usage，但无内部attempts；增加私有controller与可选trace，旧行仍可读，不新增不可忽略Session事件。 |
| `src/llm-attribution.ts` | 公共 `llm/stream` + ALS + 单undici dispatcher为模型POST加归因header，未观察response。扩展既有seam获取必要failure facts，不增加第二dispatcher owner。 |
| `apps/node/src/approval.ts` / `configuration.ts` / `runtime-partitions.ts`；integration `agent-config.ts` | 当前默认Codex、逐Agent覆盖/继承与生效、shared-host中的owner释放/disabled控制。配置格式、当前模型能力选择及lifecycle不变；不增加可配retry开关，不让供应商always覆盖上限。 |
| `tests/{approval*,codex-approval*,llm-attribution*,personal-security*}.test.ts` | 已有native profile、source/parser/admission、context rebuild/late cancel、tool/disclosure namespace及effort回退。新测试通过窄controller接口与真实HTTP/native/IM路径补缺，不替换有意义的现有回归。 |

上表 `src/` 与 `tests/` 未展开前缀时均位于 `packages/dsh-integration/`。

### 既有约束

- AGENTS/SPEC：仅 integration 使用 DSH 公开 exports；不 runtime fork、private import、第二套 Agent loop或新增内核HTTP服务。PA/Channels/IM 不 import DSH。
- current `docs/specs/gateway/agent-capabilities.md:502–608,1025–1030` 保留默认Codex/显式CC或DSH、来源、原模型effort能力、风险/授权、子任务边界与fallback。L535“已有重试”含混，不作已实现证据。delta仅在当前完整Requirement内修改失败Scenario，不恢复默认Nano或缩窄继承链。
- 所有已确认额度/完整预算不再提问；不同模式fallback保持，尤其无人值守配置allow。主动取消、owner disabled/释放优先；不得借恢复使停止的Agent在shared host中复活或影响同host其他owner。
- 不动客户端面；Work继续展示实际工具与用户可见结果，无新页面/按钮，故无prototype。详细attempt trace通过原approval domain / `session.observe`取证，不声称Work已有attempt明细UI。
- `CodexApproval.reviewDisclosure`、独立PA入站检查、消息representation/转发/Task审查不是本次普通工具Auto恢复范围；共享service重构必须保留其严格parser、context与checkpoint命名空间，不让代码复用变成新增重试授权。

### 可复用能力

本次在新workspace执行 `pnpm install --frozen-lockfile` 成功，锁定 DSH `0.2.1-alpha.1`、undici `8.11.2`；实际重读package export map、公开d.ts和下表相关打包实现，Node根import核实 `LlmError`、`resolveRetryPolicy`、`BlockAssembler`、`isAgentLoopRequest` 均为function。这是当前公共能力取证，不继承历史probe输出、不证明625实现已完成。

| 能力 | 用 / 改 / 不用与证据 |
|---|---|
| `@deepseek-ai/dsh-llm` 根/`./types` | 用 `LlmFailure` 的 code/status/providerRetryAfterMs/requestId、`LlmError.failure`、`BlockAssembler.finish.failure`；用公开类型而非解析 JSON.stringify(error)。公开 retry-policy/types 仅复用概念，不照搬供应商 always/default5次。 |
| `@deepseek-ai/dsh-llm-retry` 根 | 不调用它执行审核恢复：公开 `apply` 是插件，挂 `agent/request-error`；没有公开通用 retry(fn)。CC hand-built stream 不经过该事件；Guardian scoped listener拥有终止权、不调用next，避免再叠原生重试。主 Agent 的原生重试照常，非本unit。 |
| `@deepseek-ai/dsh-agent` 根 | 用 `ctx.agents.create({signal,setup,…})`、`Agent.cancel/whenIdle`、`AgentHandle.dispose`；公开 create支持creation-only signal，dispose停止、drain、移除会话/展开scope。所有恢复使用原生Agent，不新建循环。 |
| public `agent/request-error` payload | 用结构化 failure 捕获 Guardian 最终adapter失败，返回 undefined让该尝试结束；由 controller 决定是否开启新审核尝试，不在事件内同step重试。 |
| pi-ai adapter | 打包实现 `maxRetries:0`，原生 loop负责重试。已观察 `mapStopReason` 的 in-band错误常仅保留code/message，没有status/Retry-After；不能许诺上游总能提供headers。 |
| `llm-attribution.ts` + undici 8.11.2公共 `Dispatcher.compose/onResponseStart` | 改既有模型HTTP seam以补实际可见 response status/Retry-After；只观察不改响应/重发，不读取body/credentials。其他adapter无法观察到的facts明确unknown；不patch pi-ai。 |
| 原 audit/route/deny counters、原Guardian isolation/context预算 | 用，增加optional trace和全action rebuild计数，不增加新数据库或第二套计数器。 |

包内证据定位：`@deepseek-ai/dsh-llm/lib/types/{index,types,retry-policy}.d.ts`、`@deepseek-ai/dsh-agent/lib/types/{index,runtime-types}.d.ts`、`@deepseek-ai/dsh-llm-retry/lib/{index.js,types/index.d.ts}`、`@deepseek-ai/dsh-llm-pi-ai/lib/index.js`（mapStopReason/maxRetries）。这些路径只用于**阅读包声明/实现取证**；实施imports只用export map根或已声明子路径。

### 相关历史

- feat-615：独立CC/Codex插件与Guardian生命周期；沿用full/delta/fork、配置失效和只读工具限制，不把Codex简化成另一段分类prompt。
- 既有approval-sources及classifier相关测试：去重指令、来源事实与超窗处理；不得裁授权、改来源或模型以恢复失败。
- refactor-581：DSH接入与进程边界；不恢复旧Python broker。
- [bugfix-626](../archive/bugfix-626-approval-context-fidelity/design.md) 的普通工具有效上下文、来源规范化、admission/parser行为仍在当前源码，必须保留；历史报告不作本轮验收。
- 后续current已默认Codex并加入原模型effort回退；Guardian已支持独立PA disclosure和可终止的inspection子进程；来源扩展到宿主确认的human/represented user、Task stop/UI resume，主Agent默认独立换窗而非一律摘要。新设计必须基于当前投影/killable检查/生命周期，不从旧625草案复制旧策略或旧prompt。
- 本次实际运行 `approval-sources.test.ts`（14）、`codex-approval.test.ts`（9）、`codex-approval-lifecycle.test.ts`（8），31/31通过，exit0。证明当前source/parser/admission/缓存隔离及声明effort回归基础可复用；没有发真实模型请求、运行HTTP/IM旅程，也不证明新增重试已实现。

### 626交叉保真约束（最新基线必须保留）

- `approval.ts` / `classifier.ts` / `types.ts`：`ApprovalReviewRequest`已无personalAuthorization；所有service恢复仅重用冻结的有效context投影，不调用PA入站/披露检查作备用审核。PA两道消息检查及主人/observer边界仍独立，故障恢复不得修改它们。
- `sources.ts` 的`codexEntries`在当前/继承来源规范化后再计算cursor：Inbox每message独立保留page/真实sender/reply/observation；同call generic正文去重但不同call不删。**同action技术恢复**只重用prepare冻结的实际live/restored，不因503、超时、创建新full reviewer或context重建改变observation。**同进程委派**按现有epoch/来源契约保留：`saved.epoch === this.epoch`使用`restoreEntries(...,false)`，保留可信live；已有restored绝不升live。**跨epoch/真正失去进程观察证明的恢复**才按既有`restoreEntries(...,true)`置restored；旧持久`host_context`也保持原restore语义，不能仅凭“inherited”身份统一降级或升级。`codexEntries`只规范化/去重、不解释授权；首次prepare冻结规范化rows，技术恢复full重用它们，不能反复按进程恢复规则重标。CC保持普通工具正文省略及有效历史界限；不复活压缩原文、不新增授权取数，也不把技术恢复或持久化本身变成新授权。
- Codex profile/admission保留626：User/ManualApproval计消息成本，非用户成功纳入才计40条上限，消息/工具单项5000/1000、聚合20000/10000；ProtectedAssistant及最近5条已选工具受保护。先剔除永远放不下的optional，再按类别/旧先策略淘汰；preserve不裁历史，recovery才按规则缩旧历史并保来源首尾/遗漏。无全库重读、无0.65预算乘数、无新证据摘要器。
- output prompt及`parseCodexDecision`保持626：`{"outcome":"allow"}`为有效low allow；bare deny缺省high、authorization缺省unknown，rationale用原默认，外围文字中的JSON按现parser有效；非法outcome/enum/type才是格式失败。不得强制旧四字段或恢复parser额外critical-allow禁令；风险语义由现有policy判定而非格式恢复controller改写。
- 这组是保留已合入行为，不扩大首文档要求；新增恢复的格式计数必须以当前parser结果为准，不能将合法bare/embedded verdict误耗format额度。

## 架构总览

Before：CC每个阶段直接调用stream；Guardian tool/disclosure共用执行器且只有context重建；独立审核错误直接进入facade失败分流。After：仅普通tool Auto路径新增一次action恢复租约，原策略提供一次正常判定，原facade保留授权/最终分流。disclosure仍使用原有单次90秒+context恢复路径，既不接收普通tool的controller，也不共享其额度或失败checkpoint。

```text
原 tools/pre-execute → downstream 权限/既有 fastpath
                         ↓ 仅需模型审核
NanoApproval: 冻结动作、配置、模型与来源 → 一个 ReviewRecovery
  ├─ CC/legacy: prepare一次 → run(stage1,30s) → 有效非allow才run(stage2,60s)
  └─ Codex: prepare一次 → run(guardian,90s)
                          ├─ 首轮可复用已提交checkpoint/full/delta/fork
                          ├─ context rebuild至多一次/action，共用本次90s
                          └─ 技术失败：dispose失败reviewer → 退避 → 全新full尝试90s
                         ↓
有效verdict 或明确终态 → 原 audit/deny计数/人工或fallback路由 → 原生工具至多执行一次
```

controller仅恢复**判定工作**，从不调用待审工具体。CC正常阶段与Guardian检查步骤不是额外恢复；计数隶属同一 `ToolExecution`，不隶属stage、model request或reviewer session。

## 关键决策

### 1. **新建窄的 action 级 ReviewRecovery；策略保留其自身正常判定。**

`policy/recovery.ts` 隐藏结构化错误分类、共享2次恢复/1次格式额度、计时、退避/取消及trace。只有普通工具Auto facade构造一个并传给选中策略；CC在单阶段边界调用run，Guardian tool在一次正常审核生命周期边界调用run。策略提供不含service loop的一次正常工作；共享Guardian执行器保留 `purpose`，disclosure未传controller时保持当前语义，不另复制一套Agent loop。模块有深度：去掉它会让安全计数/错误/取消规则在策略间漂移；不是任意业务可用的retry库。

controller必须有明确owner lifetime并链接精确exec.signal。当前shared-host中的Agent disabled、configuration release、service卸载均撤销所拥有action的generation、打断退避、cancel/drain自己创建的reviewer；仅配置切换排队不抢改正在执行整轮的冻结规则。release以purpose+parent精确归属，不按整个进程杀Agent；未知/失效owner不得提交allow或发布checkpoint。保留现有tool/disclosure缓存namespace；registry只登记持有tool controller的reviewer，不截获disclosure流。

不选：整个facade外套loop（会重做CC stage1、重复准备/授权读取，并把fastpath/fallback也套进去）；也不选把供应商policy全局改成2次（会改变主Agent，且无法表达格式子额度/Guardian预算）。legacy共享classifier使用同controller，单阶段30秒，作为兼容覆盖。

### 2. **Guardian技术失败后废弃失败分支、用同一冻结证据从full恢复；不重用失败历史。**

第一次正常尝试保留现有缓存和并发fork优化。遇到可恢复服务失败、格式失败或90秒deadline：先撤销本次generation的发布资格、cancel并dispose其handle；清空本次可用checkpoint引用，后续恢复从该动作开头冻结的parent evidence重建full reviewer。失败turn中的assistant输出、检查结果和半成品事件均不seed新尝试，只有当前动作成功完成且generation有效才commit新checkpoint。已有另一并发动作的成功checkpoint不能被失败分支覆盖或清除。

`contextRebuildRemaining=1` 属于action controller，在全部技术恢复间共享。context overflow/compaction仍可一次重建，处于当前90秒尝试内，不消耗服务恢复额度；第二次context失败终止，不得再借service retry重置context额度。沿用626的`reviewInput` preserve/recovery admission：有checkpoint的delta用`allowHistoryTruncation=false`（preserve），放不下触发正常context rebuild；无checkpoint的full（含初次full、context重建full和技术恢复full）沿用当前默认`true`的recovery admission，按实际模型剩余预算选择，不恢复已删除的0.65任意乘数。技术恢复改成无checkpoint的干净full并不重置contextRebuildRemaining，也不另套新的证据裁剪策略或重放父压缩已删除的历史。完整动作与required证据放不下即unavailable；授权约束不可静默删掉，recovery仅按626规则对旧历史保来源/首尾/显式遗漏地缩短。

替代方案：在公开 `agent/request-error` 返回retry可保留已完成检查，但同一个turn的整体90秒deadline、非法verdict、事件半提交和context重建额度将分散到多处，难以证明重置预算且不串状态。当前选择牺牲失败分支的只读检查缓存，换取确定隔离；只读重复无业务副作用，所有model/inspection仍计入trace。不是未经清理的“外层重跑整个Guardian”。

### 3. **完整判断预算分配给新尝试，准备、退避与回收另有硬边界。**

| 事项 | 本设计值与范围 |
|---|---|
| action准备 | 15秒，使用父取消和owner lifetime，冻结来源/精确动作/配置及resolve审核模型能力一次。包含必要messageContext、当前有效历史和inherited，**不调用pa.authorization或全库授权/聊天历史**。静态fastpath先返回；需context才能确认的owner_message及Auto关闭保持原路径，不启动model attempts。相关异步lookup使用同一个15秒envelope，不在try外无限等，发现无需模型时不消耗恢复额度。prepare超时为技术不可用，不是判断超时，不重试准备。 |
| CC判断 | 每次stage1模型尝试30秒、stage2尝试60秒；重试仅当前失败阶段，保留之前有效stage结果，2次额外额度跨阶段共享；legacy每次30秒。 |
| Guardian正常尝试 | 每次90秒，覆盖reviewer创建、上下文编排、所有模型步骤/只读检查及至多一次全action context rebuild；技术恢复的新尝试重新分配90秒。 |
| 额外恢复 | action最多2次；其中format最多1次；不因CC stage/Guardian新session/context重建而重置。 |
| 退避 | 第1/2次本地基准500/1000ms，±10% jitter；每次等待最多10秒，总最多20秒。有效Retry-After按下文处理，不截短。格式恢复也计额度，使用本地退避。 |
| 单次回收 | 最多5秒等待stream iterator收束或原生handle.dispose；超时quarantine该资源和未完成promise，终止动作，不再启动恢复。最多5个handle回收等待（原旧cache一次+3个正常尝试+一次context重建）。 |
| action安全上限 | 360秒，不含原有fallback人工等待及工具体执行。Codex最坏15+3×90+20+5×5=330秒；CC正常90+2×60+15+20+最多4×5=265秒；legacy更小。此保护留足完整获准机会，不是复活被撤回的共享90秒方案。 |

prepare异步只读工作超时后不使用晚到值；它们持有被撤销token，只允许资源回收、不允许创建可执行reviewer/commit判定。源文件读取尽量传signal；不能原生中断的只读promise需挂settle handler避免未处理异常，不能因promise race而遗忘创建中的handle。`agents.create`传creation signal且setup/commit检查generation，迟返handle立即dispose。

### 4. **结构化分类优先；空返回统一占format子额度，真实拒绝永不作为技术失败。**

| 输入事实（优先级自上而下） | 分类/处理 |
|---|---|
| 父exec已取消/owner释放或controller已关闭 | cancelled，撤销generation，无重试、无fallback放行；始终优先于同刻TIMEOUT/allow。 |
| 本次controller判断计时器到期 | review_timeout，允许共享额度内恢复；不能凭通用AbortError文字猜测。 |
| AUTH/INVALID_CREDENTIAL/MISSING_CREDENTIAL、QUOTA/ACCOUNT_QUOTA、NO_ADAPTER/INVALID_REQUEST/永久配置错误 | permanent，不恢复；即使同时有429status也不能覆盖quota/auth。 |
| 当前parser接受的有效最终deny/allow（含626的Codex bare/embedded/default verdict） | 正常verdict，不进入错误分类、不耗format额度；CC stage1非allow正常推进。controller不新增风险/字段校验。 |
| 原生EMPTY_RESPONSE或正常完成但空白/无法解析verdict | invalid_verdict（细分empty_response/empty_text/malformed），最多一次，共用总额度；不因native默认把EMPTY_RESPONSE当transient而绕开子额度。 |
| RATE_LIMIT或可确定的429 | transient，尊重可得Retry-After；若quota/永久事实存在先排除。 |
| status=503，或SERVER且status不可得 | transient；已知非503服务器状态本unit不额外泛化重试。TRANSPORT/STREAM_CLOSED等明确结构化传输失败、provider TIMEOUT可恢复。 |
| CONTEXT_WINDOW_EXCEEDED/本地ReviewBudgetError/compaction | CC不可用；Guardian只走一次全action context重建；不能落入service retry。 |
| 未知异常/中间件或编程错误、无本地deadline的ABORTED | unavailable_unknown，不盲重试；保留facts，无message regex推断临时网络故障。 |

`BlockAssembler.finish.kind=error/aborted`读取其failure；thrown只接受真实LlmError或已校验的公共failure来源。Guardian在scoped request-error保存完整failure，turn/end仅作终态佐证，不再JSON字符串化后反向解析。context本地标记/结构化code替代当前宽泛正则；其它错误不臆测context恢复。

### 5. **补充实际可见的HTTP facts，但不依赖上游私有错误分类。**

沿用 `installLlmAttribution` 的单个dispatcher owner，新增内部 `withReviewHttpFacts(sink, iterable)`，在iterator创建/每次next/return的ALS context内安装唯一请求sink。**`llm/stream` bound于全局LlmRuntime，不是Agent carrier；scope.on不提供按reviewer隔离。** 本设计只安装一个integration级`llm/stream`分派listener；不在每个Guardian scope注册llm listener。`agent/request`与`agent/request-error`仍用其真实Agent carrier scoped listener。

分派在读取任何`currentAttempt`、创建request ordinal或绑定sink之前执行：

1. Guardian owner registry只接受本service创建的**精确原生reviewer sessionId**（包含每个full/delta reviewer或并发fork各自唯一ID），不用parent/rootOf/主Agent session、模型名或字符串前缀推断归属。公开`GenerateOptions.sessionId`是loop stamped身份；另用根export `isAgentLoopRequest(options)`确认原生loop envelope。普通CC hand-built options没有该marker。
2. `!isAgentLoopRequest(options)`、无sessionId、无精确registry entry或辅助`purpose`流：原样`yield* next()`，不读任何owner/currentAttempt、不断言active、不改signal/metadata、不新建或清空sink；因此CC调用者自己安装的ALS sink也原样保留。辅助compaction仍由现有scoped request/context检查处理，不能借它创建普通reviewer request额度。
3. 只有精确命中本tool reviewer的普通loop流才读取该entry的`currentAttempt`；校验active generation与冻结provider/model/resolvedEffort一致。resolvedEffort沿当前模型能力：有low选low，否则defaultEffort或首个声明effort，无可调能力则不强设；不得固定low、换模型或在恢复时改变档位。idle entry缺currentAttempt时仅拒绝**这个reviewer自己的异常发流**，绝不能阻断main/CC/另一reviewer。成功匹配后为这一条stream分配requestOrdinal和sink，快照attempt引用，后续iterator绝不重新从可变entry读取新attempt；继续next或写facts/usage前检查所捕获generation仍有效；失效后仍须对旧iterator执行return清理，但关闭sink写入，晚到值不得写终态trace或后继attempt。
4. owner entry在`agents.create` setup登记（已知创建用sessionId，尚不可drive），setup失败负责释放；create完成后在followup前绑定currentAttempt。缓存idle保留身份但清空attempt；每次复用显式绑定新attempt；dispose/quarantine先使attempt失效并保留精确entry tombstone阻断该旧reviewer，直到drain完成才按entry对象相等条件删除。新full/fork使用新ID，不继承旧entry。流finally只关闭自己的sink，不清除后继attempt的绑定。
5. CC/legacy在其调用点直接包装**本次stream**，而不向Guardian registry登记主session；同parent多个CC请求各有独立ALS/request ordinal。transport handler只捕获当前sink的模型POST response facts，全部原handler方法保持this/参数/返回值透传。

公开依据：`dsh-llm` public index.d.ts的事件this为LlmRuntime；types.d.ts的sessionId声明为loop stamped request routing identity；公开`isAgentLoopRequest`检查精确request对象身份。已读固定版agent-loop打包L1269–1276，正常request用`markAgentLoopRequest(Object.freeze({...sessionId:this.session.id}))`；读取实现仅为证据，不private import。Author R1公开无网络探针与局限见design-review报告，实施native/HTTP验收不能被该探针替代。

仅 `POST /(v1/)?messages|chat/completions|responses` 的当前有sink流可观察；跳过主Agent流/其他工具HTTP。只取status、Retry-After和白名单request-id，不记录完整headers、body或URL query。成功200不覆写同次失败facts，多次HTTP只关联本model request最后失败响应；不得把不同模型请求之间的429带入下一请求。

adapter已有结构化code优先，HTTP补status/delay；401/403可确定AUTH，429/503可在adaptercode不精确时明确分类，但未知400不能伪装成transient。Retry-After解析秒数或HTTP-date（相对接收时wall clock转成单调duration）；非法/过去值视为不可用并记录缺失，不猜0。有效delay在等待开始按尚需等待计算，不能重复扣减为负。

有效Retry-After不大于10秒时，等待 `max(本地退避, 尚需等待)`；超过10秒则以 `retry_after_exceeds_budget` 终止、走原fallback，而不是截短后提前请求。已有授权额度但没有可接受等待不启动下一次。provider原生failure与HTTP事实冲突时保留二者的摘要，以更保守永久分类优先；不会用retry-after绕过2次上限。

非undici或不暴露HTTP headers的adapter，只能按公开failure提供的delay处理；若两者均没有，使用本地退避并明确 `retryAfterKnown=false`，不宣称遵从了不可见的header。当前生产pi-ai/Anthropic路径的HTTP fixture必须证明补充observer确实生效；不允许只靠类型通过签字。

### 6. **旧fallback、计数与工具调度不进入恢复controller。**

所有恢复仍处于一个pre-execute Promise内。controller只返回有效verdict或带trace的终态错误；facade在检查父取消和generation后才返回allow。技术耗尽先审计no_verdict再按原route处理；不计classifier_block，不自动换审核模型，不改denyLimit或风险升级规则。unattendedFallback=allow的既有放行只在恢复终止之后执行一次并标记route，不被记为有效模型allow。interactive按原ask_timeout等配置；Global/child仍return_to_agent，schedule/heartbeat仍unattended。

## 接口与数据流

以下为integration内私有接口，不加入product-contracts或公开package exports；具体类型命名可在实施时等义调整，职责/约束不可改变。

```ts
class ReviewRecovery {
  prepare<T>(work: (signal: AbortSignal) => Promise<T>): Promise<T>;
  run<T>(scope: 'cc-s1'|'cc-s2'|'legacy'|'guardian',
    budgetMs: number, work: (attempt: ReviewAttempt) => Promise<T>): Promise<T>;
  takeContextRebuild(): boolean; // action共一次，不给新的service retry机会
  finish(outcome: ReviewOutcome): ReviewTrace;
}
interface ReviewAttempt {
  readonly signal: AbortSignal; readonly generation: number;
  request<T>(work: (facts: HttpFactsSink) => Promise<T>): Promise<T>;
  assertActive(): void;
}
interface GuardianStreamOwners {
  // exact native reviewer identity, not parent/root/model route
  register(sessionId: SessionId, owner: GuardianOwner): () => void;
  // Global llm/stream: identity test first, then bind exactly one request sink.
  wrap(options: GenerateOptions, next: () => AsyncIterable<StreamChunk>): AsyncIterable<StreamChunk>;
}
```

- Facade先跑downstream/静态免审检查，再对候选动作使用有界prepare（含必要message context和可能的owner免审判别）；只有需模型时才开始reviewId下的attempts。冻结exec工具名/完整参数、配置、provider/model、按声明选取的resolvedEffort、有效历史和真实message context；不把后续模型建议或技术恢复当新授权。模型能力/effort只解析一次，每个恢复重用，不承袭主Agent effort。trace不存敏感prompt副本。
- `ReviewRun` 保留purpose和parse/evidence回调，tool额外传私有recovery；disclosure不传，继续原90秒/context重建及严格 `parsePersonalDecision`。tool恢复分支不可改变disclosure的context profile、reason/needs_owner/unavailable解释、宿主commit检查或缓存；同parent tool/disclosure+main并发需各自有效，reviewer registry只认带tool attempt的精确身份。
- `ApprovalReviewRequest`增私有recovery，`ApprovalReviewResult`可返回决策/usage/metadata，trace由controller统一持有，失败同样可取得。策略为单个run回调提供“不含重试的一次正常判断”，不得自行另套service loop。
- CC的buildPolicy/transcript/suffix/model info准备在一次15秒prepare内完成；每次stream建新BlockAssembler（不混partial），传parent关联sessionId便于现有proxy定位。有效stage1结果不会因stage2失败丢失；stage2共享总额度。legacy只用s1。
- Guardian把trunk claim/忙闲/fork作为整个action租约，准备parent证据一次。初次能沿用committed checkpoint；恢复强制full。复用的reviewer保存可替换的`currentAttempt`引用；Agent carrier的scoped request/error监听器读取当前引用，全局llm分派仅在精确身份命中后快照它，不能依赖scope隔离llm事件或捕获上一个动作的controller/signal。action结束/idle时清空它，未绑定时只禁止这个reviewer自己发起普通请求。成功commit时必须满足：signal未取消、generation有效、仍持有原trunk对象/租约且配置fingerprint未失效。失败/cancel/config release不能republish旧cache。
- 原生reviewer每次model request通过`ReviewAttempt.request`记录独立request ordinal及usage；多个只读检查步骤不计额外恢复；无判定结束才进入format分类。context重建先dispose旧分支并takeContextRebuild，再在本次剩余90秒内重建，不重置正常尝试时限。
- action、attempt、request ordinal三层区分：CC正常s2也是新attempt记录但retryOrdinal不增加；Guardian多step是request记录，只有controller授予的恢复增加retryOrdinal。audit避免把“最大2次额外”误读为“总共只能2/3个model requests”。

### 回收和晚到结果

每个尝试拥有独立AbortController/timer、generation token；父exec signal保持独立。计时器abort后策略先失去提交权，再中断请求。Guardian移除abort listener、cancel、dispose，await其drain，dispose完成前绝不开始下一次恢复。CC主动关闭iterator并等待其settle，丢弃partial/verdict。

5秒内无法drain是 `cleanup_unavailable`：本action不可恢复；controller封闭、引用放入service的tracked cleanup集合，不缓存/seed/交给新调用；Guardian该parent reviewer租约quarantine，直到旧dispose真正settle才允许再次创建该parent reviewer。晚到allow和late create结果只可清理，永不能resolve旧动作allow。服务dispose继续drain tracked集合，生产runtime正常shutdown保留原生清理路径；不从这里kill共享DSH进程。测试必须验证迟返/不合作模拟的失败关闭，不能仅用Promise.race声称取消了底层工作。

### Context 消费链与组合验证

Consumer是CC/legacy分类模型、普通tool Guardian，以及共享执行器但不接入恢复的PA disclosure Guardian。来源链保持当前 `ApprovalSources.history/transcript/codexEntries → policy/reviewInput → public llm/stream`；CC保留当前instructions/省略工具正文规则，Codex保留当前effective evidence/admission/parser和只读host tools，不新增授权检索或来源解释器。

生命周期：一次prepare冻结当前模型实际可见rows、精确动作/受众和能力；技术失败丢弃失败reviewer的assistant/检查结果，再用同一冻结rows按full规则恢复。后来的新工具动作重新读取有效上下文，按正常cursor/full/delta/fork处理；配置变更、换窗/有效历史重写或owner释放失效原checkpoint。主Agent默认独立换窗及可选压缩均以当前deriveMessages实际保留内容为准，不重放丢失正文。原有source的live/restored、represented user、Task/UI stop来源保持宿主事实，不随新reviewer身份重标。

最小Before/After例：第一次输入有真实来源 `Inbox(message=m, live, sender=S)` 与完整planned_action A；reviewer做guardian_read后503。恢复输入仍有同一个m的live/sender/S、A与相同配置，不含失败read/assistant残片；跨epoch本来restored的m仍restored。已有合法bare allow仍被当前tool parser接受，format=0；PA disclosure的相同bare allow仍由其严格parser拒绝，不能借tool格式恢复转为授权。

Validation：除runbook§5.2的626来源/admission/parser组合，新增represented user/实际sent/Task stop投影原测试、tool+disclosure并发/namespace、owner disable与其他shared owner隔离、killable inspection卡FS时默认90秒及主动cancel排空回归。捕获脱敏的实际组装请求对照冻结rows/动作/effort，不用类名或mock输入证明模型消费。Gate2 reviewer须执行 `agent-context-review` Design Review；实施后的独立code reviewer执行Implementation Review，仍写入原报告，不另增审批角色。

### Trace与兼容

在既有approval record新增optional `recovery`，旧行无需迁移或重写，domain version/layout维持；Zod定义与读写同时接受旧行。trace上限由2次额度和Guardian90秒所界定；model request摘要最多100条，超出只累积计数/可得usage并置requestsTruncated=true，不影响执行权限。

| 层 | 必要事实 |
|---|---|
| review | reviewId、callId（原工具关联）、rules/reviewer、start/end/elapsed、terminalReason、finalRoute/fallbackOutcome、retriesUsed/formatRetriesUsed、contextRebuilds、complete |
| attempt | scope、attemptOrdinal、retryOrdinal、generation（诊断用）、开始/结束/预算、触发/最终failure category/code/status、delay与Retry-After可得性、Guardian sessionId/contextMode、outcome |
| request | 本attempt内requestOrdinal、model/provider/resolvedEffort（未声明可调时标明未设置）、可得requestId/usage、结束原因；不保存完整prompt/参数或原始headers |

usage优先保留每request原生用量；partial或缺失标unknown，不补0。汇总只标`knownUsage`加`usageComplete`，不能把成功末次usage当全部成本。格式输出仅保留类别与必要脱敏原因，不记录完整响应。最终原审计行仍负责计数；详细trace附该行，fallback第二行只关联reviewId而不重复累计usage。主动取消也新增不增deny计数的取消审计；domain写入失败为不可用，不能用丢失审计为理由自动allow。

trace在进程内收集；facade先计算拟采用的原route/fallback outcome，将该终态和完整trace持久化，再返回决策；人工待答记为interactive_pending而非伪造最终allowed，后续人答沿用既有human audit关联reviewId。终态由session.observe返回；不新增进行中journal、重启恢复/replay或新的UI。进程突死时不保证完整终态trace；可用原生Work/代理request事实定位，不能伪造未落盘尝试。Q报告注明此能力边界。

## 契约层增量 (delta-spec)

- Gateway：唯一target `docs/specs/gateway/agent-capabilities.md`，对应 [specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md)。新增失败恢复Requirement；完整替换含模糊“已有重试”的既有Requirement，保留其它Scenario语义；不改IM、全局Agent或顶层SPEC。

## 风险与回退

- 完整恢复可把一次判断拉长到几分钟且增加费用，这是已确认取舍；无并发预判或盲目模型切换。执行侧端到端等待需至少覆盖360秒审核+既有人工等待，不能沿用测试120秒poll把正常长恢复当失败。
- transport observer是进程级hook但有request-local sink、仅审核模型POST生效；必须回归现有主/子session归因和并发隔离。不可见headers明确unknown，不扩大到工具网络。
- Guardian full恢复会重复只读调查、失去失败分支缓存；公开Agent能力及request identity可用，但implementation/native fixture须证明create/dispose与全局llm分派的登记/绑定/回收顺序。强制同时保留idle cache、同parent的active reviewer与fork、另一parent reviewer、CC及main并发流，核对各request sink、header、delay、usage和取消互不串；另测缓存复用切换attempt、失败后新full身份和late旧流不能获得新generation。这些未验证实现不当作已完成能力。
- 不合作provider/FS teardown无法靠应用实现绝对物理消失；5秒quarantine保证无late授权/无继续重试，不以无限等待守住表面cleanup。发生真实cleanup不可用时记录具体资源并阻断，不自动重启生产。
- 回退为撤回本unit产品commit（保留历史audit可读性、未知optional字段无害），恢复原无故障恢复行为；不修改owner配置。merge/部署仍需人类指令。

## 一次性部署迁移

无。optional trace旧行兼容，不做历史记录回写或一次性数据迁移；不新增部署提示词，不执行生产操作。

## Runbook for Reviewer

详见 [reviewer-runbook.md](reviewer-runbook.md)：当前daily标准阵容、双策略真实插件旅程、IM/Work与脱敏trace出口、故障矩阵、计时和清理。只改integration库，没有新常驻服务；实际验收使用当前隔离IM+Node/DSH，不碰生产。fixture为测试进程，不是产品服务；正式handoff实际身份、Q节点、运行命令和导出定位由E冻结实现后填写。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本次隔离IM + Node管理的DSH | `./scripts/e2e-down.sh --wt "${WT_ROOT:?}"` | 真实产品 `./scripts/e2e-up.sh --profile daily --wt "${WT_ROOT:?}"`；受控fixture另用default/`--main-config "${E2E_CFG:?}"`，不与daily混用 | `source "$WT_ROOT/.e2e-ports.env"; curl -fsS "$IM_URL/openapi.json" >/dev/null`，再检查本次node online与daily清单身份 |
| 本地LLM代理（仓库外依赖，不由本unit管理） | 不停止 | 不重启，沿用开发入口 | `GET http://127.0.0.1:4000/health` |

**Review驱动方式**：端到端真栈，不改客户端面；允许复用客户端同一IM HTTP/WS接口代驱动（不可用RuntimeClient直接submit代替产品旅程）。Native RuntimeClient fixtures是worker工程证据，不替代Q真IM旅程。

**验收前置与本轮实际检查**：本次已安装锁定依赖，31项窄baseline通过；Node24.22.1，系统Python3.9.6，不满足全栈开发Python≥3.11要求。默认docs-check因缺yaml失败后使用本次独立临时文档环境修复，结果以交接验证为准；不把文档检查环境冒充合格全栈环境。未启动栈、未查代理健康、未调用真实模型，真实可用性未知。E/Q需准备自己的≥3.11 dev环境及按daily模板生成本次实际阵容/能力；Luna是模板审核路由，不是已验证真实可用。当前原模型effort适配已存在，runbook不再硬性要求low或固定Sol来修旧配置问题。Q执行前须对本次实际审核路由smoke，失败分本地配置/HTTP/provider报告；可继续独立的确定性矩阵，不能以stub或旧结论代替真实旅程。不得读/复制生产凭据或改生产配置。

## Milestones

默认单M1，CC、Guardian与共享恢复是一个安全闭环，不按策略或层机械拆分。设计期仅放 `.gitkeep`，不预填tasks/progress。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-review-recovery | 同一动作内完整预算的有界审核恢复 | 无 | 单M1 | integration policy recovery/transport、types/audit、classifier/cc/codex、llm-attribution/index；直接相关Vitest/HTTP fixture与IM关键路径；本unit设计/delta/验收证据、脱敏trace导出入口及最终canonical归并 | [reviewer] 首文档17场景逐项覆盖，CC/Codex真实隔离全局插件创建→安装→两次调用有Work/实际副作用证据，原权限/最终deny/各模式fallback不变；[reviewer] 真IM受控故障矩阵显示共享2次/格式1次、完整预算、Retry-After、取消及晚到零执行，真实服务可用性与fixture证据分开；[worker] recovery接口fake-clock组合矩阵、完整公开failure/header事实/native装配，精确原生reviewer身份分派及idle+active同parent fork+另一parent+CC+main并发归因、缓存attempt切换/旧流隔离、Guardian生命周期dispose/full恢复/全action rebuild≤1/quarantine、legacy兼容和optional audit旧行读写测试通过，runbook§5.2的有效context/零全库读取、真实human/represented-user/Task/UI-stop来源、admission/parser交叉回归不退化；tool+disclosure namespace/严格PA parser/预算/host commit不串，low/default/first/不可调effort全覆盖，保留默认Codex与CC/DSH继承和现有免审；shared-host owner disable/release只收束自己action且不复活、不影响其他owner，killable inspection卡FS/取消仍SIGKILL排空；[worker] 最窄相关Vitest后扩大typecheck/build、runtime dependency contract、docs-check及当前CI命令，独立门禁和脱敏证据齐全；[worker] runbook的受控HTTP fixture与可复跑真IM驱动进入长期测试，不改生产或增加正式运行配置。 |
