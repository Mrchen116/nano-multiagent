# bugfix-646 — 回归验证

> 对齐: incident.md / design.md Runbook for Reviewer
> Round 1 · full · 2026-10-23
> executed_base: e7f8249d26287dbaccde298365323c70e3cd5fc8
> validated_at: e2219e12b（实际运行源码）；启动时 HEAD fe95c0fe2 仅追加设计报告。报告期间 owner 继续修复源码，但未重启本轮服务，后续提交不冒充本轮已验版本。

## Verdict

**fail**。Highest Required Action: **fix-implementation**。3 个问题（2 major、1 minor），需要复验。未创建 GitHub issue。

Global 的真实等待、Schedule 空闲唤醒、续期、独立工作、原聊天结果交付、一小时边界与普通参数修复已观察成立；SingleThread 的必要提问/发送失败，而且停止后旧排队答复重新打开任务，阻断整体交付。不能用 Global 成功抵消 SingleThread 失败。

## 环境与证据边界

- 独立 reviewer 只读契约、公开产品 API/聊天/工作轨迹与实施证据，不读实现定位、不改源码/测试/受控配置。
- 真实 DeepSeek 默认 E2E 模型，独立审批保持；IM `http://127.0.0.1:58165`，node `wt-unit-bugfix-646-98729`，Gateway PID 99161；构建启动交接 `/tmp/nano-646-e2e-final.log`。专用登录用户 `u_9j4cbwfa`。
- 入口为 Web 同源认证聊天/Task/Agent work API，无客户端 UI 变更，viewport 不适用；未宣称 Web/iOS 视觉验收。用户能从原聊天读到任务标识、阻塞对象、检查时间和结果，而不用查看私有结语。
- Runbook `/openapi.json` 实际 404；caller 确认当前服务无 OpenAPI，按交接的现行 API schema 操作，GET agents 确认 online。旧 622341280 环境只有认证/只读请求，不算本轮业务证据。
- 可复查原始 API 摘要存于本机 `/tmp/646-evidence.jsonl`，Global work 快照 `/tmp/646-work-all.json`；以下稳定聊天、图、消息和 turn 标识写入报告，不提交 token、日志或运行数据。所有时间均 UTC（本地 +08）。
- 可信故障注入复用 `implementation.md` 的 native source/flush、拒绝与普通输入、反馈 deferContext 回归及 7 files/34 tests 记录；它们不替代下列正常真实模型旅程。未现场注入网络/持久化故障或真实拒绝。

## 旅程结果与来源

| 来源 | 独立实际观察 | 裁决 |
|---|---|---|
| incident「多项任务与合法替代」；Runbook 同图一等一做 | 直接聊天 A `c_g94q90t4`，图 `tg_0ca36100` n2 等外部文件，n3 完成；磁盘 calculation.txt 为 `17 × 23 = 391`，n3 done，n2 waiting，反馈 15:40:30 到 A。 | pass |
| incident「Agent派发与跨聊天」固定目标部分；Runbook 不同聊天最新输入 | B `c_d61ev2if` 15:40:37 输入9+8，仅收到17；A任务最终37仍发送A，消息 `cf85fad597ef469fb0e58438df0a09b4` 15:45:32。图固定 conversation_id 与交付相符。Agent派发本轮未独立造另一来源，反馈来源投影复用native测试。 | pass（实测范围如左） |
| incident「建立及更新等待」「到期与提前恢复」；Runbook 无消息外部文件 | 第一图根保持doing且模型用sleep，因此**不把第一图作为纯Schedule证据**。另建单根 `tg_eed525bc`：turn4 15:48:02 completed，n1 waiting，15:49:08真实Schedule；turn5 trigger cron/schedule，发现仍缺失，更新rev4下一次15:50:48且15:49:27 completed。15:50:19 reviewer仅落外部文件 `schedule-only.txt`，不向Global发消息；turn6 cron/schedule读取 `VERIFY-646-OMEGA`，15:51:06交付A，rev5 done，15:51:11 completed。 | pass |
| incident「到期与提前恢复」不刷屏与重估 | tg_eed525bc turn5真实检查缺失，再续90秒；A只保留15:47:55首条等待说明，到15:51:06结果前没有重复阻塞消息；私有结语说明无变化。文件必须外部提供，未自行伪造替代。 | pass |
| incident「等待和完成反馈」 | A首次说明包含已完成计算、缺失文件、目录检查、外部提供条件、实际检查时刻；结果发送先返回 held_for_revalidation，无消息发送；模型inbox读取自身Task通知后重新调用，实际sent且历史可见，没有把held当送达或回退doing。 | pass |
| incident「建立及更新等待」一小时限制；Runbook 实际API | 普通90分钟Schedule `schedule-01868d3d-fc2a-4914-b6be-d89f950098e9` 真创建（17:21:59触发）。把它关联已有waiting `tg_a653c5a4` rev3，返回 `task_wait_schedule_too_late`，rev3及原短安排不变；改原有效短Schedule成功rev4。新todo `tg_491bf290` rev1首次waiting同样拒绝、仍todo/rev1。该图验后closed。 | pass |
| incident「校验错误与运行故障」参数修复；Runbook 普通参数错误 | Global turn4 seq181 create mode:none返回invalid_arguments；seq184同轮改dag并用同request_key成功建立tg_eed525bc；后续真实waiting与完成均成功。turn1 assignee_not_member也被修正，不造成永久停跑。 | pass |
| incident「提前恢复」；Runbook 提前答复 | Global新根 `tg_67ed546f` 先15:54:36实际询问，Schedule15:58:42，waiting；15:55:20答复19后已在到期前rev4 done，结果209；15:56:33消息 `ad534f1ea8ce4497b8251c6a8c25cccf` 实际交付209，turn10 15:56:46 completed，均早于原Schedule；旧安排已删除。SingleThread独立旅程受P1/P2阻断。 | Global pass / SingleThread fail |
| incident「定时触发不重开paused」；Runbook stop旧timer | Global `tg_a653c5a4` /stop消息 `26e481a2cca24c9e9c63408a84922492` 15:52:50，图rev5 paused；模型删除其15:53:43短Schedule并说明停止；过原到期且后续新任务输入后仍paused。先前重复群图 `tg_a63981dc` 也一直paused。SingleThread旧排队输入违反停止，见P2。 | Global pass / SingleThread fail |
| incident「Global有意义私有收尾」 | Global turn4/5/6均有非空私有结语，明确已交付/无变化不公开；A没有NO_REPLY。SingleThread公开NO_REPLY见P3。 | Global pass / SingleThread fail |
| incident「拒绝与无关唤醒」「运行故障」「交付或状态操作失败」 | 不人为制造审批误判；native故障注入证据按implementation.md复用。真实产品已观察held重核验恢复。等待持久化未知与模型运行故障未现场注入，不声称真实异常矩阵全跑。 | pass（native回归+上述真实覆盖） |

## Issues

### P1 — SingleThread 等待反馈工具失败，必要提问未送达（major）

- Regression Relation: unclear；Recommended Action: fix-implementation。
- 来源：incident waiting要求请求实际送达、Runbook提前答复、SingleThread影响范围。
- 聊天 `c_ikg8xvpt`，任务 `tg_2648b411`。输入 `c2cbea212dd84ca88a68b4d8b11f050c` 15:43:22要求先询问整数，再waiting并在提前答复后计算。
- 实际：图rev3 15:44:26已waiting（Schedule15:48:10），初始Agent消息15:43:23至15:49仍running且正文空；消息工具详情显示 send_message current/聊天ID返回invalid_scope，改target仍失败，之后长时间尝试排查。没有实际公开询问就声称等待用户，关键旅程不可完成。
- 期望：SingleThread通过其正常投递路径先送达提问；必要反馈失败如实收口，不持续无效尝试。
- Action Rationale：正常专用身份无法完成需求，需owner定位执行/投递接线；reviewer不根据实现猜因。owner已接收修复，但新源码不计本轮通过。

### P2 — /stop 后旧排队答复恢复并完成已暂停Task（major）

- Regression Relation: suspected-regression；Recommended Action: fix-implementation。
- 来源：incident「定时触发不重开paused」、用户停止优先契约与Runbook stop。
- 证据顺序（同聊天/图）：15:45:29旧答复 `9d16b83a7ad4441d830b01c9687ab53b` 指定13；15:49:09 `/stop` 为 `e690c0e06d2a4a3fb29ac46cc6edef5b`；暂停系统消息 `17e57f09a1f149c3b86e253d8b61ab2e`；停止确认 `82dc5bb4447c4f8fa9cfc4157f11176a` 明确暂缓1项。Agent `6e08be6ac6364faebe8d2beff18a76a5` 也说明已paused不恢复。
- 然而15:49:37 `cd2689a35e754128b28a325e80676705` 宣称「按你的提前答复恢复Task」并给91；15:50:04图rev6 done，系统完成消息 `a824ffbdfda14c4c877d2a179873bd0c`。stop之后用户没有给任何恢复意图。
- 期望：旧答复不能越过更新的停止控制。不能把这个结果记为提前恢复成功。
- Action Rationale：直接违背用户明确停止，必须修复输入/控制顺序并用同类排队场景复验；仅测试旧timer不够。

### P3 — SingleThread 静默哨兵作为公开消息可见（minor，随P1/P2复验）

- Regression Relation: unclear；Recommended Action: fix-implementation。
- 消息 `fc19b615e7414fb7af5fa66ef1d4e363` 15:50:07正文恰为 `NO_REPLY`、delivery_status completed，出现在c_ikg8xvpt聊天历史。
- 期望保留SingleThread静默协议但不把哨兵变成用户正文；此项单独是局部体验问题，整体阻断来自P1/P2。

## 回归与收尾

- 最初群 `c_vt5bhymn` raw @名称没有立即处理；后被Global其他轮次读到并建重复图tg_a63981dc。reviewer通过合法Task API暂缓该图，主证据用直接聊天，未将入口构造/延迟误判为失败。
- 所有写入仅本轮隔离身份/Task/Schedule/临时workspace文件；没有生产或外部消息。90分钟Schedule验后已由Agent删除；Global stopped短Schedule删除；模型已完成任务的Schedule按真实状态清理。服务由caller持有，reviewer没有停栈。
- 待修后须复验SingleThread发送、必要询问、提前答复与stop旧输入优先，确认NO_REPLY不泄漏；同时保留本轮Global证据，若相应实现变化使其失效则扩大复验。

## Reference Artifacts Reviewed

AGENTS.md；docs/README.md；incident.md；design.md及Runbook；change-reviewer SKILL、handoff、regression模板；prototype-and-runbook验证平台/深度；docs/specs/gateway/task-graphs.md、docs/specs/im/task-graphs.md；implementation.md故障注入证据。未加载worker成功叙述替代正常旅程。

## 上层文档同步

- [x] SPEC.md：无需更新（跨包边界未改变）。
- [x] docs/specs/gateway/task-graphs.md、global-agent.md：需要由owner在最终验收后归并delta-spec。
- [x] AGENTS.md / CLAUDE.md：无需更新。
- [x] docs/specs/CONTRIBUTING.md：无需更新。

## Round 2 — targeted closure + main 集成复验

> validated_at / executed_base: `3a2debdd5eea8d3153fa5ae4903f67a33c9c5d92`，2026-10-24 本地时间。

**Verdict: fail**；Highest Required Action: fix-implementation。R1 P1/P2 已关闭，P3 仍复现（1 minor，但必验静默项 fail，未获得降低验收标准的授权）；needs_re_review=true。

### 运行版本与范围

第一次55324之前的53868栈被caller确认仍用旧lib，reviewer立即停止写入，所得结果全部排除，不作为本轮通过证据。caller显式 `pnpm build` 后核对产物的 root reconcile/usage 与 stop恢复补丁，再启动最终隔离IM `http://127.0.0.1:55324`、node `wt-unit-bugfix-646-27791`、Gateway27931；初始化账号 `u_8abizydw`。开始时HEAD完整hash与上述一致、工作树干净。后续owner源码修改未重启，不计入本轮。

本轮仍通过真实同源认证API、聊天历史、Global work公开轨迹，沿用默认DeepSeek与独立审批；无生产/外部消息。原始API记录 `/tmp/646-r2b-evidence.jsonl`。不改源码/配置；没有视觉变更，不做无关客户端矩阵。

保留R1未失效证据：真实一小时首次/续期拒绝及原子性、普通Schedule无期限限制、同图独立责任、普通参数同轮修复、Global跨聊天固定归属。此次变化触及SingleThread投递与停止控制，另以Global真实Schedule及stop验证main合并集成；未机械重跑未变的一小时矩阵。

### 必验项与实际结果

| 来源/目标 | 本轮证据 | 裁决 |
|---|---|---|
| R1 P1；incident必要请求实际送达、提前恢复 | SingleThread聊天 `c_ctzoho3d`，图 `tg_98000523`；先公开提问 `b19d43bbf3a14d109d960cf15bf2adc1`（completed），再waiting关联实际Schedule 16:19:19。提前答复 `a1cb5c14d5ce44eea379a0620a992787` 提供13；结果消息 `e07ef4a7c955474b901168648acc204c` 实际交付 `13×7=91`，Task done且Schedule删除，早于到期。没有invalid_scope。 | pass，P1关闭 |
| R1 P2；stop必须优先于旧排队答复 | 新图 `tg_b542f1d3` 等整数×9，先waiting。reviewer明确授权一次 `bash sleep 50` 作为可观测耗时操作；确认工具call_00_0ZRjvSuI1Kga8YPzXZbP0296状态running后，16:18:18.485发旧答复 `f39ac56b9c6f46fa892eeda13532456e`（返回pending），16:18:18.676紧接 `/stop` `8aa00ca1888c4da5b4675db900304892`。16:18:18.732图rev3 paused；停止确认 `03927c421896419395dd65bfcb84af28`。旧答复随后completed；16:18:40终态消息 `21adbd4ec23f4e46a93ebda60e9288ae` 无Task工具调用。到原Schedule 16:20:32之后图仍rev3 paused、无结果；不是只凭瞬间UI状态判定。 | pass |
| R1 P2；新的明确恢复仍可用 | 经过上述停止观察后，新输入 `69f1878a22974bc29e0630972d7ddc8b` 明确恢复同图并重申17。16:21:04消息 `26f14f41ce0e4d8ca729436e73b5302e` 交付 `17×9=153`；图rev5 done、结果保存。旧输入未恢复，新恢复意图才完成。 | pass，P2关闭 |
| main集成：Global纯Schedule外部文件恢复与固定聊天交付 | 聊天 `c_c80hbvdz`，根图 `tg_3bcfefc9`。turn1 16:15:47 completed，waiting安排16:16:59；之后reviewer仅外部写 `review646-r2b/external.txt`，内容 `R2B-SCHEDULE-VERIFIED-731`，未发Global消息。turn2明确trigger cron/schedule，16:17:13 completed；消息 `2b15c846fa3d46d49b07e1f5ec8a46b4` 在原聊天实际交付验证码，图done。独立新路径避免旧文件命中。 | pass |
| main集成：Global短stop不重开 | 另建 `tg_b67243cd` 等缺失stop.txt，Schedule16:20:19；16:19:51 `/stop` `c2c608fbe6b94ec7b7d8f992d0e3b04e`，图rev3 paused。Global turn4 task-human-control于16:20:06 completed，旧安排清理；过原定时点仍paused，无读文件或恢复结果。 | pass |
| R1 P3；SingleThread静默哨兵不公开 | 消息 `3f878d843d4846a88ed85c7a2596136e`（分配后）、`3e921be18b67402a839a0d0a4a096e81`（完成后）均正文恰为NO_REPLY且completed；stop旧答复终态 `21adbd4ec23f4e46a93ebda60e9288ae`、新恢复后的 `8cce474a967d4e58ab74a19b21666dd7` 也公开NO_REPLY。业务P1/P2修好没有消除该可见问题。 | fail，P3保留 |

### 问题与收尾

P3保持 **minor / Regression Relation unclear / fix-implementation**：真实聊天中多次公开内部哨兵，用户无法从该文本理解发生了什么。owner已收到稳定消息ID并另行修复；本轮不能以尚未重启的新源码关闭该项。下一轮可以仅复验受影响的SingleThread系统通知/静默，以及普通真实用户回复不被误吞；P1/P2和Global证据在相应实现未失效时保留。

全部测试Task为done或paused，结果与停止事实保留；所有临时Schedule由模型按真实状态完成/清理。reviewer未停caller服务。上层文档待同步结论沿用R1。

## Round 3 — P3 最窄闭环复验

> validated_at: `1fbacfe3d89f842424fa5e6a7d57707dc02971f7`；executed_base: Round 2 `3a2debdd5`。

**Verdict: pass**。Highest Required Action: pass；open issues=0；needs_re_review=false。R1 P1/P2 保持关闭，P3本轮关闭。该结论为本单元产品验收，不替代构建/CI、代码审查或生产部署。

### 版本、范围与保留证据

caller显式构建product-contracts/PA（`/tmp/nano-646-notice-build.log`）后仅重启本隔离Gateway：IM仍55324，node/owner与R2b相同，Gateway35366，16:26:45Z ready；reviewer开始时核实HEAD完整hash一致。工作树已有他人code-review.md/verification.md修改，未触碰，仅追加本报告。

本次范围为SingleThread真实Task通知独立轮次的静默终态与普通真人回复。新聊天 `c_4uqc8f03` 使用SingleThread `e2e`，避免将R2历史哨兵计为本轮失败。R2已通过的必要询问/提前恢复、stop前旧排队输入不重开及stop后新恢复、Global纯Schedule固定聊天交付与短stop，按其具体图/消息/轮次证据保留；本次窄通知投递修正不改变Task、Schedule或停止控制判据。R1一小时边界、独立责任和参数修复也保留，不重跑未变矩阵。

### 独立可观察结果

- 输入 `a782607972c846418f0273226f40d472` 要求等待整数×8，建立图 `tg_470c8c69`。分配系统消息 `c2add8a5979f4c23894769fa42467777` 于16:28:04进入聊天。
- 必要询问 `f86caf0de39a43b9ac01f9ee06609011` 于16:28:06实际送达；waiting说明 `bd92f89e19594f6fa0d78014a2ea4fa4` 于16:28:22可见，Task waiting且Schedule真实安排16:32:10。
- 分配通知处理后再次读取全新聊天：仅上述有意义消息，没有NO_REPLY，也没有空running占位。随后16:29:32真人输入 `49445b9ddb4a41758f439ea3dca3f755` 给23，并另问6+5。
- 16:29:36结果消息 `a417cd376e464a1290cb2e571cbfcee5` 实际可见，包含 `23×8=184` 与 `6+5=11`，均正确。图rev4 done，安排取消；16:29:40产生完成系统通知 `9b730b9a669140d4af4e21f331a6d5af`。
- 完成通知处理后重新读取全量消息：共7项（2条真人、2条Task系统、3条有意义Agent消息），全部completed；正文无NO_REPLY，无空消息/残留running。会话run_state=idle。普通真人问题和结果没有被静默规则吞掉。

### 独立轮次的补充宿主事实

SingleThread `/agents/e2e/work` 不可访问，不能把无公开消息直接推定为模型没执行。caller提供了只读宿主sqlite提取的原始终态事实，reviewer读取核对 `output/review646-r3-host-turns.json`：session `ac6c116e-cf6f-4bbc-8722-fbdcdc7c8610` 中，分配消息对应turn2、seq88于16:28:38.592Z completed；完成消息对应turn4、seq121于16:29:46.345Z completed，输入均为真实 `sender_type=system / system_notice.kind=task_graph`。这份宿主事实只证明独立轮次确实结束，聊天无哨兵/无空running及真人结果由reviewer直接通过产品API观察，不依赖owner成功描述。

P3状态：**closed**。必要的分配/完成独立系统轮次、流式终态和真人回复保护已覆盖。只读证据及临时产物不提交；服务未停止，最终Task done。上层文档归并仍由owner收尾，本报告不修改current spec。

## Round 4 — final sync 输入对账/终态集成

> validated_at: `defa49f2db762ab7e0e0415b4a10312f0dcaf764`（合入main `55376c111`）；baseline为R3。

**Verdict: fail**，Highest Required Action: fix-implementation。新增P4（1 minor、必验自动通知静默失败），needs_re_review=true。停止优先与新恢复正常，R3已修的纯Task通知静默仍成立；不能将混合自动来源漏判与普通真人输入混为一类。

### 版本与保留范围

caller完整build `/tmp/nano-646-final-sync-build.log`，installer `bca4d1524c5d`；本隔离Gateway44583于16:38:22Z ready，IM55324/用户/node/历史保留。reviewer开始时HEAD完整匹配且clean。新增main perf648/perf649涉及pending输入、终态缓存及fallback归属，本轮覆盖真实排队/停止/恢复与显式send、Task通知收尾；R1期限与独立责任、R2Global纯Schedule/固定聊天和stop、R3正常SingleThread询问等未失效证据保留，不机械重跑。

创建direct按产品语义返回原聊天 `c_ctzoho3d`，因此只按16:38:22后新输入、消息ID与新Task判断，未将R2历史哨兵当本轮问题。

### 实测事实

- 新图 `tg_982485a1` 等整数×6；询问 `0e57230a792440dc96ef6037bb3bfc34` 实际送达。waiting rev2，真实Schedule16:42:25。reviewer确认单次授权 `bash sleep 50` 正在running后，16:40:13.072提交答复29（`eed519dc576d4622bd52ab7f27a3edb9`，返回pending），16:40:13.297紧接 `/stop`（`2a5cd1f85f9545529bdec78f007748c9`）。16:40:13.464图rev3 paused；旧答复随后completed，16:40:22对应模型轮终态完成，16:42:18新恢复前仍rev3 paused、没有174结果。停止确认 `976c94b1f52542dcbbbde15df6f75259` 可见，停止优先 **pass**。
- 新恢复 `4fa9edd9d9c74c0a91f41b49909b4cb4` 于16:42:18明确恢复并另问10+4。16:42:42消息 `3a08161be3464dbcb9f7394e42b558d3` 交付 `29×6=174` 和 `10+4=14`，图rev5 done，正常新输入/显式send **pass**。本轮新恢复在原定时点前7秒发生，不宣称本轮再次跨timer；R2对应停止跨原timer证据保留。
- 另建普通独立图 `tg_85efeacc`，分配系统消息 `4c16c11822a24dfa9c4d34e321b18782`，结果 `01a8c51278414f52b9e84a8419681704` 正确交付17×4=68，完成系统消息 `22aa4a16636c49e5bb7862b43d6482e4`。终态idle，正常新消息与纯通知后的历史未新增NO_REPLY或空running。宿主JSON追加的new_task_notices已读取核对：该图分配为turn20 completed、完成为turn21 completed，确认不是尚未执行。被stop中断的旧轮空failed记录保留真实中断事实，不当作残留running。

### P4 — Task通知与context-only自动输入混合轮泄漏哨兵

- Severity: minor；Regression Relation: direct；Recommended Action: fix-implementation；Action Rationale: 本单元自动输入静默的真实交叉场景，须按实际来源组合处理，不能只覆盖纯单一通知。
- 新消息 `c606210a788b46da9125addeebc006fb`（16:40:13.757）正文NO_REPLY、completed，用户确实可见。
- reviewer读取caller只读宿主提取 `output/review646-r4-host-turns.json`：session `81161fc0-739d-4878-ad1c-5e5994ff7733` turn13 输入同时含真实Task系统分配消息 `e44d404b6e2b4898876c3923d1914d5c`，以及 `context_only=true / origin=task_execution` 的 task-change。轮次completed；工具只有schedule_list/delete，无send_message；投递记录confirmed NO_REPLY。此为自动输入组合，不含真人新消息，期望保持静默。
- 公开结果由reviewer直接读聊天；宿主事实只用于准确界定输入与轮次，未读实现推断。

### Side finding — 旧真人答复回合选择NO_REPLY

消息 `f1345cd538a14525a4717865fc0dd435`（16:40:22.159）同样可见NO_REPLY，但宿主turn14仅含旧真人答复 `eed519...`、无Task系统通知/自动输入、无工具或确认send。它**不是P4同因**。当前已确认范围保留普通真人输入无确认交付的原投递语义，不将系统静默规则泛化为吞真人输出；该文案对用户不友好，作为范围外模型回复体验观察保留，不以它再增加本次门禁。关键业务效果仍正确：旧答复没有越过停止。

本轮无源码/配置修改，测试Task最终done，Schedule已清理，服务未停。待P4窄修后只需复验同类混合自动输入静默和普通新回复不被吞；其余未失效结论保留。

## Round 5 — P4 混合自动来源闭环

> validated_at: `00ffba95923751b2ef04cc561158f85cb66adfa0`；executed_base: R4 `defa49f2d`；修复范围 `b0d107309..00ffba959`。

**Verdict: pass**。Highest Required Action: pass；P4 closed，open in-unit issues=0，needs_re_review=false。R4普通旧真人输入选择NO_REPLY的side finding保留原范围判断，不扩大为通用吞真人输出协议。

caller PA编译成功后Gateway53900于16:49:01Z ready；仍为隔离IM55324、同node/身份/DB。reviewer开始核实HEAD完整hash一致且clean。仅复验混合自动输入静默及独立真人回复：本次按逐输入允许类别组合判定，未改变停止、Task状态或Schedule业务语义，因此保留R4停止前旧答复不恢复、新明确恢复174、纯通知turn20/21及新任务结果68，R1–R3未失效Global/期限/询问等证据继续保留。

### 真实复现与决定性证据

- 在 `c_ctzoho3d` 新建 `tg_42e4c903` 等整数×5，询问 `82dd4812a0514a8e8b726b9b79855ad0` 实际可见，分配系统消息 `41368d1e64c6411ebc838055d60f4c3b`。真实Schedule已建、图waiting。
- 确认一次授权bash sleep40正在执行后，16:50:47发送 `/stop` `a02aa3ea1ed14faf9b411658ae870da8`；暂停通知 `320197600cfa4d46a1c26a81d69dbe49` 与停止确认 `e036eaf004f94920b8f7e7861345f908` 真实可见。
- reviewer直接读取16:49:01之后的聊天历史：混合轮收尾后无新增NO_REPLY，无空running消息，会话idle、Task paused。被用户中断的原轮保留空failed终态，不误称running残留，也没有伪造完成。
- 读取核对caller只读宿主JSON `output/review646-r5-host-turns.json`：session `81161fc0-739d-4878-ad1c-5e5994ff7733` turn23同时包含分配系统消息 `41368...`（system_notice.kind=task_graph）及 `task-change:1b071824-ebf4-4080-93d7-34e77e72ad66`（context_only/origin=task_execution）。两输入同轮completed，seq425于16:51:04.981Z turn/end；delivery23 confirmed、message_id null、content空。**已实际形成与P4相同类别的混合轮，不是未执行导致无消息。** 后续暂停通知turn25也completed且静默。
- 真人新问题 `f40e6b6556c04538a30643fa53c4bbb8` 要求保持Task暂停并问31×4；16:52:08消息 `0778337c0ec742c7850e62adc3e075e9` 正确回答124并说明保持暂停，delivery completed。宿主turn26 completed；同轮显式send可见，未吞普通回复或重复投递。最终idle、图paused。

P4由“混合自动输入公开哨兵”变为“同类真实混合轮completed且无公开占位”，并保留真人独立结果，闭环通过。没有修改实现/配置，没有操作生产；服务仍由caller持有。上层文档归并/CI/部署仍不由本产品报告替代。

## Round 6 — Stop 零唤醒与外部 Task 事实同步

> reviewed runtime: 初段 `503498e1f`；main 合并后的 `3bdcdc546`（caller 编译并重启）；报告时 HEAD `48894194b4cabffc1cfc257a063dfed729a93c01`。隔离环境 IM `127.0.0.1:65373`、node `wt-nano-multiagent-89192`，真实模型 `deepseek:deepseek-v4-flash`。时间均为 2026-10-23 UTC。

**Verdict: inconclusive（外部改派最终消费被模型服务 402 阻塞）**。已完成停止/冷恢复/人工恢复场景 pass；没有新增已证实的本单元实现缺陷。Highest Required Action: restore-test-environment；needs_re_review=true，仅余外部改派最终交付需环境恢复后复验。不得把路由触发成功称为模型完成交付。R1–R5 未失效证据保留。

### 已完成的真实产品证据

- **Global 停止不唤醒、旧答复不恢复**：群 `c_k31qjfl9`、图 `tg_89396459` 父 n1 / 子 n2 同归 e2e-global。在真实 sleep50 工具执行中，旧整数17消息 `fb6ff0104a5b4ca1a64b5d222a5c5cc2` 后紧接 stop `e01a0ecba0ff47aaa23ca37edb55f529`（19:00:09.428）。父子均 paused，停止确认 `1cfd6627d8bc403bb5fa2442abe6c63b`；父暂停通知 `a789e0e4450f44ea9c6b06e354e2d983`、子通知 `3c248169ee434ac7b52170420c257b7a` 均可见。原生主 session `32ecec36-1b0a-43cc-863e-b5451ffb88c4` 的 step/start 总数维持16、turn总数维持1，19:00:23与19:00:57两次确认，stop及同Agent父子通知未新起模型步骤。没有将 request/header 数量误当调用次数。
- **其他Agent与下一次有效输入**：19:00:57只@e2e的4+5得到消息 `b07bad733a2e484ba8d642f0d870277e` 正确9，没有唤醒Global。19:01:09新@Global问2+8且不恢复，原生turn2 seq114包含可信 `task-stop-notice`；消息 `7f17977823284b20bf62110a26b973fc` 回答10并核对父子paused，旧17没有重新承担责任。
- **SingleThread 真实 waiting、stop 与同Agent父子通知不唤醒**：合并版中 peer群 `c_srk0ejg6`、图 `tg_35dc6808` 的父子已通过真实 Schedule `schedule-3e91e0ea-32e5-40b1-96ed-762c522eb68b` 进入waiting。真实sleep50中，旧13消息 `65b7b034ea7c45069b899399402626d4` 后stop `3f9ed7e880d94a938caec3ea3cee515c`（19:05:22.805）；两项paused、停止确认 `05bfb39128e44f1f92e3541850720941`。主session `f4bd74aa-3b20-4661-b73f-8ce47b9aed15` 的step总数24在超过45秒观察内不增加，idle。不存在“先唤醒再靠模型选择静默”的假通过。
- **真人从 Task API 明确恢复**：19:05:33.973用户对 `tg_89396459/n2` 发出正常 Task apply，将其恢复doing并明确计算17×7。19:05:43.989消息 `90104f737794462e82deea3625bfe323` 实际交付119，n2 done、父n1仍paused。证明停工事实没有挡住后来的明确人工恢复。本轮通过的是Web使用的同一Task mutation API；Chrome Task页能见paused节点，但节点详情按钮未展开，未宣称完成浏览器点击恢复路径，caller已明确接受API验收。
- **冷恢复首个真实模型步骤消费停工事实和当前快照**：caller正常重启Gateway，保留IM、原生DB和绑定；没有手工改持久化状态。peer停工notice此前未消费。19:08:20.747原有真实Schedule到期（早于19:08:22普通输入），原生turn3首step seq193在19:08:20.875开始；seq194为停工notice（actor、原stop ID、19:05:22、paused2），seq195为真实schedule reminder，seq196为当前 `quiescent / tasks:[]` 快照。因此这是有效Schedule唤醒后的冷恢复消费，不能称为stop自行唤醒。新问题消息 `58ab52b5b34140cb949c0f16d6f90f6a` 后回复 `96967df8583c488a95bb0f8e4d2bc8c2` 正确11，父子保持paused、旧13没有恢复。
- **群解散移除现有责任**：独立群 `c_va9xocxd`、doing根 `tg_42762148/n1` 于19:11:35.108由用户解散，API确认closed、dissolved_at存在、can_write=false。原生Global seq518在19:11:35.390追加nano-system/task-change，明确 `removed:["tg_42762148/n1"], doing:[], waiting:[]`。这是运行中消费者实际收到移除事实，不仅是DB/callback断言。后续要求确认的普通消息 `df0d159be6624f6aa47fe55f4dbe91f3` 未得到成功回复，受下述余额阻塞，故不额外声称最终回答或完整收尾已验证。

### 环境阻塞与验收边界

- **外部改派待复验**：用户API创建 `tg_7ffac859`，19:11:46.476将负责人由Global改为e2e并设doing，目标为实际交付13×3。改派系统消息 `589eaaf6f7fa4b0698100f3a06a54624` completed，确实触发新负责人；但公开失败消息 `badda266c36140c9a642ded3387cda71` 返回 `402 Insufficient Balance`，request_id `9f243acb-8869-4158-a895-11b51e78a833`。任务仍doing，没有39交付，因此该项 inconclusive；不因模型账户余额失败虚构实现问题，也不更换模型绕过已约定联调条件。
- 初始夹具schedule allowlist错误导致Global旧session无schedule工具；caller修正为六个真实schedule工具后，新peer场景成功建立Schedule。Global旧session仍无该工具且探索多轮，其等待配置不算本轮有效waiting验收；停止与人工恢复证据有效。群解散后停止扩展探索，没有把该夹具问题增列本单元缺陷。中途caller维护重启打断初次颜色任务输入，不计产品失败。
- 证据为reviewer直接操作产品API、Chrome可见状态与原生SQLite只读事件；没有以模型thinking或源码推断行为。原始API流水 `/tmp/646-stop-sync-evidence.jsonl`，筛选原生事件 `/tmp/646-r6-native-evidence.json`，原生DB在隔离worktree `.dsh-runtime/wt-nano-multiagent-89192/node.sqlite3`。这些本地产物不提交。未改源码、测试或运行配置；服务由caller持有。最终余额阻塞后不再新增模型调用；剩余doing测试图与测试服务交回caller清理。
