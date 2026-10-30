# Verification Report: bugfix-678

> Validation snapshot: `9bf2b13da4005631096f2a49223564cd68647c3c → 21b8da0d315b63795775a84e20e1ef475f028f2a`

- review_round: 1
- verification_mode: `full`，附同次 delta reconciliation
- validated_at: `21b8da0d315b63795775a84e20e1ef475f028f2a`
- executed_base / effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_through: `21b8da0d315b63795775a84e20e1ef475f028f2a`
- requires_full_verification: `false`；这是完整首轮核查，后续按真实 fix delta 判断复验范围。
- verdict: **fail / 尚不可交付 PR**。实现路径大体遵循批准设计；1 个实际恢复缺陷，真实产品/模型验收及最终回归未完成。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现主体具备；R1–R8 的真实可见退出标准尚无完整验收证据，W2/W3/W5 未完成 |
| Correctness | 消息隔离、重试归属、冻结动作等机制有窄测试；unknown 主人提醒恢复存在确认缺陷 |
| Coherence | 审核入口/执行器/上下文职责遵守设计，包边界保持；日常图像能力前提不成立，需 owner 裁决 |

## Completeness

tasks.md 当前 5 项实现勾选、4 项交付/验收未勾选，状态与现场相符。此次独立静态报告不代替产品 reviewer 的真实旅程，也不将 source/test 映射记成 R1–R8 真实结果通过。没有 UI 原型/截图 must-match，Prototype/Reference 为 N/A。

| 退出项 | 直接证据 | 状态 |
|---|---|---|
| W1 最窄状态/Context/native retry | 审核专项 39 tests、PA 18 tests；本机 source/tests 核查；独立 unknown seam | 机制证据可复用，有新回归缺口 |
| W2 IM+Node 真模型 R1–R7 | progress.md 明示真实旅程尚未验收；本次没有产品验收报告 | 未完成 |
| W3 独立代码/Context 审查 | code-review.md，1 CONFIRMED WARNING | 未通过 |
| W4 迁移副本/文档 | pa-permission-migration/input-admission 测试覆盖 plan/apply/verify、重复与事务回滚；docs.log integrity passed | 机制已覆盖；升级后真实 PA 剩余处置仍依赖 W2/R8 |
| W5 入口盘点/构建/类型/契约回归 | build-frozen.log 目标 SHA、typecheck.log Done；pytest.log 113 passed/28 deselected；standalone/model-setup/native tests；最终 vitest 822 passed / 2 failed（154 files passed / 2 failed） | 未完成 |

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 单次拒绝不建立隐藏 Task 限制；Agent 显式暂停/等待 | task-execution.ts 删除 denied map 与 tools/result/approval 拒绝监听，runnable 仅按显式任务；policy/approval.ts 分类 block/unavailable | task-execution.test.ts；原生审核故障测试 | 机制 covered；R1 真模型可见状态待验 |
| Codex 原生 read/read_image/glob/grep，禁止 Bash/写入/委派 | policy/codex-inspection.ts:inspectionTools；review-session.ts:create scope allowlist/guard | codex-approval-native.test.ts 实际 schema/长文件/输出捕获 | 文本机制 covered；日常 read_image 能力受阻，R2 未完成 |
| 完整原话/问答/来源/撤回；fork/rebuild 按实际历史补送 | retained-instructions.ts:retainInstructions/retainedEnvelope；codex.ts:review；approval.ts 委派保留证据 | retained-instructions.test.ts；codex-approval lifecycle/native 测试 | 机制 covered；真实长任务行为待验 |
| 单消息拒绝/故障，重复/重启终态，显式重审 | inbox-review.ts；personal-assistant.ts:admit；global-agent.ts:restorePersonalInputs/deliverReviewFailures/inbox review；inbox.ts:entries | input-admission.test.ts；personal-assistant.test.ts | covered；R3 真模型显式调用待验 |
| 当前+前20条+窗口外reply，超限整条、省略明确 | personal-input-context.ts:personalInputContext；personal-security.ts:inputReviewEvidence | personal-input-context.test.ts；personal-security.test.ts | covered；输入附件明确 unavailable，未伪称已审核 |
| PA 自行先提醒主人、后原聊天拒绝，有限授权与真实回执 | personal-agent.ts:incident/incidentRead/incidentReceipt；global-agent.ts:recoverPersonalObservations；personal-assistant.ts:send | personal-disclosure/personal-assistant tests；独立 ACK 丢失 seam | **implementation-mismatch**：unknown 主人回执不可恢复；R4 未通过 |
| 删除 disclosure_revision/60s；真实变化未发送、一次性消费 | personal-actions.ts:validate/review/commitChecked/commit；PA send/task/external | personal-disclosure.test.ts、personal-images.test.ts | 删除与冻结校验 covered；不得据此声称 R5 真实旅程通过 |
| 图像完整受审、实际请求全图、提交同字节，能力不足准确故障 | personal-images.ts；personal-actions.ts:prepareChecked/validate/commit；personal-security.ts:personalReviewImages；review-session.ts:run/llm-stream manifest guard | personal-images.test.ts；codex-approval-native.test.ts:151（自带 pricing fixture） | 故障/装配机制 covered；现用路由成功图片路径无法满足，R6 未完成 |
| 原生恢复与 standalone 不叠加，缓冲部分流、共享额度、取消 | standalone-model-retry.ts:installStandaloneModelRetry；classifier.ts；model-setup.ts；web.ts；index.ts；review-session.ts request-error | standalone-model-retry.test.ts；model-setup/model-policy；原生审核测试含故障/取消/副作用 | 机制 covered；R7 真模型/全用途退出证据未完整 |
| 升级旧终态/未知回执/凭证，重复应用/中断回滚 | migrate-pa-permissions.ts；migrate-input-review.ts；inbox-review.ts:migrate；deployment-prompt.md | pa-permission-migration.test.ts；input-admission.test.ts；Python 合同测试 | 迁移机制 covered；R8 剩余事件真实处置与 unknown 恢复未通过 |

## Coherence

| Design 决策 | 遵守? | 代码证据 |
|---|---|---|
| A 审核约束动作，Task 依据显式状态 | 是 | task-execution.ts 删除拒绝推断；原权限 guard 保留 |
| B 原生四工具与独立 reviewer scope | 是，图像能力受现用路由限制 | codex-inspection.ts；review-session.ts:create |
| C 有界原话独立保留与实际可见性补送 | 是 | retained-instructions.ts；codex.ts；sources.ts 不将保留原话重复投影普通 history |
| D 审核入口/执行器/context 分责；DSH 持有 Loop | 是 | codex.ts / review-session.ts / codex-context.ts；原生 request-error next；无 private import/fork |
| 消息级准入及故障交 PA，不后台重审 | 是 | InboxReviews generation/state；Global 显式 review 与故障事件 |
| 事件由 PA 沟通、查询回执后恢复 | 部分偏离 | stable incident publication/实际回执已接；sending/unknown 缺主人投递事实查询 |
| 图片公开计费与全图完整输入 | 安全故障语义符合；现用路由正向能力缺失 | review-session.ts:91-98；Pi-AI 无公开 imageRequestPricing |
| 仅缺失入口接 standalone，Agent 原生恢复保留 | 是 | middleware isAgentLoopRequest/WeakSet；classifier 两阶段共用 budget；未替换 cordis llm-retry |
| 生产只读迁移/健康，隔离功能验收 | 是 | 部署提示词与副本测试；本审查未操作生产/起栈 |

### Prototype / Reference Contract

N/A，design 无前端原型或 must-match。

## Issues

### CRITICAL

- **V1 / CONFIRMED，缺退出证据及现用图像能力前提**：design.md:304-312 要求 R1–R8 真实结果、W2 真模型端到端；当前 tasks/progress 仍未完成。尤其 R2/read_image 与 R6 图片正向路径在日常 Codex OAuth/Pi-AI 因缺公开 imageRequestPricing 明确 unavailable（review-session.ts:93,97），fixture adapter 自行提供 512 visualTokens 只能证明装配机制。owner 已向用户询问是否扩展图像预算适配，本审查不豁免批准契约。建议取得范围裁决；若扩展则先对齐设计/独立复审，随后补真实请求与真实授权成功/含私人信息拒绝证据。其余 R1–R7 按产品 reviewer 真实可见结果补齐，R8 副本升级后处置也需闭环。此项区分设计/能力前提、行为未验证，不声称已观察到模型误判。

### WARNING

- **V2 / CONFIRMED，unknown 主人提醒恢复缺失**：personal-assistant.ts:158 与 global-agent.ts:348、inbox.ts:408。完整触发、影响、宿主查询修复建议和独立复现见 code-review.md 唯一 finding。违反 design.md:196、207 及 PA delta“暂停与发送结果未知”。建议恢复原 operation 的真实回执并绑定 incident；禁止用新 key 重发。修复后做针对性 closure，复用未受影响机制证据。
- **V3 / CONFIRMED，最终回归未完成**：design.md:312 W5。`/tmp/bugfix678-vitest-final.log` 最终 822 passed / 2 failed（154 files passed / 2 failed）：knowledge-review 等待 held 状态未取得；workflow-native 40 秒超时。不能把此前窄复跑或 Python 通过替代全量 TypeScript。建议 owner 先定位这次实际失败，完成适用回归并记录固定版本/命令/终态；不从本日志推断产品根因或提出猜测修复。

### SUGGESTION

None。

## Corrected Delta Reconciliation

同次核对全部现有 delta，未修改 spec 迎合实现。

| Delta item | Implementation / test evidence | Outcome |
|---|---|---|
| specs/gateway/task-graphs.md 拒绝不建隐藏任务屏障与故障屏障修订 | task-execution.ts / task-execution.test.ts | aligned（机制），产品证据待完成 |
| specs/gateway/agent-capabilities.md 四工具、保留原话、恢复归属及普通审批上下文修订 | codex/retained/standalone/classifier + native/lifecycle/standalone tests | aligned（受支持能力）；R2 图像路由前提待裁决 |
| specs/gateway/personal-agent.md 单消息、原始背景、PA 实际处置 | InboxReviews/input context/incident/PA send；input-admission/personal-disclosure tests | **implementation-mismatch**（unknown 恢复 V2） |
| specs/gateway/personal-agent.md 凭证只随条件变化、完整图片受审 | PersonalActions/frozen images/review-session；personal-images/native image fixture | aligned（机制/安全故障）；R6 正向能力与行为证据未完成 |

### Uncovered Observable Behavior

未发现 unit diff 中需要另建产品 delta 的遗漏行为：消息级准入、事件处置、凭证、图片、Task/恢复行为已分别覆盖；审核局部职责重构为 no spec delta；一次性迁移由 deployment-prompt 维护。当前缺陷应修实现；图像能力问题需 owner 裁决，不能静默缩小 delta。

Outcome: **implementation-mismatch**。

## Evidence provenance and handoff

复用 caller 在固定目标树声明的审核 5 files/39 tests、PA 18 tests；核对永久测试与日志以确定证据层级。构建 `/tmp/bugfix678-build-frozen.log` 明确绑定 validated_at；typecheck `/tmp/bugfix678-typecheck.log` Done；Python `/tmp/bugfix678-pytest.log` 113 passed/28 deselected；文档 `/tmp/bugfix678-docs.log` integrity passed。初次 build.log 显示旧 SHA，因此版本结论采用 frozen build。最终全量日志已结束，2 个失败未解决；本次不推断其根因。

独立补核 `/tmp/bugfix678-static-review/review.test.ts`，命令 `pnpm exec vitest run --config /tmp/bugfix678-static-review/vitest.config.mjs --maxWorkers 1`，`repro.log` 2 tests passed。其一反证生命周期候选（schema trigger 自动注入 revision3），其二确认 ACK 丢失无回执查询。使用内存 DB 与可控 transport，无新服务、无真实模型、无生产变更。没有源码/测试/设计修改，也未提交；报告由共享现场 owner 提交。已有 `.bugfix678-runtime-sha` 未触碰。后续改动的结论延伸须另做 delta 失效判断。

1 critical issue, 2 warnings found. Fix and complete required evidence before PR.

## Round 2 — Targeted closure and corrected delta

> Validation snapshot: `21b8da0d315b63795775a84e20e1ef475f028f2a → 80941dfd6afcd181536a08da1b0762051ee98b11`

- review_round: 2
- verification_mode: `targeted-closure`，附受影响 corrected-delta 核对
- validated_at: `80941dfd6afcd181536a08da1b0762051ee98b11`
- executed_base / effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_through: `80941dfd6afcd181536a08da1b0762051ee98b11`
- fix_delta_range: `21b8da0d3..80941dfd6`
- focus_issues: Round 1 V2；V1 中被用户纠偏的 pricing 前提；V3 的窄失败复核状态。
- requires_full_verification: `false`。共享权限、冻结资源、消息准入和恢复 owner 未变化；未受影响 Round 1 结论 retained。
- scoped_verdict: **pass / 静态实现及受影响 delta aligned**，0 新 CRITICAL / 0 新 WARNING。
- overall_delivery: **pending**，真实产品验收与最终全量结果仍待 owner 完成，非 Ready PR 结论。

### Reconciliation of prior issues

| 既有项 | 当前结论 | 直接证据及边界 |
|---|---|---|
| V1 的 pricing 能力前提 | **superseded** | 用户明确要求沿主 Agent 图片路径；design `5789ce9ef`，Gate 2 Round 4 Approved 0/0。pricing 接口存在与否不再是批准要求，不需要额外估算适配或更换 Luna |
| V1 的 R1–R8 / W2 真实退出证据 | **pending** | 此次只核静态 patch；产品 reviewer 正在完成既有旅程，新版本 R4/R6 待针对性验收。没有把 fixture 响应记为真实模型结果 |
| V2 unknown 主人提醒回执 | **closed** | `personal-assistant.ts:158–168` 查询原 operation 的 host status，确认消息/会话后绑定 receipt；found=false 不重发；`:179–182` 能在绑定中断后补绑定。code-review Round 2 关闭原 CONFIRMED finding |
| V3 knowledge-review/workflow-native 的窄失败 | **复跑通过；最终全量 pending** | `/tmp/bugfix678-runtime-repro.log` 2 files / 5 tests passed。只说明同两测试在安静单 worker 环境通过，不证明最终全量稳定性或失败根因 |

### Correctness and coherence of the fix delta

| 受影响契约 | 实现及直接保护 | 结果 |
|---|---|---|
| design.md 原生图片 admission → followup → runtime/adapter | `personal-security.ts:78–93` 调同一公开 admitPromptContent；`review-session.ts:115–117` 原生 followup，与主 Agent `index.ts:861` 一致；原 pricing/imageCost 删除 | aligned |
| 当前 pending 图完整性，不能占位/offload/丢图后 allow | `review-session.ts:219–225` 核对本 inputId 的全部图片数量、引用及 offloaded；freeze/hash/提交同字节路径无变化 | aligned，未放宽既有保护 |
| 实际超限准确失败及一次携图重建 | `review-session.ts:191–206` 保留文本预算/typed context rebuild，既有 loop 重建仍复用冻结 plan.images；没有增加恢复 owner/额度 | aligned；真实模型超限行为证据仍属后续验收 |
| 未知主人提醒查原回执，不当失败重发 | PA send 的 status 查询及绑定；系统事件/结果说明同 incident_ref/target 的真实查询入口 | aligned；ACK lost 参数化 true/false 回归保护 |
| limited incident authority、先主人后原聊天、独立披露 | 修复只查询宿主事实并绑定真实 receipt；原 `incidentRead`/`securityNotice`/外发审核与目标限制保持 | aligned |

### Corrected delta outcome

既有 canonical delta 未要求图片 token 预估或 imageRequestPricing。`specs/gateway/personal-agent.md` 的“实际消费待发图片 / 能力或材料不足”仍要求真实 image input、同字节发送和准确故障，修正 design 及本 patch 均与之相符；删除 author 额外门槛无需反向缩小 delta。`specs/gateway/agent-capabilities.md` 的原生 read_image 调查与恢复要求也保留。V2 修复使 PA delta“暂停与发送结果未知”的实现偏离关闭。

Uncovered observable behavior: **None in this patch**。同 incident_ref/target 再调用用作回执查询属于原未知状态恢复契约的具体入口，不新增发送授权或产品动作。

Outcome: **aligned**（限定修复 delta）。Round 1 旧 implementation-mismatch 在该固定目标上的 V2 原因已关闭；完整 unit 的真实产品/最终回归证据仍 pending，不静默改 spec，也不因待补日志重复全 unit 静态审查。

### Evidence and handoff

复用 caller 的 red→green 证据：`/tmp/bugfix678-native-image-green.log` 3 files / 32 tests passed；对应 fixture 已删除 optional pricing，经过真实 DSH 子进程捕获 full/delta/fresh 当前图片数量。`/tmp/bugfix678-runtime-repro.log` 2 files / 5 tests passed。按风险保留这些有效窄证据，本轮未重跑全量或重新起栈。新版本真实模型/IM 两端回执与全量日志由 owner 后续补齐；无需为纯证据补入第三轮完整静态审查，有新实质 delta 才按影响复核。

报告追加保留 Round 1 历史；仅写 code-review/verification，未改源码、测试、设计或生产。共享现场由 owner 提交报告，report_commit 尚未产生；不触碰已有未跟踪 regression.md。

## Round 3 — Final evidence closure

> Validation snapshot: `80941dfd6afcd181536a08da1b0762051ee98b11 → 41a315eb972616176dbce2b6f3146715b578ed8e`

- review_round: 3
- verification_mode: `targeted-closure`
- validated_at: `41a315eb972616176dbce2b6f3146715b578ed8e`
- executed_base / effective_base: `9bf2b13da4005631096f2a49223564cd68647c3c`
- effective_through: `41a315eb972616176dbce2b6f3146715b578ed8e`
- fix_delta_range: `80941dfd6..41a315eb9`
- focus_issues: Round 1 V1 剩余 R1–R8/W2 退出证据、V3 最终全量；V2 与 corrected delta 沿用 Round 2 闭环。
- requires_full_verification: `false`
- verdict: **pass**，0 CRITICAL / 0 WARNING / 0 SUGGESTION。完整 unit 的实现及适用退出证据已成立，可进入 current spec 归并、归档及 PR 收尾；本结论不代表已创建 PR、远端 CI 通过、合入或部署。

### Scope and retained source review

直接核对 HEAD 为 validated_at、main 为 executed_base，checkout 干净。`git diff --name-only 80941dfd6..41a315eb9` 只有本 unit 的 code-review、verification、regression、supplemental-validation、progress、tasks 六份 Markdown；源码、测试、配置、design、delta-spec 均未改变。因此 Round 2 code-review `findings=[]`、unknown 主人回执 finding closed、Context Implementation Review 和 corrected-delta **aligned** 均 retained，有效延伸到本次固定目标；没有重做无变化代码审查或全量测试。

此次核查独立产品 reviewer 提交 `4636bc606` 的 `regression.md` Round 2、`evidence/supplemental-validation.md`，并直接读其关键原始 locator 和最终日志。覆盖按真实 Web 旅程、真实 DSH/宿主服务接缝及确定性故障注入区分；不以测试总数或实施者摘要替代未观察的产品事实。

### R1–R8 exit evidence

| 退出项 | 本轮核查的证据及来源边界 | 结论 |
|---|---|---|
| R1 工具拒绝后继续合法工作、显式暂停 | regression Round 2 旅程9：真实 hard_deny 的 write 为 Denied / Not executed，A2 Paused、B2 Done，受限文件保持 KEEP-UNCHANGED-678、合法产物 ALLOWED-ROUND2；`/tmp/bugfix678-product-review/round2-r1-work.txt` 与 result.txt 可复查。技术故障见旅程3/8；人工拒绝由原生确定性测试保护，不冒称此次 Web 点击拒绝 | pass |
| R2 长文件、原委托与撤回 | 旅程5/7：503 行文件末尾、同 child 的逐字委派和后续撤回，`round2-r2-withdrawal.txt` 中原许可与撤回分清，PUBLIC-678 产物保留；四工具、实际 reviewer 输入和 full/delta/fork/rebuild/重启机制由已核原生测试及本次全量通过补齐，未把主执行者 read 当作 reviewer read | pass |
| R3 单消息隔离、故障显式重审 | 旅程8/11：原生轨迹 `round2-r3-native-review.txt:133–138` 真实 inbox review 返回 failed/review_unavailable、other_admitted_inputs_available=true，check generation=2；主人后续合法任务实际完成。同群风险单条拒绝后消息 `18fa31b4e6b343298a603e3f444280df` completed；20条/reply/恢复/重复状态由机制测试保护 | pass |
| R4 主 PA 先提醒、后原聊天拒绝，回执恢复不重发 | 实读 round2-final-owner.json/group.json：主人提醒 `399314c3b2964f908e018e1b4ce2673a` 于15:24:51.274Z completed，原聊天拒绝 `00b9ec07bbfb4c42a5b876cc9b09692c` 于15:25:04.375Z completed，措辞没有私人事实；R8 原始证据含真实 Astra send_message → host status → receipt 绑定且消息数不增加。停用/失败分支沿用机制保护 | pass |
| R5 独立许可、超过60秒与真实条件变化 | 直接核对 `/tmp/bugfix678-r5/evidence.json`：Luna A/B/C allow 为 full/delta/delta，任何提交前 A/B 已获许可；64,410ms/62,061ms 后分别 confirmed，两个消息 completed；主人新消息后 C 为 not_sent/owner_already_replied。UI正常连续发送另有旅程1；这是服务接缝+真实模型补证，非额外 Web 全链路声称 | pass |
| R6 原生图片真实送达、未授权图不泄露及同字节 | 旅程6：原蓝图真实送达，直接核对 round2-image-hashes.json，源/目标均96 bytes、SHA256均 f373227cd29539cf4bbc07c25280412e18f3125ff76c510a329b92d3a1518372。PRIVATE 原图在真实 PA/输入边界被拒，`round2-r6-private-boundary.txt` 明确不能外发整图；不声称该拒绝一定发生在最终 disclosure proposal 阶段。冻结完整图的实际请求及能力错误由已核原生专项保护，旧 pricing unavailable 是已修历史故障 | pass |
| R7 匹配入口的恢复、取消、耗尽与无重复副作用 | supplemental 矩阵逐项列普通/子/Workflow/知识记忆 Agent、Codex reviewer、CC/legacy/input、网页、模型验证及 BasicCompaction 入口；本仓四类直接 stream 出口与已核实现相符。日常主/子/审核真实模型成功与 native-runtime 确定性503/取消/耗尽/部分流注入分开；Loop标记、共享预算、重入、90秒窗口、checkpoint/timer及副作用已有专项和全量保护，不声称对真实供应商逐项人为故障演练 | pass |
| R8 副本升级、原回执、幂等与未完成恢复 | 直接核对 `/tmp/bugfix678-r8/evidence.json`：两迁移CLI均 plan/apply/apply/verify，verified=true；真实 Astra 调用 send_message 后 host status 查询原 operation、绑定既有主人回执，publication unknown→confirmed，pending清空，消息47→47。数据来自隔离副本、非生产；额外 task_graph harness 不支持错误未被误记为任务通过。中断/回滚/旧allowed失效由本轮通过的永久迁移测试保护 | pass |

### W1–W5 and final regression

| 工作退出项 | 核查结论 |
|---|---|
| W1 最窄机制及 Context 保护 | retained，相关专项均纳入最终后端全量；不以 fixture 响应替代真实模型旅程 |
| W2 隔离 IM+Node 真模型与必要故障补证 | 独立 regression Round 2 R1–R8 均 pass、0 issues；代表性 Web 旅程与真实服务接缝、故障注入的组合覆盖批准退出要求，边界如上 |
| W3 独立静态/Context 审查 | code-review Round 2 pass、V2 closed、corrected delta aligned，源码未变 retained |
| W4 部署副本及文档 | 副本两CLI重复应用/verify、真实未完成事件恢复，加永久回滚测试与 docs integrity passed；无生产功能测试 |
| W5 入口盘点、构建/类型/相关回归与清理 | 已完整提供并独立抽核下列日志和原始 JSON；清理记录与现场只读检查相符 |

- `/tmp/bugfix678-build-final.log` 成功，产物明确绑定 `80941dfd6afcd181536a08da1b0762051ee98b11`；该实现树与本次目标源码相同。`/tmp/bugfix678-typecheck-final.log` 各包 Done。
- `pnpm exec vitest run --maxWorkers=2` 的 `/tmp/bugfix678-vitest-round3.log`：156 files / 826 tests passed，242.17s。直接解析同名 JSON：success=true、826 passed、0 failed；其内部 suite 分组统计为178，不与 CLI 的156个文件口径混用。Round 1 两次失败事实保留，最终本轮全量已通过。
- `/tmp/bugfix678-frontend.log`：108 files / 1029 tests passed；`/tmp/bugfix678-pytest.log`：113 passed / 28 deselected；docs integrity、Ruff check/format 与 packaged iOS runtime 检查日志通过。没有 iOS源码改动，不扩展为真实设备或真实Feishu视觉验收。critical审计阈值通过；已记录既有5项high，非本次新增，不隐去审计边界。
- supplemental 记录超时遗留的专属 workflow 进程组已清理、日常 e2e-down STOPPED、专用 tmux 关闭。此次只读 `lsof` 核对58487无监听，`ps` 核对13000/31071/31077/31296均不存在；未重新启动服务。

### Final issue closure

| 历史项 | 最终状态 |
|---|---|
| V1 pricing 前提 | superseded，沿 Round 2 用户纠偏及批准设计；未恢复为门槛 |
| V1 剩余真实旅程/退出证据 | **closed**，独立产品裁决与以上可复查原始/机制证据补齐 |
| V2 unknown 主人提醒恢复 | **closed / retained**，Round 2修复审查不失效；R8真实模型补证进一步确认原消息不重复 |
| V3 最终全量 | **closed**，最终826后端测试通过；保留此前失败与窄复跑历史，不以窄通过替代最终全量 |

没有新增实现或设计问题；corrected-delta **aligned** 延伸至 effective_through，无 uncovered observable behavior。报告只追加本 Round 3；源码、设计、spec及其他报告未修改，未提交/推送。后续 owner 同步勾选交付记录、归并 current spec/归档并按文档变化跑相应检查；若此后只有文档收尾，不要求第三次完整静态审查或重跑未变化源码的全量测试。

All verification checks passed for this fixed tree. Ready for PR closeout after the documented spec merge and archive steps.


## 2026-10-30 targeted delta consistency

独立静态审查者 `per_message_review` 同次受派 code review 与定向一致性核对，validated_at=`6e80670e3`，范围 `14964ba653..6e80670e3`。结论 **pass / aligned**，0 CRITICAL / 0 WARNING：逐条 deny 交付主 PA 的原需求落实到独立持久事件与回执；联系人摘要聚合保留在现有 UI，design 澄清、delta/current spec 同步，无新增权限、API、schema 或运行时边界。自身标签修复不改变真实 sender 或授权语义。历史聚合记录不重放，已保存回执不清除。未变 R1/R2/R3 准入/R5/R6/R7/R8 机制证据 retained；R4 连续沟通与身份体验由 regression Round 4 单独复验，不能以静态一致性代替产品通过。
