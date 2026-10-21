# feat-627 Design Review

## Round 1

### Metadata

- reviewer: `/root/design627_review`（独立于 author）
- reviewer target: `spec.md`、`design.md`、`prompt-baseline.md`、`specs/gateway/agent-capabilities.md`、`M1-agent-context/.gitkeep`
- review_mode: `full`
- mode_reason: 首轮，无历史审查；覆盖需求、公开接口、实际产品组装入口、数据与时序、delta、milestone 和 runbook。
- started_at: `2026-10-21T10:42:27+08:00`
- completed_at: `2026-10-21T10:44:03+08:00`
- duration: `PT1M36S`（首个记录到绝对时间的核对至结论收口；之前的只读取证未计，非全部审查耗时）
- checkout: Nano `main@37a4c2acb96654f8a539821069268dad31579eac`，受审文档为当前 working tree；仓库有既有 staged/dirty/untracked，本 reviewer 仅新增本报告。
- source baselines: fork `d74876a90968bd5498b5af0bcc2f327c3131f007`；DSH `5badb15009ae1756c3afe0ae0cef1faafc290ccc`；Codex `464add49587a7cb6032d5ab04faa8a1585947853`，均已核对本地 HEAD。Nano 依赖仍为 `0.2.1-alpha.1`。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

总体职责拆分、独立固定版本包、复用原生日志与 compaction 事务的路线成立；需先修正实际 scoped 加载方案、正常换窗时未提交 runtime snapshot 的处理，以及 fallback 提示的内部冲突。上述都是已存在代码路径或受审文本的直接冲突，不要求新增框架、扩大产品范围或提前实现。

### Coverage 与证据

| 范围 | 独立核对与判断 |
|---|---|
| 需求与用户约束 | `spec.md:73-137` 的五类场景均有设计与 M1 验收承接：连续至少三次换窗、后续纠正、长结果后半段、恢复缺失、正常重启、权限边界、启停/失败。命名、固定 release 包、不用子仓、不升级/patch DSH、尽量保留 Codex 原文均有明确决定。当前仅设计，无实现/发布/部署结论。 |
| Nano 真实接线 | `packages/dsh-integration/src/index.ts:260` 注册实际 Agent preset；`agent-config.ts:99-127` 在该 preset 接入 workspace extensions；`workspace-tools.ts:58-89,121-139,165-211` 负责本地 profile、scoped tree、加载审计与工具发现；`compaction.ts:17-23` 将自动/人工 compaction 所有权交给 preset。没有仅依据 fixture 推断上线接线。包行尚有 R1-W1。 |
| 生命周期与发布 | DSH `packages/boot/plugin-manager/src/install-spec.ts:74-82` 接受 HTTP tarball；Nano `workspace-tools.ts:218-221,276-281` 的 localSource 确实按目录处理。独立预构建 tgz、固定 URL/digest、版本替换遵循 restart-required、停用不删除日志/Notes、回退不恢复旧活动 surface，边界合理。Release 地址明确标为未发布目标。 |
| 公开 API 与事务 | DSH `packages/core/agent/src/runtime-types.ts:309-320` 公开 pre-step 的 messages 决策；system-prompt 公开 section/context/assemble，session/compaction 提供原生持久 bracket 与 surface 操作。fork `src/rollover.ts:219-315` 已使用完整事务、配对与严格缩短约束，可在 fork 修改而无需导入 private projection。正常请求的待提交 snapshot 存在 R1-W2；overflow 分支明确要求显式重建和只在缩短后 retry。 |
| 数据与稳定引用 | `design.md:69-100,111` 对 Notes 的 session namespace、路径边界、分页、长行接续、原样 append、大小限制和读后可见性有明确契约；History 只开放离开 surface 的正文，保留 tool-call/result、Nano source 和 Inbox 嵌套来源。当前引用通过持久事件 seq、成功 bracket 起点形成，失败事务不生成窗口；未持久结果不承诺 ID。没有新增全量历史数据库或跨 Agent 查询面。DSH Agent/session 使用同一持久 identity（`agent-loop/src/index.ts:640-653`），按执行 session 隔离可以实现重启恢复；它不等同于 Nano 产品配置中的 Agent ID，展示名称须避免混淆，但不影响此隔离方案。 |
| 预算与提示词 | `design.md:113-122` 按 window 管理一次 reminder/fallback，保留硬上限、供应商 overflow 与无进展终止；参数不是照搬某个模型。直接解析 Codex `models-manager/models.json`，确认 models[0] 为 gpt-6-astra、enabled/use_history_notes_extension 均 false；guidance/reminder/fallback 原文在附录逐字存在。Notes/History 描述与动作字面量核对 `ext/history-notes/src/tools.rs:27-29,111-140`。fallback 适配有 R1-W3；测量依赖持久 surface 的实施注意项见 R1-R2。 |
| Delta | `specs/gateway/agent-capabilities.md` 只 ADDED 两个 requirement，canonical target 正确，未以 MODIFIED 丢失既有 scenario；客户端无改动，no IM delta 合理。生命周期一句措辞可澄清，见 R1-R3。current specs 未被覆盖。 |
| Milestone 与 runbook | 单个 `M1-agent-context` 骨架存在，退出标准同时绑定 fork commit/版本/hash、Nano 接入及真实任务证据；两仓分别 PR 不要求把源码纳入 Nano。真栈从用户消息经过 PA 到实际回复；至少三窗含后续纠正、长结果尾部及一次受控副作用；正常 restart 保留 state，禁用/其他 workspace/加载失败/清理均有观察点。fixture 与真实压力路径证据分开，未用服务健康代替用户接受。没有客户端变更，不要求 UI 原型。设计审查未启动 E2E 或声称这些验收已通过。 |

**架构判断：** 上下文策略、Notes/History、预算与 fork 包由插件负责；Nano 继续只负责产品来源、权限和 workspace 生命周期，方向正确。复用 DSH session 日志、公开 compaction、scoped loader 足以承载需求，新增 ID 数据库、第二套执行 loop 或 Nano 专用上下文框架均无必要。主要缺口是现有机制的具体装配和同一步状态所有权，修正它们即可，不要求泛化。

### 历史问题闭环

无历史 Round，本轮首次建立 issue IDs；无 Author Resolution 可核验。

### Issues

#### R1-W1 — 唯一 bundle row 未建立 compaction isolate，且未收口上游 model-surface 开关

- **位置：** `design.md:63-67`；关联 `design.md:28-30`。
- **证据：** 设计明确 bundle 只插入 `id/name/config: {}`，不含 isolate。fork 的 `ContextRolloverEngine` 继承 `CompactionEngine`，后者构造器以 `super(ctx, 'compaction')` 发布服务（DSH `packages/compaction/compaction/src/index.ts:119-121`）。真实 Nano loader 在 `workspace-tools.ts:185-205` 检测 root services、标记失败并卸载该行；scope 本身不会创建服务 isolate。DSH `agent-preset-registry/src/mount.ts:59-83,203-213` 同样区分 scope 与 isolate。现有 Nano compaction 集成 fixture 的有效行明确使用 `isolate:{compaction:true}`（`tests/workspace-tools.test.ts:246-267`），与真实 loader 一致。
- **另一项同入口缺口：** fork `src/config.ts:110` 默认 `modelSurface='auto'`，`src/index.ts:126-152` 在存在 agentPresets 时不注册工具/guidance；Nano 正是 preset 部署。设计的 `config:{}` 既没有覆盖该值，也没有明确在 fork 中移除/改变这个 host-only 判断。仅改变包名和工具实现不会自然启用模型入口。
- **未修后果：** 按所列 patch 构造的包不能成为合法的 workspace compaction owner；即使只补 isolate，直接沿用上游注册条件仍可能出现有引擎却没有四个工具和 guidance 的半生效状态，与“安装后通过现有入口工作”不符。
- **修订方向：** 在设计中给出实际可用的 scoped row/group，明确 compaction isolate；同时选择配置 `modelSurface:'always'` 或在 fork 中按当前 scoped owner 正式注册 model surface。保持 host 默认引擎不变，绑定工具/guidance/hooks 与该 scope 的启停；无需改 Nano 通用 loader。

#### R1-W2 — 新 checkpoint 之后仍会提交换窗前生成的 runtime-context snapshot

- **位置：** `design.md:96-98,104-108`。
- **证据：** DSH `agent-loop/src/agent.ts:269-285` 在 pre-step 之前 assemble 并调用 runtimeContext.project，闭包中的 `context` 已包含当时的 `<context_window>` 与 `<context_references>`。默认 `next()` 返回 `[..., context]`。`agent.ts:419-421` 在 pre-step 返回后才逐条 append `decision.messages`。`runtime-context.ts:152-161` 对变化的 contexts 生成完整 snapshot。设计新增引用索引每步跟随最新持久消息变化，因此模型调用 `new_context` 后的下一步通常已经生成一个仍写着旧 Current window id 的 snapshot。
- **未修后果：** pre-step 事务即使先写入带新窗口身份的 checkpoint，也不会取消闭包里的旧 snapshot；旧 snapshot 随后作为较新的 runtime-context 入模。同一新窗第一条请求同时出现新旧两套“当前窗”身份，模型可能保存错误 `(window_id,item_id)`。只依赖“后续 assembly 会重建”不能修正这一次请求，也不能保证重建发生，因为旧 snapshot 又被投影器记为 retained。
- **修订方向：** 明确 pre-step waterfall 对待提交 `decision.messages` 中 loop-owned runtime-context 的处理：成功切窗后剔除/重建旧 snapshot，确保本次请求只有有效的新窗 context，保留全部 claimed 新用户输入和其他合法 notices。公开 `PreStepDecision.messages` 支持此操作，不需要 private import 或修改 frozen request。将“本步 snapshot 已因 references 更新、同一步切窗”的路径列入首次新窗请求断言，并保留 overflow 不经过新 pre-step 的独立处理。

#### R1-W3 — fallback 的 golden 文本同时要求和禁止预算工具

- **位置：** `prompt-baseline.md:95-98,105-108`，对照 `design.md:100,119`。
- **证据：** 适配文本要求 `Before saving a checkpoint, use get_context_remaining ... when needed`，随后又要求恰好一次 Notes 写入，并明确 `do not use any tools other than notes and new_context`。设计正文则已经选择 fallback snapshot 覆盖最新已提交输入/结果，fallback 期间不再要求调用预算工具。
- **未修后果：** 本文被指定为 golden fixture；直接实现会把互斥指导发给预算最紧张的模型，迫使它选择违反调用顺序或额外花费一次工具往返，破坏已收口的“先保存再切窗”路径。
- **修订方向：** 单独适配 fallback 的引用说明，使用已附带的 reference snapshot，去掉此处额外预算调用要求，并同步逐处差异/理由。普通 guidance/reminder 可以保留预算工具提示，不需要重写 Codex 整体文风。

### Recommendations（不阻断）

- **R1-R1：安装工具名称。** `design.md:65` 写 `plugins`，真实 Nano 注册名是 `plugin_manager`（`workspace-tools.ts:75-81`），action 才是 install_bundle 等。改正名称即可，现有入口的总体选择正确。
- **R1-R2：预算测量时点。** DSH `token-meter/src/index.ts:132-167` 测量的是当前持久 surface/请求 header；pre-step 尚未 append claimed 新输入和此次 runtime snapshot。实施应明确 T 的观测时点，避免把该估算称为即将发送请求的精确大小；可利用公开 estimateMessage/header 能力计算本步增量，实际 provider overflow 仍按已设计兜底。现有设计已保留估算来源与溢出分流，不据此要求新增 provider tokenizer 或另建预算服务。
- **R1-R3：delta 的停用条件。** delta `正常重启与重新启用` 的 THEN 末尾“未来工作恢复默认上下文管理行为”应明确仅指停用期间，避免从同一段读出“重新启用后也使用默认引擎”。design 的启停意图已清楚，这是局部措辞澄清。

本报告只确认静态设计与当前源码关系；未运行新插件、未发布资产、未修改其他受审文件、未提交。author 修订后可按真实变化选择 closure 或 delta 复审，无需因上述局部缺口重开产品需求。

### Author Resolutions — Round 1

- **R1-W1 accepted**：真实 loader 的 root-service 审计与上游 `registersModelSurface` 证据成立。design“包与生命周期”改为 `isolate: {compaction: true}` + `config: {modelSurface: "always"}`；明确 scope 不代替 isolate、四个工具/guidance 随 row 启停，不修改通用 loader。
- **R1-W2 accepted**：DSH 的 pre-step 闭包确实会在 replacement 后提交预先生成的旧 snapshot。design“新窗事务”第4步明确成功切窗后通过公开 `decision.messages` 剔除本轮 loop-owned 旧 runtime-context 候选，保留所有新用户输入/其他通知；新 checkpoint 负责本次完整有效状态，下一步走原生 projection。增加首次新窗请求的针对性断言；overflow 仍独立处理。
- **R1-W3 accepted**：原 fallback 同时要求/禁止额外预算工具存在真实冲突。prompt-baseline 为 fallback 独立使用 attached references 文本，移除额外查询要求，保留“一次写 Notes → new_context”的原文顺序并补差异理由。
- **R1-R1 accepted**：design 中工具名改为实际 `plugin_manager`。
- **R1-R2 accepted**：design“预算状态机”明确持久 surface 测量时点、待采纳输入/当前 assembly header 的增量估算、不重复计数与 estimated 标记；不引入另一套 tokenizer/预算服务。
- **R1-R3 accepted**：delta 澄清仅停用期间使用默认管理行为，重新启用恢复该换窗能力。

修订范围：design 的包行、公开 pre-step 候选消息处理、预算测量时点，prompt-baseline 的 fallback 引用说明，delta 的一处启停条件。首文档、产品范围与 M1 骨架不变；提请独立 reviewer 按实际影响决定复审范围。

## Round 2

### Metadata

- reviewer: `/root/design627_review`（同一独立 reviewer）
- reviewer target: R1 Author Resolutions、修订后的 `design.md`、`prompt-baseline.md`、`specs/gateway/agent-capabilities.md`；复核原 `spec.md` 的需求映射和 M1/runbook 承接。
- review_mode: `delta`
- mode_reason: 本轮不仅关闭原问题，还具体调整 scoped 装配、pre-step 候选消息处理和本步预算估算，属于有界技术设计变化；因此检查这些变化及相互影响，而非只做文字 closure。产品需求、模块职责、工具公共形态、数据边界和 milestone 未扩大，无需 full 重审。
- started_at: `2026-10-21T10:47:28+08:00`
- completed_at: `2026-10-21T10:47:57+08:00`
- duration: `PT29S`
- retained_from: `Round 1`
- checkout: `main@37a4c2acb96654f8a539821069268dad31579eac`；前述第三方固定源码基线继续适用。本轮仅追加本报告，无实现、提交或运行服务。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2、R1-W3 均已关闭；R1-R1、R1-R2、R1-R3 均已落实。本结论批准修订后的设计进入实施，不代表插件已经实现、发布、安装或通过真实连续任务验收。

### Coverage 与证据

1. **Scoped 装配及生命周期。** `design.md:63-67` 现在明确 `isolate:{compaction:true}` 与 `modelSurface:"always"`，与 Nano `workspace-tools.ts:174-190` 的隔离映射和 root-service 审计一致，也直接满足 fork `src/index.ts:150-152` 的工具注册条件。没有禁用宿主默认 compaction、改写其它 preset 或扩大权限。四个工具、guidance、hooks 与引擎仍随同一 scope 释放，因此 R1 的启停/回退设计继续成立。
2. **首次新窗请求和下一步重建。** `design.md:104-109` 在成功切窗后处理 `await next()` 返回的旧 loop-owned runtime-context，保留新输入/其他 notices，失败路径保持原候选。再次核对 DSH `agent-loop/src/agent.ts:269-285,409-425`：插件得到的正是随后入日志的消息数组；公开 seam 足以解决旧 snapshot 后提交问题。`runtime-context.ts:134-161` 在旧 retained snapshot 被 replacement shadow 后清除 retained，下一次 assembly 可正常生成新 snapshot；设计没有引入第二个 projection 所有者。正常 pre-step 与 overflow retry 的差异仍明确，新增首次新窗真实请求断言已承接到 worker 验证范围。
3. **预算及 fallback 联动。** `design.md:115` 区分持久基数、本次待采纳增量、当前 tools header 和只读工具的测量时点，标为 estimated。DSH `token-meter/src/index.ts:132-156` 公开接受替换 requestHeader，已有 estimateMessage 可用于消息增量，不要求 private API。该改动与“保留未采纳新输入”和 overflow 兜底相容，没有新增 tokenizer、授权旁路或第二套预算 service。fallback 的 attached references 指引保持一次 Notes 写入后 new_context，不再要求额外预算查询。
4. **提示保真与 delta。** 对固定 Codex models.json 再次做字面检查，guidance/reminder/fallback 三段原文仍完整保留；修订 fallback 的适配正文与 diff 一致，专用变更理由位于 `prompt-baseline.md:122-124`。delta 明确停用期间使用默认管理，重新启用恢复该能力，仍为正确 canonical target 的 ADDED requirements。
5. **保留证据。** `retained_from: Round 1`：Notes/History 的命名空间、稳定引用、窗口归属、长片段分页、原始来源、固定包与双仓职责、用户场景覆盖、无客户端变更的判断未受此次修订影响。再次查看 M1/runbook 与 `.gitkeep`：仍要求真实用户→PA→回复的至少三窗任务、最新纠正、长结果尾段、单次副作用、重启及隔离；修订没有削弱退出标准。保留 R1 相应源码与需求映射，不重复运行与本轮设计无关的产品测试。

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核验 | 状态 |
|---|---|---|---|
| R1-W1 | 接受；增加 compaction isolate 和 modelSurface always | `design.md:63` 与真实 loader/上游注册条件一致，作用域所有权及模型入口均收口 | closed |
| R1-W2 | 接受；剔除旧 loop-owned snapshot，保留新输入 | `design.md:107` 明确成功/失败两路径、公开 decision.messages 接缝及首次新窗请求断言；符合 DSH 提交顺序 | closed |
| R1-W3 | 接受；fallback 使用附带引用，取消预算查询 | `prompt-baseline.md:97,109,122-124` 无 get_context_remaining 指令，仍保留恰好一次 Notes→new_context 和工具限制 | closed |
| R1-R1 | 接受；修正安装工具名 | `design.md:65` 为实际 `plugin_manager` | closed |
| R1-R2 | 接受；明确测量时点与增量估算 | `design.md:115` 使用公开估算能力、标记 estimated，保留 overflow 分流 | closed |
| R1-R3 | 接受；限定默认行为仅在停用期间 | delta 的“正常重启与重新启用”区分停用期间与重新启用后行为 | closed |

### Issues

无新增 CRITICAL / WARNING，无 still-open 项。

### Recommendations

无新增建议。后续按现有 M1 验证真实效果即可，不为假想边界继续扩大设计。

### Author Resolutions — Round 2

接受 Approved 结论；复核三项阻断均已按实际公开接口闭合，无待处理实质问题。受审设计、首文档、prompt baseline、delta 与 M1 骨架在本轮后无实质变化。文档校验在干净 HEAD 加本 unit 的快照中为 0 问题；当前工作区全量校验仅保留 6 个既有无关链接问题。当前只交付设计，不将静态审查视为实现或运行验收。

格式收尾：仅移除 prompt-baseline 的 diff 展示块中 3 个空白行上的尾随空格；原文和适配文本不变，R2 结论 retained，不另开实质复审。

## Round 3

### Metadata

- reviewer: `/root/design627_review`（同一独立 reviewer）
- reviewer target: 相对 `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28` 的 `spec.md`、`design.md`、`specs/gateway/agent-capabilities.md`；`prompt-baseline.md` 和此前未改变的恢复协议保留 R2 证据。
- review_mode: `full`（从派发的 delta 扩大）
- mode_reason: 新用户要求把可选 workspace 插件改为全部新旧 Agent 的默认机制，并新增运行依赖、迁移、空白名单例外与无 workspace 分支，已改变需求和产品控制边界；按 reviewer 的 full 触发规则检查所有受影响消费者。未改变的算法/提示词不重新开题，证据明确 retained。
- started_at: `2026-10-21T11:08:30+08:00`
- completed_at: `2026-10-21T11:11:49+08:00`
- duration: `PT3M19S`
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-627`，`unit/feat-627@d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`。只追加此报告，保留测试准备及其他既有修改。
- retained_from: `Round 2`，限于未被本次默认化覆盖的设计与已关闭问题。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

固定 release 包作为 integration 依赖、installation anchor、一次性 profile 默认迁移和原生启停的方向可行。默认化仍缺内部恢复工具的审批决定、现有真白名单契约的 MODIFIED delta，以及首个请求没有预算记录时的 bootstrap 决定。无须新增插件框架、运行时 patch 或迁移数据库。

### Coverage 与证据

| 范围 | 本轮核验与判断 |
|---|---|
| 用户约束与需求 | `spec.md` 已记录用户的“所有 agent 默认”原话，并覆盖新建/升级前已有普通、Global、Personal、子 Agent、空业务 allowlist 和显式停用持久化。独立包、不用子仓、真实长任务验收后交付仍保留。相比 R2 的可选安装，这是一项有意的范围变更。 |
| 包锚点与共用实例 | DSH `app-boot/src/profile.ts:372-422,441-474` 从 installAnchor 的依赖/peer 图 BFS 构造 installation scope，`resolveBundleDir:695-714` 优先 installation 后 profile。integration 直接依赖插件并继续直接依赖当前 DSH/Cordis 包，使设计中的固定版本来源和同一宿主实例有公开承载点。真实路径应从 integration 包位置取得，不能假设该包目前导出了 `./package.json`；这是实现方式选择，不阻断设计。 |
| Manifest 与 lifecycle | 已在本 worktree 的实际 `0.2.1-alpha.1` 安装中解析并动态导入 `@deepseek-ai/dsh-plugin-manager/operations`，确认 `saveManifest` 为函数。其公开实现原子保存完整 manifest，`PluginManager.selectBundle:734-752` 只改选中集合并保留其他字段。因此单次 `nano.agentContextDefaultInitialized` marker 可与原生 set_bundle 共存，之后 bundle 缺席不应再解释为“未初始化”。已有依赖但 deselected 保持停用，旧 patch 原样保留，设计闭合。 |
| Shipped inventory | DSH `plugin-manager/src/index.ts:278-327` 列举 installation.dependencies，`installed` 指 profile 直接依赖，shipped 包 removable=false；开启状态来自 profile.bundles。Nano 当前两处 installed 过滤（`workspace-tools.ts:224,255`）确需按新设计调整为包含该 shipped 包。包解析 installation-first 可避免 profile 同名包替代实际运行版本。 |
| 运行组装与所有 Agent | Nano `index.ts:168-179` 在实际 agent/created 路径 attach 配置/审批；`agent-config.ts` 的 preset attach 和 WorkspaceExtensions 是正确挂载点。无 workspace 分支现在明确直接挂同一 isolated 包，不创建虚假 profile。DSH `subagent/src/child-agent.ts:196-218` 先继承 preset，再叠加子工具限制；普通子任务及 Nano Workflow 的当前 parent-schema 派生工具集能够承接四恢复工具。需分别验证空业务集下的展示与真 dispatch，不能只验注册列表。当前阻断来自审批路径，见 R3-W1。 |
| 工具与授权边界 | 四个固定 session 内部工具成为有限 allowlist 例外是用户默认机制要求的合理实现；停用后注册撤销、其它 workspace 工具不一并获权、业务操作审批仍保留，方向正确。现行审批没有此内部类别，设计不能仅以工具出现证明可用。current spec 的“任何工具均拒绝”也必须同步增量修订，见 R3-W1/W2。 |
| C/O 与时序 | 新增从实际 `request/header.config.maxTokens` 取 O、adapterDefaults 只作来源标记是正确的；但首次 pre-step 早于 prepareCall 与初始 header/context，必须区分尚未观察与真实无合法预算，见 R3-W3。正常换窗清理待提交旧 snapshot 的 R1-W2/R2 修订未被本次改变。 |
| Delta、milestone、runbook | 默认生效和重启停用场景已加入首文档及 ADDED delta；M1 仍以 spec 全场景收口，runbook 新增新旧 profile/各 Agent/空业务集/停用重启观察点，发布资产 frozen-lockfile smoke 与真实三窗任务分开。当前缺 MODIFIED 现有真白名单 Requirement，不能带矛盾归并。审批/首个请求验证需随修订补入现有 M1，不需新里程碑。 |
| 保留项与架构判断 | `retained_from: Round 2`：Notes/History session 边界、原始来源、稳定窗口/事件引用、长结果恢复、compaction 严格缩短/配对、fallback 提示保真、无摘要/tail、真实任务与外部副作用验收继续适用。插件负责恢复策略，Nano 负责默认安装、工具选择和产品审批；没有理由把这些能力下放 PA/Channels 或建立第二个 loop。无新增客户端界面，不要求原型。 |

### 历史问题闭环

R1-W1/W2/W3 及 R1-R1/R2/R3 保持 closed；R2 无未关闭项。此次问题由新的默认覆盖范围和相关增量引出，不回写前两轮结论。author 对尚未写入冻结设计的后续修订意向不计为本轮闭环证据。

### Issues

#### R3-W1 — 四个基础恢复工具绕过业务 allowlist 后仍被普通审批路径阻断

- **位置：** `design.md:71-72,134`；`spec.md` 的“所有 Agent 默认使用无摘要换窗且可显式回退”。
- **证据：** 当前 `policy/approval.ts:20` 的 safeTools 不包含 notes/history/new_context/get_context_remaining；`review:99-121` 在 downstream allow 后，对它们仍执行普通审批。当 Auto 关闭且没有额外 alwaysAllowTools 配置，`review:121` 进入 `escalate`；普通人类会话返回 ask，Global/子 Agent 根据 `route:71-77` 返回 return_to_agent，继而 deny。开启 Auto 则依赖独立分类模型，不是内部上下文操作的确定路径。四工具本身只发布普通 ToolDefinition，注册存在不免除此审核。
- **未修后果：** 合法的 Auto-off Agent 虽展示了四个工具，却无法无人干预地写检查点/主动切窗；Global/子 Agent 直接被拒。新的默认机制会在正常预算回收时阻断连续工作，不能靠扩大业务 allowlist 或 dangerouslySkipPermissions 解决。
- **修订要求：** 明确当前 Agent/session 内部上下文工具的专门审批语义及审计来源，覆盖 nano/codex/dsh 和 Auto off，同时保留 downstream 明确拒绝与工具自己的作用域/路径校验。其它业务工具不得随此放行。用真实 dispatch 覆盖 Auto-off 普通/Global/PA/子 Agent 的四工具可用，以及业务工具仍受限；把此证据加入现有 M1。

#### R3-W2 — 只有 ADDED delta，会与当前“显式空名单拒绝一切工具”契约同时成立

- **位置：** `specs/gateway/agent-capabilities.md:3-15`；`design.md:136-138`。
- **证据：** canonical `docs/specs/gateway/agent-capabilities.md:223-255` 的 Requirement 明确静态工具集恰为白名单，显式空集没有任何工具，Scenario“显式空名单的 Agent 会话拒绝一切工具调用”要求任何工具都不执行；“显式工具白名单不被默认集合自动扩宽”同样只允许 plugin_manager 的有限增量。本轮新 ADDED 要求空白名单也得到四个内部恢复工具，直接改变了这些现有消费者契约。
- **未修后果：** 归并后同一配置同时要求四工具可用和一切工具拒绝，实施/验证会在两条权威断言间自行取舍；只新增一个要求不足以表达这次行为变更。
- **修订要求：** 在 delta 中对该既有 Requirement 给出 MODIFIED 完整版本，保留未改变 scenarios，仅为当前已挂载的四内部恢复工具增加有限例外，明确其它业务工具和 workspace 插件规则不变；同时更新 design 的 delta 摘要。无需提前改 current spec。

#### R3-W3 — 首次 pre-step 尚无有效 request header/context，缺少预算 bootstrap 状态

- **位置：** `design.md:123`。
- **证据：** DSH `agent-loop/src/agent.ts:269-285` 先进行 pre-step；到 `step:408` 才调用 prepareRequest，`prepareRequest:547-595` 才获得 adapter prepareCall 的 C/O；`buildRequest:618-625,654-665` 才写首次 request/header 和 request/context。新会话首个 pre-step 没有这些记录是正常时序，并非 Node 缺少 max_tokens 或模型配置非法。设计指定从 prepareCall 后的 header 取 O，同时仍笼统规定“无合法 C/O”就报告无法容纳，尚未明确首次请求如何进入这一步。
- **未修后果：** 按文字实现可能在第一个模型请求前误报配置失败，或把尚不可知预算返回为 0/已耗尽；所有 Agent 默认挂载会把此前可选插件的冷启动缺口扩大到普通首次对话。
- **修订要求：** 明确“尚无已准备请求”的 bootstrap 与“已准备但模型无合法预算”两种状态。前者通过公开模型信息读取可得预算，或暂不作压力判定并允许首次请求形成有效 header；不得报配置错误或虚构剩余值。首次 prepareCall 后再依已持久有效 C/O 判定，工具首次不可观测时如实返回不可用。保留真实无合法配置/固定输入超窗的错误及 provider overflow 兜底；增加全新 session、未显式 max_tokens 的首请求验证。无需调用 private 接口或复制 adapter。

### Recommendations

无额外建议。以上是三个直接影响默认机制兑现的缺口；不因未实现的运行结果或假想并发场景扩大设计。


### Author Resolutions — R3

- R3-W1 — Accepted. Design now specifies four session-local internal context operations with `internal_context` audit, after retaining downstream denial; Auto-off dispatch must be verified for all three rulesets and child/PA scope. Business authorization and recovered-content provenance remain unchanged.
- R3-W2 — Accepted. Gateway delta now MODIFIES the complete tool_allowlist Requirement, retaining unrelated scenarios and explicitly bounding the internal-tool exception for empty selection, previews and dispatch.
- R3-W3 — Accepted. Design now separates initial awaiting_first_request bootstrap from missing resolved model bounds; first pre-step permits DSH prepareCall, tool budget reports unavailable, provider overflow remains guarded, later steps use persisted effective C/O.

## Round 4

### Metadata

- reviewer: `/root/design627_review`（同一独立 reviewer）
- reviewer target: R3 Author Resolutions；`design.md` 的内部审批、首次请求预算及 runbook 修订；gateway delta 的完整 MODIFIED Requirement 与新增 Auto-off scenario。
- review_mode: `delta`
- mode_reason: R3 已完整审查“所有 Agent 默认”的需求与组装边界；本轮收口其三个具体缺口，并检查审批例外和预算初始化对既有约束的直接影响。没有进一步改变产品范围、包生命周期或 milestone，保留此前公开接缝证据。
- started_at: `2026-10-21T11:14:50+08:00`
- completed_at: `2026-10-21T11:15:09+08:00`
- duration: `PT19S`
- retained_from: `Round 3` 的公开接缝、默认迁移、所有 Agent 覆盖及架构判断；`Round 2` 的未变恢复算法/提示词与历史问题关闭证据。
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-627`。仅追加报告，未改设计或实现、未提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R3 三项全部关闭。该结论覆盖“所有 Agent 默认”的修订设计；实际实现、固定发布包与真栈连续任务验收仍须按 M1 证明。

### Coverage 与证据

1. **内部审批及业务边界。** `design.md:72-73` 将四工具的可见性与实际执行分别收口：仅当前 Agent/session 内部上下文操作在 downstream allow 后按 `internal_context` 放行，明确保留 deny/ask，覆盖 nano/codex/dsh、Auto off。未扩大 alwaysAllowTools，也未使用 dangerouslySkipPermissions；`design.md:137` 继续规定恢复内容不创造操作授权，PA 发送重验不变。该处理可接在 R3 已核实的 `NanoApproval.review` downstream 判定之后，无须改变 DSH 的执行拒绝边界。
2. **契约完整性。** gateway delta 新增 MODIFIED 与 canonical 同名的完整真白名单 Requirement，明确四个内部工具是有限例外，停用即撤销，预览/下发/执行一致。独立比较原五个 scenarios：禁用默认业务工具、Cron、skill 默认上报三项逐字保留；空集合与显式白名单两项仅加入所需内部工具例外；另增 Auto-off scenario，保留底层拒绝与业务审批。这消除了 R3 的权威契约冲突，没有借默认化放宽所有 workspace 插件。
3. **首请求预算状态。** `design.md:124-126` 选择明确的 awaiting_first_request 路径：无持久 header/context 时不发压力提示、不因未知预算切窗，预算工具返回 unavailable；由 DSH 首次 prepareCall 建立实际 C/O，随后进入既有预算状态机。已解析但仍无合法边界才报配置问题，首次 provider overflow 仍按既有规则处理。该决定与 R3 核实的 pre-step→prepareCall→header/context 顺序一致，未复制模型默认值或读取 private API。
4. **验证承接。** `design.md:164` 已把三 rulesets 的 Auto-off 四工具真 dispatch、业务工具保持受限、首次预算 bootstrap 和首请求后有效 C/O 加入现有 runbook。保留至少三窗真实任务、最新纠正、长结果尾段、单次副作用、新旧 profile/各 Agent 类型及停用重启证据。没有用注册列表或本轮文档检查代替运行验收。
5. **保留结论。** 默认固定包、installation anchor、公开 saveManifest、shipped inventory、单次 marker 迁移及正常启停未再变化，retained_from Round 3。Notes/History 作用域、稳定引用、正常/overflow 重建、提示词保真等 retained_from Round 2；无需重复读取第三方实现或重新审查未改需求。

### 历史问题闭环

| Issue ID | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R3-W1 | Accepted：内部工具专门审批并保留底层拒绝 | `design.md:73,164`；delta Auto-off scenario，明确三规则、Auto off、当前 session、internal_context 与业务约束 | closed |
| R3-W2 | Accepted：补完整 MODIFIED 真白名单 Requirement | delta 对准原 canonical Requirement，保留三项未变 scenarios，修订两项受影响 scenarios，四工具例外有界 | closed |
| R3-W3 | Accepted：区分首请求 bootstrap 与真实缺失配置 | `design.md:124-126,164` 明确 unavailable、允许首次 prepareCall、持久有效 C/O 与首请求验证 | closed |

R1 的所有问题仍 closed，无 still-open 项。

### Issues

无新增 CRITICAL / WARNING。

### Recommendations

无新增建议。进入已授权的实施和既定验收即可。

### Implementation evidence requiring R5 delta

Full Nano regression after default activation exposed 25 failures, including native event evidence ending at the next step with `valid model contextWindow and maxTokens output reserve are required`. A real Web IM to Node to DSH to deepseek-v4-flash smoke reproduced the same terminal error. DSH pi-ai `modelInfo` deliberately sets `defaultMaxTokens` only for deployment-configured caps; provider/catalog limits are not necessarily request defaults (public source `packages/llm/llm-pi-ai/src/adapter.ts:300-315`). Omitted maxTokens is valid existing configuration, not invalid setup.

The author revised only the unresolved-output-limit policy: retain actual explicit output limits; otherwise use labeled policy reserve min(32768, floor(C*0.25)), optionally configured per model, without changing model request options. Expose reserve provenance and retain real provider overflow handling. This supersedes the prior post-bootstrap requirement for a concrete maxTokens. C must still be known and valid. No new model lookup service or private DSH seam.

## Round 5

### Metadata

- reviewer: `/root/design627_review`（同一独立 reviewer）
- reviewer target: `design.md:124-133` 的输出预留策略及上方实际实施证据说明。
- review_mode: `delta`
- mode_reason: 实施暴露 DSH 合法省略 maxTokens 的现状，需修正 R4 对已 prepareCall 后必有具体 O 的假设；只改变缺省输出预算策略，不改变默认覆盖范围、恢复工具、授权边界或 compaction 所有权。
- started_at: `2026-10-21T11:27:31+08:00`
- completed_at: `2026-10-21T11:28:04+08:00`
- duration: `PT33S`
- retained_from: `Round 4`，但其“已解析后仍无具体输出上限即配置缺失”的预算表述由本轮取代；其余默认安装、审批、契约、bootstrap 及恢复机制证据继续适用。
- checkout: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-627`。仅追加本报告，未改实现、未提交、未重跑模型请求。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

允许缺省 maxTokens，并使用明确标记的策略预留，是符合当前 DSH 契约的有界修正。原预算假设确实不能覆盖所有合法模型配置；本轮替换该假设，不回写 R4 历史结论。

### Coverage 与证据

1. **现状核实。** 独立读取固定 DSH 的 `packages/llm/llm-pi-ai/src/adapter.ts:300-315`：只有 deployment 配置的 configuredMaxTokens 才返回 defaultMaxTokens，catalog maxTokens 明确不是请求默认值。`packages/llm/llm/src/index.ts:883-892` 仅在存在 defaultMaxTokens 时补默认值；`929-950` 的 prepareCall 保留 resolved config，adapterDefaults.maxTokens 只是是否补入的布尔标记。因此 prepareCall 成功、contextWindow 有效但 header.config.maxTokens 缺席完全合法。author 报告的 25 项回归失败及真实 Web IM smoke 是本轮修订触发证据；本 reviewer 未重复运行这些用例，不把报告的失败数量宣称为独立复现结果。
2. **优先级与含义。** `design.md:126` 优先使用实际请求的明确 maxTokens；仅缺省时才选择 `outputReserveTokens` 全局/per-model 策略值或默认 `min(32768, floor(C*0.25))`。这不覆盖已经明确的请求上限，也不把 catalog 能力当作配置值。request-maxTokens 与 policy-estimate 两种来源显式区分，符合预算工具必须如实标记测量来源的既有约束。
3. **计算与错误边界。** C 仍必须合法，O 只用于计算 H/W/R；缺省 O 的 H 已明确称为预算估计，不宣称供应商保证的硬容量。显式但非法的上限/预留以及固定输入无法容纳继续报错，不把非法数值悄悄替换成策略默认。现有 `0<R<W<H` 与压力状态机保持，真实 provider overflow 仍走缩短后 retry、无进展失败的原路径。调整没有承诺突然超长结果仍必有完整保存机会。
4. **模型请求与职责。** 策略值不写入真实模型请求、不更改 Nano 已冻结的 turn 模型配置，仅由上下文插件用于预算；无需私有 DSH 接口、额外模型 lookup 服务或第二个默认值所有者。bootstrap 仍表示首次尚无可观察请求，之后缺省 maxTokens 转为可计算的 policy-estimate，而不是永久 unavailable 或配置失败。
5. **验证承接。** 现有 M1 的预算状态、真实压力/overflow、首次请求和长任务验证继续适用。实施复验需覆盖合法缺省 maxTokens 的后续步骤、显式 cap 优先、策略覆盖及非法值、两种 output_reserve_source，并核对真实请求没有被注入策略 cap；重跑已暴露的回归与同一路径 Web IM smoke 后，才能声称实际故障已修复。本轮仅批准设计，不以数学/静态核对替代这些运行证据。

### 历史问题闭环

R3-W3 的“区分 bootstrap 与已准备请求”仍成立；它及 R4 中对缺省 O 的错误假设由本轮明确纠正。R1、R3 其余问题保持 closed，没有新增未解决的设计项。

### Issues

无新增 CRITICAL / WARNING。

### Recommendations

无新增建议。按修订策略修复实现并执行既定复验即可。
