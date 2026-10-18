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
- validated_at: 上述 HEAD **加未提交冻结设计树**；`research/design-r1-snapshot.sha256` 的 SHA-256 为 `b7dcebe3d093502a79e5ed101c396675ac8096f2a03d2197520f5797b15a86d0`。逐文件校验 11/11 通过，包含 spec、design、prototype、7 个 delta 与 M1 `.gitkeep`。这些文件尚未提交，不以 HEAD 冒充其提交 SHA。
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
- validated_at: 上述 HEAD 加未提交冻结树，`research/design-r2-snapshot.sha256` SHA-256=`e90317f090174dfe3d5b8b7e4644994b5cb9c28a0fdf894f981ed183b1957e32`；14/14 文件通过。R2 manifest 路径以仓库根为相对基准，与 R1 manifest 的 unit-relative 格式不同；按正确基准校验，不把首次工作目录错误当文件变化。
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
- validated_at: **上述 HEAD + 未提交 R3 manifest 所定义的实际工作树**；manifest `research/design-r3-snapshot.sha256` 的 SHA-256 为 `2436a3eb1ce537f64450fb8854e4e3b4e72a317cbc44df1e2e02ee4c2e7cd9a1`，开审与写报告前均核实 **14/14**。这不是已提交的 unit SHA。
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
- validated_at: **HEAD + 未提交 R4 manifest 定义的工作树**。`research/design-r4-snapshot.sha256` 的 SHA-256 为 `8576a481e1d60690ebe7f9c91fd37b552ca29acb843ec39a1feadd8f9d4eee3a`，开审及写入前 **14/14** 验证通过；不伪称 unit commit。
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
- validated_at: **HEAD + 未提交 R5 manifest 的实际树**；`research/design-r5-snapshot.sha256` SHA-256 `6e2562d439f05ab9dca3a8a846c14f164b0bb4461adbb9f35f99e441caad28ee`，开审和写入前 **14/14** 核验通过，不表示已提交 SHA。
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
- validated_at: **HEAD + 未提交 R6 manifest 定义的实际树**。`research/design-r6-snapshot.sha256` SHA-256 为 `683719c53b7024d29330e7500603dc046c2cf6f65af5eef22e7b001a7c3a0db3`；开审及报告写入前 **14/14** 验证通过，不表示已提交 unit SHA。
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
