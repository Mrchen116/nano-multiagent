# feat-625: Auto 审核失败的有界恢复 — 技术方案

> 对齐: [spec.md](spec.md)，定稿 commit `80134297ddfabb08e80e83c01a20e20280de20f0`。

## Changelog

## 现状分析

### 涉及范围

事实基线为 `80134297ddfabb08e80e83c01a20e20280de20f0`（首文档提交；产品源码同 `5454f3140f9c92532c690db8dec80b9f77080384`）。

| 当前路径 | 实际职责与本次影响 |
|---|---|
| `packages/dsh-integration/src/index.ts:107,155–158,370–375` | 生产安装 LLM attribution、CC/Codex/NanoApproval；`session.observe` 已返回 durable approval entries。本次只增安装窄 HTTP facts observer，不新增运行服务。 |
| `src/policy/approval.ts:99–145` | downstream 权限、fastpath、冻结配置和审核模型、策略派发、取消、审计、计数/fallback；当前在 try 外/内的准备无统一边界，异常字符串化丢结构化 facts。这里拥有“一次待审动作”恢复 controller。 |
| `src/policy/classifier.ts` / `cc.ts` | CC workspace fastpath、两阶段或 legacy 单阶段；每阶段一个独立流。准备后才创建30/60秒 signal，没有失败恢复，stage1异常不会进stage2。改为 controller 驱动单阶段模型尝试，保留有效阶段结果。 |
| `src/policy/codex.ts` / `codex-context.ts` / `codex-inspection.ts` | DSH 原生 reviewer Agent、full/delta/fork、一次 context rebuild、只读检查、90秒共享时限；错误 listener 丢结构化 facts。改为明示正常尝试生命周期与 action 级恢复额度，检查权限和上下文投影不重写。 |
| `src/policy/types.ts` / `audit.ts` | request/result、Nano 自有 `nano_approval` domain v1。添加私有 controller 引用和向后兼容 optional trace；不把重试写进原生不可忽略的 Session events。 |
| `src/llm-attribution.ts` | 通过公共 `llm/stream`、Node AsyncLocalStorage、undici dispatcher 为模型 POST 加关联 header。扩展这个已存在的 seam，采集审核请求必要 response facts，避免第二个全局 dispatcher owner。 |
| `apps/node/src/approval.ts` / `configuration.ts` | owner/workspace Auto 配置解析、独立审核模型解析与下一轮配置应用。保持配置格式及生效边界；不增加可配 retry 开关，不让供应商 always policy覆盖产品上限。 |
| `tests/{approval*,codex-approval*,llm-attribution*}.test.ts` | 已有 native profile/RuntimeClient 真 DSH 测试、生命周期 fake clock 与只读约束。复用断言面，新增恢复组合与真实 HTTP fixture 测试，不替换成纯 mock façade。 |

上表 `src/` 与 `tests/` 未展开前缀时均位于 `packages/dsh-integration/`。

### 既有约束

- AGENTS/SPEC：仅 integration 使用 DSH 公开 exports；不 runtime fork、private import、第二套 Agent loop或新增内核HTTP服务。PA/Channels/IM 不 import DSH。
- current `docs/specs/gateway/agent-capabilities.md:508–579` 保留来源、独立模型、风险/授权、子任务边界与 fallback。L541“已有重试”与独立流现状含混，delta 明确修正，不作为已有实现证据。
- 所有已确认额度/完整预算不再提问；不同模式 fallback 保持，尤其无人值守配置 allow。主动取消优先，取消不借 fallback 执行。
- 不动客户端面；Work仍呈现真实工具和结果，不新增页面/按钮/卡片，因此无 prototype。详细审核 trace 通过既有 approval domain / `session.observe` 供诊断，不能声称现有 Work 已显示 attempts 明细。

### 可复用能力

本轮实际读取安装版本 `0.2.1-alpha.1` 的 package export map、公开 d.ts 与已打包实现；根 `LlmError`、`resolveRetryPolicy`、`BlockAssembler` 已以 Node import 只读核实为 function。版本与仓库 package.json 相同。

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
- refactor-581：DSH接入与进程边界；不恢复旧Python broker。其后feat-623改动sources的消息投影，本次不改那部分语义。

## 架构总览

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

`policy/recovery.ts` 隐藏错误分类、共享2次恢复/1次格式额度、预算计时、退避/取消、trace。只有 facade 构造一个并传给选中的策略。CC在单阶段边界调用run，Guardian在一次正常审核生命周期边界调用run。模块有深度：若去掉它，安全计数/错误/取消规则会在两条策略中重复漂移；不做可供任意业务使用的通用retry库。

不选：整个facade外套loop（会重做CC stage1、重复准备/授权读取，并把fastpath/fallback也套进去）；也不选把供应商policy全局改成2次（会改变主Agent，且无法表达格式子额度/Guardian预算）。legacy共享classifier使用同controller，单阶段30秒，作为兼容覆盖。

### 2. **Guardian技术失败后废弃失败分支、用同一冻结证据从full恢复；不重用失败历史。**

第一次正常尝试保留现有缓存和并发fork优化。遇到可恢复服务失败、格式失败或90秒deadline：先撤销本次generation的发布资格、cancel并dispose其handle；清空本次可用checkpoint引用，后续恢复从该动作开头冻结的parent evidence重建full reviewer。失败turn中的assistant输出、检查结果和半成品事件均不seed新尝试，只有当前动作成功完成且generation有效才commit新checkpoint。已有另一并发动作的成功checkpoint不能被失败分支覆盖或清除。

`contextRebuildRemaining=1` 属于action controller，在全部技术恢复间共享。context overflow/compaction仍可一次重建，处于当前90秒尝试内，不消耗服务恢复额度；第二次context失败终止，不得再借service retry重置context额度。context重建收紧历史的现有规则保留，完整待审动作/授权不可裁掉。

替代方案：在公开 `agent/request-error` 返回retry可保留已完成检查，但同一个turn的整体90秒deadline、非法verdict、事件半提交和context重建额度将分散到多处，难以证明重置预算且不串状态。当前选择牺牲失败分支的只读检查缓存，换取确定隔离；只读重复无业务副作用，所有model/inspection仍计入trace。不是未经清理的“外层重跑整个Guardian”。

### 3. **完整判断预算分配给新尝试，准备、退避与回收另有硬边界。**

| 事项 | 本设计值与范围 |
|---|---|
| action准备 | 15秒，冻结来源/动作/策略材料及resolve审核模型一次，包含pa.authorization、inherited、transcript/history；使用父取消信号。prepare超时为技术不可用，不是已经开始的判断超时，不消耗恢复额度、不无限重做准备。 |
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
| 有效最终deny/allow | 正常verdict，不进入错误分类；CC stage1非allow正常推进。 |
| 原生EMPTY_RESPONSE或正常完成但空白/无法解析verdict | invalid_verdict（细分empty_response/empty_text/malformed），最多一次，共用总额度；不因native默认把EMPTY_RESPONSE当transient而绕开子额度。 |
| RATE_LIMIT或可确定的429 | transient，尊重可得Retry-After；若quota/永久事实存在先排除。 |
| status=503，或SERVER且status不可得 | transient；已知非503服务器状态本unit不额外泛化重试。TRANSPORT/STREAM_CLOSED等明确结构化传输失败、provider TIMEOUT可恢复。 |
| CONTEXT_WINDOW_EXCEEDED/本地ReviewBudgetError/compaction | CC不可用；Guardian只走一次全action context重建；不能落入service retry。 |
| 未知异常/中间件或编程错误、无本地deadline的ABORTED | unavailable_unknown，不盲重试；保留facts，无message regex推断临时网络故障。 |

`BlockAssembler.finish.kind=error/aborted`读取其failure；thrown只接受真实LlmError或已校验的公共failure来源。Guardian在scoped request-error保存完整failure，turn/end仅作终态佐证，不再JSON字符串化后反向解析。context本地标记/结构化code替代当前宽泛正则；其它错误不臆测context恢复。

### 5. **补充实际可见的HTTP facts，但不依赖上游私有错误分类。**

沿用 `installLlmAttribution` 的单个dispatcher owner，新增内部 `withReviewHttpFacts(sink, iterable)`：在iterator创建/每次next/return的ALS context内安装唯一请求sink；classifier调用以及Guardian scoped `llm/stream`各自包装，不能用sessionId全局map（并发同parent易串）。transport handler捕获当次模型POST的response start status及Retry-After，全部原handler方法保持this/参数/返回值透传。

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
```

- Facade先跑既有downstream/免审检查；只有需模型时创建reviewId及controller。冻结exec的精确工具名/参数、模型、配置、message context、可信来源，不把后续模型建议当新授权。trace不持有敏感prompt副本。
- `ApprovalReviewRequest`增私有recovery，`ApprovalReviewResult`可返回决策/usage/metadata，trace由controller统一持有，失败同样可取得。策略为单个run回调提供“不含重试的一次正常判断”，不得自行另套service loop。
- CC的buildPolicy/transcript/suffix/model info准备在一次15秒prepare内完成；每次stream建新BlockAssembler（不混partial），传parent关联sessionId便于现有proxy定位。有效stage1结果不会因stage2失败丢失；stage2共享总额度。legacy只用s1。
- Guardian把trunk claim/忙闲/fork作为整个action租约，准备parent证据一次。初次能沿用committed checkpoint；恢复强制full。复用的reviewer保存可替换的`currentAttempt`引用，scoped request/error/llm监听器每次读取该引用，不闭包捕获上一个动作的controller或signal；action结束/idle时清空它，未绑定时禁止发请求。成功commit时必须满足：signal未取消、generation有效、仍持有原trunk对象/租约且配置fingerprint未失效。失败/cancel/config release不能republish旧cache。
- 原生reviewer每次model request通过`ReviewAttempt.request`记录独立request ordinal及usage；多个只读检查步骤不计额外恢复；无判定结束才进入format分类。context重建先dispose旧分支并takeContextRebuild，再在本次剩余90秒内重建，不重置正常尝试时限。
- action、attempt、request ordinal三层区分：CC正常s2也是新attempt记录但retryOrdinal不增加；Guardian多step是request记录，只有controller授予的恢复增加retryOrdinal。audit避免把“最大2次额外”误读为“总共只能2/3个model requests”。

### 回收和晚到结果

每个尝试拥有独立AbortController/timer、generation token；父exec signal保持独立。计时器abort后策略先失去提交权，再中断请求。Guardian移除abort listener、cancel、dispose，await其drain，dispose完成前绝不开始下一次恢复。CC主动关闭iterator并等待其settle，丢弃partial/verdict。

5秒内无法drain是 `cleanup_unavailable`：本action不可恢复；controller封闭、引用放入service的tracked cleanup集合，不缓存/seed/交给新调用；Guardian该parent reviewer租约quarantine，直到旧dispose真正settle才允许再次创建该parent reviewer。晚到allow和late create结果只可清理，永不能resolve旧动作allow。服务dispose继续drain tracked集合，生产runtime正常shutdown保留原生清理路径；不从这里kill共享DSH进程。测试必须验证迟返/不合作模拟的失败关闭，不能仅用Promise.race声称取消了底层工作。

### Trace与兼容

在既有approval record新增optional `recovery`，旧行无需迁移或重写，domain version/layout维持；Zod定义与读写同时接受旧行。trace上限由2次额度和Guardian90秒所界定；model request摘要最多100条，超出只累积计数/可得usage并置requestsTruncated=true，不影响执行权限。

| 层 | 必要事实 |
|---|---|
| review | reviewId、callId（原工具关联）、rules/reviewer、start/end/elapsed、terminalReason、finalRoute/fallbackOutcome、retriesUsed/formatRetriesUsed、contextRebuilds、complete |
| attempt | scope、attemptOrdinal、retryOrdinal、generation（诊断用）、开始/结束/预算、触发/最终failure category/code/status、delay与Retry-After可得性、Guardian sessionId/contextMode、outcome |
| request | 本attempt内requestOrdinal、model/provider、可得requestId/usage、结束原因；不保存完整prompt/参数或原始headers |

usage优先保留每request原生用量；partial或缺失标unknown，不补0。汇总只标`knownUsage`加`usageComplete`，不能把成功末次usage当全部成本。格式输出仅保留类别与必要脱敏原因，不记录完整响应。最终原审计行仍负责计数；详细trace附该行，fallback第二行只关联reviewId而不重复累计usage。主动取消也新增不增deny计数的取消审计；domain写入失败为不可用，不能用丢失审计为理由自动allow。

trace在进程内收集；facade先计算拟采用的原route/fallback outcome，将该终态和完整trace持久化，再返回决策；人工待答记为interactive_pending而非伪造最终allowed，后续人答沿用既有human audit关联reviewId。终态由session.observe返回；不新增进行中journal、重启恢复/replay或新的UI。进程突死时不保证完整终态trace；可用原生Work/代理request事实定位，不能伪造未落盘尝试。Q报告注明此能力边界。

## 契约层增量 (delta-spec)

- Gateway：唯一target `docs/specs/gateway/agent-capabilities.md`，对应 [specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md)。新增失败恢复Requirement；完整替换含模糊“已有重试”的既有Requirement，保留其它Scenario语义；不改IM、全局Agent或顶层SPEC。

## 风险与回退

- 完整恢复可把一次判断拉长到几分钟且增加费用，这是已确认取舍；无并发预判或盲目模型切换。执行侧端到端等待需至少覆盖360秒审核+既有人工等待，不能沿用测试120秒poll把正常长恢复当失败。
- transport observer是进程级hook但有request-local sink、仅审核模型POST生效；必须回归现有主/子session归因和并发隔离。不可见headers明确unknown，不扩大到工具网络。
- Guardian full恢复会重复只读调查、失去失败分支缓存；公开Agent能力足够，但implementation/native fixture须证明create/dispose和scoped llm listener顺序；这些未验证实现不当作已完成能力。
- 不合作provider/FS teardown无法靠应用实现绝对物理消失；5秒quarantine保证无late授权/无继续重试，不以无限等待守住表面cleanup。发生真实cleanup不可用时记录具体资源并阻断，不自动重启生产。
- 回退为撤回本unit产品commit（保留历史audit可读性、未知optional字段无害），恢复原无故障恢复行为；不修改owner配置。merge/部署仍需人类指令。

## Runbook for Reviewer

详见 [reviewer-runbook.md](reviewer-runbook.md)：双策略真实插件旅程、API入口、故障矩阵、计时和清理。只改integration库、没有新常驻服务；实际验收依赖既有隔离IM+Node/DSH，不碰生产。fixture为测试进程而非产品服务。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 本次隔离IM + Node管理的DSH | `./scripts/e2e-down.sh --wt "${WT_ROOT:?}"` | `./scripts/e2e-up.sh --wt "${WT_ROOT:?}" --main-config "${E2E_CFG:?}"` | `source "$WT_ROOT/.e2e-ports.env"; curl -fsS "$IM_URL/openapi.json" >/dev/null`，再通过登录后的nodes检查本次node online |
| 本地LLM代理（仓库外依赖，不由本unit管理） | 不停止 | 不重启，沿用开发入口 | `GET http://127.0.0.1:4000/health` |

**Review驱动方式**：端到端真栈，不改客户端面；允许复用客户端同一IM HTTP/WS接口代驱动（不可用RuntimeClient直接submit代替产品旅程）。Native RuntimeClient fixtures是worker工程证据，不替代Q真IM旅程。

**验收前置与本轮实际检查**：隔离脚本、默认无secret config、node_modules存在；LLM_PROXY health返回200。当前P workspace没有`.venv`，系统Python3.9.6且缺yaml/httpx/pytest，不满足仓库≥3.11要求；E/Q需提供自己的≥3.11解释器并按local-development创建或复用隔离dev环境（runbook给安装命令），不是借生产主仓环境。health不证明指定模型可用；Q执行前通过专用E2E目录的smoke确认模型/窗口/low支持，不读或复制生产凭据。本轮未启动栈、未花真实模型请求、未宣称验收pass。真实provider不可用时可继续确定性矩阵，但对应真实旅程必须inconclusive并报E，不用stub冒充。

## Milestones

默认单M1，CC、Guardian与共享恢复是一个安全闭环，不按策略或层机械拆分。设计期仅放 `.gitkeep`，不预填tasks/progress。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-review-recovery | 同一动作内完整预算的有界审核恢复 | 无 | 单M1 | integration policy recovery/transport、types/audit、classifier/cc/codex、llm-attribution/index；直接相关Vitest/HTTP fixture与IM关键路径；本unit设计/delta/验收证据及最终canonical归并 | [reviewer] 首文档17场景逐项覆盖，CC/Codex真实隔离全局插件创建→安装→两次调用有Work/实际副作用证据，原权限/最终deny/各模式fallback不变；[reviewer] 真IM受控故障矩阵显示共享2次/格式1次、完整预算、Retry-After、取消及晚到零执行，真实服务可用性与fixture证据分开；[worker] recovery接口fake-clock组合矩阵、完整公开failure/header事实/native装配与并发归因、Guardiandispose/full恢复/全action rebuild≤1/quarantine、legacy兼容和optional audit旧行读写测试通过；[worker] 最窄相关Vitest后扩大typecheck/build、runtime dependency contract、docs-check及当前CI命令，独立门禁和脱敏证据齐全；[worker] runbook的受控HTTP fixture与可复跑真IM驱动进入长期测试，不改生产或增加正式运行配置。 |
