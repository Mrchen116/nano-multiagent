# Verification Report: feat-635

> Validation snapshot: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a → e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0`

## Summary

- review_round: 1
- verification_mode: full；同时核对全部 corrected delta。
- branch / worktree: `unit/feat-635` / `/Users/czj/.codex/worktrees/unit-feat-635/nano-multiagent`
- verdict: **not-pass**；0 CRITICAL / 3 WARNING / 0 SUGGESTION。
- requires_full_verification: false。本轮全量静态范围已完成，后续可针对发现与 fix delta 复验。
- 产品 must-match 证据仍 **pending/inconclusive**，不能据本报告宣布 M1 全部验收通过。
- report_commit: caller 统一提交；本角色未提交、未改变 HEAD。

| 维度 | 结果 |
|---|---|
| Completeness | 全部 11 Requirement / 30 Scenario、M1 R1–R7 / W1–W4 已核对；功能骨架存在，W2 回归保护有缺口，W3 产品证据 pending |
| Correctness | 两个恢复分支有可复现 implementation mismatch；其余已读实现未见确定偏离，不将实现存在等同于产品验收通过 |
| Coherence | IM 唯一真相、PA scope、公开 DSH 生命周期、独立 Schedule、Goal opt-in 均遵守；故障恢复和能力重新开启两个分支偏离目标 |

## Scope and Evidence

读取仓库 AGENTS、docs/README、SPEC、current IM/Gateway Task 与能力契约、testing 规范、两项 skill、validation/handoff/template，以及本 unit spec/design/全部四份 delta。审查固定完整 diff 的 63 个文件及直接调用方。初始 HEAD 与 validated_at 相同、工作树干净；角色仅新增本报告和 code-review.md。

复用 caller 指定且经源码核对仍适用的证据：

| Evidence | 结论与边界 |
|---|---|
| `evidence/implementation-validation.md` | 等待原子保存、PA 审核后核验、真 Web waiting 与暂停/Goal 操作、审批及静默；实施证据不替代独立产品验收 |
| `/tmp/feat635-frozen-build.log`、`/tmp/feat635-frozen-typecheck.log` | 构建与类型检查成功；build 明确包含受审 SHA |
| `/tmp/feat635-frozen-backend-bounded.log` | caller 确认最终固定源码 `pnpm exec vitest run --maxWorkers=2`：119 files / 552 tests PASS，267.16s；默认并发曾使 workspace-tools 90s timeout，未修改 timeout |
| `/tmp/feat635-policy-green.log` | 原生两类拒绝屏障及最后结果 3 pass |
| `/tmp/feat635-web-full.log`、`/tmp/feat635-web-final-narrow.log` | Web 960 pass；最后窄范围 24 pass。只证明自动化行为，不证明实际 viewport/触控 |
| `/tmp/feat635-pytest.log` | 62 passed / 31 deselected，包含非 E2E 架构与工具检查，不是生产链验收 |
| `/tmp/feat635-ios-final-test.log`、`/tmp/feat635-ios-final-archive.log` | Swift 43 tests、Release archive 成功；真实网络兼容和 UI 仍需真驱动 |
| 三张现有 `evidence/*waiting-detail.png` / `ios-goal-saved.png` | 已实际查看；支持业务原因、保存时间、执行 unknown、原生 sheet 及保存反馈。iOS Goal 图只展示保存反馈，不展示开关位置；三图不足以证明全部 must-match |
| `/tmp/feat635-review-config-recovery.log` | 本角色真实锁定 DSH 子进程复现 F1：失败后配置恢复，模型请求仍 1、idle。详见 code-review.md |
| `/tmp/feat635-review-enable-recovery.log` | 本角色实际 PA 协调器/NodeStore 复现 F2：开启后只发 changed、binding 仍为空。详见 code-review.md |

未为重复已有有效证据重跑全套。临时复现在 /tmp，自己的 DSH home 已在 finally 清理；没有启动 Web/iOS 或生产服务。产品 reviewer 的长旅程尚在进行，未完成结果不预先计 pass。

## Completeness

简化流程不要求 tasks/progress；M1 为共同闭环，不能仅因代码存在宣布完成。

| M1 Exit | 实现和直接证据 | 结论 |
|---|---|---|
| R1 五组/分页/全层责任/todo | Web task-progress.tsx:9,42,53；iOS TaskModels.swift:128；IM task-graphs.ts:804,900；IM 55 项跨页、Web 根/层级测试 | 代码与自动化覆盖；真实多树/他人/Global 跨聊天及 viewport pending |
| R2 waiting/运行分离、提前答复/到期/失效/离线 | IM task-graphs.ts:483,860；PA task-execution.ts:25；两端 TaskWait/Runtime；有效等待真实图 | 实现存在；提前答复、真实到期再安排、删除/失效旅程 pending |
| R3 原生纵向/sheet/安全区/关闭 | iOS TasksView.swift、TaskPresentation.swift；waiting 图、构建测试 | 390/430、长原因与返回位置待补，不主观评分 |
| R4 Goal 默认关闭/下一轮生效 | features/goal.ts:16、capabilities.ts:27,61、agent-config.ts:117,132；native Goal 测试与两端回读记录 | 自动化及部分产品证据成立；完整对照 pending |
| R5 持续/父整合/退出、自动审批/结果/故障/静默 | Driver task-execution.ts:38,56,110；SingleThread single-thread.ts:211,232,322,344 | 第二轮及审批/静默有直接证据；父整合和完整故障产品证据 pending |
| R6 scope stop/restart/reassign/旧提醒/自然恢复/运行中 A/B | PA task-execution.ts:58；IM task-graphs.ts:814；Driver task-execution.ts:132,142 | stop UI、模拟持久恢复、server 未知写等待有证据；native 组合缺口 W3；产品长旅程 pending |
| R7 故障真实/无热循环/无预算/换窗 | Driver 错误/拒绝屏障与配置接线 | F1 配置恢复失败；没有 Task 专属轮数预算 |
| W1 原子性/核验/幂等/范围/owner | IM tests/task-execution、personal-disclosure:239；PA tests/task-execution；Cron inspect | 大部分 covered；实际双 Agent 改派整体接续 pending |
| W2 公开生命周期竞态/恢复及构建 | native Task 3 tests、Cron/Goal；IM stop-write、PA stop fake runtime；最终构建/测试 | 部分覆盖，缺关键 native 组合回归 W3；模块各自测试不能称为完整 IM/PA/DSH 跨栈 |
| W3 原型逐项真 Web/iOS 对照 | 三张代表图、进行中的独立验收 | pending/inconclusive |
| W4 真栈/delta/清理/限定提交 | 实施记录、带版本构建、全部 delta | delta 有 F1/F2 实现不符；current 归并、主栈清理由 caller 后续收口，不将正常收尾报为代码缺陷 |

## Correctness

逐项覆盖首文档全部 30 个 Scenario。短文件名在对应包内唯一，行号为受审版本。covered 表示实现与适用自动化证据，不包含未完成的独立产品体验结论。

| Requirement / Scenario（spec.md） | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| doing / 已开工不反复催促（481） | IM task-graphs:804；PA task-execution:79；Driver:110 | IM 55 项、native continuation | covered，重新开启见 F2 |
| doing / 多项自主安排（486） | IM task-graphs:570,900；Driver:91 | 全深度/跨页、完整 prompt 集合 | covered；产品跨树选择 pending |
| doing / todo 与开始区别（490） | IM task-graphs:572 | IM todo 保留、既有 claim | covered |
| waiting / 等预算（496） | IM task-graphs:483,779；PA task-execution:46 | IM/PA 核验、真实 waiting revision 4 | covered |
| waiting / 全等与部分推进（501） | PA task-execution:25；Driver:119 | PA quiescent/continue | covered |
| waiting / 无安排拒绝（505） | IM task-graphs:483；Runtime index:512 | invalid、owner、native 过期、审核后拒绝 | covered |
| waiting / 后续失效（509） | PA task-execution:36,94；Driver:119 | session mismatch/invalid/cron-disabled | covered 模块级；native 组合回归待补 |
| waiting / 询问未送达（513） | features/task-graphs:9；原发送结果 | 实施 invalid_scope 未伪造 waiting | 指导存在；未新增消息语义评分器 |
| 消息/定时 / 提前答复（519） | 既有 Inbox；Task prompt；apply 清 wait | 既有输入链、状态清除 | 实现可达；真模型提前恢复 pending |
| 消息/定时 / 到期仍未满足（523） | Runtime inspect；PA snapshot；tool guidance | Cron 消费/无效/有效检查 | 真实到期与新关联 pending |
| 消息/定时 / 旧提醒不重开（527） | features/task-graphs:9；Driver:91；applyOperations | 状态过滤、wait 清除 | 组合测试缺口 W3，不推测必重开 |
| 页面 / 同组状态独立（533） | Web task-progress:42,53；iOS TaskModels:132 | Web 5 栏/动作、iOS contracts | covered |
| 页面 / A 等 B 工作（537） | Web task-wait:21；iOS TaskPresentation:32 | Work 状态与 waiting 分离 | covered；产品多任务图 pending |
| 页面 / 离线（541） | 两端 runtime view | Web query 断线/错误测试 | covered；原生实际离线对照 pending |
| 用户暂停 / 单项暂停（547） | IM notifyChange；Driver:132,38 | Web/iOS 暂停；native A/B 缺口 | 实现可达；W3 |
| 用户暂停 / stop 范围（551） | PA task-execution:58；IM task-graphs:814 | scope/idempotency/server pending write、PA durable control | 模块 covered；native restart W3 |
| 用户暂停 / 自然语言恢复（556） | 普通 input + task_graph apply | 无固定恢复命令门禁 | 实现可达；真实模型 pending |
| 交付 / done/review（562） | IM 状态过滤；Driver:56；SingleThread drain | native 末项退出保留结果 | covered |
| 交付 / 返工（566） | 既有 applyOperations change_note | 既有 rework/claim tests | covered |
| 改派 / doing 转移（572） | IM notifyChange:856；Driver changed:132 | 旧新 agent_ids、scope filter | 实现可达；实际双 Agent pending |
| 改派 / waiting/paused（576） | prepareWaits 保留原 wait；PA owner/session 比较 | previous session invalid、状态保留 | 模块 covered；实际改派 pending |
| 父责任 / 委派后整体交付（582） | 全层责任、Task guidance、原有通知 | 深层查询、既有通知 tests | 真模型父整合 pending |
| 父责任 / 逐层通知（586） | taskNotices；pauseExecution:838 | 既有 notifications 保护 | covered，无整树强停 |
| 父责任 / 不机械开后继（590） | 无 DAG scheduler；责任按 owner/status | 既有结构契约、todo 不开工 | covered |
| 中断 / 重启断线恢复（596） | main onReady/ready；PA recoverStops/recover | PA 模拟恢复、native cancel | F1 恢复错误；其余旅程 pending |
| 中断 / 正常换窗（601） | 仅 idle/pre-step 驱动，不改 Task 状态 | 既有 compaction、无 rollover hook | 静态一致；真实换窗 pending |
| 多轮 / 无专属预算（607） | Driver 无 round/token counter | native 多轮与代码核对 | covered |
| 多轮 / 运行条件不可用（611） | interrupted/limited；modelNotices | 本角色 native failure→config recovery | implementation mismatch F1 |
| Goal / 默认关闭（617） | ToolSelection、goal pre-step、prompt filter | native 旧新/child/legacy allowlist | covered |
| Goal / 主动开关（621） | 两端联动、runtime next-turn gate | busy config/竞争输入、真实两端保存 | covered；完整对照 pending |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 七状态/五组、运行态分离 | 是 | IM validateDocument:127、counts:341；Web task-progress:42；iOS taskGroups:129；runtime view |
| IM 唯一状态、全部直接责任、无 DAG 调度 | 是 | task-graphs:804,900；product-contracts 纯 DTO；PA 不存 Task 副本 |
| native idle/pre-step/followup/steer，根 binding 驱动 | 是 | Driver:21,38,110,132；无第二执行 loop |
| waiting 真实 Schedule、事务外查/事务内重查 | 是 | task-graphs:483,779；personal-actions:153；Runtime index:512 |
| 来源、权限/PA 审核不绕过 | 是 | nano-system；commitChecked 先核 reviewed operation 再核 Schedule；无伪造 nano-human |
| 持久 stop/屏障/排空远端写/原子暂停 | 是，组合回归不足 | PA:58；main productCalls；Gateway:389；IM pauseExecution:814 |
| 无预算、故障恢复后接续 | 否 F1 | Driver:123 将配置恢复和重复提示使用同一 Task 指纹屏障 |
| Task 重新开启按当前责任检查 | 否 F2 | main:361 仅 changed，无 binding 无法发现责任 |
| Goal 独立 opt-in、公开 export/disarm | 是 | package 显式锁定 dsh-goal；Goal/ToolSelection；未改 phase/objective |
| 静默保留审批/结果/故障 | 是，适用证据支持 | SingleThread drain/modelNotices/approval/stream；Store 原生 input；native 末步结果和审批用例 |

### Prototype / Reference Contract

仅核 explicit contract 与证据链，不替产品 reviewer 驱动产品或主观评分。

| Reference contract（design.md:210） | Milestone | Implementation | Durable evidence | Status |
|---|---|---|---|---|
| Web 五组/卡片，1280/390，根/负责人/子层 | R1/W3 | task-progress:19,42,48 | 代表 Web detail 图，一个宽度 | pending/inconclusive |
| Web valid/invalid/unknown/offline/恢复/暂缓 | R2/W3 | task-wait:8,21、page actions | 有效图、真实动作记录；自动化三种 health | pending/inconclusive，实际全状态不齐 |
| iOS 390/430 纵向、长原因/滚动/关闭/动作 | R3/W3 | TasksView、TaskPresentation | waiting 图、测试/归档 | pending/inconclusive |
| 两端 Goal 默认/开/关/保存反馈 | R4/W3 | 两端编辑与 runtime gate | iOS 保存图、跨端回读记录 | pending/inconclusive |

## Issues

### CRITICAL

0。产品证据仍由另一角色验收，因此未把 pending 计为通过，也未凭空确定实现缺失；此报告整体仍不能用于批准交付。

### WARNING

1. **F1：运行条件恢复仍被相同 Task 指纹拦截。** 契约：spec.md:611；design 关键决策 6；Gateway delta「多轮与运行故障」「中断与换窗」。实际：`packages/dsh-integration/src/task-execution.ts:123`。模型失败置 interrupted，配置换成健康模型后责任 unchanged 时仍不清屏障。本角色真实 DSH fixture 复现请求 `1 → 1`、idle。建议区分配置/运行条件恢复与重复 Task 提示，恢复后重查接续，保留同因权限拒绝的防热循环；在既有 native Task 测试保护失败→恢复链。CONFIRMED，code review 同因 F1。

2. **F2：开启能力未发现无 binding 的既有责任。** 契约：Gateway delta「配置任务图特性」；spec.md:481；design 责任发现/恢复。实际：`apps/node/src/main.ts:361` 仅 changed；PA recover:82 关闭时跳过，Driver changed:133 只遍历已有 binding。关闭期间 UI 开始 doing、随后开启能力，不建根会话，直到额外聊天或重连。实际 PA/Store 复现只发 changed、binding 为空。建议有效能力启用/恢复后调用现有 recover 发现 scope，不另造调度器；补公开协调 seam 回归。CONFIRMED，code review 同因 F2。

3. **W3：原生生命周期关键边界缺回归保护。** 契约：design.md:255 M1-W2（公开 DSH stop 屏障恢复、安排失效/消费/重启及错误恢复）、M1-R6（运行中 A 改变不误停 B），testing.md 的稳定风险/最低 seam 原则。实际：`packages/dsh-integration/tests/task-execution.test.ts:8,62` 三项只覆盖 idle 入场刷新/并发真人/cancel、两类权限拒绝和最后结果；PA stop 测试 fake RuntimePort，IM stop-write fake Schedule inspector。它们有独立价值，但没有经过真实 DSH block/pre-step + queued ordinary/Schedule + stop 恢复的组合，也未在运行中多 step 确认 A 撤销/B 保留。F1 已说明缺失恢复用例会漏真实回归。建议在现有 native fixture 扩展最小连贯链：运行中暂缓/关闭/改派 A 后下一步看到变化、B 继续；stop 挂起后恢复/重启不让旧 queued input 越屏障，确认后保留普通输入；安排失效/消费后有一次有效处理且不热循环。只补明确设计边界，不扩假想场景。**此项是测试缺口，不据此断言实现必有相同故障。**

### SUGGESTION

0。未把命名/排版或假想兼容列为问题。

## Round 1 Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway Task / 配置重新开启 | main:361；PA recover:82；Driver changed:133 | enable-recovery 复现 | implementation-mismatch F2 |
| Gateway Task / doing 全量责任、改派、结束 | IM snapshot/list、PA scope、native prompt | IM 55 项、PA session、native continuation | aligned；产品旅程 pending |
| Gateway Task / waiting、安排、主动恢复 | prepareWaits、Runtime inspect、PA snapshot/watch | IM/PA/Cron、真实 waiting | aligned；完整到期/提前恢复 pending |
| Gateway Task / stop、运行中单项变化 | PA stop、Gateway write drain、IM 原子暂停、steer | IM 写未知、PA controls；组合缺口 W3 | aligned 的实现路径；保护不足 |
| Gateway Task / 故障条件恢复 | Driver interrupted/changed | native failure/config recovery | implementation-mismatch F1 |
| Gateway Task / 自动交付/审批 | SingleThread 与 Store 原生 input | native 结果、PA 审批/NO_REPLY、真实审批 | aligned |
| IM Task / 七状态/五组/分配/等待 UX | IM model、两端 views/editors | Web/Swift contracts、三图 | aligned；must-match pending/inconclusive |
| Gateway 能力 / Goal opt-in | Goal/ConfigurationScopes/ToolSelection | native 旧新/child/busy/竞争输入 | aligned |
| IM Agent / 两端 Goal 开关 | 两端 feature 联动/文案 | 保存/回读、默认测试 | aligned；完整视觉对照 pending |

### Uncovered Observable Behavior

未发现需要新增 delta 而未被四份 delta 覆盖的独立对外行为。Schedule 底层语义和 node/channels 传输没有另起产品契约；错误屏障与自动 turn 静默/审批/最后结果已有 delta。实现不符不能靠改 delta 消除。

Outcome: **implementation-mismatch**。修 F1/F2、补必要 W2 回归；产品 reviewer 完成后增补 durable must-match 对照。保留本轮已覆盖静态范围和有效证据，无需重复成功分支全量审查。


## Round 2 — bounded closure and affected contract verification

> Validation snapshot: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a → 567785b58bef199399bc005082e383bde6e3b2ed`

- review_round: 2
- verification_mode: targeted-closure + delta；corrected-delta 一并核对。
- prior_verification_path: 本报告 Round 1。
- fix_delta_range: `e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0..567785b58bef199399bc005082e383bde6e3b2ed`
- focus_issues: F1、F2、W3；另覆盖 Task runtime 读取、真人 UI 恢复来源、host mention stop 全部关联代码/测试/design/delta。
- verdict: **pass（本轮有界静态核对范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- requires_full_verification: false。未变范围保留 R1 有效静态证据；本结论不表示产品旅程或 M1 已全部完成。真实 Web/iOS must-match 和产品 R2 仍 **pending/inconclusive**。
- report_commit: caller 统一提交；本角色只追加报告。

### Closure

| R1 issue | 状态 | 直接证据及适用边界 |
|---|---|---|
| F1 配置恢复冻结 | closed | native Task 新增 failed-model 配置恢复测试；配置 changed 清 error，重复 Task hint 不清 error；denied/cancelled 不被顺便解锁。same revision 实际重新调用模型并完成。 |
| F2 首次开启遗漏 | closed | main configuration.apply 后更新产品配置，再 recover；PA 真实 NodeStore 测试关闭无 binding → 启用 → scopes/session.ensure。无需先发聊天。 |
| W3 原生组合回归缺口 | closed | 原生测试覆盖 A 工具已进入后撤回 A、下一步收到 removed A/remaining B 且 B 完成；stop fence 随 DSH restart 恢复，真人与真实旧 Schedule 在解除前无模型调用、解除后保留；真实 Schedule 消费后补有效新安排并静默。均通过现有 native fixture seam，未为每个文字场景机械复制测试。 |

A/B 用例证明的是已经进入的 A 动作保留真实效果、下一原生 step 可见新责任且 B 不被误停；不声称撤回已发出的副作用，也不把脚本化 LLM 决策冒充真模型自主选择。stop 用例验证原生准入，IM/PA 的范围/幂等/未知写另由 R1 有效低层测试承担。

### New contract coherence

| 新增/修正行为 | Implementation and evidence | 结论 |
|---|---|---|
| Task 读权限内的负责人状态 | TaskGraphService.runtimeState 先 get ACL 和 stored node，忽略 caller agent_id；Gateway/node/runtime 认证关联；Driver.observe 仅查已绑定原生状态。IM 测试禁止无权限/无节点发 runtime 请求；native running/idle、Web stale/error 清除测试 | aligned；只暴露 state，不返回其他聊天内容 |
| 真人 UI 恢复进入模型/审批 | IM 仅认证 user paused→doing 写 resume_request，禁止 patch，暂停清除；PA 当前快照透传；native 首次事实生成一次 task-human-control；ApprovalSources 仅该 host channel 标 human-task-control，普通提醒/peer 不升级；humanInputs/Goal source 不变 | aligned；只撤销该 Task 的暂停，不构成额外权限 |
| 定向 mention stop | controlText 比对 host roster 当前 Agent user_id；Global/SingleThread/SessionControls 复用，资格与 PA admission 继续存在；正例、其他 mention 反例及 Global 定向 stop 通过 | aligned；没有泛化剥除任意 mention |
| 两端统一读取实际状态 | Web/iOS 均走 graph/node runtime；UI 不再向不存在的 SingleThread Global Work 查询，非有效 state 显式 unknown | aligned；真实产品 R2 仍待验 |

### Reused validation

- `/tmp/feat635-r2-frozen-build.log`：全包构建成功，包含 `567785b58bef199399bc005082e383bde6e3b2ed`。
- `/tmp/feat635-recovery-batch-tests.log`：9 files / 89 tests pass；`/tmp/feat635-final-native-resume-tests.log`：2 files / 51 tests pass。已读测试内容，保护修复和来源边界，未无意义重跑。
- `/tmp/feat635-observation-web-tests.log`：1 file / 6 tests pass，Web build pass；命令中另一个不存在的文件名没有实际运行，不把它计为第二个文件。
- `/tmp/feat635-r2-typecheck.log`、`/tmp/feat635-r2-ios-runtime.log`：通过；`/tmp/feat635-r2-ios-build.log`：已核 BUILD SUCCEEDED。
- R1 全量后端 552、Web 960、Swift 43/Release archive 是对应旧快照证据，不冒充 R2 重新全量。R2 新原生构建已通过，最终 tests/archive 和产品报告由 caller 在收尾关联。

### Prototype / Reference evidence status

R1 三张代表图仍只支持当时所见，不能证明最新 runtime API 和 UI resume 的真实验收；不继承“结构存在”之外的产品通过结论。新的 `acceptance.md` 及必要 screenshots/实际动作结果完成后，增补 design must-match 的 Web 1280/390、iOS 390/430 与状态对照。当前保持 pending/inconclusive，不阻碍本轮确定代码/契约发现先收口。

## Round 2 Corrected Delta Reconciliation

适用范围：全部四份已校正 delta；R1 未变项保留原静态核对，补查此次两个修改文件及新对外行为。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway Task / 重新开启与运行条件恢复 | 配置接线 configured/recover；区分 error/denied/cancelled | native model recovery、PA first enable | aligned，F1/F2 closed |
| Gateway Task / stop 范围、运行中责任、安排修复 | 原生 steer/pre-step/block 不另建 loop，IM 原子真相保留 | native A/B、restart fence+human+Schedule、consumed replacement | aligned，W3 closed |
| Gateway Task / 定向 mention stop | host roster controlText，原身份/attention gate | SessionControls 正反例、Global directed stop | aligned |
| Gateway Task / UI 明确恢复事实 | IM authenticated user transition，PA透传，native task-human-control，审批限定语义 | IM 防伪/暂停清除、native 一次投影、approval sources 区分 | aligned |
| IM Task / 真实负责人运行状态与读权限 | graph ACL→stored assignee→authenticated node→bound native observation，两端 Task runtime route | IM 拒绝/身份/unknown；native running/idle；Web offline/error | aligned；真实产品对照 pending |
| 其他 IM Task 七状态/五组/等待信息 | 无关联实现变化，保留 R1 的适用核对 | R1 自动化与有效图；未沿用完整体验 pass | aligned；must-match pending |
| Gateway / IM Agent Goal opt-in | 无相关变更；未引入 UI resume 为 nano-human/Goal 资格 | R1 native Goal 与两端配置证据保留 | aligned |

### Uncovered Observable Behavior

None。本轮新增 Task runtime state 和 attested UI resume 已准确加入 delta；mention stop 已入 Gateway delta。恢复修正兑现原目标，未静默改 spec 适配错误实现。没有新的底层 Schedule 行为或第二运行时。

Outcome: **aligned**。本轮静态结论可收口；M1 产品 must-match、完整真模型旅程和最终交付检查继续由相应角色完成。


## Round 3 — recovery and integration verification

> Validation snapshot: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a → 30cd2e0a1272ec0a157337ebe644ad11e642809c`

- review_round: 3
- verification_mode: targeted-closure + integration delta；corrected-delta reconciliation 同轮。
- executed_base: 保留 `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a`；effective_base: latest main `0904bc49c`。
- prior_verification_path: 本报告 R1/R2；fix_delta_range: `567785b58..30cd2e0a1272ec0a157337ebe644ad11e642809c`。
- verdict: **pass（有界静态/契约范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- requires_full_verification: false。主干整合影响可界定为来源/审批适配与 Task iOS 呈现接线；已核共同边界及相应 native 回归，不重复审查上游独立功能。
- 本结论不代替产品最终迁移复验、正常 rollover 及 must-match；它们仍 pending/inconclusive，不能据静态结论宣布 M1 全部完成。
- report_commit: caller 统一提交；本角色仅更新两份报告。

### Completeness / correctness / coherence

| Affected contract / issue | Implementation and direct evidence | Outcome |
|---|---|---|
| 运行条件恢复后按当前责任接续；保留已接收输入 | Driver configured 区分 error/denied/cancelled，并在有效 idle 无 stop fence 时唤醒原生非空 Inbox；3 类 native failure fixture，queued notice 只消费一次 | aligned；本次实际暴露的 retained-input gap closed |
| F1/F2 恢复修正保持有效 | error configured、PA scopes recovery 接线仍在；新增 queued 输入唤醒不替代 scope discovery | closed，R2静态结论保留；配置恢复使用新三分支证据 |
| W3 原生边界覆盖 | A/B、stop restart+human+Schedule、消费替换6项仍保留，与新3类恢复同批通过 | closed；脚本化LLM仍不冒充真人模型旅程 |
| bugfix-633 真人来源与 Task 审批共存 | host human source=user+identity；isHumanSource兼容旧日志；approval route保留Task入口且不放开Global/child/Schedule；sources保留direct-parent与human-task-control独立类别 | aligned；没有以source.kind=user单独断言真人授权 |
| Goal 默认关闭与可选原生真人资格 | ToolSelection/Goal feature gate保留；上游native-human fixture仅增加dsh_goal=true，真实source资格与审批拒绝断言保持 | aligned；不上调Task自动输入的Goal资格 |
| PA真实来源/投影 | global task provenance与work projection同步识别host-attested user，系统Task wake仍nano-system | aligned；跨聊天/权限不因source适配扩大 |
| iOS最新compact卡片与waiting | TaskCompactCard根/负责人/子层传wait/health；TaskStatusSummary waiting→doing定位；detail runtime/动作保留 | 代码aligned、模拟构建成功；最新真实两端体验pending |
| 上游PA入口/chat polish | 相对0904这些入口及chat实现没有本方差异；Goal特定联动增量仍在 | retained；不把上游独立交付重新归因本unit |

### Retained evidence boundaries

- R1 全量规范/30场景映射，R2 未变 Task 数据、ACL、runtime state、attested resume、stop scope 与 Schedule 静态证据保留；重叠的恢复/来源/iOS接线以R3为准。没有把“源码未变”扩张成未知产品旅程已通过。
- `/tmp/feat635-main-integration-tests.log`：9 files / 86 pass，测试执行树与30cd一致（caller明确确认）；涵盖Task/native-human/Goal/approval/capabilities/PA provenance/Global。未为重复有效证据重跑全量。
- build/typecheck、ios-runtime、iOS simulator compile、docs-check均通过。build日志stamp为0e5405c79：当时仍在merge提交前，但产品冲突已全部解决；caller确认产品源码等于最终30cd，之后只改native-human fixture opt-in与文档。因此按source-tree等效复用，**不声称stamp为30cd**。
- caller正在执行提交后最终Web全量/build、Swift tests/archive、runtime contract和重建release stamp；结果未返回时不预先计pass。
- iOS改用最新compact布局影响W3真实对照。旧567截图不自动继承为新版本视觉/操作通过；产品reviewer的rollover与最终迁移后的真实复验仍须关联新源版本。

## Corrected Delta Reconciliation

适用全部四份delta和本次current归并，保留R2未变实现的适用核对。独立只读脚本按Requirement分段比较：共16项ADDED/MODIFIED/REMOVED，归并后目标正文规范化比较全部一致，删除项均消失。另与最新main比较，未覆盖/丢失上游真人来源或PA/iOS长期契约。

| Item | Implementation / canonical evidence | Outcome |
|---|---|---|
| Gateway Task / 运行故障恢复与保留输入 | configured有界唤醒、三类native failure、一次通知；canonical“多轮与运行故障/中断与换窗”覆盖 | aligned；这是兑现原恢复要求，不新增授权语义 |
| Gateway Task / 全量责任、等待、停止、UI恢复、交付审批 | 对应实现无新的相反改动；source整合保留Task审批、专用human-task-control与系统边界；canonical正文一致 | aligned |
| IM Task / 七状态、五组、等待与实际执行 | iOS最新compact卡片带wait，waiting定位doing；真实runtime API保留；canonical正文一致 | aligned；最新must-match待产品复验 |
| Gateway能力 / Goal默认关闭与最新真人来源 | native-human与Goal opt-in并存；current保留upstream真人来源，新增Goal Requirement；索引38 | aligned |
| IM Agent / 两端Goal配置及PA入口 | Goal联动保留，上游PA入口未被覆盖，canonical新增项一致 | aligned |
| Removals / 六状态旧契约 | current旧Requirement消失，七状态正文完整；其他upstream条目保留 | aligned |

### Uncovered Observable Behavior

None。queued-input wake修复兑现既有恢复保证；原生human-source适配和最新PA/iOS产品行为由已合入上游canonical约束，无需重复加一份feat-635 delta。设计bugfix-633归档链接已修正。

Outcome: **aligned**。仅后续文档归档不会改变本轮源码核对对象；如再改产品实现，须按实际fix delta补核。产品最终证据未完成部分继续保留pending。


## Round 4 — CI fix bounded verification

> Validation snapshot: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a → 1bd82f9ebbec17b85868640eb1c5e78733c0c709`

- review_round: 4
- verification_mode: delta（CI修复及受影响原生恢复边界）；no new spec delta。
- pre_fix_head: `42aa1f9afb0faeb59cd55574626fb67040d911fc`；fix_delta_range: `42aa1f9af..1bd82f9eb`。
- effective_base: `0904bc49c`；prior_verification_path: 本报告R1–R3，均保留。
- verdict: **pass（本轮有界范围）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- requires_full_verification: false。共享controller边界已有真实冷恢复/创建并发、首次冷binding、Cron、profile/supervisor和来源回归保护；影响可界定，无需重跑整个产品验收。
- report_commit: caller统一提交；只追加本报告与code-review.md R4。

### Correctness / coherence

| 受影响契约 | 实际证据 | 结论 |
|---|---|---|
| 重启时原生Schedule与产品ensure不竞争会话写句柄 | controller.resolveAgent公开声明和去重resume契约；已有binding先resolve，仍走create；Promise.all(observe,ensure)原生回归先红后绿 | aligned，CI冷恢复缺陷closed |
| 可信binding及cwd/preset不绕过 | binding冲突、PA owner/workspace、配置存在校验在resolve前；原生create原样调用，仍核cwd/preset；只有session/not-found被允许继续创建 | aligned；没有通用吞错/fallback |
| 尚未落盘binding可创建 | session/not-found继续原路径；cron/model-policy/runtime-profile/supervisor/native-human相邻15项通过 | aligned |
| stop fence早于恢复、排队输入保留 | initialize taskStops先安装；本轮真实restart并发保留旧Schedule与真人输入，确认前无LLM调用、之后处理原输入 | aligned；R1/R2 stop范围与幂等低层证据继续适用 |
| Goal默认关、显式开启后下一轮配置 | 仅fixture hold条件由旧source过滤改为明确用户消息ID；产品Goal/配置代码无改动；native Goal通过 | aligned，不改变来源授权或Goal语义 |

### Validation

- `/tmp/feat635-cold-race-red.log`：改动前真实native并发复现session/writer-held，不把偶然重试变绿作为根因证据。
- `/tmp/feat635-ci-race-green.log`：Task+Goal 2 files / 10 pass；`/tmp/feat635-ci-cold-bindings.log`：相邻冷绑定/原生来源5 files / 15 pass。
- `/tmp/feat635-ci-fixed-full-backend.log`：本轮最终全量121 files / 575 tests PASS，93.05s；初轮573/575失败保留在实施记录，未放宽timeout。
- caller本轮build/typecheck通过声明可复用。首轮CI Web及iOS tests/Release archive通过，且此patch无Web/iOS改动，不为提交号机械重复产品旅程。

### R3 product evidence retained

已读取归档acceptance.md的R3最终pass、must-match及全部30场景表，连同其显式继承边界核对本次影响。本轮不重做产品reviewer：

- Web/iOS正文、compact卡片、五组映射/定位、waiting/runtime详情、Pause/Resume、Goal开关代码未改，因此R3 J20/J21及指定R1/R2的1280/390/430对照和返回位置证据保留。390最终版未重新跑、430触控含用户手动证据的原限制也保留，不把它们升级成新的观察。
- R3 J18模型配置恢复、J22自动第二轮审批/交付和早期多树/改派/父子交付不依赖新的界面实现；源码及有效native保护保持，产品实测结果可保留。
- 正常rollover J17没有新hook或Task状态语义变化；保留其真实责任接续证据，仍不声称不存在的Schedule跨窗已测。
- 既有成功冷重启/stop旅程保留为当次事实；本轮新增确定性并发native测试专门补足此前未覆盖的writer竞争，不能倒写旧旅程为早已证明并发无竞态。

### Delta reconciliation supplement

本轮仅design实现说明和evidence更新；四份delta、canonical、配置schema、依赖与Web/iOS均无差异。修复兑现既有“恢复后按当前真相接续、未确认stop不能越屏障”要求，不新增外部行为或新的权限路径。R3的16项canonical一致结论仍适用。

Outcome: **aligned — no new spec delta**。无需修改需求或delta迁就实现。没有新未覆盖的可观察行为。


## Round 5 — user-corrected Goal tools and local-only images

> Frozen implementation: `30a53c2047ea391adba6399a35234883d6c1e8fd`；effective main `866877a83`

- review_round: 5
- verification_mode: delta + corrected-delta；prior_verification_path: 本报告R1–R4。
- fix_delta_range: `89a4beeb8..30a53c2047ea391adba6399a35234883d6c1e8fd`。
- verdict: **pass（代码/契约有界核对）**，0 CRITICAL / 0 WARNING / 0 SUGGESTION；requires_full_verification: false。
- 整体交付仍待本轮Web真入口补证与PR最终squash去图历史。用户最新明确收缩验证：iOS仅源码审查+已完成编译测试，不再新增原生UI实测，也不声称新逐工具原生UI独立验收通过。三项失败已无代码变更窄复验通过，见下表边界。
- report_commit: caller统一提交，本角色只追加两份报告。

### Completeness / correctness / coherence

| 用户修订及关联契约 | 实现与直接证据 | 结果 |
|---|---|---|
| 无Goal Feature，默认集不含三个工具 | Node feature目录删除Goal，三个tool default_on=false；ToolSelection默认分支排除；源码搜索无dsh_goal/disarm残留 | aligned；Node目录与native默认/空集合/Global测试 |
| 显式名单逐项生效，不联动 | ToolSelection显式选择；Web/iOS删除专门联动、普通工具列表不变；native create-only/get-only/update-only/all曝光断言，get实际执行/未知工具结果 | aligned；Web组件仅保存get_goal |
| 无工具无专属引导 | ConfigurationScopes按有效selection是否含Goal工具隐藏tool:goal；不是Feature值判断 | aligned；native prompt含/不含覆盖 |
| 取消立即收缩、新增idle，不早开默认未选工具 | restrictSelection使用当前有效选择与候选显式名单求交，原refresh限制层生效；配置whenIdle后完整setConfiguration | aligned；忙时get/read→update、缺省→get两条native回归 |
| 原生Goal语义/权限独立于Task | 删除专门Goal plugin/disarm/source过滤及直接依赖；保留原生工具和审批；Task driver/PA/IM均无改动 | aligned；原生权限/真人来源回归移除Feature前提仍通过 |
| 图片仅仓外保留 | 当前unit tracked images为空，53张删除，无图片Markdown路径；README声明文件名为本地标识 | 当前树aligned；历史squash尚待caller完成 |

本轮测试rewrite删除的是被用户否定的Feature总开关、disarm与竞争Goal过滤风险；新默认/逐项选择、普通配置收缩保护在既有goal-opt-in文件承担，不因文件名仍为opt-in推断存在Feature。审批与native-human测试只移除过时Feature配置，原权限断言保留。

### Validation status and retained product evidence

- `/tmp/feat635-tool-selection-green.log`：4 files / 12 pass；`/tmp/feat635-tool-selection-web-tests.log`：2 files / 28 pass；typecheck已通过。caller确认contract13通过，未为重复有效证据重跑。
- 全量后端日志当前为573/575，personal-security30s和workspace-tools90s timeout；全量Web962/963，chat-workspace无法找到Reply draft。并发与运行环境因果尚未证实，不把失败解释成无关flake或代码缺陷。无代码变更窄复验现已通过：`/tmp/feat635-tools-recheck-backend.log`为2 files/7 tests、43.04s；`/tmp/feat635-tools-recheck-web.log`为chat-workspace59 tests、11.95s。初轮失败与窄复验成功都保留，不声称已证明并发因果，也不要求重复完整套件。`/tmp/feat635-tool-selection-ios-tests.log`已核TEST SUCCEEDED。
- 新M1-R4改成两端普通工具逐项选择；acceptance R1–R3的Feature开/关与driver撤销结论明确**superseded**。历史实际原生Goal授权/审批事实可作为背景，不能证明新目录、单工具选择或保存反馈。
- 未变Task七状态/等待安排/stop/改派/父子协作、runtime state、故障恢复、正常rollover及其原型M1-R1/R2/R3，可按R4既定版本边界retained；图片外移不抹去文字实测记录，也不把历史观察升级成新复验。
- 新普通工具列表由Web真入口/运行时补产品证据；按用户本轮最新授权，iOS以源码+编译测试回归收口，不要求新增原生界面实测。当前组件/native测试不冒充原生触控或完整原生保存旅程验收。Task全旅程无需机械重跑。

### Corrected Delta Reconciliation — R5 supplement

只读按Requirement分段抽取四份delta并与canonical规范化比较，18项ADDED/MODIFIED/REMOVED全部一致。新增两项完整MODIFIED保留原Gateway5个/IM11个Scenario；只在通用配置正文明确撤销/新增边界。

| 修订delta | 实现/归并证据 | Outcome |
|---|---|---|
| Gateway能力 / Goal工具默认不选且可逐项配置 | default选集排除、显式名单逐项、prompt有效选择、无Feature/driver/额外生命周期干预；canonical正文一致 | aligned |
| Gateway能力 / 完整运行配置与工具撤销例外 | 立即收缩从当前有效选择计算，新增whenIdle；原其他配置路径保持；canonical全Requirement一致 | aligned |
| IM Agent / 两端逐项Goal工具 | 普通工具列表，无Feature与联动；canonical一致 | aligned；Web真入口待补，iOS按用户授权源码/编译测试范围 |
| IM Agent / 普通配置版本与生效边界 | 完整配置整轮不切换、工具撤销有限例外，原11个Scenario保留；canonical一致 | aligned |
| 其余IM/Gateway Task delta | 本轮未改Task实现和delta，沿用已核语义 | retained/aligned |

### Uncovered Observable Behavior

None。用户明确选择的普通工具配置语义已进入design/M1、两端delta和canonical；没有用静默文档修改掩盖实现错误。图片留存政策按用户要求优先，仓外标识用途已说明；最终历史清理尚未作为已完成事实。

Outcome: **aligned**。本轮代码/契约可收口，未完成的验证和交付事项须补充后再宣告PR最终可交付。
