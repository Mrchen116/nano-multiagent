# Design Review

## Round 1

### Metadata

- reviewer target: `/root/skill_stats_design_review`（独立 reviewer）
- review_mode: full
- mode_reason: 首轮；覆盖 incident、完整 design、delta、prototype 源码及实际产品组装和消费链。
- started_at: 2026-10-28T11:02:38+08:00
- completed_at: 2026-10-28T11:03:18+08:00
- duration: 40 seconds（最终结论核对计时；此前只读准备未计时）
- validated_at: `594cf4128333d1a9946be46a8b47a184305241b4`
- executed_base: `ff326c351d104447028f4b185740ab6d6be55de6`
- 检查时 checkout 为 detached HEAD；开始时 clean，后续出现非本 reviewer 创建的 `.vite.process-start`，未修改或清理。仅本报告由 reviewer 写入；不提交。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

后端职责拆分和宿主归属方案可行，且符合用户“仅展示修复后新统计、不回填旧样本”的明确选择。旧缓存兼容、iOS 日期/计数呈现及必要的原型视觉证据仍未收口，暂不能交付为已通过 Gate 2 的完整方案。

### Coverage 与证据

1. **现状与需求。** `KnowledgeFiles.use()` 在同一 root 锁内更新旧累计、200 条去重键和 60 条样本；`usage()` 在共享 root 以筛选后的样本数重算累计，并对所有 root 从样本计算 30 天趋势（`packages/dsh-integration/src/knowledge/files.ts:123-156`）。这直接支持 incident 的截断根因。保留旧字段而新增 per-agent 累计/日桶，不需要增加数据库或扩大样本保留；首次未去重调用创建新统计，与用户选择一致。
2. **真实组装和归属。** `packages/dsh-integration/src/index.ts:179,439` 将 `configurationService.forAgent()` 注入 KnowledgeRuntime，并注册 `knowledge.usage`；`agent-config.ts:48` 从宿主保存的 Agent scope 返回配置。`runtime.ts:223-240` 从配置允许的 roots 定位已成功使用的 Skill，随后才检查 F4 开关和 binding。传入 `config.agentId`、移除读取端的会话 cwd 推断，能在共享引用被挤出后继续准确归属；不引入模型可控 owner。
3. **维护与 Context 隔离。** `files.ts:159-168` 的 references、`178-200` 的 F4 计数/候选与 `224-239` 的归档依赖原字段；`runtime.ts:87-100` 的换窗恢复通过原 references 加载 Skill。设计明确不改变这些字段的用途、样本保留、事件触发或 F4 判定。新增统计不交付给 LLM，因而本次无新增 Context Surface，不触发完整 Agent Context Review；实施时仍须验证原 references 和 F4 回归，不能用新投影替换维护输入。
4. **公开链路。** 实际链为 `apps/node/src/main.ts:266-270` → integration `knowledge.usage` → IM。Web 当前使用 `/im/v1/agents/:agent_id/settings/sections/usage`（不是 design 中简写的 `/settings/usage`），经 `agent-settings.ts:99-117` 白名单及持久快照；iOS 使用 `control.ts:1050-1071` 的 `/skills/usage`，该接口当前直接输出 runtime 的 skills。设计要求两条链都核对且不透出其他 Agent 聚合是正确的，但旧快照分支见 R1-W1。
5. **Web 与 iOS。** Web `agent-detail-page.tsx:825-870,975-1089` 当前使用客户端本地日期，热力图补全年；指定服务端 UTC 窗口和起点前未知状态能够修正这些含义。iOS `AgentSkillsView.swift:27-30,55,78-89` 仍是仅含整数的序号柱状图，并将窗口合计命名为总数。该端决定缺口见 R1-W2。只做字段绑定时采用编译/解码回归、共享链路用 Web 验证是合理的，不机械要求模拟器。
6. **Delta 和范围。** delta 锚定 `docs/specs/im/agents-nodes.md` 的既有 Requirement，保留查询、source 类型和离线场景并添加新口径；无一次性生产迁移，因而无需 deployment-prompt。离线/缓存场景需要补上旧版缓存的处理，不能只写“保留现有语义”。单 milestone 覆盖 integration、两个 IM 投影和两端消费，无并行文件冲突。
7. **测试和验收。** >60 次、共享 Agent、跨日、重启、去重、维护字段、聚合不泄漏，以及真实 Web 新统计/空态/390px 是合适的范围；已有 `knowledge.test.ts`、`knowledge-review.test.ts` 可复用 F4 与归档验证。daily 隔离脚本及临时 Skill/Agent 来源明确，不依赖生产写入。需把以下缺口相应纳入退出标准；本轮只有设计，不运行或声称实现测试通过。
8. **视觉证据限制。** 只读取 prototype 源码，未看到渲染画面，也未操作原型。已知 file URL 与 Codex 原生窗口读取被策略拒绝；本 reviewer 没有更换协议、起服务、换浏览器或其他工具绕过。真实产品隔离 HTTP 入口的后续验收是另一动作，不能倒推本轮原型已经过视觉核验。具体对设计判断的影响见 R1-W3。

### 历史问题闭环

首次审查，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 旧版 usage 快照仍会穿过新统计边界

- 位置：`design.md:17-19,27,44-48`；delta `specs/im/agents-nodes.md:32-34`。
- 证据：`readSettingsSnapshot()`（`apps/im-server/src/agent-settings.ts:74-86`）只校验 owner、node epoch 和 workspace，随后原样返回缓存 JSON；`control.ts:838,856` 在离线或读取失败时调用它；Web `agent-detail-page.tsx:1227-1232` 直接使用 `read.data`。既有缓存含旧 use_count/heatmap_data，但没有新统计起点和日期边界。
- 后果：升级后节点离线或第一次刷新失败时，即使 `.usage.json` 的新投影完全正确，Web 仍会拿旧缓存计数进入新版视图。若把缺失起点视为空，会同时出现非零旧数与“尚无新调用”；若直接显示这些数，则违反仅展示新统计的选择。离线提示只说明时效，不说明统计口径变更。
- 修订要求：明确缺少新版统计字段的缓存不可作为新统计输出，选择最小的读取时失效/降级规则；保留合法新版缓存语义，无需生产批处理或回填。加入“旧 usage snapshot + 离线/刷新失败”与“新版 snapshot + 离线”的接口/客户端回归。在线旧形状响应同样不得被默认包装成新版统计。

#### R1-W2 — iOS 对起点前日期和累计数的决定尚未形成可实施契约

- 位置：`design.md:19-20,35,54,62`；delta `specs/im/agents-nodes.md:11`。
- 证据：现有 iOS Agent 视图用 `heatmap_data.reduce(0,+)` 显示“调用总数”，`AgentUsageChart(values:)` 仅接 `[Int]`，以 1..N 为时间轴；起点前补零和有依据的零调用没有区分。设计仅说明复用现有趋势/字段、增加“最近 30 天（UTC）”与起点，未选择该端如何处理起点前桶；“同一语义 / may-adapt”没有补足这一决定。
- 后果：实现者可以按现文字仅添加两条标签并保留柱状图和总数计算；当累计超过 30 天窗口时“调用总数”仍下降，且起点前日期仍被画成零调用，不能兑现 incident 对 iOS 的要求。
- 修订要求：明确 Agent 总数来自所有 Skill 的新累计还是将该值明确命名为窗口内调用数，并明确图表对起点前/无起点数据采取省略、未知状态或其他具体表示，以及服务端日期如何对应图表。将这些规则纳入 iOS 解码/展示契约测试；若最终仅调整字段和图表数据绑定，不必因此要求整套原生实测。

#### R1-W3 — 原型仍是视觉未验证草稿，尚不足以确认本次窄屏信息关系

- 位置：`design.md:30-36,54,62`；`prototype.html`。
- 证据：设计如实记录未渲染，且没有当前产品截图/操作证据。源码原型的列表只有名称、次数、起点三列；真实列表还有来源、状态、最近使用和趋势（`agent-detail-page.tsx:940-965`）。新增起点如何放入实际列表、30 天格子和说明如何在 390px 保持对应关系，无法从该缩减背景或源码判断。共同标准要求必要视觉检查在设计阶段完成，工具不可用时只能标注草稿。
- 对实际判断的影响：不否定聚合与 API 方案，也不把未观察到的挤压宣称为已存在产品缺陷；但本 unit 明确承诺窄屏可读，且调整列表信息与热力图布局，缺少画面使 reviewer 无法独立确认这一 must-match。目前不能把该部分评为 Approved，不能仅以后续实现验收替代。
- 修订要求：保留实际受影响容器和邻近字段，收口起点放置及窄屏关系，再由获准的人工观察或明确获得授权的可用证据途径补足代表性画面和走查记录。此要求不授权绕过已经被拒绝的预览操作；在限制解除或取得合规证据之前继续标注视觉未验证，不把它声称为就绪原型。

### Recommendations

- **R1-R1（可选）**：把“跨日”测试具体化为跨越 30 天窗口边界：旧日桶退出窗口后累计仍保留，另一 Agent 的首次新调用时间和累计不被该清理影响。这比重复多组同日计数更能验证新增持久累计与有界日桶的职责划分。

### Author Resolutions

- R1-W1 accepted：design 接口段明确新版必需字段、旧快照读取失效、在线旧形状拒绝，delta 离线场景和退出标准同步。
- R1-W2 accepted：design 明确新累计与窗口合计分开，UTC 日轴、起点前省略和无起点空态，以及相关测试。
- R1-W3 accepted，视觉证据 pending：已走查隔离产品六列表格；原型补足邻近字段，起点放在名称下，窄屏沿用横向滚动，热力图保留周/日关系。受限预览不重试，仍标注视觉未验证草稿。
- R1-R1 accepted：跨日细化到 30 天清理边界，确保累计与其他 Agent 统计不受影响。

## Round 2

### Metadata

- reviewer target: `/root/skill_stats_design_review`（与 R1 相同的独立 reviewer）
- review_mode: delta
- mode_reason: R1 后的变化限于既有新统计契约的缓存入口保护、客户端具体呈现及对应验证；累计/日桶/样本职责、宿主归属、持久化边界和 milestone 划分均未改变。复核全部设计 delta 及其接口/客户端影响，不仅依据 author resolution 关闭问题。
- started_at: 2026-10-28T11:17:41+08:00
- completed_at: 2026-10-28T11:18:43+08:00
- duration: 62 seconds
- validated_at: `18d6922d25f632deb1facdfcc425e36620c67314`
- executed_base: `ff326c351d104447028f4b185740ab6d6be55de6`
- effective_base: `ff326c351d104447028f4b185740ab6d6be55de6`
- effective_through: `18d6922d25f632deb1facdfcc425e36620c67314`
- retained_from: Round 1，Coverage 1–3 的根因、架构、宿主配置归属、维护/F4/Context 隔离证据；两次检查间仅 unit 文档和原型变化，实际 owning code 与 base 未变。
- 检查开始时 worktree clean；本轮只追加本报告，不提交，不改变截图或原型服务。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1 的三项问题已在设计层面关闭。批准范围是可进入实施的方案；尚无修复实现、实现测试或真实产品验收通过结论。

### Coverage 与证据

- **入口与缓存。** 独立核对 `594cf4128..18d6922d2` 完整 unit diff。`design.md:28` 用已经需要的新统计字段识别口径，区分 null 起点与缺失字段；旧 snapshot 降级为 unavailable，在线旧形状读取失败且不得覆盖合法新快照，合法新快照继续保留 last_known/captured_at。该决定覆盖 R1 已核实的 `readSettingsSnapshot` 与两个 IM 路由分支，不增加迁移数据库或通用版本抽象。delta 的离线场景和 `design.md:50` 的回归退出标准与之相符。
- **客户端含义。** `design.md:36,38` 明确 Web 起点放在 Skill 名称下，保留六列及局部横滚；两类总数分开标记。iOS 使用全部 Skill 新累计之和与 30 天桶合计两个值、UTC 日期轴、按对应起点省略前置桶，无起点不画图。Skill 图使用自己的起点，避免误用 Agent 最早起点。delta 的“累计超过当前窗口”场景覆盖两端结果，数据契约测试覆盖失真发生的关键边界。
- **独立视觉观察。** 本 reviewer 通过图片工具实际查看 `evidence/prototype-desktop.png`、`prototype-mobile.png`、`prototype-mobile-scrolled.png`。桌面图可见名称、来源、状态、次数、最近使用和趋势的同一行关系，起点紧随 Skill 名称；空记录与有调用记录容易区分。390px 图中名称/起点保持可读，表格右侧有明确裁切，滚动后截图可读最近使用与趋势；热力图卡片仍在同一页面宽度内，两个计数各有标签，起点、UTC 窗口和未知/零/有调用图例完整。与 R1 仅有三列源码相比，现有证据足以判断本次局部增量的空间与信息关系。
- **观察范围。** 用户已明确授权仅 127.0.0.1 HTTP 预览，作者在 `design.md:46-48` 记录渲染及横滚，截图来自原型 `f2a038751`；随后提交只补记录，所审原型未再改变。本 reviewer 尝试打开获准的预览 URL 时，本聊天工具返回 `Browser is not available: iab`，因此没有声称亲手完成横滚；独立视觉判断基于上述已渲染的三张截图，横滚动作证据复用作者记录。原型无本次新增的业务交互，布局和横滚前后证据已足够，不因本 reviewer 的浏览器运行环境不可用继续阻断，也未尝试此前被拒绝的 file URL 或原生窗口操作。
- **未变范围与验证。** 用户选择的新统计起点及不回填规则、按 Agent 的聚合、30 日桶/60 条样本/200 条去重的独立职责保持 R1 判断；维护字段与 Context 消费链未扩大。单 milestone 加入旧缓存、iOS 展示数据及 30 日清理边界验证，覆盖新修订。真实 Web 产品验收及 iOS 编译/契约验证仍按原 runbook 在实施后进行，与本轮原型观察互不替代。

### 历史问题闭环

| Issue | Author Resolution | 本轮独立证据与判断 | 状态 |
|---|---|---|---|
| R1-W1 | accepted；新字段形状判定、旧缓存失效、在线旧形状拒绝 | design:28/50 与 delta 离线场景覆盖实际快照回退路径；不再默认把旧数带入新视图 | closed |
| R1-W2 | accepted；双计数、UTC 日期、起点前省略、无起点空态 | design:38 与新增 delta 场景给出可实施且可验证的 iOS 数据/呈现决定 | closed |
| R1-W3 | 初次 resolution 仍标 pending，后由用户授权及 design:46-48 补齐证据 | 本 reviewer 已独立看到桌面、390px、局部横滚后截图；六列、起点、30 日图例及空态可辨。早先“视觉未验证”状态已由后续事实取代 | closed |
| R1-R1 | accepted | design:50 将 30 日清理边界、累计和其他 Agent 不受影响纳入退出标准 | adopted |

### Issues

无新增或仍未关闭的 CRITICAL / WARNING。

### Recommendations

- **R2-R1（可选）**：后续整理文档时把 design:39-40 和原型顶栏的“视觉未验证”明确标成历史状态，链接本轮记录，减少接手者在前后段落间判读状态的成本。后续证据已有明确时间和覆盖说明，此处不构成 Gate 2 阻断。

