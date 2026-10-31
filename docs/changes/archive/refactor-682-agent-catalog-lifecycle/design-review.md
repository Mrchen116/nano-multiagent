# refactor-682 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/catalog_design_review`（独立 reviewer；未参与设计编写）
- review_mode: `full`
- mode_reason: 首次 Gate 2；核对完整后端设计、真实产品组装链、delta、迁移及 M1；另执行 agent-context-review Mode A。
- started_at: `2026-10-31T15:09:12+08:00`
- completed_at: `2026-10-31T15:12:00+08:00`
- duration: 约 3 分钟
- source_baseline: main `6d602fdae08464fbc5cc834fc403054581521c96` 加本 unit 未提交设计。现有 `apps/node/src/main.ts` / `packages/dsh-integration/src/index.ts` 日志补丁仅作为可见源文件读取，未修改；独立实施 worktree 的起点 `4cea0166d` 及实施前整合 main 的安排已核对文档。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

主方案方向可行，依赖边界和用户明确要求的纯后端范围得到保留。但异常父进程退出后的存活 worker 归属，以及显式失效和在途刷新之间的 fence 仍未闭合；这两项直接影响本次消除卡死、残留资源和过期目录的目标，须先收口。

### Coverage 与证据

1. **需求、范围与现状。** 读取 motivation、design、两份 delta 和 deployment-prompt。`control-routes.ts:305-342` 确认 settings 在 `ops.serialized` 内等待 recover/catalog；`node-rpc.ts:26-44` 只移除 pending 并报超时；`channels/src/index.ts:142,296-297` 以 serverRequests 保留响应关联，但 handler 失败并不清理；`dsh-integration/src/index.ts:367-405` 确认临时 preset/Session 及逐层清理，原来未删除持久 Session。未将报告中未证实的内部锁或长期 RSS 泄漏当成事实。用户纠正已落实：不新增 UI、文案、刷新交互或只读规则，不要求前端原型。
2. **真实组装与职责。** 从 `apps/node/src/main.ts:103-155,212-261,426` 追踪 RuntimePartitions、provider、catalog/preview、prepare；`runtime-partitions.ts:250-259` 和 `index.ts:616-632,348` 证明 prepare、apply 隐式 prepare 及冷初始化 pendingConfigurations 都会走同一 preview。设计在 preview 原语处反向调用 inspector，可覆盖这些隐藏调用者；双向 `RpcPeer.receive` 分开派发请求与响应，不会因反向请求必然死锁。保持 reservation、usage、apply 在原聊天 runtime，临时目录构建归 integration；Node 不直接使用 DSH API，Channels 只管关联，IM 管权限与展示。复用现有官方 RuntimeClient/prepareProfile 比新增目录引擎或 Session 删除兼容层更适当；独立可终止进程对任意插件挂起有实际必要性。
3. **超时、取消与预算。** 9/8/7 秒分层预算、最终进程组终止、退出后删 home、逐项 finally、最多两个 worker、waiter 分离取消和短退避，方向足以解决只超时等待而底层继续运行的问题。持久配置 mutation 不被错误解释成“超时等于未执行”。shutdown/update 调用 close 已明确；异常 Node 退出仍有 R1-W1。现有 `RuntimeClient` 启动 detached 子进程，不能把普通 close 或 Gateway 单实例锁视作子进程死亡保证。
4. **缓存与权限。** key 包含 owner/Agent/节点、绑定、连接、workspace、profile version，命中保留 captured_at；保存重新检查，且 settings 等待后重鉴权，符合 current `agent-settings.ts:23-46` 和原 settings fencing。解除 GET 写锁、复用 ConfigOperations 恢复 owner 不引入第二写协调器。显式模型/插件变化的 in-flight invalidation 尚缺 R1-W2，不能仅依赖现有 profile/连接 fence。
5. **Agent Context — Mode A。** Surface 为工具/Skill 候选、配置校验与 native assembled prompt；不改变模型输入文字，但改变来源加载和缓存时序。Node `configuration.ts:92-103` 已将共享/workspace 插件路径和有序 Skill roots 显式装入可信配置；`agent-config.ts:94-108,124-141` 使用这些路径，`capabilities.ts:93-104` 按 provider 顺序去重，因此新 DSH home 不必复制聊天数据即可保留主要来源。普通/global/PA、固定工具、同名覆盖和 Feature/Skill 选择必须继续由原 native 组装产生。M1 要求 catalog 对 session.capabilities、prompt preview 对真实 assembly 的保真检查是合适退出标准；已有 `personal-security.test.ts:62-116` 提供普通 Global/PA native 场景可复用。当前是设计审查，未执行新 inspector 或真实模型，不能声称已证明语义等价。缓存 R1-W2 间接影响消费者选择和预览；不推断会突破实际执行白名单。
6. **delta 与 milestone。** IM delta 锚定 canonical 同名 Requirement；逐项核对其原有 11 个 Scenario 全部保留，新加刷新/恢复场景不改前端语义。Gateway 新增临时资源不变量归属正确。单 M1 将缓存、取消、进程回收一并交付有因果依据；30+ 并发、失败后恢复、100 次实际刷新、30 分钟/1000 请求 soak、真 native 保真和跨层关联测试都已安排。无需为了层次机械拆分 milestone。应将两个 finding 的验证补入该 M1。
7. **迁移与验收边界。** deployment-prompt 仅适用于另外授权部署已验证版本；先停旧 writer，严格名称/header/binding 筛选并归档，保护其他 Session，不永久删除；清单支持重复执行和中断恢复。功能/失败/幂等验证在隔离副本，生产仅有限只读核对，不把部署当补验收。正常 inspector orphan 回收与旧 preview 一次性迁移明确分离。Runbook 用同一 HTTP→IM→Node→DSH 真栈、不改前端，符合本次范围。

### 历史问题闭环

首次审查，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — Node 异常退出后仍存活的 inspector worker 没有回收 owner

- **Severity / evidence:** WARNING / CONFIRMED（设计缺口及 detached 行为可确认；未运行故障注入，不宣称已经发生生产泄漏）。
- **位置：** `design.md:53-55,73-75`，M1 退出标准 `design.md:115`。
- **证据：** `packages/dsh-integration/src/client.ts:49-54` 使用 `detached: process.platform !== 'win32'`；`RpcPeer` stdin 关闭只释放关联，`index.ts` 未提供父进程丢失时强制退出机制。`apps/node/src/lifecycle.ts:164-188` 的 Gateway lock/state 保护 Node 单实例，并不终止历史 inspector 进程。设计只规定正常 close/timeout 杀 worker 和 initialize 清理“已确认无活 worker”的 orphan。
- **失败场景与后果：** Node 被 SIGKILL 或崩溃，运行中的 worker/plugin 持有定时器或卡住；父进程里的 deadline/kill 定时器一并消失。新 Node 发现目录仍有活 worker，按当前文字不能删也没有终止它的 owner；新两-worker预算不包含该历史进程，反复崩溃可留下多批 worker 和目录。与“Node 重启后遗留临时状态有回收路径”不符。
- **修改建议：** 明确选定一条异常父进程死亡恢复机制，例如 inspector-only worker 的父链路失联看门狗加独立硬截止，或持久化可校验的 worker 身份/进程组及启动标识，由新 inspector 接管、终止属于本节点旧实例的存活 worker，确认退出再删目录。不要仅凭 PID 或目录名杀进程，也无需扩大到聊天 runtime。M1 增加“worker 挂起时强杀 Node→启动新 Node→历史 worker/目录回零→新请求成功”隔离场景，并说明身份无法确认时的有限保留/报告行为。

#### R1-W2 — 模型/插件失效缺少在途结果 generation fence

- **Severity / evidence:** WARNING / CONFIRMED（接口/时序设计缺口；实际错误缓存为该遗漏允许的实现结果，并未声称实现已存在）。
- **位置：** `design.md:47,57-59,69`。
- **Context Surface / expected：** 候选目录及由它产生的工具/Skill 选择与 prompt 预览；成功变更模型服务或插件后，应使用变更后的确认目录，旧结果不应重新赋予 `current/ready`。
- **证据：** 当前拟定 key 和 completion fence 仅列 profile、owner/绑定、连接、workspace 等身份。模型服务和插件变化通过 `invalidateNode(nodeId)` 清除缓存，但通常不改变这些 Agent key；源码 `control-routes.ts:465-475` 与 `main.ts:265-271` 的插件操作也不产生 Agent profile revision。文档没有规定 invalidate 对已在途 Promise、已有 waiter、随后写 snapshot 的效果。
- **失败场景与后果：** 刷新 A 在插件变更前已取得旧目录、尚未交付；插件操作成功并 invalidate；A 随后完成，身份/profile/连接 fence 全部仍通过。若只删 Map entry，已有 waiter 仍可把旧值标成 current 并写 snapshot；若完成回调重填缓存，旧目录还可继续有效五分钟。模型变更同理。仅保证缓存表不复活也不足以阻止原 waiter 返回旧 live 值。实际执行重新校验可避免扩大工具权限，但设置展示、预览与保存的一致性会回归。
- **修改建议：** 定义节点候选 generation 或等价的刷新身份 fence：invalidate 时推进 generation/作废旧 refresh；完成结果与每个 route 的 live/snapshot 写入都必须检查该代次，过时代次只能安全失败或加入新刷新，不可再作为 current。明确相同请求合并不会让变更后的请求加入旧 generation；覆盖模型/插件成功变更和在途刷新交错的确定性测试。此修改是后端一致性，不需要新 API 字段或 UI。

### Recommendations

- **R1-R1（可选）：** 在 native 保真 fixture 中显式放入共享插件、workspace 同名覆盖、带 Feature 的工具和被禁用 Skill；catalog 本来就是候选全集，不能直接要求它与经过白名单过滤的 session.capabilities 全量相等。应比较对应配置投影后的可调用集合及 prompt/Skill 来源顺序，避免测试把预期差异误当回归。设计的整体保真目标已正确，此项只是让证据更清楚。
- **R1-R2（可选）：** 原生 fixture 多直接构造 `RuntimeClient`，例如 `personal-security.test.ts:76-80` 使用额外 `prepareProfile` patch 注入测试插件。普通 runtime 改为 reverse RPC 后，M1 应显式安装测试侧 inspector handler，并决定该 fixture 的额外可信 patch 如何传入检查进程；不能以“没有 Node”跳过全部既有 native coverage。产品 Node 的 `main.ts:155` 当前每次启动生成标准 profile，用户共享/workspace 扩展另由可信 config 提供，因此这些测试专属 patch 不足以证明生产方案遗漏了一个可持久维护的 root profile 来源；无需据此自动引入整个持久 home 的复制机制。

### Author Resolutions

- R1-W1 accepted：在 design 关键决策 3 补齐 worker 随机标识/lease/CLI 身份、父链路关闭退出、Node 重启后接管活 orphan、确认退出再删，以及无法确认时保留并阻止预算绕过。M1 增加 SIGKILL 宿主后恢复及 PID 不符保护测试。没有扩大到用户聊天进程。
- R1-W2 accepted：在 IM CatalogReads 契约补齐节点 generation、abort/旧 waiter 失效、load 完成和 route 写回双重 fence；模型异步 setup 和插件变更的触发点明确，M1 增加确定性竞态测试。
- R1-R1 accepted：保真比较先投影候选，再比较实际可调用集合及来源，不要求候选全集与 session 过滤结果全等。
- R1-R2 accepted：RuntimeClient 默认提供反向 handler，Node 共享 pool；native fixture 显式转交可信测试 patch，worker 禁用递归。不会复制整个持久 home。

## Round 2

### Metadata

- reviewer_target: `/root/catalog_design_review`（同一独立 reviewer）
- review_mode: `delta`
- mode_reason: 两项旧问题的局部解决方案新增 lease/CLI 身份接管、IM generation 和 RuntimeClient 默认反向 handler；需检查这些有界设计变化的跨层影响，范围超出纯文字 closure，但未改变需求、总体架构、客户端或 milestone 分工。
- started_at: `2026-10-31T15:14:53+08:00`
- completed_at: `2026-10-31T15:16:00+08:00`
- duration: 约 1 分钟
- source_baseline: main `6d602fdae08464fbc5cc834fc403054581521c96`；仅 design 修订及 R1 Author Resolutions，新实现尚未产生。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。** R1-W1 closed；R1-W2 still-open，剩余问题收窄到 IM generation 与 Node inspector 合并之间的交界。

### Coverage 与证据

- retained_from: Round 1。现状、后端范围、canonical delta 的 11 个旧 Scenario、迁移边界、原生配置/Skill 来源和单 M1 分工未改变，沿用 R1 的实际源文件证据。不重做无变化 UI 或迁移审查。
- 本轮核查 `design.md:53,55-61,71,75,85,117` 全部修订。独立读取已安装的官方 DSH `lib/bin.js:59-74,105-113`，确认 launcher 使用 allowUnknownOption/passThroughOptions 并将 app args 交给 profile，专属随机 CLI 参数不需要修改上游 CLI。原 `RuntimeClient` detached 和 Gateway 单实例事实沿用 R1。
- 原生 fixture 反向调用接线、worker 显式禁用递归、可信测试 patch 显式传递，以及候选投影后再与实际 callable 集合比较，分别回应 R1-R2/R1-R1。这些是测试/组装 seam 的收口，不需要扩大生产 home 复制或前端 scope。
- Agent Context Mode A：增加的 generation 能阻止旧 IM waiter 复活 current，但 Node 层相同候选共享仍可能把旧来源包装成新读取，见下项；真实执行白名单不因此扩大。未运行新 worker、故障或模型，结论仅限设计。

### 历史问题闭环

#### R1-W1 — closed

- Author Resolution：lease/随机 inspection_id/CLI、EOF 退出、新 Node 接管活 orphan，未知身份保留并拒绝新构建。
- 本轮证据：`design.md:57` 明确先校验本节点 root、完整随机身份与 lease/目录，再终止进程组并确认退出后删除；Node 仍在单实例锁内。事件循环挂起不能靠 EOF 处理的限制也明确，交给后续 Node 接管。未知身份不杀其他进程、也不绕开并发预算。M1 `design.md:117` 加入宿主 SIGKILL 后接管和 PID 身份不符验证。
- 结论：原来“存活 orphan 没有 owner”的设计缺口已关闭；剩余正确性由规定的隔离故障测试验证，不在设计审查中虚构已通过。

#### R1-W2 — still-open（收窄）

- Author Resolution：IM invalidate 推进 generation、abort 旧刷新、使旧 waiter 失效，load 和 route 最终双重 fence；补模型/插件触发点和竞态测试。
- 已关闭部分：`design.md:71` 明确禁止旧 IM 代次重新入库/返回 live，解决 R1 所述旧 Promise 完成后复活的问题。
- **剩余位置：** `design.md:59` 的 Node inspector 指纹，`design.md:71` IM generation，以及 `design.md:75` inspect 输入。
- **Severity / evidence：** WARNING / CONFIRMED（两层生命周期契约缺少关联；不是已运行缺陷）。
- **具体机制：** 插件文件/启用状态变更通常不改变 config 内的 workspace/插件 manifest 路径，也不改变 providers 或 method。Node 因此仍可将新请求合并到变更前的 worker。IM abort 旧 waiter 不保证 worker 已终止：设计本身允许其他 waiter 继续持有相同检查，例如 ordinary runtime 的 reverse prepare。新 IM generation 此时读到的“新请求”可以取得该旧 worker 的结果，并通过自身新的 entry/generation fence。相同风险也存在取消尚未完成、旧 worker 尚可加入时。
- **后果：** 旧工具/Skill 目录仍可能被新一代 IM 请求标为 current；前述 route fence 不能判断它实际由旧来源构建。保存校验和真实工具限制仍在，未据此推断授权绕过。
- **所需收口：** 将同代次合并约束延伸到实际构建 owner：例如 Node 本地候选 generation 随模型/插件实际变化推进，并纳入 inspector 合并身份/禁止新 waiter 加入旧 worker；或用等价策略保证变化后的检查不会复用变化前工作。必须覆盖所有入口，包括反向 prepare 和 Agent 自身 plugin_manager；不要求改变公开 UI/API，也不要求取消已经存在的持久 mutation。M1 明确加入“旧 worker 被另一个 waiter 保持→插件变化→新 IM generation 请求→不复用旧构建”的跨层交错验证。

### Issues

本轮无新增 issue ID；唯一存活 WARNING 为上述 R1-W2 的跨层合并缺口。

### Recommendations

无新增建议。R1-R1、R1-R2 已被设计采纳。

### Author Resolutions

- R1-W2 accepted (R2): Generation now fences Node single-flight and completion too. Model commits/plugin catalog changes invalidate and abort Node inspections before notifying IM, including reverse prepare waiters. Design decision 4 and IM interface specify the cross-layer race test. Old cleanup does not authorize new joins.

## Round 3

### Metadata

- reviewer_target: `/root/catalog_design_review`（同一独立 reviewer）
- review_mode: `closure`
- mode_reason: 仅核实 R1-W2 在 R2 收窄后的跨层 generation 缺口；本次改动把既定 fence 延伸到实际检查 owner，未改变需求、核心边界、外部接口或 milestone 分工。
- started_at: `2026-10-31T15:17:18+08:00`
- completed_at: `2026-10-31T15:17:35+08:00`
- duration: 小于 1 分钟
- source_baseline: main `6d602fdae08464fbc5cc834fc403054581521c96`；设计修订，尚无实现。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。** Gate 2 设计问题已闭合；不代表实现、资源故障测试或 native 保真验收已通过。

### Coverage 与证据

- retained_from: Round 1、Round 2。沿用完整需求/现状/职责、用户后端范围、delta、迁移、native 来源和 M1 覆盖；R2 已关闭的 orphan 接管及采纳的 fixture/候选投影澄清均未改变。
- 本轮只核查 `design.md` 关键决策 4（Node 合并身份）及 IM CatalogReads 接口段（Node invalidate、触发时点、所有 waiter 的 completion fence、跨层测试）。无需重复无变化的源文件扫描或扩大验证范围。
- Agent Context Mode A 的剩余影响仅为旧候选失效传播：新设计同时在 IM 展示端和 Node 实际构建端约束代次，保留原来源优先级、固定工具及实际执行白名单，未增加 UI/模型文本或授权变化。

### 历史问题闭环

#### R1-W2 — closed

- Author Resolution（R2 后）：Node generation 纳入 single-flight 和 completion；模型提交/插件 catalog 变化先失效 Node 检查，再通知 IM；覆盖反向 prepare waiter；旧 cleanup 不允许新加入。
- 本轮证据：关键决策 4 已把“本地 catalog generation”加入稳定合并指纹。IM CatalogReads 段明确实际模型配置提交、runtime workspace/plugin catalog change 和显式插件 mutation 触发 inspector.invalidate，作废并 abort 旧代所有在途检查，先完成 Node 失效边界再通知 IM；包括反向 prepare 的每个结果返回前校验代次；旧 worker 保有 waiter 或仍在 cleanup 均不能接受新请求。
- 由此 R2 的具体路径被切断：变更后的 IM 请求进入新的 Node generation，不能从变更前 worker 获得成功结果；旧检查即便迟到，也无法通过 Node completion 和 IM route 两层 fence。
- 验证安排明确固定旧 worker、推进两层代次、发起新 settings、释放旧结果，并断言不合并和不写 live/snapshot，属于既有 M1“模型/插件变更与在途结果交错”退出标准的具体化。持久 mutation 本身仍遵循原不确定性/恢复契约，取消的是其过期临时检查。

#### R1-W1 — closed（retained_from: Round 2）

异常父进程死亡后的可验证身份接管、EOF 退出、未知身份保留和预算保护未改动，无重开依据。

### Issues

无存活 CRITICAL / WARNING。

### Recommendations

无新增建议。停止设计审查循环，按既定 M1 实施并验证。
