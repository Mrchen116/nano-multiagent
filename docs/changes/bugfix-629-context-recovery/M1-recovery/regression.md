# bugfix-629 — 候选版回归记录 R1

> 2026-10-21；独立 change-reviewer；候选实现 Nano `2ee87df7becb22f5d2576c192dbbee3018a3a07f`，插件源码 `51eb236`、`dsh-agent-context@0.3.0-rc.2`。
> 候选 tgz SHA256：`5aa290fb5634cccccb6ed8f11b96acccac587fc708a420b80ecf29d2b2bf3461`。运行时使用 caller 已安装构建的这份本地包；后续共享 HEAD 与设计变化不冒充本轮受验版本。

## Verdict

**未形成最终验收：候选基线已被用户后续决策替代。** 用户要求新窗口只重建当前可用 Skill 目录、不自动重放旧正文，并撤掉 interrupted_turn。本轮真实压力恢复成功依赖的候选行为含该导航，不能据此批准后续方案或宣称纯 Notes/History 路径已通过。按 caller 指令只收尾已发请求，停止新增实验，交还隔离服务。

本轮只读产品实现，未定位实现根因、修改源码或测试。使用隔离 Web IM 实际消息与插件管理 API、真实模型 `codexOAuth:gpt-6-astra` medium；没有内部 submit 或脚本预定最终答案。无 UI 变更，按 runbook 采用 API 交付验收，未声称浏览器视觉验收。

## 主故障候选基线：AMBER629B

条件为默认 C=258400、O=32768、B=16384、R=6144；没有预算 override，PA Auto off。先前 Notes 已记载旧日记交付完成，navigation-check 在 seq334 写入“验证完成，无待处理任务”。新输入不依赖旧批次的待办。

1. Web IM 新消息 `0975d73d924e428f87b59dc440153827` 要求复核 AMBER629B 的25份分册，读取前不写新 Notes，只整理、不执行待办。原生 Inbox read seq360/result361 实际取得原文。
2. 同一 turn6、step4 的25次 skill 调用 seq370–418，结果 seq371–419 全部成功，共 **1,059,818 字符**，各42391–42410字符；没有用单册截断结果充当全量读取。读取后至压力换窗前没有 Notes 写入。
3. compaction/start421、summary422、end424；原生 checkpoint 明确 `Context reset reason: pressure`，shadowedTokenCount=277391，范围280–419。checkpoint含候选 `<interrupted_turn>`，turn_id=347。
4. 换窗后先 notes read preparation（430/431），返回旧批次已交付记录；随后 history list_items turn_id347（436/437）恢复新 Inbox 输入及原始工具记录，再 search 同turn skill结果 `- [ ]`（441/442）。原始 Inbox 仍为 tool 来源，observer通知仍为 system/nano-system，没有重标成人类授权。
5. send_message446/result447 真实发送消息 `14fd98802483482fbe5ec2ac6e895544`，聊天落库 completed；只有一份 AMBER629B 最终清单：琥珀实验原始波形归档B17（周四前）、给秦老师六张显微照片（明早）、读书会两袋咖啡豆（周日）。与分册01/13/25独立核对一致；未误用旧批次、未执行待办。turn/end452=completed。

**结论：该候选的默认压力组合实测成功；撤除 interrupted_turn 后必须重新实测，不能继承为最终 pass。** 后续 observer轮仅读取本测试owner另一聊天的背景，turn/end480=completed，无新增交付。

## 已完成的其他候选观察

| 场景 | 实际证据 | 候选结论与保留边界 |
|---|---|---|
| 七份Skill与普通步骤 | recovery-1..7各成功读取8697字符。PA主动换窗278；snapshot291的nano-used-skills仅1552字符，七个正文sentinel均0。seq298/303/308/313/318/324连续六个Notes/普通步骤；329实际skill重读recovery-1；334写完成，339仅发完成。上述步骤期间没有新runtime snapshot。 | 当时“曾用Skill导航”分支无逐步全文增长，实际按需重读成功。最终目录生命周期改变后需重验。 |
| 直接输入、两个有内容窗口 | 普通Agent session `ee8ae939-2cfa-479f-8b87-ca3450b0d8aa`，chat `c_isi20umr`。显式 `/skill:ledger-check`，业务工具仅workflow。compaction25/67；history按turn_id6读原输入item10及第二窗item60；最终消息`af1590df9a3d4769a0bdfbce0925a55d`一次正确交付108、67、175贝壳和规则标记。 | 两个有内容窗口与真实原文恢复成功。无skill/read时正文自动恢复属于旧候选行为，用户已要求取消，不能当最终通过。 |
| 正常重启恢复 | 同隔离Node正常stop/start，PID81429→84397。原session不变；普通Agent seq111/116/121实际History读原输入、第二窗结果及Notes，正确再次核对175。 | 候选重启恢复成功，未删除原记录。 |
| 插件off/on | 同workspace产品API set_bundle false/true；off后的实际provider tools仅workflow，显式Skill核算47成功；on后seq151/156/161实际读取原History/Notes，正确返回175。 | 候选开关与记录保留成功；未测试停用后长任务摘要压缩，不作该声明。允许skill工具分支的off组合尚未补跑，按后续暂停要求保留缺口。 |
| 空业务白名单 | 普通Agent profile改为[]；实际provider仅get_context_remaining/history/new_context/notes；seq177实际Notes读取，最终175+规则标记。 | 没有扩大业务schema。 |
| 会话与来源边界（暂停前已发） | 普通Agent seq190过滤不存在turn，195读取PA会话item遭not_found，200读取本会话agent-instructions项，turn/end206正常结束。 | 原生操作证明会话隔离；最终模型拒绝披露内部元数据，未给用户三项逐项结果，因此不把最终回答当完整用户旅程pass。 |

## 环境前置尝试，不计压力通过

- 首次七Skill路径不正确产生unknown；修正后七次正文成功才计入。此前插件安装、custom journal_fixture调用均被Auto off manual_required阻断；没有绕过审批。fixture预装由caller执行，仅作环境准备。
- 单个1,386,415字符journal-archive被原生spill裁为49,930字符（遗漏1,337,055字节），随后正确交付旧批次三todo但没有压力换窗。本轮明确不把它算主故障通过；有效压力证据来自后续25份完整分册。
- 一次History max_chars_per_item=6000被校验拒绝，模型自行改4000继续；未修改工具schema或实现。

## 证据与交接

- PA session：`30f48cc2-b740-43d8-aaf7-1ca035a4d48d`；chat：`c_7bdf1ad3596a`；隔离IM `http://127.0.0.1:63693`，node `wt-nano-multiagent-79125`。
- 原生证据位于本worktree `.dsh-runtime/**/sessions/**/<session>/session.v4.jsonl.zstd`；真实provider请求目录为 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_16-07-04_374_30f48cc2-b740-43d8-aaf7-1ca035a4d48d/` 及 `2026-10-21_16-13-18_886_ee8ae939-2cfa-479f-8b87-ca3450b0d8aa/`。
- 本机归纳 `/tmp/bugfix629-e2e/30f48cc2-evidence.json`、`ee8ae939-evidence.json`；最终产品响应 `pa-final-timeline.json`、`direct-final-timeline.json`。原始日志、凭据和测试素材不入Git。
- 最后观察PA turn7和普通Agent turn6均completed。Node PID84397，`.gateway.pid`已同步；服务保持运行，无新实验待发。PA/普通Agent上下文插件均已恢复enabled，普通Agent业务白名单当前为空。测试workspace、Notes、History、临时fixture保留，由caller接管清理或后续复验。
- 未新增自动化测试。Reference Artifacts Reviewed：派发时incident/design/runbook、当前agent-capabilities/auto-permissions、旧feat627验收（只参考范围，不拿其结论替代本轮新路径）。本轮只提交此候选报告。

## 上层文档

当前用户已改变Skill与恢复策略，incident/design/delta-spec由caller修订；本报告不修改它们。SPEC/AGENTS/文档体系未由本轮改变。最终受影响场景及验收标准需以修订后版本重新冻结并复验。

---

## Round R3 — 撤除候选恢复协议后的独立真栈复验

> 受验 Nano `35fccff2fdea096aad481c02e683c4176b7319b2`（实现 `c2a7d2a6c`）；插件源码 `2c29b0b`、不可变 `0.3.0-rc.3`，tgz SHA256 `58aee15f347f2a2a26e02bb9bd0c8766e3a54e06ae294695d3aed1583c9c8f99`。后续 R4 代码/设计推进不属于本轮受验快照。
> 全新隔离实例 `/tmp/bugfix629-r3-runtime`，IM `http://127.0.0.1:53554`；真实模型 `codexOAuth:gpt-6-astra` medium，PA Auto off。只经 Web IM 产品 API 发请求，未修改代码、预算或安全策略。

### Verdict：FAIL

**原故障：FAIL，已覆盖，非“未触发”。** 默认预算下，旧 Notes 已完成、新 Inbox 已读、新进度尚未保存、实际大工具结果导致 pressure 换窗这一组合再次使任务丢失。新窗口取消旧 Skill 正文、已用索引和 interrupted_turn 的机制符合本轮设计；但模型随后信任旧 Notes 而结束，未恢复新任务，也未交付待办。

R3-1：**major / blocking；Regression Relation=direct（原事故仍可复现）；Recommended Action=fix-implementation。** 期望是按原 Notes/History 恢复并完整交付一次，实际为任务无清单交付便 completed。没有给失败任务追加提示、没有要求必须 History、没有重发或补救；后续独立维护检查不回写此失败。此报告不根据实现代码推断根因；caller 后续原生裁剪接线及 R4 复验另行冻结。

### 原事故的完整证据链

PA `pa_983b7fa8a560`、chat `c_e19a27f30db5`、session `534620fd-450e-4756-9b6d-04ba99d3276f`。

1. 准备输入 `b7c485373e024634b4013b632978891d`。七份 recovery Skill 成功结果 seq25/30/35/40/45/50/55，每份8651字符，源文件总58373字符；seq59/60 Notes写入“准备已完成，目前没有待处理任务”。唯一准备回复 `97d7a61d1a6844a79f6b49515a3b5abc`，turn/end70 completed。
2. 新用户任务 `31ed8a15a99b417481cf6d334fa8ab6b` 要求 AMBER629B 的25分册、读取前不写新进度、只整理不执行待办。Inbox call82/result83真实取得该原文；seq87仅发送开始确认，落库消息 `455acb7e2dd2499daf1b2e428682e928`，不能算最终清单。
3. turn2、step4一次模型工具步骤产生25个 skill 调用 seq92–140，成功结果 seq93–141共 **1,058,668字符**。这一批是刻意构造的单步大输出压力样本，不代表普通25份日记的典型负载；每项低于单结果spill阈值，实际没有截断后冒充全量。其后没有新Notes写入。
4. compaction/start143、summary144、end146。checkpoint明确 `Context reset reason: pressure`，shadowedTokenCount=283827，移出seq8–141。新checkpoint只有原有窗口/Notes/History指引，没有 interrupted_turn、turn_id、旧任务正文或 nano-used-skills。默认预算实测由后续同配置 get_context_remaining seq210/211确认：C258400、O32768、B16384、R6144、H225632。
5. 实际换窗后 provider 请求 `2026-10-21_17-01-01_305-req-anthropic_messages.json` 中 AMBER629B、新任务正文和七个Skill sentinel均消失，interrupted_turn/nano-used-skills/turn_id均为0；原生目录由skill-catalog seq148重建。
6. seq151/152只读取旧preparation，正文仍为“准备已完成，目前没有待处理任务”；随后inbox check157、inbox read162读取另一个聊天的observer背景，**没有任何History调用**，没有恢复AMBER资料。turn/end168 completed。
7. 当时冻结的产品时间线仅含准备完成、用户新任务、开始确认，**没有三todo清单**。正确事实应来自分册01/13/25：琥珀波形B17归档（周四前）、秦老师六张显微照片（明早）、读书会两袋咖啡豆（周日）；这些事实没有预置给模型。本轮不把缺失交付当成“无需处理”。

上述283827是压窗覆盖面的本地计量。caller离线公开估算报告将25结果计为264885 tokens；该批在下一次provider请求前已被移出，**不能称为provider实际输入tokens**。原始provider请求与本地估算分开保存。

### Skill 与受限配置的独立观察

| 必验项 | 实际观察 | 结论 |
|---|---|---|
| 七Skill换窗后原生目录重建，无正文/索引重放 | PA seq148 skill-catalog；snapshot155仅sandbox、approval、窗口身份，未出现nano-used-skills；首个新窗请求七个正文标记均0。 | pass（机制） |
| 六普通工具/Notes步骤不复制正文，真正重读 | 主事故失败已冻结后，另发明确独立维护任务 `848cd6c006e7404ebee06168bb4773d1`。seq190/195/200/205/210/215为六步；期间无新增runtime snapshot，请求保持2份固定边界快照、七正文标记均0。seq220/221真实skill重读recovery-1、8651字符；之后只有该标记出现1次，其余仍0；seq225发送“维护验证完成”，turn/end231完成。 | pass；不抵销原事故失败 |
| workflow-only显式Skill首次加载及换窗后History恢复来源 | 普通Agent `e2e`，仅workflow，未开放skill/read；chat `c_uk4muc36`，session `2b9a22d0-3550-407a-b73d-694322b4d52b`。用户 `a827a2c6adb945dca38cde0702c6f43b` 显式/skill:ledger-r3。换窗24/25/27后，实际provider文件 `2026-10-21_16-58-43_736-req-anthropic_messages.json` 的正文标记为0；无nano-used-skills/turn_id。History seq52读原输入item10、seq57/58读原Skill item12，source=skill-invocation、role=system。最终消息 `cbd5967f1c864955a28dec6cc58eec7e` 正确给118、68、总186及规则标记。 | pass，原始来源没有升级为人类授权 |
| 受限配置再次换窗 | 独立重启前准备输入 `0c2ca85798f240ab9975d6a666899794`，换窗73/74/76，snapshot84仍无正文/索引。最终回复状态正确，但请求说“不要读history”，模型换窗后仍调用History，两个参数错误后自行修正。 | 无自动重放观察成立；不把这一轮指令遵循称为全pass |
| 正常重启后的真实产品恢复 | 重启前状态准备结束后，caller收紧为落报告并交回服务；reviewer尚未执行正常重启。 | **未覆盖**，不声称已完成 |
| 显式off旧摘要、再on后切窗 | 未追加新产品实验。可复用安装版原生测试5项接线证据（见下），但不是本轮真实模型off/on旅程。 | 产品旅程未覆盖 |

表中受限正文首次清空时间仅以上述准确provider文件名为准。第二轮受限任务两次History参数错误（空search、6000超过4000上限）均原样保留；未修schema或把错误藏掉。

### 复用测试与范围限制

只读取 caller 的 `/tmp/bugfix629-r3-installed-tests.log`：`pnpm exec vitest run packages/dsh-integration/tests/model-policy.test.ts` 实际1文件、5项pass。四组合测试 `keeps session effort and separates Skill catalogs from archived bodies (context windows=%s, skill callable=%s)` 覆盖新旧模式×skill可调用、manualcompact、正常shutdown/restart和configuration revision；第五项路由manual compaction。真实RuntimeClient进程配脚本模型，可证明接线/载荷/旧摘要恢复兼容，不能替代本轮真实模型任务恢复。命令中曾列不存在的agent-context.test.ts，未计作第二测试文件。

未扩大新实验；R1中依赖turn_id的结果不继承为R3有效证据。长记录分页、fork、更多身份与off/on矩阵没有在R3重新跑完，整体已由原故障FAIL阻塞。原生压力裁剪离线分析是caller后续调查，不冒充R3产品修复通过。

### 证据目录与现场归还

- 原事故时间线冻结：`/tmp/bugfix629-r3-e2e/original-incident-final-timeline.json`；原生精简证据 `534620fd-evidence.json`、`2b9a22d0-evidence.json`；均不提交原始运行数据。
- 原生日志：`/tmp/bugfix629-r3-runtime/.dsh-runtime/**/sessions/**/<session>/session.v4.jsonl.zstd`。
- PA provider目录：`/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_16-58-04_840_534620fd-450e-4756-9b6d-04ba99d3276f/`；普通Agent对应 `2026-10-21_16-58-31_693_2b9a22d0-3550-407a-b73d-694322b4d52b/`。
- 最后只读核验：PA后续observer turn4在seq249 completed；普通Agent turn2在seq102 completed。没有reviewer新请求在途。Node PID91473保持运行，未重启或清理；Notes/History/数据库和所有合成资料原样保留，操作权交还caller。
- Reference Artifacts Reviewed：R3 incident/design/runbook、交接资源、实际原生事件/provider请求/产品响应；没有读实现定位根因。上层文档和R4设计由caller维护，本轮只追加此报告。

---

## Round R4 — 接回原生压力裁剪后的同资料复验

> 2026-10-21；受验 Nano `06c7aec52d759c45dd9db82bfef0a2a052b47b6e`，插件 `ce7d551` / 不可变 `dsh-agent-context@0.3.0-rc.4`。后续 `70222b612` 为caller测试证据文档提交，不改变受验源码/依赖。
> 全新隔离实例 `/tmp/bugfix629-r4-runtime`，IM `http://127.0.0.1:58043`；Node `wt-bugfix629-r4-runtime-98383`；模型 `codexOAuth:gpt-6-astra` medium、PA Auto off、默认预算。25份资料逐文件与R3字节相同，reviewer独立比较确认；未改资料、答案、预算、安全策略或实现。

### 分范围裁决

- **R4新增范围：PASS。** 同一25份资料的单步大结果由原生裁剪处理，最新Inbox请求保留，没有不必要的强制换窗，真实模型正确交付一次。正常重启、旧摘要回退、新模式不重放正文的机制均得到实际产品证据。
- **广义“换窗后总能继续当前任务”：FAIL，残余风险仍在。** 重新启用后的一次显式new_context任务保存了新on-checkpoint，但模型换窗后读旧checkpoint，最终回复旧状态；该具体用户任务不能记为通过。R3强制换窗丢失任务的失败也不改判。
- caller按已批准R4范围确认：本轮只接回原生压力裁剪，不增加用户已撤回的恢复协议；残余旧Notes风险单列保留，不阻塞这一限定增量，但必须在交付中披露。**不能写“所有旅程PASS”或“通用换窗恢复已修好”。** 未创建外部issue、PR或部署。

### 同25份资料：原生裁剪、保留任务、单次交付

PA `pa_003c76a7af96`，chat `c_5fc89e05ee9b`，session `b4e6877b-1e6c-4f64-b878-2b41e964a3d7`。

1. 准备输入 `2c9ebc09d5be4e27af5635815871e0fb`；七个recovery Skill实际成功读取后，Notes seq59/60写“准备已完成，目前没有待处理任务”，准备回复 `25e7bff20f554b2f8b19a0db27fc19e0`，turn/end70完成。没有准备阶段日记读取。
2. 新Inbox任务 `b5ca2cdf2eea4dcd8c13be1ac0c81e11` 与R3相同文本，实际Inbox seq82/83读入。开始确认 `93013a1f65f24e788d449ba0d0a7bb2f` 不算最终清单。turn2 step4同一步25次skill调用seq92–140，原始成功结果93–141，共 **1,058,668字符**；批次后裁剪前没有新Notes写入。
3. 原生 `compaction/prune` seq143–205共32个：7份此前准备Skill、25份新分册。25新结果对应替换事件158–206，每份5159字符、合计 **128,975字符**；包含明确的 `[... tool result middle pruned ...]`。每个替换的sourceEventSeqs指回原结果，surfaceOp为replace；原记录仍保存。25新结果的原生shadowedTokenCount合计 **264885**，超过默认H225632。主任务直至turn/end216的 `compaction/end` 数量为 **0**。
4. 下一次真实provider请求 `2026-10-21_17-41-59_321-req-anthropic_messages.json` 保留新Inbox消息ID、AMBER629B用户原文、全部25个工具调用与一一对应结果。25对callId/result均完整且结果带裁剪标记；无interrupted_turn、turn_id、nano-used-skills。没有重新发用户指令、没有恢复提示、没有脚本预设模型输出。
5. 成本口径分开：批次调用前provider实际输入 **20437**（20224缓存+213新增）；裁剪后下一请求实际输入 **51293**（8704缓存+42589新增）。原始264885是本地原生计量，**没有作为一整批未裁剪内容送入该provider请求**；不能把它称为实际provider输入。
6. send_message210/result211落库 `d50178f4e7e6465fa11871f96dd008ef` completed，只有一次AMBER629B最终清单，正确给出：波形归档B17/周四前、秦老师六张显微照片/明早、读书会两袋咖啡豆/周日，并排除已完成校对。独立逐分册核对：3项事实均在各自保留头部，其余22份头部明确没有待办；中段是无行动归档。此样本不需要重读中段即可完成请求，不能据此宣称任意被裁剪中段都不重要。模型没有把裁剪标记删掉或伪造完整结果，最终没有重复清单或执行业务待办。

### 正常重启及裁剪原件恢复

主任务和普通Agent准备均completed后，按原config正常stop/start，Node **99308→1407**，`.gateway.pid`同步；未重建数据库或identity。

- 独立只读核验消息 `996ce2e93ec546f592a5322715a6671f` 明确不重发清单。PA History seq240/241读取原窗口`:initial` item93 offset0/limit1000，seq245/246读取offset22000/limit1000；后者实际返回archive01-0211等原始中段，History报告total_chars42597，role=tool、source=tool、原callId保持。这里的History规范化内容长度与原工具正文长度分别计量，不混用。
- seq250/251实际读回旧preparation Notes；seq255只交付“原件中段可读，旧记录也可读”，turn/end261完成。没有重读源Skill或文件，没有重发三todo。证明裁剪替换活动上下文后原件仍可由当前会话History分段读回，正常重启没有删除Notes/History。

### 受限Skill、旧摘要与重新启用

普通Agent仅业务 `['workflow']`，没有临时开放skill/read；chat `c_5ppvr208`，session `d7c89bcb-bfc5-4e8d-9f75-fc3eb32bd7cd`。

| 场景 | 实际证据 | 结论 |
|---|---|---|
| 显式Skill、换窗、正常重启后按原来源恢复 | 输入 `2d010a6ca37045f8ab595490170b4b12` 的/skill:ledger-r4首次正文source=skill-invocation。主动换窗34/35/37；只读checkpoint结束。正常Node重启后首个provider请求 `17-43-33_629` 中规则正文标记0、旧索引0。新任务 `aa27755db2144060b90f1fa8cca96bef` 导致History seq57搜索，62读原用户item10、67/68读原Skill item12（role=system，source=skill-invocation）。最终 `8332dd5b225d4cef8ebe301017f035ab` 正确125/78/203和规则标记。 | PASS；正文由真实History恢复，没有自动重放或扩业务权限 |
| 显式off与旧摘要兼容 | 产品API set_bundle=false；实际provider仅workflow。显式Skill准备回复“指南已收到”。公开 `/compact` 消息 `748efeaff1574c048c20f0da1e1ecd9c` 触发原生旧模式summary87/88/90，实际LLM摘要，UI消息 `03c9f699d99a4998bf1e874030554c81` 为“已压缩17项”。后续snapshot96包含nano-used-skills正文；新账本任务最终 `3a7f1c5aa7d8473a896e74d03358b93b` 正确54和规则标记。 | PASS；真实旧摘要模式，不仅是工具列表观察 |
| on后再次换窗的新模式规则 | set_bundle=true后，notes111写on-checkpoint，new_context116→compaction119/120/122。`17-47-37_155` 和 `17-47-40_144` 两个实际请求的规则正文标记和Previously used Skills均0，turn_id0；四恢复工具恢复且workflow边界不变。最终API两Agent均enabled。 | **机制PASS**；不自动恢复旧正文/索引 |
| on后这次具体任务的完成 | 用户 `1a1de8ea52764207b30165ba99cc22ee` 要求写新on-checkpoint后读它并回复“开启验证完成”。seq111确实写成功；切窗后seq126却读旧checkpoint，最终 `69297c36748e4ef1901b6cd7fce3722d` 回复“环境准备完成，等待下一条任务”。没有补救或重跑。 | **任务FAIL，R4-1**；旧笔记选择风险保留 |

R4-1：major，关系为**已知持续任务恢复风险/非本轮新增裁剪回归**；建议out-of-unit继续评估广义换窗恢复，后续方案须由用户决定。R4裁剪增量的限定范围不扩成隐藏任务提示或额外协议；本轮不宣称原任务的旧状态选择问题已解决。

### 继承、验证与剩余边界

- R3七Skill正文总量、换窗后原生目录、六普通步骤零增长、真实recovery-1重读的证据保留：该Skill生命周期路径未失效，R4又实际验证受限模式、重启与off/on。R3原事故FAIL保留为旧候选失败基线；不能借R4避免此次换窗倒推所有不可裁剪硬溢出可恢复。
- 只读取caller有效测试日志，不重复全套：`/tmp/bugfix629-r4-nano-tests.log` 显示107文件/484项pass；typecheck完成；`/tmp/bugfix629-r4-pytests.log` 显示62pass、31deselected。原生裁剪压力入口、仍超线、无服务和显式换窗等确定分支以caller版本绑定测试为准，不把脚本测试说成额外真人旅程。
- 新增范围无未解决的裁剪/配对/持久化/权限边界阻塞；**广义持续任务保证仍由R4-1与R3失败阻塞**。无新的浏览器视觉界面，按runbook使用真实Web IM调用链验收，未声称完成视觉验收。

### 证据与交接

- 本机原生归纳：`/tmp/bugfix629-r4-e2e/b4e6877b-evidence.json`、`d7c89bcb-evidence.json`，包含prune/sourceEventSeqs/surfaceOp；产品时间线 `c_5fc89e05ee9b-timeline.json`、`c_5ppvr208-timeline.json`；fixture hash对照 `fixture-hashes.json`。原生日志在runtime `.dsh-runtime/**/sessions/**/<session>/session.v4.jsonl.zstd`。
- PA实际provider目录 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_17-40-36_556_b4e6877b-1e6c-4f64-b878-2b41e964a3d7/`；普通Agent目录 `2026-10-21_17-41-14_591_d7c89bcb-bfc5-4e8d-9f75-fc3eb32bd7cd/`。
- 最后只读确认PA turn3 seq261 completed，普通Agent turn5 seq133 completed。Node1407运行，`.gateway.pid`同步；两workspace的上下文插件enabled，普通Agent保留workflow-only。所有Notes、History、数据库和资料保留；reviewer不再发测试请求，操作权归还caller统一清理。
- 只追加此报告。未改源码、设计、生产或测试；未push、创建PR或部署。上层契约归并和残余限制说明由caller按R4明确范围维护。

---

## Round R5 — Notes hint 格式对齐后的 R4-1 单轮复验

> 受验 Nano `418dd4bfb36cf6ecd81e25dc6f3ba225d2f4729e`，插件 `823a202` / `0.3.0-rc.5`。沿用原R4 runtime、普通Agent `e2e` / chat `c_5ppvr208` / session `d7c89bcb-bfc5-4e8d-9f75-fc3eb32bd7cd`；原有checkpoint/references/on-checkpoint保留。未人为改Notes、未改模型/权限、未加入恢复协议或选择提示。

### Verdict：FAIL（R4-1 未关闭）

**Notes hint 新格式与新旧排序实际生效；当前任务恢复仍失败。** reviewer从R4产品时间线取原任务，发送前逐字比较相等，仅重放一次。用户新消息 `3de51209bbd548b3a5498805ad439e15` 没有额外说明排序或提醒该读哪一份；本轮没有补救、重试或扩大实验。R4同25资料裁剪PASS保持原有范围，不重复测试、不受本轮失败改写。

| 链路 | 原始事实 |
|---|---|
| 保存当前状态 | seq142 notes.write on-checkpoint，正文“开启验证已完成，换窗后只回复开启验证完成，不读取History或其他笔记。”；成功结果143。 |
| 实际换窗 | new_context147，compaction/start150、summary151、end153。 |
| 首个postreset真实提示 | provider `2026-10-21_18-02-07_543-req-anthropic_messages.json` 确实包含下列body-free提示，on-checkpoint排首位；没有旧正文、nano-used-skills、interrupted_turn、turn_id或规则标记自动注入。 |
| 首次Notes读取 | seq157读取 **checkpoint**，而不是刚写入的on-checkpoint；结果158返回旧环境准备状态。 |
| 最终交付 | `778082a4d04c4b1e85a6d544444cc270` completed：“环境准备完成，等待下一条新任务。”预期是“开启验证完成”；turn/end164 completed。 |

实际进入模型的提示原文：

```text
Recent notes (up to 5, most-recent first):
- on-checkpoint (1 lines, 97 UTF-8 bytes)
- references (1 lines, 520 UTF-8 bytes)
- checkpoint (1 lines, 127 UTF-8 bytes)
```

提示只含相对路径、行数、UTF-8大小，没有Notes正文。它足以证明R5格式接线成功，但不能证明模型选择成功。**R4-1继续保持major任务交付失败；没有观察到该格式改动关闭旧笔记选择风险。** 此单轮不评价其他同类静态适配问题，不把31项实现测试等同于真实用户任务通过。

### 证据与运行环境交接

- `/tmp/bugfix629-r5-e2e/task.txt`：逐字匹配R4原任务；`message-id`、`timeline.json`、`native-events.json`：本轮完整产品与原生证据。
- 首postreset请求定位保存在 `first-postreset-request-path.txt`；原路径 `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_17-41-14_591_d7c89bcb-bfc5-4e8d-9f75-fc3eb32bd7cd/2026-10-21_18-02-07_543-req-anthropic_messages.json`。
- 原生日志仍在 `/tmp/bugfix629-r4-runtime/.dsh-runtime/**/sessions/**/d7c89bcb-bfc5-4e8d-9f75-fc3eb32bd7cd/session.v4.jsonl.zstd`。本轮已结束，无reviewer新请求在途。
- Node状态文件PID **4684**；reviewer未启停服务，IM保留运行。runtime `/tmp/bugfix629-r4-runtime` 的独占操作权交回caller清理；不新增实验。只提交本报告，不push、不改实现或设计。
