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
