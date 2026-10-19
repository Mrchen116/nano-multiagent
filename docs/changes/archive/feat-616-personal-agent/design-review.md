# Design Review — feat-616-personal-agent

## Round 1

### Metadata

- reviewer target: `change-design-reviewer`，独立 native reviewer `/root/prepare_pa_implementation_gates/review_pa_design_gate`；未参与受审 spec、design、prototype、delta 或研究产物的编写。
- dispatch: 按仓库 Codex 执行适配派发独立 reviewer，使用父级配置；仅写本报告，不改设计或产品，不建分支、不提交。
- review_mode: `full`
- mode_reason: 首轮，需独立覆盖需求、真实生产组装、共享接口/权限、体验、canonical delta 与 milestone；没有可继承的历史审查结论。
- started_at: `2026-10-16T17:29:09Z`
- completed_at: `2026-10-16T17:41:59Z`
- duration: `12m 50s`
- executed_base: `481467ac16f0eda4561fca5c8230050541600de9`（本地 `main` HEAD 与 `refs/remotes/origin/main` 一致；本轮未声称重新获取远端）。
- validated_at: 当轮 HEAD 加未提交的 R1 冻结设计工作树；当时逐文件校验 11/11 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- 工作树：审查开始时仅 `?? docs/changes/feat-616-personal-agent/`；本报告为审查输出，不在受审 manifest 中。研究记录是旁证，不替代冻结设计或执行验证。

### Verdict

**Issues Found — 0 CRITICAL / 8 WARNING。Gate 2 不通过。**

- `R1-W1` 至 `R1-W6` 是可自主修订的实质设计/契约/交互问题，不能归咎于浏览器或模型凭据。
- `R1-W7`、`R1-W8` 是必要观察/验收资源缺口。当前没有用户批准的 Gate 2 资源例外，不预先接受“交付前补验”的提议。
- 此结论针对设计是否足以指导实施，不是对尚未编写的 PA 实现报漏洞，也不要求提前完成未来全部实现测试。

### Coverage 与证据

#### 1. 用户目标、范围与实施组织

已核对 `spec.md` 全文，尤其四种 PA 关系、默认持续观察而非逐条转发、本人任务责任不变、原生 DM/群交流、拒绝第二请求门户，以及 `spec.md:186–198` 的自主 UI 授权。固定自定义 PA 名称主导航 A 是作者在授权内作出的选择，不再要求用户选 A/B。完整实现、dot 云端、非生产部署、默认简化实施及单 M1 与受审设计一致。

`design.md:203–207` 的单个纵向 M1 合理：身份、ACL、执行域、观察与界面无法按数据库/API/UI 切开而分别交付安全可用的 PA。目录只有 `.gitkeep`，没有提前伪填任务/进展。R1–R5 用户结果与 W1–W8 工程退出标准覆盖主要旅程、普通 Agent/channel 回归、真实模型与负向隔离测试；尚需纳入以下发现的明确退出条件。iOS 新导航确实排除，既有聊天/API 兼容仍需回归，不能把 Web 窄屏当原生验收。

#### 2. 实际生产组装与职责

独立从生产入口追踪，而非只读测试替身：

- IM：`apps/im-server/src/main.ts` → `server.ts:160–172` 注册 identity/onboarding/messaging/conversation actions/control/Work/media/gateway 与 trajectory。
- Node：`apps/node/src/main.ts:37–61,171–176,230–264` 读取真实配置、创建 NodeStore/runtime client，按 mode 路由 GlobalAgent/SingleThread，装配 product call、配置 apply、heartbeat 与恢复。它是现有 DSH integration 的宿主，不应新建另一运行时。
- PA：`packages/personal-assistant/src/global-agent.ts:48–86,111–118` 目前只有 `global:<agentId>` 主 binding，`/stop` 可在 Inbox 前处理；新增可信路由必须发生在这些控制分支前。ProductBridge 当前由 parent 链找到 root binding（`packages/dsh-integration/src/product-bridge.ts:11–27`），并不自动隔离新的 external/observation root。
- DSH integration：`agent-config.ts:70–89,111–141` 按 product agent 查首配置/更新同 agent 的 scope；设计的 executionProfileId 与不可变 ceiling 是必要的新机制。现有全局扩展、AGENTS、knowledge/skills、工具 guard 与模型请求前缀均在实际装配链，不能只改 IM 标签。
- IM 当前 task mutation 和身份/space/member 检查是实路径（`apps/im-server/src/task-graphs.ts:379–386,445–462,655–674`）；不能让 Node 自报 owner 或直接绕过同一任务事务。

职责划分总体成立：IM 持有身份/策略/许可/源 ACL/最终投递与任务真相；Node 持有 durable ingestion、execution binding 和可信路由；integration 装配受限 profile、工具上限及原生生命周期；Web 展示真实状态及确认。复用现有任务图、消息、runtime、knowledge、配置 operation 和 Work 比另建任务/请求/运行时系统更合适。新增 binding、event/cursor、release/grant 与 execution profile 分别解决既有系统没有的身份、恢复和授权问题，不能以“减少新表”取消这些边界。

但“复用知识能力”尚未闭合来源清理和上下文重建，非 IM egress 也尚未落到实际工具生命周期；这些是有运行后果的缺口，见 W3/W4。节点交接涉及另一条真实入口，不能只在常规消息路由上修权限，见 W1。

#### 3. API、数据流、并发与复用核对

- 创建：owner/agent 唯一、operation id、配置 apply 回执前不显示 ready，覆盖并发与未知结果；未把既有第一 Agent 静默改成 PA。
- 读取：owner 当前 ACL ∩ 观察策略 ∩ 目标，覆盖附件/snippet/cursor；观察不伪造已读。联系人严格投影与 privateAssetAccess 分离方向正确，实施须覆盖已知 ID、媒体、WS、relay 及聊天 commands 能力发现，不能只过滤目录。
- 观察：同事务 source event、snapshot watermark、durable_received/processed 分离、finalized 后合并、gap/resync 与新回复取消候选，具备实现基础；无需第二任务状态机。
- 对外：external root 不设 native parent、不继承 owner prefix，受限原生工具呈现 + guard + broker 三层边界合理。公开 npm 静态取证支持这些设计接缝存在，但不是“隔离已经通过”的证据。
- 放行：精确内容/对象、受众、用途、期限、真实 owner confirmation 与最终提交重验、operation 幂等形成闭环。`design.md:79,123` **已将 audience/object/source-policy revision 重验应用到 task mutation**；因此不把“任务受众完全未检查”列为新问题。实施接口必须继承此总则，graph revision 本身不能代替 audience revision。
- 任务：delegated mutation 保留 PA actor、owner 授权、不 claim/改派/删除，方向正确；权限上限和 canonical 冲突见 W2。现有系统通知必须保留并在确认前说明，见 W5。
- 控制/恢复：owner canonical DM 与群中 owner 发言分域，外部 `/stop` 不控制主脑，旧历史不产生授权；热更新/冷恢复按 profile/policy/audience/node epoch 失败关闭已纳入 W5 验证计划。已有 fork/distill 另查了 `conversation-actions.ts:191–305`、`personal-assistant/src/history.ts:52–175`：蒸馏入口明确只选 single_thread；未证明 global 回复存在可 fork 的 kernel 锚点，不据通用 fork 实现臆报 PA 漏洞。未来若为 PA 新增这些入口，必须显式定义 scope 与历史继承。

#### 4. Canonical delta

逐一读取 7 个 delta，并与 canonical 对比 MODIFIED Requirement 名称及既有 Scenario；已列出的修改目标均存在，未发现丢掉未修改 Scenario。新增 `im/personal-agent.md`、`gateway/personal-agent.md` 的消费者视角基本正确，归并登记包入口已在设计说明；本轮不提前改 current。

`im/agent-work.md` 与 `im/auth-tenancy.md` 已明确普通共享规则和 PA owner-only 私人资产例外；`gateway/global-agent.md` 的跨聊天/收信及 `/new`、`/stop`、`/compact` PA 适用范围也有修改。问题是 **变化面尚大于这 7 个 delta**：设备整体交接、任务成员/space 界限、Agent 自行入群及按 Agent 整体配置/审批的既有明确承诺仍需收口，见 W1/W2。不会因为 docs-check 能通过就认为这些语义已一致。

#### 5. 原型与体验证据

源码层核对了创建/重试、改名、本人主动建议、保留原草稿和附件、任务 revision 冲突、DM/Agent/群资料确认、受众变化、未知投递回执、暂停/排除/清理/恢复。原型外层标注模拟控制和视觉未验证；此状态诚实。

**本 reviewer 没有看到实际渲染画面，也没有走真实浏览器或当前客户端对照。** 因此不判断排版、美观、密度、窄屏可用性或屏外内容依赖已通过。46 项 jsdom 是作者的交互状态旁证，不是本轮视觉验收。W5/W6 可由可见文案和缺失交互的静态证据直接成立；其余视觉结论保持未验证，见 W7。

#### 6. 验证及资源边界

本轮执行：只读源码/文档对照、冻结文件 SHA-256 校验、Git 基线/状态核对；仅新写本报告。没有启动浏览器、绕开既有访问拒绝、安装 Chromium、配置凭据、调用真实 DeepSeek 或修改产品。

`research/implementation-readiness.md` 记录未改代码的 build/typecheck、104 个选定测试、docs-check、Web build 和 audit 通过；这是基线健康度，不证明本设计已实现。`execution-isolation-feasibility.md` 的 19 个锁定 npm 包 integrity/源码核验属于静态可行性；`prototype-completion.md` 的 jsdom 检查属于模拟状态；两者均不替代未来实际模型请求/工具/恢复负向验证。Runbook 使用现 TypeScript 入口和隔离脚本方向正确，但必要真实浏览器与 DeepSeek 配置尚未落实。

### 历史问题闭环

无历史 Round；无可关闭或 retained 的旧问题。后续 author 应在本轮末尾追加 Author Resolutions，不改本轮原结论；复审另追加 Round。

### Issues

#### R1-W1 — 节点整体交接与“PA 不转 owner”冲突，且本机私人残留没有安全处置决策

- 分类：实质设计/身份与数据生命周期；可自主收口。
- 位置：`design.md:71,83,186`；delta `specs/im/auth-tenancy.md` 的“显式整机交接”例外；缺失的 `im/agents-nodes` 设备交接修改。
- 证据：current `docs/specs/im/agents-nodes.md:350–361` 明确全部 Agent、身份、工作记录和 workspace 随整机移交，私人 Work 转给接收人。实际 `apps/im-server/src/identity.ts:834–850` 整体改写 node/agent/channel owner 和私人空间。Node `device-binding.ts:220–225` 只把旧 runtime 重命名为同目录 `.previous-owner-*`，`:260–268` 写新 owner/token 而保留 agents/workspace；`configuration.ts:31–41,57–92` 继续从同一文件系统读取 workspace、memory、skills、plugins。
- 后果：单独停用 personal binding 或不转 server Work owner，仍可能将同一 OS 运行权限下的历史归档、工作区知识和缓存留给新 owner 的普通 Agent 读取；同目录改名不是安全隔离。另一方面，照 current 全部转移又违背 PA 恒属于原 owner 的设计。断开原 node 后如何恢复同一个 PA、旧节点能否重新上报冒领，也缺少闭环。
- 需修订：明确跨 owner 换绑前、commit/recover、断线恢复与本机启动的检查职责和失败状态，覆盖 PA 私人 workspace、runtime/history/export、观察库/缓存及派生资产；同步设备交接与 auth canonical 例外及用户提示。最小可选方案是本期拒绝含 PA 私密资产/未完成清理的节点跨 owner 交接，另行定义可验证迁移或清理流程；代价是该设备暂不能沿旧“一次整体转交”使用。若选择继续支持交接，则必须给出实际可执行的隔离/清理或迁移协议，不能只改 owner 字段或删除 binding。
- 关闭证据：修订设计与 delta 可说明两端重试/恢复仍不转移旧 owner 的 PA 私料，并为 M1 增加 server 与本机残留负向验证。无需现在执行真实清理。

#### R1-W2 — delegated task 与 PA 特例尚未完整收口到 current 契约，任务权限上限有相互冲突的描述

- 分类：实质共享契约/权限；可自主修复。
- 位置：`design.md:55,59–67,96,139,176`；现有 7 个 delta。
- 证据与具体冲突：
  1. 设计 `:67,96` 允许 PA 非成员按 owner 当前写资格做 delegated mutation；`:139` 却写“owner 当前…资格（或已具备的 PA 成员资格）”，可能在 owner 失权后继续按 PA 成员资格写。current `im/task-graphs.md:54–78,159–177,269–275` 与 `gateway/task-graphs.md:28–50` 要求实际 Agent 的固定空间及所属会话成员写资格。现有 task delta 只 ADDED 结果/责任规则，未定义非成员/跨 PA 固定空间的精确例外。`design.md:176` 的“不改…现有 ACL”也不能覆盖这个新增委托路径。
  2. PA 加群须 owner 决定（`:55`），但 current `im/conversations-messages.md:493–500` 和 `gateway/task-graphs.md:92–97` 仍允许有资格的 Agent 自行加入公开群；没有对应 delta 指明 PA 的例外、owner 确认对象及过期资格重验。
  3. profile 按域缩减配置且不可被私人配置/Auto 扩权（`:59–65`），改变 current `gateway/agent-capabilities.md:109–135,223–244,371–404,457–468,497–551` 的“同 Agent 最新完整配置/工具与特性/继承与 Auto”适用范围；`gateway/global-agent.md:208–217` 的真实 Inbox 人类授权语义也要明确 PA 仅 owner 当前输入可授权。需要限定普通 Agent 保持原行为与 PA ceilings 优先，不能把这些共享规则留给实现者自行决定。能力发现 API `apps/im-server/src/conversation-actions.ts:129–189` 目前会向会话参与者投影该 Agent skills/commands，亦应落实 PA 私人配置不外露的 scope 决策。
- 后果：实施/测试可能分别按两套相反契约执行，或为满足旧测试把 owner 权限撤销、群加入决定、配置 ceiling 再放宽。ADDED PA 目标不能代替对明确冲突场景的归并决策。
- 需修订：owner 当前源写资格必须始终为 task grant 上限，PA 成员资格不得作为替代；明确 delegated path 的实际 actor、source/audience/revision、feature/工具能力及普通路径边界。对实际受影响的上述 canonical Requirement 写完整 MODIFIED，保留普通 Agent 场景；不要求重写无关条目。privateAssetAccess/communicationAccess 同时覆盖能力发现、配置控制及已知 ID，不仅目录。
- 关闭证据：修改后的设计和 delta 可无歧义地回答“owner 已退群但 PA 尚在”“私人 PA 协助本人公司任务”“PA 自行公开加群”“owner 开插件后 external profile”四类情形。`design.md:79,123` 已有 task audience 同事务重验，应继续保留而非另造一套 grant。

#### R1-W3 — 私密主脑的非 IM egress 只有安全目标，尚无可信授权到真实工具执行的闭合机制

- 分类：实质执行设计；可自主修复。
- 位置：`design.md:65,79,89–103,123`；`specs/gateway/personal-agent.md` 最后一个 Requirement。
- 证据：设计具体的 owner confirmation API 只有 message releases 与 task-actions，未定义 URL/query/上传/plugin/shell 等非 IM 动作如何形成可信候选、向 owner 展示实际收件服务和参数、取得许可、消费/撤销及传入 child。`ProductBridge` 只截产品方法；原生通用工具并不都经过它。实际 `packages/dsh-integration/src/policy/approval.ts:20,92–116,123–138` 存在 safe tool、always-allow、skip、classifier 和 unattended fallback 分支，`:101` 还将顶层 run_code 交给后续处理。受限域有 native+guard 决策，不等于 private 域和其委派也已获得同样的出站控制。
- 后果：实施者可能只在产品 send_message 前查 grant，却仍允许被观察材料诱导的搜索 URL/query 或 shell/plugin 携带私人内容外发；或为了安全直接禁全部工具，使已授权助手工作无法完成。仅要求“绑定 owner 当前动作”不足以确定哪个组件可靠建立这个绑定。
- 需修订：选择并写清最小可实施方案。例如，自动私密工作禁用未受控任意 egress，仅允许宿主中介的少数能力；或新增宿主可信、精确 action/tool/参数/目标/有效期/来源绑定与确认消费协议。明确 private 与 child 的继承规则、pre-execute/guard 的顺序、run_code/插件自建工具/进程能力怎样被覆盖或拒绝，以及批准后参数变化/撤销/重试时的处理。无需把每个实现函数写入设计，但不能把出站能力留在未选择的安全口号。
- 关闭证据：从第三方消息触发 private → web query / plugin / shell / child 的路径能指出不可绕过的最终检查和无 grant 的结果；M1 负向测试覆盖实际工具参数及 provider/tool 调用边界。

#### R1-W4 — 清理/排除后的衍生资料失效尚不能由现有 memory/history 复用方案兑现

- 分类：实质数据生命周期；可自主修复。
- 位置：`design.md:71,79–83,93,131–133`；`prototype.html:130` 清理说明。
- 证据：候选虽带 source object/version，但现有 `MemoryChange` 没有该元数据（`packages/dsh-integration/src/knowledge/files.ts:8,49–67`），持久注释只有 session/time；memory 注入是会话快照且 child 继承（`features/memory-curation.ts:11–15,24–34`）。`history.ts:267–318` 另导出完整原生历史和 workspace 可读副本。设计尚未决定源到 memory/summary/skill/主及子上下文/输出的可靠依赖索引、受控写入边界，以及如何处理没有逐片来源的已压缩上下文。用户 API 也没有明确“清理”的可恢复操作/完成回执协议。
- 后果：排除源 S 后只删 source cache/candidate，S 的内容仍可能经 memory 快照、child、导出或保留的本人 DM 建议重新进入主脑。原型合理保留用户原聊天，但“展示历史保留”不等于其全部正文都能重新作为模型输入；当前设计未分清这两层。清理中崩溃或离线恢复时，也无法据已定义状态判定何时可以再次准入。
- 需修订：明确私密自动资料的权威来源/lineage 元数据及写入责任，限制通用 memory、文件编辑、shell 和自进化绕过；决定对不可细分的已污染上下文采取保守整 scope 废弃/重建等策略，覆盖活跃 child、快照、exports 与恢复。明确保留的 owner DM/Work 历史与后续模型输入过滤边界，以及清理 operation/epoch、暂停准入、持久进度、最终确认的责任。可继续复用现有知识文件，不要求再建一份任务或内容真相。
- 关闭证据：设计能演绎“S 被观察→进入 memory/摘要/本人建议→排除或清理→重启及继续聊天”后不会再次注入 S；M1 增加此完整链路及 child/compaction/未知清理结果测试。

#### R1-W5 — 任务写回确认错误承诺“不发群消息”

- 分类：实质用户授权/交互；可自主修复，无需视觉环境才能确认。
- 位置：`prototype.html:95,125`；`design.md:67,139`。
- 证据：确认页将状态改为“待确认”，同时显示“不会改派负责人，也不会给群里发消息”。current `docs/specs/im/task-graphs.md:209–221` 要求待确认/完成生成所属会话系统通知；真实 `apps/im-server/src/task-notifications.ts:25–37` 生成通知，`task-graphs.ts:671–674` 与任务保存同事务持久化。本 unit 未提出取消此契约。
- 后果：owner 会在错误理解可见结果和通知受众的情况下确认；下游照原型实施可能错误抑制现有任务协作通知。
- 需修订：保留当前任务语义，确认页明确原任务可见范围、状态变更将产生的系统通知及提醒对象；区分 PA 另发聊天回复和任务自动通知，不能用“不发群消息”概括。grant/audience 校验覆盖这个事务副作用。
- 关闭证据：原型/设计对同一待确认路径展示真实副作用，M1 对结果、actor/authorized_by、负责人不变及通知一次性同时验证。

#### R1-W6 — 已承诺的外部联系屏蔽控制没有可执行产品设计

- 分类：实质需求/交互覆盖；可自主修复。
- 位置：`spec.md:194`；`design.md:53,79,93,157–164`；`prototype.html:121–122`。
- 证据：spec 决定“屏蔽与频控始终可用”。policy API 只笼统说 contact policy；设置中“谁可以联系我”只有说明，没有屏蔽/恢复入口、对象选择或结果状态。观察来源排除和暂停不等于阻止外部联系人继续与 PA 会话；现有 must-match 也未覆盖此决定。
- 后果：owner 无法停止具体真人/Agent 的持续打扰；实现者可能把暂停观察误当关闭外部联系，或仅隐藏联系人而既有 DM、已排队回复与已知 ID API 继续可用。
- 需修订：决定最小 contact policy 字段及 owner 操作旅程，说明屏蔽的对象、既有/新 DM 和群场景范围、待处理消息/许可/执行的失效、恢复后积压如何处理，以及外部可见反馈与频控责任。补可交互状态、delta、must-match 和 M1 验收；可以采用简短控制，不需新门户。
- 关闭证据：从 owner 设置能完成屏蔽与恢复，设计能说明 active external scope、排队发送、直接 API 与重复来信的结果，且不会错误清除原始聊天或关闭所有合法协作。

#### R1-W7 — 必要真实原型体验与当前产品对照尚未观察

- 分类：纯观察/环境资源阻塞；不等于已经发现“丑”或窄屏故障。
- 位置：`design.md:143–168,201`，前端共同判断标准。
- 证据：现有记录和派发明确无成功渲染、截图及当前客户端对照；本 reviewer 也未取得这些证据。jsdom/CSS/源码不能证明 1440/768/390px 以及挤压宽度下的层级、阅读、关闭/返回、草稿保持、确认受众和操作可达性。
- 后果：独立 reviewer 无法按用户明确要求判断整体体验与审美，也不能确认方案足以指导真实客户端。repo 规则不允许把必要原型视觉检查默认为实施后事项。
- 关闭条件：在正式允许、实际可用的云端浏览器路径渲染，独立走四种关系及关键确认/错误恢复、观察控制与创建路径，并对照当前产品入口，留下代表性截图和基于画面/操作的判断；或取得用户明确调整此门禁范围/验证时点的授权后，按准确的新边界复审。此刻没有该授权，不能提前放行；不再尝试已拒的 Chromium/socket/clipboard/frame 绕行。

#### R1-W8 — 必验真实 DeepSeek 链路的云端资源未落实

- 分类：验收资源阻塞；不是要求在设计阶段完成未来实现测试。
- 位置：`design.md:188–207`，Runbook 验收前置。
- 证据：作者与基线记录均明确云端隔离环境尚未配置 DeepSeek；锁定 npm 包源码核验、mock/DOM 测试和 build 均不证明真实模型服务可用。M1 W7 又要求真实 DeepSeek 同时验证主动价值与攻击边界。
- 后果：实施后的必要旅程暂无落实的可执行资源，按当前 Gate 2 规则不能以“届时再找凭据”替代可用性。用户已授权完整实现和自主 UI，不等于授权取消或默认后移该门禁。
- 关闭条件：通过正式安全方式落实云端隔离模型配置和允许的服务可达性，记录不含密钥的资源/运行方式；真实产品效果仍在 M1 验证。或者用户明确批准改变资源落实时点/验证范围，并同步设计与门禁边界；不接受推测性同意，不读取用户本机配置，不在文档或聊天写密钥。

### Recommendations

无额外非阻断建议。以上关闭条件是设计收口与后续验证边界，不是要求作者在 Gate 2 前实现整套 PA。修订后应冻结新 manifest，由独立 reviewer 按真实变化选定复审范围；涉及执行/生命周期及共享权限边界，不能仅以修文案的 closure 代替受影响设计复核。

### Author Resolutions after Round 1

- R1-W1 accepted：本期选择 PA residency 节点拒绝跨 owner 交接，覆盖两端准备/commit/recover/启动；同 owner 新节点恢复原身份递增 epoch，不自动搬旧私料。修改 agents-nodes/auth-tenancy delta。
- R1-W2 accepted：owner 当前权限始终为上限；增加完整 task/group/capability/Inbox MODIFIED 条目，普通场景保持，明确窄化 PA 例外与私密能力发现。
- R1-W3 accepted：结构化 host candidate→owner 确认→exec.token permit→单调 guard→最终 broker；任意工具采用明确批准的独立任务并披露广权限残余风险，不给自动观察通用工具。
- R1-W4 accepted：provenance-aware writer、整 scope 失效、可恢复 cleanup、过滤保留历史；旧日志 append-only，文案不承诺物理删除。审核/知识/child/export 一并覆盖。
- R1-W5 accepted：原型确认与结果保留源群系统通知，不再承诺不发群消息。
- R1-W6 accepted：原型新增目标级屏蔽/解除、取消、离线及冲突状态，规则落 design 和 delta。
- R1-W7/R1-W8 unresolved：真实视觉及 DeepSeek 云端资源仍未落实；流程顺序调整尚待用户明确批准。不得标 Gate 2 Approved 或开始产品代码。

以上为作者处理说明，不能替代 reviewer 复审结论。拟按实质权限/生命周期改动发起 delta 复审，不申请只看勾选的 closure。


## Round 2

### Metadata

- reviewer target: `change-design-reviewer`，同一位独立 reviewer `/root/prepare_pa_implementation_gates/review_pa_design_gate`；未参加作者修订。
- review_mode: `full`（由计划的 delta 扩大）
- mode_reason: 修订新增 `authorized_task`、出站许可、来源生命周期及 3 个 canonical delta，改变核心权限边界和共享接口；不能只核作者勾选。重新覆盖现稿 spec/design/prototype/全部 10 个 delta/M1，未变化的生产基线证据沿用 Round 1。
- started_at: `2026-10-16T17:47:26Z`
- completed_at: `2026-10-16T17:54:06Z`
- duration: `6m 40s`
- executed_base: `481467ac16f0eda4561fca5c8230050541600de9`；本地 HEAD 与 origin/main 引用一致，tracked diff 为空，本轮未重新 fetch。
- validated_at: 当轮 HEAD 加未提交的 R2 冻结设计工作树；当时逐文件校验 14/14 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- evidence boundary: 本轮不重新读取产品代码、不浏览、不读凭据、不运行真实后端/模型；仅文档、canonical、原型源码与内存函数检查，并追加本报告。未将研究旁证或旧基线测试升级成实现验证。

### Verdict

**Issues Found — 0 CRITICAL / 7 WARNING。Gate 2 仍不通过。**

5 项可自主修订的问题（W1–W5），另 2 项沿用的环境/资源阻塞（W6–W7）。R1 的设备交接决策与任务通知错误已关闭；出站 guard、可恢复清理和联系控制已明显具体化，但新增独立任务还没有接好私人资产与返回资料边界。并非只剩浏览器和凭据。

### Coverage 与证据

#### 需求与架构复核

- 全文重读 `spec.md`。唯一/可命名 PA、自动观察、四种原生 IM 关系、不另建请求门户、原 task_graph 责任、Web 增量/iOS 兼容、dot 云端完整实现及自主 UI 选择未改变；没有新增应由用户先选的 UI 问题。
- **retained_from: Round 1** 的生产入口、IM/Node/PA/DSH 依赖方向、现有 TaskGraphService 事务、普通 Agent Work 共享、配置/审批/knowledge/history 接缝。理由：HEAD 和 tracked 产品树不变；本轮按范围不重读产品代码，用 R1 记录的实际生产证据核对新设计，非只依赖作者新研究。
- 重新评价新增机制：双端 residency 阻止含 PA 资产节点跨 owner 换绑，代价明确，避免仅改 server owner 的伪修复。宿主 action candidate → authenticated owner confirmation → native exec.token permit → 单调 guard → 最终 broker，职责比让审批模型自行判断有效；普通 safe/skip/fallback 不再能覆盖 PA gate。新增 provenance writer、保守整组退休、cleanup operation、重建确认和 filtered history，合理复用现有文件/runtime 而不伪造 DSH purge。
- `authorized_task` 的“最小任务包 + fresh root + 明确授权”能保留专业执行能力；`design.md:90,100–102` 诚实承认同 OS 广权限可读残留/联网，不将工具 guard 说成 OS 沙箱。**不因这种已披露的普通执行风险本身提出阻断**；但 professional product actor 的共享投影、返回数据重新入脑、真实确认旅程必须闭合，见 W2–W4。

#### 关键接口、并发及撤源

- 创建唯一性/operation 恢复、对外通信/私密资产分离、snapshot+incremental ingestion、durable_received/processed、cursor/epoch、精确 release、IM task mutation 及未知回执策略：保留 R1 已成立判断；复核现稿无把 model/source text 升为 owner 权限。
- 新 task-actions 绑定 source/audience/policy、通知受众和 patch hash；owner 当前写资格不再被 PA 成员资格替代，`design.md:131,174` 已修正。仍有 canonical 读写混写，见 W1。
- cleanup 现在明确 old main/children/reviewer/knowledge/checkpoint、exports、KnowledgeRuntime.batchHistory、普通文件读取和旧 owner DM 建议都不可自动重注入；未知来源隔离、日志展示与执行资料分离、离线/崩溃保持 operation 未完成，覆盖了 R1 的原有路径。该结论是设计接缝成立，不是生命周期已测通。新增广权限任务返回值不能仅按初始任务包标记为干净，见 W3。
- 非 IM 出站的“发出前原子消费”按本地权威许可提交理解；未把它读成互联网请求与数据库可原子提交。精确线性化点建议见 R2-R1，不以此再报一个相同 blocker。

#### Canonical 与 milestone

- 独立结构检查结果：**27 个 MODIFIED Requirement 均有正确 canonical target，88 个原 Scenario 名称全部保留**；10 个 delta 全部阅读。结构结果不证明语义通过。
- 各修改前言已经把旧设备交接、公开群自行加入、全 Agent 配置/工具/继承/Auto、Inbox 多来源授权限定为普通路径，并明确 PA 特例；不因为保留的旧 Scenario 文字出现“Agent”就机械判为自相矛盾。旧“PA Agent”是项目用语，新增 personal-role 限定能区分本次产品角色。
- task delta 的前言确实把 read 和 mutation 绑定到了同一个一次性 grant，属于真实冲突（W1），不是标题/格式问题。Work delta 仍没覆盖新 professional authorized_task（W2）。
- 单 M1 仍合理，新增 W9–W12 覆盖 residency、非 IM 动作、再注入、联系/通知，未产生虚构实施进展。前端 must-match 表尚未覆盖新增精确 action/独立任务确认；只有 W10 工程结果不足以指导用户确认设计，见 W4。

#### 原型与实际执行证据

- 任务确认/收据现在说明“产品协作群会产生/已产生待确认系统通知”，负责人保持本人；原有错误承诺消失。清理文字现在说明缓存/上下文与保留日志的区别。
- 联系面板已有具体 DM/Agent/群对象、保存/取消、离线和 revision 分支；检查后发现“解除后新请求”状态未闭合，见 W5。
- 本轮额外执行一次 **静态内存原型函数检查**：从受审 HTML 提取脚本，用 Node `vm` 执行原有状态函数，替换 render/save 为无副作用桩；依次屏蔽 DM、解除、发送新消息。结果是三步均停留 `status=invalid, requested=true, version=2`，最后仍向外部追加“我会请陈同学确认…”；没有浏览器、网络、真实投递或视觉结论。
- 作者的 46 原断言 + 13 新断言、docs-check 通过仅作旁证。本轮没有重跑全部作者断言，不能据其通过忽略上面独立复现的序列。
- 真实渲染/截图/当前客户端对照与 DeepSeek 配置仍无证据；用户也未批准顺序调整。无视觉体验通过结论，W6/W7 继续阻塞。

### 历史问题闭环

| 原问题 | Author Resolution | 本轮独立判断与证据 | 状态 |
|---|---|---|---|
| R1-W1 | 双端 residency 拒交接；原 owner 同身份恢复 | `design.md:77–81` 与 agents-nodes:68–97/auth-tenancy:9 明确持久标记、prepare/commit/recover/启动失败关闭及旧 epoch 拒绝，未把改名当隔离。 | **closed**（设计层） |
| R1-W2 | 增补完整 task/group/capability/Inbox MODIFIED | owner 权限上限、入群与能力 ceiling 已修；task read 被写成一次性 grant 前置仍冲突，见 R2-W1。 | **still-open** |
| R1-W3 | 结构化 broker/permit；任意工具转独立任务 | 结构化工具的最终强制接缝已具体；新增独立任务的投影、返回与确认未闭合，见 R2-W2–W4。 | **still-open**（不否定已修 broker 部分） |
| R1-W4 | provenance writer、整组退休、可恢复 cleanup、历史过滤 | 原有自动域/child/reviewer/export/旧 DM 路径已明确；新增广权限任务输出重新入脑需补边界，见 R2-W3。 | **still-open**（原路径修复保留） |
| R1-W5 | 任务通知确认/收据说明 | `prototype.html:95,127–128` 与 `design.md:108,131` 一致说明系统通知，未取消现有任务契约。 | **closed**（文案/设计层；视觉仍未验） |
| R1-W6 | 联系屏蔽/解除面板与策略 | 控制入口及保存有设计，但解除后新请求复用失效状态，见 R2-W5；不能仅据新增勾选框关闭。 | **still-open** |
| R1-W7 | 尚无视觉资源/顺序授权 | `design.md:203,238` 与本轮资源状态未改变，见 R2-W6。 | **still-open** |
| R1-W8 | 尚无 DeepSeek 云端配置/顺序授权 | `design.md:238` 未落实必要资源，见 R2-W7。 | **still-open** |

历史问题不另重复计数；本轮 7 条 Issues 是当前待闭合项。

### Issues

#### R2-W1 — PA 任务只读被错误绑定到一次性写入许可

- 分类：实质契约，可自主修复；延续 R1-W2。
- 位置：`specs/im/task-graphs.md:20,53,73,100`；`specs/gateway/task-graphs.md:7`。
- 证据：重复前言要求“owner 当前源会话读写资格…及精确一次性 grant 读取/补充结果或状态”，且只允许 owner_private。与 `spec.md:95–103,160–162` 的自动发现本人任务、`design.md:69,136–138` 的当前 read ACL ∩ 观察策略和观察批次读取冲突。无 grant 的首次读取无法先为 owner 准备要批准的具体任务结果。
- 后果：实施者可能恢复成逐任务先批准才读的被用户否定模式，或直接无视 canonical，导致权限测试与产品行为分叉。read 与 write 资格也不能互换。
- 需修订：将只读投影独立写清为当前 read ACL ∩ 已启用观察范围 ∩ 可信域/批次，无逐动作写 grant；写入才要求 owner 当前 write ACL、精确一次性 grant、task/audience/policy revision 等。明确 observation/private 的允许读取入口和 external/ordinary child 不可借用边界。重复条目应统一相同事实，避免一处改了仍残留相反前言。
- 关闭证据：无单次 grant 可主动读本人允许任务并准备建议；同一任务写回无 grant 必拒；owner 退群而 PA 留群仍不可写，普通 Agent 空间 ACL 不变。

#### R2-W2 — 独立专业任务的实际主体与 Work/轨迹私密受众未定义

- 分类：实质身份/信息投影，可自主修复；新增执行支路。
- 位置：`design.md:85–90,116,140–154`；`specs/im/agent-work.md:7`。
- 证据：`authorized_task` 可选择“专业 Agent/节点”，声明结果先回 owner；没有限制选中的 professional Agent 是 private 还是 company，也没有定义该 fresh root 的 productAgentId、Work owner、trajectory/media/WS 查询规则。Work 段只新增 external_chat、observation 两类 root，现 delta 的 PA owner-only 只覆盖 PA 主/子/外部执行。current `docs/specs/im/agent-work.md:19–36,98–104` 仍明确普通公司 Agent 的完整 Work/关联轨迹向其他有资格公司成员共享，且不按原来源过滤。
- 后果：即使最终回复只发 owner，私密任务包、prompt、工具输入/结果可能已因选中公司专业 Agent 而进入共享 Work；用户批准某个执行者不等于批准其整个公司读取。
- 需修订：在候选建立和执行前确定可选执行主体及其所有投影。可以首版只允许同 owner 且相关 Work/轨迹/媒体真正 owner-only 的执行者；或以 PA 私密身份承载 authorized_task fresh root，明确专业能力和真实 actor 的关系。若允许不同 product agent 的私密任务，就需显式 scope ACL/canonical 例外，不能从“结果回 owner”推导。连同恢复、已知 ID、原生轨迹、产物/附件、WS 与关联导航一起决定。
- 关闭证据：用公司共享专业 Agent 作为候选时会拒绝或产生已定义的 owner-only scope；另一公司成员即使能看该普通 Agent 的其他工作，也不能发现/读取此任务包与执行。用户确认展示实际执行者与实际受众。

#### R2-W3 — 广权限独立任务的返回值仍可能把被清理资料带回 PA 自动上下文

- 分类：实质来源生命周期，可自主修复；延续 R1-W4 的新支路。
- 位置：`design.md:90,96–102,152–154,168`。
- 证据：设计正确承认广权限任务可能读取同机残留；但其输出只规定“结果先回 owner”，未决定结果是否进入 PA 私密 Inbox、owner DM 观察、自动知识或后续工具。已给出的 lineage 规则基于执行输入源；任意 shell/plugin 额外读取的旧日志 S 不能仅凭初始批准任务包 A 被宿主可靠归因。把输出附上 A 的来源或专业 Agent 的自报来源不能证明没有 S。“未知来源隔离”原则需要在这一已知无法完整追踪读取的分支明确如何生效。
- 后果：S 已从自动主脑/knowledge/export 恢复路径退休后，ordinary broad task 读取残留并返回，可经“合法任务结果”或写入 owner DM 再次被自动摄取，抵消 W4 原路径修复。批准在普通环境运行任务也不自动取消已排除来源的观察策略。
- 需修订：明确 broad task 输出的可信度和接入点。例如把不能证明只读受控输入的返回标为 unknown/tainted，仅供 owner 查看，不自动进入 PA 模型、memory、审批历史或来源流；如 owner 要将具体结果重新提供给 PA，必须是明确选择的新的输入，并不恢复旧来源持续观察。或者要求该执行环境能证明所有输入来源。覆盖 root、child/workflow、产物、错误文本、进度摘要及 owner DM 回流；不能用模型自报“已清理/只用批准材料”建立干净 lineage。
- 关闭证据：构造 S 已排除且仍在 native/export 磁盘、任务只获包 A、广权限任务返回 S 的场景，设计能指出 owner 展示与自动处理的分别结果，W11 包含该回流负向链。

#### R2-W4 — 新增非 IM 动作与独立任务的关键确认旅程尚无原型/对齐契约

- 分类：实质授权体验设计，可自主修复；与浏览器资源独立。
- 位置：`design.md:89–92,190–199`；`prototype.html:123–133` 的面板集合。
- 证据：设计新增精确 action approve API 与 broad-task 明确批准，列出参数/外传字段、执行 Agent/节点、输入包、工作区/网络及残余风险。但现原型只有聊天资料 release、task patch、联系/观察等面板，没有这两种授权的可操作呈现；must-match 表也未新增。研究中的 grant 字段和“确认必须明示风险”不是信息层级、阅读与操作方案。
- 后果：最重要的普通受控动作与广权限执行可能落成同一种“确认”按钮，owner 无法分辨批准的是精确字节/收件服务，还是可读取更多同机文件并联网的执行权限；缺少拒绝、更换节点、不可用、参数/输入变化与未知执行结果的连续体验。
- 需修订：在现 owner DM/面板内给出两条代表性可交互流程，可复用组件，不需新增门户。明确实际对象/数据/执行者/能力、广权限后果与可选安全替代、确认与取消、scope 变化后重审、执行回执；把本次新增旅程及已补联系控制映射到 must-match 与 M1 reviewer/worker 退出条件。
- 关闭证据：不借 design 解释或演示标签，用户能从原型辨认两种授权的不同后果并完成拒绝/修订/确认。源码交互先补齐，真实视觉仍由 R2-W6 单独检验。

#### R2-W5 — 联系解除后的新请求仍卡在已撤销旧请求上

- 分类：实质原型状态/恢复，可自主修复；延续 R1-W6。
- 位置：`prototype.html:101–105,116,121–123`；`design.md:106`。
- 证据：`saveContacts()` 把被屏蔽目标的请求设为 invalid 并递增 version，但保留 requested=true。解除时不建立新请求；`requestExternal()` 对 requested=true 直接 return。因此解除后新外部消息依旧停在旧 invalid/version，`externalSend()` 却追加“我会请陈同学确认…”；owner 的 `proactiveMessages()` 对 invalid 也显示原来的待确认卡。上述序列已由本轮原型函数静态执行复现，不是视觉猜测。
- 后果：用户明明解除并收到新请求，却仍面对旧的失效内容；屏蔽目标的旧请求继续显示为可处理建议。只检查 blocked 数组和按钮存在不能证明“解除后仅接收新请求，不恢复旧许可”。
- 需修订：区分会话联系策略与每个请求/许可生命周期；屏蔽后旧卡呈现已撤销/不可继续，解除不复活它；新消息创建新 request/version/来源快照及待处理状态。保留既有已发/unknown operation 的查询身份，不将其误当可重发。补该连续路径与取消/冲突状态检查。
- 关闭证据：屏蔽→解除（无新消息）不恢复旧请求；解除→新消息形成新有效待确认请求，旧许可不能消费；unknown 只查旧 operation。

#### R2-W6 — 真实原型观察与当前客户端对照仍缺失

- 分类：环境/观察阻塞；延续 R1-W7，关闭条件不变。
- 证据：`design.md:203,238` 仍无正式允许且可用的真实渲染/客户端路径；本轮也没有截图或浏览器操作。新增 13 项断言与本轮函数检查都不证明布局、易读性、审美、窄屏或操作可达。
- 关闭条件：在允许的路径完成当前原型及相关既有客户端对照，独立走主要及新增确认/恢复旅程、留代表性证据；或由用户明确调整该门禁的时点/范围后据新标准复审。当前没有该授权，不能先行 Approved；不尝试已拒绝的浏览器绕行。

#### R2-W7 — 必验 DeepSeek 云端资源仍未落实

- 分类：验收资源阻塞；延续 R1-W8，关闭条件不变。
- 证据：`design.md:238` 仍写“目前未配置”；真实 DeepSeek 是 M1 的必验旅程。npm 静态能力研究与未改产品的测试不证明服务/凭据可用。
- 关闭条件：正式安全方式落实云端隔离配置及可达性，记录不含密钥的验证资源；或用户明确改变资源落实时点/验证标准并同步设计。没有顺序调整授权，不读取本机密钥或以推测代替批准。

### Recommendations

#### R2-R1 — 将非 IM 提交的线性化点直接写到最终设计

研究补充 `execution-isolation-feasibility.md:180–181` 已正确说明数据库许可与外部发送不能跨互联网原子提交。建议将其简短写入 `design.md:89,158`：撤销在权威 store 接受预留/消费前提交则拒绝；预留后动作可能已开始，超时保留 unknown 且不另发请求，不能承诺直到外部服务接受前任意时刻均可撤回。此为现有“发出前消费”的精确化，不另计为阻断问题。

#### R2-R2 — 避免重复整段 PA 例外继续漂移

多个 capabilities/task Requirement 重复相同长前言与 Scenario，当前没有必要为此单独阻塞；修 W1 时可保留完整 MODIFIED 条目，同时把共通 PA 权限事实放到一个明确 canonical Requirement、其他条目短句引用。保持普通场景完整，避免未来只改一处形成相反权限。

### Author Resolutions after Round 2

- R2-W1 accepted：所有重复task前言分开当前read ACL/观察策略与写入grant，不要求单次确认才观察。
- R2-W2 accepted：首版固定PA product actor的authorized_task fresh root，专业能力是配置快照；不向公司共享Agent账号派私料，Work/轨迹/media/WS均owner-only。
- R2-W3 accepted：广权限输出全链unknown/tainted，只给人看；主脑仅收到固定无正文状态。本人可明确选择具体内容作为新输入，不恢复旧源观察。
- R2-W4 accepted：新增两种确认连续原型与must-match/M1映射，包含完整输入、权限后果、节点替代、撤销/修改/未知回执及隔离结果。
- R2-W5 accepted：撤销旧请求与新消息新建区分，阻止刷新复活旧卡，保留unknown operation。新增连续测试覆盖。
- R2-W6/W7 unresolved：仍缺实际视觉及DeepSeek资源，尚无用户顺序调整授权。
- R2-R1 accepted：明确许可预留线性化点与网络非原子性；R2-R2 noted：本轮统一修复重复前言，未仅为去重改写无关契约。

请求独立复审实际变化；作者说明不替代批准。


## Round 3

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/prepare_pa_implementation_gates/review_pa_design_gate`；未参与受审 spec/design/prototype 的创作，仅追加本报告。
- reviewer target: `docs/changes/feat-616-personal-agent` 的 R3 冻结设计树。
- review_mode: **delta**。
- mode_reason: R2 已对新增执行用途与共享权限变化做 full；本轮是该设计内的有界收口：读写资格拆分、确定 authorized_task 的既有 PA 私密主体、落实未知来源输出隔离、增加相应交互及修复联系请求生命周期。未新增执行运行时、用户范围或 milestone。对这些变化及关联 ACL/Work/恢复/来源路径展开复核，其余引用 R1/R2；没有因作者声明“已修”直接关闭。
- retained_from: **Round 2**（生产组装/DSH 公开能力/依赖方向/自动观察与清理机制、未变 canonical 兼容性）；R1 的直接生产源码证据通过 R2 保留。本轮遵照派发不重读未改产品代码、不执行产品或环境验证。
- started_at: `2026-10-16T17:59:34Z`
- completed_at: `2026-10-16T18:03:21Z`
- duration: `3m 47s`
- executed_base / HEAD / 本地 origin/main: `481467ac16f0eda4561fca5c8230050541600de9`。reviewer 未联网刷新远端，不将本地 tracking ref 称为本轮实时远端核验。
- validated_at: 当轮 HEAD 加未提交的 R3 冻结设计工作树；当时逐文件校验 14/14 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- working tree: tracked diff 为空，只有本 unit 未跟踪；未创建分支/提交。本次仅追加 `design-review.md`，追加前 SHA-256 为 `8a0b5e64ebc13e86c41d90a01748822aaf9c270033b81ba11628b85de4ab1f7d`，保留 R1/R2 及作者 resolutions 全文。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

三项核心设计修订已闭合：任务无逐次 grant 可读且写入仍有精确授权；专业任务以 PA 私密主体运行而不投递给公司共享 Agent；广权限正文全部隔离，具体选择才成为新的本人输入。剩余 **2 项可自主修复的交互生命周期问题**，另有 **2 项未解决的资源阻塞**。Gate 2 不通过，不附带条件批准。

### Coverage 与证据

#### 实际变化及 retained 范围

将 R2/R3 manifests 逐项比较：变化仅为 `design.md`、`prototype.html`、`specs/gateway/personal-agent.md`、`specs/gateway/task-graphs.md`、`specs/im/agent-work.md`、`specs/im/task-graphs.md` 六项；`spec.md`、另外六个 delta 与 M1 骨架八项 hash 未变。完整阅读变化的六项以及本轮 Author Resolutions；需求、唯一 M1、普通 Agent 与现有产品入口保留前轮证据。重新读取 workflow/reviewer/report/派发适配及共同体验标准。

对本轮三个 MODIFIED delta 独立结构核对：**7 个修改条目名称匹配 canonical，21 个原 Scenario 名称保留，0 个遗漏**。这是结构核对；权限语义按下列路径独立判断，不以名称匹配代替审查。

#### 1. 任务读写与原有空间约束

- `specs/gateway/task-graphs.md:7` 与 `specs/im/task-graphs.md:20,53,73,100` 已一致拆分：可信 owner_private/observation 按 owner 当前 read ACL ∩ 观察范围 ∩ 本次目标/批次读取，无逐任务批准；仅 owner_private 的写路径才要求当前 write ACL、任务能力和精确一次性 grant。external/普通 child 不取得这一投影。
- 与 `design.md:69,136–138,174` 及首文档主动观察相容；owner 退群而 PA 留群仍不能写，PA 不需为协助被偷偷入群。原普通任务场景保留且有明确普通路径适用前言，未把全部普通 Agent 扩为 owner 代理。
- 任务受众/通知及 graph/source/policy revision 继续成立，保留 R2 对既有系统通知修复的证据。本轮没有把读权限重新当写权限，也未扩大 claim/删除/改派。

#### 2. 专业能力与真实 PA 私密身份

- `design.md:90,142,178` 明确首版 `productAgentId=PA`、fresh authorized_task root、独立 profile/purpose。专业能力只是 owner 选定的版本化配置快照，不把任务包送入普通公司 Agent 的账号/历史，不继承其共享监听器。
- `specs/im/agent-work.md:7,37–40` 将 authorized_task 的 Work、轨迹、产物、media、WS、已知 ID 访问纳入 owner-only；设计补上恢复前 binding/profile/policy epoch 和关联导航。`specs/gateway/personal-agent.md:59–63` 同步消费者契约。
- 这一取舍复用当前 PA product actor、私密资产边界与 DSH fresh profile，不另创“共享 Agent 但私密 Work”的例外系统。普通专业 Agent 原共享规则保留。实现仍须在既有产品组装点兑现，文档审查不表示 ACL 已实现。

#### 3. 广权限输出不自动重新进入私密主脑

- `design.md:180–182` 对正文、产物、错误、进度、child/workflow/reviewer 输出整体标 unknown/tainted，不依赖初始包或执行者自报来源。自动主脑仅收到宿主固定无正文状态；内容留在 owner-only Work，不进入 Inbox、owner DM 正文、观察、记忆、审核历史或后续任务工具。
- 只有具备可证明输入集合的受控 broker 结果可以自动携带可靠 lineage；广权限分支由 owner 明确选择准确文字/文件、确认新输入含义，服务器记录 bytes/version/选择事实。任务执行许可、自然语言短同意和解除源排除都不代替此选择。
- `specs/gateway/personal-agent.md:72–75`、`specs/im/agent-work.md:40` 与 M1 W11/W13 同步；覆盖 S 已排除但磁盘残留、包 A 返回 S 时不自动再摄取的负向链。此处接受其设计机制，未声称广权限本机具备 OS 沙箱。

#### 4. 新增确认与结果交互

- `prototype.html:116,124–132` 在本人聊天/设置提供实际产品入口，分别展示精确搜索词和独立任务完整输入、实际 PA 执行者、专业能力版本、节点、仅本人结果受众及同机广权限风险；独立干净节点不可用会保留草稿，不偷偷回退。取消/修改后重新确认、未知回执查询和具体结果选择均有交互。
- `design.md:206–207,254` 已把新增流程、联系屏蔽和结果选择映射到 must-match、M1 R6/W10/W13、R4/W12。结果内容选择可见且默认未选，自动执行批准不会代替这一步。
- 不再因“缺少确认面板”报错；但跨两个动作来回查看、来源撤销、旧操作恢复仍有可复现缺口，见 R3-W1。联系普通待办分支已修，unknown/已完成旧操作分支见 R3-W2。
- 搜索/任务 UI 的标签、布局、阅读次序及三宽度可用性仍**未视觉验证**。没有浏览器、截图或当前产品画面对照证据，不能据 HTML/JS 阅读认定体验通过。

#### 5. 独立静态复现的范围

本轮用 Node `vm` 加载受审 HTML 的原始 script，仅替换 `render/focusPanel`、提供空 DOM 查询与可控 timer 队列，直接调用其实际状态函数。未请求网络、未读取产品代码、未模拟真实后端授权，也没有产生浏览器画面。复现结果：

```text
operation before switch: task / unknown / action-1
operation after search -> task: task / draft / operation=null
source revoked then confirm: sourceAvailable=false, taskAvailable=false,
                            status=running, operation=action-2, hasInput=true
pending block -> unblock -> new: waiting / new requestId / version=3 / revoked=false
unknown block -> unblock -> resolve -> new:
  status=sent / requestId=null / deliveryId=old-op / followup=true
```

作者提供的 46+13+17 静态断言未作为全路径正确性或视觉证明；上面两条新问题由 reviewer 自己复现。R1 的基线 build/typecheck/104 选定测试、文档/Web build/audit，及 npm 19 包静态取证，继续只代表既有基线/静态能力证据，不是未来 PA 实现通过。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R2-W1（R1-W2 残余） | task read/write 分开 | 两端完整 MODIFIED 前言一致；无 grant 的观察与有 grant 的写回分离，见覆盖 1 | **closed** |
| R2-W2 | 固定 PA actor 的 private authorized_task | design 90/142/178 与 Work delta 7/37–40，包含全部投影与恢复 | **closed** |
| R2-W3（R1-W4 新支路） | 广权限结果 unknown、仅人看、明确选择新输入 | design 180–182、gateway delta 72–75、W11/W13 | **closed**（设计层） |
| R2-W4 | 新增两个确认与结果选择原型 | 面板、语义与 must-match 已补；跨动作/撤源状态不闭合，R3-W1 | **still-open**（仅保留生命周期部分） |
| R2-W5（R1-W6 残余） | 撤销旧请求、新消息建新请求 | pending 路径关闭；unknown 保留后 sent 分支仍吞新请求，R3-W2 | **still-open**（范围收窄） |
| R2-W6 / R1-W7 | 视觉资源未落实 | design 213/248；无新观察或用户调整授权 | **still-open**，R3-W3 |
| R2-W7 / R1-W8 | DeepSeek 未配置 | design 248；无新资源或用户调整授权 | **still-open**，R3-W4 |
| R2-R1 | 明确非 IM 线性化点 | design 158 已说明权威预留/消费与网络非原子、撤销不能追回已开始效果 | **closed** |
| R2-R2 | 本轮统一前言，不额外重构去重 | 重复文字一致；可选维护建议，不阻断 | **noted** |

R1-W1 设备交接与 R1-W5 任务通知的关闭结论 retained；对应设计/契约未被本轮破坏。历史条目不重复计数。

### Issues

#### R3-W1 — 新动作的操作身份与来源失效没有贯穿连续交互

- 分类：实质交互设计，可自主修复；延续 R2-W4，按同一新增动作生命周期归一报告。
- 位置：`prototype.html:124–132`，对照 `design.md:89–90,98–100,158,206,254`。
- 证据 A：`openAction` 用单个 `s.action` 存储两种动作；打开不同 kind 会重置整个对象。实际 task unknown=`action-1` 后返回私聊、打开 search、再打开 task，状态变 draft、operation=null。已经运行或不确定的原操作没有产品内恢复入口，重新确认可以创建新操作；旧 timer 还持有已脱离当前界面的对象。
- 证据 B：已打开并核对 task 候选后，来源与任务均失权，`executeAction` 只核 action revision/task graph revision/online，不核来源可用或策略失效，仍进入 running 并带着旧输入；source 权限变化不一定改变 task graph revision。`reviewAction` 也会继续从旧 proposed 复制资料。此为受审原型的真实状态转换，与文档撤源边界相反，不推断后端已泄漏。
- 后果：用户正常在两项建议之间切换，会丢失需查询的旧操作并可能重复启动有副作用工作；来源失效后界面仍引导其确认旧资料，实施者无法按 must-match 同时实现正确失效与现原型语义。
- 需修订：按候选/operation 保留独立持久状态，视图切换不等于创建/遗忘任务；已提交/unknown 操作回到原状态和同一查询入口，callback 绑定其操作身份。候选在预览及提交前核当前 source/policy/输入版本，失效后明确不可提交，不能从缓存静默复制。已开始动作的撤销应如实反映停止/未知/可能已有外部效果，不能伪报已经回滚。
- 关闭证据：搜索↔任务往返分别覆盖 running/unknown/complete，保持原 operation 且不额外执行；候选预览前后来源排除/失权/清理均阻止旧输入新提交；保留可理解的恢复、重新准备与返回路径。

#### R3-W2 — 保留 unknown 旧回执后，新联系请求仍停留在已完成旧请求

- 分类：实质交互生命周期，可自主修复；延续 R2-W5 的窄残余。
- 位置：`prototype.html:101–107,116,122`，对照 `specs/im/personal-agent.md:61–65`、`design.md:106,207`。
- 证据：`saveContacts` 对 unknown/sent 不设置 contactRevoked，合理保留旧投递查询；但 `externalSend` 仅在 contactRevoked 时创建新请求。静态连续路径为：unknown 旧投递 → 屏蔽 → 解除 → `finishRelease` 核实旧操作 → 对方新消息。结果仍为旧 `status=sent`、`deliveryId=old-op`、无新 requestId，仅 followup=true；本人侧继续展示“已回复”，对方仅得到“其他安排需要另行征得同意”，没有新待确认请求。
- 后果：解除后有效的新请求不能形成新的本人决定，私料请求被口头承诺会征询却没有实际接续。不能为了不恢复旧许可而把会话永久绑定到已结束请求。
- 需修订：将联系策略、请求实例与投递 operation 分离；旧 unknown 仍只能查询原回执，旧 sent 记录保持；解除后的新消息形成新的 request/source/version，不继承旧批准。若旧投递未决时先保存新消息，应明确待处理关系，旧结果确认后仍可推进新请求而不自动重放屏蔽期消息。
- 关闭证据：分别从 waiting、sending、unknown、sent 开始，覆盖屏蔽/解除/新消息和回执先后顺序；新有效消息可形成 fresh request，旧许可从不复活，unknown 从不重复发送。waiting 分支本轮已通过，不需重报原已修 bug。

#### R3-W3 — 仍缺实际渲染、关键交互视觉观察与当前客户端对照

- 分类：环境/资源与必要体验证据阻塞；延续 R2-W6 / R1-W7。
- 位置：`design.md:190–213,248`；共同体验标准。
- 本轮无成功渲染/代表截图/现客户端对照。新增确认及结果视图同样未经过实际视觉判断。76 项作者静态断言与本轮 vm 复现均不能替代观察；未重试历史被拒浏览器、socket、clipboard/frame 路线。
- 恢复条件：提供正式允许且可达的真实浏览器路径，完成适用 viewport 与关键旅程的独立观察并留证；或收到用户对这项门禁顺序/验收方式的明确调整。当前未收到此授权，不能预先后移或豁免。

#### R3-W4 — DeepSeek 真链路必验资源仍未落实

- 分类：纯资源阻塞；延续 R2-W7 / R1-W8。
- 位置：`design.md:248,254`，M1 W7。
- 设计与本轮派发均确认云端 DeepSeek 未配置；未读取秘密、未推断有凭据、未将静态 DSH 包取证或旧基线测试视为真实请求/产品送达证明。
- 恢复条件：按安全方式落实隔离环境模型资源，后续执行既定真链路验收；或用户明确授权调整此前置顺序。当前无授权，仍阻塞 Gate 2。

### Recommendations

无新增非阻断建议。本轮只要求闭合已受影响的连续生命周期与仍缺的门禁资源，不扩展为全产品重设计，也不因已有两项环境阻塞而掩盖可自主修复的问题。

### Author Resolutions after Round 3

- R3-W1 accepted：原型按动作类型保存独立operation与状态，切换不覆盖running/unknown；任务来源失效在预确认、提交、回执与结果新输入处检查，已提交操作保留ID且阻断后续回流。
- R3-W2 accepted：联系撤销标记也覆盖sent/unknown，但保留旧投递身份供查询；旧unknown完成后新消息另建新请求，不能继续旧许可。
- R3-W3/W4 unresolved：实际视觉与DeepSeek仍为环境门禁，无顺序调整授权。
- 新增9项静态连续检查通过，非实际执行证明；本轮只修原型状态，正式架构不再扩展。


## Round 4

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/prepare_pa_implementation_gates/review_pa_design_gate`；非设计作者，仅追加报告。
- reviewer target: `docs/changes/feat-616-personal-agent` 的 R4 冻结树。
- review_mode: **closure**。
- mode_reason: R3→R4 的 14 项 manifest 比较确认只有 `prototype.html` 改变，spec/design/10 个 delta/M1 骨架全部未改。仅复核 R3 两项交互问题及其已要求的在途/回执顺序，不重开架构审查。
- retained_from: **Round 3** 的设计/契约关闭与资源状态；生产组装、职责复用及运行时公开能力继续保留 R1/R2 full 的证据。没有重新读取产品代码或执行环境验证。
- started_at: `2026-10-16T18:05:30Z`
- completed_at: `2026-10-16T18:07:19Z`
- duration: `1m 49s`
- executed_base / HEAD / 本地 origin/main: `481467ac16f0eda4561fca5c8230050541600de9`；未重新查询远端。
- validated_at: 当轮 HEAD 加未提交的 R4 冻结设计工作树；当时逐文件校验 14/14 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- working tree: 仅本 unit 未跟踪、tracked diff 为空。本轮仅追加报告；原报告（含 Author Resolutions after Round 3）SHA-256 `e2c82651dc2e8182e1f5e1c13f30887ccf35e063c7e1c4f2c87baa6d20b87bad`，原字节全部保留。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

前轮明确的三条路径已修：动作往返不丢原 operation、失权来源不能新提交、旧联系回执完成之后的新消息能建 fresh request。仍有 **2 项原生命周期问题的窄残余**：撤权后失去旧操作查询入口；新联系请求在旧回执未决期间到达后不能接续。另保留 **2 项资源阻塞**。没有新增架构问题，Gate 2 仍不通过。

### Coverage 与独立闭环证据

#### R3-W1：动作身份、来源失效与原操作恢复

- `prototype.html:44,124` 新增按 kind 保存的 action 对象。对 task 的 running、unknown、complete 三种状态分别执行“返回→打开 search→返回→打开 task”，都保持相同状态与同一 operation；callback 持有原对象，不再因切换丢失。**此部分关闭。**
- `prototype.html:126,128` 在准备/提交 task 时检查 task 可用及 sourceActive。复现来源和任务均 unavailable 后确认，得到 blocked/operation=null；没有创建新操作。回调与结果选择也有来源检查。**原提交前失权路径关闭。**
- 但是来源在已提交/unknown 后变化会将执行状态覆盖为 blocked，查询入口也消失，不能只凭保留 ID 声称恢复已闭合；见 R4-W1。

#### R3-W2：联系策略与请求/回执生命周期

- `prototype.html:122` 对 sent/unknown 同样标记 contactRevoked，并保留 deliveryId。旧回执已经核实后，新外部消息通过 `externalSend` 新建 requestId/version，状态 waiting，旧 deliveryId 不继承。**R3 的“先完成旧回执、后收到新请求”复现已关闭。**
- 普通 waiting→屏蔽→解除→新消息路径继续有效，原批准不复活。unknown 保留查询、以及“先收到解除后的新消息、后核实旧回执”的顺序仍不闭合，见 R4-W2。

#### 验证边界

本轮再次在 Node `vm` 中执行受审 HTML 的原始 script，仅替换 render/focusPanel、空 DOM 查询和可控 timer；对产品内可达入口同时检查原函数返回的面板/卡片 HTML。未调用网络、浏览器、产品后端或秘密读取。结果摘要：

```text
switch running  -> running, same operation=true
switch unknown  -> unknown, same operation=true
switch complete -> complete, same operation=true
pre-submit source revoked -> blocked, operation=null
unknown then excluded -> blocked, original operation retained,
                         query control=false, only return control=true
contact unknown -> block -> unblock -> close settings:
  status=unknown, contactRevoked=true, deliveryId=old-op,
  owner card review/query entry=false
new message before old receipt resolved -> old status=sent,
  requestId=null, contactRevoked=true; message remains in old messages
another new message after resolution -> waiting, new requestId,
  contactRevoked=false, deliveryId=null
```

作者 46+13+17+9 共 85 项静态断言仅为补充。上述复现不是视觉体验或真实投递证明；没有因静态检查通过而改变视觉/DeepSeek 门禁。

### 历史问题闭环

| 原 issue | 作者修订 | 本轮证据 | 状态 |
|---|---|---|---|
| R3-W1（R2-W4 残余） | 按 kind 保留 action；各阶段来源检查 | 三种状态切换与失权前提交已通过；已提交操作被 blocked 状态遮掉核对入口 | **still-open**，范围收窄至 R4-W1 |
| R3-W2（R2-W5 残余） | revoked 包含 unknown/sent，旧回执完成后新消息重建 | 后到消息可重建；未决查询入口及先到新消息接续仍缺 | **still-open**，范围收窄至 R4-W2 |
| R3-W3 / R2-W6 / R1-W7 | 资源未解 | design 213/248 未变；无视觉观察或用户顺序调整授权 | **still-open**，R4-W3 |
| R3-W4 / R2-W7 / R1-W8 | 资源未解 | design 248/254 未变；DeepSeek 仍未配置且无顺序调整授权 | **still-open**，R4-W4 |

R3 已关闭的任务读写、PA 专业执行主体、广权限输出隔离，以及前轮设备交接、任务通知等结论保留；本轮未改这些事实。历史问题不重复计数。

### Issues

#### R4-W1 — 已提交动作撤源后，只保留 ID，失去原操作核对路径

- 分类：可自主修复的交互生命周期；R3-W1 残余。
- 位置：`prototype.html:128–131`，对照未改 `design.md:89,158,206,254`。
- 证据：task 已提交并进入 unknown 后，排除 team 来源并点击核对，`recoverAction` 先把 status 改 blocked；`actionPanel` 的 blocked 分支仅展示原 operation 与“返回，保留记录”，不再提供核对。running 回调在发现来源失效时也落入同一终态。用户能阻止新提交，但无法知道已经提交的操作是否完成、失败或仍未知。
- 后果：撤销资料使用资格与操作执行结果被合成一个 blocked 状态，未知外部效果永远无法在产品路径中核实。仅显示 ID 不能替代查询入口；也不能把停止后续内容处理视作已停止原运行。
- 需修订：独立保留“来源/结果使用已撤销”与“操作 delivery/execution 状态”；撤源不重发，但允许核对原 operation 的最小固定状态/真实回执，正文继续隔离，不自动回流。若运行已开始，应如实呈现停止请求、最终状态或仍未知，不能承诺追回既有效果。
- 关闭证据：running/unknown→来源排除→关闭再打开后仍能查询相同 operation；不创建新操作，不再使用旧确认，内容不自动进入 PA。无需真实后端实现即可在原型呈现这一路径。

#### R4-W2 — 联系撤销后旧回执不可达，未决期间的新请求没有接续

- 分类：可自主修复的联系请求生命周期；R3-W2 残余，同一请求/投递未分离造成的两个表现。
- 位置：`prototype.html:102,107,116,122,138–140`。
- 证据 A：unknown 请求被标 contactRevoked 后，`proactiveMessages` 在 unknown 操作按钮前命中“请求已撤销”分支；从联系设置返回本人聊天，没有 `reviewRelease` 或“核对发送结果”入口。`releasePanel` 虽有 unknown 查询分支，但正常产品入口不可达。记录 deliveryId 并未完成可查询恢复。
- 证据 B：解除后、旧回执未决时，对方发送有效新消息；`externalSend` 将其存进旧 messages，并回复“这条新请求尚未处理”。之后核实旧回执，`finishRelease` 只把旧请求置 sent，没有建立/唤起新请求。本人看到旧已发送记录，对方必须再发一条消息才产生 fresh request。该输入是解除后的有效消息，不属于应丢弃的屏蔽期重放。
- 后果：不确定投递无法从正常 UI 核实；已经正常收到的新请求被搁置却没有待处理状态或继续动作。用户需靠额外重发才能恢复交流。
- 需修订：保留历史投递的查询入口，区别它与已撤销的批准；新输入以独立 request/source identity 保存或明确排队，旧回执解析后推进新请求。可以要求 owner 点击明确继续，但不能只能等待对方再发消息。仅旧 operation 查询，不复活旧许可或自动重放屏蔽期输入。
- 关闭证据：分别验证新消息在旧回执前/后到达；均能从产品路径核对旧操作，并获得新的待处理请求/决定；旧 deliveryId/批准不被新请求复用。

#### R4-W3 — 实际视觉及当前产品对照仍缺

- 分类：环境/资源阻塞；retained from R3-W3。
- `design.md:213,248` 未变；没有成功真实渲染、代表截图和当前客户端对照，新交互视觉未验证。静态 HTML/VM/85 项断言不能替代实际观察。
- 仍需正式允许且可用的真实浏览器路径，或用户明确调整该门禁顺序/方式；目前未获调整授权。未重试历史被拒路线。

#### R4-W4 — DeepSeek 真链路资源仍缺

- 分类：纯资源阻塞；retained from R3-W4。
- `design.md:248,254` 仍要求真实 DeepSeek 链路，云端资源未配置；没有新证据或用户顺序调整授权。既有基线测试与静态包分析不替代该资源。
- 按安全方式落实隔离资源，或取得用户对前置顺序的明确调整后再复核；本轮未读取凭据。

### Recommendations

无新增非阻断建议。本轮仅收窄原问题的剩余状态组合，未增加产品功能或扩大架构要求。

### Author Resolutions after Round 4

- R4-W1 accepted：来源撤销与原operation回执查询分离；blocked操作仍有核对入口，核对不复活资料/结果或重复提交。
- R4-W2 accepted：contact unknown优先呈现原投递核对；未决期间收到的新消息单独暂存，核对完成后建立新请求。新一次屏蔽清除尚未处理请求，旧receipt身份保留。
- R4-W3/W4 unresolved：视觉和DeepSeek资源仍未解。新增6项静态序列检查通过，前9项也复验通过；只改原型状态。


## Round 5

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/prepare_pa_implementation_gates/review_pa_design_gate`；非受审材料作者。
- reviewer target: `docs/changes/feat-616-personal-agent`，R5 冻结树。
- review_mode: **closure**。
- mode_reason: manifest 比较确认 R4→R5 仅 `prototype.html` 改变；只复核两个原问题及同一请求替换的 sending/unknown 相邻时序，未扩大架构/功能范围。
- retained_from: **Round 4**（未改变的设计/需求/10 个 delta/M1 及前轮已关闭判断）；实际组装/运行时公开能力继续保留 R1/R2 full 证据。未重新读取产品代码。
- started_at: `2026-10-16T18:08:41Z`
- completed_at: `2026-10-16T18:10:13Z`
- duration: `1m 32s`
- executed_base / HEAD: `481467ac16f0eda4561fca5c8230050541600de9`，tracked diff 为空，只有本 unit 未跟踪；未刷新远端。
- validated_at: 当轮 HEAD 加未提交的 R5 冻结设计工作树；当时逐文件校验 14/14 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- write scope: 仅追加 `design-review.md`；此前全部报告与 Author Resolutions 原字节保留，前缀 SHA-256 `9ac9ffab7cbf93ff25bc888a0979832fed9c5022d54eb953b30d1c0b6eb1df97`。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

R4 的明确复现路径均已修复；联系请求替换的相邻 sending 时序仍有 **1 项可自主修复的竞态**。另外 **2 项资源阻塞**继续保留，Gate 2 不通过。本轮没有新增架构问题。

### Coverage 与关闭证据

本轮完整读取变更状态函数及其产品入口。沿用 Node `vm` 的纯原型验证：加载 HTML 原始 script，替换 render/focusPanel、空 DOM 查询与可控 timer；通过面板/聊天卡片 HTML 核实按钮入口。未调用网络/浏览器/产品后端，未读取秘密，不将状态机检查称为视觉或实际安全验证。

1. **已提交专业任务撤源后查询**：`prototype.html:129,131` 为 blocked 且已有 operation 的任务保留“核对原操作”。running→排除→回调 blocked→切换 search 再回 task→核对，保持同一 operation，receipt=confirmed，status 仍 blocked；选择结果后 shared 仍 false，面板不出现结果正文。未重发，也未把资料重新变有效。R4-W1 **closed**。
2. **联系 unknown 可达**：`prototype.html:116` 优先呈现旧投递查询入口，联系撤销不遮挡；releasePanel 原 unknown 查询分支可从本人聊天进入。
3. **未决期间的新消息接续**：`prototype.html:102,107` 将两条解除后新消息保存在 pendingIncoming；旧回执核实后建立 fresh waiting request，新 requestId/version、incomingSnapshot、无旧 deliveryId/批准，旧 receipt 单独保留。重复核对不再生成新实例。再次屏蔽会清 pendingIncoming；解除及旧回执完成不会重放已撤销的新请求。R4-W2 的两个明确复现路径 **已关闭**，但同一实例替换的 sending 回调仍有 R5-W1。
4. **未改判断 retained**：任务读写权限、PA 私密 authorized_task 主体、广权限结果隔离、设备交接、任务通知及两类确认 must-match 均未改；不重复审查已成立设计。

独立结果摘要：

```text
revoked action: original query entry=true
after query: same operation=true, status=blocked, receipt=confirmed,
             shared=false, result body visible=false
contact unknown owner query entry=true
queued inputs -> fresh waiting request, incomingSnapshot length=2,
                 deliveryId absent, reviewVersion=null, old receipt retained
repeated old query -> same fresh request
reblock -> pendingIncoming=[], no fresh request replay
old sending -> block -> unblock -> new message:
  before old callback: new request-4 / waiting / no deliveryId
  after old callback:  same request-4 / invalid / no deliveryId
```

作者随后报告原 46 项回归也通过，合计 91 项纯原型静态检查已归档至 `research/prototype-state-checks/`。这些文件是旁证、非本轮 14 项受审树；未逐项重跑或据此宣称全面通过。本轮关键路径由 reviewer 独立复现。

### 历史问题闭环

| 原 issue | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R4-W1 | blocked 原操作增加查询；独立复现保留 operation、确认回执、不回流正文 | **closed** |
| R4-W2 | unknown 入口优先；新消息单独暂存与接续、重复查询和再次屏蔽通过 | 原明确路径 **closed**；同一请求生命周期仍有 R5-W1 |
| R4-W3 / R3-W3 / R1-W7 | 无真实视觉证据或顺序调整授权 | **still-open**，R5-W2 |
| R4-W4 / R3-W4 / R1-W8 | DeepSeek 资源仍未配置、无顺序调整授权 | **still-open**，R5-W3 |

历史项不重复计数。剩余竞态是修复后替换请求与旧 callback 的关联问题，不否定本轮已验证的修复。

### Issues

#### R5-W1 — 旧 sending 回调按会话取当前请求，污染已替换的新请求

- 分类：可自主修复的联系请求生命周期竞态；前轮相邻时序。
- 位置：`prototype.html:102,106–107,122`。
- 证据：`approveRelease` 的异步回调保存 key，执行时通过 `requestFor(key)` 获取当前请求，而非原 request/delivery。按产品路径先批准旧回复进入 sending，随后屏蔽使旧请求 invalid、解除后新消息创建 fresh waiting request；旧 timer 返回时检查并修改的是新请求。独立复现同一新 `request-4` 从 waiting 变 invalid，notice 为“发送前信息发生变化，已停止发送”，但新请求从未提交。
- 后果：用户正确撤销旧请求并接收新请求后，仍会被旧操作完成事件错误撤销；若新请求已经进入确认/发送，还可能把旧回执错误归属到新操作。不能依赖 callback 到达速度或仅有一个演示会话消除该问题。
- 需修订：所有异步投递完成/失败/未知处理绑定原 request identity、delivery/operation identity 和版本，更新原操作记录；替换后的新请求不接收旧 callback。对旧请求的取消/已提交事实如实记录，不把新请求置失效、确认或完成。可捕获不可变原对象/身份并在必要时检查当前关联，但不能只按 conversation key 取最新请求。
- 关闭证据：sending→屏蔽→解除→新请求，分别令旧 callback 在新请求 waiting、review、sending 时到达；新请求状态/内容/许可/回执不被旧事件改变，旧操作只更新自己的历史。同一 callback 重复也不造成跨请求副作用。

#### R5-W2 — 实际视觉与当前产品对照仍未验证

- 分类：环境/资源阻塞；retained from R4-W3。
- `design.md:213,248` 未变，仍无真实渲染、代表截图或当前客户端对照。本轮及作者静态检查不能替代画面观察；未尝试历史被拒路线。
- 正式允许且可用的浏览器资源需落实，或用户明确调整此门禁顺序/验收方式；目前没有调整授权。

#### R5-W3 — DeepSeek 真链路资源仍未落实

- 分类：纯资源阻塞；retained from R4-W4。
- `design.md:248,254` 未变。当前未配置云端 DeepSeek 资源，没有新的真实链路证据或顺序调整授权；未读取凭据。
- 需安全落实隔离资源，或取得用户对此前置顺序的明确调整，再判断恢复条件；基线测试及 npm 静态取证不替代它。

### Recommendations

无新增非阻断建议；保持本轮窄范围，不扩展架构或以原型静态通过替代后续真实验证。

### Author Resolutions after Round 5

- R5-W1 accepted：异步release回调绑定原request对象及deliveryId，实例被替换后直接退出，不通过会话key修改新请求。新增sending→屏蔽→解除→新请求→旧回调六断言通过。
- R5-W2/W3 unresolved：视觉与DeepSeek资源仍未解；本轮只修原型回调。


## Round 6

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/prepare_pa_implementation_gates/review_pa_design_gate`；未创作受审设计/原型，仅追加审查报告。
- reviewer target: `docs/changes/feat-616-personal-agent`，R6 冻结树。
- review_mode: **closure**。
- mode_reason: R5→R6 manifest 对比确认只有 `prototype.html` 变化，修订为 release callback 的原请求/投递身份绑定；核实该竞态及其直接相邻的正常、unknown、重复回调路径，不重开未变架构。
- retained_from: **Round 5**；spec/design/10 个 delta/M1 骨架未变，前轮已关闭设计结论继续有效。生产组装与 DSH 公开能力证据仍引用 R1/R2 full，本轮不重读产品代码。
- started_at: `2026-10-16T18:11:05Z`
- completed_at: `2026-10-16T18:12:20Z`
- duration: `1m 15s`
- executed_base / HEAD: `481467ac16f0eda4561fca5c8230050541600de9`；未重新查询远端。tracked diff 为空、只有本 unit 未跟踪，无分支/提交操作。
- validated_at: 当轮 HEAD 加未提交的 R6 冻结设计工作树；当时逐文件校验 14/14 通过，不表示已提交的 unit SHA。临时校验清单已清理，历史内容保留在 Git 提交 `1190bbbfc`。
- write scope: 仅追加本报告；R1–R5 与作者 resolutions 原字节保留，追加前 SHA-256 `2bf089fe197378e19463847cfe57d57f5f8f6642bc42952cbecc88582b888bf5`。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

**截至本轮，已报告的可自主修复实质设计/交互问题均已闭合，本轮未发现新的实质问题。仅余实际视觉与 DeepSeek 两项资源阻塞。** 这不等于已实现或已通过实际体验/安全验证；没有用户调整门禁顺序的授权，故 Gate 2 仍不通过，不给附条件 Approved。

### Coverage 与独立关闭证据

`prototype.html:106` 的 callback 现在捕获 `submittedRequest` 与 `submittedDelivery`；返回时同时核对当前对象及 deliveryId，不匹配直接退出。因此旧会话 key 不能把旧回调作用于替换后的请求。两项身份检查位于 releaseInvalid、unknown 标记、notice 修改和 finishRelease 之前，拒绝路径没有新请求状态副作用。

独立加载 R6 HTML 的原始 script，在 Node `vm` 中替换 render/focusPanel、使用空 DOM 查询及可控 timer。对每种情况建立新的演示状态，不使用作者测试的通过结论替代复现：

- 旧 sending→屏蔽→解除→新消息：在新请求 **waiting** 时执行旧 callback 两次，完整 request 与 notice 序列化前后相同。
- 新请求已打开确认预览时执行旧 callback 两次，完整 request/notice 不变，批准版本未被污染。
- 新请求已单独批准进入 **sending** 时执行旧 callback 两次，完整 request/notice 不变；新请求自己的 callback 之后正常完成，按自己的 deliveryId 仅产生一条消息。
- 未替换的原请求：正常回调仍进入 sent，模拟未知回执仍进入 unknown，修复未使合法投递全部被拒绝。
- 同一个请求对象但 deliveryId 已变化：旧 callback 不改变对象，第二个身份维度确实生效。

```text
new waiting: old callback twice -> unchanged
new review:  old callback twice -> unchanged
new sending: old callback twice -> unchanged;
             own callback -> sent, one matching-delivery message
original request -> sent / unknown (respective paths)
same object, different delivery -> unchanged
```

以上是纯静态原型状态机证据，未使用网络、浏览器、产品后端或凭据。没有证明真实投递、真实撤权事务、真实 DSH 装配或视觉体验已实现；后续仍须按设计/M1 验收。R5 已关闭的操作回执与来源隔离、unknown 入口、新消息排队/接续/再次屏蔽路径未改，结论 retained。

### 历史问题闭环

| 原 issue | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R5-W1 | callback 绑定原 request 和 delivery；独立覆盖新请求 waiting/review/sending、重复旧 callback、原正常/unknown 分支及 delivery 变化 | **closed** |
| R5-W2 / R4-W3 / R1-W7 | 无新视觉资源或顺序调整授权；design 213/248 未变 | **still-open**，R6-W1 |
| R5-W3 / R4-W4 / R1-W8 | 无新 DeepSeek 资源或顺序调整授权；design 248/254 未变 | **still-open**，R6-W2 |

由 R1-W2–W4/W6、R2-W1–W5、R3-W1–W2、R4-W1–W2 延续的实质问题，以各轮关闭证据和本轮竞态修复为准全部闭合。R1-W1 设备交接和 R1-W5 任务通知继续 closed。这里汇总的是既有 findings 的状态，不扩张成未观察体验或未来实现正确性的保证；历史问题不重复计数。

### Issues

#### R6-W1 — 仍无实际渲染、关键操作视觉观察及现客户端对照

- 分类：环境/资源与必要体验证据阻塞；延续 R5-W2 / R1-W7。
- 位置：`design.md:190–213,248`，原型与共同体验标准。
- 当前没有成功的真实渲染、代表截图和现客户端对照；三宽度与关键确认/恢复交互视觉未验证。HTML/JS/DOM/VM 检查和作者静态断言均不替代实际观察。本轮未尝试历史被拒的浏览器绕行。
- 恢复条件：正式允许且可达的浏览器路径落实后，完成独立关键旅程观察并留证；或收到用户明确调整这项前置门禁顺序/验证方式的授权。当前没有此授权，不能自动后移。

#### R6-W2 — DeepSeek 真链路必验资源仍未落实

- 分类：纯资源阻塞；延续 R5-W3 / R1-W8。
- 位置：`design.md:248,254`，M1 W7。
- 云端 DeepSeek 仍未配置，无新真实请求/响应与产品送达证据，也没有用户调整该前置顺序的授权。本轮未读取秘密；既有基线 build/tests 和锁定 npm 静态取证不替代此资源。
- 恢复条件：按安全方式落实隔离环境模型资源，或取得用户对此前置顺序的明确调整；随后按保留的真链路验收要求验证，不把资源后移等同于省略验收。

### Recommendations

无新增建议。仅保留上述两个已明确的资源闭环，后续复审范围由新证据及受审树是否变化决定。


## Round 7

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/design_review_r7`；未创作本轮 spec/design/prototype，只追加本报告。
- reviewer target: `docs/changes/feat-616-personal-agent` 2026-10-19 目标推进版，工作树 `/Users/czj/.codex/worktrees/feat-616-personal-agent/nano-multiagent`，分支 `docs/feat-616-personal-agent-handoff`。
- review_mode: **full**。
- mode_reason: 核心产品责任、持续授权、私密执行能力、成果返回及主旅程均已重写；R6 closure 的范围不足以覆盖新方案，不沿用旧问题全部关闭即整体通过的结论。
- started_at: `2026-10-19T10:03:38+08:00`
- completed_at: `2026-10-19T10:10:15+08:00`
- duration: `397s`
- executed_base / HEAD: `f4162189f9ec50fe437913a68bd540d5d6ab3c0e`；没有 rebase、切分支、提交或刷新远端。
- validated_at: HEAD + 当前未提交修改。spec SHA-256 `afe88f532ffe7a0cef5e9ec8ac26861ff4b6f997378a9af0c5fd814ae21cb46b`；design `3224d93edb1eda785290a350843988a8dd6ba3d027121fd50e8a7375726afd64`；prototype `3ed05914b788b099b7a84914fba0c0c1a392bf5d6d382f17e1150856350305c7`。作者在本轮中途修订 unknown 自动核对及群成员呈现后，reviewer 已 reload 自己的 tab 并按最终版本重新走主链。
- write scope: 仅追加本报告，旧前缀 SHA-256 `8b02f5bdfc012f417d8afab2f4a863a3da7a2b7aceb8b5f808e07a7a427c9991`；保留既有 dirty/untracked 文件，不创建截图或其他文件。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

持续目标版已实质减少用户操作：一次交办后普通准备直接推进，内部成果自动承接，业务选择和新增披露各有清楚含义；本轮没有发现需要重做核心架构或恢复逐动作 PA 审批的问题。仍有一项直接复现的稍后提醒问题，以及当前产品画面对照、真实模型资源两项前置缺口，故不签发 Gate 2 Approved。该结论不阻止交付本轮明确请求的设计、可评审原型及模拟录像，也不要求本轮实现产品后端。

### Coverage 与证据

**需求、决定和模块职责。** 本轮读取最新 spec/design、10 个 delta、当前 global-agent / agent-work / task-graphs 契约及安全验收场景；核对命名、自动观察、四类 IM 关系、普通工具同策略、持续授权、任务唯一事实、安静跟进、内部返回、对外范围、恢复与来源清理。新文档明确替代历史 authorized_task 人工批准/结果重新提供链，因此不再把这些旧门禁当作必须恢复的行为。

从真实组装入口向下核查，而非只看测试：`apps/node/src/main.ts:41–61,234–262` 创建 RuntimeSupervisor、GlobalAgent、Heartbeat，并将 `product.call` 交给 GlobalAgent；`apps/im-server/src/main.ts:57` → `server.ts:164–170` → `control.ts:959` 注册 onboarding/messaging/work/task 路由。`packages/personal-assistant/src/global-agent.ts:46–109,149–198` 现有 global binding、可靠 Inbox wake、schedule evidence 与 task_graph relay 确认复用落点；`heartbeat.ts:48–77` 的 due/pending 与 onlyIfIdle 说明精确跟进不能仅靠普通 heartbeat。`apps/im-server/src/task-graphs.ts:370` 起持久图与幂等回执同事务，任务 actor/revision/通知应继续在 IM 落地。

架构判断：目标业务状态保留在 task_graph，pa_assistance 只附加跟进/等待/提醒关联，较新增第二任务库简单且避免双写状态；DSH 承担调度/执行，PA 负责来源关联、授权范围和交付，IM 负责身份、ACL 与权威任务写入，职责与现有依赖方向相符。private child 复用既有内部委派，外部 shared Agent 仍需明确协作许可。`approval.ts:102–121` 确认当前 safe fast path 与既有 ask/deny/Auto 是真实产品路径；新版“同配置、同意图同权限结果”可沿此实现，不需要新增 PA 人工审批链。它也意味着普通广权限工具风险不会凭 PA 名称消失；设计及安全场景已明确把这一点留给真实攻击/有用性验证，不将 host ACL 夸大成同 OS 强隔离。

external/observation 的 fresh session、executionProfileId、动态工具 ceiling 和注入隔离继续引用 `research/execution-isolation-feasibility.md` 的锁定公开 exports 取证；本轮检查其边界与新方案相容，未重新下载依赖或宣称实际隔离已经实现。来源排除重建、owner/node epoch 和私人 Work/附件/WS 的 host 边界仍需 M1 实现验证。

**delta 与跨平台。** 逐一将 MODIFIED requirement 锚回相同 canonical 文件/标题，并比较原 Scenario 标题集合：8 个包含 MODIFIED 的 delta 中，27 个修改目标全部存在，没有丢失旧 Scenario 标题；同时检查 PA 特例前言、普通主体场景、任务 actor/revision 与原通知语义。新增 personal-agent 两文件为 ADDED；没有借归并把普通 Agent 的工具/跨聊天规则或公司任务普遍扩权。Web 桌面为侧栏/目标摘要/私聊，窄屏为隐藏导航与全宽详情/面板，已有足够具体的内容顺序和动作方案；原生 iOS 新导航明确不在本轮范围，既有聊天/任务/API 回归纳入 W7，不把窄屏 Web 当作 native 证据。

**独立原型观察。** 用 CUA 在独立隐藏 IAB tab 打开 `http://127.0.0.1:8766/prototype.html`，未绑定或操作作者录像 tab。先观察实际画面，再核源码和清单。最终冻结版独立完成：

1. 390 预览：交办演示 → 自动准备 → 推荐零售/制造案例 → 选择后自动制作 → 打开可阅读的演示页面 → 回同一目标 → 查看外发身份、群成员、正文与两份附件 → 一次确认。
2. 下次发送回执未知：确认后按钮不允许重复提交，页面说明核对同一次发送；随后自动进入“等林悦确认”，无需用户点核对。只证明模拟交互，不证明网络幂等。
3. 暂停观察 → 模拟林悦确认 → 界面说明“确认已到原群；观察暂停，PA 尚未读取” → 恢复观察后同一任务完成，第二目标仍独立存在。发送成功之前不展示目标完成。
4. 768 与 1440 预览检查导航、已完成目标和“周五杭州行程”独立摘要；390 的成果/外发面板保留固定返回或提交区域，正文可滚动，关键身份/受众/操作未被裁掉。1440 是原型提供的缩放预览，不声称原生设备验收。
5. 初始版本独立走过“16:00 再提醒我”→快进到16:00→同一案例卡重新出现；最终冻结文件仍保持该卡与 snooze 的硬编码时间，形成 R7-W1。unknown/群成员的后续改动不涉及此函数。

视觉判断：紧凑目标摘要持续回答当前阶段；推荐、理由和两项业务后果在选择区邻接；预览与分享分开，分享页可同时判断谁将收到什么；手机面板的返回/提交位置稳定。这些直接支持本轮主链体验，不仅是“按钮可用”。当前客户端的真实导航/密度/交互对照尚未成立，见 R7-W2。

**milestone 与验收前置。** 单 M1 已同时列 reviewer 用户结果和 worker 原型对照、授权/恢复/任务并发/资产隔离验证；未把原型静态结果或历史 97 项脚本当作真实产品通过。作者三宽度录像报告 `research/prototype-goal-journey-validation.md` 在本轮核查时尚未写入，未提前引用为通过证据；作者已口头报告的录像仅作待交付材料，不影响上述独立结果。DeepSeek 仍按 R7-W3 保留。

### 历史问题闭环

| 原 issue | 本轮核查 | 状态 |
| --- | --- | --- |
| R6-W1 / R5-W2 / R1-W7 | 当前可用浏览器已完成上述独立渲染、连续操作与跨宽度观察；旧“没有真实浏览器”的资源判断不再成立。design 明确没有当前产品真实画面对照 | 原型资源部分 **closed**；当前产品对照 **still-open**，合并为 R7-W2 |
| R6-W2 / R5-W3 / R1-W8 | design:166 明确保留未落实 DeepSeek 资源；无新的可用性证据或门禁调整授权 | **still-open**，R7-W3 |
| R5-W1 及 R1–R4 已关闭的旧逐动作/结果交接交互问题 | 本轮原型与授权模型已重写，旧 request 生命周期不作为新版完整正确性的证据；新版 unknown 已独立观察自动核对，核心主链重新审查 | 旧结论保留历史，不再把旧实现检查机械移植为新要求 |
| 设备交接、任务系统通知、外部私人 Work 边界 | 新 design 与对应 delta 保留上述限制及实际 actor/owner/revision/受众要求，未恢复跨 owner 私料转移或普通 Agent 委托越权 | 设计约束保留，实际实现待 M1 |

### Issues

#### R7-W1 — 到达提醒时间后，“稍后”仍承诺同一个已经到达的时间

- 分类：可自主修复的原型交互问题。
- 位置：`prototype.html:37,46,91,110`；对应 design:77、spec“关键业务取舍/稍后提醒”。
- 证据：案例选择卡点“16:00 再提醒我”，再通过外层事件推进到16:00，卡片恢复但仍提供“16:00 再提醒我”。`snooze()` 只设 boolean 并固定通知16:00，没有新的 future deadline；再次稍后只能进入“好，16:00 再提醒你选案例”。这是主旅程已有按钮的实际操作，不是假设边缘情况。
- 用户影响：用户在约定提醒时仍暂时无法决定，会被承诺一个已经到达的时间，无法理解下一次何时提醒；实现者若照原型兑现，也会得到反复即时提醒或无后续唤醒的两种错误解释。
- 需修订：稍后动作生成并展示一个晚于当前模拟时间的新提醒点；摘要、决策卡与时间推进使用同一提醒值。只需覆盖当前主旅程，不要求新增完整日历编辑器。
- 关闭证据：首次稍后→到期→再次稍后，显示新的未来时间；再次到期仍是同一决定、后台准备保留且无重复目标。

#### R7-W2 — 原型已可真实观察，但与当前产品的实际界面对照仍缺失

- 分类：必要体验证据缺口，保留 R6-W1 尚未闭环部分；不是浏览器不可用。
- 位置：`design.md:34–39,149`，`research/prototype-ux-review-2026-10-19.md`。
- 证据：design 明确前轮材料是原型对照、不能替代现网客户端画面，本轮未运行当前客户端。reviewer 核实真实产品 `AppShell` 的桌面顶部导航和 mobile bottom bar，以及 chat-workspace 的会话列表/详情组装；原型呈现全局左侧导航/目标列表和手机抽屉。源码只能证实差异存在，不能代替画面及相关动作对照。作者亦确认目前只有静态原型服务。
- 用户影响：下游尚不能判断新增 PA 固定入口与既有聊天/任务导航在实际产品中的并存方式、密度及返回路径；按原型整体替换或局部嵌入可能形成不同体验。
- 需补证：允许环境下观察当前产品对应入口/相邻页面，用可复查画面与短路径说明哪些沿用、哪些明确改变及原因；隔离现有产品即可，不要求先实现 feat-616 后端，也不要求访问生产私料。补齐前不得把“像 IM”或组件名称相同当作已对齐。

#### R7-W3 — DeepSeek 必验资源仍未落实

- 分类：纯实施验收资源前置，延续 R6-W2；不算本轮静态原型功能失败。
- 位置：`design.md:166,174`，M1 W7。
- 证据：当前文档仍记云端凭据未落实，没有新的隔离资源可用性证据或用户调整前置顺序的明确授权；本轮未读取、搬运秘密，也未要求运行尚未实现的产品链路。
- 影响：后续真实模型的有用性、来源隔离与送达验收仍没有可执行资源保障，不能凭模拟视频通过 Gate 2。
- 恢复条件：安全落实授权隔离环境中的模型资源，或取得并记录用户对前置顺序的明确调整；最终真模型验收继续保留。无需为交付本轮设计/录像提前完成产品实现。

### Recommendations

无新增非阻断建议。本轮完成所需主链和边界覆盖后停止扩展原型分支；修复后按实际变化进行一次有界复核。


## Author Resolution — R7-W1 (2026-10-19)

R7-W1 接受。稍后提醒从当前模拟时刻计算：09:42时为16:00；到达16:00后再次稍后为17:00，再到期后为18:00。决策按钮、目标摘要、承接文案、详情和演示事件读取同一提醒值，不重复承诺已过时间；外层演示按钮改为“下一次提醒 / 跟进到达”。本轮只修该分支，视频主链的09:42→16:00流程不变。R7-W2/W3资源事实未变化，不声明关闭或Gate 2通过。

补充同轮走查修正：最终完成卡调整到历史跟进记录之后；切换回目标定位最新进展。避免完成后最下方仍是16:00“尚未确认”的旧记录，让用户误判当前状态。该修改不改变授权或结果条件，将重新录制最终主链。

R8窄复核中继续修正同一时间源：发送后的nextCheck按当前模拟时刻生成，并由目标摘要、等待卡、原任务、详情及模拟到达共同读取；跟进后用lastCheck记录已执行时间，nextCheck向后推进。因而17:00选择并发送材料后，下一次检查为18:00，不退回16:00。


## Round 8

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/design_review_r7`；只追加报告。
- reviewer target: R7-W1 Author Resolution、相邻等待阶段时间与完成卡顺序；同一工作树/分支，HEAD `f4162189f9ec50fe437913a68bd540d5d6ab3c0e`。
- review_mode: **closure**。
- mode_reason: 仅修原型的提醒时间、相邻跟进时间与完成记录呈现；spec/design 哈希与 R7 相同，无核心范围或接口变化，不重开 full review。
- retained_from: **Round 7**；需求、架构、10 个 delta、跨端范围与 M1 判断继续有效，两项资源事实未变。
- started_at: `2026-10-19T10:12:48+08:00`（本轮首个显式计时点，进入浏览器稍早于此）
- completed_at: `2026-10-19T10:16:20+08:00`
- duration: `212s`（显式计时区间）
- validated_at: 最终 prototype SHA-256 `c699986cfe234f2c15db48d11ef191609ae9f74652b1ede1d9a298f2e3080af6`；追加前报告 SHA-256 `a55538f881c9681912a433b1c3ed7177c97550d4c281b97d2a7e5b7fe2aaa516`。本轮中发现相邻时间遗漏后由作者修正，reviewer reload 最终版本重新走该路径。
- write scope: 仅追加本报告；无产品修改、分支、提交或部署操作。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

**R7-W1 及本轮同源时间遗漏已关闭，完成结尾呈现通过；没有未关闭的新增实质交互问题。** 两项既有前置缺口仍在，故 Gate 2 未 Approved；不阻止本轮设计/原型录像交付，不要求部署或实现新后端。

### Coverage 与独立关闭证据

本轮 IAB 返回不可用；CUA inventory 仅列 Chrome，随后创建独立 `R8 原型复核` Chrome session/tab，未绑定或操作用户/作者原有标签。通过可见按钮、选择器和输入实际运行，不通过改页面状态跳过流程。

1. **连续稍后**：09:42交办 → 自动准备 → 点“16:00 再提醒我”；目标摘要和承接卡都显示16:00。点击外层“下一次提醒 / 跟进到达”的模拟到达，时钟16:00、同一选择卡提供17:00。再次稍后，摘要/卡片都为17:00；再次到达，时钟17:00、按钮变为18:00。原TASK-184及另一行程目标保留，无重复目标。
2. **相邻等待阶段**：首次复验继续选择案例和分享时，时钟17:00却出现“今天16:00检查”，即时反馈作者并在本轮一起修正，不另开无界分支。最终版重新从交办走连续稍后到17:00，选择案例→自动制作→确认分享，摘要和等待卡均显示18:00；再次模拟到达，时钟18:00，摘要/等待卡/历史跟进消息都记录18:00已检查、19:00再检查，没有退回固定16:00。源码 `prototype.html:25,36,38,47,66,71,92,95,111` 使用当前clock生成提醒/nextCheck，并以lastCheck保留已执行时间；不要求新增日历机制。
3. **完成结尾**：产生一次“仍未确认”历史跟进后模拟林悦确认，真实AX顺序与画面均为历史跟进在先、最新完成卡在后。切换周五行程再回客户演示，稳定滚动位置完整展示完成卡、已完成条件与两个后续按钮；没有以旧催办记录作为结尾。最终时间修订后再次完成，旧18:00跟进仍位于完成卡之前。对应 `prototype.html:54–55,82`。

以上证明当前静态原型交互与呈现。没有证明真实调度、持久化、模型调用或外发已实现。已读取作者新写的 `research/prototype-goal-journey-validation.md`，其三宽度操作与证据局限可供复查；最新版视频仍在重录，本轮不宣称视频文件已完成或独立验收录像。R7的独立390主旅程、768/1440呈现证据保留，不为本次时间文案重跑全套视觉检查。

### 历史问题闭环

| 原 issue | Author Resolution / 本轮证据 | 状态 |
| --- | --- | --- |
| R7-W1 | 提醒按钮、摘要、卡片按当前clock递进；独立实际验证16→17→18，同目标正常继续；相邻分享后18→19亦复验 | **closed** |
| R7-W2 | 新验证记录仍明确缺少当前真实IM客户端画面对照；本轮只测原型，未产生新的现产品证据 | **still-open**，R8-W1 |
| R7-W3 | 模型资源与前置顺序未变化；未读取秘密，未运行产品/模型 | **still-open**，R8-W2 |

### Issues

#### R8-W1 — 当前产品真实界面对照仍待补齐

- 分类：必要体验证据缺口；retained from R7-W2。
- 位置：`design.md:34–39,149`、`research/prototype-goal-journey-validation.md` 证据边界。
- 当前原型已有真实浏览器证据，但仍没有当前产品入口及相邻界面的真实画面/路径对照，不能确认新固定PA入口与既有聊天/任务导航如何并存。补证范围保持R7要求，不新增产品实现或部署前置。

#### R8-W2 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R7-W3 / R6-W2。
- 位置：`design.md:166,174`，M1 W7。
- 无新的隔离模型资源可用性证据或用户调整前置顺序的授权；后续真实模型有用性、安全与送达验收资源仍待落实。当前原型和录像不能替代，亦不要求本轮先实现后端。

### Recommendations

无新增建议。当前实质原型修正已完成有界复验，停止扩展检查；后续仅按新增证据决定是否复审。


## Author Resolution — 现有 UI 校正（2026-10-19）

用户要求撤回全局侧栏改版。spec、design、IM PA delta 与 prototype 已保持现有桌面顶栏、消息列表、手机列表/底部导航；只增加 PA 入口、私聊内目标进展、普通聊天回复帮助与已授权观察的主动接手。目标保持持续推进，未恢复搜索或内部委派审批。

对 R8-W1 新增当前真实 React 组件的隔离渲染对照及截图，详见 `research/existing-ui-alignment.md`；合成会话不声称真实后端产品验收。R8-W2 的 DeepSeek 资源状态未变化。请独立复核当前 UI 与相关文档 delta，保留历史报告。


## Round 9

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/design_review_r7`。
- reviewer target: 用户要求恢复现有 UI 后的 spec/design/prototype、IM PA delta 与 `research/existing-ui-alignment.md`；同一工作树/分支，HEAD `f4162189f9ec50fe437913a68bd540d5d6ab3c0e`。
- review_mode: **delta**。
- mode_reason: 全局导航回归既有框架、PA 多目标收回私聊、普通聊天辅助回复是有界但实质的 UI 变化，需重新看画面与相关路径；目标授权、执行/任务职责、安全接口和 M1 范围没有新增变化，无需重做 full 架构审查。
- retained_from: **Round 7 / Round 8**。R7 的非 UI 架构、任务唯一事实、安全接口与跨端范围判断，R8 的递进提醒时间修复继续有效；旧全局侧栏/手机抽屉的体验结论由本轮替代，R8-W1 根据新证据重审。
- started_at: `2026-10-19T11:05:10+08:00`
- completed_at: `2026-10-19T11:10:28+08:00`
- duration: `318s`
- validated_at: HEAD + 冻结的未提交文件；spec SHA-256 `680f79e14258a24508a01c164387ae199771e381be3bff1c9144b850400a286a`；design `0931c69945aa4bb65acf812834355635223389cf30818835a6ddfd98dc10a761`；prototype `11ca546ab00d1f86c3e0620fd89745e6df6b313464539ea47188d270d0c25f23`；IM PA delta `78cdcbb67a6287564e4a9b7f93f5bfc4bb0a3e302f7babb7379fc70984024223`；UI 对齐记录 `e57ecf8f2ad7a406924c0d9b7214ade8c740e1df16ad29e16266189265ab77f0`。
- write scope: 仅追加本报告；追加前报告 SHA-256 `3d2c90bb872a428f159a7ba4fa0482ad963a90aaaf4cd1fd31dc0937f95ba8f1`。未修改原型/产品/设计、未提交、未操作作者或用户标签。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

**现有 UI 对照缺口 R8-W1 已关闭；本轮未发现新增实质体验问题。** 方案已回到现有 IM 的桌面顶栏、消息列表和手机列表/底栏，PA 的目标索引与协助在本人私聊内承接。仅 DeepSeek 实施验收资源前置仍未落实，故不签发 Gate 2 Approved；这不阻止交付当前设计、可评审原型及明确标识的模拟录像。

### Coverage 与独立证据

**当前产品对照。** reviewer 自建三个 Chrome 标签，分别打开原型 `http://127.0.0.1:8766/prototype.html`、现有组件桌面 `http://127.0.0.1:8767/` 和390宽手机基线 `/frame.html`。先看实际渲染并操作返回列表，再核对夹具与源码。`/tmp/feat616-ui-baseline-20261019/baseline.tsx` 直接导入当前未修改的 AppShell、ConversationSidebar、MessagePane、useIsMobile、global.css，Query 缓存及消息为合成数据；它不是手工仿绘的基线，也不是完整产品后端验收。

实际产品组装落点核对 `app/router.tsx:38–39` → `chat-workspace-page.tsx:1091–1092,1147,1169,1217–1218`：桌面并列列表和消息，手机按会话选择二选一，返回 `/chat`。`app/shell/app-shell.tsx:22–69` 控制桌面导航和手机会话隐藏底栏；`styles/global.css:413–414,1662–1674` 与 `hooks/use-is-mobile.ts:3–4` 对应48px顶栏、262px列表及768断点。被引用组件/样式相对本工作树 HEAD 无未提交差异。基线画面确认上述结构、原聊天/任务/智能体顺序、手机四项底栏、灰色对方气泡和浅绿本人气泡；原型保持这些关系，只增 PA 固定项、快捷入口及聊天内协助内容。

**相关增量路径。** 所有操作通过可见 UI 控件完成，无注入内部状态：

1. 林悦私聊 → “让小航帮我回复” → 回填原输入框 → 改成“明天上午发给你确认” → 切到 PA → 返回林悦：修改后的草稿仍在原会话，PA 输入框为空。发送后显示本人浅绿消息，输入框清空，明确已回复的问题不再重复提醒。
2. 重置合成场景后模拟已授权范围的消息到达：PA 在本人私聊引用林悦和群的来源，先提出接手，未提前对外承诺；点一次“交给你跟进”后关联原 TASK-184，自动从准备进入带理由的案例选择。
3. “跟进中2”在 PA 标题内展开两件事；切到周五行程并输入独立草稿，经全局“聊天”再回 PA，仍在周五行程且草稿保留。返回演示时是原待决定事项，输入框不混入行程草稿。没有全局左侧目标栏或新增任务中心。
4. 在768预览选择零售案例，自动制作成果；切390预览后从聊天返回列表，底栏恢复聊天/任务/智能体/我四项；固定 PA 项再次进入原目标，底栏隐藏，成果与输入框可达。材料分享面板同时展示 PA 身份、陈同学/林悦/小航三个收件成员、可编辑正文及两份附件范围，底部确认/保留动作可见。
5. 一次确认分享后进入“等林悦确认”，显示16:00检查；模拟到期后显示16:00已跟进、17:00复查，无再次审批。再模拟林悦确认，原任务完成且跟进数减为1；最终完成卡位于旧跟进消息之后。回周五行程仍显示独立推进及此前未发送草稿。
6. 实际观察自适应桌面、1440、768、390画面。768保留并列消息列表及紧凑顶栏，390隐藏全局框架并保留返回/目标索引/设置；手机列表结构与真实组件对照一致。1440完成页的当前摘要、历史记录、完成结果和后续按钮可区分。预览是浏览器 iframe 的逻辑宽度，不作为原生 iOS 设备证据。

体验判断：PA 入口在既有会话体系可发现；目标选择没有抢占全局导航；正常回复的原收件人与本人发送身份清楚；目标摘要、决定、成果、等待、完成连贯，手机新增信息没有截断主要动作。当前密度和局部卡片差异没有构成需要进一步风格迭代的用户代价。

**文档、职责与验收。** spec 最新“现有 UI”约束、design:135–163 和 `specs/im/personal-agent.md` 的新增框架/回复 Scenario 一致；该 delta 为 ADDED，不覆盖现有普通聊天契约。M1 的 R1/W1/W2 已落实既有框架与三宽度对照。其他任务/智能体/账户页面只是原型背景，文档明确不重做其整页设计；原生 iOS 新导航仍不在范围。PA 多目标面板只索引原任务投影，继续复用现有聊天组装和 task_graph，不引入第二任务库或第二导航体系。旧录像/走查已明确被当前导航证据替代，不能用旧侧栏截图指导实施。

本轮证明当前静态交互与布局对齐；没有证明真实发送、后台调度、持久化或模型已实现，也未独立验收作者录像文件。没有新增跨包职责变化或要求提前实现产品的证据缺口。

### 历史问题闭环

| 原 issue | Author Resolution / 本轮证据 | 状态 |
| --- | --- | --- |
| R8-W1 / R7-W2 | 作者撤回全局侧栏，提供真实组件隔离基线；reviewer 独立观察桌面与手机并走返回列表、辅助回复、PA目标切换，核对实际组装与夹具导入 | **closed** |
| R7-W1 及 R8 相邻时间/完成卡问题 | 时间机制本轮未重新改动，保留R8连续稍后证据；本轮再次实走16:00跟进→17:00复查及完成卡在旧记录之后 | **closed，retained** |
| R8-W2 / R7-W3 | design:176 仍明确模型凭据未落实；本轮没有新的授权隔离资源可用性证据或前置顺序调整 | **still-open**，R9-W1 |

### Issues

#### R9-W1 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置，retained from R8-W2；不是本轮原型交互失败。
- 位置：`design.md:176,185`，M1 W7。
- 证据：当前设计仍写明云端 DeepSeek 凭据未落实，真实模型有用性、来源边界和送达验收需实施阶段执行；本轮没有新的资源可用性证据或用户调整前置顺序的明确授权。
- 后果：静态原型及模拟录像不能保证该必验链路可执行，Gate 2 仍未满足全部前置。
- 关闭条件：安全落实授权隔离模型资源，或记录用户对前置顺序的明确调整；最终真实模型验收继续保留。不要求本轮提前实现产品后端。

### Recommendations

无新增建议。当前 UI 修订已完成必要的独立对照与增量旅程，停止扩展审美或猜测性边界检查。


## Author Resolution — 可疑套取双向告知（2026-10-19）

按用户追加，spec 保存原话并新增可疑套取双向告知需求；design 第 7 节补充判断责任、来源证据、事件合并、owner 通知与外部告知的送达顺序、误会/屏蔽与正常工作不受影响。两个 PA delta 与安全验收同步。prototype 在原有 UI 内增加信息卡及外部事实告知，无新增审批页或产品导航。

新增不是 Instinct 已核实实现的声明，也不解决此前讨论的开放任务语义披露风险；模型可疑判断仍可能误判，通知不替代权限与隔离。DeepSeek 资源前置仍保留。请独立审查本次有界增量及其影响，历史结论不回写。


## Round 10

### Metadata

- reviewer: independent `change-design-reviewer`，`/root/design_review_r7`。
- reviewer target: 可疑套取双向告知的 spec、design第7节、IM/Gateway PA delta、安全验收、原型及作者走查记录；同一工作树/分支，HEAD `f4162189f9ec50fe437913a68bd540d5d6ab3c0e`。
- review_mode: **delta**。
- mode_reason: 新增有依据的可疑事件报告、本人/请求者双向事实告知和误会/屏蔽控制，需检查来源、送达依赖及新的 UI 路径；未改变目标授权、工具审批、external profile 隔离或任务事实边界，不扩大为 full 重审。
- retained_from: **Round 7 / Round 8 / Round 9**。架构、安全能力限制与递进时间修复保留；R9现有框架对照和普通目标旅程仍有效。新告知卡在同一聊天容器内，本轮复查新增内容和交互。
- started_at: `2026-10-19T11:44:33+08:00`
- completed_at: `2026-10-19T11:50:23+08:00`
- duration: `350s`
- validated_at: spec SHA-256 `4e306dd73df99e66cd12aa68cc789e7990ffd986547efbfe0f1bac598e64ee61`；design `6e720ee1bcf1ff68d158df4d3fe82fc77ebdd60afa05d68016566ac20ed9c62e`；最终prototype `64efc86ae5966e8a99f517067f2cb208261c0c9c64a61d013da3269e5843c177`；IM PA delta `45cbf492dff2e8e230b770581056116722d63afc658fe8021c8d6cc433f4687c`；Gateway PA delta `f855d17b3060f8be64b99e2e1faf97a4f05d42c6efbadeee54e9ee9c65ccfc38`；安全场景 `ff896af330f0d93d7ed4eb00092f3d296952bb8e7e633825afec414137af9ab7`。
- write scope: 仅追加本报告；此前字节保留，追加前报告 SHA-256 `1d87924587229b4bbaa5151f3bbf6a761c5f3f3da5f9c51f872f81be602f70c1`。原型中的一处按钮缺陷由作者在本轮修复，reviewer reload最终文件复验；没有产品修改、提交或部署。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

**本次双向告知增量没有未关闭的新增实质问题。** 主人通知送达前不向请求者宣称已通知；告知限原会话、事实措辞不披露主人反应；重复事件合并，误会标记不扩权，无新增审批。屏蔽按钮的真实交互缺陷已在本轮修复并独立复验。仅保留 DeepSeek 必验资源前置，Gate 2 仍未 Approved；不阻止交付当前设计与静态原型。

### Coverage 与证据

**需求与决定。** spec:265–286 保存用户原话，并把恶意指控收敛为有具体来源的“疑似”判断；首次模糊越界先解释边界，重复/伪造授权/要求隐瞒才形成事件。design:98–107 明确 actor/conversation/source-message refs、owner-only事件、两侧operation refs、去重、本人送达依赖、同会话回复权限以及误会/屏蔽行为。IM与Gateway的 ADDED requirement 与这三类场景一致，不借通知扩展可读资料或新授权。`security/acceptance-scenarios.md:19–20` 增加真实来源证据、送达pending/unknown、重复和误会负例；既有M1依然要求真实host/API/模型安全与有用性验收，静态演示不替代这些退出条件。

**模块职责与复用。** incident属于PA私密来源事件及投递关联，不属于任务审批或全公司信誉系统。模型判断可疑语义，host负责认证actor、真实消息计数、持久事件和可靠operation；IM负责会话ACL与消息存储。这是在现有消息能力和已规划 `pa_source_events/deliveries` 上补充有界事件，没有第二Agent loop或新的任务事实库。

从实际组装路径核对现有能力：`packages/personal-assistant/src/global-agent.ts:235–294` 在 `agent.message` 调用前保存publication，完成回执后写confirmed/message_id，失败写unknown；`inbox.ts:185–187` 保存operation状态；`apps/im-server/src/gateway.ts:504–553` 用真实Agent身份、会话write ACL和dispatch key处理发送，`messaging.ts:348–397` 按caller幂等key复用消息并持久化内容/事件。这些支持复用同一operation核对、以本人DM持久可见回执作为告知前提；本轮未声称新的incident编排已经存在。发送回执也不代表本人已读。固定对外事实文案仍受最终同会话权限/屏蔽约束，不能因“保护主人”绕过既有发送规则。

**独立原型操作。** 新建独立 Chrome 标签打开 `http://127.0.0.1:8766/prototype.html`，未使用作者/用户标签或修改内部状态。通过演示事件和正常输入完成：

1. 外部DM首次索取其他日程：只回复“其他个人安排不在分享范围”，没有恶意定性或新审批。打开“下次主人通知延迟”再模拟伪造授权请求，外部只得到拒绝及“已记录”；切本人尚无该信息卡。恢复通知后，本人才出现可核对来源/理由/阻断结果的卡片，外部随后出现“已通知陈同学”。记录页明确“不代表已读”。
2. 再次恢复无重复发送；同一伪造请求再次到达，主人卡计数从1变2，外部仅新增请求，没有反复警告。主人不操作时已交办演示照常从准备进入案例选择，告知没有变成新的任务/审批，也没有停住另一行程目标。
3. 点“这是误会，继续协作”，主人卡显示误会已标记、原分享范围不变；外部DM没有主人反应或误会结论。随后在外部发送“演示时长调整到二十分钟吧”，得到正常协调回应。没有产生新的私人日程分享授权。
4. 切群视角时，DM告知未出现于群。通过群输入相同伪造授权文案，群先显示拒绝/已记录，通知恢复后仅该群出现已通知文案；本人侧按DM与群分别显示来源和计数，DM误会标记没有混入群事件。
5. 屏蔽按钮初次点击无效果，浏览器console明确报 `ReferenceError: s is not defined`；定位 `prototype.html:171` 的inline handler引用IIFE私有变量。作者将参数在渲染时展开为true/false后，reviewer重新加载最终版：屏蔽立即显示已阻止新请求，重复演示请求不增加计数；解除后仅接收之后请求，计数仍为1，未回放屏蔽期内容。
6. 最终版补验相邻送达边界：群事件通知pending时先屏蔽林悦，再恢复主人通知。本人可见群事件，但群中仍只有拒绝/已记录，没有补发“已通知”来绕过屏蔽。最终复验没有新增脚本错误；console中保留的旧错误时间早于reload。

实际观察自适应桌面、768和390新增卡片及记录页。姓名/来源/依据/处理结果邻接；手机卡片可滚动至查看记录、误会和屏蔽操作，输入框保持可用，既有顶部/列表/手机返回关系未变。信息卡明确“你不用处理”，与业务决定卡有不同含义，未迫使用户逐条审批保护措施。R9真实组件视觉基线继续有效，不为这次局部卡片重开全IM视觉验收。

**证据边界。** 恶意识别、通知回执和阻断结果均为静态演示；不能据关键词分支或本轮浏览器路径证明真实攻击识别率、持久投递、所有资料未泄露或模型安全。开放任务中的语义披露风险、广权限工具/同OS限制及既有隔离必要性没有因双向告知而消除。通知是拒绝后的可见反馈，不能替代上下文隔离、权限与披露判断。本轮没有修改external/observation隔离架构；用户关于这些机制的进一步讨论不计作已落地设计变更。作者原55秒视频未覆盖本次新增告知旅程，未将它作为R10证据。

### 历史问题闭环

| 原 issue / 本轮发现 | 本轮证据 | 状态 |
| --- | --- | --- |
| R9-W1 / R8-W2 | design:188仍明确DeepSeek资源未落实；没有新的可用性证据或用户调整前置顺序的明确授权 | **still-open**，R10-W1 |
| R8-W1现有UI对照 | 本轮只在已有消息容器加信息卡，桌面/768/390局部复核无框架变化 | **closed，retained from R9** |
| 本轮屏蔽按钮引用私有状态报错 | 作者展开字面参数；reviewer reload后实际验证屏蔽、阻断新请求、解除及pending通知期间屏蔽不补发 | **closed** |

### Issues

#### R10-W1 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R9-W1。
- 位置：`design.md:188,196`，M1 W7。
- 证据与影响：没有新的授权隔离模型资源可用性证据，或用户对前置顺序调整的明确授权。双向告知的有用性、误判与真实来源/发送边界仍需真实模型和host/API验收；静态演示不能满足该前置。
- 关闭条件：安全落实授权隔离资源，或记录用户对前置顺序的明确调整；最终真实模型验收仍需执行，不要求本轮提前实现产品后端。

### Recommendations

无新增建议。当前增量与直接发现的问题已完成有界复核，停止扩展猜测性攻击或新的架构方案。

## Author Resolutions — R10 与统一 PA 设计修订（2026-10-19）

- R10 屏蔽按钮问题：accepted，已将 inline handler 的私有状态引用改为渲染时字面参数；R10 独立实际复验已关闭，本轮保留该原型文件。
- R10-W1：accepted，DeepSeek 隔离资源前置仍未落实，本轮没有新增密钥/资源证据，不宣称 Gate 2 已过。
- 用户最新原话“先按这个来考虑怎么设计吧，改一版设计”授权按统一 PA、独立入口/出站检查与系统执行边界修订。spec 保存原话与范围；design 新架构图、第3/4/7节、接口/能力边界/里程碑重写，两个 PA delta、capabilities delta、安全验收及研究依据同步。
- 本轮不改产品代码或原型。R9 现有 UI 与 R10 告知交互证据可作为保留项；旧 external/observation 无私料 session 不再是当前架构目标，相关安全证据不能直接沿用。研究历史不回写，当前解释由 design 与新研究依据提供。
- 请 reviewer 独立决定复审范围，重点核对可信授权与语义判定、实际出口/工具装配、子执行和自动记忆、拒绝/不可用的恢复、正常任务效用与既有契约衔接。没有指定期望结论；原模型资源警告单独保留。


## Round 11

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`；未参与本轮设计编写。
- reviewer target: 用户明确授权的统一 PA 架构修订；spec/design、全部10份 delta、安全与有用性场景、新研究依据及实施就绪记录。工作树 `/Users/czj/.codex/worktrees/feat-616-personal-agent/nano-multiagent`，分支 `docs/feat-616-personal-agent-handoff`，HEAD `f4162189f9ec50fe437913a68bd540d5d6ab3c0e`。
- review_mode: **full**。
- mode_reason: 从 external/observation 无私料业务 session 改为统一可读私料主上下文，改变核心信任边界、运行时装配、共享接口与 M1；旧隔离结论不能直接沿用。重新检查整体需求、职责、可信授权、所有出口、记忆、恢复及正常任务效用。未变的 UI 和交互保留独立证据。
- retained_from: **Round 9 / Round 10**，仅现有 Web 框架、连续目标/普通聊天、双向告知交互以及 DeepSeek 资源状态；旧 external 模型不含私人 canary 的成功标准不保留。
- started_at: `2026-10-19T12:23:07+08:00`
- completed_at: `2026-10-19T12:28:08+08:00`
- duration: `302s`
- validated_at: spec SHA-256 `76b2c1ee6a90dd3f8b5a290f15ddf210903b790c04af0e3393c38af798d23d92`；design `841ca3ca538e56b488857cfa5500cc19a4291e314ed9a0d365b2d3f15e4d83b5`；prototype `64efc86ae5966e8a99f517067f2cb208261c0c9c64a61d013da3269e5843c177`；Gateway PA delta `9ab0d8bf06ad3a270ad52046c883e90b6fc1cb53e0ee3e30560364ec1c63bf4c`；capabilities delta `1c778524207c2628ec38fe91bd138d16332799883d6584135747650933493f68`；安全场景 `10c2ab4d8658dba75e0ce24b4968af84461277bb3be6c134ab7581802864bcb5`。
- write scope: 只追加本报告；此前123780字节完整保留，追加前 SHA-256 `96c9c9305aba65f925e43940afe41b4bc20be168c2945b05728cf51c518bb00c`。无产品代码修改、安装、服务启动、生产操作或提交。

### Verdict

**Issues Found — 1 CRITICAL / 1 WARNING。**

统一 PA、来源约束、独立语义审核与强制出口的方向符合最新用户授权，不要求退回每个外部会话无记忆的旧架构。新增实质问题是：现有普通 Agent 与 PA 共享 DSH 宿主，普通扩展可在共享 root 初始化，而设计尚未选择能兑现“普通 Agent 保持原能力、不可控插件不进入 PA 宿主”的装配方案。这影响核心安全前提，须先收口。另保留 DeepSeek 真实验收资源前置。Gate 2 未 Approved。

### Coverage 与证据

**需求与整体决定。** spec:298起保存本轮用户原话和授权，design:22–45明确统一理解、独立无工具审核、代码关口及残余误判；没有把论文效果写成产品保证。第1–6节继续使用唯一PA、原任务事实、目标级scope、真实schedule和本人业务决定，内部子任务结果自动回流；不新增逐工具审批、第二任务库或另一Agent loop。第7节明确从认证owner当前输入签发许可，引用/历史/system/模型总结均不能扩权，新增scope还需保留原文供出口复核。自动安全改写最多两次、跨key拒绝记录和仅必要新增决定，避免“每次不确定都问主人”。审查不可用仅暂停该动作，不伪装成用户应批准的隐私判断。

**真实装配及公开接口。** 从 `apps/node/src/main.ts:40,58–63` 的实际启动入口追至 `packages/dsh-integration/src/index.ts:94–129` 的单一 bindings/configuration/root、`agent-config.ts:76–91` 的插件装配和 `extensions.ts:7–18` 的动态import。由此得出 R11-C1，而非仅因引用行存在认定安全。当前 `policy/approval.ts` 的 safe/skip/run_code提前返回不能替代新披露关口。检查本机现有依赖中 `@deepseek-ai/dsh-tools@0.2.1-alpha.1` 的公开类型：restrict限制继承工具，guard在pre-execute后单调拒绝；有工具边界可复用，但guard不拦插件初始化/任意JS副作用。本工作树未安装依赖；这里只读主checkout同版本的已安装包，未以其证明本工作树产品已运行。

`@deepseek-ai/dsh-web` 根export提供search/fetch provider注册，现有 `web.ts` 已用公开 `applyWebFetchTool` 和provider接口，因此可在dsh-integration接入受控网络adapter而不private import。现有search `get()`与原生fetch的自动重定向并没有新隐私检查；design:147要求实际query/URL/path/body及redirect重新检查，必须由实施替换/包裹真实provider路径并验收，不能仅凭工具名或初始URL放行。本文没有把当前网络能力误称已受控，也不据设计阶段缺少实现新增问题。

**授权、来源及审查数据闭合。** design:122–138、209–221把可信binding/actor、原owner消息/提案、真实受众、实际读取与已注入记忆来源、历史披露放入host组装证据。模型自报引用不能省略敏感证据，缺失/超窗为unavailable；审核结果绑定冻结正文、附件、destination、scope/source/audience/policy版本和期限。最终执行还校版本，不让修改正文、共享受众或引用内容复用旧pass。owner DM只凭真实收件路由快速通过披露边界，原工具审批仍适用。职责分配保持 IM 持有身份/任务/ACL，PA编排operation/资料证据，Node/dsh-integration运行公开DSH和adapter；Channels/IM不import DSH。

**实际出口与共享存储。** 独立阅读 `personal-assistant/src/external.ts:100–179`，确认显式agent.message、message_completed/final_content自动publish以及streaming relay均为真实路径。design:138,144–148覆盖未审正文不外部流式、显式/自动回复、Channels最终投递、任务/附件/共享文档、网络工具和外部Agent委派；Channel不可在审核后追加私人信息。共享写入按实际受众处理，不能称内部任务所以免审；实际provider回执与IM镜像落库区分。内部child/Work/logs限定owner，背景最小化，继承关口，外部专业Agent委派不冒充内部执行。这些边界与既有 global/inbox/messaging 幂等能力相容；新业务operation不是模型可签的公开pass工具。

**记忆、撤源与恢复。** 实读knowledge runtime/files，现有自动memory来源主要是session/timestamp，fork/后台更新会复用现有机制，不能假定已有完整派生来源。design:124–126明确新自动派生项继承实际读取来源集合，owner_decision/external_claim/derived不互相升级，generic edit/skill不能改权限及自动知识根；这一必要增量落在现有knowledge存储，不另建全盘taint引擎。来源失权使旧执行退休，允许内容重建；普通资料工具不读退休导出/原生日志，owner-only历史查看与自动摄取区分。design:157,221将unknown/sending计可能披露，同owner短提交锁校disclosure revision，避免并行审核用同一旧历史全部直接发送；冷恢复先校owner/node/能力策略，再核旧操作、失效pass、恢复安排。无跨平台真实身份绑定则不猜合并，未知串通风险明确保留。

**delta及实施边界。** 对全部10份delta逐项检查canonical目标；26项MODIFIED requirement名称都能匹配 `docs/specs/`，旧Scenario标题无遗漏。能力delta为PA附加明确例外，普通Agent原配置/Auto语义保留；PA与IM新增需求包括统一理解、派生事实不授权、不可用不先发、连续/并行披露及双向告知。安全场景已废弃旧“external主请求绝无canary”的标准，改检查实际recipient/sink。M1要求真实DSH装配、主/子/后台、全部sink、skip/HMR旁路、冻结/并发/unknown，并同时完整完成演示和场地两条正常旅程、记录误拒绝/必要分享/打断次数与质量。不是只跑孤立policy或只报阻断率；本轮未提前要求产品后端实现。R11-C1收口后需相应补装配/生命周期验收。

**研究使用边界。** 独立查看 [FlowSeal原文](https://arxiv.org/html/2609.14003v1)、[Claude Code Auto Mode官方说明](https://www.anthropic.com/engineering/claude-code-auto-mode)及[Agents SDK guardrails文档](https://openai.github.io/openai-agents-python/guardrails/)。前者明确工具外执行与独立语义判断的分工，后两者分别支持剔除主模型自我解释、工具管道覆盖不同的注意点。研究表的这些核心借鉴与本设计一致；不把FlowSeal形式化条件或论文数字转移为Nano保证，其余论文不是本轮实现可行性的必要证据。本仓可行性仍以公开exports、真实装配与上述限制为准。

**UI与证据边界。** prototype哈希与R10最终版完全相同；本次未新增界面、改导航或改告知动作。保留本人在R9对当前真实React组件基线和三宽度连续目标/普通聊天的独立观察，以及R10延迟通知、重复/误会、屏蔽/解除的独立操作。无需为未改原型重跑相同浏览器流程。“审核暂不可用/能力不足”沿已有目标阻塞摘要，不加审批页。上述UI证据只证明界面方案；不证明真实来源、模型抗攻击效果、全网络覆盖或持久投递。

### 历史问题闭环

| 原问题/证据 | 本轮判断 | 状态 |
| --- | --- | --- |
| R10-W1 DeepSeek资源 | design:264继续明确未落实；无新资源证据或用户调整该前置顺序的授权 | **still-open，R11-W1** |
| R8-W1现有UI对照、R10屏蔽按钮 | 本轮原型哈希未变，独立R9/R10真实渲染和交互证据保留 | **closed，retained** |
| 旧external/observation隔离与无canary验收 | 用户明确改统一PA；本轮按新的host来源/出口与实际接收端标准重审 | **superseded，不沿用为安全通过证据** |
| 共享宿主插件装配 | 当前startup/root扩展证据显示设计尚未闭合；作者已认可缺口并表示报告后统一修订，受审文件未变 | **open，R11-C1** |

### Issues

#### R11-C1 — 普通 Agent 与 PA 共享运行时，初始化前排除不可控插件的边界尚未落定

- 分类：核心安全装配与职责设计；CRITICAL。
- 位置：`design.md:149–153,217,275`；现状 `apps/node/src/main.ts:40,58–63`，`packages/dsh-integration/src/agent-config.ts:76–91`，`extensions.ts:7–18`。
- 证据：Node目前把全部config.agents交给同一RuntimeSupervisor；ConfigurationScopes将任一Agent的global extensions加载到共享 `this.host`，随后直接import并执行插件。插件初始化和后台监听可使用Node fs/fetch或贡献root行为，不必经过PA工具guard。新设计同时要求普通Agent保持任意既有配置，且不可控插件在执行/初始化前不得进入PA宿主，却没有选定怎样改变上述共享装配及热更新/恢复路由。
- 未修后果：实施若仅按PA agent配置过滤插件或加restrict/guard，普通Agent已经加载的root贡献/后台代码仍与PA运行时共存；最终sink的“所有受控执行”前提不成立。反向对整个共享host禁插件又会改变明确保留的普通Agent能力。这是已有装配的确定冲突，不是假想插件漏洞，也不能由审核提示词补救。
- 关闭条件：明确一个可实施的可信宿主/配置边界及生命周期路由，覆盖启动、普通Agent新建/插件热更新、PA主/子/审核/knowledge与冷恢复，保证未知插件代码在进入PA宿主前被排除且普通Agent原能力保留。沿apps/node → dsh-integration/client与stdio即可，不要求新增Agent loop或OS沙箱；须继续明确同OS受信代码及磁盘隔离的实际限制，并把此边界加入M1验收。

#### R11-W1 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R10-W1。
- 位置：`design.md:264,275`，M1 W7。
- 证据与影响：没有新授权隔离模型资源可用性证据，或用户对前置顺序调整的明确授权。统一主上下文会接触私人资料，新的独立审核有用性/误判及实际出口必须经真实模型和host/API验收；静态原型与一手论文不能替代。
- 关闭条件：安全落实授权隔离资源，或记录用户对前置顺序的明确调整；最终真实模型验收仍须执行。不要求本轮提前实现产品后端。

### Recommendations

无新增可选建议。当前核心需求与边界已完成有界审查；先收口确定的共享宿主装配问题，不扩展为任意攻击穷举或重新选择未经用户要求的架构。

## Author Resolutions — R11（2026-10-19）

- **R11-C1 — accepted。** 核实 `apps/node/src/main.ts` 单 supervisor 和 `agent-config.attach` 共享 host global extension 路径，问题成立。design 第7节新增“宿主分区”：普通 Agent 保留原宿主，每个可信 personal binding 经现有 RuntimeSupervisor/client 获独立 home/profile/进程；主/子/审核/knowledge 同 PA 分区，不按外部会话拆 session。明确 RuntimePort 路由、进程来源验证、初始化前过滤、配置预览/HMR、新建、冷恢复、局部故障和整体更新；注明同OS受信代码仍不是恶意插件沙箱。接口职责、M1、Gateway PA delta、安全场景与研究依据同步。修订仅设计文件，没有提前运行或实现新分区。
- **R11-W1 — accepted，retained。** 没有新增 DeepSeek 隔离资源，不申请或暗示批准跳过前置；当前可交付设计修订，Gate 2 仍需按实际资源与最后审查结论判断。
- 本次其余冻结产物及 prototype 不变，请独立核对 R11-C1 的修订与影响，自定范围，不重开已保留的相同 UI 旅程。


## Round 12

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`。
- reviewer target: R11-C1 Author Resolution；design宿主分区、grounding/职责/M1，Gateway PA增量场景、安全验收和研究依据。工作树、分支与HEAD同R11。
- review_mode: **delta**。
- mode_reason: 围绕R11-C1的有界修复，但新增多supervisor和RuntimePort路由会影响配置、事件、集合查询、后台结果及轨迹，需检查这些实际消费者，不能仅核旧问题措辞。统一PA业务结构、授权/出口、UI未变。
- retained_from: **Round 11** 的非宿主架构及安全/效用判断；**Round 9 / Round 10** 的原型与UI独立证据。R11资源警告保留。
- started_at: `2026-10-19T12:30:30+08:00`
- completed_at: `2026-10-19T12:31:59+08:00`
- duration: `90s`
- validated_at: design.md `eea1fd480f3ef9982adbec6a89d6fcfb0def49181bee1b1f7942471203a1971c`；specs/gateway/personal-agent.md `cac6b9128f32ac58b0ce07cb22b8312fea84f0e2c486a900e8de5e94849228a6`；security/acceptance-scenarios.md `7aae9f710bb152615925ee272b72a03a1fc3d82d22a43f140fc6b91ae002c12d`；research/unified-pa-security-design.md `1ccab76532f046a5626d9844b4ad9d16a31604d26e7612434b0b65095cc6d1a7`；prototype.html `64efc86ae5966e8a99f517067f2cb208261c0c9c64a61d013da3269e5843c177`。
- write scope: 仅追加报告，保留此前 137320 字节，追加前SHA-256 `3368fbedf8286d162c465a28cd2f0dd9b49d16954f93eb6f900fab9f7a9db255`；无产品修改、提交、部署或提前实现。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

**R11-C1已关闭。** 专属DSH宿主与初始化前配置控制已给出可实施方案，普通Agent保持原宿主，且未夸大为OS沙箱。新增路由设计仍缺现有无agent/session请求的聚合与句柄归属规则（R12-W1）；DeepSeek资源前置继续保留（R12-W2）。Gate 2仍未Approved。

### Coverage 与证据

**初始化边界与职责。** design:156–165选定 `ordinary` 与 `personal:<bindingId>` supervisor，服务器认证binding/node epoch决定分区，不接受模型参数改role，不在PA初始化期间临时落入ordinary。PA主/子/审核/knowledge留在同一分区，独立home/cwd/profile仅装受审配置，普通global/workspace插件不复制；初始化、preview/catalog、HMR、新建和冷恢复均纳入，足以关闭旧“同进程root已加载”的确定冲突。新的apps/node职责和M1范围与该决定一致。

实读 `packages/dsh-integration/src/client.ts:13–28,43–54,79–151`：prepareProfile以传入home建profile，RuntimeClient每实例spawn官方CLI并指定DSH_HOME/cwd，Supervisor有独立ready/recovery/process状态；`package.json`声明 `./client` export。复用这些能力比修改DSH、发明第二loop或只加工具白名单更直接。prepareProfile当前默认仍加载base/integration，过滤与受控profile是实施增量，不能把现有函数调用本身当作安全证明。设计已要求import前审来源，M1以真实初始化PID和后台hook验收，不仅看工具列表。

**生命周期与身份。** design:160–163明确NodeStore/session lineage、实际进程来源与ProductBridge核对、冲突/旧epoch拒绝而不fallback；配置改变及provider数据不广播全部Agent配置，停旧admission后才换epoch。实读 `apps/node/src/main.ts:235–298` 的配置应用、handler、heartbeat可用性、全局update及stop，确认这些是必须改的实际调用点。新设计对某PA故障局部unavailable、整体更新fan-out/drain与部分失败释放给出明确行为；不是“节点在线则一切ready”。现有NodeStore持久session归属可复用，新增子执行/审核lineage需覆盖冷恢复。这里无需新跨包SDK，Node内部实现原RuntimePort即可；但具体请求类别覆盖还有下述R12-W1。

**同OS与正常行为。** design:165明确普通进程恶意代码仍可能直接读取同用户磁盘，部署者、本机宽权限代码与内建adapter处于可信环境；专属home不是OS权限隔离。外部联系不开放普通插件安装/代码执行权限。这与本unit现有受信本机边界一致，不要求引入新沙箱。普通插件同项配置继续可用，PA不合规能力明确受限，正常任务效用的R11标准保留。

**delta、验收和UI。** Gateway PA新增同节点普通配置变化与PA运行不可用两项Scenario，表达消费者可见行为而非要求用户管理进程。安全场景:18–19增加普通global/workspace插件初始化PID、后台hook、主/子/审核/knowledge、preview/HMR/恢复与进程来源测试；M1:288同步实际DSH验证及正常Agent能力保持。研究补充只记录源码和设计选择，不宣称运行通过。prototype SHA-256与R10一致，导航、目标和双向告知无变化，保留R9/R10独立操作证据；未重跑无变化UI。没有新的模型资源证据。

### 历史问题闭环

| 原问题 | Author Resolution与独立证据 | 状态 |
| --- | --- | --- |
| R11-C1共享宿主插件初始化 | 独立supervisor/home/profile；初始化前过滤、配置/HMR/恢复范围、真实进程来源、普通Agent保持，公开client确可复用 | **closed** |
| R11-W1 DeepSeek资源 | design:277仍明确未落实，无新证据或用户调整前置授权 | **still-open，R12-W2** |
| R9/R10 UI与R11其余架构 | 原型未变，路由变化不改变用户流程；已有独立证据继续有效 | **retained** |

### Issues

#### R12-W1 — 新RuntimePort分区路由遗漏无agent/session的集合查询与opaque句柄请求

- 分类：共享内部接口与恢复闭合；WARNING。
- 位置：`design.md:160,163`；实际消费者 `packages/personal-assistant/src/knowledge.ts:41,64`、`workflows.ts:56–59,138`、`apps/node/src/trajectory.ts:35–60`；运行时handler `packages/dsh-integration/src/index.ts:347–348,384–385`。
- 证据：设计声明按agentId或session binding定位分区，无法唯一归属拒绝，另明确update/provider fan-out。实际 `knowledge.facts({})`、`workflow.pending({})` 是全宿主集合查询；`knowledge.acknowledge({id})`、`workflow.acknowledge({runId})`只带结果ID；`trajectory.prepare`之后的call/next/abort/close只带observerId。它们没有可直接套用的agent/session参数。RuntimePort本身仅request/onNotification，不会自动补这些路由事实。
- 未修后果：直接按当前规则实现会拒绝集合查询与后续确认，阻断后台知识及内部任务结果回流；若为使其工作广播ack/轨迹或回落ordinary，则可能串区。冷恢复中仅保留临时句柄映射也不足以解释未确认结果归属。
- 关闭条件：为现有请求分出有界的集合查询与句柄后续操作，选择由分区消费者分别调用，或在Node路由器按可信分区聚合；结果/ack须保留来源分区及epoch。trajectory等由prepare创建的句柄按原分区路由，失效/未知不得fallback，重启按有效持久事实重建或明确使临时句柄失效；局部宿主不可用不让其他分区结果一起丢失。补对应M1/场景即可，不要求逐RPC实现表、新通用框架或提前编码。

#### R12-W2 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R11-W1。
- 位置：`design.md:277,288`，M1 W7。
- 证据与影响：没有新授权隔离模型资源或用户调整前置顺序的证据。宿主设计闭合不替代统一PA的真实模型、全sink及正常任务效用验收。
- 关闭条件：安全落实资源，或记录用户对前置顺序的明确调整；最终真实验收仍须执行。不要求本轮提前实现产品后端。

### Recommendations

无新增建议。问题限于实际存在的集合/句柄接口，不扩展为假想插件攻击或重新设计业务会话拓扑。

## Author Resolutions — Round 12

- **R12-W1：接受并修复。** 选择按分区实例化既有 KnowledgeUpdates/WorkflowResults，使用 Node 绑定的 scoped RuntimePort，不引入集合聚合框架。查询、确认与通知固定来源分区；真实记录身份复核，产品投递/去重使用稳定分区与原生 ID 复合键，保留原生 RPC 参数。区分持久结果恢复与 supervisor generation，局部故障独立恢复。轨迹由 prepare 建立 observerId 归属，后续句柄操作路由到原分区，重启/失权失效并重新 prepare。design 第7节、M1和安全场景同步补充同名结果、正确确认、局部故障和临时句柄验收。
- **R12-W2：保留。** 真实 DeepSeek 隔离验收资源尚未落实，本轮不宣称 Gate 2 Approved 或安全运行通过。
- 本轮不改产品代码或原型，不扩大正常用户流程；请求仅对上述真实接口缺口作闭合复核，其余沿 R12 有效证据。


## Round 13

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`。
- reviewer target: R12-W1 Author Resolution；design:161–163、M1与安全场景的集合/ACK/句柄闭合修订；工作树、分支、HEAD同R12。
- review_mode: **closure**。
- mode_reason: 修订只为已证实的无agent/session接口补明确归属，未更改统一PA、宿主分区方案或用户流程；按R12-W1关闭条件逐项核对，不扩大到其他边界。
- retained_from: **Round 11 / Round 12** 的架构、全出口与安全/效用判断；**Round 9 / Round 10** 的UI独立证据；DeepSeek资源警告保留。
- started_at: `2026-10-19T12:34:08+08:00`
- completed_at: `2026-10-19T12:34:52+08:00`
- duration: `44s`
- validated_at: design.md `6cd18651cc6cef6441838d20d7d5aa80065b689dc7303f422639a157a18ccbaa`；security/acceptance-scenarios.md `8a9257c285eca1d8337690af5bc33c99f60126e20f024204213a5203a1e4e656`；prototype.html `64efc86ae5966e8a99f517067f2cb208261c0c9c64a61d013da3269e5843c177`。
- write scope: 仅追加报告，保留此前 146127 字节，追加前SHA-256 `6b86cec2b6bc1d93e28ed94e0b1c653cb94cba1d5b9dc906292ab2362f744ad0`；无产品修改、提交或部署。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

**R12-W1已关闭，本轮无新增实质问题。** 集合查询和原生ACK采用分区消费者，临时轨迹句柄有明确来源/generation；恢复与局部失败均已收口。仅保留DeepSeek必验资源前置，Gate 2仍未Approved。此结论只说明设计缺口闭合，不表示产品实现或安全运行已通过。

### 历史问题闭环与证据

#### R12-W1：closed

**集合与确认。** design:161选择按分区实例化既有 `KnowledgeUpdates`、`WorkflowResults`，Node注入与真实supervisor绑定的scoped RuntimePort。`knowledge.facts({})`、`workflow.pending({})`及其ACK都留在同一分区，不再按缺失agent/session猜路由或广播。源码复核 `knowledge.ts:11–27,41,64`、`workflows.ts:18–36,56–59,138`：两消费者本来通过注入的RuntimePort查询/订阅/确认，分区注入能直接复用现有结构；不必引入全宿主集合聚合框架。`index.ts:347–348,384–385`确认原生查询/ACK语义，`workflow.completed`确是通知而非查询，新文档正确区分。

**可信归属与冷恢复。** 结果agent/root/session/parentSession必须匹配有效分区binding；产品投递与去重采用稳定分区+记录类别+原生ID，同名fact/review/run不跨区合并，RPC继续用各自原生ID。design:162区分持久结果和临时generation：旧回调丢弃，重启从同binding持久数据重查未确认结果，以稳定键核对既有接收事实后再ACK。某分区失败只延后其消费，其他分区正常；不因局部批次完成确认未处理项，更换binding/撤epoch不恢复旧资格。这覆盖R12提出的结果回流、正确确认、重启与局部不可用后果。

**临时轨迹。** design:163在有效owner ACL/ticket的prepare时建立observer→分区/generation/session，后续call/open/next/abort/close及stream按该登记，未知/冲突/失权/旧generation拒绝，无广播/ordinary fallback。源码 `apps/node/src/trajectory.ts:33–60`确认这些后续请求实际只带observer/stream信息，新映射填补真实缺口。close清登记，宿主重启关闭该分区观察连接，查看器重新prepare；不尝试跨宿主扫描或持久恢复临时句柄。

**验收对应。** `security/acceptance-scenarios.md:20–21`新增ordinary与两个PA同名原生ID、ACK仅回来源、局部故障、冷恢复不重复投递、旧generation及observer失效场景；M1:291同步分区知识/内部成果回流与确认、同名去重和轨迹句柄。检查覆盖点与上述具体设计一致，不能用单纯工具列表测试替代。受审设计与场景diff检查通过；本轮没有运行产品测试，也未复跑未变化的原型。

#### R12-W2：still-open → R13-W1

`design.md:283,291`继续说明DeepSeek隔离资源尚未落实；Author Resolution也未提供新可用性证据或用户调整前置顺序的授权。沿用原资源问题，不把接口闭合计作真实模型验收。

### Issues

#### R13-W1 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R12-W2。
- 位置：`design.md:283,291`，M1 W7。
- 影响：统一PA的真实模型有用性、语义审核、实际接收端边界与受控能力仍需隔离资源验证；设计及原型证据不能替代。
- 关闭条件：安全落实授权隔离资源，或记录用户对前置顺序的明确调整；最终真实模型验收仍须执行。不要求本轮提前实施后端。

### Recommendations

无。本轮关闭范围已完成，不再扩展相同设计审查或猜测性边界。

## Author Resolutions — Round 13

- 接受独立 closure 结论：R12-W1 已关闭，本轮无新增实质设计问题，停止设计修复循环。
- 保留唯一 DeepSeek 隔离验收资源前置；当前交付为设计与契约修订，不标 Gate 2 Approved，不声称后端或安全效果已验证。后续实施前落实该资源并执行设计中的真实模型与正常任务效用验收。

## Author revision — 新消息协助与完整历史查询

- 根据2026-10-19用户追加原话同步spec/design及Gateway、IM delta、安全场景：30天仅首次后台整理，历史按本人当前权限随时按需检索；区分暂停、排除、清理；原消息出处、无已读副作用、历史非授权。
- 新消息允许草稿/授权内代发/不回复；原人际会话保留，代发为可信PA actor并向双方固定标识，新增受信代理写入契约，不伪造本人身份或增加第三成员。
- 产品代码、prototype未改；原型历史证据不用于认证新增的代发标记与历史定位，实施须按本次场景验证。DeepSeek资源前置继续保留。

- 用户进一步明确拒绝固定30天窗口：当前spec/design/delta/security已删除首次整理与查询窗口，prototype同步三处文案，均为按需检索、不设人为时间上限。前述作者“30天预热”解读被此次原话替代；旧报告仅为历史记录。


## Round 14

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`。
- reviewer target: 用户新增“新消息可草稿/PA标记代发/不发”与“随时查过去本人参与聊天”的需求，以及最新“不要无端限制30天”纠正；spec/design §8、UI段、Gateway/IM PA delta、安全场景和原型三处文字修订。工作树、分支、HEAD同R13。
- review_mode: **delta**。
- mode_reason: 新增可信代理写入、按需历史查询及用户可见身份/出处路径，波及消息DTO/同步/历史和读取权限；统一PA安全架构及宿主边界未变，不重开全量审查。
- retained_from: **Round 11–13** 的统一PA、宿主分区、来源/披露与恢复判断；**Round 9/10** 的既有UI与连续目标交互。新增代发标记和历史结果路径没有继承旧原型通过结论。
- started_at: `2026-10-19T13:13:24+08:00`
- completed_at: `2026-10-19T13:15:32+08:00`
- duration: `129s`（含等待作者落实用户即时取消时间窗的修订）
- validated_at: spec.md `ca6d2982e9f03efa36f806a68e53a91f5b9585ef672249b2b5d19d3c2f7e183a`；design.md `757b875005da91ab2d050447e2ce893e4a17af34ce1fca3011a4ac6a61dc0fa3`；prototype.html `77002be3a4a6009e5c258169cc31f9a6603a3589f3dfbe4fc7635bfb0d9b9b21`；specs/gateway/personal-agent.md `68cfff96bcf0d89c174c4e5c13c1e0cae9f002b14671d52fbdf0a03ab05df0fe`；specs/im/personal-agent.md `ebffe95809c00119447f58d37b2b20d2a26924178736d00eedde1b328803b543`；security/acceptance-scenarios.md `8270f5570c51bf3efb7d4aff76392a10f29da732007675f938df5ec6866116d4`。
- write scope: 仅追加报告，保留此前152361字节，追加前SHA-256 `40a19957d4dba4f0ca17de3a50ab2ccada41c46896b8c4a166c30971bf8f06c7`；无产品修改、服务或生产操作。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

新需求的数据与权限路径已给出可实施设计，固定历史时间窗口已完整取消。新增问题是两段用户可见路径尚缺与改动相称的原型和实际走查（R14-W1）；DeepSeek资源前置继续保留（R14-W2）。Gate 2仍未Approved，不把设计结论作为实现或安全运行证明。

### Coverage 与证据

**最新需求。** spec:332–362保留用户原话与取消30天的即时纠正；最终design:193,197与Gateway delta/security不再把首次整理或查询限制为固定时间窗，分页只控制单次量。独立检索design/prototype/Gateway delta/security未发现残留30天门槛。新消息三种处理是PA按内容/已有许可选择，不是每条消息新增用户三选一；不回复不创建待办，草稿本人发仍为本人消息，已有scope内代发不重复问批准。作者转述的用户最新“优雅极简、不要复杂配置/交互”原则与此相容，本轮冻结文件未新增该段，不把后续修订计作已审证据。

**原DM代发与真实身份。** 实读 `apps/im-server/src/gateway.ts:504–553`，现agent.message先requireAgent再按该Agent检查目标write ACL，不能自然发送到两真人DM；`messaging.ts:458–475`的普通浏览器身份校验也不允许冒充Agent。design:195明确新增受信代理写入分支，以personal binding、owner当前write ACL、scope、受众及已审operation授权；真实PA actor和authorized_by持久化并经DTO/同步/历史传递，不偷用owner token、不改变DM参与者。这个新增落点必要且职责明确，不是只改显示名。普通浏览器不可设置代理身份，原工具审批/外发关口仍适用；owner先回复后重核待发动作，避免过期代答。现 `messaging.ts:271–305`集中构造消息DTO、insertMessage持久化/事件机制可复用，实施需补可信代理元数据的同一投影；本轮未声称这些字段已有实现。

**历史范围、权限与副作用。** `messaging.ts:834–867`现有消息游标分页先access校验，读路径不执行 `:820–827` 的已读写入；设计保留此分离。新增 `pa.history.search/read` 在IM权威存储按可信owner binding执行跨会话条件检索及命中上下文，不复制聊天数据库或强制新向量服务，返回真实作者/时间/消息出处与覆盖状态。当前代码只有会话分页，没有现成跨会话关键词契约，文档对此断言准确。

`conversation-access.ts:16–31`实际按当前成员/公开群及space资格决定read，成员且未解散才能write。design:201相应区分参与过与当前可读：退出私有群可能不可读，公开群全站可见不自动纳入个人历史集合，必要时持久参与记录；未覆盖/删除/失权不装作未找到。每次query/page/原文/附件都校当前ACL与source policy，索引/缓存不绕撤权；暂停观察不禁按需查询，排除禁止读取，清理缓存不删除原消息或永久禁止获准重新读取。查询不推观察cursor/已读，不以旧owner原话签新scope，对外传播仍进独立披露审核。与既有可信来源/撤源约束一致。

**消费者及UI现状。** `src/IM/frontend/src/features/chat/components/work-thread-link.tsx`已有带message_id的真实聊天链接，`chat-workspace-page.tsx:321,621–661`解析定位参数并加载/定位旧消息，能复用为原文出处入口；不是新发明独立历史门户。现 `message-pane.tsx:1535–1541,1700–1721`以真实sender区分本人/Agent气泡并显示作者，新增代理固定标记必须在该关系中设计，不能从普通Agent名字或正文推断owner授权。R9对这些聊天基线的独立实际观察仍有效，但未观察新增标记/查询答案界面；本轮没有把代码阅读充当新增视觉验收。

**delta与M1。** Gateway新增按需任意时期查询/当前权限Scenario，IM新增三种处理/真实代理身份/来源定位Scenario；均位于PA新增消费者契约，普通消息冒充身份规则不放宽。M1:301与安全场景:22–24覆盖人物/时间/关键词、分页上下文、原文、撤权/排除/暂停、可信actor与双方实时/历史展示、DM成员不变和本人已回复。需要验证的实现边界明确，真实产品与DeepSeek验收未提前执行。受审文档diff检查通过。

### 历史问题闭环

| 原问题/变化 | 本轮证据 | 状态 |
| --- | --- | --- |
| R12-W1集合/句柄分区 | 本次未修改宿主/消费者设计，R13闭合证据有效 | **closed，retained** |
| R13-W1 DeepSeek资源 | design:293,301仍说明未落实，无新资源证据或调整前置授权 | **still-open，R14-W2** |
| 固定30天窗口 | 用户明确纠正后，最终spec/design/delta/security及三处原型文案均取消首次/查询固定时间窗 | **本轮已修正，无新增issue** |
| 新代发标记与历史出处体验 | 仅文字契约，原型未覆盖这两段新路径；作者明确不将旧证据当新证据 | **open，R14-W1** |

### Issues

#### R14-W1 — 新增双方代发标记与历史答案定位缺少原型和实际体验证据

- 分类：前端设计/必需体验证据；WARNING。
- 位置：`design.md:195,197,256,278,301`，`specs/im/personal-agent.md:104–113`，`prototype.html`。
- 证据：本次原型只删三处固定窗口文字，未加入原DM双方的PA代发标记，亦未加入PA历史答案/作者时间/原文定位/返回路径。旧R9/R10原型没有覆盖这两个新增用户结果，文字“双方固定标记”“提供出处”尚不足以判断实际辨识与阅读/操作关系。`change-design-author/references/prototype-and-runbook.md:17,46–48`要求与UI改动相称的原型并实际渲染走查，明确“不能宣称原型就绪或把必要视觉检查推迟到实施验收”。
- 用户代价/未修后果：实施者需要自行决定本人消息、PA代答和外部消息的视觉归属，以及多条历史依据如何阅读、点击后看到哪段原文、手机如何返回；可能虽字段齐全却让对方误认真人发送，或让本人无法核对答案出处。本轮没有观察到这些具体失误，因此问题记为设计/证据缺口，而非虚构现成视觉bug。
- 关闭条件：在既有聊天壳内补最小两段连续原型：本人/对方视角辨认同一代发消息（含与本人发送草稿的区别），以及本人问旧事→答案带作者/时间/来源→打开原文上下文→返回。保留未找到/无权或来源不可用的必要差异；实际桌面与窄屏观察并留简短证据。无需改导航、增历史时间配置、每消息三选一或安全参数面板；不要求提前实现后端。

#### R14-W2 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R13-W1。
- 位置：`design.md:293,301`，M1 W7。
- 影响：代发scope/审核、历史来源与真实任务效用仍需隔离模型、host/API和实际接收端验收；当前设计/静态原型不能替代。
- 关闭条件：安全落实授权资源，或记录用户对前置顺序的明确调整；最终真实验收仍须执行。

### Recommendations

无新增建议。新增发现限于真实前端流程证据，不扩展为新的配置体系或假想权限边界。

## Author Resolutions — Round 14

- **R14-W1 accepted**：补原输入框查询历史→原群高亮原文→返回，以及明确代发→本人原私聊→对方原私聊两段原型。没有新设置页，双方固定PA标记，1440/390实际浏览器观察见research/history-delegation-ux.md及截图。同步design体验契约；修正错误“今天”标签与连续对话保留后复查。
- **R14-W2 retained**：DeepSeek资源前置未变，仍不宣称Gate2 Approved。
- 用户最新“优雅极简”原话纳入spec，design明定系统承担安全复杂度，无历史窗口/逐消息三选一/审核参数，IM delta同步。


## Round 15

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`。
- reviewer target: R14-W1原型闭合、用户“优雅极简”原则的spec/design/IM delta收敛及新增走查记录；工作树、分支、HEAD同R14。
- review_mode: **closure**。
- mode_reason: 新增原型只补R14已经确定的两段用户流程，极简原则明确不加配置/逐消息选择，未更改业务授权或架构；独立实际操作核旧缺口，不重开无变化旅程。
- retained_from: **Round 14**的数据/权限与接口判断，**Round 11–13**宿主/来源/出口，**Round 9/10**现有聊天基线及其他目标/告知旅程；DeepSeek资源警告保留。
- started_at: `2026-10-19T13:19:42+08:00`
- completed_at: `2026-10-19T13:22:28+08:00`
- duration: `166s`
- validated_at: spec.md `107e45fb71d570b8fc4a45b6541a657b2136b39622fe82bce211b9110cf92c8a`；design.md `085e85d9904e7893076b843881d90c427ef35bbcd64b00f0f8e479d5e92f0fef`；prototype.html `95d41f1bb2fc826512916d5540ad8d4aea5c0ec278782c86f0be4018869629cb`；specs/im/personal-agent.md `462f0f2d2ff06366977734b6f4fb4037d7f55aa78b8d4bbe3d37f7320dd2a3b5`；research/history-delegation-ux.md `ec4ee489dd307db1b2e203c46d106eb2d7354becebc4abf7ac624d7e688eb4ec`。
- write scope: 只追加报告，完整保留此前 162123 字节，追加前SHA-256 `400efcb178e51de74d85b640cd10293ba277a33cee03605339e0246b3ba49abd`。原型本轮一处邻接消息顺序问题由作者修复，reviewer reload最终版独立复验；无产品修改、提交或部署。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

**R14-W1已关闭，本轮没有未关闭的新增实质问题。** 历史答案→原文→返回与双方PA代发标记均有真实浏览器操作证据；发现的邻接顺序问题已同轮修复复验。仅保留DeepSeek必验资源前置（R15-W1），Gate 2仍未Approved。原型是合成静态样例，不证明实际检索、鉴权、模型或投递已实现。

### 历史问题闭环与独立证据

#### R14-W1：closed

**检索与出处。** IAB对reviewer不可用后，新建独立Chrome复核页 `http://127.0.0.1:8766/prototype.html`，未使用作者/用户标签、未写内部状态。在1440原输入框询问“去年产品协作群里，我们怎么约定演示报价的？”，直接得到“演示不放报价、重点门店协作，报价另发林悦”的答案，下方相邻展示产品协作群、陈同学、2025年6月12日14:32及“查看原消息”。结论先于出处，出处可在同一眼阅读范围内核查，没有时间窗口、查询模式或审批步骤。

实际点击进入原产品协作群，2025日期、原文高亮、前后林悦两条上下文同时可见；没有错误“今天”标签。“返回个人助手”回同一答案。随后连续要求代发，原问题和历史答案仍保留在其前。切390再从已保留答案点原文/返回，两侧文字自动换行，原文内容和返回动作可见，不需记住屏外信息或重问一次。这独立复核了作者记录的日期/连续对话修订。

**代发身份与草稿区别。** 从原PA输入框明确说“替我回复林悦：这次演示先不放报价，重点展示门店协作，报价单会另发给你确认。”，没有额外确认弹窗。回执附同一正文与“查看原聊天”；原人际DM显示小航头像/名字，固定标记“陈同学的 PA · 代为发送”贴在正文上方。产品外切换“林悦看与陈同学的私聊”，标题仍为陈同学的人际聊天，正文和标记相同，不把聊天改成林悦与PA的另一个DM。1440与390实际截图中，身份标记、文字及输入框清楚可见，标记不是正文自称。

在本人390原DM补走“让小航帮我回复→放入输入框→发送”：草稿说明本人编辑/发送，发送后为本人右侧浅绿气泡；PA代发仍为有固定标记的Agent气泡。对方视角本人消息作者为陈同学，PA消息作者为小航并有代发标记，区别由真实界面表达而非用户读技术字段。

**同轮发现并关闭。** 首次补走草稿时，较晚本人消息被插在先前PA代发上方，源于ordinaryContent把全部peerReplies画完后固定追加delegatedMessage。已向作者报告实际步骤，作者把PA代发也追加同一消息序列，双方视角按同一序列渲染。reviewer reload后重新代发，再完整完成草稿放回/发送：本人界面顺序为林悦原请求→PA代发→本人后续消息；对方也显示相同顺序与各自作者，没有丢失或重复。最终console未见原型脚本错误；两条错误来自浏览器Zotero扩展连接，不归因原型。未据此扩展其他无关旅程。

**证据与适用边界。** 可持久复查的代表图/作者走查在 [history-delegation-ux.md](research/history-delegation-ux.md)，包括 [历史答案桌面](research/history-delegation-evidence/README.md)、[历史答案手机](research/history-delegation-evidence/README.md)、[原文](research/history-delegation-evidence/README.md)、[本人手机代发](research/history-delegation-evidence/README.md)、[对方手机代发](research/history-delegation-evidence/README.md)；本轮独立操作与其主要流程一致，邻接消息顺序修复的额外证据以上述reload复验为准。仅检查合成报价约定和固定代发文本，不将其称作通用搜索器；未找到/未覆盖/无权与分页撤权的真实差异由现有spec/design/安全场景明确，留待产品运行验收，不宣称本原型实现这些后端状态。手机是响应式Web，不是native iOS验收。

**极简原则。** spec保留用户最新原话，design:65–67把检索分页、来源/审核/恢复归系统责任，正常入口保留聊天输入；自然语言暂停/来源例外和只给草稿可表达偏好，必要新决定才询问。IM delta同步普通流程不配置历史时间、审批参数或每消息三选一。实际新增路径符合此收敛，没有把安全技术步骤搬成产品按钮。原型表/M1与新增记录衔接，不要求重做导航或扩大配置范围。

#### R14-W2：still-open → R15-W1

design:298,306与Author Resolution继续说明DeepSeek隔离资源未落实。无新资源证据或用户调整前置顺序的授权，原警告保留。

### Issues

#### R15-W1 — DeepSeek 必验资源仍未落实

- 分类：实施验收资源前置；retained from R14-W2。
- 位置：`design.md:298,306`，M1 W7。
- 影响：静态原型闭合不代替真实模型有用性、来源/外发审查、host/API及真实接收端结果。
- 关闭条件：安全落实授权隔离资源，或记录用户对前置顺序的明确调整；最终真实验收仍须执行。

### Recommendations

无。两段新增体验及本轮直接发现问题已完成有界复核，不继续扩展相同审查。

## Author Resolutions — Round 15

- 接受R14-W1关闭结论：独立1440/390查询原文往返、双方代发身份与本人草稿发送完成。审查发现的原型消息顺序问题已将本人/PA消息统一按发送顺序渲染并同轮复验通过，无新增实质问题，停止修订循环。
- 唯一DeepSeek资源警告继续保留，不标Gate2 Approved；此次交付为设计与静态原型，非真实后端验收。

## Author admission update — 用户授权先实施

2026-10-19 用户原话“你先去实现吧”。在已反复明示唯一资源缺口的上下文中，按此直接授权把 DeepSeek 资源准备顺序移至交付前真实验收，不省略最终验收。design资源段同步；功能/安全/原型语义无变化。请求独立关闭资源准入警告后进入默认简化实施。


## Round 16

### Metadata

- reviewer: 独立 `change-design-reviewer`，agent `/root/design_review_r7`。
- reviewer target: 用户明确授权先实施后的唯一资源准入警告R15-W1；`design.md:298,306`与Author admission update。工作树、分支、HEAD同R15。
- review_mode: **closure**。
- mode_reason: 仅核对旧警告关闭条件中的用户授权调整前置顺序，不重审没有变化的功能、安全、接口或原型。
- retained_from: **Round 15**及其明确继承的R9–R14独立证据；全部已关闭设计问题保持关闭。
- started_at: `2026-10-19T13:26:03+08:00`
- completed_at: `2026-10-19T13:26:24+08:00`
- duration: `22s`
- validated_at: design.md `02467560927547b14de7b586a84905c9914c3414b211c478c8b006952b4d32bf`；prototype.html `95d41f1bb2fc826512916d5540ad8d4aea5c0ec278782c86f0be4018869629cb`。
- write scope: 仅追加本报告，保留此前 169904 字节，追加前SHA-256 `480ae638c4bcfef3fab8cb541fd082eed3a76af05cadda5a7d9365618ad2d53b`；无产品实现、模型调用、提交或部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2设计准入通过，可以进入实施。**

这不是模型或产品验收通过：DeepSeek资源尚未核实，真实模型、有用性/安全与host/API验收继续作为交付退出条件。

### 历史问题闭环与证据

#### R15-W1：closed（用户调整前置顺序）

R15-W1原关闭条件明确允许两种证据：资源落实，或用户明确调整其前置顺序。本轮收到用户在资源缺口已明确告知后直接要求“你先去实现吧”的授权，Author admission update保留该原话和上下文；design:298据此把资源准备从实施准入前置移至交付前真实验收。此次关闭基于用户对顺序的调整，未声称凭据已经可用，也未把模拟验证视为替代。

design:306的M1 W7仍要求真实DeepSeek端到端同时证明有用与边界，并保留普通Agent/渠道/iOS API回归及runtime dependency contract。安全场景与原有接收端/全出口验证没有删减，后续若资源未落实，实施可继续但不能以当前设计批准宣告最终验收完成。

未发生新的功能、安全或原型决定，本轮没有重复浏览器操作、扩展检查范围或要求再次确认。所有其他结论按R15保留。

### Issues

无未关闭设计准入问题。

### Recommendations

无。按用户授权进入既定实施流程，保留真实验收退出条件。


## Round 17

### Metadata

- reviewer: `/root/design_review_r7`，独立 `change-design-reviewer`。
- target: feat-616 **设计版本 R9**，基于 feat-617 `87f5214a7`，集成 HEAD `b50704bdd`；本节序号沿用报告历史，非设计版本号。
- review_mode: **full**。
- mode_reason: 主人输入授权、工具边界、目标体系、来源撤销及交互承载均实质重写；不能以 Round 16 或旧实现验收代替本轮审查。
- started_at: `2026-10-19T20:25:34+08:00`
- completed_at: `2026-10-19T20:30:14+08:00`
- duration: `281s`
- worktree: `/Users/czj/.codex/worktrees/feat-616-personal-agent/nano-multiagent`。
- frozen input hashes: spec.md: `bb7b135b2324473f71e92a57de188c6480b9995706cac3b0666b1c3bbbc7a316`; design.md: `294670fbb1693c853c397e72eb530ee1d24c509e3ad5d079e588558d1021112d`; prototype.html: `2bf216ad3b334a32c0e3088ed2e13f1c5db02453ae575fc106ac3da0e7d01a1c`

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。** 复用与缩减方向可实施；新增草稿采用的完整往返及已有输入冲突仍缺少与设计一致的可操作方案。此结论不要求恢复任何旧 PA 目标、审批或配置体系。

### Coverage 与证据

**需求与现状。** 本轮逐项核对新版 spec 的固定绑定、完整 Global 能力、双身份历史、双向新消息、草稿/代发/静默、来源控制、持续协助、披露及双向告知。实际产品入口 `packages/personal-assistant/src/global-agent.ts:80,136–184,209–269,336–393` 仍含旧 admit/scopes/assistance 与 PA 专用发送分支；`apps/im-server/src/personal-agent.ts:23–40,72–96` 已有可信绑定和来源访问基础，但历史 SQL 仍仅枚举主人参与历史；`packages/dsh-integration/src/personal-security.ts:15–19,89–114,132–174` 仍有白名单、替代文件/搜索工具、goal/decision 和退休上下文。新版明确删除这些生产引用并扩展原 conversations/Inbox，正对实际需要改动的接缝；没有把当前代码已经存在误当新契约已实现。

**职责与复杂度。** IM 持有绑定、当前会话权限、来源事件、披露冻结和提交；PA 编排原 Inbox、Global、send_message/task_graph；DSH integration 承担模型审核和原工具适配。主人输入直达主 PA、来源工具只做可信身份/证据/版本验证，取消独立 scope 抽取和 PA 决策状态机，符合最新要求且减少重复授权状态。私人运行实例继续作为数据归属隔离，普通插件/代码沿原能力规则；这是用户明确改变的支持边界，不再要求旧“所有任意执行均受出口门覆盖”的保证。保留旧 task_graph 数据，不新增旧私有表兼容读取，也未要求删除用户任务。

**披露和告知。** `design.md:44–58` 将真实主人消息、617 提交和服务端材料作为证据，明确模型提案不签发许可；冻结具体消息/附件/共享任务、独立审核、后端复核和真实回执链继续成立。`apps/im-server/src/personal-actions.ts:47–79,83–115` 说明旧实现确有冻结、权限/受众/版本复核，但也仍有 scope 和任务动作限制，必须按本轮设计移除；不能直接保留旧分支声称复用完成。新版明确外发 interactive 全量内容进入 payload，不只查 text；私聊给主人不加披露审核。固定对方通知仍以主人通知真实回执为前置。任意 shell/插件网络流量与审核模型误判均未被夸大成已解决。本轮无真实模型安全测试，M1 仍须验证拒泄露与正常持续协助。

**617 复用接口。** `apps/im-server/src/interactions.ts:58–73,76–138` 已持有不可变 publication、私有 interaction_drafts 的 CAS revision、真实提交身份和 interaction_reply；`packages/product-contracts/src/interactive-types.ts` 区分 public UI、私有草稿和提交快照。`src/IM/frontend/src/features/chat/interactive/interactive-card.tsx:55–119` 已持有本地当前字段、异步保存及提交。设计新增 reply_draft 仅保存来源定位/field_name，正文由该唯一存储持有，采用另走原聊天输入框，避免复制造成第二套正文/决策状态。实际 `message-pane.tsx:385–398` 的 draftSeed 当前直接 setDraft，不能未经冲突判断复用；其 `:211–215,414–436` 已有按会话保存未发送内容的基本能力，适合复用而非另建草稿库。

**独立 UI 操作。** 独立 Chrome 标签 `1805414554`，`http://127.0.0.1:8766/prototype.html`，先看桌面实际渲染再操作。将回复改为“周四 16:00 演示，材料提前发你。”，采用后标题为林悦、内容只出现在输入框、历史无新增气泡；点击发送才产生本人气泡。390×844 视口下原聊天没有返回或聊天列表入口。恢复桌面后输入另一段尚未发送的文本，再切 PA 并采用，原输入被替换，未出现保留/取消等处理。源码 `prototype.html:8–10` 与观察一致。视口已恢复；这只是静态原型，不声称后端/权限/存储验证。原产品 `app-shell.tsx:17–18,24,55–88` 明确手机会话隐藏全局导航、列表有底部导航；本轮所需是继承原会话返回路径，不是新增一套导航。旧 R9/R15 的基线/代发身份证据仅继承其未改视觉要求，不能替代本轮新增采用流程。

**delta 与 milestone。** 两个 personal-agent delta 的 canonical target 当前尚不存在，ADDED 分类正确；原先分散的八个 delta 删除与“普通 Global 不增加 PA 业务”一致。新版 IM delta 覆盖配置/双身份/双向/草稿/代发/来源/告知；Gateway delta 覆盖完整能力/来源/外发；持续协助明确沿 current Global 语义。M1 单组避免跨共享文件并行冲突，退出项包含旧生产引用清理、普通 Agent 回归、模型与重启证据。主 6.1 Sol/审核 6 Luna 为本轮确认配置，旧 DeepSeek 资源问题不复活。未运行产品测试或访问生产。

### 历史问题闭环

- Round 16 的原前置顺序警告保持关闭；新模型配置与本轮验收范围以 R9 为准。
- 旧 PA 专属 goals/decision/cleanup、全出口限制、来源派生清理相关通过项由最新用户授权显式替代，不作为本轮复用保证，也不以旧已通过阻止缩减。
- 固定绑定/私人 Work ACL、真实 actor 与代发标记、主人通知回执顺序保留为要求；本轮未宣称重新完成全部实现验收。

### Issues

#### R17-W1 — 草稿采用缺少完整往返与已有输入保护

- 位置：`design.md:52–54,76`；`prototype.html:2,5,8–10`。
- 证据：390 宽度采用后侧栏隐藏、无可用返回入口；桌面原聊天已有未发送输入后切到 PA 再采用会丢掉该内容。原型亦未体现“主人已回复”的过时提示。设计虽说“不自动覆盖用户编辑”，没有指定发生冲突时用户如何保留已有输入并继续采用。
- 后果：实施者若照原型或直接套用现有 draftSeed，会造成输入丢失；手机用户不能完成 PA→原聊天→PA 往返。仅验证“采用不发送”不足以指导这条新增交互。
- 收口要求：补最小可操作方案并同步设计：继承现有会话返回/列表路径；按会话保留输入，目标输入非空时明确保留、取消或用户主动替换的处理；显示已回复时的过时状态。无需新设置页、审批、业务状态机或新草稿数据库。用桌面和390实际操作证明往返、冲突不丢内容、采用不自动发送即可。

### Recommendations

无额外建议；本轮不扩展实现范围。


## Round 18

### Metadata

- reviewer: `/root/design_review_r7`，独立 `change-design-reviewer`。
- target: feat-616 设计版本 R9，Round 17 后最小原型/设计修复。
- review_mode: **closure**。
- mode_reason: 仅复核 R17-W1；没有新增架构、权限或产品能力变化。
- retained_from: **Round 17** 的需求、架构、617 接口、披露边界、delta 和 milestone 审查；没有重新扩大范围。
- started_at: `2026-10-19T20:30:23+08:00`
- completed_at: `2026-10-19T20:33:13+08:00`
- duration: `170s`
- final hashes: spec.md: `bb7b135b2324473f71e92a57de188c6480b9995706cac3b0666b1c3bbbc7a316`; design.md: `9342659f47f14264b3949836c3123d905994759fdaddf74f654d358aa4016430`; prototype.html: `f3c557297ad2b342b1b5bf860d4500e30686dcf776740e7b8f8416e36b7c6e3e`

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

这是设计准入结论。R9 实现、真实模型持续协助/披露测试、重启和普通 Global 回归仍需按 M1 完成；不把旧版本实现验收继承为新版本通过。

### 历史问题闭环与证据

#### R17-W1：closed

作者在 design 的“IntelligentUI 与原聊天草稿”明确：非空目标输入由用户取消保留或明确替换，手机版复用原聊天返回/列表路径；原型按会话保留 composer 并加轻量过时提示，没有新配置或草稿存储。

独立复验桌面：在林悦输入“原聊天已有草稿，暂不发送”，回 PA 编辑另一份草稿并采用；取消替换后原输入仍完整且无新消息。普通空输入采用与真正发送的区分已在 R17 实操成立。明确替换分支由原型 confirm 的选择控制；本轮未把浏览器确认框的工具超时算作替换成功证据。

独立复验最终390×844页面：可见“你已在原聊天回复，草稿可能过时，请核对后采用”；将草稿改为“手机回复：周四16点”，采用后只进入林悦输入框，聊天历史无新增本人消息；通过返回按钮往返 PA 与林悦，PA 编辑字段及林悦未发送输入均保持。方案中的返回继承现有产品会话导航；静态两会话原型的切换仅表达这条往返，不作为新增生产导航要求。观察了最终画面和文本层级，轻提示在草稿动作旁，未增加审批负担。原型标签已关闭，临时视口已恢复。

证据澄清：R17 的 UI 观察是修复前页面；报告落盘采样与作者开始局部修复接近。最终接受的设计/原型以本轮 final hashes 为准，R17 历史观察不被回写成修复后结果。

### Issues

无未关闭项。

### Recommendations

无。
