# feat-738 永久删除 Agent 设计审查

## Round 1

- Reviewer：`/root/feat738_design_reviewer`，独立审查，未参与需求或技术方案编写。
- Target：`origin/develop` 基线 `ad77720d9`，文档提交 `3fd91496a` 加 index 中的三份修订。受审设计 blob `a4262fda6`，首文档 `3ef1d804c`，Gateway delta `6e944994`，IM delta `5f941649`，M1 空骨架。
- review_mode：`full`。本轮为首次 Gate 2，覆盖完整需求、设计、delta 与 M1。
- started_at：`2026-11-09T11:46:25+08:00`
- completed_at：`2026-11-09T11:51:13+08:00`
- duration：4 分 48 秒。
- Verdict：**Issues Found**。**2 CRITICAL / 5 WARNING**。

### Coverage 与证据

- **授权、现状和职责。** [IM lifecycle](../../../apps/im-server/src/agent-lifecycle.ts) 在事务中推进 intent revision，独立接受节点停止回执，并关闭投递、Task 和权限入口。[Gateway 注册](../../../apps/im-server/src/gateway.ts#L268) 对已存在 profile 恢复 availability。[Node 产品组装](../../../apps/node/src/main.ts#L104) 从共享 ordinary 分区启动 DSH，通过 integration client 安装生命周期与绑定。复用真人 owner 检查、停止证明、中心控制通道及配置原子写入成立。删除增加独立操作记录以保存范围、清理阶段和不可逆回执，适合由 IM 和 Node 各自承担。DSH 专用能力放在 integration 内，清理调用可走既有 stdio。恢复和共享写入的缺口见 R1-C1、R1-C2、R1-W3。
- **原生会话与运行时边界。** 独立核对了本机锁定的 DSH `0.2.1-alpha.1` 包公开类型和实际 JS。JSONL 包的根 export 提供 `resolveCurrentLog` 和 `acquireWriteLease`，后者在 session 的 cwd 派生目录上锁。基础持久化服务没有删除方法。官方投影缓存根 export 提供 `SessionProjectionCache`，`write` 在 flush 后异步提交，`coldSnapshot` 有独立的写回。通过 [Nano profile 的正常 Cordis 装配](../../../packages/dsh-integration/src/client.ts#L17) 扩展官方公开服务，限定删除到目标 session，避免修改安装包或私有导入。该方案仍需以固定版真实产品装配验证官方缓存事件和其他 Agent 冷读。R1-W1 记录归属完整性的已知缺口。
- **用户明确的隔离约束。** [需求](spec.md)与修订后的 [design](design.md#在共享进程内逐个清理已关闭的目标会话)都保留 B 在途执行、任务准入和历史读取，删除前置只看 A 的停止和归属。目标会话租约、目标缓存 fence、目标观察连接是正确粒度。产品验收应在 A 清理实际进行时发出 B 新输入、读取 B 冷历史，并对账 B 原在途工作与 shared host PID，避免只测删除前后。将 R1-C1 的同一批旧 Work 上传和 R1-C2 的 B 配置交错加入窄验证。
- **Agent Context，设计模式。** [Node 运行时路由](../../../apps/node/src/runtime-partitions.ts#L244) 对 `session.export` 等只读路径绕过执行屏障，[Native 轨迹](../../../packages/dsh-integration/src/trajectory.ts#L50) 会打开冷 Session 和父链。删除需要新增目标读侧屏障和失效既有目标观察连接，范围按设计已分开。可复用当前工作 generation 对输入、续做和恢复的校验。受控 provider 应记录 A 旧投递与恢复无出站请求，同时记录 B 收到的输入及有权共享历史。保留的聊天材料需要明确排除拟清理的执行投影，见 R1-W2。
- **前端体验，设计模式。** 核对了 Web Agent 详情与 [渠道删除确认](../../../src/IM/frontend/src/features/settings/agents/agent-channels-panel.tsx)，以及 [iOS 管理页](../../../src/IM/ios/NanoIM/Features/Agents/AgentsView.swift)。独立查看 feat-657 本机留存的 [Web 390px 停用画面](/Users/czj/.codex/reports/feat-657-final-20261025/early-web-validation/web-390-disabled.png)和 [iOS 停用配置画面](/Users/czj/.codex/reports/feat-657-final-20261025/ios-config-disabled.png)。既有视图中可区分 Agent、节点和停止状态。按设计先显示身份与后果，再提供默认不勾选且列明路径的专用目录选项，复用现有确认和进度区足以对齐这一局部交互，无需单独 prototype。实施时仍须观察窄屏和原生 sheet 的长路径、主操作、失败恢复和完成返回。当前阶段未观察删除成品，旧链接与离线状态契约见 R1-W4、R1-W5。
- **Delta 与 M1。** Gateway/IM delta 路径镜像 canonical area，面向节点消费者和所有者表达新增行为。Gateway 停用原有保留历史 scenario 可以保留，随后明确永久删除的转移状态。IM 离线只读规则需同步修改，见 R1-W5。M1 骨架只含 `.gitkeep`，单项实现共用跨存储协议，避免让多个 worker 各写一半。无一次性部署迁移。
- **验收前置与证据界限。** 本机核实锁定 DSH 已安装、受支持的 Node `24.22.1` 位于 `~/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin/node`，默认 PATH 的 `25.8.2` 不满足仓库 engines。使用 `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` 可读到 iOS 26.4 iPhone 模拟器。daily 模板及本机选定的测试 YAML 包含相应测试模型条目，未请求 provider。隔离目录用同一个 `WT_ROOT` 承载 Node home 和清理暂存即可满足同卷要求。设计第 15–17 行的三个探针是作者报告的合成会话证据，未独立重跑。它们可说明技术切点，不证明旧代际完整性、并发产品流或异常恢复。未启动服务、修改运行数据或执行产品验收。

### Issues

#### R1-C1 · CRITICAL · Work 占位切换可能永久阻塞 B 的 Work 同步

位置：[design.md 第 60、79 行](design.md#通过真实归属生成清单按存储所有者清理)。

[中心 WorkSync](../../../apps/im-server/src/work-sync.ts#L134) 在 batch 追加前核对原始 payload hash，对分片也用相同 seq 与内容摘要做唯一校验。[节点 WorkSync](../../../packages/personal-assistant/src/work-sync.ts#L83) 对 HTTP 409 设置 pause，未被后续 `signal()` 解开。具体交错为 A 的旧分片已进入 PUT 并等待文件 I/O，IM 落 fence 并清除 A 暂存，Node 换上占位，同一 journal 后面还有 B 的正常记录。仅描述“旧上传无法写回”允许用 409 拒绝旧请求，或让旧请求使用删除前取得的 staging row 恢复 part 写入。替换占位也会与原已提交 hash 回执冲突。此时 A 的旧内容可能回写，或 B 后续历史永久停在 A 的序号。

修订需要明确 Node 与 IM 的同一切换协议。覆盖对已获授权的目标序号的旧 batch、部分分片及在途 finalize，规定不写旧内容且能继续推进的回执，定义 Node 在旧请求返回后如何丢弃旧 pending、重读游标并继续其他事件。指定对持有旧请求的重新校验点，并用 A/B 混合批、重试及其后的 B 事件验证。

#### R1-C2 · CRITICAL · 删除工作区的最终专属校验可与 B 的目录配置交错

位置：[design.md 第 73 行](design.md#工作区须有节点侧的专属证明)。

[NodeConfiguration](../../../apps/node/src/configuration.ts#L119) 的 prepare 在持久化前解析工作区并调用 `mkdir`，第 137 行串行化的是之后的 persist。[IM 创建入口](../../../apps/im-server/src/control-routes.ts#L185)支持新 Agent 的工作区选择。设计只冻结 A 配置并在删除时核对已见的根。A 校验完至实际递归清理之间，B 的创建可以在 A 目录或子目录准备，随后写入配置，A 则删掉 B 已选的工作区。文件身份见证本身不约束 B 的配置准入。

修订需要明确一个 Node 拥有的短临界区或路径占用。将所有受管 Agent 的相关 workspace 创建/选择、仍待应用的目录占用、A 的最后复核和安全摘除放入同一互斥边界。耗时文件回收可在摘除后进行，使 B 的执行、历史读取和新消息不等递归删除。M1 用真实配置入口制造该交错。

#### R1-W1 · WARNING · 公开 list 的成功不证明旧会话清单完整

位置：[design.md 第 52、66–69 行](design.md#通过真实归属生成清单按存储所有者清理)。

锁定 JSONL provider `listArtifacts` 跳过不支持格式和损坏 header，`list` 每个 ID 返回一份选中的快照。现行 [Descendants.read](../../../packages/dsh-integration/src/descendants.ts#L100) 会报告目录中无法读回的 child。[History.fork](../../../packages/personal-assistant/src/history.ts#L74) 在 DSH 生成分支后才保存产品绑定，current fork 契约明确不补偿已派发的远端 fork。因此，未写进 NodeStore 的分支和 header 不可读的已知冷子项都需要独立判据。对快照里能找到的每个条目归属正确，仍可能漏掉目标磁盘内容并误报完成。

修订应明确清单的核对来源、已知目标 ID 不在 list 时如何区分已不存在与不可读产物，以及如何判定有源 root、同 preset 的未完成分支和已终结 one-shot。将核对限定到有目标证据的资源，避免无关 Agent 的未知格式成为删除前置。提供包含真实锁定版旧代际、已知冷子项及未完成绑定分支的验证。

#### R1-W2 · WARNING · IM 聊天行和事件重放都存有拟清理的执行数据

位置：[design.md 第 48、58、80、84 行](design.md#通过真实归属生成清单按存储所有者清理)。

[消息读模型](../../../apps/im-server/src/message-records.ts#L125) 将工具、思考、审批和 `reply_process` 存入消息行，与正文和附件同时返回。部分同类内容也经 [持久聊天事件](../../../apps/im-server/src/message-records.ts#L54)和 [WS replay](../../../apps/im-server/src/gateway.ts#L218) 重放。设计同时承诺保留原消息和清除工具/权限历史，尚未说明同一消息的字段边界。只清 Work 会留下聊天内的执行记录，只改消息行会让重连拿到旧执行投影。

修订需要明确哪些字段和事件是保留的发布内容、哪些是随目标执行清理的投影，并定义现有事件序号和客户端缓存如何收敛。验证至少一条带工具或审批的普通 Agent 原消息，比较旧客户端重连与新加载，同时核实正文、作者及附件保留。

#### R1-W3 · WARNING · 同一 owner 恢复设备凭据后，删除操作没有可继续的 epoch 规则

位置：[design.md 第 46、48、78–79 行](design.md#接口与数据流)。

中心固定接受时的 binding epoch，并拒绝不匹配的回执。这能拒绝过期连接和其他设备。现行 [同设备恢复](../../../apps/im-server/src/identity.ts#L995) 在 owner 和 node 保持一致时仍递增 `node_epoch`。若删除已落盘，旧凭据失效后只能通过新 epoch 重连，原操作会持续等待或拒绝完成。对设备转移设置互斥也不覆盖同一 owner 的恢复。另需区分完成后历史身份与 [设备转移](../../../apps/im-server/src/identity.ts#L884) 当前按 `node_id` 批量快照和转 owner 的行为，避免原 owner 的历史回执跟随设备转移。

修订应定义同设备、同 owner 凭据恢复后的授权接续规则，沿用原操作 ID 和清理范围，同时继续拒绝旧连接回执。明确已删除身份和回执如何排除在可转移 Agent 集合外。验收加入落盘后断连、恢复凭据再回执。

#### R1-W4 · WARNING · 已删 Work 链接缺少可继续执行原权限判断的最小索引

位置：[design.md 第 48、58、80 行](design.md#接口与数据流)。

设计列出的永久字段没有说明 Work/轨迹定位如何在执行行移除后解析。[Work routes](../../../apps/im-server/src/work.ts#L386) 先取活跃 profile 再定位 session，原生 [Trajectory](../../../apps/im-server/src/trajectory.ts#L63) 还需要 Work session 链。聊天上的 [View Work](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L1992) 以原消息 ID 进入 Agent 详情。移除投影后沿用原查询会先拒绝。反过来只凭已删 Agent ID 返回删除提示，无法证明指定 session 或消息属于该 Agent。

修订应说明如何用保留聊天关联或无执行内容的最小历史索引解析旧链接并重新检查原有空间、聊天或 Work 权限。用一个旧消息入口和一个轨迹 session 链接验证有权可辨、无权及伪造 ID 不可探测。

#### R1-W5 · WARNING · 新的离线删除例外与现行 IM 只读契约冲突

位置：[design.md 第 77 行](design.md#接口与数据流) 与 [IM delta](specs/im/agents-nodes.md)。

方案允许最后一次认证表明支持删除的已停止 Agent 在离线时提交或重试持久删除请求。[现行 IM 离线设置契约](../../specs/im/agents-nodes.md#requirement-agent-设置与外部渠道离线时保持可读并统一只读恢复后刷新再解锁) 明确禁用所有写入和节点操作，只为独立停用保留例外。新增 Requirement 只描述等待/失败，未更改这个既有前置，客户端可能在离线配置页按旧规则禁用删除入口。

在 IM delta 补 MODIFIED，保留现行离线设置的其余 scenario，明确删除的提交、重试和已确认范围条件。将认证过的已停止目标离线提交、等待并重连列为产品入口用例。

### 历史问题闭环

首轮，无历史 issues。

### Recommendations

无。

### Author Resolutions

| ID | 处置 | 证据与修改 |
|---|---|---|
| R1-C1 | accepted | WorkSync 把摘要冲突视作全节点暂停。设计增加精确去内容回执，先在中心落回执再替换节点事件。旧 batch、分片和占位通过同一响应收敛，跨文件 I/O 后重新核验，节点刷新游标后继续。验证包含后续 B 的历史。 |
| R1-C2 | accepted | `NodeConfiguration.resolve` 的目录准备早于配置持久化。设计用同一节点目录占用边界约束配置准备与删除摘除，递归回收留在边界外。 |
| R1-W1 | accepted | JSONL 列举的确会跳过部分坏记录。清单补充已知会话种子、逐 ID 物理核对、可信旧 fork/冷子项归属及无法读取时的失败语义。 |
| R1-W2 | accepted | 聊天行和回放事件均有过程内容。设计明确发布内容的保留字段、执行投影的清理字段，并走两端已有的快照对账入口。 |
| R1-W3 | accepted | 同 owner 的设备恢复会旋转 epoch。设计在原恢复事务接续未完成删除，设备转移排除已删除身份及回执。 |
| R1-W4 | accepted | 旧链接需知道精确的原会话或消息归属。设计保留不含执行内容的定位索引，并要求按原空间及现行权限查验。 |
| R1-W5 | accepted | 原方案的离线提交不是首文档要求。设计改为在线首次确认及手动重试，已受理操作掉线可查询并在重连后恢复。因此现行离线只读契约仍适用。 |

## Round 2

- Reviewer：`/root/feat738_design_reviewer`，沿用 R1 独立 reviewer。
- Target：`origin/develop` 基线 `ad77720d9`，文档提交 `3fd91496a`。从 index 核对 design blob `48eacca4`、含 Author Resolutions 的报告 blob `9f2f3650`。首文档、Gateway/IM delta、M1 骨架与 R1 相同。
- review_mode：`delta`。删除授权、产品目标及共享运行时拓扑未变。本轮检查 Work 传输和缓存协调、旧数据归属、目录占用、设备授权接续及历史索引的有界修订，并重新核对这些机制的现有调用方。
- retained_from：Round 1。沿用已核实的正常产品装配、锁定 DSH 公开接口、目标缓存写入切点、前端既有入口、模拟器及隔离资源前置。未重跑作者的合成探针，未做产品验收。
- started_at：`2026-11-09T11:54:17+08:00`
- completed_at：`2026-11-09T11:56:38+08:00`
- duration：2 分 21 秒。
- Verdict：**Issues Found**。**0 CRITICAL / 2 WARNING**，含 1 项历史问题仍未闭合。

### Coverage 与历史问题闭环

| ID | Author Resolution | 本轮证据与结论 |
|---|---|---|
| R1-C1 | 持久化精确去内容回执后才替换本地事件，匹配的旧上传成功收敛 | [design 第 62 行](design.md#通过真实归属生成清单按存储所有者清理)明确摘要前判定、旧分片在回执和 finalize 前复核、已提交水位不回退、节点重读游标并继续。按目标事件处理可保留同一批的 B 事件，原 409 全节点暂停路径已闭合。新增协议另需确定尚未提交位置的归属来源，见 R2-W1。**closed** |
| R1-C2 | 目录预留、最终复核及原子摘除共用 Node 边界 | [design 第 77 行](design.md#工作区须有节点侧的专属证明)在 `prepare/mkdir` 前预留所有当前和待应用配置的路径，封闭了 [NodeConfiguration](../../../apps/node/src/configuration.ts#L118) 中准备与持久化之间的窗口。A 已摘除后只在私有暂存范围做慢回收，B 的配置与执行不等回收。**closed** |
| R1-W1 | 可信种子、list 扩展、逐 ID 核对物理产物 | [design 第 52–54 行](design.md#通过真实归属生成清单按存储所有者清理)对已知冷子项和旧分支定义归属证据。已知 ID 没出现在 list 时不会直接记成功，有实体且身份未证实则明确失败。其他 Agent 的独立绑定优先，无归属证据的目录不进入目标判断。旧代际、漏报已知 ID 和未落绑定 fork 已进入 M1 样本。**closed** |
| R1-W2 | 定义正文与执行投影的字段边界，清理消息行和 replay，并复用客户端对账 | [design 第 64 行](design.md#通过真实归属生成清单按存储所有者清理)关闭了存储和事件字段的不确定性。现有 Web 对账与 iOS resync 仍可保留清理前的执行字段，复用点需要补充针对旧缓存的失效语义。见下文。**still-open** |
| R1-W3 | 同 owner 凭据恢复推进授权 epoch，转移排除历史身份和回执 | [design 第 48、82 行](design.md#接口与数据流)覆盖 [同设备凭据恢复](../../../apps/im-server/src/identity.ts#L995) 与 [转移](../../../apps/im-server/src/identity.ts#L884) 的实际分叉。中心在原恢复事务更新当前 epoch，仍凭同一操作和范围认领，并拒绝旧连接。**closed** |
| R1-W4 | 先存精确定位，再按原空间和现行权限解释旧链接 | [design 第 84 行](design.md#接口与数据流)保存 session/root 与关联消息或会话身份，命中后才应用 [Work](../../../apps/im-server/src/work.ts#L386)、[Trajectory](../../../apps/im-server/src/trajectory.ts#L63) 或消息入口的 ACL。无权与伪造定位同样未找到。**closed** |
| R1-W5 | 首次确认及手动重试在线，已受理操作掉线后只读并自动恢复 | [design 第 81 行](design.md#接口与数据流)保留原离线只读契约。现有 IM delta 的等待 scenario 从已确认操作开始，无须引入离线新写入例外。验收改为先确认再断线。**closed** |

[design 第 98–100 行](design.md#本次审查安排)已安排真实入口、同进程双 Agent、混合 Work、真实配置竞争、冷代际和权限恢复验证。实施阶段应把 B 的新输入和冷历史读取放在 A 实际清理和重连恢复期间，同一 PID 对账。普通连接同步只恢复目标屏障，长时间清理从目标操作继续。该行为与现有 [Node 全局 lifecycleSync](../../../apps/node/src/main.ts#L180) 的每帧等待范围不同，不能把 A 清理本身放入此等待。

### Issues

#### R1-W2 · WARNING · 已对账或重新同步的聊天仍可恢复清理前的执行字段

位置：[design 第 64、99 行](design.md#通过真实归属生成清单按存储所有者清理)。

Web 的 [`message.reconciled` reducer](../../../src/IM/frontend/src/features/chat/chat-stream-reducer.ts#L190)能替换当前消息，但 [REST 历史恢复](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L567)会从独立 `tokenUsageCache` 回填旧计量。重连超出 replay 窗口时也会走 [REST 合并](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L111)，后者保留本地权限、回复过程和后台结果。iOS 收到 [`resync_required`](../../../src/IM/ios/NanoIM/Features/Chat/ChatStore.swift#L101)仅重置 cursor 并重读最近页。[iOS 的 loadChat](../../../src/IM/ios/NanoIM/Features/Chat/ChatStore.swift#L229)遇到一条旧 ID 就停止补页，[TimelineMerge](../../../src/IM/ios/NanoIM/Features/Chat/ChatModels.swift#L157)继续保留没有重新取得的较早消息。该消息的执行过程仍会在 [ChatMessageView](../../../src/IM/ios/NanoIM/Features/Chat/ChatMessageView.swift#L117)显示。

补充一个按受影响会话或消息失效执行字段的明确客户端契约，覆盖在线通知和 replay 窗口外恢复，防止缓存或删除前在途快照回填。验证 Web 收到清理事件后再触发 REST 刷新，以及 iOS 先缓存早于最新页的旧消息、清理后再打开该页。验证清理后的正文、发送者和附件仍可读。

#### R2-W1 · WARNING · 去内容回执缺少中心可使用的未提交事件归属判据

位置：[design 第 62、98 行](design.md#通过真实归属生成清单按存储所有者清理)。

新协议要求 IM 在登记精确位置时核对其目标归属。已提交的 [agent_work_events](../../../apps/im-server/src/work-records.ts#L154)有 `root_agent_id`。尚未提交的 [work_sync_uploads](../../../apps/im-server/src/work-sync.ts#L35)只有节点绑定、journal、seq、event ID 和摘要，分片内容完整后才解析归属。完全未上传的位置连 staging row 也没有。[知识维护事件](../../../packages/personal-assistant/src/knowledge.ts#L46)的 event ID 也并非统一包含可追溯的产品根。实际发生待传 A 事件位于 B 事件之前时，现方案没有定义 IM 用何证据核对归属。等待先上传原内容会拖住删除并让 B 卡在共享序号，直接按传来的位置去内容又缺少与已有归属或身份冲突时的明确决策。

写明已提交记录、仅分片及未上传记录各自的授权来源。对没有中心执行行的位置可以明确使用当前 binding 和删除操作授权下的节点清单，由 InboxStore 的 journal 生成，并校验所有现存回执与执行身份的冲突。这样可以在无需上传原执行内容的前提下推进。验收覆盖未提交 A 分片和其后 B 事件，以及申请覆盖已知 B 位置的拒绝。

### Recommendations

无。

### Author Resolutions

| ID | 处置 | 证据与修改 |
|---|---|---|
| R1-W2 | accepted | 现有合并及补页确实保留部分旧过程。设计明确会话执行投影的清理版本和旧分页、计量缓存失效，在线与重连均比较版本。验收覆盖旧分页、迟到请求与超出回放窗口。 |
| R2-W1 | accepted | 分片记录没有产品根。设计要求节点从 InboxStore 选目标事件，中心用现存 root、event ID 和回执拒绝冲突。未提交位置采用当前绑定及删除授权下的节点声明。验收覆盖未提交分片和尝试覆盖 B 的事件。 |

## Round 3

- Reviewer：`/root/feat738_design_reviewer`，沿用 R1、R2 独立 reviewer。
- Target：`origin/develop` 基线 `ad77720d9`，文档提交 `3fd91496a`。从 index 核对 design blob `a249241e`、含 R2 Author Resolutions 的报告 blob `37eb569f`。首文档、Gateway/IM delta、M1 骨架仍与 R1 相同。
- review_mode：`closure`。修订只涉及两项未关闭问题的原范围。核对会话清理版本的传递与缓存消费、Work 登记的归属证据，并检查对既有权限和同节点 B 连续性的影响。
- retained_from：Round 1、Round 2。会话归属清单、DSH 装配与公开边界、工作区占用、设备接续、历史链接 ACL、离线前置及 M1 资源结论保持有效，相关设计未变。
- started_at：`2026-11-09T11:57:49+08:00`
- completed_at：`2026-11-09T11:58:35+08:00`
- duration：46 秒。
- Verdict：**Approved**。**0 CRITICAL / 0 WARNING**。

### 历史问题闭环

| ID | Author Resolution | 本轮证据与结论 |
|---|---|---|
| R1-W2 | 以持久会话清理版本失效旧页、派生缓存和旧请求，在线和重连均比较版本 | [design 第 64 行](design.md#通过真实归属生成清单按存储所有者清理)把版本与消息行、持久事件清理置于同一事务。会话同步、历史分页及授权通知都携带版本。较新版本先失效全部旧页、计量与过程缓存，再从权威入口恢复阅读位置，旧请求不能进入合并。这覆盖 Web 的 [合并保留](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L111)与[计量回填](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L567)，也覆盖 iOS [仅补到已有页边界](../../../src/IM/ios/NanoIM/Features/Chat/ChatStore.swift#L229)的原路径。现有 [同步与历史 API](../../../apps/im-server/src/messaging.ts#L823) 可携带版本，历史 ACL 继续由 [原读路径](../../../apps/im-server/src/messaging.ts#L937)执行。超出 replay 窗口时先比对权威版本再复用缓存，避免依赖遗漏的在线事件。**closed** |
| R2-W1 | InboxStore 提供尚未提交位置的归属，中心独立核验已有身份 | [design 第 62 行](design.md#通过真实归属生成清单按存储所有者清理)要求节点从 [原 journal](../../../packages/personal-assistant/src/inbox.ts#L444)选取 root 属于目标的记录。中心验证当前授权，并以[已提交记录](../../../apps/im-server/src/work-records.ts#L154)中已有的 root 和 event ID 拒绝冲突。只有分片或尚未上传的位置使用授权清单，核对 [staging](../../../apps/im-server/src/work-sync.ts#L35)和现存回执。中心不必等上传旧执行内容即可发去内容回执。R2 已核对的前置 fence、I/O 后复核和连续序号规则仍有效，B 事件继续走普通校验。M1 覆盖未提交分片与 B 正常记录交错，并验证拒绝覆盖已知 B 归属的位置。**closed** |

### Coverage 与证据

修订限定在现有 IM/Node Work 所有者和 Web/iOS 聊天读取。消息清理版本只影响含目标执行投影的会话，中心保留 B 的持久聊天数据及原访问路径。Work 不依赖重新上传 A 原始内容，无节点级暂停或共享 host 维护步骤。沿用 R2 的验收要求，在同一进程内检查 A 实际清理时 B 的在途执行、新输入和冷历史。

本轮依据冻结设计与基线源码。未运行产品、未重跑合成探针。在线、旧分页、迟到请求、回放窗口外重连、旧分片与混合 journal 的结果仍由 M1 证据确认。

### Issues

无。

### Recommendations

无。
