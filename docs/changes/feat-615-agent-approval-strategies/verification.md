# Verification Report: feat-615-agent-approval-strategies

> Validation snapshot: `08b06c57b → ccf74c47cafa2aef4b3a9e73fec05f178578c5a0`

## Round 1

- Reviewer: `/root/static_review_615`，与实现独立；兼任本 unit code review，分别保存结论。
- verification_mode: `full`，同时覆盖当前全部 corrected delta。
- requires_full_verification: `false`；后续修复/证据补齐按关联范围复验，未变部分可保留。
- Verdict: **尚未通过：1 CRITICAL / 2 WARNING / 0 SUGGESTION**。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 实现主链存在；人工授权投影缺失；产品/同条件比较证据尚在执行 |
| Correctness | 配置、CC、Codex 会话/工具隔离已映射；原生预算/取消失效保护缺必要直接验证 |
| Coherence | 独立 DSH plugins、公共 facade 与既有 Node/IM 边界符合设计；人工审批保留未兑现 |

## Completeness

- 单 M1-strategies。未强制简化流程补 tasks/progress 文件。
- 新建与编辑控件、可空配置全链、CC workspace fastpath、Codex 有界审查与 trunk/fork、共有审计及失败分流均有实现。
- 当下 native 测试覆盖 host-owned 工具表、禁止 run_code/宿主 effect、只读调查、full/delta、并发 checkpoint fork 与 invalid verdict 后恢复。
- 明确缺口：D4 的已验证人工审批未进入证据；D6/D7 与 M1 所列 native compaction/预算 admission/持续工具或慢调查期限行为缺直接回归证据。
- 本报告核对时还没有完整真实产品 acceptance 与两层策略比较报告。主代理继续这些工作；此处不能宣称 M1 或 PR ready。

## Correctness

| Requirement / Scenario | 实现位置 | 测试/证据 | 状态 |
|---|---|---|---|
| 逐 Agent 独立选择、持久化、旧字段省略与清空继承 | product-contracts/configuration.ts:14-42；im-server/control.ts:73,416,487,790；db.ts:42；gateway.ts:343；node/configuration.ts:56-70 | approval-configuration.test.ts（API、两个 Agent、失败、migration、fingerprint）；node/configuration.test.ts（reload/DSH/Auto disabled） | covered |
| 下一轮生效，进行中整轮与人工 request 保持关联 | Node runtime revision；dsh-integration/agent-config.ts:42-43,117-148；现有 configuration apply/history 路径；approval.ts:47-62 | personal-assistant/configuration.test.ts；既有 requestId/取消协议沿用；真实 UI/聊天证据待补 | implemented / evidence pending |
| 保存失败与待确认恢复 | control.ts:767-795 的既有 ops 路径；前端共享既有 mutation/draft | API offline 不改 profile；前端相关 create/edit 测试由主代理本地 CI 运行；真实 must-match 待补 | implemented / evidence pending |
| CC 普通工作区 write/edit 无分类 | policy/cc.ts:11-17；cc-workspace.ts:35-42；approval.ts:102-103 | approval-workspace.test.ts：0 judge calls、真实写入、downstream deny、目录外仍审查 | covered |
| CC lexical/realpath/symlink/敏感/自定义规则边界 | cc-workspace.ts:8-42 | 同文件路径矩阵含 .nanoassistant workspace、dangling/outside symlink、受保护别名 | covered |
| Codex 现场检查、不写入/联网/消息/递归审批 | codex.ts:126-150；codex-inspection.ts:7-31 | codex-approval-native.test.ts + codex-approval.test.ts 特殊文件/取消 | covered |
| 用户、Inbox、私稿、工具结果的来源语义 | sources.ts:75-146；codex-context.ts:20-29 | approval-sources.test.ts 的 Codex tool-result/private/live 投影；CC 默认输出未改变 | covered except manual approval |
| 已验证人工审批保留 | codex.ts:61 / sources.ts:80-139 缺 asked/decided 投影 | 临时 seam `/tmp/feat615-manual-approval-projection.json`：hasManualAuthorization=false | WARNING R1-W1 |
| 会话复用、并发 fork、成功 cursor、失败恢复 | codex.ts:45-121 | native full/delta/fork/invalid；lifecycle mock 历史改写/配置变更/overflow | covered，native admission/compaction 待补 |
| 有界总预算、完整 action、overflow/compaction 一次恢复 | codex-context.ts:41-57；codex.ts:67-86,100,111-115,142-146 | pure预算/action测试、mock overflow 成功提交；无 native budget admission/compaction 回归 | WARNING R1-W2 |
| 90 秒共享期限、父取消、重试不续期、迟到 verdict 不执行 | codex.ts:42-43,90-98,108,113,119-125；inspection.ts:13-30 | mock 手动 abort/晚到 allow 两例；无 native 持续工具或慢调查 cancellation/drain 回归 | WARNING R1-W2 |
| 失败不算安全拒绝、high/critical 不放宽、可取得 audit usage | approval.ts:79-97,127-139；audit.ts:4-19；codex.ts:110 | 既有 approval 分类错误分流保留；native invalid action不执行；严格判定 pure测试 | covered |
| 固定 action + 同自然语言等条件策略比较 | evidence/fixed-actions.mjs | 首轮 `/tmp/feat615-fixed-first.jsonl` 存在；完整最终对照与自然语言证据尚未交接 | CRITICAL R1-C1 |

## Coherence

| Design 决定 | 遵守? | 代码/证据 |
|---|---|---|
| D1/D8 可空模式、继承、统一 fingerprint/operation、下一轮冻结 | 是 | Node/IM/product-contracts 的同一 canonical mode；无第二条配置 apply 链 |
| D2 CC fastpath 限普通文件且保留 downstream | 是 | cc-workspace.ts、approval.ts:102-103、native 0 judge test |
| D3 独立受限审查 Agent 与固定政策 | 是 | codex.ts scoped tools/restrict/guard/never；native 恶意同名宿主工具未执行 |
| D4 Guardian evidence/source/manual approval | 部分 | 普通工具、私稿与来源保留；人工 allowed-once 缺投影，R1-W1 |
| D5 trunk/checkpoint/fork、仅成功提交 | 是 | codex.ts:52-57,99-121；native 并发与失败测试 |
| D6 改写/配置/预算/compaction 重建 | 实现存在，验证不足 | prefix/fingerprint 与 retry code；native admission/compaction 待补，R1-W2 |
| D7 共享 deadline/取消/await dispose | 实现存在，验证不足 | 单 deadline + cancel listener + finally discard；原生 async drain 待补，R1-W2 |
| D9 公共路由、risk/auth/audit、失败与拒绝区分 | 是 | approval.ts + audit.ts；没有 runtime fork/private import 或 PA/IM 的 DSH import |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 行为卡策略与解释，桌面/390、不溢出 | M1 reviewer must-match | ApprovalModeField；详情行为卡与新建行为卡 | 当前只有设计阶段 prototype-review/design-review；实现产品对照待 reviewer | pending R1-C1 |
| 保存、dirty 草稿、失败/成功与下一轮提示 | M1 reviewer must-match | 共用选择与原有 save mutation；description/timing 文案 | API/前端自动测试保护不能替代真实 must-match 对照 | pending R1-C1 |
| 身份/rail/其他配置是背景示意 | 明确仅 incremental | 现有配置页局部插入控件 | 无需把原型背景当删减要求 | aligned |

## Issues

### CRITICAL

- **R1-C1 — M1 外部退出证据待完成。** `design.md` 的 M1 与 spec 最后一个 Requirement 要求固定 action 和同自然语言实跑对照、初始状态/结果/耗时/usage 与首轮失败，以及真实配置页 must-match 对照。本报告冻结时只有首次 fixed-action 原始记录，没有最终比较报告或产品 reviewer acceptance 可核对。主代理应完成并交接实际报告路径/版本；只补证据时无需重跑已通过静态范围。首轮 Codex 对两个临时文件的 rm 被评 medium/low 并 allow 必须保留；它不证明“未授权大范围破坏已被拒绝”，也不能因上游 low/medium 策略而伪造应拒样本。

### WARNING

- **R1-W1 — Codex 缺真实人工批准证据。** `codex.ts:61` 使用的 `sources.ts:80-139` 未把 log-only `approval/asked` / `approval/decided` 投影进 Codex。design D4 明确保留已验证人工审批。按 approval id 配对、连接有效 callId 与精确动作，只投影真实 allowed-once，保持 scope，不以历史授权替代新批准；增加最窄 source seam 回归。直接证据与定位见 `code-review.md`。
- **R1-W2 — 原生恢复/取消退出标准尚未获得直接回归保护。** `codex.ts:67-115,142-150` 与 D6/D7/M1 涉及 DSH 的 request admission、compaction event、原生 cancellation 和 async disposal，现有 lifecycle mock 不调用 setup、不执行 request hook，也不经过真实原生 loop。需在锁定 DSH seam 证明实际预算重建或 compaction 后丢弃 pending、共享 deadline 在连续只读工具/慢调查中终止且 await dispose、父取消不执行晚到 verdict；可合并为少量连贯原生测试，不要求重复 pure/mocked 风险或真实模型测试。主代理已确认当前未另存这些证据，正在补齐。

### SUGGESTION

无。

## Round 2 — targeted closure

- Validated product head: `8aa3c814946cc0d8296ff90d6a269b8d68f5ccd8`。
- Fix delta: `ccf74c47c..8aa3c8149`；保留 Round 1 已覆盖且未变的配置、CC、工具隔离、fork 与来源结论。
- Verdict: **1 CRITICAL / 1 WARNING 尚未关闭**；R1-W1 已关闭，无新增问题。
- requires_full_verification: `false`。

### Closure disposition

| Issue | Disposition | 直接证据 |
|---|---|---|
| R1-C1 产品与两层真实策略比较报告 | still_open | 主代理与独立产品 reviewer 继续执行，尚未交接完整报告 |
| R1-W1 人工批准未投影 | closed | Codex opt-in asked/decided 配对及有效 exact action/PTC 关联；批准明确限一次，不复活移出surface的动作；7 source tests passed，`/tmp/feat615-static-source-closure.log`；原 seam 现 hasManualAuthorization=true |
| R1-W2 原生恢复/取消证据 | partially_closed | 锁定 DSH native fixture 新增 provider overflow rebuild 和父取消 late grant suppression，`/tmp/feat615-native-recovery.log` 1 test passed；共享deadline只有mock，未直接执行原生慢调查/持续工具的到期收尾 |

原生 compaction 仍未被本轮独立触发。其识别/rebuild代码与预算 admission 静态核对、pure budget 与 mock recovery可复用；不得把 provider overflow fixture 记成 compaction 测试。剩余 W2 只需补 D7/M1 明列的原生调查过程中 shared deadline/收尾证据，不重复全部单测或真实模型任务。

## Round 3 — evidence closure and usage patch

- Validated product head: `ba88c18bcb9179d84b6765fcef8712f17b6db1bf`；delta `8aa3c8149..ba88c18bc`。
- Verdict: **1 CRITICAL / 0 WARNING 尚未关闭**。R1-W2 已关闭；R1-C1 仍待综合产品与真实比较报告。
- requires_full_verification: `false`。
- R1-W2 closed：真实锁定 DSH 原生调查工作流先执行 guardian_read，随后模型等待信号，90秒共享deadline触发classifier_unavailable/no_verdict；没有晚到allow或原动作effect，五个reviewer全部dispose。最终测试 `/tmp/feat615-native-final.log` **1 file / 1 test passed，92.59s**。与原有mock的一次deadline/重试不续期、native父取消/overflow证据组合，覆盖D7/M1所列整体时限与收尾风险。
- 新增并发错序观察：parallel-a延迟80ms allow，parallel-b即刻deny；分别断言decision/rationale及不同fork sessionId，结果正确。
- Usage patch：按public API将原生新增事件限于turn/start至turn/end；native audit验证uncachedInputTokens10/outputTokens5。源码和API证据见code-review Round3。
- 首次native deadline测试末尾usage字段误写而失败的日志保留于`/tmp/feat615-native-deadline.log`；最终schema字段修正后通过。原生compaction仍未独立触发，预算 admission/compaction 的静态与pure/mock证据边界保持，不虚构直接场景。

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway MODIFIED：默认/来源/超窗适用 CC/DSH；旧子 Agent、规则切换、失败路径 | classifier.ts 提取原逻辑；approval.ts保留路由/never；sources默认选项不变 | approval现有测试 + source测试 + node继承测试 | aligned |
| Gateway MODIFIED：逐 Agent 明确选择/清空/继承与下一轮 | product-contracts + Node runtime + existing apply/config scopes | API/Node/PA configuration tests | aligned |
| Gateway ADDED：CC 普通文件快速放行及路径保护 | cc.ts + cc-workspace.ts + downstream facade | pure/native workspace tests | aligned |
| Gateway ADDED：Codex 本地只读、精确 action、来源、连续并发、预算与失败审计 | codex/context/inspection/sources/audit；8aa3c8149 补 verified manual action | pure/native/mock、7 source tests、90秒原生deadline/drain及usage测试 | aligned |
| IM ADDED：选择、继承、省略保留、失败与下一轮 | shared UI + control/db/gateway + Node mode | API/Node tests；产品验收待补 | aligned at contract; evidence pending |

### Uncovered Observable Behavior

没有发现 unit diff 中需要另加 delta 的独立外部行为。Codex low/medium 在缺授权时仍可能 allow 是已选择固定上游策略的行为，真实报告必须明确展示，不把它等同于“全部未授权动作拒绝”。人工授权已在 8aa3c8149 修实现，未静默删改设计。

Outcome: **aligned**（ba88c18bc corrected-delta closure）；两个 corrected delta 的文本与最终已核对实现相符。完整 M1 仍受 C1 产品/对照证据门禁约束，aligned 不等于产品验收通过。

## Validation Evidence

- 独立窄验证命令与完整结果见 `code-review.md`：冻结 head 下 **7 files / 26 tests passed**，`/tmp/feat615-static-review-tests.log`。
- 审查未修改源码、测试、配置或设计；未启动真实服务。复用锁定 DSH public 源码作为原生事件/API语义证据。
- 不重复主代理全量 CI、真实模型或独立产品 reviewer；这些证据只在交接后核对其被测版本与结论。
