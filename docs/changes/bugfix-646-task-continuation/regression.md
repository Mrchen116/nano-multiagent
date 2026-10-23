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
