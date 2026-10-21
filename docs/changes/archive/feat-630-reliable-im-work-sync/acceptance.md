# feat-630 — 验收报告

> Final verdict · full（Round 1全量旅程，后续受影响路径targeted复验）
> Final validated_at: `a1b5b15e2982382539e8e5498d1cdd033cbda00e`; integrated executed/effective base: `536d5a29fd449de5da7ef8c29030c1868d91567a`。
> Validation snapshot: `5665af409426f22eec86d03d68e6ffbb1c935d00 → 19f16cb74fe9ec2112d928c31695a2640882f6cd`
> 独立 reviewer；只通过真实 Web 与专属隔离运行环境验收，未阅读实现定位、未修改源码/测试。2026-10-21 Asia/Shanghai。

## Verdict

**pass**。全部13个必验Scenario闭合，当前无blocking或major问题。独立真实Web旅程覆盖查询、离线恢复、发送幂等、停止/权限、撤权、纠正、完整Work与最终构建后续收发；精确崩溃、实际输入重投和100节点持续负载以原始记录及已提交技术报告补齐。最终容量结论限于下述96 KiB/s/Work节点测试profile，不代表生产容量。历史失败与修复过程保留在各Round。

## 用户旅程体验

专属 `http://127.0.0.1:55843`，账号 nano，节点 wt-.e2e-review-39209，真实官方 DSH 与 `deepseek:deepseek-v4-flash`。caller 交接服务和前端由候选构建；reviewer 在现场确认 HEAD 为 validated_at，并仅用该构建启停专属 Node。

桌面 1200×727 中，左侧聊天列表和右侧消息区域保留原层级，发言身份、正文、时间及主动查看 Work 的入口清楚；390×844 中，聊天单列显示，返回/会话名固定在顶端，输入框可达，授权卡的具体命令及 Allow once/Deny 均可辨认并实际点击。Work 503、节点离线与恢复没有新增同步进度、游标、内部阶段标签或诊断气泡。单 Thread 原有 Process/permission 明细仍是原产品交互，不能与新增同步状态混为一谈。

实际会话 c_34qqce90：21:41 基线 4.278 秒得到回复；21:42 Work HTTP 持续503时要求读取当前聊天，5.803秒返回准确的上一条原文；21:44—21:45停Node后两条已保存消息仍留在聊天，无要求重发提示，启动后自动收到两条对应回复。Work 故障持续超过5分钟，21:49恢复时现有 Work 出现此前缺失轮次。

实际会话 c_y5dc9e1y：运行任务后从普通输入框发送 `/stop`，133毫秒内收到“已停止当前操作”；在专属workspace临时设 auto_mode.enabled=false 后，通过真实卡片 Allow once 运行 printf 并看到 approval-review 输出；以上都在 Work 503 下完成。

文字与附件发送均从普通输入框操作。Playwright route.fetch 先获得中心201再abort，未由测试主动注入幂等key。有效截图附件的产品请求自带 idempotency-key；刷新后只见一条原附件和一次“有效附件已收到”回复（模型1.6秒）。后续将浏览器置offline，在提交结果未知时编辑新草稿，再恢复网络，原回复出现且新草稿保留。另在未知提交状态退出nano并登录review630b，原聊天拒绝访问；切回nano后原输入和正式回复各一条。新显式发送同正文形成独立第二条输入/回复。证据见Scenario 6。

首个1px base64 PNG可被浏览器保存但模型图片解码报 Unsupported or malformed image data；Global Inbox read 因该坏fixture失败并触发反复重读/发送复核，未收到该附件后的正常回复。caller只读取证确认输入已持久接收、wake推进且WS ready。后改用浏览器原生截图PNG在单Thread验证成功。坏fixture不作为本feat可靠性通过证据，也不把它归因本次同步隔离改动。

## Reference Artifacts Reviewed

已读 spec.md 全13个Scenario、design.md Runbook V1–V8、共同体验标准、current IM消息与Work契约、权限运维文档。design明确无新UI原型；保持原聊天布局与主动Work入口为必须结果。真实截图已打开检查，不能仅以DOM存在替代视觉判断。

| Reference | Required contract | Actual product evidence | Viewport/state | Conclusion |
|---|---|---|---|---|
| design Runbook V8/既有聊天入口 | 不新增内部同步标签；正文、发送和Work入口可用 | work-down-desktop.png、offline.png、narrow.png | 1200×727、390×844；故障/离线/恢复 | match |
| design V1/V8 原权限入口 | 可读动作并作出决定 | approval.png、实际Allow once后输出 | 390×844/需要确认 | match |

本地证据根：`.e2e-review/evidence/feat630-review/`（忽略的测试产物，不提交图片）。消息JSON仅为同一专属账号只读核对；UI快照和真实截图共同提供用户侧证据。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| A1 | closed（原证据blocking） | 精确恢复/重投/大内容/持续负载原先缺证 | 已按原门槛补齐全部13项，不降低标准 |
| A2 | 测试fixture，不定为产品缺陷 | 1px PNG图片解码失败导致Global反复重读 | 保留事实；有效截图PNG替代复核通过 |
| A3 | closed（原blocking） | DSH durable accept后强杀恢复缺口 | 稳定recovery通知链经重复强杀、唯一write/回复与最终UI后续收发闭合 |

## 验收标准覆盖

期望来源均为 spec.md 同名Scenario；技术补证只按其实际层级引用，不代替用户可见证据。

| # | Requirement / Scenario | 验证方式与证据 | 结果 | 边界 |
|---|---|---|---|---|
| 1 | 历史工作记录同步不阻塞当前沟通 / 有大量历史记录待同步时继续交办 | technical V1：真实工具产生9MB待上传历史期间原聊天查询并正式回复；独立Work503查询旅程 | pass | 技术积压证据与独立用户查询证据组合 |
| 2 | 同上 / 工作记录同步暂时不可用时仍能查询并回复 | c_34qqce90查询原聊天并准确回复；work-down-desktop.png、messages.json | pass | 5.803秒可见回复 |
| 3 | 暂时不可达的消息自动恢复投递 / 节点离线期间发送消息 | 停Node、UI发送、原身份启动；offline.png、narrow.png、c_34qqce90.json | pass | 用户未重发、对应两条回复各一次 |
| 4 | 同上 / Agent 运行时尚未恢复 | technical V2 seq12在DSH暂停时已保存，supervisor恢复后处理；独立UI查看对应输入/回复 | pass | Node保持在线，用户未重发；final-recovery-history.png |
| 5 | 确认丢失与进程重启不造成重复处理或回复 / 已接收消息的确认丢失 | .e2e-relay-replay.json同relay实际WS6次，Inbox/notification/write/正式回复各一次；独立UI检查 | pass | 拦截receipt上行使中心真实重投，不仅丢ACK |
| 6 | 同上 / 普通消息发送回包丢失后重试 | 文字及有效截图UI发送→201后abort→刷新；text-commit.txt、valid-attachment-commit.txt、valid-attachment-refresh.txt；edited-draft-recovery.txt；account-unknown-commit.txt、unknown-second-account.txt、account-returned.txt | pass | 产品自动生成key；后来草稿保留；未知提交状态切账号不泄漏，切回恢复原结果；新显式发送相同正文产生独立第二条 |
| 7 | 同上 / 持久接收后节点重启 | technical V2精确窗口与重复恢复通知强杀；独立历史查看及最终a1b普通输入/回复 | pass | 原缺口保留历史；不是以普通重启单独替代精确故障证据 |
| 8 | 必要控制不等待旧工作记录 / 补传期间停止或回应授权 | c_y5dc9e1y：真实/stop与Allow once，stopped.png、approval.png、消息JSON | pass | Work503下停止133ms；权限返回真实输出 |
| 9 | 工作过程在恢复后完整且不重复 / 大体积工具结果恢复回看 | Round 4真实展开4MiB正文；.e2e-work-hash.json本地/远端292事件零差异 | pass | main session、root、turn和事件顺序字段对齐；未声称额外构造子session |
| 10 | 一个节点的历史积压不拖住其他人的沟通 / 多用户和多 Agent 同时交办 | 同节点global/single_thread真实交办；final V7 100节点、20Work、20msg/s完整600秒，12000条均保存接收 | pass | 限96KiB/s/Work节点；save/receive p99增量198.56/200.15ms，均低于500ms |
| 11 | 恢复与重试保持原授权和纠正语义 / 排队期间失去访问资格 | Round 2：UI排队交办→删除成员→恢复；relay cancelled且无回复 | pass | 撤权后新内容也未产生Agent relay |
| 12 | 同上 / 回复前收到新纠正 | Round 3：两次UI提交相隔148ms，只发布最新周六15点/B安排 | pass | 正式发布前纠正，不冒充精确publication checkpoint |
| 13 | 聊天保持简洁，不暴露同步实现 / 正常使用与自动恢复 | 桌面与窄屏真实截图+发送/权限操作 | pass | 未见新增同步内部标签；原Work、必要失败及授权入口保留 |

## 上层文档同步

- [x] `SPEC.md`：需要核对Work独立HTTP与职责边界；由caller归并。
- [x] `docs/specs/im/`、`docs/specs/gateway/`：需要归并本unit delta，reviewer未代写canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新，架构红线未改变。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新，未改变文档体系。

## 环境与清理

写操作仅在`.e2e-review`、55843与其故障代理61541；经caller授权只读查看54957 Work，未修改该栈或生产。测试授权配置仅在专属e2e workspace中。已运行e2e-down停止专属栈，关闭故障代理与feat630-review浏览器；截图与证据保留在忽略目录。

## Round 2 补充：排队期间失去访问资格

Validation snapshot：`bfb059d2d765df0c00299ded9b1a08ae4f41ee31`。caller确认此构建可启动本轮；此前Round1已通过旅程不冒充在本版本重新跑过。

Scenario 11 → **pass**。专属私密群c_f2ulpdln先从真实输入框选择@E2E Peer Agent，1.7秒得到“群成员基线正常”；停止Node后，再UI @发送“节点恢复后请回复：撤权队列不得执行”。通过既有成员删除API移除u_oqpdpddd返回204，再UI发送撤权后的新内容。使用保留身份/队列的bfb构建启动后：原relay ae166f667921433ea8ad18071a3e5694由queued变cancelled；新内容e7d9f7a4cef64b648a6792165180ed71中心已保存，但无发给该Agent的relay；聊天没有追加旧交办回复。证据：revocation-group.json、revocation-relay-before.json、revocation-relay-after.json、revocation-messages.json、revocation-recovered.txt。只读核对中心存储，没有手改成功状态。

## Round 3：最终构建受影响路径复验

Validation snapshot：`2f057ba8ecedb7f15d6906a62094e480f35f69f2`（caller提供构建日志`.e2e-build-final.log`，启动专属Node pid60978）。相对Round1/2，caller说明本轮改动是Channels公平调度和Work429重试等待，合入631/632；普通聊天布局、发送attempt、停止/权限交互无修改。因此保留Round1的Scenario 3/6/8/13与Round2的Scenario11具体证据，对Work隔离/普通回复及新纠正重新操作。

- Scenario 2 受影响复验：Work HTTP503下，新增专属global e2e-review-correction，真实输入后3.872秒获得“最终构建普通回复正常”。证据final-workdown-baseline.txt、correction-messages.json。
- Scenario 12 → **pass**：普通输入框先提交周五9点/A会议室安排，148毫秒后提交周六15点/B会议室纠正；正式回复只出现“已确认最新安排：周六下午3点，地点B会议室。”。旧安排没有发布。证据correction-sent.txt、correction-completed.txt/png、correction-messages.json。此证据是输入处理期间、正式回复前的新纠正，不冒充在publication事务精确checkpoint暂停。
- Scenario 13 受影响复验：390×844截图实际查看，最新构建仍保留消息主次和Work入口，未新增内部同步状态。
- ACK丢失补证：代理分别丢弃一次node.delivery_receipt成功ACK及agent.message成功ACK，计数均降为0；有效普通消息a81faa999acf4773bf3eb8587220fc76只有一次输入和一次正式回复c85829de3df34adb8c21cceb38f2f0a0，30秒后仍各一条（ack-lost-visible.txt、ack-lost-messages.json）。这证明ACK未知恢复没有重复可见发布；接收回执根本未到中心导致原输入重新投递的精确窗口仍待V2补证。

## Round 4：大内容真实 Work 展开

经caller授权，只读打开54957的e2e-fixture Work，在22:07:27轮次展开`write four630.txt`。实际页面PRE长度4,194,306，其中F恰为4,194,304，前缀为`+ `，尾部仍为F；不是省略号或短预览。实际截图已查看，展开正文可滚动。证据`.e2e-review/work-large-dom.txt`、`work-large.png`、`work-large-expanded.png`。已读取caller的`.e2e-work-hash.json`：本地/远端292条事件零差异，ordered canonical SHA256为`c0389cde56aa06e74a6c92a5202928d9af6fdc6b6b8457a85cad4815b4aa4c3f`；seq267/268分别为12,583,671/12,583,832字节，属于main session `c96ca378-d0ab-4339-8e69-cd3975af59bf`。caller核对字段包含payload/root/session/seq/eventid/turn/observed_at；4MiB文件SHA256为`b14138a3ca83b79cc5b448a07ab8d1dd9e1220652bc0ca1b248c15c12b9e5a68`。技术全量一致与独立真实页面完整展开相互对应，Scenario 9 → pass。

## 待修复再验：DSH持久接收后进程退出

caller在V2精确故障中发现：DSH durable accept后强杀Node，重启后旧轮为interrupted，重发相同通知未再次驱动模型，Inbox仍未读。此为实际恢复缺口，Scenario 7目前不能通过。caller正在修复PA恢复owner；保持其他有效用户旅程证据，修复后需最小补验此窗口的恢复普通收发。

## Round 5：恢复修复后的受影响路径复验（进行中）

目标product source `432400f08`，完整tree `ffdbb99f1b34071c30f8b69667ded6d9074fb0cd`（后续差异只含fixtures/test/evidence）。独立读取已提交的[technical-acceptance.md](technical-acceptance.md)、原始`.e2e-crash-evidence.jsonl`和`.e2e-crash-native-counts.json`；本轮保留此前不受PA恢复和Work提交触发器改动影响的真实UI证据。

技术证据显示：Inbox commit前后保留同一relay/input；DSH durable accept后旧轮interrupted，稳定recovery通知经历再次强杀后仍恢复原输入，所有original/recovery user/message ID各一次；成功write的native call各一次。中心publication已提交、本机未确认窗口恢复后原回复仍一条，未用成功发布虚构模型轮次完成。Node在线而DSH暂停期间seq12已保存、未consume，杀死DSH后supervisor自动恢复并处理原输入。V1的9MB待上传历史期间普通查询和正式回复完成。

仍待最终构建栈重启确认后真实输入框最小复验，以及V7完整十分钟结果。Scenario5的原relay重新投递证据正在与caller核对；中心receipt ACK丢失不单独冒充原输入已经重投。

补充核对：读取`.e2e-relay-replay.json`，`b9705a44063246c7a6cb17b16df79f81`实际WS重投6次；native计数记录唯一notification与成功write，technical记录唯一Inbox/回复。独立登录真实Web，在原聊天查看runtime-paused与relay-repeat各一条原输入和对应正式回复；`final-recovery-history.png`已实际打开检查，聊天身份/正文/时间及Work链接清楚。Scenario 1/4/5由技术原始事实和独立产品可见结果闭合。

最终product source更新为`a1b5b15e2982382539e8e5498d1cdd033cbda00e`，仅Work pending唯一查找性能细化；前一轮负载未作为通过依据。继续等待最终栈确认与十分钟负载结果。

Round 5最终构建最小复验：caller确认center69512/Node69531从a1b源码和build指纹fc088dbfb592重启，Web亦重建。独立reviewer于22:56通过c_52e69qwg普通输入框发送“最终构建恢复后普通交办：请确认收到这条消息。”，同分钟见一条`FIXTURE630_OK`正式回复，截图`final-followup.png`及快照`final-followup.txt`已保存，截图已实际查看。结合精确故障窗口、本机原始计数和历史UI观察，A3关闭、Scenario 7 pass。最初失效的旧DOM ref未发送任何内容，重新抓取后成功发送一次。

本轮本人浏览器已关闭，未启动或终止caller服务；当前唯一待闭合项是Scenario 10的最终V7持续负载。

## Round 6：最终持续负载核对与收口

独立读取`.e2e-load-result-final-pass.json`与已提交technical-acceptance最终V7：100真实WS节点，20个Work节点按每节点96 KiB/s持续上传，20条普通消息/秒，with-Work有效600秒（含结算601.441秒）。12,000条sent/stored/received全等，无重复或消息错误；save p99=254.07ms、durable receive p99=253.86ms，相对保留无Work基线55.51/53.71ms增量198.56/200.15ms，分别满足1秒/2秒及各500ms增量要求。20上传者提交65,330事件，accepted HTTP body总计1,047,824,074字节；329次Work-only busy按Retry-After恢复，不影响消息计数。Scenario10 → pass，A1关闭。

版本与保留范围：最终用户侧普通输入框复验见Round5，运行product source为a1b；整合执行基线为536d5a29fd449de5da7ef8c29030c1868d91567a。Round1的3/6/8/13、Round2的11、Round3的2/12及ACK补证、Round4的完整Work展开均按其实际版本保留，未冒称在a1b重跑；后续PA恢复和Work pending查找变更不修改这些UI/权限/发送attempt契约。受影响的恢复路径由精确硬杀/通知链/唯一副作用记录、独立原聊天历史观察和a1b实际后续收发复验。无Work基线沿用未受Work-only触发器及未实例化PA恢复helper影响的原数据，技术报告明确其条件。

最终结论：13/13 pass；当前未关闭问题0。本人专属服务/代理/浏览器均清理，caller测试栈留由caller管理；未修改源码、测试或生产，未提交。
