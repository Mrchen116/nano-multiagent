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
