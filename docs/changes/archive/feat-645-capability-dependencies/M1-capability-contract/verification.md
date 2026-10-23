# Verification Report: feat-645-capability-dependencies

> Validation snapshot: `5d03e0567^2 → 850e6cd82547c083655bc69d5de465105fd5eeac`
> verification_mode: `full + corrected-delta`; review_round: `1`
> 产品实现冻结：`9802c9347`；`850e6cd82` 仅补 Web 测试类型。现场后续提交文档证据并合并至 `5ce70533c`；已核实 `850e6cd82..5ce70533c` 的 `apps/`、`packages/`、`src/` 无变化。另按 caller 派发静态核对 CI 差分 `aeccebccb`。本报告由独立 verifier 写入，不修改源码、测试、配置或设计。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 实现及相关自动回归已覆盖主要契约；M1-R2 / M1-W3 原生局部交互证据未完成，最终 Swift 回归和远端 CI 待返回；独立产品验收尚未收齐 |
| Correctness | 本轮未发现新增可证实实现偏离；首轮 code review 两项 finding 均已 closed，closure 报告为 `[]` |
| Coherence | D1–D6、职责及 DSH 公开接入边界遵守；没有新增 Agent loop、权限旁路或产品内历史配置补齐逻辑 |
| Corrected delta | `aligned`；包括 IM 空工具集仍显示模式固定能力的修订；不等于完整验收通过 |
| Findings | 1 CRITICAL（必需证据尚未完成），0 WARNING，0 SUGGESTION；不是新增产品代码缺陷 |
| Verdict | **INCOMPLETE / 不 pass**。用户已允许 Draft PR 转远端 CI；本报告不阻止该验证方式，也不把 Draft 或待验当作完成 |
| requires_full_verification | `false`；完成下述证据后可 targeted 补核，无需重跑已有效矩阵 |

核对输入为本 unit `spec.md`、`design.md`（含 M1）、全部四份 delta、相应 current Requirement/Scenario、`SPEC.md`、`docs/development/testing.md`、实际代码及测试。Current 中与目标不同的旧 `requires_tool`、Feature AND 门槛、交互卡片禁止及配置取消维护语义，均已在对应 delta 明确替代；没有用 active 文档提前覆盖 current。

## Completeness

唯一 milestone 为 M1，不把前后端拆成可独立完成的交付。以下是退出标准的实现及证据对账，`covered` 仅表达该行直接证据，不替代独立产品 reviewer。

| 退出标准 | 实现及有效证据 | 状态 |
|---|---|---|
| M1-R1：六 Feature、Task→Cron、共享依赖、合法关闭、不增加归属标记 | `product-contracts/src/capabilities.ts:28,109`；Web/Swift reducer 及公共 17 fixtures；Web 真页面自检见 `validation.md` | 实现 covered；产品 reviewer 最终结论待收齐 |
| M1-R2：责任/占用阻止关闭、只提示、2 秒浮层、窄屏和 iOS | IM Task guards、CapabilityState、Knowledge/Heartbeat 占用有直接自动回归；真实 Web 三宽度 geometry 和截图已保存；尚无原生保护 Toggle、焦点/VoiceOver、安全区交互证据 | **未完成，见 C1** |
| M1-R3：关 Feature 再单开工具、preview、权限、两条 interactive 发布路径 | native capabilities / communication、PA interactive-replies / personal-assistant 测试；真实 tool-only 保存及重启配置对账 | 实现 covered；产品 reviewer 最终结论待收齐 |
| M1-R4：单开 schedule_create 到期执行、Memory/Skills 不复盘、Task 不续跑 | `dsh-integration/tests/cron.test.ts:7` 经真实 native runtime 创建并等待 schedule evidence，断言无 Feature section / knowledge reviews；IM `task-execution.test.ts:21` 区分普通工具与自动入口 | 自动化直接证据 covered；不虚称已收到独立产品结论 |
| M1-R5：部署演练补齐且不覆盖后来选择 | `deployment-prompt.md`；`validation.md` 记录旧无密钥 fixture 副本演练；`evidence/restart-choices.json` 显示所有 Feature 关闭、tool-only 和禁用 Skill 在正常重启前后完全相同 | covered；无生产迁移或生产验收声明 |
| M1-W1：公共 fixtures、Swift/TS、schema/export | 公共契约 6 tests；Web 公共 17 cases；早期 iOS 21 tests / 5 suites 通过；最终 Swift 新命名 Skill 回归已编译，但运行未完成 | 原能力矩阵 covered；最终 Swift 回归 **pending** |
| M1-W2：落盘前拒绝、重放/补偿、两种竞争次序、维护不取消 | PA configuration、IM control/Task、native capability/cron/knowledge-review；code review P1/P2 红绿回归及 closure | covered |
| M1-W3：真实 Web 三宽度与原生局部交互 | Web `web-toast-geometry.json` + 三张真实截图；iOS build/早期契约 tests 不替代原生交互 | **未完成，见 C1** |
| M1-W4：schema/prompt/call、新建/恢复/preview/run/wait、公开依赖 | native capabilities/cron/communication/knowledge；Node/IM projection；架构 Python tests；没有 private import 或 runtime patch | 相关直接证据 covered；最终 CI 仍待返回 |
| M1-W5：窄验证后按风险扩大、不做代码迁移及双写 | 窄 tests、构建和 Python 65 项已通过；用户允许终止高负载本地大矩阵转远端 CI；停止前的新 Swift test 不能记 green | 相关窄证据 covered；最终远端 CI、任务现场清理由 caller 继续收口 |

### 复用证据及边界

- 公共契约、IM 47、Node/PA 47 与配置恢复追加 5、native 核心/扩大验证的版本及结果见 `validation.md`。它记录早期 native 12 files / 51 tests 为 50 pass + 1 原超时单测复跑通过，不能写成首次全绿。
- Web 8 files / 95 tests：`/tmp/feat645-web-all-final.log`；修复后 Web 2 files / 26 tests：`/tmp/feat645-review-green-web.log`。相应红测在 `feat645-review-red-web.log`；验证的是原真实缺陷，而非只加断言后宣布通过。
- Node 分区 7 tests：`/tmp/feat645-review-green-node.log`；红测在 `feat645-review-red-node.log`。closure 还独立用轻量 mock 复核拒绝 prepare 后重启仍读取旧快照、新 PA 空快照初始化/release，以及仅 effective apply 更新 snapshot。该 mock 未启动服务，不冒充真实 DSH/iOS 验收。
- Web TypeScript + Vite：`/tmp/feat645-web-review-build.log` 通过；Node 包编译：`/tmp/feat645-node-review-build.log` 通过；主线合并影响 PA 3 files / 56 tests：`/tmp/feat645-merge-pa-tests.log` 通过。
- iOS 早期 21 tests / 5 suites：`/tmp/feat645-ios-tests-retry.log` 明确 `TEST SUCCEEDED`；新增 busy Skill 三种模式测试源码位于 `CapabilitySelectionTests.swift:6`，修复后 `/tmp/feat645-ios-review-tests.log` 有 Simulator IPC server died，随后 caller 停止等待。**新增回归运行结果未证实**，不沿用早期 green 覆盖新增测试。
- Python `pytest -m "not e2e" -q`：`/tmp/feat645-pytest.log` 为 65 passed / 31 deselected。架构规则新增 browser-safe subpath，未提交 formatter 仅将同一集合换行；不扩大跨包依赖。
- Caller 确认最后一次本地 broad native 使用了 shell Node 25.8.2，且已中止；那些超时既不作为有效 green，也不据主机负载直接判为产品缺陷。后续采用 CI 固定 Node 24.22.1 的实际结果。用户授权将高负载检查转远端；本轮未再开启大矩阵。
- `code-review.json` 保留 R1 两项；`code-review-closure.json` 为 `[]`。本 verifier 复用其独立 full/closure，不重新执行另一轮 full code review。

## Correctness

| Requirement / Scenario | 实现位置 | 测试 / 直接证据 | 状态 |
|---|---|---|---|
| 六 Feature 的完整依赖、default Task→Cron、资源不存在时原子拒绝 | `packages/product-contracts/src/capabilities.ts:28,85,109`；`apps/node/src/capabilities.ts:63`；Web `agent-create-page.tsx:477`；Swift `CapabilitySelection.swift:115`；IM `control.ts:718` 与 `personal-agent.ts:359` | `product-contracts/tests/capabilities.test.ts`、公共 JSON fixtures、Web/Swift fixture consumers、Node capabilities tests | covered |
| 关闭直接依赖、共享 read/skill 保留、Task 关闭保留 Cron、独立重开不反向启 Feature | 同一纯 reducer；Swift `CapabilitySelection.swift:51` 数据解释 | 公共 17 cases + Web 真页面自检；合法后续配置重启对账 | covered |
| Global/Personal 固定基础能力、正确 subagent 名称、子 Agent 不继承根角色固定项 | `capabilities.ts:54`；integration `capabilities.ts:67`；Node `capabilities.ts:63`；Swift `AgentModels.swift:75` | 公共 fixedTools 测试及 runtime capabilities/角色约束；未知/缺失 context 工具仍不凭空注册 | covered |
| Tool/Feature 分离，普通 Task 调用不触发自动续跑，身份/会话权限保留 | integration `agent-config.ts:106` 与各 Feature `registerTool`；`capabilities.ts:62`；IM `task-graphs.ts:585`；PA `global-agent.ts:428`；原 TaskExecutionDriver / PA execution 仍要求 Task Feature | `cron.test.ts:7` tool-only、`task-execution.test.ts:21` 普通 get 成功/自动 snapshot 拒绝、native task/知识测试 | covered |
| Memory/User 注入、主动复盘和扫描只跟 Feature；单开 memory/skill_manage 保留合法写入 | `features/memory-curation.ts:36` / `skill-creation.ts:15`；`agent-config.ts:170`；`knowledge/runtime.ts:187,230` | native `cron.test.ts:7` 实际写入文件且 reviews=[]；`knowledge.test.ts` 和 `knowledge-review.test.ts` 保留联合、F4、成功事实与取消/进程停止语义 | covered |
| Cron Feature 关时单工具可调用、必要 service 存活、跨重启兑现安排；不恢复其他工具/额外指导 | `capability-state.ts:9`；runtime `index.ts:678`；`cron-owners.ts:44,59`；`agent-config.ts:118` | `cron.test.ts:7` tool-only 定时接收、重启 active 安排、工具 schema/prompt；`cron.test.ts:66` 保留崩溃前真实 admission 证据，不宣称 exactly-once | covered |
| Task 全会话 doing/waiting 阻止关闭，pending 期间新增责任被拒；不暂停/删除责任 | IM `task-graphs.ts:14,19,910`；`control.ts:207,317` 在同一同步事务检查与插入 operation | `control.test.ts:22` 先有 doing 的拒绝、反次序 pending 下 doing 拒绝而 todo 成功；查询按 Agent、状态及 assignee，不依赖当前 session/binding | covered |
| Task 依赖或任一 active Schedule 阻止关闭 Cron，不按未来时间过滤关闭计数 | `capabilities.ts:30`；`capability-state.ts:63`；runtime `index.ts:515`；CronOwners chain 的 admission fence | 公共 dependency 测试、CapabilityState tests、native cron 两次序检查；waiting inspect 仍独立验证实际未来时间和会话归属 | covered |
| 已接收维护/Heartbeat、真实调用与命名 Skill 占用保护；无关配置不因 Agent running 被拒 | runtime `index.ts:168,515,687`；`capability-state.ts:23,38`；Knowledge `runtime.ts:107,194,235`；PA `heartbeat.ts:31`；Node `main.ts:374` | native held tool/无关 edit、knowledge-review 联合工作关闭被拒且不 cancel、PA heartbeat pending/hold、Web busy Skill 新红绿回归；Swift 最终运行 pending | 实现 covered；Swift 最终运行 pending |
| 配置完整候选、保存前拒绝、pending 重放/补偿及不会把被拒绝候选当重启配置 | IM `control.ts:205,284,317`；Node `configuration.ts:104` / `main.ts:374`；PA `configuration.ts:43,65,82`；runtime `index.ts:529,539`；Node `runtime-partitions.ts:118,210,235` | PA 5 项 configuration recovery、IM operation/CAS/ACK tests、Node R1-P1 回归及 closure；新 PA prepare 建可信路由且成功 apply 后 main 报告 availability | covered，P1 closed |
| usage API 只返回当前 Agent 计数/忙碌能力，状态未知失败；HTTP errors 保留结构化原因 | IM `control.ts:889`、`safeRejections/resolve`；Web `http-error.ts:13` / config API；Swift Session error envelope | IM `control.test.ts:23` owner隔离/仅安全字段/未知503；Web config API及反馈 tests | covered |
| Intelligent UI 关只移除指导，Global/普通与 Personal 显式合法 interactive 继续原审批/幂等/降级 | PA `global-agent.ts:499`、`personal-assistant.ts:107`；integration `agent-config.ts:117`；Web i18n help | PA `interactive-replies.test.ts:26` feature=false 时 Web 卡片/Feishu文字降级/幂等；`personal-assistant.test.ts:42` feature=false 且保留 disclosure review/冻结proposal/真实receipt；native communication 测试单独核 prompt | covered |
| Web/iOS 同一依赖数据、关闭保持原态、保存拒绝保留其他草稿、局部反馈 | Web `capability-editor.tsx:56,99` 和 create/detail 接线；Swift `CapabilitySelection.swift:45,51`、`AgentConfigView.swift:100,130`、`CapabilityToast.swift:18` | TS/Swift shared fixtures；Web usage延迟/重复Toast/focus/错误后保留草稿；真实截图/geometry；iOS 原生交互缺失 | 实现 covered；原生可见验收未完成 |
| 一次性部署补齐不进入代码，不覆盖用户后续合法选择 | `deployment-prompt.md`；Node 启动仅 validate；没有新增自动历史补齐调用 | caller 旧fixture副本演练记录；`restart-choices.json` head=1ce3925a3、equal=true，修复仅改拒绝快照及预检，未变此选择语义 | covered；不推断生产状态 |

## Coherence

| design 决策 | 核对结果 | 实际证据 |
|---|---|---|
| D1 完整六项依赖与有效默认闭包 | 遵守 | product-contracts 单一声明；创建默认值先展开；保存/preview 验证完整候选 |
| D2 角色固定能力，不把默认全升级为必需 | 遵守 | fixedTools(mode,role,contextEnabled)，仅固定 Global 根通信和已注册 context 工具；Swift `agent` 修正为 `subagent` |
| D3 工具与 Feature 行为分离 | 遵守 | 三类 registerTool 独立、Feature scope 管提示/订阅；Cron service 按工具/持久安排；两条 interactive 发布入口去掉 Feature 否决 |
| D4 一份纯数据及有限集合运算 | 遵守 | Web browser-safe subpath，不引入 node:crypto；Swift 消费同一 `requires/fixed_tools` 及公共 fixtures；未增加点击历史或通用规则引擎 |
| D5 权威占用与最小保护范围 | 遵守 | Task SQL、native active catalog、真实调用 middleware、Knowledge kinds/scans、Heartbeat pending/执行来源；不按普通 running 猜测 |
| D6 复用已有 operation/fence/recovery | 遵守 | IM 持久 operation + SQLite 事务；Node prepare→persist→apply；runtime reservation；旧两个局部写RPC明确拒绝；只有 effective apply 更新重启快照 |
| 仓库架构与测试层级 | 遵守 | 新依赖仅 product-contracts/capabilities；Node 保持 integration/client；无 DSH private import/fork/新HTTP内核；新增测试归公共契约、原owner测试及客户端已有门禁 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Feature 开关联动、默认 Task→Cron、共享 read/skill | M1-R1 / M1-W3 | Web/Swift 同一元数据及有限算法，真实 Web 自检 | `validation.md`；公共 fixtures | Web 有直接证据；独立产品结论 pending |
| 浮层不占位、工具区坐标和高度不变，Web 1440/768/390 | M1-R2 / M1-W3 | Web portal/fixed/max-content；已独立打开三张真实截图并核对 JSON | `evidence/web-toast-{1440,768,390}.png`、`web-toast-geometry.json` | covered：三组 before/during/after 完全相同；右边缘 1381.29/752/374，各宽度右侧均≥16px |
| 约2秒、重复不堆叠、focus不被夺取 | M1-R2 / M1-W3 | Web timer依stamp续期，单个toast，不调用focus；Swift task(id)/overlay/accessibility announcement | Web相关 tests + 自检记录；Swift源码/早期build | Web covered；Swift原生交互见 C1 |
| 原生 Form Toggle、安全区、VoiceOver/焦点、窄屏 | M1-R2 / M1-W3 | Swift overlay/Anchor/geometry/不拦截点击；实现可定位 | 只有设计意图图与 build/契约 tests；CUA -10005、Simulator IPC错误不构成通过 | **未完成** |
| 同一草稿关 Feature 再单开工具、保存重读及重启 | M1-R3 / M1-W2 | reducer/runtime/operation组合 | `web-tool-only-saved.png`、`restart-choices.json` | covered；独立产品结论待收齐 |

## Issues

### CRITICAL（完成 M1 前必须补齐）

**C1 — M1-R2 / M1-W3 要求的原生局部交互证据缺失。** 契约为 `design.md:254,267,273` 与 IM delta 的“阻止关闭时保留选择”。`src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift:100` 和 `CapabilityToast.swift:18` 已有实现，但 build、公共 reducer tests、HTML iOS 意图画布都无法证明真实 Form Toggle 不闪动、焦点/VoiceOver 不受扰和窄屏安全区。现有 CUA 返回 `-10005 timeoutReached`；caller 最新说明仅能看到主屏，点击仍 timeout。**本项是未完成必需退出标准，不是已确认 Swift 代码 bug。** 建议在可操作的本 unit Simulator/真实原生现场，完成一个受保护 Toggle 场景，记录触发前/显示中/消失后的选择态、布局/安全区及焦点/VoiceOver结果，由独立产品 reviewer 对账；无需为本项重新跑全部后端矩阵。

### WARNING

无新增实现或 delta 偏离。

### SUGGESTION

无。

### Pending evidence（不冒充通过，也不直接归因产品失败）

1. 修复后 Swift 新 busy Skill 回归实际运行及最终 iOS gate；早期21项 green不能覆盖新增用例。用户已允许转远端，不再要求高负载本地继续等待。
2. 最终受支持 Node 24.22.1 的 backend/native、frontend、iOS tests/archive CI 结果。Draft尚未归档时 archive gate按现有规则仍应失败；这与具体功能 tests 能否通过是两件事。
3. 独立产品 reviewer 的完整 M1-R1–R5结论。本报告已核可复查证据，不替代其真实产品旅程或主观视觉判定。
4. 收尾时 caller 清理其隔离服务和本地临时现场；verifier本轮未创建服务或需清理的资源。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `gateway/agent-capabilities.md`：完整requires、固定角色、单工具不附带Feature、合法关闭、未知状态与占用、interactive、联合维护保留 | 公共 reducer、Feature注册拆分、两条PA发送、CapabilityState/Knowledge/operation链 | 公共6+17cases、native capability/cron/knowledge、PA/IM及R1修复回归 | aligned |
| `gateway/heartbeat-cron.md`：开关与service分离、active保护、tool-only跨重启执行、Heartbeat独立 | needsSchedules/configureSchedules/CronOwners；Heartbeat局部hold和runtime来源检查 | native cron、PA heartbeat；保存后重启choices | aligned |
| `gateway/task-graphs.md`：普通tool允许、自动执行仍Feature、doing/waiting跨会话关闭保护 | IM身份SQL、activeTaskCount/save fence、PA/DSH TaskExecution gate | IM control/task-execution、native Task/PA相关回归 | aligned |
| `im/agents-nodes.md`：工具/Skill联动、浮层、失败保留草稿、usage权限、空业务工具保留固定项 | Web/Swift editor及error envelope；IM静态校验和安全usage投影 | Web95+修复26、早期Swift公共fixtures；三宽度真实geometry；原生局部证据缺口单列 | aligned，完成度受 C1 限制 |
| 本次校正“存储为空全不亮”→“可选业务工具均不亮，模式固定能力保持选中” | 原约定context固定集合仍注册；Web/Swift effectiveTools并集，empty selection不重新启用可选业务工具 | 公共fixedTools测试、native capabilities显式空集、客户端空名单回归 | aligned |

### Uncovered Observable Behavior

未发现本 unit 产品 diff 有尚未投影到上述 delta 的新增对外行为。`requires_tool`→`requires`/`fixed_tools`、新usage接口及结构化错误、默认闭包、卡片tool-only行为、低层局部配置RPC拒绝、旧配置启动拒绝而不代码迁移，均有设计/契约投影。

附加 CI 步骤顺序调整属于验证流程，不改变产品能力契约。父分支合并的 skills/docs 与 iOS push范围过滤为独立主线变化，本 unit 不以其归属宣称新增产品实现。

Outcome: **aligned**。没有 `delta-mismatch` 或已证实 `implementation-mismatch`；未完成证据仍使总体 verdict 为 INCOMPLETE。

## Targeted CI Diff Review

范围：`aeccebccb` 对 `.github/workflows/ci.yml` 的唯一改动；按 caller追加授权执行静态 code-review + verification，不扩大为全仓 CI redesign。

- 归档检查的命令、PR条件、`GITHUB_HEAD_REF`和同一必需 backend job均未改变，仅移到依赖安装、构建/typecheck、native/IM tests、Python、Ruff之后。
- 没有 `continue-on-error`、条件绕过或删除归档检查；未归档Draft仍会在该步骤失败，但不会再仅因归档检查置于前面而根本跳过后端验证。更早的实际构建或测试失败仍按GitHub默认规则停止后续步骤，是正确失败语义。
- 远端 backend/frontend使用Node24.22.1；iOS相关路径和workflow本身触发原生gate。该顺序变更自身无新增可证实缺陷，targeted code-review findings: `[]`；verification: aligned。实际远端运行结果 pending，不依据YAML静态检查宣布CI通过。

本轮仅新增本报告；没有提交，也没有修改其他工作内容。C1及pending evidence补齐后可作一次targeted证据复核；若后续修改产品代码，应按实际fix影响补核。

## Round 2 — Targeted CI / Provider Fixture / Single-thread Card Delta

> Validation snapshot: `5ce70533c → 629c6aff7a347c10ff597d1ece2d179613fef5f4`
> verification_mode: `delta + targeted-closure`; code-review scope: 三个指定提交及其直接调用方；不重新 full。

本节更新 Round 1 的适用证据和完成度。Round 1 的源码一致性判断不能覆盖随后真实产品验收发现的 single_thread 卡片失败，也不能替代真实旅程。独立产品 `acceptance.md` 已记录 A1 invalid_scope；本轮只核其修复和相关自动回归，不静默改写该份验收报告的历史 fail。

### 合并审查结论

| 项目 | 结论 |
|---|---|
| Targeted code review | 无新增存活问题，`code-review-ci-card.json` 为 `[]` |
| 实现一致性 | 三个实际修复均 aligned；没有新增授权旁路、产品依赖图副本或通过放宽超时掩盖失败 |
| 原始 P1 / P2 | 保持 closed；三处增量不改变恢复 snapshot 或命名 Skill 关闭预检 |
| 产品 A1 | invalid_scope 根因及修复经直接代码链和红绿回归核实；**真实卡片 targeted 复验仍 pending**，不能在验收层宣布 closed |
| C1 / 产品 A2 | 原生 Toggle、VoiceOver/焦点、安全区可见交互仍缺证据；iOS CI通过不关闭此项 |
| 产品 A3 | 独立 reviewer 仍缺维护/Heartbeat在途、部分tool-only及Global/Personal实际卡片证据；自动化证据可支持实现，不能把未走完的真实旅程记pass |
| 最终 verdict | **INCOMPLETE**；本轮没有新增实现 mismatch，仍不能宣布全部M1退出标准完成 |
| requires_full_verification | `false`；卡片实际复验和其余有界证据可 targeted 补核 |

### 三处实际差分

| 差分 | 触发失败与期望契约 | 实现 / 调用方核对 | 直接验证 | Outcome |
|---|---|---|---|---|
| `704c62d89`：干净前端job编译共享契约 | Web引入browser-safe `@nano/product-contracts/capabilities` 后，干净frontend job仅npm ci，没有packages/product-contracts/lib，17 suites加载失败。D4要求公开subpath可构建，不用源码alias绕过 | `.github/workflows/ci.yml:140` 在npm ci后执行 `npx tsc -p ../../../packages/product-contracts/tsconfig.json --typeRoots ./node_modules/@types`；前端已有TypeScript和显式@types/node；product-contracts tsconfig输出lib，exports仍指lib；不加入业务跨包相对import | caller已在Node24运行同一显式命令通过；修复后的干净远端frontend完整结果仍待返回。原run已过863项不能覆盖17个未加载suite | aligned；targeted code review无finding |
| `e53d3a1d4`：providers纯模型夹具遵守能力契约 | 旧fixture tool_allowlist=[]但Feature按默认开启，configuration.apply拒绝未断言，随后session.ensure报Unknown configuration revision；目标测试仅核credential移除，不应隐式要求不完整Feature配置可用 | `apps/node/tests/providers.test.ts:74` 显式六Feature=false，断言effective=true；真实native lifecycle、HTTP授权头断言、20秒永久超时及产品校验均保留 | run39990544671的native回归为637pass/1fail；修复用例Node24.22.1以原20秒超时单跑11.66秒通过，`/tmp/feat645-provider-fixture-fix.log` | aligned；失败前提修正，没有绕过产品依赖 |
| `629c6aff7`：single_thread query不注册Global Work | M1-R3 / gateway delta要求IntelligentUI关闭、send_message单开时普通/Global/Personal实际能发布合法卡片；真实single_thread卡片在query前无条件ensureAuthority，IM agent.session.ensure只允许global而返回invalid_scope | `packages/personal-assistant/src/global-agent.ts:491` 仅config.mode==='global'调用ensureAuthority；IM `gateway.ts:564` 的Global限制保留；`work.ts:488` 本已仅Global查询要求Work session记录，single_thread仍验证agent/node/is_stale/available/用户/会话；ProductCall绑定身份、发送revalidation/schema/approval/idempotency均未删除。Global与Personal的原global注册仍保留 | `interactive-replies.test.ts:26` 明确single_thread，并让mock的Global注册失败；修前Web/Feishu两项invalid_scope红（`/tmp/feat645-single-card-red.log`），修后同文件+global-agent共52tests过（`/tmp/feat645-single-card-green.log`）；PA build通过。真实卡片发布待产品reviewer复验 | aligned；机制修复自动回归通过，产品A1验收关闭pending |

本轮还检查 query 的其他实际调用方：messageContext 的目标身份查询、inbox describe/info和conversations，以及send的resolve_target/info。mode条件与服务器现有Work.query分支匹配；普通single_thread不建立Global记录，并不免除IM现有访问校验。未对未知或离线状态增加成功fallback，query仍传播服务器拒绝。

### 更新的远端自动化证据

本 verifier 通过GitHub connector只读获取 run `39990544671` 最新job/step summaries。iOS job `120540953635` 已 `completed / success`，其 `Native regression tests` 与 `Release device archive` 两步均为 `completed / success`。

- [该run的iOS job](https://github.com/Mrchen116/nano-multiagent/actions/runs/39990544671/job/120540953635) 对应 `5ce70533c`，包含 `9802c9347` Swift busy Skill修复及新增三模式回归；`5ce70533c..629c6aff7` 没有iOS源码/测试改动。因此可补齐Round1“修复后Swift新增回归运行pending”和对应iOS Release archive缺口。
- 这是Swift/iOS自动化gate证据，不是原生可见交互、焦点/VoiceOver或安全区验收；C1和产品A2保持未完成。
- 同一旧run的backend job因providers fixture失败、frontend因共享契约lib缺失失败，与本次两项修复相对应；旧run不是最终全量CI green。`629c6aff7` 的最终backend/frontend以及整个PR状态仍需以其对应run为准。用户已允许远端CI，本轮不重跑大矩阵。

### Corrected Delta Reconciliation 增量

| Delta / 对外行为 | 本轮影响 | Outcome |
|---|---|---|
| gateway agent-capabilities：IntelligentUI关但send_message正常，普通/Global/Personal保留权限与审批 | 新增修复仅消除single_thread查询误走Global注册；目标行为在原delta中已明确，不需为修复放宽契约 | aligned；实际旅程复验pending |
| im agents-nodes：配置与实际使用一致 | 卡片的invalid_scope是真实执行链偏离，已按原契约修复，不能仅凭保存成功替代发布验收 | aligned；产品A1的最终结论待补 |
| 架构与运行配置 | 无新产品对外接口；CI只生成既有公开包lib，providers只修测试前提 | aligned；no additional spec delta |

本轮没有发现三项差分产生尚未被unit delta覆盖的新增产品行为。仅追加报告及写入指定JSON，没有提交或修改源码/测试/配置，也没有操作隔离服务。

## Round 3 — Targeted Edit Fixture / Workspace Preparation Delta

> validated_at: `e725603ed5d4c8d799ed5c38055a9b4a5bf7c3ce`
> executed_base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
> fix_delta_range: `629c6aff7a347c10ff597d1ece2d179613fef5f4..e725603ed5d4c8d799ed5c38055a9b4a5bf7c3ce`
> verification_mode: `delta + targeted-closure`; scope为caller指定两处修复及直接调用方，不重新full。

### 本轮结论

- Targeted code-review无新增存活问题：`code-review-workspace.json` 为 `[]`。原P1（拒绝候选污染重启快照）与P2（命名Skill关闭预检）保持closed。
- 两处修复与原契约 **aligned**；workspace准备时序问题的实现/回归已修复，但Personal真实创建/发卡片的产品复验仍pending。本轮不根据尚未收到的结果关闭产品A1/A3，也不提前关闭原生C1/A2。
- Web干净job的共享契约产物问题及旧edit fixture问题已有远端完整通过证据；这只补Web自动化完成度，不把Web通过等同于整个PR/原生可见验收通过。
- 总体仍为 **INCOMPLETE**；`requires_full_verification: false`。后续产品与最终CI结果可作targeted证据更新，无需再次full。

### 差分核对

| 修复 | 契约 / 失败原因 | 实现及直接调用方证据 | 测试证据 | Outcome |
|---|---|---|---|---|
| `3af469eb7`：agent-edit夹具与实际选择模式/usage一致 | UI关闭动作必须刷新真实usage，读取失败保持原态；D4允许历史explicit allowlist按原语义调整，不要求任意Skill编辑都转换mode | `agent-edit.test.tsx:27,43` 明确initial mode为explicit_allowlist；`:76` 为实际capability-usage路径提供空占用成功响应；`:209` 期望启用集合为tdd-execution-worker/plan，mode保持allowlist。仍执行页面交互、版本更新及实际PATCH快照断言，没有更改产品实现、永久超时或绕过usage | `/tmp/feat645-web-edit-fixture-green.log` 为5tests通过；GitHub job120547121912的共享契约构建及完整vitest步骤均success | aligned；targeted code-review无finding |
| `e725603ed`：新Agent/Personal workspace在runtime prepare前可挂载 | 真实新PA创建在prepare中WorkspaceExtensions.attach/realpath报ENOENT；D6要求prepare先于candidate持久化，而运行时挂载仍需要真实目录 | `apps/node/src/configuration.ts:97-113` 保留identity、mode、Personal owner/binding不可变、Global workspace不可变、完整静态依赖校验；先由runtime(resolved)校验模型、reasoning/fallback、approval读取，再mkdir目标目录，返回候选，不调用persist/write。Node main将resolve交给既有ConfigurationOperations；后者仍依次保存operation receipt、校验CAS、prepare、成功后persist、apply | `apps/node/tests/configuration.test.ts:45` 原默认/自定义workspace base两场景扩展目录存在、config.current不存在、重读磁盘也不存在候选断言；修前两项ENOENT，修后Node24.22.1下9tests与Node build通过，见validation.md“新建个人助手workspace时序修复” | aligned；代码/回归修复成立，真实新PA验收pending |

### Workspace持久化与权限边界

1. `NodeConfiguration.resolve` 的新增副作用是创建经现有验证解析的目标目录；**不代表零文件系统副作用**。新目录可供catalog/preview及WorkspaceExtensions挂载；如果后续prepare拒绝，空目录可能已存在，但候选不因此成为持久Agent配置、有效runtime配置或已确认重启快照。
2. `packages/personal-assistant/src/configuration.ts:43-79` 没有变化：resolve之后写入的是既有write-ahead operation receipt；prepare不ready时保存rejected receipt并release，只有ready后调用persist。`NodeConfiguration.write` 才写配置文件、更新value.agents；该持久边界没有前移。
3. `apps/node/src/runtime-partitions.ts` 的routeConfiguration/only-effective-apply snapshot规则没有变化；新增mkdir不调用assign、不启动Agent、不发布availability，不重新引入P1。
4. IM创建入口仍先认证owner及owning node，Personal创建仍由server-issued binding产生candidate；Node仍核Personal owner与global mode、既有binding及Global workspace不可变。新增mkdir不接受额外身份字段、不放宽会话/资源空间访问、不关闭Auto或改审批规则。
5. 目标路径仍来自已选择workspace或现有defaultWorkspace，沿用原persist/write已经使用的recursive mkdir行为；不增加任意路径扫描、复制已有内容或自动历史迁移。runtime配置校验发生在mkdir之前；能力/模型等前置失败不会因为这两行新增逻辑而写入candidate。
6. 创建preview/capability入口原已在runtime挂载前mkdir（Node `main.ts:206`），本修复补齐的是configuration operation真实resolve→prepare路径，未新增另一份配置真相。

### 证据更新与保留缺口

本verifier通过GitHub connector读取job `120547121912` 的step summaries：`Install dependencies`、`Build shared browser contracts`、`Dependency audit (critical)`、`vitest run`和Complete job均为completed/success。因此Round2的“修复后干净frontend完整结果pending”已由真实成功步骤补齐；caller将其归属为包含edit fixture修复的远端Web job。本轮e725仅改变Node目录准备及测试，没有Web代码变化。

Node workspace红绿与9tests结果复用caller的`validation.md`记录及实际新增断言，没有重复启动大矩阵或服务。记录可证明resolve前置目录和未持久candidate，不能替代“真实Personal创建、首条输入与卡片发布”的产品入口结果。

caller本轮交接称Round2的single_thread/Global真实卡片、Memory/Skill维护busy保护已pass；这些结果尚未在本轮收齐独立产品报告，本报告先保留为交接进展，不据此预写全部M1-R3/R4或产品A3完成。Personal待正常重启后复验、Heartbeat进行中、native AX恢复后已交独立reviewer；**这三部分在收到实际结果前继续pending**。iOS自动化测试/archive已通过的Round2证据仍适用，原生C1/A2只由可见交互证据关闭。

### Corrected Delta Reconciliation 增量

两项修复均落实既有“配置操作可恢复/先校验再持久化”“创建默认workspace可实际运行”“工具/Skill选择真实可用且保留mode”承诺，没有新产品对外接口或需求变化。无需为修复另写行为delta：**no additional spec delta / aligned**。

本轮只新增指定JSON及追加本报告；未提交、未修改业务或测试、未操作服务，也未替产品reviewer修改acceptance结论。

## Round 4 — Final Targeted Evidence Closure

> validated_at: `e9b76b457979faa121ec605789c8fe7a2b63d203`
> executed_base: `55376c1112ff870837a6ee65febf52e1f3686a9b`
> verification_mode: `targeted-closure + corrected-delta evidence reconciliation`
> 本轮范围：C1及Round1–3尚未收齐的产品/CI证据；已核实 `e725603ed..e9b76b457` 没有apps/packages/src或workflow变更，仅报告/截图与用户批准的验证范围记录。不重跑code review、测试或真实服务。

### 最终结论

**PASS（依用户明确批准后的本次验收范围）**。0 CRITICAL / 0 WARNING / 0 SUGGESTION，`requires_full_verification: false`。C1和产品A1/A2/A3的本次阻塞项已收口；原P1/P2保持closed，既有空数组code-review closure及targeted结果沿用，corrected-delta仍为 **aligned**。

此结论覆盖实现一致性、已声明退出标准及本次有效证据；不将VoiceOver实体iPhone播报/读屏焦点列为已测，不宣称生产部署、公网长期稳定或所有历史流程限制已修复。后续canonical归并、unit archive、对应归档门禁重跑及caller拥有的服务/Simulator/临时数据清理仍是交付收尾动作。

### 验证范围的授权与原生证据

`spec.md`“实施验收范围确认”、`design.md`“实施验收平台范围确认”和`design-review.md`作者补注一致记录：用户先确认“真机”为实体iPhone、Simulator已测、剩余仅为VoiceOver播报/读屏焦点后，明确回复“不用不用这个。”。caller将该直接用户授权转交独立产品reviewer，`acceptance.md` Round2据此只排除该项门禁，未改变依赖、关闭保护、Toast呈现或实现。**本verifier采纳的是明确的范围授权，不是自行把未测项降成通过。**

本轮独立打开并核对以下真实原生截图及Round2操作记录：

- `acceptance-r2-native-dependency.png`：本任务Nano feat645 Simulator原生配置Form，Task graphs和Scheduled jobs均开启，Tools为22；与reviewer的Task开启→Scheduled jobs 0→1、Tools17→22操作记录一致。
- `acceptance-r2-native-toast-visible.png` / `acceptance-r2-native-toast-dismissed.png`：固定new_context保持开启；显示时提示完整位于应用画布内且不盖目标switch，消失后原工具行和下方Form布局位置一致，无占位行。画面为真实Simulator窗口714×1660并含chrome，不是Web390或HTML意图原型。
- reviewer还在原生实际执行Scheduled jobs受Task保护、skill受Skill Creation保护、关闭Task后可再关闭Cron、保存后收到node confirmed并由Web回读一致；AX能读取switch名称/值和提示。`acceptance-r2-native-block-toast.png`和`acceptance-r2-native-tool-block.png`只作为相应状态的补充，不把未捕获到提示的静态帧单独当作Toast证明。
- 安装产物与该任务构建的主程序SHA256均为`1f5031b3fa1a6e5df8d2de47c9186f5ba10110ee751373842777db97e7645e9e`，debug dylib摘要也一致，见`validation.md`与reviewer独立比对记录。后续Node/PA修复没有Swift变更，证据适用受审实现。

**C1 closure：closed within approved scope。** 原生Toggle/提示显隐/AX/安全区/保存确认已有实际证据；VoiceOver实体设备语音和读屏焦点仍未测、按用户授权排除。AX可读或Simulator窗口聚焦均不被改写成实际VoiceOver焦点/播报通过。

### 其余pending证据闭环

| 历史缺口 / 退出标准 | 最终直接证据 | 收口 |
|---|---|---|
| A1 / M1-R3：普通、Global、Personal在IntelligentUI关时实际发布新卡片 | `acceptance.md` R2-J1逐条给出配置、真实调用及可见新卡片；single消息ID`e7b65d17cba04eceb5eebb885783d238`，Global/PA分别显示验收卡片。Personal截图本轮已独立打开，确认原PA会话有“PA645验收卡片”可见内容；保留正常API辅助恢复前提 | closed；不再仅依mock或选中态证明发送 |
| 新workspace真实PA恢复 | e725修复后正常Node restart；caller使用原creation.request_key和原node/name调用正常产品创建API，HTTP201/binding active；reviewer随后真实进入该PA、配置并发布卡片 | 本次实现及实际使用证据closed；旧pending UI恢复入口限制保留，不声称全程UI创建顺畅 |
| A3 / M1-R2：真实Memory/Skill维护busy且关闭不cancel | R2-J2前台收口后关闭Memory/Skill均保持checked并提示in-use；后台随后继续成功写入隔离MEMORY.md并通知；两张busy截图和真实后续写入/来源session定位齐备 | closed；“不取消已接受工作”有真实后果证据 |
| A3 / M1-R2：Heartbeat真实busy、阻止关闭而工作继续 | R2-J2两次capability-usage返回heartbeat feature busy，Task/Schedule计数均0；点击关闭保持checked且in-use；同一回合继续产出HEARTBEAT645_READ_OK，32tools/49.2秒；随后按正常cadence/version刷新再合法关闭 | closed；初次bash被low参数审批拒绝的回合明确不计成功 |
| A3 / M1-R4：tool-only不反开Feature或恢复自动行为 | R2-J1 memory合法写入；R2-J4六Feature全false下skill_manage list、task_graph创建todo；约01:28:50至01:30:30有界观察无新后台维护，四次MEMORY hash/mtime相同，候选未写入、todo未推进、usage无active/busy；结合既有生命周期集成回归 | closed；不把有限观察夸成长时间无人值守保证 |
| M1-R1/R2原生及M1-W3 must-match | 上述真实Simulator交互/截图/AX、保存confirmed和Web回读；原Web1440/768/390三阶段几何与独立R1/R2产品检查仍有效 | closed；VoiceOver按明确授权排除且仍记未测 |
| M1-R5整理/后续选择 | R2覆盖矩阵明确继承本unit旧fixture隔离演练及`restart-choices.json`，并标注其实际版本1ce3925a3；后续正常restart和合法tool-only使用未反向迁移 | retained covered；无生产迁移声明 |

独立产品`acceptance.md`保留Round1 fail，Round2对15个Scenario逐项对账并最终pass；没有删除失败历史。M1-R1–R5和M1-W1–W5的实现/证据完成度在本次调整范围内已闭合，先前Round1–3的INCOMPLETE是当时快照，现由本节最终结论取代。

### 最终远端CI核对

本verifier通过GitHub connector只读获取 [run39992871340](https://github.com/Mrchen116/nano-multiagent/actions/runs/39992871340) 最新job/step summaries，核对如下。该run为e725产品版本，e725→本轮validated_at没有源代码或workflow变化，结果适用。

| Job | 实际结果 | 解释 |
|---|---|---|
| backend `120548802272` | Build/typecheck、packaged runtime、native/IM、Python、Ruff check/format均success；仅Change unit is archived失败 | `validation.md`记录127files/638tests、Python65passed/31deselected及85files format。归档检查仍正确拒绝active unit，整个backend job当前结论仍failure，**不写成整个CI green** |
| Web `120548803026` | completed/success；npm ci、共享契约构建、critical audit、vitest均success | `validation.md`记录104files/987tests全部通过，已覆盖先前干净job与edit fixture问题 |
| iOS `120548889910` | completed/success；Native regression tests与Release device archive均success | 补齐最终Swift自动回归及device archive证据；真实可见交互仍独立取上述产品证据 |

因此最终功能/构建/格式检查已通过，唯一剩余CI红项为交付流程中的active-unit归档门禁。caller应在canonical归并与archive后让该门禁按实际归档状态通过；本轮不修改CI规则或提前宣称该步骤已成功。

### 保留的边界与交接

- VoiceOver实体iPhone播报/读屏焦点未测，按用户本次明确授权排除；不得在最终交付描述中省略“未测”或改写成通过。
- 旧PA pending UI未提供可达Retry的恢复限制仍存在；本轮通过正常认证产品API、原request key恢复，随后reviewer真实UI配置/调用成功。不得宣称PA创建全程无故障，也不得把API辅助恢复写成直接改DB。
- 自动审批模型不支持low参数、实时连接重连现象仍保留；验收仅用必要的逐项Allow once/实际持久结果核对，没有修改审批模型或弱化权限，不宣称这些独立限制已修复。
- reviewer补注的四个自建标签`1805418682`、`1805418685`、`1805418688`、`1805418691`因Debugger unattached未关闭，已明确移交caller；本轮没有代为操作用户或其他任务标签。隔离服务、Simulator、临时配置/数据的最终清理由caller执行，不在未核实前记已完成。
- 既有`code-review-closure.json`、`code-review-ci-card.json`、`code-review-workspace.json`的空数组及corrected-delta aligned结论均沿用。本轮只追加本报告，不重开全审、不运行测试、不修改其他文件、不提交。

Final outcome: **PASS / aligned；0 CRITICAL、0 WARNING、0 SUGGESTION（用户已批准的验证范围内）**。可继续canonical归并、unit归档及最终交付收尾；没有新增实现修复要求。

### Final sync补注

`effective_base: 503c98e93`，`effective_through: f93700d2cf69f7e5c9de4bf903afbef3c8b91377`。原executed_base和validated_at保持不变；本轮只读核实e9b76b457→f937的apps/packages/src及workflow无差异，主线增量仅prod-fleet-deploy的备份轮转说明，不影响上述结论，不触发full复验。

caller交接已通过e2e-down正常停止本任务IM/Node/DSH，原PID均不存在，54795/48646无listener，专属Simulator已shutdown；临时secret清理仍在进行。该状态按caller现场证据登记，本verifier未另行操作服务，也不把尚在进行的secret清理或未补证的浏览器标签关闭记为完成。
