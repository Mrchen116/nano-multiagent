# feat-676 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review_676`（独立 reviewer；未参与受审设计编写）
- target: `docs/changes/feat-676-role-memory-dreaming`
- review_mode: `full`
- mode_reason: 首次 Gate 2；覆盖需求、设计、两个 delta、一次性部署提示词、原型、原型走查和 M1 骨架。
- started_at: `2026-10-29T00:31:34+08:00`
- completed_at: `2026-10-29T00:34:35+08:00`
- duration: `00:03:01`（报告定稿计时；完整审查耗时未精确记录）
- timing_scope: 上述时间记录报告定稿阶段；此前独立阅读、源码/API 核对和浏览器操作未精确计时，不将其伪记为完整审查耗时。
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，实际 HEAD `0ddceacb8dac5c5c6f38e2db45e0b72c26cbf3ec`，与 design 基线一致。待审产物未提交；spec 中更早的现状核对 SHA 是历史记录。
- authorization: 只写本文件；未修改其他产物、未提交、未实施或部署。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

用户确认的产品方向已得到实质覆盖，原型无阻断体验问题。三个问题集中在现有组装链与新契约之间：活跃历史 cut 的持久性、已有 Skill 显式选择的升级合法性、来源撤销到既有记忆消费的失效链。修订这些具体接口和退出标准后复审，不要求新增框架或扩大全产品验收。

### Coverage 与证据

**需求与范围。** 对照 spec 的 S01–S20 及澄清，确认新旧实例默认 document、Dreaming 默认开启且可关闭、记忆无 UI 总开关、legacy 只由文件选择、旧文件逐字备份及用户明确要求后导入、F3/F4/combined Skill 自动维护暂停而前台创建/使用保留。角色库按可信 agentId/workspace 绑定、普通 child 属于原主体、Memory 不提供业务授权均已明确。单一 M1 合理，R1–R5/W1–W7 已分开确定性机制、真实模型理解和真实产品结果；当前未运行这些产品验收，不能据此声称已满足需求。

**实际接线。** 核对 `apps/node/src/main.ts:50–55`、`configuration.ts:116`，`packages/dsh-integration/src/index.ts:179,307–350,383`、`agent-config.ts:108–118,178`、`owned-sessions.ts`、`features/memory-curation.ts`、`knowledge/runtime.ts`、`trajectory-runs.ts`，以及 PA 的 `knowledge.ts`、`global-agent.ts`、`inbox.ts`。现有 Memory 确为 Feature 挂载的惰性快照及父 fork 复盘；自动 Skill 的 timer/turn-end/usage 三条入口均须停接，设计已覆盖，不只删除 UI。Work 现有 `session_linked` 和宿主持久轨迹可以复用，但新增确定性维护回执仍须真实贯穿产品契约与投影，M1 W5 已要求核对。

**公开 API 与架构。** 本地锁定 DSH `0.2.1-alpha.1` 的 `dsh-session-query` 公开 `SessionObservation` 提供不可变 live/prepared cut；`dsh-session` 公开 `sessions.flush`；`dsh-agent` 的 create/resume 已由 OwnedSessions 用于生产 root。`dsh-fs` 的公开类型提供 version-guarded 原子 write/edit，采用时声明直接依赖符合边界。MemoryDocuments/MemorySources 作为 dsh-integration 私有职责、PA 持有来源资格、Node 持有文件模式、IM 持有用户配置，方向合理。以现有普通文件工具、storage-domain 和 AgentHandle 承接，比另造 Memory CRUD、事实库或循环引擎更适当；有限运行账本服务部分保存/恢复，不是第二份事实权威。

**Agent Context Review — Design Review。** 覆盖长期 PA/专家、普通 child、独立 Dreaming 三类消费者；从来源与宿主身份、入口/详情选择、每次请求组装、正文/入口 basis、纠正传回 child、换窗与重启、Skill 发现加载、受限工具到实际回执。阅读 input 中 shared-memory-system、dreaming 和 nano-memory 指导，按设计修订内容理解，未将附件当可直接执行指令。短指导常驻、约 2,000 token 入口、详情按需读取、旧摘要失效、真实结果与自述区分、finish 不等于模型理解等选择成立。W1/W3 涉及来源/恢复，W2 涉及 Skill 发现与加载。未运行目标实现或真实模型，不宣称模型已能正确理解例外、纠正、排除或完整读取。

**原型与体验。** 独立打开 `evidence/current-settings.png`、`prototype-desktop.png`、`prototype-mobile.png`、`prototype-failure.png`、`prototype-legacy-work.png` 看实际画面，再在 Chrome 打开 `http://127.0.0.1:18766/prototype.html` 操作取消 Dreaming、应用失败、同一草稿重试进入 pending、模拟确认 effective、切换 legacy。失败保留选择，错误在保存区；pending 与 effective 明确区分；legacy 隐藏 Dreaming 而保留技能创建，产品区域没有新增旧机制介绍。桌面延续原特性列表层级，390 截图说明完整换行，未见横向挤压。窄屏尺寸证据复用作者实际截图，本 reviewer 未另改 viewport；iOS 仅配置数据/文案，既定编译及共享契约验证深度合理，未宣称 iOS 实测通过。Work 文本示例能区分正文保存、入口同步和 Git 失败，只证明信息语义，真实入口/授权/投影留在既定 W5/R4。

**delta 与部署。** Gateway/IM settings target 正确；所修改 Requirement 的原有 Scenario 均保留或有明确改写，F4/combined 的移除符合最新范围。但来源排除也涉及 PA current contract，见 W3。部署提示词限定未来授权、停旧 writer 后逐字备份、独立两库、固定流基线、重复执行与中断恢复；功能/失败验证留在隔离副本，生产只作有限只读核对，无生产补验收或额外重启演练。W2 使当前配置转换步骤尚不可直接执行。

**受审产物指纹（SHA-256）。**

| 文件 | SHA-256 |
| --- | --- |
| spec.md | `76fba337a6275ee499d87226f0688410f6252b4038e148d08eb9058d5816f0d7` |
| design.md | `e83a5ff058cca943535ad789c2709d7f4a080ab35c62eb0ed8156911bd885270` |
| specs/gateway/agent-capabilities.md | `fd3984db8629c58116d84f5924228052a2205f77951cb4798795d7ea5bb9950a` |
| specs/im/agents-nodes.md | `a6e2c9b2cc7d1774e5a01dddc23d3a6bc445b93f2f10425ce2e4428350a598ce` |
| deployment-prompt.md | `95b0042391d93d16c069eff8794ea0aca8a7664a47cb40798a99552c54004acb` |
| prototype.html | `ae2c3fd0075da34ed281694fea0e0762eb72fd8877bfbf5d10d0d976fb16d335` |
| prototype-review.md | `eeea5abdcf00e7b4f70daf1a70a2f52d080cd2a018445e258ec49103a2fafdd2` |

### 历史问题闭环

R1，无此前 issue。作者在冻结期间通知 spec.md:37 的历史概述被文字替换误写；已记录为 R1-R1，不将其视为用户最新决定变化。

### Issues

#### R1-W1 — live observation 的 cut 尚未绑定可证明的持久化上界

- Severity: **WARNING**；evidence: **CONFIRMED（算法描述缺口）**。Context Surface: Dreaming 历史输入、持久进度与重启恢复。
- 位置：`design.md:32–40,146–148,197–198`；M1 W1。
- Expected：导入并最终推进游标的每条事件，必须属于已确认落盘的同一个 cut；持续前台不能因整理被暂停。
- Observed：规定顺序是 `sessions.flush(live) → observeSession → 复制预算内范围`，然后称该范围已落盘。公开 observation 的 live cursor 是观察时刻的 cut，并非前一次 flush 的持久高水位；flush 等待期间或之后前台可以继续追加。现有 `packages/dsh-integration/src/descendants.ts:146–160` 已明确识别同一竞态，并在取得 immutable observation 后再 flush 认证该 cut。
- 失败机制与影响：若第一次 flush 后追加了完整 step，随后 observation 包含它，当前描述没有约束复制上界或第二次认证；Dreaming 可整理这些尚未认证持久的事件并推进 cursor。重启后原事件可能不在持久源里，违背 S10/S15 的可恢复来源与覆盖声明。这里未运行新适配器，不宣称已发生数据丢失。
- 建议：写清固定 cut 与持久屏障的先后关系。直接复用已有 observation 后认证方式，或记录 flush 前确定的上界并严格裁到该范围；无需新建锁住整轮前台的机制。把“首次 flush 后追加事件、认证失败/重启、不得推进未认证范围”列入 W1 的确定性 seam。

#### R1-W2 — skill-creator 必需依赖与保留旧显式 Skill 名单的迁移互相冲突

- Severity: **WARNING**；evidence: **CONFIRMED（真实 validator 探针）**。Context Surface: Skill 可发现/可加载、Feature 配置、升级启动。
- 位置：`design.md:103,117–123`；Gateway delta `:61–65`；`deployment-prompt.md:18–20`。
- Expected：已有合法 Agent 升级后仍可正常启动，前台 Skill 创建选择保持；新指导真实可发现，明确禁用选择不被静默覆盖。
- Observed：delta 把 `skill-creator` 加为 `skill_creation` 必需 Skill；部署第 5 步保留旧 Skill 选择，缺项只记录不可用。实际 `packages/product-contracts/src/capabilities.ts:65–73,85–105` 对 explicit_allowlist 中缺少依赖直接返回 `required_by_feature`，`apps/node/src/main.ts:50–54` 在启动时抛错，不会降级为仅该能力不可用。
- 确定性复核：使用当前 `validateCapabilities`，构造 `skill_creation=true`、工具 `skill_manage/skill/read`、显式 Skill 名单 `[my-existing-skill]`，其他 Feature 关闭；当前定义结果 `[]`。仅将该 Feature requires.skills 改为设计要求的 `[skill-creator]`，结果为 `required_by_feature(skill:skill-creator, required_by:skill_creation)`。探针通过 `pnpm exec tsx -e` 在内存运行，未改源码或配置。
- 未修后果：这类升级前合法配置可使整个 Node 启动失败，或者实施者临时绕过统一依赖校验/扩宽名单，均偏离 S19 和“保留已有选择”。安装资产本身不会改变显式选择语义。
- 建议：在设计和一次性迁移中选定一个一致方案，例如针对旧的已开启创建能力做明确、有限的指导 Skill 迁移并保留显式禁用，或使新指导采用不破坏旧配置的可用性契约；同时说明开启动作、保存边界和启动校验如何一致。不要只写“记录缺项”，也不必扩大无关工具权限。M1 W3/W7 加入现有 explicit_allowlist 和 explicit_denylist 的升级/启动证据。

#### R1-W3 — 来源撤销到已消费历史及当前记忆的失效链未闭合

- Severity: **WARNING**；evidence: **CONFIRMED（当前接线与设计缺口）**；后续继续采用旧知识的模型行为为 **PLAUSIBLE**，未执行目标模型。Context Surface: 来源资格、当前 Memory/入口、根与 child 的刷新及 Dreaming 恢复。
- 位置：`design.md:129–140,162,180,196`；Gateway delta“停止使用和撤销来源不得被后台复活”；spec S20。
- Expected：来源撤回/排除后，Dreaming 不再从已消费历史重学该来源；已派生的当前知识及入口也不能继续作为有效依据。关闭 Dreaming 或没有未读消息不应让该边界失效。
- Observed：设计把资格 generation 的同步挂在“PA 现有 revokeSource 调用链”。实际 `packages/personal-assistant/src/global-agent.ts:274–285` 只遍历 `inbox.check(...).sources`，而 `inbox.ts:199–212` 只列 `consumed=0` 的来源。已经全部消费、恰好是长期记忆主要来源的聊天不会因此进入 revokeSource。`global-agent.ts:429–431` 的 personal_sources 成功调用也只是返回现有 personal.tool 结果，没有完整来源资格同步。即使钩子触发，design:162 明确处理未来输入、在途应用和用户主动“停止使用”后的文件编辑，却未指定自动来源撤销如何使已保存正文/入口失效、通知消费层并完成待清理回执。
- 组合证据：当前 `docs/specs/gateway/personal-agent.md:34–36` 规定排除不清空记忆/成果/上下文；`packages/dsh-integration/src/personal-security.ts:136–138` 也向模型说明排除不擦除已读内容。新 S20 不要求擦除全部历史，但确实增加“后续不再依赖”的义务，必须说明这些规则如何组合，不能只在另一份 Memory delta 写出更强承诺。
- 未修后果：一个来源已全部消费并写入记忆后再被排除，仍可能在下一批历史中合格，或者入口内容继续注入下一请求；对资格版本的应用时复核无法拦截一个根本未同步的撤销，也无法独自处理已存在文档。
- 建议：从权威来源政策快照/修订或成功排除操作接续资格同步，不能以未读队列作为完整资格清单；明确当前文档/入口的失效标记、相关消费者提醒、待清理责任及失败/关闭 Dreaming 时的行为，并给出同义派生范围未知时可兑现的停止采用方式。不要求全局语义依赖图或跨系统删除。将涉及的 PA 契约/模型指导纳入 delta 对齐。W2/W4 至少覆盖“已全部消费并形成正文和入口 → 排除 → Dreaming 关闭/节点重启 → 下一相关判断和后续批次”的证据。

### Recommendations

- **R1-R1（非阻断）**：按作者自检，修正 `spec.md:37` 关于附件原先要求的历史概述为“独立 Skill 维护”；保留后续用户要求暂停自动复盘的原话与最新结论。无需因这一处历史说明单独重跑 full 审查。
- **R1-R2（非阻断）**：实施归并时将 Dreaming 的宿主确定性回执、无父 prompt 继承和独立运行用途落到 `docs/specs/im/agent-work.md` 的维护轨迹契约，避免 Work 消费者长期只能从 Gateway 文档发现其结果语义；保留旧 combined 历史轨迹的可读性。

### 本轮限制与收尾

这是设计可兑现性审查；未运行真实模型、隔离真栈、迁移或生产验证。作者已报告 docs-check 通过，本 reviewer 不把该结果当作运行证据。只新增本报告，受审七个文件 SHA-256 在报告完成时复核均未变化，`git diff --check` 无输出；完成本轮既定覆盖后停止探索。

### Author Resolutions

- **R1-W1 — accepted。** `DescendantReader.observe` 已有第二次屏障，确认不是假想竞态。design 的可复用能力、§4 freeze 顺序与 W1 已明确固定 observation 后认证同一 cut，认证失败不得导出/推进；冷持久源用其 revision，不加前台整轮锁。
- **R1-W2 — accepted。** 保持 `skill_creation` 当前硬依赖为 skill_manage/skill/read；skill-creator 随包安装、按既有 Skill 选择发现，不设为新增必选依赖。默认发现配置可加载；旧显式 allowlist 未选或 denylist 禁用时不偷偷扩宽、不假称可加载，原创建工具仍可用，用户可通过已有 Skill 列表选择指导。design §2.1、Gateway delta、部署第5步及 W3/W7 对齐；不采用启动时绕过 validator 或使整个节点因缺少可选指导而失败的方案。
- **R1-W3 — accepted。** 已确认 refreshPersonalSources 的遍历确实只含未读来源。design §4 现在从权威来源快照同步所有已知源，成功来源操作、政策/成员事件、启动重连及维护准入/应用走同一入口；以 policy revision + 完整集合 hash 标识，覆盖不改变 policy revision 的成员变化。资格变化使入口/主题失效，未知派生范围保守待核对；普通主执行承担清理，Dreaming 关闭不阻断，根/child 下次组装和普通读结果标明状态。状态只存来源/文件元信息，不建语义事实库。新增 PA delta，更新 personal-security 指导及 W2/W4 证据要求。
- **R1-R1 — accepted。** 修正 spec 澄清记录中附件原意为“独立 Skill 维护”；用户原话和最新暂停结论不变。
- **R1-R2 — accepted。** 新增 `specs/im/agent-work.md`，把独立 Dreaming 用途、宿主回执、安静完成及历史 combined 可读性落到 Work 的对应 canonical target。
- 其他小范围消歧：design 明确文件版本清单由脏路径与工具回执更新，启动/恢复或 watcher 失效才做有界全量核对，避免把“每请求检查版本”误实作为每请求遍历全库；符合原输入的无变化复用要求。原型及视觉契约未变化。

## Round 2

### Metadata

- reviewer: `/root/design_review_676`（与 R1 相同的独立 reviewer）
- target: `docs/changes/feat-676-role-memory-dreaming`
- review_mode: `full`
- mode_reason: 修订不仅关闭旧问题，还细化 Node–runtime 来源同步、根/child 消费失效与恢复，新增 PA/Work canonical delta，并调整 M1 退出标准；因此按 full 检查组合关系。对未变化的基线和原型复用 R1 有效证据，不重复运行相同浏览器操作。
- started_at: `2026-10-29T00:40:52+08:00`
- completed_at: `2026-10-29T00:43:32+08:00`
- duration: `00:02:40`
- checkout: 主仓 `main`，HEAD 仍为 `0ddceacb8dac5c5c6f38e2db45e0b72c26cbf3ec`；待审产物未提交。
- authorization: 只追加本报告；未改设计、代码或 current specs，未提交、实施或部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2、R1-W3 在设计层全部关闭，未发现本轮新增的实质问题。方案可以进入后续实施阶段的既定流程；本结论不代表实现、迁移或真实模型验收已经完成，也不增加本轮实施或部署授权。

### Coverage 与证据

**需求、用户约束和现状。** 重新核对完整 design、修订后的 spec 澄清、四份 delta、部署提示词及 M1。默认 document/Dreaming、内置记忆不可经 UI 关闭、文件级 legacy、旧文件逐字备份、暂停自动 Skill 自进化、前台 Skill 能力与显式选择保持，均未在修订中改变。S01–S20 的覆盖仍在 M1 R1–R5/W1–W7，新增闭环场景没有挤掉原验收。`spec.md:37` 已准确区分附件原意与用户后续调整。

**生产组装与来源边界。** 本轮重读 `apps/im-server/src/personal-agent.ts:21–23,40–71`，确认 `pa.sources` 返回完整 policy 与当前可访问来源，已消费来源并不因 Inbox 消费消失；不可访问的已知来源可以通过“不在允许集合”识别。`packages/personal-assistant/src/global-agent.ts:356–395` 已有政策/成员事件恢复、刷新、follow-up 和处理确认链，可承接设计的同步入口。新的 `knowledge.sources.sync` 由 PA/Node 供给可信来源元信息，DSH 仍只由 dsh-integration 使用，未新增跨包私有访问。以集合 hash 补充 policy revision 能覆盖不修改排除政策的成员变化；每主体串行、失败不确认事件、恢复先待核对等规则与现有重放机制一致。

**Agent Context Review — Design Review。** 本轮重点检查 Skill 可发现/加载，持久历史导出，来源变化后的入口、正文、已读历史与 child，普通文件读取提醒及 checkpoint 恢复。修订后既有字节保留与当前知识有效性明确分开；未知派生范围采用导航及待核对状态，相关任务按需核对有效来源后恢复，不靠静默删除或模型“应该记得撤销”。普通主执行承担清理，关闭 Dreaming 不关闭纠正；暂停/失败持久保留待核对，include 不解除另行登记的停止使用意图。控制状态只存 path/hash/generation 等元信息，没有引入语义事实权威。文件脏路径/watcher 的选择减少正常请求全库扫描，S07 的保存后及时采用仍是退出标准；本轮没有运行 watcher 或模型，不宣称该时序已实现。

**架构、部署与 delta。** 原有 MemoryDocuments、MemorySources、KnowledgeRuntime、Work 分工继续成立。来源同步新增的是实际缺失的资格边界；文档失效和 checkpoint 为 S20 服务，没有新建通用任务框架或全库语义依赖图。PA delta 以 REMOVED+ADDED 明确替换原“仅改变未来访问”Requirement，保留两个原 Scenario，并增加文档记忆停止采用及重新允许语义。Work delta 保留并行/嵌套与历史 combined 可读性，区分独立 Dreaming 和旧 fork，补宿主确定性回执；canonical target 正确。部署第 5 步与 Skill 可选指导一致，其余备份、固定基线、模式排他和有限生产核对保持 R1 结论。

**retained_from: Round 1。** HEAD 未变；原型 HTML、prototype-review、IM agents-nodes delta 的 SHA-256 与 R1 完全一致，UI must-match 和验收平台未变。R1 独立看图与 Chrome 操作的体验证据仍有效，无需重开原型走查；本轮未新做 UI/iOS 实测。DSH 公共 API、文件原子版本操作、角色主体归属、维护生命周期、部分保存/Git 区分和模型证据边界沿用 R1，已与本轮新失效链一起核对，没有冲突。

### 历史问题闭环

| Issue | Author Resolution | 本轮独立证据与判断 | 状态 |
| --- | --- | --- | --- |
| R1-W1 | 固定 observation 后二次 flush 认证同一 cut | `design.md:33,148–150` 固定 cursor/events 后认证，不读取认证后的新 live 数组，失败不导出/推进；与现有 `descendants.ts:146–160` 一致。M1 W1 增加首次 flush 后追加及第二次认证失败/重启测试。足以指导实施，无需前台整轮锁。 | **closed** |
| R1-W2 | skill-creator 改为可选随包指导，不增加 Feature 硬依赖 | `design.md:121`、Gateway delta“开启 Feature 展开完整依赖”、部署第 5 步采用同一规则。重新用当前真实 validator 验证旧 allowlist 缺少该 Skill、denylist 明确禁用该 Skill 两类配置，结果均为 `blocks: []`；未绕过校验或改名单。M1 W3 明列升级/启动/保存与真实发现加载证据。 | **closed** |
| R1-W3 | 权威完整来源同步，并联动当前文档/入口及主 child 消费 | `design.md:164–168,176,186,203` 明确完整资格快照、来源 ID 注册、事件与直接操作/重连/freezing/applying 刷新、同 revision 集合变化、持久待核对及 checkpoint 的 generation 校验。核对 IM `sources()` 和 PA 事件链后确认有实际接线落点，不再依赖未读队列。PA delta 和 M1 W2/W4 纳入全部已消费、关闭 Dreaming、同步失败与重启的消费证据。 | **closed** |
| R1-R1 | 纠正附件历史概述 | `spec.md:37` 已改为原先保留“独立 Skill 维护”，后续用户原话和最新暂停范围保留。 | **closed** |
| R1-R2 | 新增 Work canonical delta | `specs/im/agent-work.md` 完整保留原 Scenario，并区分宿主确定性回执、独立维护、安静完成与历史 fork。 | **closed** |

W2 的 validator 探针只证明本轮选定依赖规则不会产生 R1 的确定性配置拒绝；并不证明产品已安装或加载 skill-creator。W1/W3 的关闭是可兑现设计与验证计划闭合，真实模型、故障恢复和来源撤销消费仍必须在 M1 完成。

### 受审产物指纹（SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| spec.md | `12e1f1460f6ef39647b635b8e58dd85f6491c8ed98ea396dd649ce0db82d179c` |
| design.md | `f1fd0d727c699876b95c71cd1f3a1b7b3ebddb38b8be22359ceebb732eef450a` |
| specs/gateway/agent-capabilities.md | `0ea6bd58b7482ead46dc1880d23efdf9ccfda7abf0cbf7beb8ba162669bb0e9e` |
| specs/gateway/personal-agent.md | `e30bbfef6c9ff369955b964fa0e87fb0f824a062e1893f582cb671b6246fccb0` |
| specs/im/agents-nodes.md | `a6e2c9b2cc7d1774e5a01dddc23d3a6bc445b93f2f10425ce2e4428350a598ce` |
| specs/im/agent-work.md | `f6883f417eac823e84fa992274bdd7cf3af75982cc89cb353391e7dbe6357a49` |
| deployment-prompt.md | `a15cfa2f83ae0d52b25116e67dcf9bff747cfe8d9f34aca57281cf33dba95801` |
| prototype.html | `ae2c3fd0075da34ed281694fea0e0762eb72fd8877bfbf5d10d0d976fb16d335` |
| prototype-review.md | `eeea5abdcf00e7b4f70daf1a70a2f52d080cd2a018445e258ec49103a2fafdd2` |

### Issues

无新增 issue；无未关闭 CRITICAL/WARNING。

### Recommendations

无新增建议。本轮到此停止，不因未实现而要求额外设计机制。

### 本轮收尾

只追加本报告，保留 R1 与 Author Resolutions 原文。受审九个文件的 SHA-256 在收尾复核均未变化。未运行目标实现、真实模型、迁移或生产验收；`git diff --check` 无输出。

### Author Resolutions

- 接受 R2 Approved 结论，复核 R1 三项问题的设计修订与证据，无实质异议、无待升级的产品决定。受审九个文件在交付前保持原 hash。
- 归档格式整理：仅将空 `.gitkeep` 骨架从 `milestones/M1/` 移到仓库 Full 标准目录 `M1-role-memory-dreaming/`。单一 M1 范围、依赖和退出标准未变；按 review-loop 的纯格式 retained 规则保留 R2，不重开审查。
- 原型截图保存在本 unit 的 gitignored `evidence/`，按仓库 evidence 规则只提交原型、文字结论和本地定位，不提交截图缓存。设计与原型通过不代表 S01–S20 已运行。

## Round 3

### Metadata

- reviewer: `/root/design_review_676`（独立 reviewer，与 R1/R2 相同）
- target: `docs/changes/feat-676-role-memory-dreaming`
- review_mode: `full`
- mode_reason: 用户把 skill-creator 从可选指导改为固定内置，改变需求、Skill 选择/加载契约、配置归一化与 M1；检查这些组合关系，并保留未受影响的 R2 证据。
- started_at: `2026-10-29T00:56:51+08:00`
- completed_at: `2026-10-29T01:00:25+08:00`
- duration: `00:03:34`
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`，HEAD `0099cdbe2e8bb3de08550086ce238d5ee1c083dd`。R2 产物已提交，本轮七个受审文件为未提交修订。
- authorization: 仅追加本报告；不实施、不提交、不部署。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

新设计已一致表达用户最新决定：skill-creator 固定内置，无 Feature/Skill 选择项；旧 false/allowlist/denylist 不隐藏该指导，底层工具权限仍有效，后台自动 Skill 维护继续暂停。R2 的“可选指导、遵守该名禁用选择”已被本轮明确新需求取代，不再作为实施目标。

### Coverage 与证据

**需求与决定。** 阅读本轮 spec/design/deployment、Gateway capabilities 和 IM agents-nodes delta 的完整 diff，核对 `spec.md` 澄清原话与 S17。移除技能创建行而不补固定开启卡片符合用户指向的具体控件；没有把这次选择扩为所有 Skill 固定可用，也没有把指导可发现等同于自动授予文件或发布权限。旧内容备份、默认文档记忆、Dreaming 可关闭、legacy 文件回退和 F3/F4/combined Skill 停接保持不变。

**真实发现与加载落点。** 独立核对 `packages/dsh-integration/src/capabilities.ts:84–91,137–155`：当前设置候选直接枚举 native provider，实际模型的 list 与 get 均做用户选择过滤。仅从 UI 隐藏名字或给 list 补一条假描述都不足以兑现固定指导。`design.md:121–125` 现已明确宿主解析固定保留真实随包资产、模型可发现并可按需加载、UI candidates 不列该名、同名用户目录不覆盖；这同时约束 list/get 和候选投影，未留下“目录有名字但无法读取正文”的设计歧义。

`apps/node/src/configuration.ts:95–104` 现有 workspace-first roots 和 `packages/personal-assistant/src/builtin-skills.ts` 的随包安装证实需要区分固定资产与一般用户根的优先级；设计采用单一资产特例，复用 native 文件解析/资源加载，不另造 Skill 系统。固定规则只用于正常任务 setup，独立 Dreaming setup 明确不加载；普通 child 继续按已有工具范围返回建议，不因此获得共享发布权。

**Feature、配置和权限。** `packages/product-contracts/src/capabilities.ts:28–35` 当前仍定义 skill_creation；`agent-config.ts:108,118,178` 分别承担工具独立注册、prompt 过滤与 Feature 挂载；`features/skill-creation.ts` 的 apply 同时订阅后台复盘并添加指导。新 design 明确移除 Feature/依赖联动/prompt 关闭条件，正常 root 保留短指导，后台订阅不接回，真实工具仍独立受选择和审批控制。这是对现有职责的可执行拆分，不是把旧 apply 无条件挂载而意外恢复复盘。

`design.md:123` 和 deployment 第 5 步约束旧 false、缺少该名的 allowlist、含该名的 denylist，同步覆盖一次性迁移与正常保存/启动解析；只清理退役键和这个固定资产的陈旧选择，其余名单、模式和工具保留。移除 Feature 必需依赖不会重现 R1-W2 的新增硬依赖拒绝；本轮没有把旧 validator 的结果冒充目标配置归一化已实现。M1 W3 增加固定发现、真实加载及配置往返，W4 继续核对实际模型请求和禁用工具，W6 对齐双宽度/UI 无开关，范围充分。

**Agent Context Review — Design Review。** 检查正常 root 的短指导、按需完整正文/资源、同名解析、当前会话配置刷新与普通 child/Dreaming 组合。宿主固定发现不要求每轮注入全文，维持渐进加载；实际 skill/read/skill_manage 禁用时如实说明限制，不用“内置”恢复权限。旧 Feature false 不再抑制指导，Dreaming 仍无创建工具和对应 Skill，当前设计没有相互矛盾的操作指示。仍需 M1 的请求捕获与真实任务证明实际加载及创建结果；本轮只确认设计链路闭合。

**原型独立判断。** 本 reviewer 实际打开 `evidence/prototype-r3-desktop.png` 和 `evidence/prototype-r3-mobile.png`：技能创建整行已移除，没有空行、禁用开关或固定开启替代卡；桌面 Dreaming 与 Cron 并列，390 宽单列说明完整，内容顺序保持清晰。随后 Chrome 实际打开当前 `prototype.html`，取消 Dreaming，观察“有未保存的更改”，点击保存后看到“配置已生效”且取消选择保持。保存 JS 未改变，R1 的失败/pending 反馈证据仍可复用。旧截图明确标为历史，不能继续作为当前含技能创建行的 must-match；iOS 简单设置项删除仍按既定编译/共享契约深度，不宣称已实测。

**delta、部署与整体架构。** 两份本轮 delta 与新默认能力一致，其余 Scenario 保留。部署提示词清理旧选择而不扩大工具权限，目标解析可读取未转换旧配置，避免依赖一次性脚本才可启动；生产检查仍有限，未把功能/失败分支推迟到上线。实现 owner 仍为 Node 配置、dsh-integration Skills/Prompt 及 IM capability 投影，依赖方向不变；移除废弃 Feature 减少重复开关，没有增加通用配置框架。

**retained_from: Round 2。** 从 R2 的代码基线 `0ddceacb8…` 到本轮 HEAD 仅提交 unit 文档；实际 runtime、Node、PA 与 product-contracts 代码无变化。本轮 git diff 仅涉及固定 skill-creator 及原型行移除。R2 对历史 cut 二次认证、来源完整快照/文档失效、普通文件版本回执、角色归属、恢复与 Work 的独立判断保持有效；S01–S20 的原证据要求及单一 M1 未被删减。PA/Work delta 未变，不重做同一链路取证。

### 历史问题闭环

| Issue | 本轮状态与依据 |
| --- | --- |
| R1-W1 | **closed，retained_from R2**；固定 cut 认证未改。 |
| R1-W2 | **closed**；R2 的可选方案被用户最新要求取代，但新方案移除 skill_creation Feature，而非新增依赖；标准解析与迁移明确归一化废弃选择，并保留真实工具权限。未复现原“旧合法配置因新必需 Skill 被拒绝”的设计矛盾。 |
| R1-W3 | **closed，retained_from R2**；完整来源同步、当前文档/入口失效与主/child 消费未改。 |
| R1-R1、R1-R2 | **closed，retained_from R2**；历史概述与 Work delta 不受本次变更影响。 |

### 受审产物指纹（SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| spec.md | `9fe8004204b31c0f592a5e9ec75934907a27e906c835c99c7643525c86ef3b9a` |
| design.md | `671f7ee86620b73b5332cc67a3557b572b2b837ab9008f5ae13c41fee48378b2` |
| deployment-prompt.md | `2467a1adb0d2c70454e180511a3d21b545ea17ea6a62e9a5f01f812f78103106` |
| specs/gateway/agent-capabilities.md | `a7e2425b1de362b37513e5cbf796e65ca146a009c3f220d89ee856ecb780e0ea` |
| specs/im/agents-nodes.md | `cbaf2717a60c9bd8e8b6f06d9221b30f0fb0cd8797cfe252bc54067b468e2c04` |
| prototype.html | `91289b73ee8b617b105a0723cdd15361ac6735903cb96da64d875cc6bcfcbaf8` |
| prototype-review.md | `449b3acc10012d78acf167eb83d9e24cc5e9441a4d469ec98c62d35dd312730e` |

### Issues

无新增设计 issue；0 CRITICAL / 0 WARNING。

### Recommendations 与文档收尾

- **R3-R1（非阻断，格式收尾）**：作者报告本轮 docs-check 将 prototype-review 中 gitignored PNG 的 Markdown 链接判为 `BROKEN_LINK`。本 reviewer 已实际读取本地截图，设计证据存在；按仓库产物规则把这些链接改为明确的本地 locator、保持画面/结论不变，并重新运行 docs-check。此类 locator 格式调整可记录 retained，无须新增实质设计 Round。当前不能报告 docs-check 已通过。

### 本轮收尾

仅追加本报告，保留 R1/R2 原文；受审七文件收尾 SHA-256 复核未变。`git diff --check` 无输出；未实施、提交、迁移或部署。未运行新实现、真实模型、完整产品验收或 iOS；Gate 2 通过不替代这些后续退出标准。

### Author Resolutions

- 接受 R3 Approved，用户最新的默认内置、无需选择已覆盖前两轮可选指导设计，无实质异议。
- **R3-R1 — accepted。** prototype-review 的7个截图链接改为纯文本本地 locator，图像、路径、走查结论和原型不变；格式调整后的文件 SHA-256 为 `8747d438c3d7d2e15a1dd851c8e5ba9f826f2107edaf152b897e7ffafdf8be98`。其余6个受审产物仍匹配 R3 hash，按 retained 规则不重开审查。
- 将此前 R2 的 Author Resolutions 归回 R2 末尾，原文未改；本轮只修订设计文档和原型，没有实施或部署。


## Round 4

### Metadata

- reviewer: `/root/dreaming_design_revision_review`（新的独立 reviewer；未参与设计编写，不是 R1–R3 reviewer）
- target: `docs/changes/feat-676-role-memory-dreaming`
- review_mode: `full`
- mode_reason: Global 输入、child 摘要生命周期、跨流边界、运行进度、恢复和迁移发生核心变化，且 reviewer 更换；不能仅凭 R3 Approved 继承结论。本轮完整检查新主链，未变化的配置/原型按可核实证据保留。
- started_at: `2026-10-29T13:03:19+08:00`
- completed_at: `2026-10-29T13:05:35+08:00`
- duration: `0:02:16`
- timing_scope: 时间为报告定稿阶段；此前独立阅读、源码与上游核对、截图观察未精确计时，不将此值当作完整审查耗时。
- checkout: 主仓 `/Users/czj/Repos/nano-multiagent`，`main`，HEAD `6b4213c205db04adcebc950fe539a5a759e57391`；受审文档未提交。实现参考为开发 worktree `/Users/czj/.codex/worktrees/unit-feat-676/nano-multiagent`，HEAD `80db8b9a604de15476dceb5e2e9a3c92d5fdf170`，不能以主仓没有新实现判断开发分支能力不存在。
- authorization: 只追加本报告，不修改设计/代码/current specs，不提交或部署。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

新主链、Context 适配和实施退出标准总体闭合；一个可定位的迁移基线错误需要修订：不能把“根流已整合到某时刻”当作“此前 child 历史已整合”的证明。该规则会漏掉旧 document 实例中启用之后、升级之前发生但尚未汇报的任务经历。修订只需调整一次性 child 基线与对应隔离验证，不要求新增兼容运行时或重新设计主流程。

本结论是 Gate 2 设计判断，不是新链路实现/模型行为/迁移已完成的判断。原 PR 实现与旧验收不证明 S21–S26。

### Coverage 与证据

**需求与核心决定。** 阅读 spec 全部澄清及 S01–S26、design 全文、四份 delta、部署提示词和原型 diff。Global 经确定性投影保持交流原文，固定 CycleTarget 后从已完成位置连续分批，保存成功才能推进；两批之间立即续接受资源/本轮预算约束。第一层 child 按可信 session 身份跨窗重提炼，同版复用，新版替换，不喂旧摘要、不给更深层独立摘要。独立整理者合并两路和现有记忆，前台纠正继续即时保存。设计 §4–7、M1 W8–W12 明确撤回逐 step JSON/finish 和阶段增量摘要，并保留失败、无信号、未整合与已保存的区别，覆盖最新用户决定。

**实际组装与公开边界。** 独立读取开发分支 `knowledge/runtime.ts:20,39,56–57,183,200`、`knowledge/dreaming.ts:137–195,228,296–360`、`knowledge/memory-sources.ts:43–73,124–139,185–228` 及 `descendants.ts:97–160`。现有 KnowledgeRuntime 已持有 Dreaming/MemoryDocuments；sources 从业务 bindings 读取 root，旧 child 证据从汇报触发，确实是本次替换落点。DescendantReader 已从原生 catalog 得到可信父子关系，现有 read 会递归，design 明确要求仅选 depth=1、不能全递归导出；无需再造身份注册表。锁定 DSH 公开 `dsh-session/lib/types/types.d.ts:495` 确实有 `SessionEvent.time`，并非依赖私有字段；seq 保持流内顺序、time 只限制跨流上界、无法认证则待办，足以指导实现。live cut 二次持久认证及逐流释放仍保留。

**Agent Context Review — Design Review。** 按提炼者、整理者、前台 root/child 三类 Consumer 检查来源、选择、交付、使用与失效。Global 的 Inbox/conversations 消息在工具载体中仍按真实作者处理，原文和实际送达回执分开；child 的预算选择、未展开标记、两字符串输出/no_signal、更新替换和深层归属明确。整理请求直接包含有界原文与摘要变化目录，不再要求模型拼 JSON 或逐事件交账；背景回查通过本主体登记的 sourceRef、范围/祖先/资格校验，不向模型开放任意 sessionId/path。批次摘要快照、文件版本和 generation 防止在途来源变化被静默复用；失效摘要与缺席摘要语义分开。前台较新更正、no_signal 后仍有其他支撑的旧知识、来源撤销及人工保存分别由现有文档消费规则和新的上游适配约束承接。

新流程没有要求模型填写宿主才知道的 cursor、身份或来源 generation；宿主以实际请求 hash 证明交付，以保存回执证明应用，语义理解由真实模型验证。仍未运行实际请求或模型，不能声称模型已可靠处理一次性要求、授权证据、跨事项关系或较新纠正。迁移阶段的一项选择错误会在模型前排除合法材料，见 R4-W1。

**上游原文与行为保真。** 本地 Codex HEAD 已核实为 `8fdf6472955749a731fd9e4b8ffc218e8e80c51d`。三个模板和 LICENSE/NOTICE 与该 checkout 原件逐字相等，SHA-256 全部匹配快照 README。实际阅读三个模板，并核对 `rollout_input.rs` 的 sanitize、分层近期选择、时序恢复与 extraction_messages，`phase1.rs` 的输出处理，以及 state `memories.rs:860–1020` 的按 thread upsert/no-output 删除与 phase2 通知。design §“上游保真与提示词适配”不是只引用原则：保留请求/纠正、早期未完成工作、单次要求与普遍偏好、授权证据缺失、敏感引用等具体约束，同时明确改动单文件/字节格式及原禁止回查规则的原因。Global 连续原文和受控 read_source 是 Nano 自己的决定，未冒称 Codex 原有能力。W12 要求最终适配 diff、真实请求及行为证据，足以防止实施只按中文摘要重造提示词；此轮没有把研究原件当作运行时资产或指令执行。

**架构与复杂度。** 来源认证/确定性投影仍由 MemorySources 承担，提炼/整理/调度由 Dreaming 承担，文件版本与暂存应用由 MemoryDocuments 承担；PA 只同步完整来源资格、IM 只投影 Work。新增 CycleTarget、每 child 的源版本/整合版本和本批输入快照分别服务固定目标、不重复提炼和崩溃恢复，有实际必要；取消逐 step reviewed 清单减少重复状态。沿既有 storage-domain、AgentHandle、普通 fs 和维护轨迹，没有再造 Agent Loop、全局语义事实库或递归摘要系统。状态无变化不跑模型、共享本轮资源预算、仅短提交锁与 7 天非活动材料清理边界明确，未发现需要额外框架解决的复杂度问题。

**delta、迁移与 M1。** Gateway/PA/IM settings/Work 的 canonical target 正确；MODIFIED 中原有 Scenario 得以保留或按明确退役要求调整。新增 Gateway 三个 Scenario 覆盖原文、child 更新和独立进度，Work 明确提炼/整合/保存/剩余状态。单一 M1 延续文件记忆能力，W8–W12 和 R3/R4 加入新输入链、真实请求、恢复与用户可观察结果；旧报告标为历史，不拿旧 gate 替代新链验收。部署主体权限、目录逐字备份、正常 document 不误搬 legacy、旧 JSON continuation 不当原文 offset、退役旧计划而保留真实保存、重复迁移与回滚保持数据，均明确。生产检查限于备份/状态/服务，功能和失败分支在隔离副本完成；唯一缺陷为存量 child 基线规则（R4-W1）。

**原型独立判断与限制。** 本 reviewer 实际查看 R3 桌面和 390 宽截图：Dreaming 就地显示、说明能解释关闭后的即时记忆能力，桌面并列/窄屏单列自然，技能创建行已消失。与本轮 `git diff prototype.html` 核对，只有底部 Work 演示段落由 18/24 单元改为本批交流、任务复盘与待重试，CSS、布局、设置控件、保存 JS 均未改。原有设置体验可保留 R3 证据；旧 Work 正文不能作为本轮目标。新文字从内容上区分交流、任务复盘、正文保存、入口未同步和版本失败，符合信息语义契约。尝试通过独立 Chrome 标签页打开当前 `file://` 原型被工具的 URL 安全策略拒绝，未绕过、未更改用户页面；故本轮新增回执的实际展开渲染未验证，不声称完成新 UI 实测。这里是既有容器内文案替换，无新布局/交互决定，不将此工具限制单列为产品缺陷；实现阶段 W5/W6 仍需对应真实 Work 与原型检查。

**retained_from: Round 2 / Round 3（有范围的保留）。** 本轮独立重查旧报告、作者 resolutions 及当前内容。PA delta hash 与 R2 相同；IM settings delta 与 R3 相同，prototype-review 与 R3 格式修正 hash 相同。固定 skill-creator、文件工具权限、legacy 排他、源资格同步及当前文档失效在本轮没有改变。开发分支 `global-agent.ts:275–291` 已从完整 pa.sources 快照同步至 `knowledge.sources.sync`，`index.ts:439` 有实际 RPC handler，因此旧 R1-W3 的设计闭环不是仅靠旧 Approved。这些保留仅指仍成立的设计决定与原型观察；实现分支相较 R3 已变化，不继承 R3 的“运行代码未变”断言，也不从旧实现推导新输入链通过。

### 历史问题闭环

| Issue | 本轮证据与状态 |
| --- | --- |
| R1-W1 | **closed**：design §4.1 保留不可变 observation 后二次 flush 同 cut 认证；开发分支 memory-sources 的真实接线和公开 API 已核对。新 child cutoff 同样必须认证，不能把 time 当持久性替代品。 |
| R1-W2 | **closed，retained_from R3**：固定 skill-creator、旧 false/allowlist/denylist 归一化、底层权限保留仍写在 §2.1 及部署第 5 步，没有重新引入必选 Feature 拒绝旧配置。 |
| R1-W3 | **closed**：完整资格快照、普通执行清理、关闭 Dreaming 仍失效的设计保留；已独立核实开发分支的完整来源 RPC 接线。新增 child 缓存也接受 generation 与来源撤销。 |
| R1-R1、R1-R2 | **closed**：历史原话与当前决定分开，Work delta 已存在且本轮更新两阶段回执。 |
| R3-R1 | **closed**：prototype-review 使用纯文本本地 locator，hash 与作者格式修正一致，截图仍可读取；不声称本轮已运行全量 docs-check。 |

### Issues

#### R4-W1 — 旧 document 升级不能以已整合根 cursor 建立 child 已处理基线

- severity: **WARNING**
- evidence: **CONFIRMED**（可由规则与真实旧接线确定的漏选机制；未在生产执行迁移，不声称已有用户数据丢失）。
- 位置：`deployment-prompt.md:46`；关联 `design.md:189–201`（§4.3）、`design.md:347`（W9/W11），spec S22/S25。
- Context Surface：child 原始历史的选择下界 → 首次提炼请求 → 后续摘要替换。
- expected：存量 document 主体启用后的合格任务经历，包括 child 独自推进且尚未汇报到 Global 的内容，能够进入新提炼链；启用前历史不自动回溯。根与 child 进度独立，根完成不等于 child 完成。
- observed：部署步骤 4 指定“建立升级时 child 基线为已整合根 cursor 对应时间的安全位置”。而真实旧实现 `memory-sources.ts:58–70` 只推进 root；`124–139` 仅在 agent-message/subagent-settled 到达 root 时调用 childEvidence，`185–208` 只抽取其工具证据。旧根已整合到 T 不能证明 child 在 T 之前的 own-history 已交付/整合。
- 可成立场景：主体启用于 T0；child A 在 T1 获得任务中的关键约束或失败结果，尚未向根汇报；Global 因其他聊天继续到 T2 并完成旧 Dreaming（T0 < T1 < T2）。升级把 A 的提炼下界置为 T2，A 的 T1 材料不进入首次请求，后续更新仍从该新基线重提炼，无法补回。即使 A 曾报告，旧代码只补工具证据也不足以证明所有 child 请求/纠正已被审阅。
- impact：新模型没有机会理解被宿主排除的经历，可能持续缺少约束、返工原因或未报告结果；将根处理进度当作任务经历处理进度，违反本轮明确的独立更新语义。仅检查 child cutoff 时间合法、或缓存从空开始，不能发现这一遗漏。
- recommendation：一次性升级保留/重建原 document 启用 cut 对应的 child 安全基线；原启用后创建的 child 从 own-history 起点读取。首次重提炼可以与当前记忆按稳定来源合并，不必把已读 root 重跑；如真有逐 child 的旧覆盖证明，可据实际证据采用更晚边界，不能仅按 root cursor 推断。没有可证启用边界则如设计已有规则保留待核对，禁止静默跳过。W11 增加上述“旧根已推进、child 在启用后产生未报告材料”的隔离迁移场景，断言该材料进入新提炼请求、无超范围回溯，且重复迁移不重置新进度。无需新增长期双协议分支。

### Recommendations

无新增可选建议。不要因本轮新模型行为尚未运行而添加设计机制；完成 R4-W1 的具体迁移修订及复验即可重新判断 Gate 2。

### 受审产物指纹（SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| spec.md | `ffa98061f183bef00c3a274b0a0dd84c4cad42f1ae13bbfc23a2f65cea92d651` |
| design.md | `6cc6d393114d1ef5560983af1bc2672f6ff8dafe98b1d80d19014c540c846cd8` |
| deployment-prompt.md | `bf32ac1fd28e8b6bfa0cf02beadb3434599073e699d60fa91353b7e213ffd0ce` |
| specs/gateway/agent-capabilities.md | `b566627b963fda391ec415f0fa1c88b2c78b84809397a12c56e5f6515f1509ca` |
| specs/gateway/personal-agent.md | `e30bbfef6c9ff369955b964fa0e87fb0f824a062e1893f582cb671b6246fccb0` |
| specs/im/agents-nodes.md | `cbaf2717a60c9bd8e8b6f06d9221b30f0fb0cd8797cfe252bc54067b468e2c04` |
| specs/im/agent-work.md | `753306934bd4bd4642234f274b19d3f74374b84815d37d315fa944100e2a28a3` |
| prototype.html | `13a01eea170f75e96c96fde5ad087c29e1f42352650f167826d7d340dd5f303c` |
| prototype-review.md | `8747d438c3d7d2e15a1dd851c8e5ba9f826f2107edaf152b897e7ffafdf8be98` |

三个 Codex 模板与 LICENSE/NOTICE 的 hash 均匹配 `input/codex-memory-v2-8fdf647295/README.md`，且已与锁定 checkout 原件逐字核对。

### 本轮收尾

只追加本报告；没有修改受审产物、代码或 current specs，没有提交、迁移、部署或运行真实模型。未启动服务。主仓与开发 worktree 的资料均按其各自 HEAD 解释，旧实施/验收不作为本版通过证据。报告后执行 `git diff --check` 并复核受审指纹。

### 范围追加待审（2026-10-29T13:06:00+08:00）

报告初稿写入后收到用户补充：Global 的用户/人物关系/互动反思也须核对 Muse 原始材料并保真适配，不能只保存 Codex 模板。author 正在补充设计与参考材料；本 Round 4 暂不签结，以上结论仅对应指纹所列版本。收到新范围后由同一 reviewer 在本轮追加复核证据和最终结论，不把初稿视为新增范围已审。

### Author Resolutions（R4 初稿及范围追加）

- **R4-W1 — accepted。** 旧实现仅随根收到报告补 child 工具证据，根 cursor 不能证明所有子经历已整理。部署提示“已有 document 实例”第 4 步已改为原 document 启用 cut 对应的 child 基线；启用后创建的 child 从 own-history 起点读取。边界不可证时保留受阻，绝不默认跳到升级尾部。design M1 W11 增加根已推进而 child 尚未汇报的定向迁移场景、越界回溯和幂等验证。
- 用户新增 Muse 与实际记忆结构要求已并入 spec 原话、design 的“Global 的 Muse 参考与 Nano 内容落点”、M1 W12 和 gateway delta；原始说明在 input/muse-reference-1b6f936124。等待同一 reviewer 对扩展范围及上述修订作最终判断，本段不自行批准 Gate 2。


### Round 4 扩大范围复核与最终结论

- reviewer: `/root/dreaming_design_revision_review`（与本轮初稿相同，持续独立审查）
- review_mode: `full`；本轮内部追加 `delta + closure`，没有另开 Gate 或新 Round。
- scope_reason: 用户在审查中追加 Global 的 Muse 原始材料与现有记忆结构适配要求；同时复核 R4-W1 修订。初稿范围和历史结论保留，上述“暂不签结”状态至此结束。
- completed_at: `2026-10-29T13:11:09+08:00`
- timing_scope: 本轮未累计精确全程耗时；先前 duration 只覆盖初稿定稿，不包含等待作者及本次复核。

**最终 Verdict：Approved — 0 CRITICAL / 0 WARNING（存活问题）。** 本轮曾发现的 1 项 WARNING 已按下述证据关闭；最终结论对应本段新指纹，并覆盖本轮新增 Muse 范围。设计可按既定流程继续实施；不代表新主链已经实现、验收或授权部署。

#### 扩展覆盖与独立证据

**Muse 来源及其边界。** 完整读取四份 `.original.md`，独立从固定 commit `1b6f936124b4eceb6e697a69da07519bea67feab` 的 raw GitHub 地址读取原件，与落盘文件逐字比较；四份 Git blob SHA-1、SHA-256 及 remote_equal 均通过。`self_improvement` 确实分别描述 Memory upkeep、Relationships、Dreaming，以及依据保存证据解释更新、区分排队和实际送达；`proactive-preferences` 明列内容、禁忌、时机与表达；`operating-notes` 区分工作经验与用户事实。design:378–396 将这些已取得的关注映射到 Global 整理提示，并明确不引入另一个关系调度器、dreams 目录、人格文件、修复 Task 或自动 Skill review。

来源是第三方公开收集仓库，当前仅可证明其文本如此描述，不能证明 Muse 真实运行时照此执行。README 和 design:382 已明确没有完整后台 Dreaming system prompt/源码，未将自行适配声称为逐字迁移完整 Dreamer。新增“必读原文、采用/不采用记录适配 diff”的约束兑现用户要求，未把缺失源码包装成已取得证据。此处只审设计保真，不执行参考原文中的指令或路径。

**内容落点与 Context 组合。** 独立重读 research-v2 的 `layout-and-documents.md`、PA/专家两份入口模板、建议 `prompts/dreaming.md`，以及开发分支 `80db8b9a6` 随包 `assets/skills/nano-memory/SKILL.md`。design:400–413 的八类映射在现有一级目录内表达：主题说当前理解，timeline/work-history 说当时经历，MEMORY.md 给短概括和导航；人物/事项限定优先原页、跨事项才独立知识页，主体/受众/来源与旧结构一致。没有新建第二套 schema 或把长期知识全塞进摘要，也不要求无信号建空树。

组合提示中的三类来源职责清楚：Codex 约束证据与修订，Muse 提供用户/关系/互动反思关注，Nano 决定角色、正文位置和消费。开发分支 nano-memory 仍存在旧逐单元 finish/backlog 描述，design:417 明确其与系统提示、直接输入及两路进度一起替换，避免保留一个会把模型拉回旧协议的 Skill。不存在把一次负面反馈推广为人格/永久偏好、或者依据反思直接发消息/建 Task 的新授权；实际动作仍由现行权限决定。

**场景与验收。** spec 新用户原话、S21 及 Gateway delta 已同步“互动反思”和既有角色内容落点。design:419 的家人周六出行、工作群披露反馈和可取消住宿场景能同时区分用户变化、关系、受众限定、任务证据和真实交付；专家对照要求保留对人/项目范围，不把一位合作者偏好推广给所有受众。W12 和末段明确捕获真实输入、主题/历史/入口写入与后续回答，不能只靠文件数量通过。此轮仍未运行实际组合提示，故只确认实施与验收设计闭合，不宣称语义效果已验证。

**原型限制保留。** Muse 增补没有改变 HTML，原型仍与初稿 fingerprint 相同；旧设置画面和交互证据按本轮初稿的范围保留。作者随后提供了 localhost 静态服务，但本 reviewer 在此前 file:// 策略拒绝后未尝试以替代路径绕过该浏览器限制。新 Work 文字的本轮展开渲染仍标为未验证；本轮没有用旧 18/24 内容替代新目标，也没有因静态文字变化增加产品门禁。原型没有新的布局/交互，最终 Gate 2 判断依据该有限差异、已独立看过的容器画面和明确的 W5/W6 后续检查范围。

#### R4-W1 闭环

- Author Resolution：接受问题，child 首次下界改为原 document 启用 cut；启用后创建的 child 从 own-history 起点；根游标不证明 child 已整合，缺少边界只阻塞该源。
- 本轮独立证据：`deployment-prompt.md:46` 已明确上述规则，并保留来源资格、停止使用范围、当前文档合并及不越过启用前边界；`design.md:347` W11 加入“根已推进而启用后 child 尚未汇报”的材料必须进入首次提炼请求、无越界及重复迁移不重置新进度。
- 判断：**closed**。原可成立场景中 T1 的 child 材料仍位于原启用基线之后，升级不会再以 T2 根进度将其排除；重复语义由当前文档/稳定来源合并处理，无需牺牲历史覆盖。无需新增长期兼容读取器。这里只关闭错误的设计选择，迁移实测仍属于隔离 M1。

#### 最终受审指纹（SHA-256）

| 文件 | SHA-256 |
| --- | --- |
| spec.md | `ccb128abce22062ab3cd26f034a16231a8447a46df0b00b25cf67948c138e05c` |
| design.md | `db3e9babe2d8d2efb77560a449a3f3dfb9078dadddb08e0c846d5cd4cb422f17` |
| deployment-prompt.md | `19423df61ece336b5f29da7482871d7b8fbd3bd04ac119cf5f420efb4d50cb5b` |
| specs/gateway/agent-capabilities.md | `f1cf90e82dc8bbc0b3e12dbc923132a0f80c6464145953f311b5b9136ead9452` |
| specs/gateway/personal-agent.md | `e30bbfef6c9ff369955b964fa0e87fb0f824a062e1893f582cb671b6246fccb0` |
| specs/im/agents-nodes.md | `cbaf2717a60c9bd8e8b6f06d9221b30f0fb0cd8797cfe252bc54067b468e2c04` |
| specs/im/agent-work.md | `753306934bd4bd4642234f274b19d3f74374b84815d37d315fa944100e2a28a3` |
| prototype.html | `13a01eea170f75e96c96fde5ad087c29e1f42352650f167826d7d340dd5f303c` |
| prototype-review.md | `8747d438c3d7d2e15a1dd851c8e5ba9f826f2107edaf152b897e7ffafdf8be98` |
| input/muse-reference-1b6f936124/README.md | `af865f542c7a86cbb86888434fbfb850208f2aebb51572285ad0866135eb116f` |

Muse 四份原始文件均匹配其 README 中完整 hash，且本 reviewer 独立核对固定版本远端字节；Codex 原始模板及许可文件未改，保留本轮初稿核验。

#### 最终收尾

只追加审查报告，保留 R1–R3、本轮初稿和 Author Resolutions。受审设计、规范、原型、源代码和上游快照未由 reviewer 修改；未提交、实施、迁移或部署。`git diff --check` 通过，最终指纹再核对。无存活 CRITICAL/WARNING，无新增可选建议；到此停止复审，不继续追查假想边界。

### Author Resolutions（R4 最终收口）

- 接受 R4 最终 Approved，0 CRITICAL / 0 WARNING；R4-W1 已关闭，Muse 原件与 Nano 内容映射已独立复核，无实质异议。
- 最终受审文件 hash 再核对一致；只追加本段收尾，不修改已审设计。`PYTHON=.venv/bin/python ./scripts/docs-check` 通过（322 maintained Markdown sources / 68 required routes）。作者文档 diff 格式检查通过；Muse memory 原件保留上游四处 Markdown 硬换行空格，Git blob 逐字节一致，不为消除格式提示改写原件。
- 原型仅底部 Work 示例文字变化，新增文案的实际浏览器渲染未验证，保留报告的准确边界；新实现、真实模型和 S21–S26 验收尚未执行。旧 PR #428 已转 draft，下一次实施须先同步本版设计并重做受影响验证；不因本次 Gate 2 通过恢复为可合并状态。
