# feat-635 — 产品验收报告

**最新结论：Round 4 targeted pass**，验证版本 `30a53c2047ea391adba6399a35234883d6c1e8fd`。Goal改为三个独立工具的Web复验通过；未变Task结果保留Round 3。本轮按用户明确修订不重复iOS UI实测，范围和证据见文末Round 4。历史结论保留。

## Round 1 — full

> Validation snapshot: `f6695dcaabfd8b3b1acadd0f7dda20378d0bc27a → e1e187e0e9c4c488aba2f0ec61e8c1c48f827ab0`
> 真实验收：2026-10-22 14:02–14:44 CST；隔离 Web `127.0.0.1:53674`，专用测试用户及 e2e/e2e-peer/e2e-global。后续修复不倒填本轮。

### Verdict — fail

核心旅程已经可完成：开始后多轮推进、有效等待、提前答复、跨层责任、父子交付、返工和改派均有真实模型与产品状态证据。但原生恢复后重复依据旧暂停意图索要审批，定向停止未走控制屏障，SingleThread 负责人执行状态无法辨认，妨碍用户判断和控制工作。离线恢复、换窗及部分 must-match 证据仍不足，整体尚不可交付。最高处置为 `fix-implementation`；无证据要求修改设计。

### 用户旅程体验

Web 1280 五栏便于比较，负责人视图显示父路径，直属视图不混入孙任务；390 改为纵向分组。等待原因和时间集中显示，安排失效时业务原因仍保留。原生 390/430 长原因可读，关闭和固定编辑入口可见；但长 sheet 底部暂停/恢复的触控滚动未能由本次工具证实，AX 可以调用不等于触控体验通过。原生恢复状态正确，却连续两次出现旧暂停理由审批，需要用户重复批准才能重新等待。

详细实际时序、任务/消息标识和截图见 [journeys.md](evidence/acceptance-r1/journeys.md)。证据仅使用虚构测试数据。

### Reference Artifacts Reviewed

已阅读 design.md 前端原型契约、prototype.html、Web 详情和 iOS 失效参考画面及共同体验标准。

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| prototype.html / M1-R1 | 根/负责人/直属五组，doing+waiting计数与分页 | web-board1280、web-assignee-1280/390、web-deep-390；J6 | 1280/390，真实待办28项和混合状态 | inconclusive：已观察部分匹配，根390/直属1280对照仍缺 |
| prototype.html / M1-R2 | 业务原因、安排诊断、运行状态分离；暂停恢复 | web-waiting1280/390、web-invalid390；J1/J5 | 有效、消费失效、恢复 | deviation：I3运行不可辨；离线待补 |
| prototype.html / M1-R3 | 原生纵向组、长原因、sheet、关闭、安全区操作 | ios-long-wait390/430、ios-paused-390/430、ios-resumed-390 | iPhone13 390、iPhone15Plus 430 | inconclusive：状态和文本明确，AX操作成功，触控滚动未证明 |
| prototype.html / M1-R4 | Goal默认关、开关保存反馈、下一轮有效 | web-goal-default、web-newagent-goal390；原生配置实际保存 | Web390/1280、原生初始402；off/on/off | inconclusive：配置和保存已观察，下一轮完整工具曝光证据待补 |

### 问题清单

| # | 严重度 / 关系 | 期望与实际 | 证据 | 处置 |
|---|---|---|---|---|
| I1 | major，阻塞，本unit恢复链 | 原生明确恢复后应按最新事实审批；rev5 doing 后 schedule_create 和 task_graph 连续被旧“保持暂停”理由拦下 | J5 两审批ID、ios-resumed-390 | fix-implementation：将真实恢复事实送入审批，保留独立工具审批 |
| I2 | major，阻塞，既有定向stop契约 | @Agent /stop 应走原生停止屏障；实际作为模型输入，由task_graph/schedule_delete自行实现 | J7 消息772616... | fix-implementation：核定向命令与scope，不能用模型暂停结果替代屏障 |
| I3 | major，阻塞，本unit执行展示 | waiting与同负责人其他doing并存时应区分实际运行；SingleThread两端一直unknown | J6及waiting截图 | fix-implementation：沿权限展示实际负责人执行，unknown只用于真未知 |
| E1 | 证据缺口，阻塞 | 离线恢复、换窗、失败投递/运行限制、依赖、完整原生触控和Goal曝光未收齐 | 下表inconclusive | 继续隔离真实验收，不能放行 |
| O1 | 观察偏差，未裁根因 | J1要求群内询问，初次问题送到既有DM；后续定时和成果回群 | J1 | 保留路由事实，不据此推断本unit实现根因 |

### 验收标准覆盖

全部期望来源均为 spec.md 同名 Scenario；界面项同时参照 design.md 前端原型。每项证据详见 journeys.md 对应旅程。

| Requirement / Scenario | 实际旅程与证据 | 结果 |
|---|---|---|
| 持续推进 / 已开工任务不依赖用户反复催促 | J2深层任务两轮；J6四阶段四轮至in_review，无继续消息 | pass |
| 持续推进 / 多项任务由负责人自主安排 | J6同负责人waiting与另一树doing共存；J2本人深层n3与他人n4分离；Global跨群A/B读取处理 | pass |
| 持续推进 / 分配待办与开始执行保持区别 | J1行李n2分配后todo；J2人类父/祖先未随子任务启动 | pass |
| 有效等待 / 等待预算答复 | J1真实询问、Schedule、waiting rev3；Web进行中卡片原因/时间。询问路由偏差另记O1 | pass |
| 有效等待 / 全部任务等待与部分任务可推进 | J6 waiting未阻断4轮doing；仅waiting未立即热循环；J1安排消费后处理 | pass |
| 有效等待 / 无有效安排时拒绝转入waiting | API非法Schedule关联400且未改状态；未取得Agent收到拒绝后自行修正完整旅程 | inconclusive |
| 有效等待 / waiting的安排后来失效 | J1到期消费后短暂invalid保留原因，模型补安排；J8改派后新负责人识别失效并重建 | pass |
| 有效等待 / 询问未送达 | 未制造发送失败/未知并观察完整恢复，成功投递不能替代 | inconclusive |
| 再次行动 / 相关答复提前到达 | J1预算早于新检查时间到达，waiting解除并交付，无恢复命令；同时新待办通知可能也触发读取，不独断唤醒来源 | pass |
| 再次行动 / 定时到期但条件仍未满足 | J1真实2分钟到期无预算，更新10分钟安排；未把到期当答复或授权 | pass |
| 再次行动 / 过期提醒不能重新开启已停止的工作 | J5暂停后删除旧提醒，终态保持；缺真实旧提醒在终态到达覆盖 | inconclusive |
| Tasks展示 / 进行中任务正在等待 | J1 waiting/doing同栏，详情有效/失效保留原因，恢复清等待；原生同状态映射 | pass |
| Tasks展示 / 一个任务等待但Agent正在做别的工作 | J6真实并行责任存在，但SingleThread Web/iOS运行一直unknown，无法辨认 | fail |
| Tasks展示 / 节点离线 | 本轮切换前未取得离线真实两端画面 | inconclusive |
| 暂缓停止 / 暂缓指定任务 | J5原生Pause后paused清wait；普通打招呼仍paused；J7其他群任务保持waiting | pass |
| 暂缓停止 / /stop暂缓对应范围 | 裸stop范围正确；定向@e2e /stop进入模型普通轮次，未进入停止屏障I2 | fail |
| 暂缓停止 / 自然语言恢复 | J6自然语言恢复singleA/B及globalA/B，随后按规则安排等待，无固定命令 | pass |
| 真实交付 / 按任务约定交付 | J2 Peer按约定done；J6四阶段in_review；J7子done父in_review，无全任务强制审批 | pass |
| 真实交付 / 返工继续原任务 | J7原父任务rev6→8，记录返工、09:00及雨天原则，再in_review | pass |
| 改派 / 改派进行中的任务 | J8 e2e第一阶段rev2doing，改派Peer rev3，Peer接续成果rev4in_review，无额外开始 | pass |
| 改派 / 改派等待或暂缓的任务 | J8 waiting保留，新Peer重建自己的安排；paused改派仍paused | pass |
| 父责任 / 委派后继续或等待 | J7 Global委派Peer、自写原则、子done后整合冲突检查并in_review，非机械done | pass |
| 父责任 / 父状态变化逐层通知 | tg_847d2fac三层普通暂缓父已准备，切换前未收齐接收处理和孙状态证据 | inconclusive |
| 父责任 / 前置完成不机械启动所有后继 | 未完成真实依赖边旅程，普通父子状态不联动不能替代 | inconclusive |
| 中断接续 / 重启或断连后恢复 | caller版本切换尚未完成，无doing接续及各状态保持的完整证据 | inconclusive |
| 中断接续 / 正常上下文换窗 | 未完成真实正常换窗并核对Task/Schedule，不以单测补齐 | inconclusive |
| 多轮责任 / 多轮仍有有效下一步 | J6四个真实回合，阶段1–3doing、阶段4in_review；仅声明实测4轮 | pass |
| 多轮责任 / 运行条件不可用 | 未形成模型/网络失效→明确原因→恢复自动接续完整链 | inconclusive |
| Goal默认 / 现有及新建Agent的默认配置 | 三Agent默认off且Task实际推进；Web创建acceptance-default635后Goal仍off | pass |
| Goal默认 / 配置页主动开启或关闭 | Web Global及原生Peer开关保存已观察；Global口述get_goal结果但群回复不附原生过程；关闭后下一轮被环境切换打断 | inconclusive |

### 上层文档同步

- [x] `SPEC.md`：无需新增运行时/包边界，仍沿DSH唯一入口。
- [x] `docs/specs/im/`、`docs/specs/gateway/`和Task契约：需要归并waiting、持续责任、stop暂缓及Goal默认关闭。current gateway仍有“不新增持久停止”旧表述，由orchestrator收尾校正，reviewer不修改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新，协作和架构红线不变。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，文档体系不变。

报告未提交，由caller汇总。修复版追加Round 2，保留前轮结论和继承边界。

## Round 2 — 修复复验与补齐场景（进行中）

- validated_at / executed_base：`567785b58bef199399bc005082e383bde6e3b2ed`
- review_round：2；scope：targeted修复I1–I3，同时继续Round1全场景缺口。
- verdict：**fail（尚有必验证据缺口）**。I1、I2、I3在新版本真实路径关闭；不能据此将全部必验项放行。
- 环境：沿用专用身份和53674隔离服务；新IM/Web/node及原生430安装包。详细消息、版本、时间及画面见[evidence/acceptance-r2/journeys.md](evidence/acceptance-r2/journeys.md)。原生390旧版本证据不冒充新版本触控验收。

### 整体体验与问题变化

离线时任务业务状态、安排未知诊断与Node offline明确分离；恢复后doing自动接续，waiting详情能显示实际Running/Idle。原生可见Resume按钮真实点击后推进成功，定向stop在当前群立即形成产品停止确认。三种原生范围与关闭返回已补齐，用户手动确认长sheet滚动；Goal下一轮实际调用/关闭拒绝也已独立核实。新发现的模型失败后配置恢复不续作仍阻塞交付。

| 问题 | 当前结论 | 依据 |
|---|---|---|
| I1 UI恢复后仍被旧暂停理由拦截 | closed，限定本次可见原生恢复路径 | J10 rev8paused→rev9doing→waiting，无旧理由审批 |
| I2 定向stop作为普通模型消息 | closed | J10 418857...即刻系统暂缓1项，另一群waiting保留 |
| I3 SingleThread执行态一直unknown | closed | J10 Web与原生waiting显示Running，后续Idle |
| I4 模型恢复后未自动接续 | open，major/blocking | J15失败后配置回可用模型已确认，任务持续rev1doing，无新回复；caller正在修复，不能用后续新版修复倒改本轮 |
| E1 必验覆盖缺口 | open，blocking | 见下表inconclusive；不以实现/单测/模型自述补齐 |

### must-match 对照

| 来源 | 要求 | 实测画面/操作 | 结论 |
|---|---|---|---|
| prototype M1-R1 | 三种任务范围五组；移动纵向；独立分页 | R1 web-board/assignee/deep390；R2 web-deep1280、web-root390-top/progress/bottom、ios-root/assignee/deep-fivegroups430；真实28条Web分页后续加载 | match |
| prototype M1-R2 | waiting原因、安排诊断、运行态分离；暂停恢复 | R1有效/消费失效；R2 web/ios-offline、doing-offline、waiting-owner-running、idle；J9/J10 | match（已观察状态） |
| prototype M1-R3 | 原生390/430长详情、可滚动、可关闭、安全区操作 | R1两尺寸长原因；R2 430可见Resume真实点击；用户手动确认430长详情可滚动；reviewer核对Done及Back返回原范围/检索 | match，触控滚动采用用户手动证据，非CUA手势 |
| prototype M1-R4 | 默认关、开关保存反馈、下一轮曝光 | 默认与保存沿用R1；J14独立provider证据证实Global开启get_goal返回null，关闭后工具列表不含且实际调用unknown tool；Peer开启工具曝光并恢复关闭 | match |

### 全部必验 Scenario 当前结论

期望均沿用Round1对应spec Scenario；继承项具体引用原旅程，修复后的新证据以J9起编号区分。

| Scenario | 证据与继承边界 | 结果 |
|---|---|---|
| 已开工任务不依赖用户反复催促 | 继承J2/J6，两轮及四轮；J9重启后自动完成 | pass |
| 多项任务由负责人自主安排 | 继承J6本人多树深层；J10等待与其他工作并存 | pass |
| 分配待办与开始执行保持区别 | 继承J1/J2；J12真实依赖后的todo保持 | pass |
| 等待预算答复 | 继承J1询问、Schedule及waiting；保留路由偏差O1 | pass |
| 全部任务等待与部分任务可推进 | 继承J6；J10/J12仍有等待与其他处理并存 | pass |
| 无有效安排时拒绝转入waiting | J12真实Agent apply假引用被task_wait_schedule_invalid拒绝，回读原状态/有效安排保留并记录具体错误 | pass |
| waiting的安排后来失效 | 继承J1到期修复和J8改派重建 | pass |
| 询问未送达 | J13两次正式发送失败，明确目标不可访问、未送达，未伪记等待；rev2in_review交用户处理权限 | pass |
| 相关答复提前到达 | 继承J1预算回复→in_review，保留并发通知边界 | pass |
| 定时到期但条件仍未满足 | 继承J1；J10面积仍未知，14:54到期重建15:09检查 | pass |
| 过期提醒不能重新开启已停止的工作 | 继承终态保持与删除提醒，但缺旧提醒真实到达 | inconclusive |
| 进行中任务正在等待 | 继承J1；R2根390进展栏含waiting原因、时间，独立列内滚动 | pass |
| 一个任务等待但Agent正在做别的工作 | J10两端waiting+Running，后续Idle | pass |
| 节点离线 | J9两端doing与Node offline明确分离，waiting保留原因但未知安排 | pass |
| 暂缓指定任务 | 继承J5；J10当前群暂停、另一群waiting保留 | pass |
| /stop暂缓对应范围 | 继承J7 Global跨群；J10定向SingleThread仅本群 | pass |
| 自然语言恢复 | 继承J6；J10额外证明UI恢复 | pass |
| 按任务约定交付 | 继承J2/J6/J7；J9按任务约定done | pass |
| 返工继续原任务 | 继承J7原图rev6→8返工再in_review | pass |
| 改派进行中的任务 | 继承J8第一阶段e2e→Peer第二阶段，无额外开始 | pass |
| 改派等待或暂缓的任务 | 继承J8；J9重启后waiting保留 | pass |
| 委派后继续或等待 | 继承J7子done后父整合冲突检查 | pass |
| 父状态变化逐层通知 | J11父暂停只通知直属Peer；Peer审批后暂停子再通知孙；孙todo | pass |
| 前置完成不机械启动所有后继 | J12真实n2→n3；n2done后n3todo，Agent收到通知后明确不开工 | pass |
| 重启或断连后恢复 | J9离线创建doing，恢复无用户新消息自动done；其他状态保持 | pass |
| 正常上下文换窗 | J17十二章实际工作，主会话两次正常换窗事件；同Task持续进度至rev12in_review，无额外恢复任务。伴随Task保留doing；原无Schedule，不外推安排跨窗存续 | pass |
| 多轮仍有有效下一步 | 继承J6四轮，不外推到无限轮数 | pass |
| 运行条件不可用 | J15真实模型403可见且状态保持；配置恢复后未自动续作I4 | fail |
| 现有及新建Agent的默认配置 | 继承R1既有3Agent及新建验收Agent默认关闭，Task照常工作 | pass |
| 配置页主动开启或关闭 | J14原始provider工具调用及结果独立核验：开启返回goal:null，关闭后不曝光且尝试调用unknown tool；未修改Task | pass |

上层文档同步要求沿用Round1，caller收尾时归并current spec；reviewer未修改产品契约或实现。报告未提交。

## Round 3 — 最终迁移版本复验完成

- validated_at / executed_base：`30cd2e0a1272ec0a157337ebe644ad11e642809c`（包含 origin/main `0904bc49c`）。
- review_round：3；scope：targeted。复验 I4、旧提醒、最新原生布局与人类控制、Goal权限边界和自动第二轮审批；其余沿用下表指定的R1/R2独立实测。
- verdict：**pass**。I1–I4及E1均已关闭，无遗留 blocking/major 问题；不是把旧版全部30场景宣称为最终版重跑。
- 环境仍为专用53674栈与原生430模拟器；证据见 [Round 3 journeys](evidence/acceptance-r3/journeys.md)。已将原生及服务控制权释放给caller清理，reviewer浏览器已关闭。

### 整体 UX 结论

任务等待原因、保存的安排时间、实际安排诊断和Agent执行态分别可读；等待中的任务不会令其他任务停工。最终原生版恢复按钮能重启任务，旧暂停理由不再阻拦；模型配置修好后不需催促即可继续。自动第二轮遇审批时明确等待决定，批准后原任务完成。最新main的compact布局省略空组正文，顶部保留零计数，waiting仍归进行中；三种任务范围与返回位置均实看正常。

| 问题 | 最终处置 | 独立证据 |
|---|---|---|
| I1 UI恢复被旧暂停理由拦截 | closed | R2 J10；R3 J20再次paused→doing→waiting，无旧审批 |
| I2 定向stop进入普通模型轮次 | closed，继承修复复验 | R2 J10系统停止确认，本群暂停且异群保留 |
| I3 SingleThread运行态unknown | closed | R2 J10两端Running/Idle；R3 J20原生Running |
| I4 配置恢复未自动续作 | closed | R3 J18新建失败任务，仅恢复模型profile5，无重启/新消息，自动done |
| E1 必验证据缺口 | closed | R2 J11–J17与R3 J19/J21/J22补齐，见全部Scenario表 |

### 最终 must-match 对照

| 来源 | 要求 | 最终证据与版本边界 | 结论 |
|---|---|---|---|
| prototype M1-R1 | 根/负责人/直属三种范围，五组映射，移动纵向，独立分页 | Web沿用R1/R2 1280/390及28条真实分页；R3 J20原生compact三范围、waiting定位进行中及返回筛选。最新main省略空正文，零计数仍在；保留五类语义 | match（记录main布局差异） |
| prototype M1-R2 | waiting原因、安排诊断与运行态分离，暂停/恢复 | R1有效/失效，R2未知/离线/Running/Idle；R3 J20再次真实Pause/Resume、原因与时间 | match |
| prototype M1-R3 | 原生390/430长详情、滚动/关闭/安全区 | 390长文证据保留R1；430 R2用户手动确认可滚动、可见按钮点击；R3 Done/Back保持范围且恢复成功。未宣称最终版390重跑 | match（保留尺寸复验边界） |
| prototype M1-R4 | Goal默认关闭，保存反馈与下一轮工具曝光 | R1默认及配置UI；R2独立provider证据；R3 J21真人明确授权四次原生Goal调用，关闭后下一轮tools无Goal | match |

### 全部30项 Scenario 最终结论

| Scenario | 最终依据 | 结果 |
|---|---|---|
| 已开工任务不依赖用户反复催促 | R1 J2/J6；R3 J22普通final后自动第二轮，批准后done | pass |
| 多项任务由负责人自主安排 | R1 J6多树；R2 J10等待与其他工作并存 | pass |
| 分配待办与开始执行保持区别 | R1 J1/J2；R2 J12真实依赖后todo保持 | pass |
| 等待预算答复 | R1 J1询问、真实Schedule、waiting；保留O1路由观察边界 | pass |
| 全部任务等待与部分任务可推进 | R1 J6；R2 J10/J12 | pass |
| 无有效安排时拒绝转入waiting | R2 J12真实Agent无效引用被拒，原状态保留 | pass |
| waiting的安排后来失效 | R1 J1到期修复、J8改派重建 | pass |
| 询问未送达 | R2 J13实际发送失败、明确未送达且不伪记等待 | pass |
| 相关答复提前到达 | R1 J1预算回复后in_review；保留并发通知边界 | pass |
| 定时到期但条件仍未满足 | R1 J1；R2 J10重建后续检查 | pass |
| 过期提醒不能重新开启已停止的工作 | R3 J19旧提醒排队，处理时已in_review，回读后不写Task、不重新开工 | pass |
| 进行中任务正在等待 | R1/R2；R3 J20 waiting仍归In progress，详情原因/时间 | pass |
| 一个任务等待但Agent正在做别的工作 | R2 J10 Web/iOS waiting+Running再Idle | pass |
| 节点离线 | R2 J9两端业务状态与Node offline、未知安排分离 | pass |
| 暂缓指定任务 | R1 J5；R3 J20暂停清wait、恢复重建 | pass |
| /stop暂缓对应范围 | R1 J7 Global跨群；R2 J10定向SingleThread仅本群 | pass |
| 自然语言恢复 | R1 J6；R2 J10和R3 J20额外覆盖UI恢复 | pass |
| 按任务约定交付 | R1 J2/J6/J7；R3 J22两阶段结果done | pass |
| 返工继续原任务 | R1 J7原图rev6→8返工再in_review | pass |
| 改派进行中的任务 | R1 J8首阶段e2e→Peer续作，无开始消息 | pass |
| 改派等待或暂缓的任务 | R1 J8 waiting保留并重建、paused保持；R2 J9重启保持 | pass |
| 委派后继续或等待 | R1 J7子done父整合冲突检查 | pass |
| 父状态变化逐层通知 | R2 J11逐层通知，孙todo未被机械开启 | pass |
| 前置完成不机械启动所有后继 | R2 J12真实依赖边、前置done后后继todo | pass |
| 重启或断连后恢复 | R2 J9 doing自动done，其余状态保留 | pass |
| 正常上下文换窗 | R2 J17主会话两次正常换窗，12章任务rev12in_review；不外推未存在的Schedule跨窗 | pass |
| 多轮仍有有效下一步 | R1 J6四轮；R2 J17长文多轮；R3 J22自动第二轮审批后完成 | pass |
| 运行条件不可用 | R2 J15真实403；R3 J18配置错误可见、仅修配置即自动done | pass |
| 现有及新建Agent的默认配置 | R1既有三Agent与新Agent默认关、Task照常推进 | pass |
| 配置页主动开启或关闭 | R1配置UI；R3 J21实际get/create/update/get，关闭后工具不暴露 | pass |

### 文档与交付边界

上层文档归并清单沿用Round1：current Task/IM/gateway契约应同步waiting、持续责任、stop暂缓与Goal默认关闭；由caller完成收尾，reviewer不改实现或契约。用户手动滚动证据、历史尺寸继承、模型生成文字笔误及O1观察都保留，不扩大成未观察的系统承诺。正常换窗证据证明Task持续责任与进度接续，不声称测试了一个不存在的Schedule跨窗。本报告无实现修改、无提交，由caller集中提交。


## Round 4 — 用户修订：Goal 三工具独立选择

- validated_at / executed_base：`30a53c2047ea391adba6399a35234883d6c1e8fd`；review_round：4；scope：targeted。
- verdict：**pass（本轮受影响 Web 范围）**；问题0，blocking 0。真实操作及请求证据见[evidence/acceptance-r4/journeys.md](evidence/acceptance-r4/journeys.md)。
- 用户明确将本轮效率优先放在Web，iOS仅源码/编译回归，不重复原生UI实测。故本轮iOS UI为not-applicable（用户缩小范围），不是已实测pass；caller的iOS测试成功不当作原生体验证据。不启动模拟器。

### 整体体验裁决

Goal三项融入既有Tool Allowlist，未选灰色、选中青绿，与相邻普通工具一致。桌面及390窄屏均可逐项辨认和操作，窄屏自然换行、名称完整；页面没有额外Goal Feature总开关，也没有将一个选择联动为三个。保存后重开仍保留准确单项选择，实际模型只取得所选工具；取消最后一项后下一请求完全移除。可完成用户此次要求，无新体验阻塞。

| 来源 / 受影响Scenario | 实际结果 | 结论 |
|---|---|---|
| spec Q16：现有及新建Agent默认配置 | J23新建表单和已保存详情均三项未选；Peer/Global镜像无Goal工具。Task不依赖Goal的结论保留R3 | pass |
| spec Q16：配置页主动开启或关闭 | J23独立create→update→get→全取消，每步保存reload只保留所选；J24 get_goal真实返回null，未选兄弟不在provider tools，取消后下一请求Goal为空 | pass |
| M1-R4：无Feature、三工具默认不选与逐项保存 | Web1280/390实看无Goal Feature；每项均有选/取消并保存重开证据，普通工具保持。iOS按用户本轮范围不重复UI | Web match；iOS本轮not-applicable |
| M1-R1/R2/R3与其余28项Task Scenario | 此次修改边界为Goal配置表示/普通工具名单；沿用R3全部对应Task旅程，含I1–I4关闭，不重跑整个矩阵 | retained pass |
| 普通失败反馈与授权边界 | 保留R2 J15、R3 J18模型失败/恢复及J22正常审批；本轮仅只读调用，没有创建持久Goal，不把选择工具解释为其他写入授权 | retained pass |

R1–R3中“Goal Feature整体开关”的历史证据不再支持当前配置体验，本轮J23/J24替换这一部分；历史Task证据继续有效。原生旧Task布局证据仅用于未变Task范围，不能用来证明新三工具选择UI。

### 同步与清理

本轮只追加报告与文字journeys，不改源码/测试/设计，不提交图片、不提交provider原始日志。图片只在仓外临时路径；独占浏览器已close，caller服务保持运行。current Agent配置/能力契约应采用三工具逐项选择且无Goal Feature，由caller收尾同步；reviewer不修改契约。无提交，由caller集中提交。
