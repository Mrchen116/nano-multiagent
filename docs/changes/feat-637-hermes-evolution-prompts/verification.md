# Verification Report: feat-637

> Validation snapshot: `5462b7217421a2c27871c1c5951c1e48644e54ba → d617906aed41fa14a34f4b3f1b5e49f179ed4129`

## Round R1 / full

- branch: `unit/feat-637`
- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-637`
- validated_at: `d617906aed41fa14a34f4b3f1b5e49f179ed4129`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- verification_mode: full
- requires_full_verification: false（本轮已经 full；修复后按受影响范围复验）
- verdict: FAIL，0 CRITICAL / 2 WARNING / 0 SUGGESTION。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 全部实现面可定位；关键拒绝、并发及在途关闭的回归证据不完整 |
| Correctness | 21 个场景均有实现或提示词映射；终态存在一项独立复现偏离，部分场景缺行为保护 |
| Coherence | DSH 公开接入、分包职责、原文件读取基线、联合用途接线总体遵守；读取结算失败分支偏离 design |

本报告仅执行独立 code review 与 verifier 职责，不代替产品 reviewer。作者 progress.md 的真实模型与截图为可追溯作者证据，不提升为独立产品验收。当前未取得全部21场景的独立产品报告，因此不宣称 M1 的 reviewer 退出标准完成。Gate 2 由另行派发的设计 reviewer 判断。

## Completeness

- M1 实现范围已落地：四份 review assets、前台工具说明、运行时调度、读取登记、锁内写入基线、F4 证据与目标约束、持久 review/trajectory 类型、两个 UI 用途消费者均在受审 diff 内。
- 简化流程不强制 tasks.md；现有 progress.md 可作交接，不能代替行为证据。
- 已有回归保护覆盖 Memory 快照／fork／压缩、单项失败不结算、实际写入与来源、独立单项维护、Global 不触发 F4、单会话不足、两会话 F4 正向、联合单 fork／冷恢复、读取分页和写后基线、Memory 未完成但 Skill 已写入。关键新增保护缺口见 R1-W2。
- 产品内容质量：assets 对原需求各条均有直接规则；实际模型是否遵守需产品 reviewer 的真实输入及产物，不能以字符串或预设模型合法 patch 替代。
- Prototype / Reference：本次不新增布局；design 明确仅用途映射，无整页原型或 iOS 专项验收要求。

## Correctness

| Requirement / Scenario（spec.md） | 实现位置 | 测试／证据 | 状态 |
|---|---|---|---|
| 画像和项目事实各归其位；没有长期价值的信息不沉淀（77、82） | `assets/knowledge/memory.txt:3`、`combined.txt:1`、`features/memory-curation.ts:17` | 联合双写 fixture；progress 真实模型无增量和偏好落盘 | 规则及写入链已覆盖；完整产品质量待独立报告 |
| 重复表达不产生重复记忆；明确纠正替代旧事实（89、94） | `memory.txt:14`、`knowledge/runtime.ts:136`、`files.ts:50` | Memory 原位 replace/remove；progress 普通会话未重复追加 | 实现映射成立；design:150 的普通／Global 连续纠正矩阵尚无完整证据 |
| 有效经验改善已有技能；未成功尝试不成为可靠流程（102、108） | `skills.txt:1`、`features/skill-creation.ts:10` | progress csv-audit 原位修正；失败方法由指令限制 | 规则及持久修改已覆盖；失败方法质量待产品验收 |
| 新建现场不被泛化为每轮惯例；Agent 的选择不冒充用户要求（115、121） | `skills.txt:3`、`memory.txt:26`、`combined.txt:12`、`skill-batch.txt:12` | 无相应真实模型反例行为证据 | 指令完整；产品结果待独立验收 |
| 同一纠正不被双份固化；关闭自进化仍有效（128、133） | assets 的单一归属规则；`runtime.ts:128`、`:341` | 独立单项关闭和保留资产已有覆盖；combined 在途关闭缺覆盖 | R1-W2 |
| 两项同时满足条件（142） | `runtime.ts:241`、`:279`；`trajectory-runs.ts:14`；两处 runTitle | `knowledge-review.test.ts:6` 联合单 fork、真实 fact、重启轨迹 | covered |
| 仅一项满足条件（149） | `runtime.ts:245`、`:251`、`:292` | `knowledge.test.ts:60` 独立 Agent 单项；未覆盖同一 session 两项开关／不同 interval 的独立结算 | R1-W2 |
| 联合复盘失败或中途关闭能力（154） | `runtime.ts:128`、`:290`、`:341` | 未读全时部分成功及下次重试已覆盖；原生中止分支复现错误 | R1-W1、R1-W2 |
| 主 Agent 修正已有技能；部分修改成功时报告实际状态（162、168） | `features/skill-creation.ts:10`、`files.ts:72` | 已有单操作写入测试；各次 fact 只在落盘成功后发布 | 实现一致；模型报告内容由产品 reviewer 核验 |
| Global 模式不触发 F4（178） | `runtime.ts:220`、`:243`、`:134` | `knowledge.test.ts` Global 达20次仍无F4 | covered |
| 有充分证据时修补目标技能（184） | `runtime.ts:301`、`:59`；`files.ts:79` | `knowledge-review.test.ts:39` 两个完成会话，先拒绝未读 patch 再读原文件 patch | 正向 covered；越界矩阵缺保护，见 R1-W2 |
| 单个会话重复使用不等于跨会话证据（190） | `runtime.ts:303`、`:265` | 同一测试先20次单会话不修改，再第二会话成功 | covered |
| 无效或已处理证据不再次支持修改（195） | `runtime.ts:307`、`:313`、`:318`；`files.ts:208` | 测试仅断言已处理ID落盘，没有再触发、未结束／待执行／错归属／缺记录输入 | R1-W2 |
| 手工技能不被 F4 自动修改（199） | `files.ts:185`、`:81` | `knowledge.test.ts:46` 手工 candidate 拒绝；接受后来源再检查未直接验证 | 部分 covered；R1-W2 |
| 同一技能的复盘不重叠执行（204） | `runtime.ts:226`、`:286` | 冻结计数后新增使用保留已有低层测试；没有两个真实 session 同时越线的测试 | R1-W2 |

## Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| 复用固定 Hermes 文本，准确适配单操作协议、无配额和临时资源规则 | 是 | 四份 assets 与 prompt-map 对账；未新增 operations、delete 或回滚协议 |
| 继承父请求前缀，实际执行白名单与父权限相交 | 是 | `runtime.ts:49-70`、`:270-282`；既有 llm-attribution wire-prefix 测试 |
| Memory 读取当前准确路径，不以父快照或注入内容代替 | 是 | `runtime.ts:232`、`:276`；`review-files.ts:29-65` |
| 只有正常结束且 Memory 读取未完成才转换为未完成错误 | 否 | `runtime.ts:297`；原生 aborted 被独立复现成 knowledge error |
| 后台已有 Skill 完整读取，锁内比对，成功写入推进基线 | 是 | `review-files.ts:48-77`、`files.ts:89-112`；分页／变化／连续 patch／支持文件覆盖 |
| F4 独立模式、两完成会话、自有事件、归属、只 patch 目标 | 实现遵守；关键拒绝与并发证据不足 | `runtime.ts:220-339`、`files.ts:79-83`；见 R1-W2 |
| 新使用扣冻结量，成功标记证据且保留扫描状态 | 是 | `files.ts:176-213`；冻结用量后新增1次仍保留测试 |
| 真实 combined 类型贯通 producer、持久 schema、公开类型及消费者 | 是 | `trajectory-runs.ts:14`、`:32`；product-contracts、navigation-model、boot.jsx 对应增量；冷恢复测试 |
| 不新增运行时 fork/private import、第二循环或跨包绕过 | 是 | 完整 diff 无该类新增；复用已通过 runtime dependency contract |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| combined 显示“记忆与技能复盘”；一个真实后台 fork，保留状态和进入／返回 | M1 联合轨迹用途和范围可辨认 | 两处名称映射，真实 kind 与范围持久记录 | `knowledge-review.test.ts:6` 冷恢复；progress 记录 Global Web IM 入口与范围 | 接线和持久化 covered；视觉／交互由独立产品报告确认 |
| 刷新后能从持久发起记录进入同一次执行 | M1 联合轨迹退出标准 | 原有导航与持久 runs，未引入地址深链变化 | 作者记录刷新回父范围，可重入同子范围；没有声称自动恢复子执行 | 与本 unit delta 一致；不扩张为地址栏子执行恢复承诺 |

## Issues

### CRITICAL

无。

### WARNING

#### R1-W1：Memory 读取状态覆盖原生失败／取消（CONFIRMED）

- 契约：`design.md:162-165`，正常结束但读取不全才转换；原生失败或取消保留相应终态。
- 实际：`packages/dsh-integration/src/knowledge/runtime.ts:297` 的 incomplete 分支未检查原生 stopReason。
- 独立复现：`/tmp/feat637-static-step-limit.mjs` 使用真实锁定 DSH 子进程。父轮次结束后 Memory review 连续读取 USER.md 而未读取 MEMORY.md，触发现有16步 hook。`trajectory/runs` 返回 `stopReason=aborted/state=cancelled`，同次 `knowledge.facts` 为 `status=error/diagnostic=memory_read_incomplete`。结果在 `/tmp/feat637-static-step-limit.log`。另用 `/tmp/feat637-static-native.mjs` 在部分读取后抛 provider failure，同样覆盖原原因。
- 建议：只在 `result.stopReason === 'completed'` 且读取未完成时转换 status/diagnostic，其余保留原失败／取消结果。扩展已有生命周期测试，保护取消和 provider failure 的可观察诊断。
- 影响边界：未发现错误推进周期或回滚真实写入；问题是持久复盘终态／诊断与真实执行不一致。

#### R1-W2：核心联合生命周期与 F4 恢复约束缺行为回归保护（CONFIRMED coverage gap）

- 契约：`spec.md:149-158`、`:184-208`，`design.md:109-117`、`:184-195` 及验证矩阵；`docs/development/testing.md` 要求保护稳定的可观察接口和持久状态，不能仅有实现文本。
- 搜索全部 integration 测试中的 F4/combined/knowledge.facts/batch* 后，现有 `knowledge-review.test.ts:39-70` 只覆盖一个目标的单会话不足 → 两完成会话正向，以及未读 patch 拒绝；断言 reviewed_session_ids 写入并未验证它实际阻止再次消费。`knowledge-policy.test.ts:124` 只拒绝 F4 edit。现有测试未驱动同目标重叠任务、待执行／运行中历史、错 owner/Agent/workspace、已处理历史再触发、错目标／错 root patch 或接受后手工来源保护。联合 fixture 也没有在途关闭参与 feature，或在同一根 session 中证明单项运行不重置另一类别及运行中新活动。
- 建议：在已有 lifecycle owner 以受控延迟 fixture 组合保护上述最重要失败原因，不为每条设计句子新建测试。至少覆盖：联合在途关闭后不能继续写、事实保留且周期可重试；同根不同 interval 的单项计数；F4 同目标并发只一 fork 且新使用保留；已处理／未完成／错归属证据排除；绑定目标与来源拒绝。复用现有真实文件测试处理文件层范围，不跨层重复。
- 边界：这是一项已确认的回归证据缺口，不声称这些分支已在生产失败。不要求为假设性异常增加产品 fallback 或抽象。

### SUGGESTION

无。

## Evidence retained

- 已读取复用 `/tmp/feat637-tests-serial.log`：122 文件、581 项；`/tmp/feat637-last-tests.log`：最终两文件9项；`/tmp/feat637-focused.log`：6文件22项；`/tmp/feat637-typecheck.log`、`/tmp/feat637-pytests.log`：65 passed/31 deselected；前端 build 和103文件963项日志。作者 progress 提供命令、版本和边界，日志结果与受审树相符，未重复全量。
- 完整 diff 和相关实际调用方逐项核对；本轮 `git diff --check` 通过。
- 独立临时原生复现2个；使用合成数据，Node24.22.1，均已 shutdown 并删除自身运行目录；证据脚本和输出位于 `/tmp`，不提交运行数据或 secret。
- 未启动产品服务或操作生产实例；未承担产品 reviewer／设计 reviewer。
- 报告由 caller 提交，report_commit 尚无；未创建额外 worktree。

2 warning(s) found. Fix before PR.

## Round R2 / delta + targeted-closure

- validated_at: `fc101f8532e638324ebcf8bf60e51044af68c377`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- verification_mode: delta / targeted-closure
- fix_delta_range: `d617906aed41fa14a34f4b3f1b5e49f179ed4129..fc101f8532e638324ebcf8bf60e51044af68c377`
- focus_issues: R1-W1、R1-W2
- requires_full_verification: false
- verdict: PASS，0 CRITICAL / 0 WARNING / 0 SUGGESTION（独立静态门禁）。R1 历史结论保留，当前结论以本轮为准。

### 历史问题关闭

| Issue | 结果 | 实现／行为证据 | 结论边界 |
|---|---|---|---|
| R1-W1 原生终态被覆盖 | closed | `runtime.ts:290` 只在原生 completed 时应用读取未完成转换；`knowledge-policy.test.ts:67-108` 的两种原生失败核对持久 review/trajectory 的 error/failed 与 aborted/cancelled，并验证不消费周期、后续重试正常 | 不生成 DSH 未返回的 provider 诊断；仅保留原有结果。原正常 completed 但 Memory 未读全的拒绝测试仍保留 |
| R1-W2 联合生命周期保护 | closed | `knowledge-review.test.ts:39-91`：同一根 session Memory=2/Skill=3，依次 memory、skills、memory；联合运行中已写 Skill，新增前台活动后关闭 Memory，后续写入不落盘，真实 fact/文件保留；下一次 skills 单项及重开后的 memory 单项正常 | 使用可观察 review kind、终态、facts 和磁盘产物；不按内部私有调度次数建立测试 |
| R1-W2 F4 并发／证据／去重 | closed | `knowledge-review.test.ts:93-148`：错误 owner 和缺失历史不能与单会话凑数；第二会话仍运行时不启动；完成后只提供 first/second；F4 持有期间两个会话同时继续使用，只有一 child，冻结后2次新使用保留；仅已处理会话再累计到20仍不产生第二 child | 错 Agent/workspace 与错 owner 使用同一资格条件，当前新增保护已覆盖实际风险链，不要求为等价字段机械复制；不新增分布式调度或永久结束标记 |
| R1-W2 绑定目标与来源保护 | closed | `knowledge-policy.test.ts:134-148`：拒绝 create/edit/write_file/remove_file、错 name、错 root，同名全局文件保持；来源在选中后变 F1 时拒绝 patch，目标正文保留 | 文件层已有锁内强制检查，测试落在最低写入边界，不再复制整个原生旅程 |

### 新增 delta 一致性

| 改动 | 契约与依据 | 核对结论 |
|---|---|---|
| 排除暂缓 Skill 修改及待确认状态进入 Memory；消除 current situation/state of operations 歧义 | spec 无长期价值信息不沉淀、单一归属、Agent 选择不冒充用户要求；Gateway delta 的长期价值与知识归属要求 | aligned；四处文案与 prompt-map 同步，无新写入能力、授权或审批机制。修复后的模型行为仍由产品 reviewer 给证据，不用文案检查冒充质量通过 |
| F4 排除 skill-catalog 元数据 | design 的“正常完成使用过程与工具结果”、有限证据预算；不把目录重复注入作为独立使用证据 | aligned；仅排除宿主自动目录 source，真实使用/结果/用户消息及两会话门槛保留，20k/100k 限额不变。24技能真实目录 fixture 在旧代码红、当前绿；修复原有正向不可达，未扩大历史权限 |
| 原生失败／取消保留；新增回归 | design 的正常完成读取结算、原生终态保留；原单项/联合/F4边界 | aligned；见关闭矩阵 |
| 设计文档状态、刷新和 runbook纠错 | R3 Approved 后的非实质 Author Resolutions | retained；未改 spec、delta、公共接口、milestone。刷新仍是回父执行后由持久发起入口重入，不改为 child 地址恢复 |

### Evidence retained / 本轮执行

- 独立核对全部 patch 产品/测试改动、R1 findings、当前实现及两份 delta；开始时 clean，HEAD 固定为上述版本。
- `/tmp/feat637-review-red.log` 两种终态用例旧实现失败；`/tmp/feat637-catalog-red.log` 原目录挤占导致 F4 不启动；`/tmp/feat637-review-fixes.log` 最终两文件9项通过。既有 fixtures 通过真实锁定 DSH 和持久文件/协议结果保护风险，可信且适用于冻结版本，无需再重跑。相关 package build 通过证据由 progress 接力段给出。
- R1 已核对、patch 未影响的全量、前端、架构和原文件读取基线结论 retained。未机械重跑全量，未启动服务，未修改源码或测试。
- spec21场景内容质量及真实 UI 由独立产品 reviewer 继续；本静态 PASS 不声称产品 gate 已通过、Ready PR 或部署完成。
- 本轮只追加 code-review.md 与 verification.md，不提交；report_commit 由 caller 落实。

## Corrected Delta Reconciliation

- verification_mode: corrected-delta，合并在本次独立静态任务中执行。
- validated_at: `fc101f8532e638324ebcf8bf60e51044af68c377`
- executed_base: `5462b7217421a2c27871c1c5951c1e48644e54ba`
- 两份 delta 与首文档从 R1 起未修改（已用指定两 SHA 的 git diff 核实），未为空变更单独重跑；本轮逐条对照最终实现/测试并保留未变覆盖。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Gateway：长期价值与明确归属（含重复、纠正、临时经验、当前读取和未读完结算） | memory/skills/combined assets；memory-curation工具说明；runtime:136-142、:290-297；review-files | 原位 replace/remove、原文件分页与快照保护；knowledge-review未读全但保留Skill的生命周期；policy原生failure/abort；prompt真实内容质量由产品gate核验 | aligned |
| Gateway：Skill单操作、部分成功及已有文件完整读取 | files:72-120；review-files:29-77；skill-creation工具协议 | knowledge-policy完整原文件、变化拒绝、连续patch及支持文件；knowledge-review联合取消已成功Skill/fact保留 | aligned |
| Gateway：非Global F4、两会话、无效/已处理排除、自动来源、目标与并发 | runtime:220-339；files:79-83、:176-213；skill-batch asset | 扩展F4原生fixture、Global禁止、manual candidate、低层错target/root/action/source拒绝；catalog过滤保留正常任务证据 | aligned |
| Gateway：combined同时到期、单项回退、独立计数、取消/部分成功 | runtime:241-299、:341-344；持久kind与真实fact | 联合单fork/冷恢复、同根2/3周期、在途关闭及后续单项、未读全重试 | aligned |
| IM：真实发起用途、单次combined范围、持久入口刷新后重入 | trajectory-runs、product-contracts trajectory kind、navigation-model与boot两处用途名称 | 原联合冷恢复协议测试、导航名称测试；作者先前真实范围证据retained，独立产品gate继续 | aligned |

### Uncovered Observable Behavior

None。暂缓知识的排除属于既有长期价值／单一归属约束的修正；skill-catalog过滤恢复原有F4合格正向路径，不是新的证据单位或放宽配额；原生失败/取消保留是既有结算契约。未发现本次 unit diff 中遗漏的对外行为。

Outcome: aligned
