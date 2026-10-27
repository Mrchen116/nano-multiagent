# Verification Report: feat-630

> **Pass — full verification complete. CRITICAL 0 / WARNING 0 / SUGGESTION 0.**
>
> Validation snapshot: `536d5a29fd449de5da7ef8c29030c1868d91567a → a1b5b15e2982382539e8e5498d1cdd033cbda00e` (product source and current frozen HEAD)

- verifier: `/root/feat630_static_review` (independent of implementation)
- verification_mode: `full`
- validated_at: `a1b5b15e2982382539e8e5498d1cdd033cbda00e`
- review_round: 1 (final after affected-delta closures)
- executed_base / effective_base: `536d5a29fd449de5da7ef8c29030c1868d91567a` (integrated main, final verification diff)
- original_implementation_base: `5665af409426f22eec86d03d68e6ffbb1c935d00` (historical initial implementation/review scope, retained separately)
- verdict: `Pass`; issues: `{critical:0, warning:0, suggestion:0}`
- corrected_delta_outcome: `aligned`
- branch/worktree: `unit/feat-630`, `/Users/czj/.codex/worktrees/unit-feat-630/nano-multiagent`
- requires_full_verification: false (already performing the full scope)
- scope: spec 全部 13 个 Scenario、design 八项决定和 V1–V8、全部五份 delta、M1 退出标准、相关 current specs、`SPEC.md`、测试与 evidence 规范。
- preservation: 只写本报告及 caller 明确要求的 code-review 增量报告；保留共享 checkout 的源码、测试、acceptance、output 与 runtime 文件。

## Summary

| 维度 | 当前结果 |
|---|---|
| Completeness | M1 1/1目标与退出证据完成；13/13原spec场景、五delta、V1–V8均有对应实现与直接证据 |
| Correctness | 原 code-review finding、公平 W1 与实际冷恢复 C2 已闭合；67e/883/432/a1b 增量未见新 confirmed 问题 |
| Coherence | 包职责与 DSH 公开边界一致；实时公平调度与数值 Retry-After 修正已核对；真实故障与完整V7同profile证据均成立，公开DSH/包边界及既有UI契约保持 |

## Completeness

单 M1 的所有目标已有对应实现，并已取得可复查的 V1–V8 及真实用户侧证据。unit/integration/contract、技术故障/负载与独立用户旅程分别记录，不互相替代。

复用证据：

| 证据 | 结果与版本边界 | 能力边界 |
|---|---|---|
| `.e2e-backend-final.log` | a1b，114 files、531/531 passed，完整suite bounded maxWorkers=2 | 后端/协议/runtime完整回归；精确kill与负载另有直接证据 |
| `.e2e-frontend-final.log` | a1b，102 files、949/949 passed，完整suite bounded maxWorkers=2 | Web组件/API/草稿恢复；真实浏览器另由reviewer记录 |
| `.e2e-python-final.log` | 62 passed、31 deselected | 非 e2e Python helper 与架构 gate；被 deselect 的 E2E 未被证明 |
| `.e2e-ruff-final.log` | check pass、83 files formatted | lint/format |
| `.e2e-build-frozen.log` | installer candidate 明确记录 19f16cb74fe9ec2112d928c31695a2640882f6cd | 构建；不等于产品验收 |
| `.e2e-build-final.log` / `.e2e-typecheck-final.log` | a1b build和全部packages typecheck通过；installer fc088dbfb592 | 最终构建和类型检查；不声称已部署 |
| `.e2e-pa-closure2.log` | PA 四文件 29/29 pass | 已知 code-review 修复和回归 |
| `.e2e-index-check.log` | bfb 索引增量真实 relay-recovery 2/2 pass | 离线/重连/终态与 scope 接线；不等于 V7 长负载 |
| `code-review.md` Round 3–7 | 19f 已知 finding 全部 closed；bfb 索引/631/632、2f fairness、67e/883/432/a1b recovery/commit delta 无新 confirmed finding | 代码审查；不替代本 full verification 或用户旅程 |
| `.e2e-pub-recovery.log` | 2 files、53/53 pass；67e/883/432 恢复修正 | interrupted、stop/completed/consumed、partial-consumed 和重复恢复、status-only publication |
| `.e2e-work-child.log` | 1 file、9/9 pass；ffdb | 完整 child tool 分块/归属及1000历史receipt物理changes |
| `technical-acceptance.md`、`.e2e-crash-evidence.jsonl`、`.e2e-crash-native-counts.json`、`.e2e-work-hash.json` | 实际公开 DSH/正常 Node CLI、四精确 kill 窗口、重复 recovery kill、runtime unavailable、12.58MB Work 与完整UI | V1/V2/V3 技术证据；不是独立产品 reviewer 最终裁决 |
| `acceptance.md` / `.e2e-review/` | reviewer实际文字/有效图片未知发送、离线、Work503、控制/权限、撤权/纠正、桌面/窄屏与a1b普通输入框复验；恢复A3已关闭 | 独立产品Round6最终13/13 pass、未关闭问题0；verifier不接管主观体验评分 |
| `.e2e-load-final-pass.log` / `M1-reliable-im/evidence/load-summary.json` | a1b，完整600s profile，12000/12000/12000，0重复/消息错误，p99 254.07/253.86ms | 仅下述明确硬件/96KiB每Work节点profile |
| `.e2e-audit-final.log` / `.e2e-docs-check-merged.log` | audit critical gate通过；docs 260 maintained sources/67 routes通过 | 非声称零全部severity依赖告警；归档后路径检查由caller执行 |

Prototype/Reference：design 明确没有新视觉原型；must-match 为沿用聊天/编辑器/消息列表/必要失败与授权入口、普通聊天不增加同步内部状态。产品 reviewer 持有对应真实截图/快照责任，本报告只核契约与证据定位。

## Correctness

| Requirement / Scenario | 实现位置 | 最低相关保护/补证 | 当前状态 |
|---|---|---|---|
| 大量历史待同步仍继续交办 | Node 独立 WorkSync 组装；GlobalAgent.receive/main/reconcile 不再 flushWork | relay-admission、work-sync、realtime-window；V1 >9MB积压、Work503和12.58MB实际工具事件 | covered |
| Work 暂不可用仍查询并回复 | 小 scope ensure＋query/send 本地 durable barrier；Work HTTP 独立 owner | global-agent、relay-admission；reviewer Work503 聊天已有局部证据 | covered |
| 节点离线期间发送消息 | Messaging.sendMessage 原子 message/relay 后成功；RelayDelivery 有界恢复 | message-attempts、e2e/relay-recovery；真实离线 UI 证据 | covered |
| Agent 运行时尚未恢复 | Inbox.acceptRelay 同事务保存输入与待回执，恢复后 wake | relay-admission；Node在线/DSH SIGSTOP持久接收，监督器自动重启后恢复 | covered |
| 接收确认丢失不重复交办/发布 | relay 身份、Inbox 唯一输入、稳定 runtime inputId、publications/status | inbox/global-agent/realtime-window；V2 原始/恢复 native input 与 write calls 各一次 | covered |
| 普通发送返回丢失/刷新/重试 | IndexedDB 不可变 attempt；lookup 后同 key 重发；按 message_id 合并 | chat-api、send-attempt-store、message-pane-send-attempt、workspace；reviewer真实浏览器文字/有效附件未知结果、刷新、新草稿/账号隔离均通过 | covered |
| 持久接收后节点重启 | Inbox、receipts、controls、wakes、publications/journal 保留 | V2 四精确 crash 窗口与两次 recovery kill；正常 CLI 重启 | covered |
| 同步期间停止/权限决定 | 控制保留槽、durable intent；single_thread 独立审批路径 | realtime-window、session-controls/single-thread、external；真实停止/授权局部证据 | covered |
| 大结果恢复后完整回看 | 有界批次/parts、hash、完整事件后原子 append/project | server/client work-sync，包含完整 parts 未 finalize 恢复；V3 真栈12.58MB tool事件、292事件hash及4MiB完整UI回看 | covered |
| 一个节点积压不拖住其他人 | HTTP 单节点/全局许可，WS 有界窗口/outbox，精确 pending 索引 | 100节点完整十分钟同profile通过；实际 caller Agent 公平偏离已闭合，见 W1 | covered; V7 passed |
| 排队期间失去访问资格 | runtime binding/epoch、专用 auth 两阶段、最终 part 再认证、relayEligible | work-sync权限/epoch/配额与现有auth回归；reviewer真实删除成员→queued relay cancelled且无回复 | covered |
| 回复前新纠正 | send 前本地 durable reconcile、Inbox blocking/read 承诺；status 查询不发布 | global-agent、personal/shared delivery 现有回归；reviewer真实148ms后纠正仅发布最新安排 | covered |
| 聊天简洁，保留必要入口 | 内部恢复；普通聊天未新增阶段枚举/同步面板 | Web suite＋真实桌面/窄屏截图；632 仅 Work 标题 | covered |

五份 delta 逐一核对：

- `specs/gateway/global-agent.md`：接收、查询回复、必要控制与 Work 独立的实现可定位；不因此放宽来源/新纠正。
- `specs/gateway/relay-protocol.md`：只有带精确 workSync route config 的三个路由使用 durable runtime token；消息镜像/附件等通用 principal 没有扩大。
- `specs/im/agent-work.md`：完整受支持大小数据进入原 Work 投影；parts ACK 不当事件 ACK；中心历史元数据不能激活旧 main。
- `specs/im/conversations-messages.md`：不可变本机发送身份、同 key 恢复、后续草稿版本与账号隔离；reviewer真实恢复场景与Round6最终13/13 pass已核对。
- `specs/im/gateway-relay.md`：离线保存不误报未保存、实时 ACK 相关性、终态单调、多目标独立；公平按 W1 已闭合，持续负载按下述V7已闭合。

明确实现定位（相对仓库，受审 a1b 行号）：`packages/personal-assistant/src/global-agent.ts:92` 接收、`:174` wake、`:205` interrupted恢复、`:284` 独立恢复、`:571`确认、`:580`publication查询；`packages/personal-assistant/src/inbox.ts:61`原子接收；`packages/personal-assistant/src/work-sync.ts:19`独立owner、`:149`parts；`apps/im-server/src/work-sync.ts:15`专用认证、`:28`许可/配额/路由、`:45`有界commit trigger；`apps/im-server/src/messaging.ts:526`保存消息、`:78`当前访问资格；`apps/im-server/src/gateway.ts:523`当前scope、`:529`只读publication状态；`apps/im-server/src/relay-delivery.ts:4`中心有界replay；`packages/channels/src/index.ts:133`实时请求相关性/窗口。Web实现为 `src/IM/frontend/src/features/chat/components/send-attempt-store.ts`、同目录`message-pane.tsx`及`../chat-api.ts`，对应IndexedDB和POST/lookup的现有定向测试及真实浏览器证据。

## Coherence

| design 决策 | 核对 | 实际证据 |
|---|---|---|
| 1 本地先收，receipt/wake/Work 各自恢复 | aligned | Inbox.acceptRelay、GlobalAgent 独立 drain/recovery；V2 四精确窗口及重复 recovery kill |
| 2 Work 独立 HTTP | aligned | WorkSync 隐藏批次/parts/backoff；Node start/stop；实时业务无 bulk flush |
| 3 session 权威与历史分离 | aligned | agent.session.ensure；historical global_main 只登记 retired；scope 真实进程回归 |
| 4 request_id/generation、有界并发、按 Agent 轮转 | aligned after fix | correlation/control slots 已保护；真实 publication 身份和三 Agent 轮转经 W1 修正及自测闭合 |
| 5 有界 outbox、单调 receipt、按 Agent 轮转 | aligned after fix | 每 node32、读取256、终态单调；三 Agent 在有界候选集内轮转经新回归保护 |
| 6 字节/许可/配额/TTL/重组上限 | aligned mechanism | product-contracts limits、Work HTTP permits/parts/hash；server 429 提供 Retry-After=1；client 在 2f/62f 已读取数值 header 并作为最小等待，真实 429/2s 回归通过；完整V7已通过，容量结论限定明确profile |
| 7 普通 Web 不可变 attempt | aligned mechanism | 首 POST 前 IndexedDB；未知结果查/同 key 重试；confirmed 只清原草稿版本；真实用户证据已核对 |
| 8 一个完整 M1，不新增中心体系 | aligned architecture and exit | 复用 SQLite/journal/Work；无 broker、第二执行 loop 或 DSH private imports |

Prototype / Reference Contract：design未新增原型或新布局（N/A新视觉稿）；明确must-match是保持现有聊天层级/Work入口、正常与自动恢复不出现内部同步状态。M1/V8投影、既有message-pane/Work路由、acceptance.md桌面1200×727与窄屏390×844实际截图/操作证据匹配；主观体验质量由独立reviewer负责。

架构与受影响 main delta：`SPEC.md` 的 Channels/PA/IM/Node 依赖方向保持。bfb 的 schema 三个索引通过真实查询计划核对为 `SEARCH relay_tasks USING INDEX relay_tasks_pending_node (target_node_id=?)`；bugfix-631 在 idle observe 后重取 background，避免已消费 batch 的 stale wake；632 的 Web/iOS 只映射既有 inbox-background 触发，普通 Inbox 保持原分类。索引/631/632 的独立 patch review 已追加 `code-review.md` Round 4。

## Issues / closed historical findings

### Current issue counts

CRITICAL 0 / WARNING 0 / SUGGESTION 0。C1的退出补证已完成：V1/V2/V3直接事实、完整V7原始计数/阈值以及独立reviewer的最终构建可见结果均已核对。早期acceptance的fail/inconclusive是历史过程，不把旧版本恢复缺陷隐藏为通过。

### CRITICAL — closed actual recovery failure

- **C2 / closed at 883/432; historical failure at 2f and incomplete 67e**：真实 after-submit 在原 inputId durable accepted、wake 未落盘时 SIGKILL，旧 DSH 重启将 turn 记 interrupted；原 inputId dedup 不重入模型，Inbox 未读。67e 通过公开 lookup/submit 仅恢复仍未读 interrupted 通知，每次以原 acceptedSeq 派生独立稳定恢复身份；实际单次及连续两次恢复 kill 已证各 ID 用户通知一次、一个成功 write call、一个正式回复。verifier 另在固定67e复现 coalesced A1/B2 只消费 B2 后错误 lookup :1，883/432 改用 max(历史attention, admittedWake)，在 ffdb 独立原探针现 lookup :2→:2:recovery:10 并 submit 正确恢复身份。user/completed/consumed 不自动继续由参数化回归保护。after-publication 重启只查原 operation status，found 后本地确认+同一 Work 事实，不重发原工具、不伪造 native completed；pending publication 独立分支不被 interrupted/不可恢复主任务阻断。参见 code-review Round6、`.e2e-pub-recovery.log` 和 technical-acceptance.md。此项已无待实施修正。

### WARNING — closed design mismatch

- **W1 / closed at 62f; historical failure at bfb**：Channels 根据 payload.agent_id 选择不同于 lastAgent 的普通请求，但真实 GlobalAgent/PersonalAssistant 的 agent.message 使用 from_session_id 携带 Agent 身份，不提供 agent_id；所有普通外发落同一空字符串身份。固定 bfb Channels 的真实 WS 复现排入 A0..A15 和 B0：前六普通槽 A0..A5，占满后释放一槽发送 A6，B0 继续在尾部，违背 `design.md:90` 和同节点其他 Agent 不等待积压的约束。定位：bfb `packages/channels/src/index.ts:245`、`:250`，实际 caller `packages/personal-assistant/src/global-agent.ts:539`。必须在实际发送边界提取/提供稳定 Agent 调度身份，并以真实 caller 字段保护公平性。另单纯“选择不同于 lastAgent”只能在两 Agent 间交替，三 Agent 的 A/B 批量可使 C 持续排尾；RelayDelivery 同样使用该选择方式。最低必要修复应覆盖实际字段和至少三 Agent 轮转，而非仅两 Agent 特例。已由 2f/62f 修正并完成 delta 核验：真实 WS 源码快照在 A/B 积压与 C 单条的队列释放三个普通槽后发送 B0、C0、A6；center 三 Agent 回归通过，见 code-review Round 5。

### SUGGESTION

无额外维护建议。Retry-After 服务端契约与 client 数值等待下界均已核对；不因推测其他服务端格式增加兼容层。

## Technical evidence — V1–V8 verified

已读取 `technical-acceptance.md` 及实际 driver、原始计数/hash、回归日志，核对版本边界。真实运行使用官方 DSH0.2.1-alpha.1，通过 `@nano/dsh-integration/client` 和公开 RuntimePort/Relay seam 冻结隔离进程；SIGKILL 后由正常 Node CLI 使用保留配置重启，没有手改持久成功/水位，也没有替代 loop。

- **V1**：Work HTTP 持续503期间，真实工具形成 >9MB历史；12,583,671/12,583,832字节 tool_start/end 仍在支持16MiB envelope内，普通查询/正式回复和 reviewer 的133ms stop/权限交互正常。不是小日志模拟积压。
- **V2**：before-submit seq8、after-submit seq9（原 acceptedSeq422、恢复434再次被 kill）、after-receipt seq10（中心ACK已应用、本地confirmed0）、after-publication seq11（中心原message976859…已提交、本地sending）均在精确公开 seam 冻结后强杀、正常CLI重启。对应 Inbox/read水位、receipt或publication后续状态、正式回复增量、成功write call均可定位。原始与每次恢复通知在 native history各一个user_message，所有 crash effect tool/call成功各一次；不能只凭固定文件存在推断一次执行。Node在线、DSH SIGSTOP时seq12先持久接收，监督器重启runtime后自动处理，补齐runtime unavailable分支。after-publication 保持 native interrupted/failed receipt 真实状态，不冒充模型已完成，但原外发已正确confirmed，正式消息不重发。
- **V3**：292个本地/远端事件的seq/event_id/root/session/turn/type/time/payload完全一致，canonical SHA `c0389cde56aa06e74a6c92a5202928d9af6fdc6b6b8457a85cad4815b4aa4c3f`；4MiB实际write内容SHA `b14138a3ca83b79cc5b448a07ab8d1dd9e1220652bc0ca1b248c15c12b9e5a68`，reviewer在既有Work入口展开完整正文。主session真实大工具和child106KiB完整参数/parent scope回归各自有证据，不混称真实子session大工具。服务端restart/out-of-order/hash/epoch/quota/TTL/atomic和client4MiB/fullparts-finalize/cursor/16MiB/abort均有最窄现有回归。
- **Retained V4/V5/V6/V8**：WS真实相关性/公平/有界window、40消息真实process重连/单调终态、权限纠正及Web attempt已按既有证据与受影响源码保留。Web最终用户旅程与must-match仍由独立reviewer裁决。当前恢复/trigger增量没有改Web attempt、布局、control业务解析或授权边界；无需全套机械重跑。

独立静态窄探针 `node --import tsx /tmp/feat630-fairness-check.mts`（bfb）包含公平失败与索引查询计划；`node --import tsx /tmp/feat630-coalesced-closure.mts`（ffdb）闭合部分消费恢复。临时WS和数据库已关闭；临时脚本不冒充长期套件或V7容量证据。

## Supplemental protocol and fix evidence

- `node --import tsx /tmp/feat630-protocol-check.mts`，Channels 来自 bfb git archive（后续 2f/62f 未改 capability/correlation）：新 Node 面对无 capability 的旧中心，只发 node.register，start 返回 rejected/upgrade_required 且 state=upgrade_required，60ms 后没有重试或业务帧；新中心两个同 type agent.message 并发、逆序 ACK 时，distinct request IDs=true，a→a、b→b，state=ready。旧 Node→新中心的协议兼容由现有 raw Frames process relay-recovery 支持，未声称运行历史旧 Node 二进制。
- `node --import tsx /tmp/feat630-fairness-closure.mts`，Channels 来自 62f git archive：初始 A0..A5，nextThree=[B0,C0,A6]，W1 已闭合。源码增加本服务数值 Retry-After 读取，`.e2e-fairness-retry.log` 的真实 429/2 秒回归通过；`.e2e-center-fairness.log` 保护中心三 Agent 轮转。
- V1/V2/V3已由上节实际技术交接补齐；完整V7与a1b独立UI复验也已交接，本报告据全部证据收口。

### V7 environment/profile and final result

Apple M3、8CPU、24GiB RAM、macOS、Node25.8.2；一个真实中心进程、100真实WS节点及100持久Inbox，20 Work节点持续补充100event批次（稳态1,562,844 UTF8 bytes、最大event108,732含106KiB字段），其余80节点共20普通消息/秒。仅WorkHTTP每节点96KiB/s（总上限约1.875MiB/s），chatHTTP/WS不限速。批准V7没有Work最低/无限吞吐要求；所有原始消息速率、20持续上传、600秒及阈值均保持。结论限定该profile，不宣称无限吞吐或生产容量。

最终a1b在全量CI结束后独立运行，原始`.e2e-load-result-final-pass.json`与归档聚合`M1-reliable-im/evidence/load-summary.json`一致。无Work基线来自2f：后续PA恢复helper未被load client实例化，center增量仅Worktrigger、在无Work时不执行；同机/相同HTTP/WS接线，故可保留。独立重算：

| 指标 | 无Work基线 | 最终20 Work流 | 原阈值 |
|---|---:|---:|---:|
| sent/stored/durably received | 12000/12000/12000 | 12000/12000/12000 | 相等 |
| 完整phase及settlement | 601023.75ms | 601440.53ms | active600s |
| save p99 | 55.509292ms | 254.065667ms | <=1000ms |
| accept p99 | 53.712209ms | 253.858334ms | <=2000ms |
| p99增量 | — | save198.556375ms/accept200.146125ms | 各<=500ms |
| duplicate/message error | 0/0 | 0/0 | 0 |

Work提交65,330events、acceptedHTTPbody总1,047,824,074bytes（逐node总数独立求和）；9个分钟快照中20节点每次都前进。329次Work-only429 busy按Retry-After重试，未影响消息完整性。已有window/许可/单pending/配额回归与实际持续进度共同支持有界恢复；429不被掩饰成“零任何错误”。

历史失败保留：无索引p99>8.5s；未限速磁盘耗尽运行；初次固定profile p99736.44/736.21ms超过+500ms；432改后约7分钟被终止。它们均不是通过证据。a1b进一步将trigger查找限定到唯一pending ID，实际EXPLAIN与完整最终load共同闭合必要性能修复；未放宽任何设计阈值。

### a1b affected/retained delta

`ffdb..a1b5b15e2982382539e8e5498d1cdd033cbda00e` 仅收敛Work commit trigger的SQL查找；前轮C2、公平W1、V1/V2/V3、Web/权限等证据全部保留。独立node:sqlite EXPLAIN用1000retained receipt证实外层主键id查询、子查询work_sync_one_pending(node_id=?)，错误journal或未达到seq均不更新、正常一次commit、重试0变化。`.e2e-last-focused.log` serverWork+GlobalAgent53/53通过；code-review Round7无新confirmed问题。旧432的约7分钟负载被主动终止，明确不是最终通过证据。最终a1b完整十分钟已在全量回归结束后独立运行并通过，避免把CI竞争混入测量。

V2/Scenario5新增实际重投补证已核对technical-acceptance.md：阻断的是出站receipt帧本身，中心真实WS重投同relay b9705a44…六次，Inbox seq13/message ad581d52…只一行，一次native通知、一个成功write call、一个正式回复；释放receipt后中心completed、本机confirmed。它补齐了“只有ACK丢失但中心并未重投”的证据边界，原精确crash四窗继续保留。


## Corrected Delta Reconciliation

- verification_mode: `corrected-delta`（并入本次full verification；本节独立outcome为aligned，full结论另结合V1–V8及产品证据）
- implementation snapshot: `a1b5b15e2982382539e8e5498d1cdd033cbda00e`
- delta snapshot: caller于该HEAD上的四份未提交校正全文；需求spec/design未改。已读取全部五份delta并与unit完整对外diff及相关现存契约比对。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/conversations-messages.md` 本人attempt GET与409快照冲突 | `apps/im-server/src/message-attempts.ts:35`仅human、当前access/is_member、sender_user_id本人；`:25`比sender/type/canonical正文附件背景；`messaging.ts:562`命中旧key先比较再返回；Web `chat-api.ts:128`与不可变attempt存储按原key/快照核对重试 | message-attempts真实route注入本人/他人/撤销/机器与canonical/4类409；Web定向及真实刷新/attachment/新草稿/账号切换证据保留 | aligned |
| `specs/im/agent-work.md` >16MiB完整事件保留本机 | product-contracts work-sync.ts:8定义16MiB；PA work-sync.ts:151完整UTF8编码后判限，`:65`onError并pause，不ack、不截断，后续seq不跨越；既有本机原生轨迹入口未改 | work-sync `events beyond 16 MiB remain local...`保护只有GET/明确event_too_large/through0/journal1；真实12.58MB支持范围和4MiB完整UI证明另一侧边界 | aligned |
| `specs/gateway/global-agent.md` 未读中断/部分消费边界/主动停止 | global-agent.ts:205公开lookup terminal.kind严格interrupted，未读guard、max历史与admitted边界、稳定恢复ID；非interrupted及已消费不submit，原消息和通知保留 | 参数化interrupted/user/completed/consumed/partially-consumed与多次恢复；独立coalesced故障→closure探针；V2真实精确kill/重复kill与native唯一计数 | aligned |
| `specs/gateway/relay-protocol.md` 新Node遇旧中心要求升级 | apps/node/src/main.ts:136要求两个capability；Channels index.ts:203缺失即停止连接/请求并upgrade_required，不走旧bulk flush；Inbox/journal未删除 | 独立真实WS旧中心探针只见node.register、state upgrade_required、delivery rejected且无业务帧/重试；现有capability/correlation回归 | aligned |
| `specs/im/gateway-relay.md`（完整复查、未校正） | 持久消息/relay、独立HTTP当前binding/epoch授权、scope ensure、receipt单调和相关性/按Agent有界窗口，已在本full各场景/design表定位；不新增入口权限 | 真实relay-recovery40消息、6次实际重投唯一处理、权限撤销、runtime unavailable、WS相关性/公平/upgrade；完整V7同profile已通过 | aligned |

### Uncovered Observable Behavior

None。五份delta均已完整核对：Work专用三路由授权、可恢复离线保存、same-type ACK归属、scope权威与历史分离、未知外发status核对、必要控制、普通Web不可变attempt的新增/改变行为均被相应Requirement/Scenario涵盖。分块/hash/许可/配额/TTL/退避/索引/SQL查找为已批准design的实现约束，没有额外对外能力或权限扩张。permission_resolved的nested业务ID迁移保持既有取消/卡片行为，已审消费方并回归；631/632来自已归档main修复、current agent-work已有相应标题，不冒充feat新增未描述能力。未发现需要新增delta的遗漏行为。

Outcome: **aligned**。本节0 delta-mismatch、0 implementation-mismatch；完整负载与产品证据已另按C1闭合，不以校正delta替代验收。


## Final resolution

Full verification **Pass** at a1b；13/13原spec场景、全部五delta（包括四份校正）与单M1的V1–V8退出标准均有实现及适用直接证据。历史confirmed代码与恢复/公平问题已独立闭合，Round7代码审查保留Pass，corrected-delta **aligned**，当前无CRITICAL/WARNING。报告以集成main536为本次executed/effective base；原实施5665和每轮固定版本保留以便追溯。仅写本报告和code-review.md；未修改源码/测试/配置、未提交。独立临时服务/数据库均已关闭；caller持有并负责清理其隔离产品/负载现场。归档仅移动文档路径不改变受审产品源码；若新增产品修改须按实际影响补验。
