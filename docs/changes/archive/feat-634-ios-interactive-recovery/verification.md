# Verification Report: feat-634-ios-interactive-recovery

> 最新结论：Round 3 targeted-closure PASS（`50a56c8ccea9`），0 CRITICAL / 0 WARNING；corrected-delta aligned。W3本地交付证据与独立产品验收已闭环，可以提交PR。新head远端CI待PR，手机安装按用户要求延后合入。以下Summary至Issues为Round1历史记录。

> Final validation snapshot: `18e1af8b1 → 50a56c8ccea9c004da71a971a8536f47147d2240`；初轮full及各修复轮固定版本见各轮记录。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 全部 10 个 spec Scenario、5 个 delta Scenario、M1 R1–R3/W1–W3 均已映射；最终交付证据由主任务闭环 |
| Correctness | 1 WARNING：保留新正文时，旧附件未清理，会随下一次新发送重复发送 |
| Coherence | 核心职责与设计一致；附件清理回归需修复 |

- review_round: 1；verification_mode: full，并合并 corrected-delta 核对。
- verdict: **FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION**。
- requires_full_verification: false（此次已按 full 审核；该局部清理修复可 targeted closure）。
- 当前报告只做实现/契约/测试核对，不代替独立真实产品验收。合入后手机安装按用户最新交付时序 deferred。

## Completeness

唯一 milestone 为 design 中 M1-native-chat，没有独立 milestone.md/tasks.md；简化流程不强制该文件。M1 progress 已提供实施归属、测试和真栈自检记录。以下覆盖不将“存在代码”写为“产品实玩通过”。

| M1 退出标准 | 实现及直接证据 | 状态 |
|---|---|---|
| R1 真客户端探索、条件/图表/查询、390 宽可读 | SwiftUI NodeView/Controls/Charts；主任务原生20→35、140→245自检与截图；Query VM regression | 实现具备；独立 reviewer 的真实查询/窄屏/大字体与可达性结论待 acceptance |
| R2 私人草稿、冲突、动作、只读与权限 | Runtime load/flush/activate/current；4 个真实 JSCore/HTTP seam XCTest；ChatStateTests 只读与权限测试 | 静态/自动化 covered；产品 reviewer 判真实旅程 |
| R3 未知发送恢复、无重复、新草稿、模拟器打开 | SendAttemptStore + ChatStore resolve/recover；SendRecoveryTests；安全真栈 recovery 汇总 | 有直接证据；旧附件清理 WARNING |
| W1 固定解析器、全目录、类型/动作/状态契约、原型对照 | 精确版本/许可证/资源检查；83 组件映射；随包资源6条测试和JSCore4条 | 源码/协议 covered；真实画面对照见原型合同表，不声称逐组件GUI已验 |
| W2 跨重启、提及改名、附件、身份撤销 | SendRecoveryTests.swift:16/53/76/93/118/142/156/177/192；SessionTests/ChatStateTests 延续覆盖 | covered with WARNING：:16 已有前提漏断言旧附件清理 |
| W3 模拟器测试、Release archive、独立审查、一致性、真客户端验收、IPA来源 | iOS43+17已过；本报告+code-review；build/typecheck/docs/runtime通过；Release/IPA/最终acceptance由主任务执行 | 交付证据尚需在PR前最终对账；不将进行中的交付误报实现缺失 |

## Correctness

以下路径均相对仓库根目录。

| Requirement / Scenario | 实现位置（file:line） | 测试/直接证据 | 状态 |
|---|---|---|---|
| 原生交互回复可阅读、探索与继续 / 阅读和本地探索 | ChatMessageView.swift:44；InteractiveNodeView.swift:18；InteractiveControls.swift:18；InteractiveCharts.swift:55；InteractiveRuntime.swift:76 | 随包VM反应计算、Reset/类型；InteractiveRuntimeTests.swift:11；主任务真实35→245 | covered；GUI大字体/窄屏以acceptance为准 |
| 同上 / 明确请求继续 | InteractiveRuntime.swift:83–147；ChatStore.swift:330/350/410 | RuntimeTests.swift:11；VM Set/完整Form/Mutation；RecoveryTests.swift:53/76 | covered；回执表示请求已发送 |
| 私人交互状态与权限一致 / 恢复私人编辑 | InteractiveRuntime.swift:42/142/175；InteractiveModels.swift:34 | RuntimeTests.swift:34 冲突停止覆盖及显式读取最新；真实35恢复 | covered |
| 同上 / 发送带相关背景的文字 | ChatStore.swift:299/392；ChatAPI.swift:14 | SendRecoveryTests.swift:192：最近三张、旧历史过滤、群聊不附带；冻结bytes测试 | covered |
| 同上 / 历史、只读与无法呈现的内容 | ChatMessageView.swift:46；InteractiveCardView.swift:14/21；InteractiveRuntime.swift:38/47/68/98 | RuntimeTests.swift:52；ChatStateTests.swift:88/112；读取失败保留摘要与读取最新 | covered；历史真实交互由产品reviewer核实 |
| 不确定发送跨重启恢复且不重复 / 已保存但返回丢失后重新打开 | ChatStore.swift:44/361/410；SendAttemptStore.swift:34 | SendRecoveryTests.swift:16/53/76/93/156；真栈summary 两POST一消息 | WARNING：新正文保留时旧附件残留，下一次新发送重复附件 |
| 同上 / 提及成员发生变化后重试 | ChatAPI.swift:14/30；ChatStore.swift:303/420 | SendRecoveryTests.swift:16 原bytes/key与原mention target；真栈改名恢复 | covered |
| 同上 / 退出、切服务或撤销权限 | Session.swift:40/63/79/98/144；ChatStore.swift:159/461/469/478 | SendRecoveryTests.swift:118/142/177；RuntimeTests.swift:68；SessionTests与ChatStateTests | covered：身份/服务隔离、撤销清理、迟到fence |
| 模拟器验证后交付PR，合入后更新手机 / 交付可合入版本 | build.sh:6；Debug.plist/Release.plist；MeView.swift:161；Xcode project version 0.2.0(634) | 已有测试log/xcresult；最终Release/IPA/源码revision由主任务补齐 | 已实现追溯；本报告因WARNING不建议提PR |
| 同上 / 合入后安装 | 沿用AltStore安装、原bundle ID；design Runbook | 用户明确改为合入后执行；当前未声称手机新版已打开 | deferred，当前PR不以手机登录/安装为门禁 |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 公开解释器复用，原生呈现，无第二Agent运行时 | 是 | Runtime/interactive-runtime.ts:1–14；InteractiveRuntime.swift:50–58；NodeView/Controls/Charts；无后端/DSH变更 |
| 全目录呈现，数据slot由父级消费 | 是（静态映射） | InteractiveNodeView.swift:18–153；83注册项对照；全目录实际视觉质量不由静态结论替代 |
| 纯本地探索；500ms私人CAS；冲突不覆盖；离开flush | 是 | InteractiveRuntime.swift:142–187；InteractiveModels.swift:35–39 |
| 白名单Query/Mutation，Set后快照，OpenURL限制 | 是 | Runtime/interactive-runtime.ts:107–139；InteractiveRuntime.swift:107/121/223–228 |
| 首次POST前冻结原body/key、落盘失败不发、交互namespace lookup | 是 | ChatAPI.swift:14–39；SendAttemptStore.swift:34；ChatStore.swift:303/343/413/420 |
| 恢复仅查，重试404后原bytes，409先核原结果 | 是 | ChatStore.swift:361–381/410–429；RecoveryTests.swift:53/76/93 |
| Session清理，origin/user隔离，迟到响应fence | 是 | Session.swift:40–60/79/98/144；SendAttemptStore.swift:62；ChatStore.swift:404/461/469 |
| 新草稿保留、附件与发送结果一致 | 部分 | ChatStore.swift:435–440：正文保留正确，已发送附件清理错误 |
| 版本与安装来源可追溯 | 接线正确 | plist + build.sh:6–17 + MeView.swift:161；最终产物/合入后安装仍待交付 |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 回复内探索：结论/控制/结果相邻、窄屏折行 | R1/W1 | NodeView.swift:18/229/261；原生字段和图表 | design-review R1原型；M1 progress真客户端35/245及截图定位 | 结构covered；最终实际对照待acceptance |
| 明确继续：动作清晰、保留内容、不冒充完成 | R2/W1 | CardView.swift:17–19；Runtime.swift:83–147 | M1 progress明确动作+fixture确认可见回复 | covered；产品判定见acceptance |
| 未知发送：简短核对/重试、新草稿保持 | R3/W2 | ConversationView.swift:141；CardView.swift:26；ChatStore.swift:410 | recovery汇总；RecoveryTests.swift:16/156 | WARNING：正文保留时旧附件清理遗漏 |
| 历史/冲突：内容可读、写受限、读取最新 | R2/W1 | Runtime.swift:68/98/159；CardView.swift:16/21 | RuntimeTests.swift:34/52；design-review原型冲突走查 | covered；真实画面待acceptance |
| 图表/系统控件 may-adapt；登录/审批 out-of-scope | R1/W1、W2 | Controls/Charts；ChatMessageView.swift:80；原Session测试 | 真实原生自检；现有回归测试 | 合同保持；不做主观视觉评分 |

截图只是带定位的当次证据，不把临时图片提交永久测试。独立产品 reviewer 的报告应连接最终可复查原生对照；本报告不把原型当真实产品验收。

## Evidence and regression ownership

- 独立窄验证：`pnpm check:ios-runtime`（含生成资源逐字节check和tsc）通过；`pnpm exec vitest run src/IM/ios/Runtime/interactive-runtime.test.ts` 6/6通过，执行真正打包资源。生成脚本携带 lang-core1.0.1、zod4.6.5和ci-info许可证；无任意网络host。
- 复用 iOS `43 XCTest + 17 Swift Testing` 零失败；`/tmp/nano-feat634-ios-test.log`；xcresult `/tmp/nano-feat634-build/Logs/Test/Test-NanoIM-2026.10.22_01-02-20-+0800.xcresult`。来源/命令见M1 progress；之后版本/图片/辅助名称变动需最终集成构建复核。
- build/typecheck/docs-check已有主任务可信通过证据；根测试目前535/537、2个未改DSH超时，串行复核结果尚未纳入本报告，不能称全绿。
- `/tmp/nano-feat634-recovery-evidence.json`已读取：post_count2、same_key/identical_body true、committed_message_count1；该证据证明真栈重启与改名的不可变重试，不证明LLM生成或物理安装。
- 既有 ChatStateTests/SessionTests 扩展沿用HTTP/session seam；新增 SendRecoveryTests负责持久跨实例，InteractiveRuntimeTests负责真实JSCore→原生HTTP，VM测试负责无DOM/Node的随包运行。这些落层保护不同失败原因，无需复制同一行为到更多层。附件缺口应直接补既有恢复测试，勿另建按milestone命名测试。

## Issues

### CRITICAL

无实现或架构级缺失。最终Release/IPA与独立产品验收目前由主任务并行执行，PR前仍须完成既定W3证据，不将该进行中工作写为已经通过。

### WARNING

- **W1 / CONFIRMED / P2：保留新正文时重复保留旧附件。** 契约：spec“已保存但返回丢失后重新打开”与current ios媒体/恢复契约；实际位置`src/IM/ios/NanoIM/Features/Chat/ChatStore.swift:438`。正文改变会跳过旧附件清理，pending却已移除，下一条新发送再次携带该附件。建议将按原attempt附件id清理移出正文相等分支，保留后续新正文及新增附件；在`SendRecoveryTests.swift:16`增加已发附件清空/下一次新请求不带旧附件的可观察断言。源码条件与新旧diff直接确认，不需要额外未证实前提。

### SUGGESTION

无。

## Round 2 — Targeted Closure

- verification_mode: targeted-closure；review_round: 2。
- finding_origin_head: `bbc03566a30e9b269857d7369738a231d01e783a`；fix_delta_range: `bbc03566a..35a9c0588`。
- executed_base: `18e1af8b1`；validated_at: `35a9c0588dfb3bd9f6c34e678c2d2cfd3396889c`；已核 HEAD 与冻结版本一致。
- verdict: **PASS（本次静态闭合范围）**；issues: []；validated_issues: [Round1-W1 closed, product-R1-minor implementation closed]。
- requires_full_verification: false；top_concern: 最终 iOS 全套、Release/IPA 与独立真实产品验收仍需完成既定 W3；不因此扩大本次局部源码审查。

### Focus closure

| Focus / 关联契约 | 实现/回归直接证据 | Outcome |
|---|---|---|
| Round1-W1，持久恢复/保留后续草稿与附件 | `ChatStore.swift:435–440`：正文仍按相等条件清空，旧附件独立按 sentIDs 移除，新附件保留；`SendRecoveryTests.swift:16–54` 新附件断言 | closed |
| 同一原次 retry 保持不可变请求 | 同一既有测试在加入新附件后仍断言两次 bytes/key 相同，只有 composer 待发集被清理 | 保留原结论，未引入“重试带新附件” |
| 产品 R1 minor：未知卡片不展示旧成功提示 | `InteractiveCardView.swift:19` 增加 !hasPending；未修改 pending 或发送结果判定 | implementation closed；真实GUI复验归acceptance |

### Evidence

- `/tmp/nano-feat634-send-attachment-red.log`：扩展既有恢复测试在原实现上失败，得到 `[kept,new]`，期望 `[new]`，直接复现历史 finding。
- `/tmp/nano-feat634-send-attachment-green.log`：真实产品源码复制至 SwiftPM seam 后，修复版本27/27 XCTest零失败；覆盖 SendRecovery/ChatState/Session。这是可信复用行为证据，非原生UI完成声明。
- `/tmp/nano-feat634-fix-build.log`：Simulator BUILD SUCCEEDED；本审查者未并发启动Xcode/Simulator。
- `acceptance.md` 当前为进行中，已独立记录真原生探索、私人CAS、重复key/body单条消息，以及后续环境恢复重验边界；不能将其解释为完整验收通过。
- 最终 iOS 全套、Release archive（`/tmp/nano-feat634-release-archive.log`）、IPA 来源与产品全部场景，由主任务完成后补入本报告，当前未记已完成。

本次 patch 未触及共享网络/授权/解析边界，旧 full 映射继续适用；只需补充交付证据，不要求再做 full 静态审核。

## Round 3 — Final Targeted Closure and W3 Completion

- verification_mode: targeted-closure + corrected-delta evidence reconciliation；review_round: 3。
- executed_base / effective_base: `18e1af8b1`；validated_at: `50a56c8ccea9c004da71a971a8536f47147d2240`。HEAD已核对；caller已fetch且main无新增。
- fix_delta_range: `35a9c0588..50a56c8ccea9`；唯一产品变化为`InteractiveNodeView.swift:29`允许正文自然增长高度，不重新审核整个unit。
- verdict: **PASS — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**；issues: []。
- validated_issues: [历史附件P2 closed, pending状态minor closed, 大字正文major closed]。
- requires_full_verification: false；top_concern: 无存活实现问题；新head远端CI待PR创建后执行，手机安装待合入后执行。

### Focus and reference closure

`InteractiveNodeView.swift:29`的`.fixedSize(horizontal:false,vertical:true)`保留父级宽度约束，按Markdown实际内容获得高度，直接对应“窄屏/大字体主内容可读”的现有契约。没有修改解析、动作、私人状态或可靠发送。reviewer独立查看红图`/tmp/nano634-390-largefont-truncation.png`与绿图`/tmp/nano634-r3-largefont-full.png`、默认图`/tmp/nano634-r3-default.png`，确认相同30分钟结果完整两行/默认完整一行，控制、结果与按钮关系仍成立。真实选择、恢复按钮可用性采用独立产品`acceptance.md` Round3记录；静态查看不冒充本reviewer执行触摸。

| M1退出标准 / Spec范围 | 最终证据 | Completion |
|---|---|---|
| R1/W1 探索、全目录接线、类型/动作、查询、390与大字/原型对照 | 既有full源码映射/资源6条/JSCore测试；acceptance R1–R3，390×844默认/accessibility-medium前后对照；条件/Each/选择/图表/Query实际操作 | complete |
| R2 私人草稿、CAS、显式动作、历史/只读、权限 | acceptance记录CAS/Load latest、A/B私人状态、真实observer、superseded/future版本、双动作与当前state | complete |
| R3/W2 文字/附件/卡片不确定恢复、改名、新草稿、退出/切服务/撤销 | acceptance真实GUI与权威同key/body消息对账；附件单条消息计数补证；恢复测试含旧附件移除/新附件保留 | complete |
| W3 iOS模拟器全套、Release archive/IPA、版本追溯、独立审查/验证/真客户端验收 | 下表43+17全套、50a build/archive、IPA核对；本报告/code-review/acceptance最新pass | complete for pre-PR local gates |
| Spec全部10 Scenario | acceptance最终9个适用Scenario pass；第10合入后安装not-applicable/deferred；源码与自动化映射继承Round1并闭合Round2/3问题 | 9/9适用完成，1按用户时序延后 |

### Final evidence and limits

| Claim / baseline | Method / locator | Result / boundary |
|---|---|---|
| 最终iOS行为集成，`35a9c0588` | `build.sh test`，`/tmp/nano-feat634-final-ios-test.log`；xcresult `/tmp/nano-feat634-build/Logs/Test/Test-NanoIM-2026.10.22_01-57-51-+0800.xcresult` | 43 XCTest+17 Swift Testing零失败，含附件修复。未声称50a重跑全套；50a仅布局一行，行为测试仍适用 |
| 布局修复集成，`50a56c8ccea9` | `/tmp/nano-feat634-text-wrap-build.log`；acceptance Round3及真实截图 | Simulator BUILD SUCCEEDED；独立GUI390大字号/默认补验pass |
| Release与设备架构，`50a56c8ccea9` | `/tmp/nano-feat634-final-release-archive.log` | ARCHIVE SUCCEEDED，arm64；最终IPA生成 |
| 最终IPA来源/内容 | `/Users/czj/.codex/artifacts/feat-634-ios/manifest.json`；独立计算IPA SHA256、直接读其Info.plist与资源列表 | IPA `NanoIM-0.2.0-634-50a56c8cc-unsigned.ipa`；SHA256 `7f49eaf23008b540e4e263fc18becadbb55811536bbf82458b1b1d93d4ff4103`；bundle win.nanoim.ios，0.2.0(634)，source50a56c8ccea9，含InteractiveRuntime.js。未签名AltStore输入，未安装手机 |
| 本地其他CI适用边界 | M1 progress；已有build/typecheck/docs/runtime证据；Python62和ruff；Web日志、DSH诊断日志定位 | Web947/949且两个未改文件单独65/65；DSH正式90秒超时仍真实存在，临时诊断161秒完成且副本删除；正式timeout未放宽。不称本地全量全绿，远端新headCI待PR |
| 独立产品完成 | `acceptance.md` Round3最终Scenario表与各轮直接GUI/对账 | 全部适用产品场景pass，blocking/major/minor未决0；不证明LLM生成、生产部署或手机安装 |

当前无待补W3本地证据。可以提交PR并由新head远端CI执行下一门禁；本报告不把PR创建/合并或手机更新提前写成完成。归并已审delta与归档可由caller执行，产品代码无需再改。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 原生通用交互回复 / 本地探索与显式继续 | NodeView/Runtime/ChatStore.submitInteraction | VM6条；RuntimeTests.swift:11 | aligned |
| 同上 / 私人状态与历史 | Runtime.load/flush/setReadOnly/activate | RuntimeTests.swift:34/52/68；ChatState只读 | aligned |
| 同上 / 私聊文字携带背景 | ChatStore.swift:392 | SendRecoveryTests.swift:192 | aligned |
| 不确定发送持久恢复 / 回包丢失、改名与重启 | ChatAPI冻结+SendAttemptStore+ChatStore.resolveAttempt | RecoveryTests.swift:16–54 扩展新附件断言及 red/green；原53/76/93/156和真栈汇总继续适用 | aligned：旧附件独立移除、新正文/新附件保留 |
| 同上 / 退出与撤销 | Session清理+ChatStore撤销+ownerDirectory | RecoveryTests.swift:118/142/177 | aligned |

### Uncovered Observable Behavior

无需要另增delta的对外行为遗漏。版本展示/合入后安装属于交付及来源追溯，已在spec与design声明；Query/Mutation/完整目录属于原生通用交互要求的实现。用户调整交付时序已写spec/design并记录Gate2 retained，不涉及运行时技术变更。附件回归已按原delta修实现，无需通过修改契约规避。

Outcome: **aligned**（最终 `50a56c8ccea9`；Round1 implementation-mismatch 已在Round2闭合，Round3布局修复符合既有阅读契约，无需新增delta）。

**Final closure: 0 critical issue(s), 0 warning(s). Ready for PR; new-head remote CI and post-merge phone installation remain their respective next steps.**
