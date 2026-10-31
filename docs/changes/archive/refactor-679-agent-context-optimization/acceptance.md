# refactor-679 — 独立产品验收

> 最新增量结论：Round child-forget-2 **PASS**，实际运行 `fea88c187`。普通子、fork 完整请求与真实缓存、自然语言遗忘及 Dreaming 单写者旅程通过；CF1 摘要内部边界头已定向关闭。详见文末；此前轮次保留为历史。

## 最终结论（2026-10-31，Round final-4）

**PASS**；validated_at: `6881952b9`；executed_base: `4b27d962c1cc09a27a567619bd5cabc3db2ee934`。5个历史major均已独立复验关闭，当前0 blocking、0 major、0 minor；highest_required_action: none。历史失败轮次保留在后文，不能视为当前结论。

范围：同一固定隔离daily栈，Web 1280×720、真实P/E/Q sol high与PA astra medium；结合代表性真实模型连续旅程、原生消费证据及可信受控机制回归。无iOS改动，不重复iOS；没有原型must-match。未测试生产，未部署；不宣称每个机制分支都重复跑过自治真模型。

| Finding | 当前状态与决定性证据 |
|---|---|
| PA679-1 最新Task读取阻断 | closed；final-2读取revision2，原群真实交付4b63d03a…并done |
| PA679-2 删除无群通知 | closed；final-3删除tg_a75c74cd/n3，群15:30显示任务名、删除及入口失效，消息6a287f248d024f73a7cb2221b056b4a9 |
| PA679-3 自删Schedule缺具体D7 | closed；final-3 native seq588在下一模型步前消费两Task的具体missing列表，随后分别重建有效安排 |
| PA679-4 公开撤销事实过于泛化 | closed；final-4群15:39明确E的身份及两个受影响任务链接；截图acceptance-visible-revocation-fixed.png；失权主体原生seq114仅保留最小撤销，无标题正文 |
| PA679-5 恢复后误用旧撤销 | closed；final-4停用E期间将n2改为1024×576/竹叶63，启用后相同只读请求，E主动查当前conversation权限→get revision8→真实私聊94e8904e429a4ff19fe7ef64b04f6299正确回答；主/子任务仍todo，无开工 |

整体体验：任务变化在所属聊天可辨认并有入口；长期事项经过等待、用户更正及跨聊天补充后回到固定聊天交付。两项等待独立修复；/stop即时暂停，补全信息只记录不擅自重启。PA只向主人交付，来源排除后不继续读取。撤销事实能让合法成员辨认受影响对象，同时不向失权主体送出新内容；恢复后能基于当前工具权限核对最新要求，不要求用户重复贴正文。

| R | 最终判定 | 真模型/真实产品证据与机制边界 |
|---|---|---|
| R1 初始身份/环境/Skill | pass | PA/P/E/Q普通问答；重启后继续；实际HTTP DOCUMENT/LEGACY capture独立检查装配顺序、persona、目录和工具。capture响应受控，不冒充线上代理wire |
| R2 真实Task变化及恢复 | pass | Web创建/正文/改派/状态/双端依赖/删除/资格撤销均观察；E停用期间更新后恢复读取最新rev8。真正网络离线/分页重放/失权队列边界沿用41pass机制回归，停用不等同断网 |
| R3 不重复及持续推进 | pass | P最新正文交付done、公告done后重启不重复；内部对象/消费ACK恢复沿用task-context-originals、task-context-sync与context-order-provider已通过机制回归，不伪称UI重建等于内部重建 |
| R4 Schedule与Task独立提醒 | pass | PA无Task的用户删除；P waiting用户删除；P两项waiting自删后具体D7及独立安排。到期/检查失败等沿用18pass既有矩阵与后续修正后的running-repair测试 |
| R5 固定聊天与发送状态 | pass | 公告在私聊补充后回固定群，仅一份；无变化等待不重复。unknown/failed状态保留和确认去重沿用task-feedback、PA external/store受控回归；未主动制造真实平台故障，不宣称自治模型在每种未知发送条件的可靠性 |
| R6 停止/拒绝/观察/失权 | pass | /stop两Task paused，后续信息仅记录且取消Schedule；PA来源排除、Q撤销拒读、E恢复权限核对。审批拒绝不绕过且独立工作继续沿用task-execution三种scope受控回归 |

### 最终 Scenario 索引

以下来源均为motivation同名Scenario，覆盖粒度按runbook“代表性真模型+机制回归”执行，而非每项重复全平台全模型：首次接收用户请求=R1 pass；内部对象重建但任务事实未变=R3 pass（机制）；正文、责任或关系发生变化=R2 pass；相关Agent离线后恢复=R2 pass（真实停用恢复+网络机制）；没有本人进行中任务时收到消息=R1/R6 pass；进行中任务跨轮次推进=R3 pass；跨聊天等待或提交成果=R5 pass；已交付、等待续期或发送未确认=R5 pass（确认/续期真实、未知机制）；确需等待外部条件=R4 pass；用户删除未关联Task的Schedule=R4 pass；用户删除waiting关联Schedule=R4 pass；Agent自己删除waiting关联Schedule=R4 pass；多项waiting失去有效安排=R4 pass；暂停或拒绝后收到新消息=R6 pass（停止真实、拒绝机制）；新会话或正常换窗后继续工作=R1/R3 pass（重启真实、native window/summary机制）。

### final-4 证据与收尾

- 运行版本由caller交接IM79545/Node79551/runtime79576；reviewer现场核对HEAD 6881952b9和health200后从Web完成复验。
- E session `4835bdcf-8437-4035-914b-dbf1f944daff`：seq114最小撤销；seq127 current conversation info；seq134最新Task get；seq139真实send；seq145 completed。`output/refactor-679/acceptance-final4-engineering-native.jsonl`。
- `acceptance-final4-task.json`证明revision8且n1/n2 todo；截图`acceptance-restored-current-permission.png`、`acceptance-visible-revocation-fixed.png`。
- reviewer未启动服务；现有隔离栈归caller集中清理。无源码/测试修改，报告由caller提交；原始日志/截图仅保留本地、不提交。
- current specs最终归并与archive仍属caller交付步骤；本验收PASS不等于已完成归并/合入/部署。

## Round final-1（2026-10-31）

- mode: full；revalidation_mode: full。
- executed_base: `4b27d962c1cc09a27a567619bd5cabc3db2ee934`。
- validated_at: `b610b02b56bb3760448208dfd567f1fba8034e51`；开始时 HEAD 与此一致、git status clean。
- 环境：`/tmp/nano-refactor679-daily/.e2e-daily.json`；IM `http://127.0.0.1:64012`；测试 nano；node `wt-nano-refactor679-daily-89152`。实际 IM/Node 进程命令指向本 worktree 的 lib；P/E/Q sol high、PA astra medium、Codex 审核，未降级模型。
- 入口：真实 Web，1280×720。无 iOS 改动，未重复 iOS；无新增原型 must-match，Reference Artifacts Reviewed: N/A。
- 方法：读首文档、设计 runbook、current Task/PA spec，独立操作浏览器；只读产品 SQLite、原生 session 取证，未读实现定位根因。报告由 caller 集中提交。

### Verdict

**fail**；highest_required_action: **fix-implementation**；2 major，0 minor。已发现决定性失败，后续关联等待与跨聊天交付不能以无效前置硬做 PASS。

### 用户旅程体验

PA 首次普通问答在约51秒后真实交付三条有针对性的建议，未创建 Task。任务在群内的创建、正文更新、改派及暂停消息表达清楚，链接与 @ 可操作，用户能辨认谁负责及发生什么变化。Task 编辑表单保存后详情显示最新正文，群通知明确“请读取最新正文”。但 P 的真实读取失败，最终要求用户重复粘贴已经保存的正文，无法完成目标；任务删除后又没有对应群消息，协作成员无法从原聊天知晓任务已消失。因此整体不可交付。

PA 独立提醒由真实模型创建；在配置页点击 Delete 后显示 No scheduled tasks，随后原生消费记录及模型私有结尾确认删除，不重建提醒。后续普通建议仍能独立交付。

### 问题清单

| ID | Severity / Relation | 期望与实际 | 复现与证据 | Action / rationale |
|---|---|---|---|---|
| PA679-1 | major / suspected-regression | P 应读取最新 Task 正文并继续；实际 task_graph.get 返回 `Current Task facts or source permissions are unavailable; revalidate before using Task tools.`，随后要求用户把正文贴到群里，任务仍 doing | 群 `c_5bq0fht5` 创建 `tg_1f445186/n1` todo→更新正文并设 doing；07:08:41Z call `call_a5fd137485274ba3ad793acf7cb000bc`；session `519271cf-6e1e-432f-910e-d90e015e2d6f`；公开回执 `2b73627d6de84900b0c7d2415211628f`；`output/refactor-679/acceptance-task-blocked.png` | fix-implementation；核心继续推进路径阻断，不能靠用户重复输入绕过 |
| PA679-2 | major / suspected-regression | Task 删除应在所属聊天说明业务变化并通知相关者；实际删除成功、列表消失，群没有删除通知 | 创建 `tg_04945503/n1` 指派 E，再改 Q+paused；Web More→Delete→Delete 1 tasks；07:12Z 后 task_graphs 不含该图，messages 最后一条对应系统通知仍07:11:32Z改派/暂缓；`output/refactor-679/acceptance-delete-no-notice.png` | fix-implementation；删除事实未交付协作者 |

### Scenario 覆盖

来源均为 `motivation.md` 的同名 Scenario；R 映射见 design M1。证据路径相对仓库；未完成项全部明确保留。

| Scenario | 实际旅程及证据 | 结论 |
|---|---|---|
| 首次接收用户请求 | PA 问答真实交付 `19801a7e090c4cd69eb5bfa4a5dbaed6`；`acceptance-pa-answer.png`；P 正常问题被随后 Task 处理占据，完整首次上下文/provider 尚缺 | inconclusive |
| 内部对象重建但任务事实未变 | 本轮未执行重建；不得用普通刷新替代 | inconclusive |
| 正文、责任或关系发生变化 | 创建/正文/状态/改派已见清楚通知，`acceptance-task-update.png`、`acceptance-reassign-pause.png`；删除无通知（PA679-2）；关系/资格未覆盖 | fail |
| 相关 Agent 离线后恢复 | 尚未执行离线重放 | inconclusive |
| 没有本人进行中任务时收到消息 | PA 普通问答与后续建议各一条真实回执；唯一创建 Task 均来自本 reviewer 的 Web 操作；PA 观察群未代表主人回复。但普通 P 问答未独立完成 | inconclusive |
| 进行中任务跨轮次推进 | 最新正文已存且通知已消费，真实读取失败 PA679-1 | fail |
| 跨聊天等待或提交成果 | Task 读取失败，未形成可交付前置 | inconclusive |
| 已交付、等待续期或发送未确认 | 未形成 Task 等待/交付；不得以 PA 问答单次发送代替 | inconclusive |
| 确需等待外部条件 | 未形成有效 waiting Task | inconclusive |
| 用户删除未关联 Task 的 Schedule | PA 07:09:47Z 创建 `schedule-c3147b6f-a723-4bd4-8c96-b8655bdfe625`；Web 07:10:35Z删除；PA 原生 seq75 同一 schedule-deleted 输入，07:11:02Z明确不再提醒/不重建；无新 Task | pass |
| 用户删除 waiting Task 的关联 Schedule | Task 工具受阻，无有效前置 | inconclusive |
| Agent 自己删除 waiting Task 的关联 Schedule | 同上 | inconclusive |
| 多项 waiting Task 失去有效关联安排 | 同上 | inconclusive |
| 任务暂停或动作被拒绝后又收到新消息 | todo→paused 的 Q 无开工，但未完成 /stop、拒绝、失权完整边界 | inconclusive |
| 新会话或正常换窗后继续工作 | 未执行换窗/恢复 | inconclusive |

### 证据与边界

- 浏览器截图：`output/refactor-679/acceptance-{pa-answer,task-update,task-blocked,reassign-pause,delete-no-notice}.png`。
- 原始本地产品事实：`output/refactor-679/acceptance-final-1-observations.json`；原生会话：`acceptance-final-1-pa-native.jsonl`、`acceptance-final-1-product-native.jsonl`。仅本地保存、不提交原始日志。
- PA 主 session `94432051-cf73-4c1f-ba17-236875cdc27b`；P 主 session `519271cf-6e1e-432f-910e-d90e015e2d6f`。原生消费证明不是最终 provider payload；交接的 `/Users/czj/Repos/LLM_PROXY/logs/session` 未找到这两个 session，因此 provider wire evidence 保留缺口。
- 启动阶段 gateway.log 的 agent_disabled 不作为本轮模型故障：PA 已实际成功回答，不能由旧启动日志归因。
- 07:12Z caller 宣布将修复并只重启本隔离 Node，reviewer 暂停新写入；此轮证据冻结在上述 SHA，修复后须另加 round，不覆盖失败。

### 上层文档同步

- SPEC.md：无需新增架构更新。
- docs/specs/gateway 与 im Task/能力：需要 caller 在最终实现通过后归并 delta，当前不判已完成。
- AGENTS.md / CLAUDE.md：无需更新。
- docs/specs/CONTRIBUTING.md：无需更新。

## Round final-2（2026-10-31，修复后连续旅程）

- validated_at: `36cef9604935754e1da0a11b0616e194a0d56523`；executed_base 不变。
- 同一 IM 数据与身份，caller 只重启隔离 Node。模式：前轮失败复验并继续 full 未覆盖场景；未声称重验未触及平台。
- 暂定 Verdict: **fail**，PA679-1 closed；PA679-2 retained open；新增 PA679-3 major。其余前轮 inconclusive 在未明确关闭前保留。

### 连贯旅程与结果

1. Node 恢复后 P 无需正文补贴，07:13:36Z 成功读取原 `tg_1f445186` revision2，核验25字欢迎文案，07:13:59Z送到原群（`4b63d03ac4df4bd297bf41783d3f2b9f`），07:14:14Z登记 done/revision3。用户15:14的“继续”消息晚于实际首次交付，不是完成前置；未重复相同文案。PA679-1 **closed**。证据 `acceptance-restored-delivery.png`、final-2 product native 与 observations。
2. 在原群请求建立并跟进“轻记待办发布公告”，缺发布日期，半小时检查。P 创建 `tg_2f2003fb/n1`，先公开明确范围与阻塞（`f18bc901a6a341cc8c3a793ee7162a87`），核对已有资料后创建 `schedule-85e0bcc0-5442-4fb8-9274-b86747a9f5f9`，07:15:59Z进入 waiting，下一检查07:45:32Z。实际等待安排和固定群说明均成立。
3. Web 删除上述安排（07:16:44Z）：原生 seq221 为独立 Schedule 用户删除事实，seq222 为具体 Task repair reminder，含 graph/node/title/relative_url/reason=missing。P 重读 Task/群后确认未完成且日期仍缺，07:17:11Z建 `schedule-16328335-e698-4181-97b3-3dc50444339a`，07:17:32Z更新 waiting/revision3；不重复原群的无变化等待说明。这关闭“用户删除 waiting Task 的关联 Schedule”。
4. 在新建 P 私聊 `c_drjzoxzi` 请求删旧检查并改20分钟后，P 07:18:23Z确实执行 schedule_delete，07:18:35Z建 `schedule-11190938-de89-4842-a0c2-5e9c0f101b66`，更新 Task/revision4 并在固定群报告改变后的复查时间。行为修复完成，但具体 D7 消费时机未满足，见 PA679-3。
5. 在 P 私聊确认最终日期2026年11月3日；P 获取后转doing，07:20:55Z将最终公告送到固定群 `c_5bq0fht5`（`17cce640b28844548c6d44c5bf3ce20c`），没有把成果误发私聊。截图 `acceptance-cross-chat-delivery.png`。07:21:44Z清理旧安排成功；最终done及收尾重复性继续观察。
6. PA 收到私人查询，实际读取获准群来源，只向主人私聊汇报负责人/缺失日期，附原始消息链接（`d132c4631e394831aadfaa82eeac0de4`），未代发群消息/改Task。随后从设置UI排除“研发日常”，再在群发布新的合成代号“青桔47”，PA面对查询明确不能读取排除来源（`7b40d74358654ea6a89eb983b39e962e`），原生session不含该新代号，pa_delegated_messages=0。截图 `acceptance-pa-private-observation.png`、`acceptance-pa-source-excluded.png`。保留已读历史与禁止新来源的边界清楚，未声称历史被抹除。

### 新问题

| ID | Severity / Relation | 实际事实与判据 | Evidence | Action |
|---|---|---|---|---|
| PA679-3 | major / direct | Agent 自删 waiting Task 关联 Schedule 后，repair 仅排到 next-turn，下一步模型能先新建/重绑有效安排，尚未消费列出具体任务的 D7。行为主动修复不能替代 motivation“Agent 自己删除…”要求收到具体 Task reminder | final-2 product native seq292：`task-wait-repair`、`target=next-turn`、文本仅“Recheck the current waiting Tasks and their linked Schedules.”；随后 schedule_create 与 task_graph.apply，未见该删除的具体repairs进入user/message。自删call `call_cc72aa59610f4add854954bc38d76839` | fix-implementation；caller已确认时机缺口，待新版本复验 |

### 覆盖更新（其余继承 final-1 的未通过状态）

| Scenario | 结论更新 | 限制 |
|---|---|---|
| 进行中任务跨轮次推进 | pass | 恢复后读取最新正文→核验→群交付→done，后续公告旅程继续覆盖 |
| 确需等待外部条件 | pass | 原群有实质等待说明，Task引用真实半小时安排 |
| 用户删除 waiting Task 的关联 Schedule | pass | 独立删除事实与具体Task repair同一步实际消费，再核查修复 |
| Agent 自己删除 waiting Task 的关联 Schedule | fail | PA679-3，不能仅凭最终修复放行 |
| 跨聊天等待或提交成果 | pass（已观察等待修改与成果送达） | Task最终done与重复性继续观察 |
| 没有本人进行中任务时收到消息 | pass（普通问答与PA观察） | P/E/Q真实普通问答均有产品回执，无问答自动建Task；仅reviewer明确创建和后续明确建任务请求产生Task；PA私下观察不代表主人 |
| 首次接收用户请求 | inconclusive | 真实回答与Skill恢复已见；最终provider payload证据尚缺，未以native装配替代 |
| 正文、责任或关系发生变化 | fail | PA679-2 retained；关系/成员撤销其他分支未完整覆盖 |
| 已交付、等待续期或发送未确认 | inconclusive | 无变化等待修复未重复公开说明；failed/unknown发送分支未实测 |
| 任务暂停或动作被拒绝后又收到新消息 | inconclusive | PA观察与来源排除通过，/stop和动作拒绝边界仍待证据 |

### 临时环境增量

- P 私聊新增 `c_drjzoxzi`；公告 Task `tg_2f2003fb`；各关联Schedule沿真实模型创建/删除。
- PA 的“研发日常”来源排除已开启，其他配置不变；用于失权边界验收，未触及生产。
- 所有本地证据在 `output/refactor-679/acceptance-final-2-*`；未提交日志、数据库、截图。

### final-2 收尾核验

07:22Z 公告 Task 已 done/revision6；07:22:21Z P turn completed，私有结尾明确当前无新消息、无需公开回复。固定群最终公告正文只出现一次，私聊仅有安排更正确认，无公告副本。更新后的 final-2 observations/native 已保存；07:22Z通知 caller 当前连续旅程完成，可重启同一隔离栈。

## Round final-3（2026-10-31，6dc940cf6）

- validated_at: `6dc940cf6`；沿用固定隔离模板与真实 Web 入口。
- PA679-2 **closed**：Web 删除 `tg_a75c74cd/n3` 后，原群15:30明确显示“检查图片文案，已删除，原入口已失效”，相关 E 与 Q 均在通知内容中。当前成员可看见业务变化。
- PA679-3 **closed**：P 在私聊按用户要求同时删除两项 waiting 的安排。native seq577/581 是两个 schedule_delete；seq588 在下一模型步之前消费具体 D7，列明 `tg_ee46be2d/n1` 与 `tg_8b73c73a/n1`、各自旧 Schedule、missing 原因；seq590 才开始新建两个检查。随后各 Task revision3 分别绑定新 Schedule，15:31 私聊真实确认，保留各自独立的日期/地点条件。不能只以另一条seq589泛化提示判缺失，具体列表已由同批seq588承载。
- 多项 waiting Task 失去有效安排：**pass**，同上，两个任务均有独立修复和下一检查；证据 `output/refactor-679/acceptance-final3-product-native.jsonl`、`acceptance-multiple-waiting.png`。
- 依赖变化：Web 为 `tg_a75c74cd/n2`→`n3` 添加依赖，群内双端通知均显示方向、两任务链接与 E/Q 相关者。随后删除依赖也显示双端变化；`acceptance-dependency-notice.png`。
- 成员撤销：Q 移出研发日常后收到最小撤销事实，后续 Task 新增“银杏82”时 Q 私聊拒绝读取，未声称仍可访问。native `acceptance-final3-quality-native.jsonl`；`acceptance-member-revoked.png`。
- **PA679-4 major / direct / fix-implementation**：撤销时原群公开消息仅“任务处理资格已撤销；此通知不授予读取原聊天或继续原任务的权限”，未明确 Q 与受影响任务；合法协作者不能由公开消息辨认业务变化。caller已修复，待新运行版本独立复验。
- **PA679-5 major / direct / fix-implementation**：Disable E→修改 `tg_a75c74cd/n2` 为960×540/松果19→Enable E；E 私聊查询仍依据历史撤销拒绝最新只读核对。此路径为停用恢复，不冒充断网重连；不能据此认定所有真实离线重放通过。证据 `acceptance-final3-offline-update.json`、`acceptance-final3-engineering-native.jsonl`（若caller导出）、原私聊15:30回执。caller正在修复，待复验。
- 重启保留：此前公告 `tg_2f2003fb` 仍done/revision6，原群最终公告仍仅1条；这是恢复无重复的实测子集，不等于完整新会话/换窗机制证据。

本轮完整 full verdict 暂保留 **fail**：PA679-4/5 未关闭，未实测机制项继续沿前轮缺口，不能按轮次降低标准。

### final-3 /stop 连续旅程

07:33:50Z 在 P 私聊真实发送 `/stop`，即时回执 `8d07476191324b34842b58a8acef5be3` 确认停止并暂缓2项；两Task均 paused/revision4。随后补充11月8日/线上会议室并明确保持暂停（`8bfda7b45fe844e79828fecd2a6f8daa`），P重读最新Task，删除两个残留检查，只记录补充要求，两Task保持paused/revision5。15:35真实回执 `3f5cb8cd717545b286c1961ffd7a37e6` 明确“不因信息补齐自动继续，等明确恢复”，未发邀请/须知成稿，未重建Schedule。

“任务暂停或动作被拒绝后又收到新消息”的 **/stop+后续消息子场景 pass**；本轮未独立制造工具审批拒绝，不能声称该分支实测。证据：`output/refactor-679/acceptance-stop-keeps-paused.png`、`acceptance-final3-stop-product-native.jsonl`、`acceptance-final3-stop-observations.json`。真实模型保留读取并记录新要求的能力，同时没有推进已暂停工作。

### 独立检查的 provider 序列化机制证据

caller交接的 `/tmp/nano-refactor679-daily/provider-wire-DOCUMENT.json`（3请求）和 `provider-wire-LEGACY.json`（4请求）经 reviewer 实际读取：原始HTTP请求body含稳定system/persona、runtime与Skill目录、human输入和本轮Task事实；system保留用户persona。当前模式工具包含history/new_context/notes，legacy模式没有这些禁用工具。DOCUMENT后续请求重建runtime及完整变更Skill目录；LEGACY明确summary请求后，下一请求含自动checkpoint、刷新runtime和新目录；session/root均为wire-session。对应 `recovery-wire.log` 2 pass、`final-fix-focused.log` 41 pass 已核对。

这是受控模型响应下真实adapter出站HTTP序列化，不是线上模型代理抓包；实际模型行为另由前述完整产品旅程支撑。由此“首次接收用户请求”和“新会话或正常换窗后继续工作”的装配/恢复机制缺口可关闭；实际模型已在重启后继续原任务并完成交付，PA/P/E/Q首次普通问答成立。没有声称每个模式、每次换窗均做了自治真模型重复试验。

## Round followup-1（2026-10-31，用户初始上下文修复 delta）

**PASS**；validated_at: `326dac00ed5d78daaa6464032a94a24daba5d794`；executed_base: `5e5d3fcc801c6ad766910b126a10ee25076627a9`。0 blocking、0 major、0 minor；highest_required_action: none。此轮只复验 Round 8 设计增量；原未受影响场景 retained，不重做全部 Task 旅程。首次请求运行于该提交前的冻结同源实现；caller确认提交仅冻结已运行代码，并将同bytes rc.7包改为不可变release URL。未把后提交时间冒充首次请求时间。

### 隔离环境与入口

- 新环境 `/tmp/nano-refactor679-context/.e2e-daily.json`，IM `http://127.0.0.1:51966`，node `wt-nano-refactor679-context-32788`；现场核对IM33366/Node33432命令指向本worktree lib及新config。原用户预览 `/tmp/nano-refactor679-daily:64012` 未修改或关闭。
- Global `daily-product` / `P · 产品与体验`，真实 `codexOAuth:gpt-6.1-sol` high；PA `pa_3e16eef0a4b1` / `PA · 个人助手`，真实 `codexOAuth:gpt-6-astra` medium。正常Codex审核；未降级。
- 新环境无seed消息；发送前Global原生session仅配置事件、没有request/header。首轮从客户端同款HTTP登录/消息API发出，按runbook许可，浏览器查看实际结果。Chrome页面fill可操作但此次click/press未推进，未以点击成功冒充发送；API记录与UI最终内容一致。
- 真实公开回复指IM聊天可见交付，包括PA主人私聊；没有发送到公网、生产、外部人员或其他账号。

### 完整输入检查（非关键词抽查）

独立读完Global与PA完整System/runtime/Skill目录/触发输入，以及全部23/38个工具的描述和参数；相同工具/目录以完整相等比较去重阅读。保存完整首轮JSON、可读文本、工具JSON和SHA256 inventory，未只保存截图片段。

| 检查项 | Global | PA |
|---|---|---|
| 产品身份 | System明确 `Your Agent name: "P · 产品与体验"` 与 `Your Agent ID: "daily-product"`；自定义中文指导完整保留 | System明确 `PA · 个人助手` 与 `pa_3e16eef0a4b1`；默认PA职责、代表主人边界保留 |
| 原生与窗口 | `You are an AI agent powered by DeepSeek Harness.` 开场及 `Current runtime context. This snapshot supersedes earlier runtime-context snapshots.` 保留；context_window只有窗口ID，无UUID名称行 | 同左；UUID仅用于窗口身份，没有冒充产品显示名 |
| Task限制 | 无当前Task/待消费Task原文，因此未出现verification unavailable/D9泛化警告；Task工具与正常权限边界仍在 | 同左；未让普通问答背负不存在Task的故障提示 |
| Memory首轮 | 绝对memory目录、绝对`MEMORY.md`、one-page key memory包装及完整初始Expert memory正文；明确详细记忆从此目录检索 | 首次source gen1相对初始化basis0失效，明确`entry_basis_stale`并禁止采用旧副本，保留绝对目录；**首次未注入有效正文，不能声称此项首轮已验** |
| 常驻噪声 | 无backup navigation、无前台缺工具清单 | 无常驻backup导航或前台缺工具警告；正式维护status按需返回backupRoot不属于常驻注入 |
| 来源/权限/工具 | inbox/conversations/send_message分工与来源sender一致；无send_user_message；read存在，按需读取项目文档；Memory唯一写者边界未因普通write/edit可用而放松 | participant与observer分明；`is_owner`与代发授权分开；send_user_message/personal_sources/memory_maintenance存在且有原请求限制；仅以send_message回复主人，没有代发或修改来源 |

Global首轮System约17,982字符（含结构计数），4条可见消息，23工具；PA System约25,482字符，4条可见消息，38工具。首轮顺序均为System → runtime snapshot → Skill catalog → Inbox系统唤醒；真人正文并不伪装为直接system，而是在真实inbox read工具结果（两者seq22）带sender/时间/聊天归属进入下一步。此顺序符合Global持久Inbox模式。Global检查群成员后读brief/feedback/checklist，PA按owner participant私聊处理，观察群没有变成PA任务。

### 真模型连续结果

1. **Global首轮**：09:32:58Z用户消息`63c40826c64e4bb8af7f64a20d82d972`，自然请求自我介绍和项目欢迎页两项体验建议，并明确不建Task/安排。session `c1413933-2d32-4574-8388-53c93d346fd3`：首轮seq9–14；inbox check→read与conversation info→读取三个项目文档→send_message。09:33:26Z群真实回执`518cccb362fd4c79aa66777f4b901a8e`介绍“我是P”，建议快速开始记录与安心继续处理，内容对应实际资料；seq35 sent、seq40 completed。没有把私有结束语当交付。
2. **PA首轮**：09:32:58Z用户消息`c917fd70ba2047bbbc86d5755187ce44`，自然请求自我介绍和20分钟整理明日清单三步建议，仅此私聊、不设提醒/联系别人。session `cbb7f3b2-dc1e-4e2a-b0e4-aab22026de9d`：首轮seq9–14；inbox check→只read主人私聊→send_message。09:33:13Z回执`c14a6740c2be4e78ae9852aaf230bec7`，三步为5分钟收集/10分钟取舍/5分钟明确下一步；seq27 sent、seq32 completed。没有代发、安排或Task创建。
3. **PA正式维护补验有效Memory**：由于首次是合法失效分支，追加明确有界请求`427af9f34b1e4d7785b2f65399e350d9`，要求仅整理主人真实表达、不要把助手建议当长期偏好。PA自主加载nano-memory，seq54调用`memory_maintenance run`并引用原request_ref。run `7b738ec1-dd0d-4dfe-8990-2cd5a27a9782` completed；seq61 status核实MEMORY.md及knowledge/planning.md均saved=true/versionRecorded=true，提交分别`ef0c663fa11cd298691ac0cc2cac73949a9452d0`与`4cc02d2333f71e841b432a0d242656e8cfc519fd`。主Agent没有用write/edit或shell写正式库；还read完整详页核验后才公开确认`f131beb90f474b09aa0f33b7da55f3f5`。
4. **PA有效正文与自然使用**：维护后seq58/64 runtime给出绝对`.../pa_3e16eef0a4b1/.nanoassistant/memory/MEMORY.md`及完整一页关键记忆，正文明确主人容易列过长清单、尚无固定三项/时间分配偏好，并链接knowledge/planning.md；source gen1有效。随后自然请求`f1e2b4918a1c4dfb8b9bcc64855f3d25`询问下次十几项待办应先做什么，PA真实回复`8e0ad8a5e9594703a0f4b07805f0ca07`先分必须/可延后，再按实际可用时间缩减，不套固定三件上限；seq95 sent、seq100 completed。**这是后续有效分支，不改写首次失效事实**。

检查后Task表仍0条；两角色均没有schedule_create/send_user_message。无引导模型复述内部Prompt；完整输入由原生取证读取。正常建议可读、明确、有针对性，内容与身份、授权和实际工具结果一致。

### 证据 locator 与诚实边界

证据均位于本地 `output/refactor-679-followup/`，不提交runtime/secret/raw logs：

- `global-initial-full.json` / `pa-initial-full.json`：完整首轮System/messages/header配置与全部工具；相应`*-initial-messages.txt`、`*-initial-tools.json`、`*-initial-inventory.json`。
- 首轮JSON SHA256：Global `199aeae6b3a6818f598cb220ad2c6d31245587e37927a1d4a5a497a705ce75b1`；PA `86374d27f946fde1da890e6189579f0e9a4a80c828ee95f184adf737bb49ee66`。
- `global-native.jsonl`、`pa-native.jsonl`：完整原生持久事件；`pa-valid-memory-snapshot.{json,txt}`及`pa-through-valid-request-events.json`保留有效分支与第三次请求前完整事件。
- `requests.json`、`pa-memory-request.json`、`pa-valid-memory-request.json`、`global-timeline.json`、`pa-timeline.json`：真实客户端消息/交付。
- `global-reply.png`、`pa-reply.png`、`pa-memory-followup.png`：浏览器实际交付。

这里的“完整输入”是原生System/user/tool持久surface + request/header工具与request/context配置，能关联真实模型后续tool calls与sent回执；**不是upstream代理最终HTTP wire抓包**。未声称捕获代理层转换。既有受控HTTP机制证据只retained，未替代本轮真模型行为。本轮不额外运行大评测。

本轮有效Memory已有真实Dreaming保存；“前台没有四个工具仍可自动维护”继续复用caller本轮真实runtime测试，不冒称此次PA（前台maintenance开放）的旅程证明该缺工具分支。插件rc.7同bytes与源码tag由caller记录，独立产品输入已证明UUID名称行消失。

### 生命周期与文档

reviewer未启动或关闭服务。按用户查看要求保留新51966预览和旧64012预览；由caller集中生命周期。无客户端布局变更、不扩大iOS。报告由caller集中提交，current spec归并及分支交付不是验收通过的同义词。

## Round consumer-1（2026-10-31，消费者接口与当前记忆读取）

**PENDING / 1 major 待关闭**；validated_at: `0718cbd3b`；基线 Memory `2724ea8d1`。本轮自然行为、初始上下文、状态与即时更正已通过；加载后的 nano-memory Skill 尚有旧机制术语，须按下述发现修正并定向复验，不能提前宣布整体 PASS。前轮无关 Task、Schedule、换窗等验收 retained。

### 环境、完整输入和实际默认工具

固定 daily `/tmp/nano-refactor679-consumer/.e2e-daily.json`，IM `http://127.0.0.1:58220`，node `wt-nano-refactor679-consumer-4938`。Global P `daily-product` 使用 `codexOAuth:gpt-6.1-sol/high`，PA `pa_0adea1e232c4` 使用 `codexOAuth:gpt-6-astra/medium`，正常 Codex 审核。群聊 `c_cq6xp802` 与主人私聊 `c_581378ff3edc`。旧51966、64012未动。

独立读完完整初始 System、runtime snapshot、Skill目录以及全部工具description/schema；两角色37个完全相同工具逐项去重阅读，PA另有personal_sources/send_user_message两项。实际模型tools为Global37、PA39；glob、grep、job_output、job_kill、job_list均在真实request/header中，非仅配置声明。Global实际调用glob/grep/read均成功。未为了证明工具存在而制造无关后台工作。

初始模型content中无inbox_result、observation=live/restored、send_message_result、send_user_message_result、Gateway身份映射指导、fs-observation-policy、Source generation、entry_basis_stale。来源规则用实际sender/target/channel/reply字段，sent/held/unknown区别与PA participant/observer边界仍清楚。两角色首轮均注入完整当前MEMORY.md、绝对目录/文件路径及一页关键记忆包装；PA首次同步不再隐藏模板正文。DSH原生开场/runtime snapshot与窗口ID保留。read/glob/grep指导保持。**这些初始结论不代表后续加载Skill没有遗留文案。**

用户接受“刻意限制工具而保留DSH jobs指导”的例外，本轮不测试或声称任意白名单配置都一致。审批器独立协议和未触发的旧场景只引用既有机制证据，不冒称此次普通问答重新验证。

### 有界自然旅程与结果

| 场景 | 实际结果 | 判定 |
|---|---|---|
| Global文件查询/记忆读取/建议交付 | 11:07:46Z请求`9f7e5fd1fa144416a3772c0b12f542ae`；session `97e406fe-2a9c-4e35-809f-1a67f81e02e8`。inbox check/read、conversations info、读三份项目资料、加载nano-memory、读正式MEMORY、grep关键词及glob目录；seq52返回sent，消息`675f825e28c448b49df9f75b1e4d9c6a`。两条建议分别为误点恢复与离开后接续，带文件/行号、前置操作预期，明确仅建议未实测、不擅自扩大跨设备要求。 | PASS |
| PA首次读取、明确保存与真实status | 11:07:46Z请求`9cb75e01983c4a519f5bbceed71a6003`；session `54f70a6a-b492-4cff-a8a8-fad495f1aecb`。读模板/列文件后按原request_ref运行Dreaming，run `afe122ca-b099-46d5-a872-292375633b5b` completed。seq53 status显示MEMORY.md和workstreams/todo-memory-test.md均saved/versionRecorded true，commit分别`e6a2fb268740e2456622ec4942b8a1dc17416c2d`、`39174e3c0e27508a7d4c8fe8fee3f2c8c6d96156`；主Agent读回两页后seq69 sent，交付`ba92862b2fa24b9d9c824abe9a91fd2a`。 | PASS |
| 状态不泄漏后台私有数据 | 实际seq53完整结果仅mode/sourcesPending/exclusions/receipts与maintenance.active/backlog/reviews；无protocol/streams/seen/rotation/integrated/cursor。backlog注明frozen_sources，global pending false/units0，children/blocked空；模型公开解释为已纳入检查来源范围内的本批0增量，不声称所有未来材料已整理。 | PASS |
| 保存后下一请求直接使用新正文 | seq50 runtime已带新完整MEMORY.md及两页变化提示；seq56仍带当前正文，不出现来源代数或失效原因。随后读回正文核实偏好仅限测试，不把行动边界泛化为永久偏好。 | PASS |
| 本轮即时更正与停止采用 | 请求`23ebfe2b48214846b443d24c23bb8793`明确本轮停用二分法、改按截止时间，不立即整理。PA读回详页，seq96 exclude按原请求登记路径，seq100新runtime保留当前正文并明确停止采用约束；没有run/write/edit/bash。seq103 sent交付`0f6d55911dc74213ab30cf312cac6b6f`：今晚食材→明早报告→下周还书，准确说明已登记但未整理、未修改正式文件。seq108 completed。 | PASS |

两角色均未创建Task/Schedule、未对外代发或联系其他人。PA仅消费主人participant私聊，群observer未变成受托工作。后台记忆保存了证据截止点的“尚未见保存回执”历史记录，PA清楚区分这段旧记录与后来真实保存回执，没有把旧过程记录当当前失败，也没有篡改历史以伪装当时已知。

客户端同一HTTP API发起消息；Chrome输入可填充但click/Enter未提交，读取聊天确认无同文后使用API，未重复发送。真实浏览器看到Global完整建议、PA保存状态和更正答复；1230×816画面可辨认主体、分项结论、来源与本轮边界，没有表格溢出或不可读内容。截图`global-reply.png`、`pa-correction.png`。

### 发现 C1：加载后的 nano-memory 仍带旧接口术语（major，待关闭）

root独立完整审读实际PA seq27的Skill结果指出，reviewer确认：首句要求使用memoryRoot及PA/specialist profile，而当前消费者实际收到Memory directory/Role；“前台不提供checkpoint，也不能给待核对页重新背书”仍描述旧失效链路；“旧逐step数量”无当前操作用途。初始System/目录通过不能覆盖此完整动态加载面。未观察到实际错误调用或错误保存，但违反本轮明确的消费者接口清理要求，因此阻塞本轮通过。修复仅需同步Skill文字，随后有界重新加载、检查完整Skill结果及行为；不需重做已通过的记忆保存旅程。

### 证据与边界

本地`output/refactor-679-consumer/`保存：`{global,pa}-initial-full.json`、`*-initial-messages.txt`、`*-initial-tools.json`、`shared-tools.json`、`different-tools.json`、`sha256.json`；原生完整`{global,pa}-native.jsonl`及去除source/meta副本`*-complete-visible-surface.json`；`pa-after-status-full.json`（seq0–57）、`pa-through-correction-full.json`（seq0–108）；状态/运行时文本`pa-status.txt`、`pa-updated-memory.txt`、`pa-after-status-runtime.txt`、`pa-exclude-result.txt`、`pa-stop-use-runtime.txt`；请求与两张截图。完整文件保留所有实际内容，不以关键词搜索代替审读。

这些是原生持久请求header/context与System/user/tool/assistant surface及实际模型行为，不是上游代理最终HTTP wire抓包；header仅在变化时持久化，后续请求继承该37/39工具集合。没有降级stub、额外评测或生产操作。reviewer未启停任何服务；三个隔离预览由caller统一管理。

### Round consumer-2：C1 定向关闭与最终裁决

**PASS**；validated_at: `5fcb9b18a288e5b1c8007c27ce41448d50637c7e`。0 blocking、0 major、0 minor；highest_required_action: none。consumer-1的行为及工具/初始输入结论保留；唯一C1现已关闭。

caller同步当前Skill并managed重启本轮Node，保留IM、session及记忆。reviewer只发一次有界重载请求`98818fdf9ad64f39bcc4ed338e9d0b01`（11:13:34Z），要求重新加载nano-memory并查询当前更正/保存状态，明确禁止启动整理或改文件。PA同一session在seq127重新调用skill，seq128返回当前完整正文。独立全文检查：首句明确“当前上下文标注的记忆目录和个人助手／独立专家角色”；旧memoryRoot/profile、checkpoint背书和逐step说法已删除；后台暂存副本职责、来源边界、真实保存/版本回执、下一有界批次数量解释仍完整。没有引入不存在工具或新的持久写入入口。

seq132实际调用status，seq133显示旧两页保存回执仍在、停止采用请求仍在；maintenance.active=false，backlog.pending、下一批units=8、无blocked。没有protocol/streams/seen/rotation/integrated/cursor。PA据此明确区分：本轮更正即时生效、旧回执不代表更正已经保存、下一批8个单元不代表全部积压。没有run/write/edit/bash/Task/Schedule调用。seq138公开sent，消息`2e7be5234a9740a0830bc759d0f003e1`；seq143 completed。浏览器实际确认完整答复可见。

新证据：`output/refactor-679-consumer/pa-reloaded-skill.txt`（seq128完整返回）、`pa-skill-reload-full.json`（完整seq0–143，含继承的header/tools及后续请求/结果）、`skill-reload-request.json`、`pa-skill-reload.png`。旧seq27的Skill原文仍自然保留在历史中，未删除或改写；C1关闭依据是本次新加载全文及随后实际状态行为，不宣称旧历史文本被追溯消除。此定向复验完成后停止新消息和模型调用。报告由caller统一提交；reviewer未启停服务。

## Round child-forget-1（2026-11-01，普通子／fork／自然语言遗忘）

**PENDING：Task summary 内部边界头待定向关闭**。executed_base `8c9d34780`，本轮实跑实现 `2b158262075097ad4e7b54afd3fd63290de73b21`，分支 `codex/refactor-679-child-context`。本节替换前轮显式exclude机制的目标判断，旧consumer证据保留为历史，不将旧契约视为本轮要求。既有无关Task/Schedule/UI场景retained。

### 实测环境与证据性质

使用caller集中启动的daily `/tmp/nano-refactor679-child/.e2e-daily.json`，IM63958、node `wt-nano-refactor679-child-62030`，专用owner `u_a81qgri2`。PA `pa_15e5d7a35be6` / 私聊`c_f8cb0d911373`，主session `255d6513-5ada-46ac-9eb4-884626f9d41b`；真实astra/medium，审核Luna，普通/fork继承模型。Global P `daily-product` / 群`c_oyhx41yk`使用sol/high，主session `da629f2f-4479-46fe-a885-35ab29764d5d`。无生产操作、旧预览未动；reviewer未启动或停止服务。

本次有真实出站HTTP request body及SSEresponse：`output/refactor-679-child-live/wire/`，仅本隔离实例的透明代理转发正常4000路由，不保存认证头。不同于前轮仅native surface证据，本轮system、tools、messages和实际cache usage可直接逐字段对照。完整初始输入通过全文阅读与完全相同段/schema去重核对，非关键词抽查。PA额外完整native事件`pa-native.jsonl`至seq190及分阶段正文/status快照已保存。

### 普通子与 fork

| 场景 | 真实输入和行为 | 判定 |
|---|---|---|
| 普通PA子 | 请求`483d4f199c42481282e42ace4130c90b`委派虚构天气条件分析；wire0044/session`53e69ef5-7afd-44ad-b9d2-8fcb56eb3ed4`。System是internal subagent，保留所属PA名/ID但无主人助理Persona或根公开交付职责；33tools，无inbox/conversations/send_user_message/personal_sources/schedule_run/schedule_history。send_message schema只有agent_id/message。实际仅内部send_message向父回传，seq19确认、seq24完成，没有公开发言。 | PASS |
| PA fork | 同请求先取得普通子结果，再fork；wire0048/session`c2aaedbd-14b3-4bf1-be50-86096107d9f9`。system和39tools与父请求0047完全相等；前24个message对象完全相等，保留上一完成轮，新增runtime及本轮委派/回传边界在末尾。父主动把当前未完成轮的普通子结论放入委派，fork成功复核天气/会议约束优先于虚构偏好，通过原生completion返回，无额外发信。 | PASS |
| Global普通与fork | caller驱动暖轮`481e30fea4cd48b6a82ae07152694d0e`、主请求`e04b5ab3428d4a6dbf3891dbd3c451b8`；reviewer独立核对完整`global-*-initial-request.json`。普通wire0024/session`f9b8520a…`为internal身份、33tools；两fork0033/0035 system/tools与父完全相同（37tools），10条既有message对象前缀相等，后接新runtime与委派。第一次fork未拿到当前未完成轮普通子原文，诚实返回证据不足；父补齐原文后第二次fork才完成复核。最终群消息`3f5f26b6cf274f37b256bb3edc92c095`三行结论真实可见。此原生fork仅继承完成轮次的边界不隐瞒，不把第一次记为成功复核。 | PASS |
| 实际缓存 | PA fork0048 SSE `cache_read_input_tokens=19968`、`input_tokens=1100`；Global0033/0035均cache read15744，未缓存input889/1009。均为实际provider返回，不从字节前缀或配置推定命中。 | PASS |

普通与fork完整输入分别见`pa-{ordinary,fork}-initial-request.json`及native文件；`pa-ordinary-tool-diff.json`展示普通子唯一修改schema是native send_message；`pa-fork-prefix-comparison.json`保留逐父请求比较。fork保留可见schema不等于获根会话权限；实际本次不尝试恶意公开调用，宿主拒绝边界引用caller原生机制回归，不能写成此次自然旅程实测拒绝。

### 自然语言记忆旅程

1. **先保存两条虚构长期偏好。** 请求`cb3400a223af4c0ab72f8d904b4fcddf`要求默认周末上午出行、方案先简短结论后细节；明确隔离验收虚构范围。PA读取nano-memory后以原request_ref运行Dreaming `5b442a0c-f975-454c-a126-092029c273c5`；seq44 status证明偏好页、入口、当日记录3/3 saved/versionRecorded，读回后交付`5215465843d54d0286d95eaff088ea6e`。正式内容保留虚构范围，未泛化成真实生活事实。**PASS**。
2. **仅本轮例外不删长期偏好。** 请求`483d4f19…`要求普通+fork分析后“仅此次先细节再结论”，并实际整理核查。Dreaming `7f358a09-7c96-4b5e-a178-21bc41e0f56d`整合两份子摘要，2/2更新页保存，seq133读回偏好页仍完整保留两条长期偏好；单次例外写在事项记录与入口，未改长期表达顺序。最终`e80eb6b22b8f4eb28a9dbd17aae15b99`确实先列条件后给结论，报告下一批仍有1单位而未假报全部清空。**行为PASS，输入头有下述独立问题**。
3. **自然忘掉先当轮不采用。** 请求`b0c8e10b85494357bc5fc17c7f17d189`要求以后不再采用上午出行偏好，保留结论优先；新条件上午/下午天气与空闲完全相同，要求先回答再整理。PA seq160先回答两者均可、无依据优先其一，明确“已停止采用、尚未修改正式记忆”；seq161送达`19aed6127d624fd9ad0da736de094168`。随后seq165才调用普通memory_maintenance run，无exclude/paths/sources参数，无停用名单操作。**PASS**。
4. **Dreaming直接从聊天清理。** `6ef6fd38-98ca-41d2-b645-597a281a1cfa`完整初始输入包含原始主人forget消息和PA即时答复，没有独立遗忘登记包；Dreaming完成3/3保存及版本记录。seq179完整偏好页只保留结论优先，seq180入口同样移除上午偏好，仍注明虚构范围。实际新版commit：偏好`e67be99017b22e1f5e86b2d40fdbf69127851596`、入口`56e54c010d5f095065d6e7ce015cb3ef29aaa823`。seq185送达`4095cc455ca24f9ba3b46d50c492479b`，说明现在已修改正式记忆、并非删除原聊天/Git历史；seq190 completed。**PASS**。

主Agent整个三轮除read/Skill/委派/内部与公开send及maintenance status/run外，未write/edit/bash写正式库，未调用遗忘工具或personal_sources，未创建Task/Schedule。memory_maintenance实际schema仅status/run及request_ref/importLegacy；context/status没有exclusions或停用请求引用。原始聊天与历史记载保留，不能将“忘掉”误报成擦除所有历史。

### Dreaming完整输入与问题

首轮`pa-dreaming-initial.json`（wire0012）System、两条messages及11tools完整核对：目录投影仅session_id/purpose/available_before；无Run/cycle/source generation行或baseline/through字段；保留实际可用的staging路径与窗口ID。遗忘轮`pa-forget-dreaming-initial.json`同样成立，已完整核对当前正文与原始忘掉原话。正文的事件seq用于原始证据定位，与内部冻结范围字段区分。前三个自然Dreaming均未自主调用source_history，因此不能据此声称实际返回已验；其工具schema已检查，返回面仍需caller机制/后续证据。

**发现 CF1（major，待修复复验）：** 含子摘要的consolidation wire0053，`pa-child-consolidation-initial.json`，新Task summary头仍注入`root=…; events 0–23/66–82; version=<hash>`。这些是宿主摘要边界/版本记账，不是模型继续读取工具所需参数；旧范围随后还出现在当日记忆引用。与本轮明确清理目标不符，不能以行为成功放行。caller已冻结修复`fea88c187`，本报告暂保留失败证据，待最终版本单次新增子摘要与Dreaming消费复验；旧历史内容不要求追溯抹除。

### 真实界面与范围

Chrome真实查看群三行结论及PA保存回报：消息明确作者、按要求分项，能分辨条件推论、实际保存与尚待处理；未出现重复子公开回复。`pa-review-global-delivery.png`保存Global画面。使用客户端同款HTTP入口发送授权测试消息，不触碰生产。无客户端布局变更，本轮不扩大iOS；fork/root工具权限机制及SingleThread静态修正由caller窄回归支持，未冒充自然PA旅程覆盖全部工作模式。

## Round child-forget-2（2026-11-01，CF1 定向关闭）

**PASS**；validated_at: `fea88c187`（实际运行产物）；报告时 HEAD `dfdfbd66b67a4912c00defad8ed0bf955b3100ac` 仅后续测试修正，不冒充重新实跑版本。0 blocking、0 major、0 minor；highest_required_action: none。child-forget-1 中普通子、fork、实际缓存及自然遗忘结论 retained；唯一 CF1 已关闭。旧失败证据和旧历史文本保留。

caller 在隔离 Node 重启后，reviewer 仅新增一次有界请求 `a65a323ce3a64f11b4c8a6c426e922a5`。普通子 `6d54c2c5-934e-4ccf-ad42-f5a51020af77` 正确区分“本机刷新后仍在”与跨设备同步证明，只向父级返回。新的提炼 wire0090 及 consolidation wire0091（`pa-closure-consolidation-initial.json`）完整输入核对：Task summary 头只有 `Source session_id=…`，不再附加 root、events 范围或 version 哈希；正文仍保留虚构项目范围、委派来源、单次约束和证据局限。原始业务记录的 seq 引用仍存在，不与已删除的内部摘要边界混淆。

Dreaming `02b34dac-70b2-495f-8009-d31b252b4f63` completed；PA 随后真实 status 返回一份子复盘 integrated、2/2 页 saved/versionRecorded；新当日记录 commit `755030c72e517d48973d1accbfa965d24d367883`、入口 `8359886ef9ed573b0b86a5bf91ef5f510ccbe147`。偏好页未再写入，保留上一遗忘轮版本。公开发送 `14a13af9b7c340618330ab33f35c069c` 为 sent，明确结论、实际保存和未改变剩余偏好，未联系外部或建 Task/Schedule。完整后续工具结果见 wire0106 继承的 messages；其后观察群消息只读至实际 P 回答，没有重复公开插话。

Chrome 1230×816 真实查看同一 PA 私聊末尾：作者、请求、两段结论与保存结果清楚，文本完整换行，无遮挡/溢出；截图 `output/refactor-679-child-live/pa-closure-delivery.png`。此前遗忘即时回报与正式保存回报也保持可辨认的时间顺序。

### source_history 证据层次

自然模型本轮未自主调用 source_history，不能声称已验证自然调用行为。补充审读 caller 现有 `dreaming-task-runtime.test.ts` valid 用例的完整 runtime 请求与成功工具结果（`source-history-runtime-requests.jsonl`、`source-history-runtime-results.json`；`/tmp/refactor679-sourcehistory-proof.log`：1 pass、6 skip）：真实 DSH 工具执行，LLM 与业务来源使用 fixture。成功返回保留原始角色、source、正文、window/item 定位、分页游标；allowed_range 仅 session_id/purpose/available_before，没有内部冻结 baseline/through 范围。此为工具运行时机制证据，不冒充本次真实模型 provider 请求。完整结果去重后仅三份时间不同的同内容回执。

reviewer 至此停止新请求；没有启停服务、改源码/测试或提交。仅写本 acceptance 报告，由 caller 统一提交、归档并清理隔离环境。生产未验收、未部署；既有无关场景沿用前轮已明确的覆盖和边界。
