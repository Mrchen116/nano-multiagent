# feat-676 — 产品验收报告

> 对齐：`../spec.md` S01–S20，`../design.md` 前端原型对齐契约。
> 独立 reviewer；只操作隔离固定日常模板与本报告，不修改实现。
> Round 1：base `6b4213c20` → `b203c5823`；Round 2 定向复验候选 `5a123bae760d429c84bc2a3f72814009a69836f0`。

## Verdict

**pass-with-issues（Round 3，定向复验）**。原 Round 1/2 对记忆内容、Work 摘要和刷新重开的结论保留，但未实际覆盖 Dreaming 原生 viewer 的完整明细与重启冷读取；原先“S01–S20 全部通过”不能证明该入口可用。用户随后发现的 `trajectory_read_failed: subagent descriptor is corrupt` 是原验收缺口。候选 `e207a51b6e8313083cff05ccebfcca7196b8653d` 已通过两条旧轨迹、一条新真实执行及隔离 Gateway 重启后的原生 UI 复验：0 blocking、0 major；保留 1 项不阻塞回溯的 minor 体验观察（完成边界需一次重新读取）。未受影响的模型内容理解与其他场景按 Round 2 具体证据继承；本报告不宣称重新执行全量矩阵。

## Round 1 — fail

验收环境为 `/private/tmp/nano-feat676-daily`，Web/IM `127.0.0.1:65225`，node `wt-nano-feat676-daily-76245`；专用 nano 测试账号，P/E/Q 与 PA 固定模板。PA 使用 astra，专家使用 sol；所有消息与资料均为合成验收内容，无生产数据、外部业务或群通知。主要原始证据在 `/tmp/nano-feat676-review/`。本轮临时增量：手工保存记忆页、主体旧备份、同名协作者、在途报告、P 短周期自动整理、Q 文件模式切换，均限该隔离实例。

### 用户旅程体验

配置沿用原有纵向表单与保存区。1280 与 390 宽度下，Dreaming 文案就地说明关闭仍可记住、更正、读取；没有记忆总开关或 skill-creator 选择项，legacy 页面没有新增模式说明卡。窄屏 409 保存冲突保留未提交选择；已生效与未保存状态可区分。离线时 Save 禁用，属于既有只读规则，不能把它当作 pending 实测。

真实聊天能交付有条件的记忆，而非只显示“已保存”：PA 在新聊天仍区分白鹭日常文字与年度 PDF 例外；轻记撤回的条数限制不再使用；专家区分同名甲乙，在同一个原执行者上应用更正并保留实际失败。Work 的关联 Dreaming 执行可以展开并在刷新后重开，显示 19/19、11/11 或 0/5 等真实范围及未闭合尾部，失败并未伪装成完成。整体有两项阻塞：状态查询误导用户认为没有积压，跨窗自动运行因长材料无法完整读取而失败。

### 问题清单

| # | 严重度 | 现象与决定性证据 | 处置 |
|---|---|---|---|
| A1 | major | E 的 676-N 回复 `2036e78429514bd2a6c02a46f8937ea8` 把 `sourcesPending=false` 报成无待处理来源；随后 N2 真正选中 27 单元。`expert-status-work.txt`、`c_bwf4co7x.json`。 | 候选 5a123 修复；Round 2 N3真实复验关闭。 |
| A2 | major | P 两次真实 new_context 期间自动运行 `47adde06-140a-428e-88d8-6e75a9b30ef6` 于 02:49:13 启动、02:50:40 失败，0/5、0 页、不推进。原生输入单行过长，read/grep 截断，模型拒绝谎报读完；`p-auto-failure-work.txt`、`p-auto-failure.jpg`。 | 候选 5a123 无损分行/长文本分片；Round 2同一积压手动恢复及后续自动完成关闭。 |

### Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `../prototype.html`；design 前端契约 | 本次能力仅 Dreaming 可选；无记忆/技能创建开关；legacy 隐藏 | `ui1280-create.jpg`、`ui390-saved.jpg`、`ui1280-legacy.jpg`、`ui390-legacy.jpg` | 1280/390，创建/配置、开/关/legacy | match |
| 同上 | 保存与生效分离，失败保留选择 | `ui390-save-conflict.jpg`、`ui390-saved.jpg` | 390，409、保存成功 | Round 1失败及生效match；Round 2补`ui390-confirmation-pending.jpg`与applied闭环，完整match |
| 同上 | 工作记录明确范围与部分成功 | `work-completed390.jpg`、`work-reopened390.jpg`、`p-auto-failure.jpg` | 390/1280，完成/刷新重开/失败 | match，信息可辨；A1 状态解释另行阻塞 |

### 验收标准覆盖

以下每行期望来源均为 `../spec.md` 对应编号。确定性故障注入用于无法稳定自然触发的崩溃、Git 失败、调度和来源边界；reviewer 已核对相应测试断言，复用执行日志，不以测试替代真实模型理解或 UI 体验。

| Scenario | 验证方式与决定性证据 | Round 1 结果 |
|---|---|---|
| S01 PA 跨聊天偏好 | H/H2 导入白鹭后，新聊天 K 回复 `035610f0c1db43a0a3cae22c92db9ecc`：日常文字、年度 PDF、负责人未确认；不恢复轻记条数限制。`c_xozrh0fq.json`。 | pass |
| S02 专家不同合作者 | E1 明确同名甲/乙不同，分别建页；I2 只修改乙为结论+回执，甲仍三条。原子执行者 `1659baec-9438-4e95-b606-25b9759a1e53` 同一工作报告改为26行。`daily-engineering-memory.json`、`child-correction-work.txt`、`child-correction.jpg`。 | pass |
| S03 完整依据及角色入口 | PA/专家实际完整阅读详细页并回答；E 保留普通发布零失败、紧急回滚例外、禁止自动跨区域迁移及区域未知。`c_bwf4co7x.json`；入口与详细页快照。 | pass |
| S04 空库/不足 | E1 未给定经历前明确未找到可靠个人偏好；Q L0 对人工标签说明 entry_basis_stale，未假称已恢复有效。K 不从旧备份推定当前负责人。 | pass |
| S05 即时保存 | A/B 实际保存更正；F 在 Dreaming 关闭时仍保存演示周四→周五与日期/时间未知。后续 K 消费。`c_2c448f93a14e.json`。 | pass |
| S06 更正及在途工作 | I2 同轮修正文档/入口，给原 child 纠正，读回同一报告126→26行；保留9过1败、原始回执缺失，不另派。回复 `6f21580f8208434f8542e9e3d3a892ad`。 | pass |
| S07 人工未提交保存 | 直接编辑轻记详细页而不提交；F 使用普通最多两点、事故不受限制的新内容并修正入口。`qingji-before-human-edit.md`及F回执。 | pass |
| S08 变化与成果 | F 记录计划变化、未知项；E 工程报告保留失败条件与来源并更新原事项，未把每次读操作生成案例。 | pass |
| S09 自述/反例/现实 | I2 明确助手全通过自述不能覆盖用户9过1败，报告完成不等于验收或发布授权；K 历史负责人未知不冒充现实状态。 | pass |
| S10 跨窗持续整理 | M 主任务两次 new_context 并完成，后台在主任务期间启动但0/5失败；未截断主任务。`c_ucpy27z5.json`、A2。 | fail |
| S11 去重与修订 | H2 逐项比对不重复追加；native `memory-sources.test.ts` 复用来源修订、继承前缀、消息配对与分页测试（完整CI836通过）。真实修订I2正确消费。 | pass |
| S12 已有观察和结果 | E 的真实子报告读回、失败回执消费正确；PA D/G 完成19/19、11/11，均列未闭合尾部且未发群；自动P长源未完成，不能称全部理解。 | fail |
| S13 冲突 | `memory-documents.test.ts` 保存human第三版本后旧beforeHash被拒且字节保持；`dreaming-recovery.test.ts` generation/third-version旧计划退休后处理原积压。完整CI通过；真实F/I2更正消费。 | pass |
| S14 不完整与后来材料 | E N2 如实报告0/27及额外1范围未知单元数；原生4类未完整结束测试（`/tmp/feat676-incomplete-runtime2.log`，9通过）断言failed/no cursor；真实A2保留待处理。 | pass |
| S15 部分保存重启 | `dreaming-recovery.test.ts` before-first/after-body/after-entry故障，恢复复用冻结计划，无第二次模型/重复写入，完成才推进；`memory-documents`丢失回执后恢复且不覆盖后续人工版本。`/tmp/feat676-full-apply-recovery.log`及完整CI。 | pass |
| S16 保存和Git分离 | `memory-documents.test.ts` 删除临时Git后保存成功、versionRecorded=false且正文可读；写后故障与恢复断言；真实Work区分0页与历史14条版本回执。 | pass |
| S17 关闭/手动/技能/UI | F关闭仍保存，G关闭仍手动11/11；Q真实skill-creator→skill_manage→重发现/load。`skill-work.txt`、`skill-created.jpg`。调度、暂停、无增量与旧自动Skill停止复用native tests；UI pending证据仍缺。 | inconclusive |
| S18 状态/普通完成 | D/G Work真实范围、刷新重开成立，无自动聊天；E N把资格状态误作无积压，A1。 | fail |
| S19 迁移/模式 | H/H2自然语言导入主体备份且保留，限定不查旧聊天；隔离迁移测试及iOS构建复用。Q L1确认LEGACY-ONLY-676，文档原字节保留；切回document待复验。 | inconclusive |
| S20 停止使用 | G登记排除并移除入口/正文，关闭Dreaming手动11/11后不复活；K跨聊天不采用，明确未删原聊天/Git。来源撤回/重启失效确定性断言通过。 | pass |

## Round 2 — pass

继承 Round 1 已通过旅程的具体结论；修复涉及输入可读性及状态范围，复验 A1/A2、S10/S12/S18，并补 S17 pending 和 S19 切回。未重跑无关平台矩阵。当前候选构建 `5a123`，gateway 59452，runtime 59455，02:56:43 启动。

### 已关闭项

- A1 / S18：N3 回复 `1b3db7cb1ca541249861c5c41588b23d`（同原始问法）明确 `backlog=pending`，下一有界批次27单元而非全部总量，`processedThrough=-1 / eligibleThrough=257 / observedThrough=513`，另列预算阻塞；明确 `sourcesPending=false` 不代表无积压。14条历史保存/版本回执与本次查询零新增严格区分。
- S19：Q 依次实际消费 DOCUMENT-ONLY-676 → LEGACY-ONLY-676 → DOCUMENT-ONLY-676；L2 回复 `378e7a1960294875944fadb3fd9552d8` 重新读取当前文档，诚实保留人工标签未checkpoint的 `entry_basis_stale`，没有查其他模式目录。
- M2 再次真实跨窗、读回stage3并明确所有产品动作尚未执行；状态如实为cancelled0/26、下一批40。此前失败和重启取消进入03:26:36退避，未篡改游标或退避状态。后续以显式M3手动恢复既有积压，成功之后才独立验证自动运行，不混淆证据。

### 自动整理修复复验

M3 显式手动运行 `b9851fd9-d1dd-4260-81f6-ed666140f9da` 完成40/40，到seq281，3/3页均保存且记录版本；真实回复 `09e0095c21964f11aa29a215df50a81d` 严格区分还有10单元的下一批与全量总数。独立读取 `p-manual-memory.json`：长文本中的三个待验证动作及低频范围限制均完整提炼，记录明确M2在本批截止处尚未获最终交付证据，未抄用后来的成功。

其后**自动**运行 `fdc890cb-46e2-47b5-b0ab-9dd32821c3bc` 于03:03:55启动，此时主任务至03:04:33才结束；03:05:46完成10/10，保存3/3页。`p-auto-success-work.txt`、`p-auto-success.jpg`显示真实Work回执；`p-auto-memory.json`显示同一原页补入M2完整读回/投递，但仍区分缺少原始status回执和M3只受理未证实完成，不把范围上界当作所有事件已提供。来源根会话始终 `3ac576f8-526b-4807-857d-581aaa84bf7c`，覆盖前述多个真实窗口；主任务未中断。普通auto完成后该私聊最后一条仍为显式M3要求的回复，群消息为0，未新增永久同事。A2关闭，S10/S12通过；A1及S18也以N3关闭。

### 等待态证据边界

390宽度真实保存已观察到 Saving…、Save/Discard禁用，随后恢复No changes；此前409保留草稿和离线禁用也已有截图。为捕获“已保存但节点未确认”，尝试仅对本隔离gateway59452短暂SIGSTOP，并安排45/50秒自动SIGCONT保护。两次UI提交对应的持久operation均在约0.5–0.6秒committed；随后同一工具调用中SIGSTOP后立即ps仍为Ss+，另次shell SIGSTOP亦如此，无法证明节点实际暂停，因此**不能把这些截图算pending，也不能据此判定UI缺陷**。已显式SIGCONT、丢弃最后一次未提交选择并重置viewport。

上述信号方案不构成等待态证据。随后改用隔离透明WebSocket代理，只暂缓 IM→本node 的 `agent.config.apply` / `agent.config.operation.status` 原帧，心跳及其他流量继续真实转发；不改UI、不伪造响应。Q的真实保存形成待确认：390页面显示 **Save awaiting confirmation**、Last confirmed 03:15:19、Refreshing · Read-only，底部 **Confirming save · Draft retained**；off选择保留且不谎称已生效。证据 `ui390-confirmation-pending.jpg/.txt`。原始operation `d67ed387003b486ea12a54f4e739079f` 实际处于pending，放行原帧后，页面自动移除等待提示，恢复可编辑，Profile Version变为v4（03:17:24），Dreaming保持off，No changes且Save禁用。`ui390-confirmation-applied.jpg/.txt`证明生效闭环。代理由caller清理；reviewer恢复viewport，不遗留未提交配置。`ui390-saving.jpg`仅证明Saving，`ui390-pending-real.jpg/.txt`文件名不代表其内容为pending，实际为已生效No changes。

### Round 2覆盖继承

| Scenario | 最终结果 | 依据 |
|---|---|---|
| S01–S09 | pass | 逐项继承Round1未失效真实旅程；修复未改变即时知识与角色消费。 |
| S10 | pass | 同根跨窗后自动fdc890cb在主任务未结束时启动并10/10完成。 |
| S11 | pass | 继承来源去重机制；新自动更新同一原页，不追加同义记录。 |
| S12 | pass | 手动40/40与自动10/10的实际文件保留观察/回执/未知边界。 |
| S13–S16 | pass | 继承已核对故障注入断言；真实长源失败恢复补充S14。 |
| S17 | pass | 关闭/手动/技能语义通过；真实pending保留草稿，放行原帧后v4/off生效。 |
| S18 | pass | N3明确backlog；自动Work完成且无额外聊天。 |
| S19 | pass | Q document→legacy→document实际消费闭环，导入/备份继承Round1。 |
| S20 | pass | 继承撤回后手动与跨聊天不复活。 |

## 上层文档同步

- [x] `SPEC.md`：无需改变顶点依赖规则。
- [x] `docs/specs/gateway/`、`docs/specs/im/`：需要归并本unit四份delta；由orchestrator收尾，不由reviewer改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] 文档规范：无需更新。

iOS 按 design 指定只验共享语义/编译，复用 `/tmp/feat676-ios-test.log`、`/tmp/feat676-ios-archive.log`；本报告不宣称 iOS 视觉验收。


## Round 3 — 原生 Dreaming 轨迹定向复验（pass-with-issues）

- `validated_at` / 实现候选：`e207a51b6e8313083cff05ccebfcca7196b8653d`；`executed_base`：原 PR #428 head `c1eea6beb` 的既有数据；原 PR 未合并。复验开始 HEAD 为候选，冷读时 HEAD 为仅更新 code-review/verification 的 `49be9e80e`，未冒充新的实现运行。
- 时间：2026-10-29 北京时间约 10:18–10:32；平台：Web，独立浏览器 tab，实际 viewport 1280×720。本次没有界面实现改动，保留 Round 1/2 390 宽度及 iOS 共享语义证据，不声称本轮另验 iOS。
- 环境：`/private/tmp/nano-feat676-daily`，IM `http://127.0.0.1:65225`，node `wt-nano-feat676-daily-76245`，专用 nano 测试身份。核对 `.e2e-daily.json` 的 P/E/Q sol、PA astra 与固定模型/审核阵容。PA 自动 Dreaming 关闭、P 开启且间隔 1000ms、E 开启、Q 关闭；本轮不改配置。
- 证据目录：`/tmp/feat676-trajectory-review/`。原故障画面 `before.png` 与旧历史备份 `pre-repair/` 均保留。reviewer 不改实现或历史，只在既有 Q 合成测试私聊增加一条输入、等待真实整理，并进行一次授权隔离 Gateway 重启。

### 真实旅程与决定性结果

可复查的隔离入口：

- [旧自动10/10](http://127.0.0.1:65225/settings/agents/daily-product?view=work&work_view=trajectory&execution=dreaming-fdc890cb-46e2-47b5-b0ab-9dd32821c3bc)
- [旧手动40/40](http://127.0.0.1:65225/settings/agents/daily-product?view=work&work_view=trajectory&execution=dreaming-b9851fd9-d1dd-4260-81f6-ed666140f9da)
- [本轮新手动21/21](http://127.0.0.1:65225/settings/agents/daily-quality?view=work&work_view=trajectory&execution=dreaming-d8ce8998-9154-4d7e-ab1e-572a315d5da9)

| 来源/必验结果 | 实际操作与观察 | 结果 |
|---|---|---|
| S18；current `agent-work.md` 完整原生明细 | 打开 P 的既有自动 `dreaming-fdc890cb-46e2-47b5-b0ab-9dd32821c3bc`，逐项展开初始系统提示、read、edit、finish 和宿主回执。独立受限 prompt、参数/结果/Schema 可读；finish reviewed=10，宿主 10/10、保存3/3。保留一次绝对路径 finish error 及后续成功重试，未把历史错误隐藏。`reviewer-auto-{prompt,read,edit,finish}.txt`、`reviewer-auto-receipt.png`。 | pass |
| 同上，较长旧历史分页 | 打开 P 的既有手动 `dreaming-b9851fd9-d1dd-4260-81f6-ed666140f9da`，点击“加载更早的历史”后系统提示与首批输入可达，再展开 read/edit/finish/宿主回执。finish reviewed=40，宿主 40/40、保存3/3，并明确另有1个源范围待处理。`reviewer-manual-{prompt,read,edit,finish}.txt`、`reviewer-manual-receipt.png`。 | pass |
| S17/S18，新真实手动整理 | 从 Q 的 Open chat 进入既有 `c_s5tkgcqp`，发送合成经验676-T：刷新保留状态不证明服务重启持久化，分别记录证据；明确仅手动整理一次、不启用自动整理。真实输入 `11fabcf00f9d425085e286a76b813c85`；Q 实际调用 `memory_maintenance run`，没有用伪造宿主结果替代模型执行。 | pass |
| 新执行完整原生链路 | UI 选择新 `dreaming-d8ce8998-9154-4d7e-ab1e-572a315d5da9`，实际展开 prompt/read/edit/finish/宿主回执。10:24:06–10:27:58 的维护运行核对21/21、保存3/3；有界批次包含 Q 原有合格历史，不把它说成只处理新消息。新增 knowledge/receipt-aware-report.md、projects/synthetic-checklist-676.md，并更新入口；明确合成性质和刷新/重启证据区别。finish prepared 与宿主实际保存分别可辨，回执保留另有1个源范围待处理。`reviewer-new-*.txt/.png`。 | pass |
| current 维护效果不佳后回溯；重启冷读 | 等 Q 主执行完成（10:22:13–10:29:12，真实回复已投递）后，guard 通过，CLI stop/start 仅重启隔离 Gateway。旧92831/DSH92837 → 新19680/DSH19686，10:30:16启动，ready/connected=true，`.gateway.pid` 已维护。重新导航三条旧/新原生轨迹，均已连接、可展开宿主回执，旧手动历史分页仍正常；无 descriptor corrupt。`reviewer-cold-{auto,manual,new}.txt/.png`、`reviewer-restart-check.txt`。 | pass |
| 既有历史保留与身份不扩散 | 复用 `history-prefix-check.txt` 的8条日志原记录不变、仅追加1条隐藏one-shot身份结论；reviewer 独立比较重启前后及冷读后压缩日志 SHA-256，8条旧日志和完整 Gateway 配置均完全一致，没有再次追加或重写。模型目录隔离复用原生回归 `pnpm exec vitest run packages/dsh-integration/tests/dreaming-runtime.test.ts --maxWorkers=1`，`/tmp/feat676-trajectory-green.log` 2/2通过；其 warm/cold 后 descendants=[] 与实际请求无descriptor/工具不扩张断言由实现与code-review证据支撑，不宣称本轮UI直接观察模型目录。 | pass |

### 完整体验与非阻塞观察

原生时间线与右侧检查器沿用现有布局：左侧选择真实事件，右侧可读 prompt、调用参数、结果与 Schema；宿主回执与助手“prepared，不等于应用”的声明分别呈现，用户能判断模型处理与实际保存的区别。既有错误、剩余材料没有被成功摘要掩盖。此轮主要可交付目标——从 Work 进入真实完整明细、重新启动后仍能回溯——成立。

| # | Severity / Regression Relation | 期望、实际与证据 | Recommended Action / Rationale |
|---|---|---|---|
| T1 | minor / unclear | 新执行实时从运行转完成时，已有完成回执仍可见，但顶部出现 `generation_changed: generation_changed`、“历史读取中断”，需要点击一次“重新读取”。点击后即恢复已连接，原数据完整，随后冷读取也正常。`reviewer-new-receipt.png` 保留中断现场，`reviewer-new-reread.png/.txt` 证明恢复。 | Side finding；建议后续改善结束边界提示或恢复体验。current 契约允许更新中断如实呈现，当前有明确恢复按钮且不重执行任务；没有阻断明细回溯或造成数据缺失，因此不扩大本轮修复范围、不据此推断根因。 |

### 覆盖继承与环境交还

S18 的原生 viewer 缺口本轮补齐；S17 关闭自动后仍可手动整理以 Q 新执行补证。S01–S16、S19–S20 的模型理解、角色边界、输入保真、故障恢复、迁移与遗忘结论继续引用 Round 1/2 的具体证据，修复没有业务提示或内容语义改动，不重复大范围真实运行。最高必要动作 `pass`，无需为本修复再复验；T1 为非阻塞 Side finding，无外部 issue 创建。

服务按用户要求保留运行与历史，不执行 e2e-down；IM 与数据库未重启，Q 自动开关未变。独立浏览器 tab 为临时验收页，未改主 tab。本轮只提交 acceptance.md，不 push；其他并行报告与实现提交由 caller 管理。上层 current spec 和设计无需因本次身份恢复修复改写。
