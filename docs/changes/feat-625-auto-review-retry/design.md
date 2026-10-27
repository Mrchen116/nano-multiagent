# feat-625: Auto 审核内有界恢复 — 技术方案

> 对齐: [spec.md](spec.md)。基线 `5454f3140f9c92532c690db8dec80b9f77080384`；仅指定 checkout `repository`，分支 `codex/feat-625-ab-e2e`。独立 R1 已 Approved（0 CRITICAL / 0 WARNING），author 已核实并闭环；见 [design-review.md](design-review.md)。这不代表实现或产品验收通过。

## Changelog

## 现状分析

### 涉及范围

以下为本次直接读取的当前源码，不是 issue 旧实验的复用结论。

| 位置 | 已核对的现状与变化落点 |
|---|---|
| `packages/dsh-integration/src/policy/approval.ts:99-145` | 原生 `tools/pre-execute` 中先执行 downstream 检查；选择 CC/Codex/classify，异常立即记 classifier_unavailable 并 escalate。该处是一次工具调用的单一恢复 owner，不能重跑工具或 downstream。 |
| `policy/classifier.ts:9-39` | CC 两阶段，阶段 1 30 秒、阶段 2 60 秒；第一阶段 allow 直接结束，否则正常进入第二阶段；DSH 仅阶段 1。stream 的 finish.error/aborted 被 JSON.stringify 后抛出，空判定为普通 Error；usage 只返回末阶段。 |
| `policy/cc.ts:11-16` | CC 工作区免审先于 classify，必须保留；免审不是模型 attempt。 |
| `policy/codex.ts:39-122,126-156` | 90 秒覆盖 preparation、只读工具和一次 context rebuild；每父 trunk 支持 full/delta/fork，成功才发布 checkpoint；失败 discard。request-error prepend 不 next，返回 undefined，已阻断原生请求重试，但 stringify 丢失 failure 结构。 |
| `policy/types.ts`、`policy/audit.ts:4-19` | 审核 request/result 小接口；持久域 nano_approval，审计 schema 目前 metadata 只有 sessionId/contextMode/risk/authorization，扩展必须改 schema，否则新字段不可靠。 |
| `src/index.ts:370-375` | `session.observe` 原样返回 `approval.entries(sessionId)` 为 approvals；这是已有运营/测试消费面，不是假设已有 Work UI attempt 展示。 |
| `docs/specs/gateway/agent-capabilities.md:508-579` | current 保留策略选择、免审、来源、预算与分流；“已有重试后仍失败”的措辞未证明本次恢复存在，真实实现仍无本 unit 所定义的服务恢复。 |

目标文件范围：以上 policy 文件、新增局部 `policy/retry.ts`（命名可在实现内微调）、专用 retry 测试；不新增通用 Agent loop。现有 `approval.test.ts` 继续作为集成 seam，专用风险矩阵放独立测试，避免机械扩大已有文件。

### 既有约束

只有 dsh-integration 依赖 DSH；不私有 import、fork、patch；不更改运行时或 4000 环境；不读旧 feat625 文档/历史/聊天/测试产物。用户要求 Full；默认单 M1，无 UI 改动、不生成 prototype。current-workflow 是角色规则来源；该快照缺 `docs/specs/CONTRIBUTING.md`，使用指定 baseline 的同文件；baseline 无 agent-context-engineering 文档，使用 current-workflow 版本。

### 可复用能力

已从 checkout 安装依赖的 package.json exports 及公开声明核实版本均为 `0.2.1-alpha.1`：

- **用** `@deepseek-ai/dsh-llm` 根 export：`LlmError.failure`、`LlmFailure`（code/message/status/providerRetryAfterMs/requestId）、`HarnessError.code`、`EMPTY_RESPONSE_CODE`、`resolveRetryPolicy`、`ResolvedRetryPolicy`、`BlockAssembler`。依据 `lib/types/index.d.ts:16-25,48-72`、`types.d.ts:26-44`、`retry-policy.d.ts`。不要把声明文件路径当成可 import 的私有子路径。
- **用** 公共结构化 finish.failure 与 Codex `agent/request-error` 的 failure；不解析 stringify message 作为控制流。后者公开契约见 `@deepseek-ai/dsh-agent/lib/types/runtime-types.d.ts:334-356`，undefined 且不调用 next 保持 terminal，可在 reviewer scope 保持现有拦截而不影响主 Agent。
- **用但限制** `resolveRetryPolicy` 校验/补全局部 normal policy：明确 maxRetries=2，白名单 RATE_LIMIT/SERVER/TRANSPORT/TIMEOUT；EMPTY_RESPONSE 单独受 invalid 上限约束。DSH 缺省为 5，不能直接继承；provider mode=always 也不能突破产品上限。此 unit 固定局部安全策略，不修改 provider 配置。
- **不用作独立 executor** `@deepseek-ai/dsh-llm-retry`：根公开声明只有 apply/配置/事件类型，无 standalone 执行 helper；它接 Agent request-error，不能覆盖手写 stream，且 default/always 与产品上限不一致。不复制或 import 其私有实现。
- **保留** CC 两阶段、Codex 原生 Agent/只读检查与一次 context rebuild、原生工具执行及 cancellation、现有 durable domain 和 escalation。只补很小的审核恢复编排与失败归一化。

### 相关历史

按授权未读取 change 历史、旧 feat625 产物或历史测试输出。只将 issue #361 作为需求，不将其 63f04f 基线或旧事故计数当本基线验证。

## 架构总览

Before：一次 pre-execute → 策略 → 首个技术失败 → unavailable/escalate。

After：一次 pre-execute → 固定动作与授权证据 → 审核恢复控制器 → 最多三个完整策略 attempts → 一次最终审计/路由 → 原生工具最多执行一次。

控制器只调用策略，不重入 pre-execute、工具、next 或主 Agent。CC/Codex 独立服务与语义不合并；legacy DSH classify 同享外层限制。免审、Auto 关闭及 upstream deny 保持原路径。

## 关键决策

**1. 重试单位为完整策略审核，两个额外 attempts 是全故障类别共享预算。**

每次工具审核从 attempt=1 开始；extraUsed 最大 2，invalidRecoveryUsed 最大 1。服务、传输、timeout 共同消费 extraUsed；空白/非法还消费 invalidRecoveryUsed。额度只在确实开始下一次 attempt 前消耗，退避取消不伪造已执行 attempt。最终有效 deny/allow 都终止恢复。CC 阶段 1 的 deny 仍是正常进入阶段 2 的信号，不是最终拒绝重试。Codex 一次 context rebuild 是原有证据恢复，不增加外层额度，不将 service/invalid 错误误识别成 context rebuild。

拒绝按阶段重置计数（会倍增额度）及直接重放主 Agent 工具（可能重复副作用）。一个完整策略 attempt 可以有两个 CC stages 或多个 Guardian 只读模型步骤；审计必须分开 attempt、stage、context rebuild、模型 request，不宣称总模型 HTTP 请求最多三个。

**2. 每个完整 attempt 具有新的完整 90 秒上限，不共享初次 deadline。**

该 90 秒从策略准备开始计时，覆盖该 attempt 的模型解析、策略材料、stream、Guardian 检查与已有 rebuild。CC 原有 30/60 秒阶段子上限仍在，不变成每阶段 90 秒；DSH 一阶段也保留子上限。重试从新预算起步，前次耗时不扣减下次。各 attempt 收敛后才开始下一次，等待退避不消耗下一 attempt 的 90 秒。

选用无抖动有界退避：第一次 500ms、第二次 1000ms；有正有限 providerRetryAfterMs 时使用 max(local, provider hint)，最多 10 秒。invalid 恢复使用相同 local 退避。最大主动审核预算 270 秒 + 最多 20 秒退避 = 290 秒，不含记录持久化和已取消资源回收的调度开销；不得以统一 90 秒总截止裁掉后两次。确定性测试验证时钟，不等真实 270 秒。

**3. 结构化分类优先，未知错误失败关闭。**

| 归因 | 是否可恢复 | 处理 |
|---|---|---|
| service：RATE_LIMIT / SERVER（含规范化 429/503） | 共享额度内 | 保留 status、requestId、providerRetryAfterMs |
| transport：TRANSPORT | 共享额度内 | 不通过字符串包含 503/fetch 等猜测 |
| timeout：本 attempt/CC阶段 deadline 或结构化 TIMEOUT | 共享额度内 | 必须区分 parent abort；上一次确已结束后才能再试 |
| invalid：EMPTY_RESPONSE、空白、无法解析有效判定 | 最多一次且共享额度内 | 不算服务503，不添“请允许”的纠正 prompt |
| auth/config：AUTH、MISSING_CREDENTIAL、INVALID_CREDENTIAL、NO_ADAPTER、无模型窗口/非法配置等 | 否 | 即使携带看似可恢复 status 也不覆盖永久原因 |
| quota/context/unknown | 否 | Codex 已有 context rebuild 在内层处理；最终仍失败不由外层泛化重试 |
| parent cancel | 否 | cancel 胜过 timeout/late success；不 escalate |
| 有效最终 deny | 否 | 仅正常 denial 路由与计数 |

Thrown LlmError 与终端 finish failure 使用同一结构。非 DSH 的异常只有可信的明确结构化 transport/timeout 分类可进入白名单；普通 Error 默认 unknown。错误文本只作截断且脱敏后的诊断，不作为授权证据或控制代码。

**4. 取消是执行边界，不只是 signal 参数。**

父 exec.signal 与每 attempt 的可清理 timer/controller 合成；所有准备及 stream 都必须可观察 abort。等待使用 abort-aware timer；启动 attempt、每次 await 结束、提交 checkpoint、审计后返回 allow 前再次检查父取消。active stream 主动结束 iterator/abort，Codex cancel 后 dispose。

对不合作的 Promise/iterator，不仅传 signal：外层 abort race 有界返回，迟到 rejection 被消费，禁止迟到 verdict/checkpoint 发布。未确认旧调用终止时**不启动另一个 attempt**，该调用技术不可用（父取消则 cancel），并隔离旧上下文直至 cleanup；不能用并行重试满足次数。Guardian 在失败/超时后 discard，不得把失败 reviewer 放回 trunk；清除/隔离缓存槽与 busy ownership 时必须保持旧完成者不能覆盖新 trunk。resource cleanup 不得让取消无限等待；未终止资源的诊断单独记录，不能声称已物理终止供应商远端计算。合规 adapter honor signal 时才能兑现中断活动请求，测试必须证明本地无下一请求/执行/缓存提交。

**5. 耗尽不改变权限路由。**

控制器不自行 allow。统一记录 classifier_unavailable/no_verdict 后，沿 approval.ts 的原 interactive ask、global/subagent return_to_agent、scheduled unattendedFallback。保留已有显式 unattendedFallback=allow（它不是模型 allow）；工具零执行的耗尽测试应明确 fallback=deny 或 return_to_agent。取消不走 fallback、不新增审批。技术失败不累计 classifier_block，真正 final deny 仅累计一次。

## 接口与数据流

- 扩充内部 ApprovalReviewRequest：显式 attemptSignal（或等价的不可变 signal 传递对象）和 attempt collector；不得可变覆写共享 exec.signal。reviewer/provider/model、动作、参数和来源证据在一次审核内固定。
- 小型恢复 helper 接受 `(runAttempt, parentSignal, timing hooks)`，返回 final result + attempt records 或携带同样 records 的 typed failure。clock/sleep 注入只用于确定性测试，不暴露用户调参接口。
- 策略返回现有 decision/source/metadata；失败用内部 typed error 携带 category、原始 LlmFailure、可得 usage 和子请求记录。classifier 在成功/失败/abort 均收集 assembly.usage，stage1+stage2 不覆盖；Codex 在 discard 前从已产生 events 提取各模型步骤用量。
- 一次 attempt 不重读新的 owner 消息来扩大授权。CC 首次组装后的 policy/transcript 可复用；Codex 基于进入审核时的证据快照重建，失败的 assistant message/inspection 输出不得污染已提交 checkpoint。只读现场检查可重新执行，但不转成新授权；已有缺失证据标记不删除。取消/失败的缓存不提交。
- 正常完成或最终失败后，以同一 callId 写一条最终自动审核记录，其中嵌套所有已执行 attempts；与另一次工具 callId 分开。已有 human/fallback route 记录可继续独立存在，不被计为新增 attempt。

### 审计及消费面

在 audit.ts 的 zod schema 和 types.ts 同步增加可选 retry 对象，旧记录无需迁移。包含 reviewId（一次审核唯一 ID）、attempts 列表、extraUsed、invalidRecoveryUsed、finalCategory、totalElapsedMs。每条 attempt 含 ordinal、start/end/elapsed、outcome、category、structured failure（仅可安全保留字段）、delayAfterMs、reviewer/provider/model、可得 usage、stage/request/contextMode/sessionId；多步骤信息可为 children 列表。usage 缺失用 absent/unknown，禁止填0伪装精确统计；避免末阶段覆盖或重复汇总同一 token 用量。

取消也写最终 cancel 记录及已发生 attempts，不增加拒绝计数，不为了 audit I/O 延迟取消执行边界。记录失败按既有存储错误处理，不放行工具。时间到但底层未停止须明确未确认清理，late completion 不能改写最终结果。

`session.observe` 的 approvals 现有通路应能 round-trip 新可选字段；添加持久域 reopen + observe 返回测试。Work 仍展示真实工具调用，不增加“模型 retry = tool call”事件。**本 unit 不承诺 Work 新增 retries UI**：运营者通过现有 session.observe 读取审批审计，产品 reviewer 将该返回作为可检查证据与 Work 同一 session/callId 关联。原始本地 durable domain 只能作为补充证据，不能宣称可见 UI。若 executor 无法通过现有授权诊断消费者取得 observe，须落实最小只读诊断接入并重新审查该增量，不能私有读取数据库冒充用户入口。

### Agent Context 消费链

Consumers：CC classifier、Guardian reviewer、收到最终工具结果的主 Agent。Before：临时故障立即形成不可用工具结果，主 Agent 可能重发。After：中间故障只留宿主审核审计，主 Agent 只收到最终工具结果/取消，不把 retry 事件作为 owner 消息。最终 unavailable 仍明确技术失败，不暗示授权拒绝或建议绕过审批。

Lifecycle：可信来源 → 首次审核快照 → attempt 重放；成功才提交 Guardian checkpoint；失败/取消副本废弃。重试不新增用户文本、不改变来源标签、模型/策略和 exact action。覆盖 CC第二阶段、Guardian delta/fork/rebuild、父取消与源权限边界；检查实际组装的 reviewer requests 和主 Agent 最终工具结果，不只看源码字段。独立设计/code review 需按 current agent-context-review 方法审此消费链。

## 契约层增量 (delta-spec)

- [specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md) → `docs/specs/gateway/agent-capabilities.md`：新增有限恢复契约，不重写已有策略/来源规则；current 不提前覆盖。

## 风险与回退

- 恢复延长等待并增加 token 成本，上限与 audit 明确；不为更快交付缩短单次90秒预算。
- 未结构化的供应商错误保守停止，可能降低恢复率但不误重试永久故障；修复归因应在 adapter 公开边界，不用文本正则绕过。
- 外层恢复叠加 Guardian native retry 会失控，必须保留 scoped terminal request-error 并测试 provider always 不增加次数。
- 并发调用共享父 trunk，需失败/取消后续调用回归。failed attempt 对 checkpoint 的污染是阻断级风险。
- 回退此 unit 实现恢复原 unavailable 路由；新增审计字段可选，旧记录不迁移，禁止回退时删除审计数据。无配置迁移、无新后台服务。

## 一次性部署迁移

无。无 deployment-prompt，不运行生产迁移。

## Runbook for Reviewer

本 author 不启动服务。后续仅在该隔离 checkout 使用仓库既有 default E2E profile（父 executor 已确认替代缺失 daily 模板）；不得触碰现有 4000 服务。新服务是本地 Node/DSH 执行子进程及该旅程依赖的隔离 IM；没有新增常驻服务。

| 服务 | 停止命令（先核对 ownership） | 启动命令 | 健康检查 |
|---|---|---|---|
| 此 checkout 的隔离 IM + Node/DSH 栈 | `./scripts/e2e-down.sh --wt "$PWD"` | `./scripts/e2e-up.sh --wt "$PWD"` | 检查脚本成功退出、`.e2e-ports.env` 的隔离端口、IM `/health` 与脚本内 Node online 检查；确认不是4000 |

**Review 驱动方式**：端到端真栈；不改客户端面，允许用客户端实际调用的同一 IM 接口发起任务/停止并检查 Work。不得调用 policy.review 来冒充产品旅程。session.observe 仅为配套审计证据，不代替产品入口。

**验收前置**：default `config/e2e/gateway.yaml`、有效执行与审核模型路由、隔离测试身份及 workspace，由 executor 核实可用；模型服务健康只读检查，不把过去成功当现在成功。确定性503/invalid/timeout/abort注入应限于隔离 reviewer 模型 seam，不影响主 Agent 模型和生产 provider。不把假模型当真实服务可用性证明。Work轨迹需要实际session locator；缺失资源时报告具体 inconclusive，不自行改运行时或复制生产秘密。

独立产品验收：在 CC 和 Codex 各走恢复后安装一次、永久失败不安装、停止不安装；真实全局 Agent 自建插件→安装→两次真实调用的完整旅程留可查轨迹。执行/审核模型、版本、策略、调用ID、实际副作用次数、注入/非注入边界分别记录。真实服务失败也应留下事实，不能通过改 prompt 暗示准确工具参数来“通过”。

## Milestones

单 M1：机制、审计、缓存生命周期与产品结果必须共同验证，没有可独立交付的层级拆分。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-auto-review-retry | 有界恢复及权限不变量 | 无 | 单组 | policy/approval、classifier、codex、types、audit、新retry helper；专用 retry 与现有 integration/lifecycle/native tests；必要的 observe 断言 | [reviewer] spec 全部 Scenario 的真实旅程结果及可查 Work/审核证据，真实与注入结果分开；[worker] 下述 W1-W7 全覆盖，提交实际测试证据，无伪造通过 |

### M1 worker 退出标准

- W1：两策略503→allow、持续503、429、TRANSPORT、TIMEOUT共享最多2 extras；混合 invalid→503→allow、503→invalid→invalid、invalid→invalid 证明 invalid 仅1次恢复，不按类别重置。
- W2：每次90秒独立；晚期首 attempt 超时后第二/三次仍有完整90秒；CC30/60、正常两阶段与Codex context rebuild边界；退避hint cap10秒与总主动预算≤290秒。fake clock验证，不用缩小生产常量。
- W3：final deny、AUTH/credential/config/quota/unknown 不重试；CC workspace exemption、Auto off、安全工具、DSH单阶段与已有deny计数不回归；native provider always 不绕过cap。
- W4：active request、preparation、backoff、allow提交竞争中cancel：零工具执行、零后续attempt、迟到结果无效；不合作 iterator无并发重试、不挂住调用方；Guardian失败/取消不commit、不复用失败session，随后成功与并发fork安全。
- W5：工具体在重试期间计数0，allow后恰1；interactive/return_to_agent/unattended-deny路径耗尽不执行，既有显式unattended-allow独立验证且不冒充模型allow。
- W6：各attempt分类、耗时、model、可得usage及缺失含义经audit schema持久化/reopen并穿透session.observe；新工具callId与原审核reviewId/attempts可区分；取消及混合原因可复查，技术失败不计安全deny。
- W7：实际reviewer输入与主Agent最终工具结果取证：授权来源/精确动作不漂移，失败文本不污染缓存或成为owner指令；运行最窄新增测试、既有approval与Codex lifecycle/native、typecheck/build及依赖边界；Full独立code-review+verifier、产品reviewer、本地CI、delta归并与archive仍须由executor完成。
