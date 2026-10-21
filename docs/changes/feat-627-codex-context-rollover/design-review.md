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
