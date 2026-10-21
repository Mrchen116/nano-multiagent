# feat-627 — 产品验收报告

> 对齐：[spec.md](spec.md) 的全部用户 Scenario；[design.md](design.md) Runbook for Reviewer。
> Round R1；mode=full；revalidation_mode=full；2026-10-21。
> Validation snapshot: `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28 → 31e47aab36782a99c17d709b6496f344892c55a1`。
> Nano 后续 HEAD 推进仅包含独立审查报告；受验实现未改变。插件固定 Release `dsh-agent-context@0.3.0-rc.1`，交接源 commit `7f0a2b78ec530075edd48452c2cf5499548ca99c`。

## Verdict

**fail**。3 项 major 可见问题，另有默认身份矩阵证据缺口。真实长任务完成了 12 份材料、同一 turn 13 次换窗与一次性测试消息，但最终报告合计错误，换窗后两次违背明确工具约束，插件模型列表与实际管理状态不一致。不能用正确的差额一列、切窗次数或工具调用成功替代整体交付正确性。

本报告仅陈述产品观察，不将这些现象归因为某段实现、插件算法或模型能力；未读实现定位根因，也未修改源码、测试或受版本控制配置。

## 用户旅程体验

真实登录隔离 Web IM `http://127.0.0.1:62224`，由其消息 API 发出用户任务，经过实际 Node/PA/DSH 和 `deepseek:deepseek-v4-flash` 模型，读取实际收到的 Agent 消息。浏览器以 1280×720 查看聊天、审批卡、最终报告和恢复回复。没有内部 submit、fixture 回复或空调用三次换窗。

用户先给“旧方案”，随后明确改为“最终验签审计”、丢弃 RC-OLD、只发一次测试确认、禁用 bash。12 份本地合成卷宗每份约 44k 字符，尾部为最终验签；Agent 按序实际读取全部文件（01 在前一阶段，02–12 在长任务 turn），工作量超过三窗。最终中文表格能按 incident 对照基线、投递、差额和凭据，确认消息为独立气泡，身份与时间清晰，整体排版沿用现有聊天设计，无遮挡或无法阅读的问题。

然而表格合计基线 **14353**、确认投递 **13308**、差额 **245** 彼此不相减成立。逐行原始值与独立 oracle 核算应为 **13482 / 13237 / 245**。用户看到“已完成”及正确外发回执，仍会拿到错误汇总。重启后要求独立复核，Agent 又声明与原始证据吻合并重复同一错误合计。这是交付内容错误，不是 UI 风格问题。

另一次旅程中，Agent 已成功使用 Notes，却从插件列表告诉用户“无已安装插件”；Web 管理接口同时显示默认插件 enabled。用户无法由模型入口可靠判断当前机制。使用准确包名的管理入口完成停用/恢复后，状态和实际工具行为正确。

关键画面保留在本机 `/tmp/feat627-acceptance/final-ui.png`、`peer-restored-ui.png`，未提交截图或原始日志。最终报告原件仍保留在隔离 workspace `acceptance627/final-report.md`，未替用户修正后冒充原始验收通过。

## 环境与证据索引

- 专用身份：`e2e` / `e2e-peer`，不同 workspace；仅隔离 IM，未触达生产或外部频道。
- 主聊天 `c_61rlhkes`，session `d21f31a1-755a-49f4-b9cf-25f21709791a`；peer 聊天 `c_zcmlq102`，session `837186c0-dad5-4923-9632-b112969bfdab`。
- E1 初始任务消息 `bfc99bb3bc754f4ea106f721e5d95d44`；最新纠正消息 `1ba8705f1ac445959d359b9a99e584c0`（native `:initial` item 103）；成品回复 `aa14662596554b0cac68caf78fbe494f`。
- E2 原始事件本机导出 `/tmp/feat627-acceptance/session-events.jsonl`；turn 5 的 compaction/start seq：135、172、210、260、310、360、413、457、495、529、563、597、638。13 次均成功提交；其中有材料处理、Notes 保存/恢复、History 恢复，不是连续空切窗。压力提醒 seq 154/446/620；fallback 包括 161/199/249/299/349/402/484/518/552/586/627。材料 02–12 read result seq 108、194、244、294、344、397、479、512、545、579、580。
- E3 原始模型请求本机目录 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_10-58-11_852_d21f31a1-755a-49f4-b9cf-25f21709791a/`。原日志与凭据不入 Git。
- E4 唯一确认消息 `f87d2153f3664417864e6241219b765d`，内容精确等于 `FEAT627_AUDIT_CONFIRMED`；重启续接完成后聊天 API 中精确匹配条数仍为 **1**。
- E5 正常重启由 `pnpm pa restart --config <本 worktree>/.gateway-config.yaml` 完成，PID 51847 → 53542，保持同一 session 与 DSH home，更新 `.gateway.pid`。续接用户消息 `1a0400a0091b4a368ddf850007a53168`，回复 `db854710b5b14c5fb6c3365c9aec34c3`。
- E6 续接 History `read :initial item 70`，`total_chars=94291`；先 offset 0 / limit 6000，再 offset **83291** / limit 11000，实际读出第 225/226 行 `valid=true`、`confirmed_deliveries=1005`、`RC-01-12934`、`PROOF-01-TAIL`、`discarded=RC-OLD-01; gap=14`。未重新读取 incident-01 源文件。用户纠正原文另由 History item 103 恢复，来源为 nano-human。
- E7 peer 无记录/越界结果回复 `28cf8e6d12ca4417a5c7a59098c6112e`；存储故障回复 `5b6a0d32bee9447887f197df1fd0fbce`；模型空列表回复 `f4af8d98ec7f4101ad5d7c37df5d8bda`；停用后未知工具回复 `6ec55e2349a14aec9ecb4f1125ef4d96`；恢复成功回复 `2bff1155e2994a7ea85fb45eb98e5492`。
- E8 完整消息响应本机 `/tmp/feat627-acceptance/c_61rlhkes.json`、`c_zcmlq102.json`；开关管理响应 `peer-disabled-after-restart.json`、`main-enabled-after-restart.json`、`peer-reenabled.json`。

### 临时环境修正与证据边界

只调整忽略的隔离配置。预算覆盖最终为 `agent-context` row config：`modelSurface: always, bufferTokens: 30000, reminderTokens: 6000`；C=65536、O=16384、W=19152。第一次临时 patch 遗漏 modelSurface 导致 Notes 未注册，补齐整段配置并正常重启后开始有效长任务；该前置错误不归为产品缺陷。

原隔离审批模型不支持固定 low effort，出现可见审批卡。广泛定位与违反用户限制的 bash 均拒绝；隔离插件只读/启停操作在具体动作上允许一次。长任务结束后的正常重启仅把隔离 `tool_approval_model` 改为支持 low 的 `codexOAuth:gpt-6-luna`，保留审批机制，主任务模型未变。前置修正不掩盖随后两次违反禁用 bash 指令的事实。

## Reference Artifacts Reviewed

N/A：本 unit 无前端变更、原型或 must-match 视觉契约。仍实际检查了受影响聊天流程，结果见用户旅程体验。

## 问题清单

| # | 严重度 | 现象与证据 | 处置 |
|---|---|---|---|
| R1-1 | major / blocking | 12 行明细全对，但成品合计 14353/13308 错误，正确为 13482/13237；245 差额正确。E1 成品和本地 final-report.md 均错。E5 重启“独立复核”仍重复错值并声称吻合。 | 交付内容正确性未通过；保留原成品，修复/重新冻结后复验完整交付。不得只修表格后宣称长任务原本通过。 |
| R1-2 | major / blocking | 最新用户原文明确“不用bash，不要做目录搜索”，且已从 History item 103 恢复。随后 seq 382 仍调用 bash `echo ok`；用户拒绝重申后，seq 654 又调用目录 `ls -la`。两次前均有 Notes 恢复，后一次 Notes 已保存“全程禁用 bash”。 | 最后确认约束未稳定保持；两次被拒绝而无实际 shell 副作用，但需要用户再介入，Scenario 不通过。仅报告观察，不预判根因。 |
| R1-3 | major / blocking | peer 实际可用 Notes；`plugin_manager list_bundles` 返回 `entries: [], diagnostics: []`，模型据此告诉用户未安装。与此同时 `GET /im/v1/agents/e2e-peer/plugins` 返回 dsh-agent-context rc.1 enabled。 | 既有模型管理入口不能正确展示默认插件；准确包名 set_bundle 可恢复成功，不能抵销列表误导。最初以 row id `agent-context` 调用的 not-installed 不另算包名正确时的失败。 |

## 验收标准覆盖

### Requirement: 多次换窗后能继续同一个任务 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 连续长任务 | spec 用户场景 1、3 | 12 份完整材料，同一 turn 13 次切窗，产出报告并一次 send_message | E1–E4；最终 UI | fail | 能推进和完成，明细与245正确，发送一次；但合计错误且两次需用户拒绝额外 shell 操作，不能判完整目标达成。 |
| 后续纠正覆盖旧方案 | spec 用户场景 1、2 | 初始旧方案→最新 valid=true 口径，并保留明确不用bash约束 | E1、E2 seq382/654 | fail | 标题、最终原因码和剔除 RC-OLD 正确；禁用 bash 约束两次被违背，不能以部分纠正有效判全通过。 |

### Requirement: 需要旧细节时能恢复可核对的原始依据 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户约束与长工具结果 | spec 用户场景 2 | 切窗后恢复 nano-human item103；重启后从94,291字符原工具结果分段读尾部 | E6、E5 | pass | 正确恢复原约束来源与01最终验签，没有让用户重新粘贴或重读源文件。错误合计另记R1-1，不影响原文恢复事实。 |
| 没有可恢复记录 | spec 用户场景 3 | 新peer会话 list为空，读取不存在文件/窗口 | E7首个回复 | pass | notes ENOENT、history not_found，明确没有取得内容，不虚构恢复成功。 |

### Requirement: 上下文压力不造成无说明的任务丢失 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 接近预算及强制换窗 | spec 用户场景 3；design压力路径 | 降低工作预算，实际材料触发reminder和fallback，Notes后new_context继续 | E2压力与13次边界 | pass | 任务未丢失，待办推进到12份。实际覆盖工作预算耗尽fallback；provider硬溢出不冒充实测，设计允许确定分支由实现层验证。 |

### Requirement: 已保存工作记录在重启后仍可恢复且访问范围不扩大 — 组内结论：pass

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 正常重启后继续 | spec 用户场景 4 | 同一聊天、同一session正常Node重启后恢复状态和长尾依据 | E5、E6、E4 | pass | 无需从头开始；已发送状态恢复，未重复发送。复核合计错误仍由R1-1阻塞整体交付。 |
| 其他 Agent 或 workspace 的记录 | spec 用户场景 4 | peer Notes `../../e2e/secret.md`、History指定主session window/item | E7首个回复 | pass | invalid note path / not_found；未获得主会话内容，未用业务文件工具绕过。 |

### Requirement: 所有 Agent 默认使用无摘要换窗且可显式回退 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新建与已有 Agent 无需手动配置 | spec 用户场景 5；design身份矩阵 | 交接的两普通Agent中实际调用恢复工具，新增peer聊天没有手工装包 | E1、E7 | inconclusive | 两普通身份可用；未交接独立Global、Personal、原生子Agent、升级前profile及空业务allowlist/Auto-off三规则的可操作测试身份/创建配置。版本绑定集成测试不替代这些未观察真实旅程。 |
| 停用状态在重启后保留 | spec 用户场景 5 | Web管理入口停用peer，再正常Node重启，查询状态并实际尝试notes | E8、E7停用回复 | pass | disabled跨重启保留；notes返回unknown tool，其他三工具不在当前集合；主workspace仍enabled且正在恢复。未把单独停用状态观测宣称为测过旧摘要模型的实际长任务压缩效果。 |

### Requirement: 通过现有插件入口控制生效与撤销 — 组内结论：fail

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 启用、停用和恢复 | spec 用户场景 5 | API停用、重启、模型以准确包名恢复并重新读取笔记；比较主workspace | E7、E8 | fail | 管理APIoff/on及状态隔离正确，恢复读回PEER627_PERSIST_SENTINEL；但模型list_bundles为空误导用户（R1-3），完整既有入口体验未通过。 |
| 加载或恢复失败 | spec 用户场景 5 | 先保存Notes，再可逆地模拟该路径为目录，实际read；随后还原 | E7 EISDIR回复、恢复回复 | pass | 明确未读出原文、给出EISDIR和修复后重读步骤，未覆盖或把记忆冒充读取。覆盖“已保存记录恢复失败”分支；未额外声明执行过坏包加载分支。 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，当前未提出跨包架构变化。
- [x] `docs/specs/gateway/agent-capabilities.md`：需要由 orchestrator 在通过门禁后校正并归并本 unit delta；本轮不应提前宣称已验收行为。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。

## 环境收尾

未另起独立服务，使用 caller 交接栈，按交接要求留运行现场用于修复。当前Node PID53542；peer恢复enabled，主Agent仍enabled；临时存储故障已还原，原笔记和报告保留。隔离预算与审批模型配置保留在忽略文件，未触及生产、主checkout或共享LLM代理。只提交本 acceptance.md。

---

## Round R2 — 定向复验与归因口径澄清

> 2026-10-21；mode=targeted；executed_base=`d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`；validated_at=`7fe9224fb3f566b1db2ed4964c4b0e4d09cedb00`。
> fix_delta_range=`b09851c01cf39b6198edd6956914e66b52153c24..7fe9224fb3f566b1db2ed4964c4b0e4d09cedb00`；prior_acceptance_paths=本文件 R1。
> 本轮运行 Node PID56378。随后共享 HEAD 的 `3cb03ab72` 仅为静态报告提交，不改变受验实现。插件 rc.1 与 rollover/Notes/History/提示词均未改动；仅复验模型插件列表修复、补齐身份矩阵，按具体证据继承其余 R1 行为，不机械重跑 13 次换窗。

### 最新裁决

**pass（本 unit 的上下文管理与默认接入范围；保留 2 项模型 Side Findings）**。

用户在 R1 后明确要求：“注意区分哪些问题是我们引入的上下文管理的问题，哪些是agent正常的问题”。据此，本轮分别判断可观测恢复机制、已确认接入缺陷，以及恢复内容已经正确送到模型后发生的计算/遵循错误。R1 的原始报告、错误成品和两次禁止调用均原样保留；本轮不是把错误答案宣布正确，也没有声称普通模型行为已经修好。

模型列表遗漏已由真实入口关闭，默认范围缺口由七种实际执行身份补齐。本轮没有发现仍阻塞本 unit 的上下文丢失、错误原文恢复、重复副作用或权限扩大。Highest Required Action：**out-of-unit**，仅指独立跟踪两项模型行为观察；本 unit 无待修复项。未创建外部 issue（gh_issues_filed=0）。

### R1 问题逐项继承与归因证据

独立检查了 [R1 attribution 证据定位](M1-agent-context/evidence/r1-attribution.md) 指向的三份真实 provider request，不只采用实施者结论。只读取运行证据，未阅读实现作根因定位。

| R1 项 | 原始可见事实是否改变 | 独立检查与 Regression Relation | R2 处理 / Action Rationale |
|---|---|---|---|
| R1-1 错误汇总与错误“独立复核” | **未改变、未修复**。原报告仍是14353/13308/245；正确为13482/13237/245。 | `2026-10-21_11-44-52_585-req-anthropic_messages.json` 在第一次错误write前包含全部12行正确基线、确认投递、原因码与proof，逐项与oracle核对存在。没有观察到Notes/History改变或丢失这12行。关系：**unclear，未证实为本unit回归**。 | 保留 major 级答案质量 Side Finding，建议 out-of-unit 的计算/复核能力评测。不将正确输入后的错误计算强归因于上下文数据损坏；也不声称已证明换窗时机对模型毫无影响。 |
| R1-2 两次违背禁用bash | **未改变、未修复**。两次请求均发生且被审批拒绝。 | seq382之前 `2026-10-21_11-42-37_313-req-anthropic_messages.json` 有2处“不用 bash”，来自已恢复Notes/进度；seq654前 `2026-10-21_11-44-34_432-req-anthropic_messages.json` 有“禁用 bash”任务标题及原约束引用。关系：**unclear，未证实为本unit回归**。 | 保留 major 级指令遵循 Side Finding，建议 out-of-unit 对照评测。不能说禁止约束未进入模型；审批阻止执行也不能把尝试说成遵守。没有新增解析器/硬禁令/提示词定制来掩盖观察。 |
| R1-3 模型插件列表为空 | 已真实修复，**closed**。 | 模型入口list_bundles先显示默认插件enabled=true；模型入口停用后显示false；恢复后显示true。各状态与管理API一致。关系：**direct**。 | fix-implementation 后实测关闭。无需再次安装包，installed=false仍可正确展示默认插件。 |
| 新/旧、Global、PA、子Agent矩阵缺口 | 已补齐，**closed**。 | 下表七种身份均经过真实IM入口、真实模型、真实工具与一次有内容的换窗。 | 不再借用测试套件代替用户旅程。空业务集合没有因上下文工具而出现文件/shell工具。 |

### R2-A：模型管理入口实际闭环

继续使用peer聊天 `c_zcmlq102`，所有调用均为真实模型的 `plugin_manager`，没有内部owner调用代替：

1. 用户消息 `ebcc439feb854ed796c6d5d54a683d34` → 回复 `c0d1d9a97ebb4061907f49c8164b4f7b`：默认插件 `dsh-agent-context@0.3.0-rc.1`、enabled=true、installed=false、row=agent-context、diagnostics=[]。响应没有单独state字段，Agent如实说明而未捏造字段。
2. 用户消息 `9e6ed42af2004a27b7ca212dcb1501a2` → 回复 `5291a134f1bc4de9ae194684e22ded36`：准确包名set_bundle enabled=false返回applied，随后模型list_bundles显示false；管理API响应也为disabled，存于本机 `r2-peer-disabled.json`。
3. 用户消息 `4f3bf995706449bbb23be5a7583c130c` → 回复 `5281c730f946454c8a3f86726134c841`：模型set_bundle恢复并再次list，显示true；Notes实际读回 `PEER627_PERSIST_SENTINEL`。管理API与主workspace均enabled，保留peer开关隔离。

无需更新前端原型。R1聊天排版与操作体验继续有效；修复后用户可以由模型入口辨认默认插件及实际启停状态，不再被“未安装”误导。

### R2-B：默认身份与工具边界矩阵

caller通过真实IM控制面准备 `/tmp/feat627-acceptance/matrix-resources.json` 中六个独立身份，reviewer创建测试聊天并发出任务；old profile 是交接时预先存在的profile，未为任何身份手工安装上下文插件。reviewer只读取配置核实Auto关闭与三规则，未扩大业务allowlist。

普通/旧profile/PA任务为40条物流材料，仅记录07和23最终核验；先预算→Notes保存→new_context一次→Notes恢复→History实际读原文再核对。正确结果均为 `EVT-007 / KEY-007-627` 与 `EVT-023 / KEY-023-627`。Global及其唯一原生子Agent用10条运单材料，正确结果均为 `A03/P03、A08/P08`，剔除valid=false候选。

| 身份与规则 | 真实聊天 / session | 四恢复工具与实际原文恢复 | 业务工具边界 / 结论 |
|---|---|---|---|
| 新普通nano；Auto off；业务[] | `c_wrkm6e9h` / `806b704b-fbf8-43ca-ad5c-5816407af222` | 四项实际成功，1个提交换窗；History item8读4021字符原始nano-human消息；IM回复`d1cb6dab85bf4d2a8444c59a0743e9b3`正确 | 实际request/header工具恰为四恢复工具；pass |
| 新普通codex；Auto off；业务[] | `c_idydet9t` / `6a0fd852-52b1-4056-b795-d5accf0c34c2` | 四项实际成功，1窗；item8读4021字符；IM回复`ca174ab6607e4789830c935047fa0897`正确 | 同上，无业务schema；pass |
| 新普通dsh；Auto off；业务[] | `c_e0yibltj` / `c8f5205c-3441-4cdd-b0db-940155d2f488` | 四项实际成功，1窗；item8读4021字符；IM回复`eeeb9de00a824a0d8a775fc7e54a4f96`正确 | 同上，无业务schema；pass |
| 升级前普通profile；nano Auto off；业务[] | `c_sdo0mozl` / `dc4a873c-b162-4d49-9dab-bb9d7d9b66f7` | 四项实际成功，1窗；item8读4021字符；IM回复`e531e0bbbcb046819293e26512cf14db`正确 | 无需人工安装或加业务工具；schema恰四项；pass |
| Global；nano Auto off；业务[] | `c_o9vjwxgv` / `4399441b-d4f4-4a1e-98ff-1631575925d5` | 四项实际成功，1窗；History恢复原Inbox结果item22（1084字符），保持role=tool来源；实际创建1个子Agent，最终IM回复`e177e69f924a4215a578edb69be889fc`正确 | 仅四恢复工具+既有conversations/inbox/send_message/subagent；pass |
| 原生子Agent，继承Global限制 | 父会话subagent真实产生 `9d6a0521-2f55-4fde-9ca9-a8fd7f0df03a` | 四项实际成功，1窗；History item8读1195字符自身任务原文；Notes读回，子结果被父会话收到并交付 | 实际schema恰四恢复工具；无文件/shell、未创建下级；pass |
| Personal；nano Auto off；业务[] | owner私聊 `c_f4fe01fbf858` / `1d9ba23e-2abb-4169-9eaf-d16c5183449d` | 四项实际成功，1窗；History实际恢复原Inbox材料item21（4545字符），保持role=tool；私聊回复`a5384fb7bfe34738bc59adbb291dd5e2`正确 | 仅四恢复工具+既有conversations/inbox/personal_sources/send_message/subagent；pass |

以上结果不仅是Agent自述：独立检查七个native session的tool/call与tool/result，无恢复工具isError；各自恰一个compaction/end。普通/子Agent的模型schema无业务工具，Global/PA只保留既有产品固定能力。本轮未故意伪造未声明的业务工具调用，因此不把“未提供业务schema”扩大成重复验证过所有强制dispatch拒绝分支；这些分支属于已有版本绑定集成证据。

Global/PA最终回复通过实际send_message到对应测试聊天，非内部submit；Global子Agent确由原生subagent工具创建，不是独立假Agent或fixture。浏览器实看Global用户请求、阶段进展和最终回复，身份、窗口前后及父子结果分段可辨认，1538×1014视口；本机画面 `/tmp/feat627-acceptance/r2-global-ui.png`。

### R2 Scenario 累计覆盖与保留边界

本表的pass限定为本轮按用户归因口径审核的上下文管理行为。R1原始任务的错误成品与禁止调用保持原fail事实，不重写成“答案完全正确”。

| spec Scenario | 当前上下文机制结论 | 证据与继承说明 |
|---|---|---|
| 连续长任务 | pass | 继承R1 12份材料、13个有内容窗口、一次且仅一次确认消息、完整明细数据；R1错误汇总保留为未修复Side Finding，不宣称完整答案正确。 |
| 后续纠正覆盖旧方案 | pass | R1最终验签口径/新标题/剔除旧码正确，History原纠正消息与Notes禁止约束实际进入后续请求；两次模型不遵守禁止指令仍原样保留，未证实为本unit丢失约束。 |
| 用户约束与长工具结果 | pass | 继承R1 94,291字符原结果在offset83291恢复尾部、原用户引用恢复；R2再覆盖nano-human和Inbox tool两种来源。 |
| 没有可恢复记录 | pass | 继承R1 E7真实空记录、ENOENT、not_found，修复未改变此行为。 |
| 接近预算及强制换窗 | pass | 继承R1真实reminder/fallback与安全切窗；R2未改预算/插件包，不重演已验证压力路径。 |
| 正常重启后继续 | pass | 继承R1同session正常重启、原长尾恢复与已发送状态恢复；不把错误复核称为正确。 |
| 其他Agent或workspace记录 | pass | 继承R1跨路径、跨session拒绝；R2实际子Agent只读取自身任务，并保持受限schema。 |
| 新建与已有Agent无需手动配置 | pass | R2-B七身份真实调用和model schema补齐原inconclusive；每个身份都有有内容换窗及原文恢复。 |
| 停用状态在重启后保留 | pass | 继承R1 peer停用、正常重启、unknown notes且主workspace仍enabled；R2仅修列表，不改变持久配置逻辑。 |
| 启用、停用和恢复 | pass | R2-A模型入口完整off/on/list闭环与API对照，R1-3关闭；Notes保留、主workspace未改变。 |
| 加载或恢复失败 | pass | 继承R1已保存笔记EISDIR真实错误、诚实用户反馈和还原后读回；仍不声称实际坏包加载分支另跑过。 |

### R2 收尾

原R1成品未修改；未改实现、测试、设计、提示词、业务工具权限或生产配置。全部矩阵身份与peer最终默认插件enabled，原笔记保留；caller提供的PID56378栈留供后续交付。只追加本报告。跨包SPEC/AGENTS/文档规范无需变化；gateway canonical增量仍由orchestrator按最终实现归并。原始矩阵消息、配置检查与native事件快照仅保留 `/tmp/feat627-acceptance/`，不提交凭据或原始日志。
