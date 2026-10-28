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
