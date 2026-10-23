# Code Review: bugfix-646-task-continuation

## Round 1 — full

- 独立 reviewer：`/root/static_review_646`，未参与实现；使用 `change-code-review`。
- 固定范围：`e7f8249d26287dbaccde298365323c70e3cd5fc8..6223412809e5bdb98a741402d913e33589d686bc`，完整 20 文件 diff；开始时工作树干净。
- 完成时间：2026-10-23 23:28 +08。完整读取 Task driver、IM 事务/receipt、PA snapshot/调用包装、工具 schema、提示生成源与产物、Codex 审核及相关测试；核对 incident、design、两份 delta 和架构/测试契约。
- 复用 `implementation.md:9-11` 的红绿测试与构建/typecheck 证据；未重复全量 CI，真实产品旅程由独立 reviewer 执行。未把尚未提供的 CI/产品结果当作代码缺陷。

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 121,
    "summary": "[P2] 依赖操作拒绝时应只阻挡可定位的关联责任",
    "failure_scenario": "同图有本人 doing A、B、C，A/B 的 add_dependency 或 remove_dependency 被拒。真实 task_graph schema 和 IM applyOperations 使用 from/to，但此处只读 node_id/container_id/scope_id，得到空 ids 后把该图所有 doing 任务都记入 denied，包括独立 C。runnable 因所有任务 held 返回 false，C 也失去下一轮自动推进，直到责任变化或新输入；违背 design.md:46 的其余 doing 继续。应识别依赖端点并保留与该操作无关的责任可执行性，增加同图独立 C 的拒绝回归。最小驱动 seam 复现输出 held=[g/A,g/B,g/C], automaticAdmitted=0。",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 122,
    "summary": "[P2] 子树操作无法匹配直接责任时仍需保留拒绝屏障",
    "failure_scenario": "本人只负责父节点 P 下的 doing 子任务 C，P 本身未进入责任快照。task_graph delete(node_id=P) 被拒后，这里只按 P 与直接责任 node_id 相等筛选，tasks 变空，因此不保存任何拒绝。下一次 idle poke 立即再次 admission 未变化的 C，而该轮可能再提出相同被拒的子树删除，重现本 unit 要停止的无效自动重复。IM delete 的真实语义会递归删除 P 的全部子树，不能把未命中直接责任解释成无关操作。应对能定位到图却无法在最小投影核实子树影响的情况保留适当作用范围的屏障，不凭空推断无影响；增加父节点不在责任清单的回归。最小驱动 seam 复现输出 held=[], automaticAdmitted=1。",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## 独立复核证据与边界

2026-10-23 在固定实现上执行：

```sh
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec tsx /tmp/nano-646-review-scope.mts
```

临时脚本直接 import 受审 `src/task-execution.ts`，以最小 Context 捕获构造器注册的 `tools/result` listener，设置完整 shown responsibility，再经该 listener 注入真实错误形状 `isError:true,error.info.name=NanoApprovalDenied`，随后调用真实 `poke`；不替换 `denied`、`heldTasks` 或 `runnable`。两例的 snapshot 和责任版本保持不变。输出：

```json
{"case":"dependency","held":["g/A","g/B","g/C"],"automaticAdmitted":0}
{"case":"delete-subtree","held":[],"automaticAdmitted":1}
```

依赖入参来自 `features/task-graph-schema.ts:97` 和 IM `task-graphs.ts:285-294`；删除子树语义来自 IM `task-graphs.ts:718-738`。复现确认 admission 计算缺陷，不声称模型在生产中已经重复删除或造成副作用；被拒动作仍需原审批，未发现由此绕审。

`policy/codex.ts:105` 的 effort 修订只在所选模型的声明能力内选择 low/default/首档，没有更换 provider/model、删证据、改变 verdict parser、失败分流或只读 reviewer 约束；生命周期参数回归有对应证据。此结论限于 CodexApproval。固定版本的默认 Nano `policy/classifier.ts:28` 仍硬编码 low（未在本次 diff 内），caller 已确认另补兼容性修订；本报告不把 Codex 测试外推为整条默认 Nano 产品链路通过。

上述两项条件均已直接复核，无待证实高风险候选。未启动服务、未改源码/测试/配置；仅新增本报告与 verification.md。

## Round 2 — patch

- 固定受审版本：`e2219e12b89b581fbd1808ad768f78c72090c081`；patch：`6223412809e5bdb98a741402d913e33589d686bc..e2219e12b89b581fbd1808ad768f78c72090c081`，其中 `1d8508030` 仅为 R1 报告。
- 时间：2026-10-23 23:37 +08；同一独立 reviewer，未参与修复。开始时仅 design-review.md 有其他 reviewer 的未提交内容，未修改或提交该文件。
- 完整覆盖 patch 内 Task 拒绝作用范围、首次 source unavailable 普通输入、Nano classifier effort 与新增测试/文档。R1 其他实现未变，沿用其已核实结论，不重新执行 full。

### Findings

```json
[]
```

### Focus findings closure

| R1 finding | 结论 | 直接证据与回归 |
|---|---|---|
| dependency from/to 未定位，独立责任被整图抑制 | **closed** | `task-execution.ts:119-124` 已提取 from/to；复用 native scope 参数化 dependency 用例（`:179-220`），被拒 A 与同图独立 B 分别保留屏障/完成；再次执行同一 R1 驱动复现得到 held=[g/A,g/B], automaticAdmitted=1，独立 C 可推进 |
| 非责任父节点子树删除拒绝漏屏障 | **closed** | `task-execution.ts:122-124` 对 delete 明确采用已知当前图责任批次，不猜测快照未展开的树；native subtree 用例同时验证另一图 B 完成；同一 R1 复现得到 held=[g/child], automaticAdmitted=0 |

### 新补丁安全与兼容性复核

- `policy/classifier.ts:15,28` 从同一 reviewer provider/model 的 ModelInfo 中选择 low/default/首个支持档位；未声明 reasoning 时传 undefined。`approval.test.ts:330-345` 的三种能力用例对两阶段请求均断言模型身份、完整适用 transcript 与最终 deny。原 context 估算/输出预留、两阶段后缀、解析和失败分流未改；这不是通过换模型或删证据处理拒绝。原 native fixture 现在明确声明其原本期望的 low 能力，不以隐含不合法 effort 维持通过。Codex R1 同模型参数测试仍适用。
- `task-execution.ts:75-80` 仅在之前已知任务时注入 source unavailable 提示；初次没有已知责任时保留原普通输入，自动 admission 的 reject/hold 未放开。直接 pre-step seam 验证：unknown responsibility 时消息数 1、原消息同一对象、interrupted=source；known responsibility 时消息数 2、仍保留原消息及 source hold。两者都允许普通输入按既有语义处理，已知旧 Task 仍收到停止依据旧快照动作的提示。
- 有效测试复用：caller 提供的 e2219e12b 源码窄测 `/tmp/nano-646-patch-final.log`，`approval/task-execution/task-recovery` 3 文件 / 24 测试，23:33:37 开始、108.78 秒通过；报告已读取汇总并逐项检查测试 seam。R1 的 Codex effort 8 测试保留。未重复全量后端 CI，不把尚未返回的真实产品结论当作缺陷或成功证据。

直接复核仍使用 R1 `/tmp/nano-646-review-scope.mts`；其 dependency 与 subtree 输入不变，另外补入 known/unknown responsibility 的 unavailable pre-step 对照。精确输出记录于 verification Round 2。没有未确认的存活候选；本轮只改报告。

## Round 3 — patch

- 固定受审版本：`3a2debdd5eea8d3153fa5ae4903f67a33c9c5d92`；上次有效报告 `97be7854e`。本 unit 实现增量 `4f8f1704f`，并检查 merge 引入 `origin/main 4bb02455b` 的共享 integration/PA 接线；未把无冲突当作集成正确的证明。
- 时间：2026-10-24 00:13 +08；同一独立 reviewer，未参与修复；开始时工作树干净。
- 范围：产品 R1 P1/P2/P3 对应 SingleThread query、宿主 stop 事实持久化及首步可见、审批来源、confirmed send/sentinel；main PR393 descendant/reconcileRoot 与 PR394 usage 的交互。R2 未受影响的 Task cap、反馈、拒绝作用范围与审核模型兼容性结论保留。

### Findings

```json
[]
```

### Focus closure（代码与故障 seam）

| 产品 R1 问题 | 代码处理与证据 | 静态结论 |
|---|---|---|
| P1 SingleThread send 查询误执行 Global session 注册 | PA `global-agent.ts:491` 只在 Global ensureAuthority；IM `work.ts:488-520` 仍验证 Agent/node/空间/会话权限，SingleThread 不需要 Global journal session；原同群修正测试显式令 agent.session.ensure 抛 invalid_scope，正常查询/重核验仍通过 | addressed；真实提问/等待链由产品 R2 复验 |
| P2 旧排队答复越过 /stop | PA `task-execution.ts:63-74` 顺序为 fence/cancel/drain → IM pause receipt → 固定 ID inject → runtime submit flush → 完成 control → 解 fence；source 携带原 actor/message/time/scope，失败前不完成 control。integration `task-execution.ts:174-175` 对被拒入场的控制保留 next-step，普通消息仍 next-turn。真实 native 队列竞态测试检查第一次模型调用含 HOST_STOP_NOTICE，定向重跑通过（RuntimeClient 使用 4f8f 编译产物，不能据此证明合并后 index）；审批来源投影及 Nano/DSH/Codex 共享规则保留停止时间优先 | addressed；不代替真实旧输入/后续真人恢复旅程 |
| P3 plain explicit send 后公开 NO_REPLY | `global-agent.ts:580-588` 仅真实 confirmed publication、同 call turn、同绑定聊天/有效映射保存既有交付键；SingleThread `:223-231,409` 共用于卡片/文字的流式和 final 哨兵处理。unknown、不同聊天不设键；visible approval 不丢弃整泡，既有 final 审批分支剔除哨兵并保留审批结果 | addressed；产品 R2 核对真实聊天 |

### 合并接线与边界

- PR393 将 PA reconcile 拆成 root 与 child drains：Task mutation/send 现在只 await `reconcileRoot`，它仍先持久记录 root events、模型投影、Inbox read/consumption，再执行来源与交付检查；子轨迹使用单独队列不参与授权。Task stop 的 drain 仍来自 `apps/node/src/main.ts:332-334` 的已接收 product calls，不会由于 child 展示读取换路而跳过。检查实际 merge 后 `index.ts:640-660` 的 submit/flush、`:427-438` 的 cancel keepInbox 以及 PA stop 的调用顺序，没有覆盖新增控制逻辑。
- PR394 的 usage.read 已由 PA UsageReports 同步消费 `{reports,cursor}`，turn/end 通知新增 usageRoot 只用于统计归属；不参与 task-human-control 分类、stop fence 或 SingleThread 交付键。检查共享 index 的 listener/RPC 与 usage 持久屏障，未发现本 patch 的停止/交付顺序被改变。
- `policy/sources.ts:9,164-165` 将宿主 Task 控制投影为 human-task-control；普通 Task/Schedule/Agent 消息仍不是新授权。classifier 与 Codex policy 均实际复用 reviewSourceInstructions。旧排队消息的原发生时间由 SingleThread 入模前言保留；不因后处理顺序将其升格为新恢复。
- 修复复用现有 control intent、inputEvidence 去重、inbox、publication 和交付键；无新调度器、存储表、审批豁免或跨包运行时依赖。

### 验证结果与未完成门禁

- 复核 `/tmp/nano-646-finalpatch-green.log`：6 文件 / 89 测试中 88 通过，新增 stop/交付均通过；旧 automatic denial 在等第二次模型调用的 5000ms poll 超时，**本报告不把该批记为全绿，也不在无新证据时定性产品根因**。该用例由 caller 在合并版单 worker 全量中重跑。
- 我方在合并源码工作树单独执行：`pnpm exec vitest run packages/dsh-integration/tests/task-execution.test.ts packages/personal-assistant/tests/global-agent.test.ts -t 'restores a stop fence|source checks independent' --maxWorkers=1`，Node24 PATH；00:11:36 开始、22.87 秒，2 文件 / 3 passed / 57 skipped。PA 两例直接 import 3a2 源码，覆盖 Task/send root 来源检查独立于 child drain；native stop 的 RuntimeClient 实际启动仍为 4f8f 编译产物，仅保留为未被 main 修改的 driver stop 修复证据。caller 随后发现 e2e-up 不执行 build，停止错误的集成验证，重新显式 build；本次 3 例不能称为 3a2 完整 runtime 集成通过。
- 产品 R1 原报告仍为失败历史；P1/P2/P3 的最终真实闭环由新隔离栈产品 R2 负责，不用静态通过取代。最终后端全量/typecheck 仍由 caller 执行，不能据此提前宣称 M1 完成。

本轮无未证实高风险存活候选；仅追加本报告与 verification.md，未修改源码/测试/配置/设计，未触碰或重启产品 reviewer 的服务。

## Round 4 — narrow patch

- 固定源码：`1fbacfe3d89f842424fa5e6a7d57707dc02971f7`；唯一受审 patch `a9e0f38ff..1fbacfe3d`。同一独立 reviewer；2026-10-24 00:27 +08；开始时工作树干净。
- 仅核对 PA SingleThread 纯 Task 通知的自动交付归类、流式边界、RelayInput 已有字段声明及新增 Scenario；保留 R3 其他结论，不重跑全量。

### Findings

```json
[]
```

### 覆盖与来源证据

- `single-thread.ts:233-238` 按**当前 turn 全部输入**的 sender_type=system 与 system_notice.kind=task_graph 同时成立才认定 Task 纯通知，复用自动轮次分支，不查另一 turn 的 confirmed-send 记录。外层循环已持有至少一条该 turn 的 input，不存在将空输入集合误分类成 Task 通知的新路径。
- `:240-246` 在没有待展示/可见审批时延后占位；结束时只抑制既有静默 sentinel/空正文，有意义 final 仍进入普通交付；approvalVisible 不丢弃整泡，既有 final 逻辑保留审批并去掉 sentinel。`:405` 对 native task_execution/宿主 Task 纯自动输入停止流式 routine text，避免已生成审批 bubble 被通知正文污染；真人/其他系统/混合真人的 stream 不满足该条件。
- 实际字段链：IM `task-notifications.ts:37` 生成 task_graph 元数据，`messaging.ts:636-639` 以 system 持久化；`:344-345` 投影 system_notice，`:651-652` 将整个消息写入 Relay；PA NodeStore `store.ts:172-175` 保存完整输入。新增 optional/null `RelayInput.message.system_notice` 只是补足已有线上字段类型，没有新线协议、权限或新来源提升。
- `single-thread.test.ts` 的直接通知矩阵覆盖纯通知 sentinel、正常正文、user 伪带同 notice、other_notice、混合真人；原 native Task 审批测试参数化为 native/notice 两种，保护审批请求/resolve/final 不丢失且没有 routine stream。未修改原 same-turn confirmed-send 判定与 Global 路径。
- 复用 `/tmp/nano-646-task-notice-green.log`：PA SingleThread + interactive 两文件 / 24 测试通过，00:24:33 开始、4.09 秒；均直接读取 PA src，不涉及 R3 旧 native lib 版本问题。implementation 保存三例有意义红测来源。本轮未追加运行测试。

产品 R2 发现的残留 P3 是新的 Task 通知 turn，不能将其归为旧 same-turn 去重再次失效。本轮只确认该新原因的代码与 delta 修复；**不含尚未提供的产品 R3 结果**。caller 的 build 后全量及原 native 环境超时复核仍独立记录，未冒充全绿。无存活待确认候选；本轮仅改本 unit 两份报告。

## Round 5 — final-main integration patch

- 固定受审 HEAD：`defa49f2db762ab7e0e0415b4a10312f0dcaf764`；executed_base / effective_base：`55376c111`；集成增量：`e53e488e5..defa49f2d`，包含 main 的 perf-648 / perf-649 合入。
- 同一独立 reviewer；2026-10-24 00:39 +08；开始时工作树干净。只审这些共享输入证据/重放变化与本 unit 的实际交互，保留 R4 之前未失效结论；未以 merge 无冲突判通过。

### Findings

```json
[]
```

### 集成风险与实证

1. **perf-648 与 Task 通知/显式交付。** `single-thread.ts:202-212` 只用 `lookupInputIds` 缩小待查询集合；随后交付仍遍历 `store.inputs(sessionId)` 的全部持久输入，并按逻辑 turn 取 sender_type、system_notice、origin。`store.ts:204-205` 不删除/裁剪 payload，evidence_final 仅控制重复 lookup，故 Task pure-notice 与 mixed/human 的分类不因终态缓存丢来源。confirmed-send 和 approvalVisible 的同 session/turn 交付键仍独立；未因 lookup 已固定就跳过待确认消息/receipt。`store.ts:231` 防止迟到物理 turn/end 覆写逻辑终态，不改变输入正文或交付结果；升级把历史终态留为 unresolved，避免把旧物理失败误当 final。
2. **perf-649 与 stop/control/旧输入恢复。** 新 `inputIdsForTurn` 的双队列、非 canceled claim、user/message 和最后 turn 归属，与原 inputEvidence 的计算一致；helper 只返回 ID，不改消息 source/content，也不操作 inbox。`model-fallback.ts:260-261` 保留原 nano-fallback 排除与唯一 run.inputs；原来的 stop cancel keepInbox、inject 去重/flush、被拒控制 next-step 恢复均未更改。fence 内 claim 后恢复的旧输入仍 pending，因此 perf-648 不会提前固定它；下次实际消费后 lookup 仍可更新最终逻辑 turn。Task 控制通知不因入 fallback inputs 变成人类新授权。
3. **真实共享接线。** 复查 runtime session.lookup 的 fallback.evidence 包装、SingleThread logicalEvents、NodeStore inputEvidence、同轮 publication 和 Task stop 的完整调用关系。perf-648 对 physical/logical turn 的判定不会拿 receipt 成功代替模型完成；perf-649 没有改变审批或恢复策略。上游两个 unit 的 archived verification 仅作为契约/已完成范围旁证，本轮结论来自 merge 后真实源码和下面窄测。

### 构建与独立测试

先读取 caller `/tmp/nano-646-final-sync-build.log`，核实完整构建对应 `defa49f2d`，installer candidate `bca4d1524c5d`；收到 build 成功通知后才启动 native 测试。本轮不存在 R3 的旧 lib 版本混用。

| 命令（Node24 PATH，均 maxWorkers=1） | 实际结果 |
|---|---|
| `pnpm exec vitest run packages/personal-assistant/tests/single-thread.test.ts packages/personal-assistant/tests/interactive-replies.test.ts packages/personal-assistant/tests/input-reconciliation.test.ts packages/dsh-integration/tests/input-evidence.test.ts --maxWorkers=1` | **4 files / 34 passed**；00:37:50，14.12 秒。直接覆盖新 final-evidence 与本 unit 通知/交付边界，归属 helper 逐历史前缀和旧 inputEvidence 差分一致 |
| `pnpm exec vitest run packages/dsh-integration/tests/task-execution.test.ts -t 'restores a stop fence' --maxWorkers=1` | **1 passed / 12 skipped**；00:38:02，26.30 秒。实际新编译 runtime 下 fence 内领取/拒绝及解锁后首模型步含宿主 stop 事实成立 |

未发现可操作新缺陷或未证实高风险候选。原全量 631 中两项失败由 caller 负责定点处理，本报告不把它们改写为已绿、也未重复其失败文件。真实产品已由 regression.md Round 3 通过，属于既有产品证据；本次集成窄验证不冒充新产品旅程或生产部署。只更新本 unit 两份报告，没有源码/测试/配置/设计改动，没有服务需清理。

## Round 6 — P4 narrow patch closure

- 固定范围：`b0d107309..00ffba95923751b2ef04cc561158f85cb66adfa0`；同一独立 reviewer，未参与实现；2026-10-24 00:49 +08。开始时工作树干净。
- 本轮只审 automaticOnly 集合判定一处修正及对应原测试矩阵扩展；其余 R5 源码/集成结论保留。不重跑全量或接管真实产品现场。

### Findings

```json
[]
```

### P4 closure 与证据边界

- `single-thread.ts:238-239` 从 `every(A) || every(B)` 修正为 `every(A || B)`，A 仍是既有 origin=heartbeat/task_execution，B 仍是 sender_type=system 且 system_notice.kind=task_graph。没有扩大单条输入获静默资格的集合；只允许同 turn 内两种既有自动类别混合，与已有 stream 的逐项 union 过滤一致。任一普通真人或其他通知不满足 A/B，则整个 direct turn 不新增静默资格。
- 修改不影响有意义 final、可见/待展示审批、same-turn confirmed-send、fallback/stop 或普通真人交付。native Task 记录经 NodeStore 既有 runtimeInput 映射为 origin=task_execution，task-change 的 context_only 不改变此分类；宿主控制来源不被升级为真人授权。
- 读取 `/tmp/nano-646-mixed-notice-red-direct.log`：新增 mixed-native 的静默与有意义正文两例均在旧实现的早期 bubble 断言失败（2 failed / 19 passed）。读取 `/tmp/nano-646-mixed-notice-green.log`：SingleThread + interactive **2 files / 26 passed**，00:47:34，3.80 秒。新增矩阵保留 mixed-human、伪带 notice 的 user、other system、正常正文与审批原有保护；不以精确文案测试替代交付 seam。
- 已读 regression.md 产品 Round 4：P4 是真实 Task notice + native context 的混合自动轮次；独立的旧真人 turn14 NO_REPLY 是范围外体验观察，本修复不通用吞真人 sentinel。P4 的**代码缺陷已关闭**，修后真实产品闭环仍待 reviewer；不将先前产品 R3 的纯通知通过外推为本次混合场景已验收。

无存活 finding；本轮仅追加/更新两份报告，未改源码/测试/配置/设计，没有新测试服务或进程需清理。

## Round 7 — same-PR quiet stop / external mutation synchronization

- 独立 reviewer 不变，未参与实现；时间 2026-10-24 03:01 +08。
- 实际 patch base：前次交付 `a22ee9043`；effective main：`503c98e93`；冻结受审源码：`503498e1f94ec05ee99e5ef6367a7ae8bd28bbee`。Requirement 索引计数另核对文档修订 `752af9f86`。本轮不审随后在共享现场进行的 main `63724d53f` 集成或未冻结修复。
- worktree：`/Users/czj/.codex/worktrees/task-stop-sync-646/nano-multiagent`，branch `unit/bugfix-646`。开始时已有未跟踪 `.gateway-test-source.yaml`，保留；审查途中 caller 开始另一轮 main 合并，后续定位均以 `git show 503498e1f:<path>` 为准，没有将移动的现场当作受审源码。
- 完整审本 patch 的 IM self-stop relay、群解散通知、driver passive stop/UI resume/冷空责任/normal-dispose 恢复与对应测试；未机械重审无改动的旧功能。

### Findings

```json
[
  {
    "file": "packages/dsh-integration/src/task-execution.ts",
    "line": 186,
    "summary": "[P2] 按停止通知首次接受顺序选最新事实，不能用最后一次重入队顺序",
    "failure_scenario": "两个可信 stop 先后注入 older、newer；fence 内一次并发普通输入触发 pre-step，blocked restore 按 messages.toReversed() prepend，产生插入序列 older,newer,newer,older。正常 shutdown 随后取消两条尚未消费的 context。冷恢复当前代码逆扫最后一次 inbox/spliced，选中重新入队较晚的 older 并立即 return，首次未来模型请求仅见 STOP_OLDER，新停止的原时间/作用范围未恢复。它违反 R9 只恢复最新可信 stop、不得回溯更早 stop 的要求，虽然没有额外唤醒。应按产品停止消息的稳定接受顺序去重身份后确定最新事实，再检查该最新通知是否 consumed/pending，不能把 restore 的二次插入视为新的停止。增加双 stop、逆序恢复、正常 dispose/restart 的真实队列回归，并保留较新已消费时不补旧 stop 的反例。",
    "review_mode": "patch",
    "status": "CONFIRMED"
  }
]
```

### 独立原生复现

在冻结源码对应的已构建 RuntimeClient/native profile 上执行：

```sh
PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH pnpm exec tsx /tmp/nano-646-latest-stop-review.mts
```

临时 profile 仅拦截 LLM stream 将实际请求保存到自己的临时目录；使用真实 initialize/session.ensure/block/session.submit(inject/followup)/session.observe/shutdown/restart。先确认旧、新两个可信控制在 fence 内都已被领取再恢复（两次 inserted），正常退出，恢复为空责任，提交未来普通问题。输出：

```json
{"stage":"blocked-restored","calls":0,"insertions":["task-stop-notice:a:older","task-stop-notice:a:newer","task-stop-notice:a:newer","task-stop-notice:a:older"]}
{"stage":"first-future-model","controls":[{"id":"task-stop-notice:a:older","text":"STOP_OLDER"}]}
```

这确认恢复了错误控制事实，不声称真实模型已据此错误恢复 Task 或发生外部副作用。独立 RuntimeClient 已 shutdown，临时 profile/data 已删除；没有读取或操作产品 reviewer 的隔离身份、服务、数据。

### 已核实与 retained

- `block(false)` 不再调用 followup；self stop 产生的协作通知只对 actor Agent 的持久 relay 标 context_only，其他接收者沿普通通知。PA needsAttention 优先返回 false；SingleThread 后续读取使用 inject，Global 仅 attention 为真才新 wake。普通 Task 通知/其他协作者和公开 stop 确认不被通用抑制。
- UI resume 的 reconsider 读取前后均允许有 passive pending context，但仍要求 runnable、真实责任变化和既有取消/拒绝屏障通过；纯暂停/删除保持空闲。冷恢复首 ordinary 的成功空责任快照进入真实模型输入；source unavailable 不冒充空责任。
- 在线写入已追踪：普通 Web/iOS/Agent execute 的 COMMIT→notifyChange，PA executeDelegated 的外层事务完成后 notifyChange，pauseExecution 的提交后 hint；changeHint 对改派/删除保留 before/after assignee 并集。群解散是独立直接 JSON 写路径，新 notifyChange 在事务完成后发给保留图的 assignee；Gateway→Node tasks.recover→native changed/pre-step 接线实际存在。迁移脚本不属于在线变更入口。
- 复用 `/tmp/nano-646-followup-green.log`，四 native/IM 文件 **32 passed**，02:56:11，17.64秒；读取 `/tmp/nano-646-followup-full.log`，本轮完整 **128 files / 656 passed**，02:56:53，107.68秒；caller 已完成 full build/typecheck。现有绿测没有双 stop 重入队时序，因此不能关闭本次直接复现 finding。
- canonical 冻结正文有 **18 Requirements / 37 Scenarios**，本 unit Gateway Task delta 有 **5 ADDED Requirements / 10 Scenarios**；752af9f86 的 gateway/spec.md Task Graphs 索引为18，与正文一致。新增 Requirement 正文与 delta一致；随后 main 合并现场出现的19不属于本轮冻结文档，留待下一轮集成核对。
- R1–R6 未受影响的 feedback/一小时waiting/实际投递/混合通知静默/审核模型兼容性与审批边界保留；旧“解fence自动唤醒”测试预期被本次用户新授权明确替换，不能继续当产品保证。R7–R9设计批准是契约来源，不代替上述实现检查与原生复现。

本轮 gate：1 条 P2 CONFIRMED 存活；需修后 targeted closure。没有额外未证实高风险候选。只追加本 unit 两份报告；未改被审实现/测试/配置/设计。

## Round 8 — latest-stop closure and main capability integration

- 固定source：`3bdcdc546a073c9503eadda6c57573547ceb45db`；patch base为R7 source `503498e1f`，报告 `7983dcac5` 已保留；main `63724d53f` 经 `d44a48792` 实际合入。2026-10-24 03:06 +08；同一独立 reviewer，未参与实现。
- 范围：R7 P2 closure、新main与本unit的Task Tool/Feature/feedback、配置依赖/占用保护、Schedule/stop/来源边界；不重新全量审查feat-645前端/其他Feature内部实现。起始只有未跟踪隔离配置；随后两canonical文件仅对齐元数据dirty，已逐行确认无契约改动，未修改或提交它们。

### Findings

```json
[]
```

### Focus finding closure

**R7 P2 — closed。** `task-execution.ts:184-195` 现按完整事件正序收集可信stop的首次出现，Set以稳定消息ID去重；重复restore不会改变接受顺序。最后一个首次接受的stop选定后，仅对它检查consumed/pending/current messages，没有因最新已消费而回溯旧stop的循环。原source/ID保持，未增加wake或额外持久队列。原生回归 `task-context-sync.test.ts:89-112` 使用与独立复现相同的older/newer→fence reject→逆序重入队→normal shutdown/restart→未来输入，实际断言只恢复newer。

读取 `/tmp/nano-646-stop-order-red.log`：**1 failed / 3 passed**，实际收到older而非newer，03:00:49，5.94秒。读取 `/tmp/nano-646-followup-integrated.log`：**7 files / 39 passed**，03:01:56，20.04秒；包含修后stop顺序、quiet release/冷恢复/UI resume、反馈Feature门控、IM入口与能力回归。既有单stop跨正常退出和第二次输入不重复保留；不重复运行同型绿测。

### 实际merge与契约边界

- **指导与工具分离正确合并。** `features/task-graphs.ts` 的完整646 Feature guidance 保留：事实推进、一小时waiting、Schedule重估、固定聊天、unknown诚实性、合法替代/非授权等没有被主线旧文本覆盖。工具移到registerTool常驻注册；`agent-config.ts:107` 的enabled回调读取执行Agent的 `forAgent` 当前/历史配置，成功apply的deferContext仅在Task Feature开启时发生，未以preset模板状态替代实际Agent选择。native feedback新增Feature=false手动tool用例证明普通调用成功、无task-feedback、无额外send；原三状态Feature=true仍实际反馈。
- **自动执行没有随tool独立而扩大。** driver enabled、PA snapshot/recover仍要求Task Feature；IM普通操作仅核工具/身份，execution/execution_scopes仍要求Feature，execution_pause保留宿主stop资格。新增IM用例同时断言Feature关闭后get可用而自动snapshot拒绝。Task工具可手动调用不等于自动责任、自动反馈或人工授权。
- **能力撤回不破坏持续责任。** main新增Task跨会话doing/waiting计数，在IM configuration gate拒绝撤回Task Feature/tool；save在配置pending期间拒绝新增加的active assignee，防止读用量与实际保存间漏过。此前paused/in_review等不阻止关闭，符合新canonical第19项Requirement。Node pendingConfigurations恢复、runtime prepare/apply reservation及current configuration回调接线存在；stop.cancel/inject/flush/block(false)不受新增工具占用门控而改成wake。
- **Cron依赖与waiting仍是实安排。** Task Feature依赖完整Cron+tool，manual Tool独立不启用自动指导；configureSchedules和schedule.wait.inspect按实际仍active的安排与会话核实，不因无关Feature开关伪造等待失效。IM一小时cap/receipt/固定聊天投影未改；Task自己的正常resume/recover继续走PA→driver最新scope。
- **其余冲突。** Global query的双方修复同为仅Global ensureAuthority，差别仅格式；SingleThread权限仍由IM。IM/native测试保留两边语义并集而非任选；新增capability pre-execute guard与原审批/source链并存，没有Task豁免。停止协作context_only、冷恢复tasks=[]和latest-stop逻辑没有被main覆盖。
- **文档并集。** 冻结canonical为Agent Capabilities **45 Requirements / 168 Scenarios**、Task **19 Requirements / 39 Scenarios**，入口索引45/19一致；本unitTask delta五个ADDED Requirement全部存在于canonical。主线新增Task责任占用保护与本unitpassive同步Requirement均保留，没有以覆盖一边消除冲突。后续两文件仅将“对齐: feat-645、bugfix-646”改成docs-check要求的单一bugfix-646，内容不变，可保留。

本轮0存活finding，R7 P2已关闭；集成build/typecheck由caller确认通过，适用39项测试已直接读取。全量后端与真实产品新栈结论由对应gate提供，不把进行中结果写成通过；前序未受影响范围保留，未启动或占用产品服务。仅append本unit两份报告，不改实现或其他报告。
