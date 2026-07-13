# Design 复审：refactor-462（final architecture, final revision）

**结论**：Approved

最新设计已闭环三轮复审中的全部问题。`SessionDirectory + ConversationSession × N + private JsonlTranscript + KernelExecutor`与本仓库期望的 CC 式“per-conversation deep module”最终形态对齐；PromptSlotSeed 的 reserved metadata grounding、append/close 同一 permit admission、raw files/writer/Transcript 单一写路径、parent-scoped find、Executor bind-before-schedule、cancel semantic terminal 与 TargetToken cleanup 分域、`/stop` 同步 held-steer park、Session.close 单向责任、composition root 构造顺序都已拍死。设计可交 change-orchestrator / worker 实施。

## 核实台账

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 生产 composition | 从 `build_kernel` 追 store/service/Runtime/Registry/Runner | ✓ 方案命中真实 seam：`src/agent/sdk/kernel.py:356-460`将同一 session manager 注入 Runtime/Registry，background 又依赖 Runtime/Registry。 |
| Runtime 是多 session owner | 查平行 maps、run lock、close | ✓ `src/agent/core/agent/runtime.py:143-305,322-378,1246-1268`同时容纳 shared engine 与 session live state，需退役其 multi-session 形态。 |
| Manager/Service 是浅 seam | 查 `.writer/.store/.manager` 与 append 组合 | ✓ `manager.py:29-41`、`service.py:64-68,120-191`证明现有抽象可穿透且不隐藏事务。 |
| Registry/Runner 执行权分裂 | 查 task owner 与 bare coroutine | ✓ Registry 自己建 top-level task（`registry.py:123-177,430-461`），RuntimeRunner 又绕过它提交 auxiliary（`runtime_runner.py:46-160`），统一 Executor 有真实必要。 |
| Kernel facade 分散 owner | 追 create/submit/append/fork/compact/close | ✓ `kernel.py:795-921,1351-1398,1450-1487`分派到 Service/Runtime/Registry，是本 unit 应治理的根因。 |
| AgentTool 穿透 | 追 subagent create/resume/run | ✓ `agent.py:357-419,512-565,640-695`穿 Runtime/store/owner-loop；Directory + auxiliary handle 是正确收口。 |
| JSONL 位置与 schema | 查 path/list/materialize/writer | ✓ workspace+parent 即时定位（`jsonl_store.py:395-430,615-625`）；turn chain 与 recovery 分类（`:247-355`）；writer 仅 enqueue，flush 才 durable（`jsonl_writer.py:11-48`）。 |
| 公开 SDK 签名 | 对照 canonical/live | ✓ submit/cancel/interrupt 为同步 non-blocking，compact/fork/aclose 为 async（`sdk-boundary.md:86-92`），设计不得偷换。 |
| cancel 返回契约 | 对照 canonical 与 live `Kernel.cancel` | ✓ canonical/live 的同步 `RunInfo(status="cancelled")`保留（`runs.md:147-150`; `kernel.py:1077-1094`）；设计已把 public semantic terminal 与 internal TargetToken cleanup 分域（`design.md:177-180,270-287`）。 |
| interrupt held-steer 契约 | 追 `/stop` 生产时序 | ✓ 设计明确保留 `interrupt()` 返回前 drain pending→held，TargetCompletion 仅兜底后续竞态（`design.md:179`），与 live/Gateway 时序（`registry.py:518-529`; `inbound_pipeline.py:1087-1111`）一致。 |
| shutdown 契约 | 核 admission/drain/consumer loop | ✓ canonical 要求有限 drain、拒绝新 run、`aclose` 不阻塞产品 loop（`runs.md:193-218`）；typed Executor + admission snapshot 方向正确。 |
| core/platform/sdk 依赖 | 核顶层规则与 DTO | ✓ `PromptSlotSeed` 属 core-owned，SDK 仅边界转换，未引入 core→sdk/platform 倒挂。 |
| canonical invalidation drift | 对照 SDK/live caller | ✓ `context-persistence.md:60-64`的 public invalidation 不存在，live 仅 Kernel 调 Runtime private invalidation（`kernel.py:1392-1398`）；可作 grounding correction。 |
| 顶点 SPEC drift | 对照当前模块清单 | ✓ `SPEC.md:67-75`仍列 AgentRuntime/SessionManager，收尾应归并为 Directory + ConversationSession × N。 |
| CC per-conversation 粒度 | 读本地 `QueryEngine.ts` | ✓ QueryEngine 明确 one per conversation，持 messages/file cache/cancel state（`QueryEngine.ts:183-215`），`submitMessage` 内部统一 durable input 与 query（`:420-473,688-747`）。 |
| CC transcript 边界 | 读本地 `sessionStorage.ts` | ✓ taxonomy/chain/write 集中（`sessionStorage.ts:128-156,1005-1082,1431-1471`）；对齐 deep module 形态，不照搬 singleton。 |
| 澄清 Q1：独立复审 | 核 author/reviewer 分离 | ✓ 本轮 fresh 对照修订后全文、live/canonical/CC，未继承上轮 verdict。 |
| 澄清 Q2：治理目标不走歪 | 核 session seam 与 kernel-wide 职责 | ✓ 决策 1/3/7 只退役 multi-session owner，LLM catalog/skill resolver/batch queue 保持 kernel-wide。 |
| 澄清 Q3：最终架构 | 做 deletion test 与 CC 对齐 | ✓ per-conversation object 拥有完整 turn transaction，不是深化全局 manager 的中间态。 |
| 决策 1：Directory + Session × N | 核 identity/eviction/binding mismatch | ✓ Directory 只 intern identity/query/close enumeration，ConversationSession 才是会话 state/transaction owner，粒度正确。 |
| 决策 2：高层事务接口 | 核调用方必须学习的 invariant | ✓ `submit_turn/append_external/compact/fork/close` 隐藏 load/durability/compact/recovery，无 public lease/command union。 |
| 决策 3：Session 接管 orchestration | 核 wrapper 风险与 Prompt seed | ✓ 禁止 `Session -> runtime.run(session_id)`；`PromptSlotSeed` 从 SDK 结构化转换，用 reserved metadata 存取，旧档 empty fallback（`design.md:130-142`）。 |
| 决策 4：Transcript + LifecyclePermitGate | 核 owner、lock order、append/close 线性化 | ✓ files 只 raw read/address，writer 是唯一 append path；Condition 只管 operation permit，to_thread worker drain 先于 permit release，无重复 borrow counter，Session.close 不反向 cancel Executor（`design.md:144-157`）。 |
| 决策 5：compact/fork transaction | 核 epoch/commit/两类 fork | ✓ summary 在锁外计算，commit 校验 external epoch，whole fork 与 as-of-M 有不同锁语义（`design.md:159-168`）。 |
| 决策 6：Executor 只持执行资源 | 核 typed interface/admission/control/terminal | ✓ bind-before-schedule、run_id→token owner、auxiliary/shutdown、sync cancel semantic terminal、internal cleanup ack、sync interrupt park 都已用具体 interface 和时序闭环（`design.md:170-184,252-287`）。 |
| 决策 7：删 Service/Manager | 核 raw/high-level 分层与 find scope | ✓ `JsonlSessionFiles` 仅 raw address/read/enumerate，schema/materialize/repair 全归 private Transcript；`find_by_metadata` 显式带 parent scope（`design.md:186-195`）。 |
| 决策 8：无公开/schema delta | 核 reserved metadata 与旧档 | ✓ exact key/payload/DTO stripping/fork copy/old empty fallback 全已拍死；这是 canonical PromptSlots 稳定性的 grounding correction，未新增 entry type/path（`design.md:197-205`）。 |
| Requirement：正常连续性 | 核 CLI/Gateway recovery | ✓ Directory.open + lazy Transcript repair/load 恢复 history，reserved prompt seed 填上 Gateway 重启时原有缺口。 |
| Scenario：CLI 多轮/恢复 | 核 `/use` 既有流程 | ✓ SDK surface 不变，open 后的 session object 独立恢复 state。 |
| Scenario：IM/Gateway 多轮/重启 | 核 existing binding 复用 | ✓ 既有 binding 不再 create 时，open 从 reserved seed 重建 PromptSlots；旧档继续 empty fallback。 |
| Requirement：带外消息/终止恢复 | 核 tail/admission/control | ✓ tail/append/close、cancel 同步返回、target cleanup、interrupt held park 都有单一 owner 和线性化点。 |
| Scenario：两轮间 append | 核 durable + epoch | ✓ tail ensure/dedupe/parent/append/flush/epoch 在同一短 mutation 内，下轮可见。 |
| Scenario：restart-first append | 核 UNKNOWN/EMPTY 与 tail 来源 | ✓ 首次 mutation 从 raw JSONL 最后 persisted reachable turn 初始化，synthetic recovery UUID 不 seed tail。 |
| Scenario：interrupt/cancel 后继续 | 核 status、permit、held steer | ✓ cancel 立即返回 CANCELLED，旧 target 在内部 cleanup，后续 run 由 session gate 等旧 permit 释放；interrupt 在返回前已停放 held（`design.md:178-180`）。 |
| Requirement：长会话/分支 | 核三类 compact 与两类 fork | ✓ 统一 private commit、epoch guard、whole/as-of-M 差异和 target restamp/seed 都已闭环。 |
| Scenario：compact 后继续 | 核 state replacement/window reset | ✓ history/memory/file/prompt window reset 由同一 ConversationSession commit 拥有。 |
| Scenario：指定消息 fork | 核 as-of-M/whole fork | ✓ point fork 只短持 Transcript mutex，whole fork 在 session transaction 内 capture，目标独立。 |
| Requirement/Scenario：prompt/file window | 核 freeze/reset/restart | ✓ PromptSlotSeed、MemorySnapshot、SessionFileState 归属清楚，seed 重启恢复与旧档 fallback 明确。 |
| 非目标：不改 SDK/产品/entry/path/中心 registry | 查新对象与 persistence | ✓ Directory 是进程内 identity host，prompt 复用既有 metadata envelope，无中心 path registry 或新 schema。 |
| 迁移/回滚 | 核 cutover 与双 owner | ✓ 单 unit 一次性删 multi-session maps、Service/Manager、store/writer 穿透，JSONL 无迁移，可整 unit 回滚。 |
| delta：kernel | 核 no-delta 与 grounding correction | ✓ `cancel()` 公开语义、SDK/DTO/entry/path 均不变；Prompt seed 和 invalidation 只修正 existing canonical grounding。 |
| delta：IM | 查包依赖/用户面 | ✓ IM 不 import agent，无 schema/UI 变更。 |
| delta：Gateway | 查 binding/stop/append 生产路径 | ✓ `/stop` 的 sync park→append marker→next real submit 时序保持，无产品 delta。 |
| delta：CLI | 查 submit/cancel/close surface | ✓ sync `cancel()` 仍立即返回 CANCELLED，其他 surface/error 不变。 |
| M1：conversation-session | 核垂直性、范围、exit | ✓ 这是一个不可拆 ownership consistency boundary；M1 覆盖全部 motivation scenarios，并把 cancel public terminal/target cleanup、`/stop` sync park、single write path、parent scope 分别列为 exit。 |

## 架构进攻

| 角度 | 发现 | 结论 |
|---|---|---|
| 归属 | ConversationSession 拥有 conversation state + orchestration，Directory 只拥有 identity/query，Transcript 只拥有绑定 session 的 schema/chain/durability，Executor 只拥有 carrier resource。 | ✓ owner 已正交；RunInfo semantic terminal 属 Registry，TargetToken cleanup 属 Executor，pending/held 语义属 Registry。 |
| 该不该存在 | Directory 解决 per-process identity/binding/list/find/shutdown enumeration；Executor 收拢 top-level/aux/lifecycle targets；Transcript 隐藏 tail/taxonomy/durability。 | ✓ 三者都有独立 invariant；LifecyclePermitGate 仅留不可删的 admission/permit，重复 borrow 已删。 |
| 深还是浅 | `submit_turn/append_external/compact/fork/close` 隐藏的进程/持久化/窗口/恢复规则显著大于接口；raw files 已不再重复 materialize/repair。 | ✓ ConversationSession 和 Transcript 都通过 deletion test，不是新壳包旧 runtime/store。 |
| 治本还是补丁 | 全局 manager 转 per-conversation object、single taxonomy/write path、single admission guard、typed Executor 都在治 owner 分裂根因。 | ✓ 同时保留 cancel 与 `/stop` 历史上已修复的线性化点，未用新架构重写既有行为。 |

## Issues

无。

## Recommendations

- 实施时严格保留设计中的三个独立线性化点：`cancel()` 写 public semantic terminal、`interrupt()` 同步 park pending、TargetCompletion 证明 internal cleanup；不要因“统一终态”再把它们合并。
- 以 M1 已列的真 Gateway `/stop`、sync cancel + same-session resubmit、fire-and-forget subagent + immediate close 作为高风险实施闸；设计文档本身无需再修订。
