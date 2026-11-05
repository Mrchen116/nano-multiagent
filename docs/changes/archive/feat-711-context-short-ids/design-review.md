# feat-711 Design Review

## Round 1

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非 design author。
- target: `feat-711-context-short-ids` 的 `spec.md`、`design.md`、`specs/gateway/agent-capabilities.md` 与 `M1-short-ids` 退出标准。
- review_mode: full。
- mode_reason: 首次 Gate 2；短编号、活动 surface 替换、History 归一化及预算接口均影响 Agent Context，合并执行 agent-context-review Mode A。
- baseline: Nano `eef6c91c5463d658d48f8e0078d0221b8003830c`；插件 `00f61960a6a81078cb9102347a277aa9147fe30b` / `0.3.0-rc.7`；实际安装 DSH `0.2.1-alpha.1`。
- started_at: 2026-11-05T00:01:29+08:00。
- completed_at: 2026-11-05T00:02:10+08:00。
- duration: 41 秒；此计时覆盖确定性复核至报告记录，前序独立源码阅读未单独计时。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。**

核心编号与恢复方案可以使用现有公开接口实现；但新增高频 `tool/result` surface replacement 的两个既有消费者尚未闭合。当前“业务源码无须改”和“重新测量即可计入标记 token”的描述会使实施实质走偏，修订后可局部复审。

### Coverage 与证据

- **需求与用户约束：** 核对用户确认的会话内有序短编号、首次可见即可引用、裁剪/换窗/重启稳定、原文续读、简洁估算预算；不恢复旧 Notes 编号、不扩大访问权限、不部署生产。设计允许 assistant 占号造成可见间隔，仍保持顺序与稳定，不构成需求缺口。
- **实际产品组装：** Nano `packages/dsh-integration/src/agent-context.ts` 默认安装与显式停用入口、`workspace-tools.ts:67,128` 的实际插件组装、`knowledge/dreaming-agent.ts:51` 的维护会话插件组装均已核对；固定包入口为 `packages/dsh-integration/package.json:87`，不是仅测试装配。
- **公开 DSH seam：** 安装插件目录为 `/Users/czj/Repos/opensource-hub/dsh-agent-context-feat-676`。其 `node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js:904-932,1040-1066` 证实 pre-step 决定返回后才追加接纳的 user 并构造请求；`dsh-llm` 公开导出 `freezeMessage`。`dsh-session/lib/index.js:391-408` 允许单个现存工具结果只改 content 的 replacement，保持 message.id、来源、错误及其他元数据。无需 runtime fork 或 private import。
- **编号、History 与宿主边界：** 插件 `src/history.ts:75-154,240-296` 的控制消息排除、消息归一化、窗口归属、活动项禁止读取与 caller-authorized immutable view 已读。首次 message.id 去重、最早原文与短编号模式同宿主 seq 模式显式分开，能保留恢复和 source_history 寻址；不需要旁路持久化。Nano `knowledge/dreaming-history.ts:80-108` 在授权与时间切片之后调用 createHistoryView；`memory-source-view.ts:16` 已排除物理 replacement。此处“seq item_id 保持”本身合理，但上游冻结切片还有 R1-W1。
- **Agent Context / Mode A：** Consumer 为开启插件的业务及维护 Agent。已核对 user/tool 就地标记 → 当前窗口身份 → Notes 保存 → 换窗/重启后 history.read 的参数来源与可发现性；guidance/reminder/fallback 由旧引用表改为短标记，避免预算查询的额外往返。控制提示不冒充任务、错误与 source 保持、正文只剥离专用末尾 block，设计也要求覆盖原有 `[id:]`、Unicode、多 block 与重复接纳。预算文本与结构化值都明确 estimated；R1-W2 涉及其实际更新链路。
- **组合与权限：** 核对 `policy/retained-instructions.ts:85-106` 和 `knowledge/document-memory.ts:85-98` 的原始事件来源消费；工具原始事件不被覆盖，replacement 不增加授权。审批来源回归已进入设计风险范围。短恢复号不应替代业务工具自己的 message/source ID，该范围未被设计扩张。
- **delta 与 milestone：** delta 锚定正确的 canonical `docs/specs/gateway/agent-capabilities.md`，仅 ADDED，不吞掉已有持续任务、Skill、裁剪、权限与停用 Scenario。M1 具有失败证据、实际入模捕获、短 ID/错误/重复项/Unicode/重启/换窗、source_history seq、预算与快照大小验证，并要求真实模型长任务交付；R1-W1/W2 所需窄回归须随修订纳入。无新增客户端 UI，无视觉原型前置。无一次性迁移，不需要 deployment-prompt；生产部署仍在授权之外。
- **架构判断：** 日志派生身份、插件内的展示/恢复归一化和现有引擎的预算/换窗职责合适；公开 surface replacement 比新增自定义持久事件或旁路索引简单。Nano 原始日志消费者对 native replacement 的识别属于 integration 的职责，不能仅靠保留 createHistoryView 的签名来保证。原生 token-meter 的 shadow-price 协议应由 replacement 生产者遵循，不另造预算计数器。
- **证据限制：** 本轮为设计及实际 API 契约审查，尚无 feat-711 实现或真实模型 trace；不声称模型已经成功恢复。下述 W1 的确定性复核仅执行当前源码中的 safeBoundary，不冒充端到端运行。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — 高频补标记 replacement 会截断 Nano 的 Memory 来源冻结边界

- severity / evidence: **WARNING / CONFIRMED**。
- 位置：`design.md:31,34,64`，尤其“采用公开 tool/result replacement”与“Nano 业务源码无须改”。
- Context Surface：业务历史 → Memory/Dreaming 冻结来源 → source_history → 维护 Agent。
- expected：补标记只改变模型显示；后续已完成步骤仍可作为合法来源按原 seq 与时间边界被选取、查询。
- observed：`packages/dsh-integration/src/knowledge/memory-source-view.ts:58-69` 的 `safeBoundary` 对每个 `tool/result` 删除 pending call，不成功就直接 break，未排除 surface replacement。`memory-sources.ts:247-258` 向它传入原始 own events；`snapshot():270-278` 使用 projectionMode none，并不先做 qualifiedEvents 过滤。新的 pre-step replacement 复用已完成 callId，因此第一个补标记结果就会命中 break。
- 确定性复核：直接提取并转译当前文件的 safeBoundary 函数，输入 `call(0), result(1), step/end(2), 同 callId 的 replacement(3), call(4), result(5), step/end(6)`，返回 `{through:2,time:2}`；仅移去 replacement 后返回 `{through:6,time:6}`。该结果与函数的确定性配对语义一致，不依赖模型推测。
- impact：按当前设计在每个工具结果后生成标记 replacement 后，新的正常工作会长期落在冻结切片之外；Dreaming 和其 source_history 只能看到旧前缀，违背既有来源证据与增量维护契约。原生裁剪也可产生同类日志，但这次设计把它从压力分支扩展到常规路径。
- recommendation：在方案中纳入 Nano 边界配对对原生 replacement 的最小识别，跳过物理替换再计算真实 tool/call/result 完成边界；保留真正未配对结果与 cutoff 的拒绝语义。M1 增加“标记/裁剪 replacement 之后第二个正常完成步骤仍进入冻结目标”的窄回归，并继续核对 source_history 原 seq 定位。无需扩大为 Memory 重构。

#### R1-W2 — 只追加 tool/result replacement 再测量不会计入标记 token

- severity / evidence: **WARNING / CONFIRMED**（已确认已安装公共计量契约；尚未运行 feat-711 实现）。
- 位置：`design.md:20,31,50,64`。
- Context Surface：工具结果补标记 → token-meter surface 投影 → 预算与裁剪/换窗提醒。
- expected：每次内容标记增加的 token 都进入实际计量，正常查询、压力阈值与重启重放使用相同估计。
- observed：安装的 `@deepseek-ai/dsh-token-meter/lib/index.js:268-335` 明确采用 shadow-price 协议：只有紧邻前置 `compaction/prune` 或 `compaction/summary` 的精确替换范围计量 claim，replacement 才产生 `新估计 - 被替换估计`；没有 claim 的 replacement 固定折叠为 zero delta。插件 `src/budget.ts:51-76` 的再次 measure 使用该投影，不会自动扫描纠正。现有原生 pruner `lib/index.js:155-180` 同步紧邻追加 compaction/prune 和 replacement，正是可复用的完整 seam。设计只规定 replacement 与“重新测量计入”，未要求前置计量 claim。
- impact：若按文档仅补标记并重测，新增 marker token 不计入工作预算；多步运行的剩余量和压力时机会偏移，不能满足文档自己规定的最终批次预算一致性。
- recommendation：明确每个标记 replacement 复用原生完整事务：以当前被替换工具消息的同一 estimator 生成精确 shadowedTokenCount，紧邻追加匹配范围的计量事件与 replacement；不单独维护补偿总量。M1 覆盖补标记前后 meter.measure 的实际增量、再次接纳不重复增加、原生裁剪后补标记与重启重放一致。

### Recommendations

- R1-R1：delta 的两个 ADDED Requirement 在归并前补成明确的 WHEN/THEN Scenario（可直接沿用 spec.md 的首次可见、裁剪/换窗/重启与查询预算三个场景），遵循长青契约格式；这不改变核心方案。

## Author Resolutions — R1

- R1-W1 accepted：按实际 safeBoundary 配对代码，原生替换不属于新完成。design 决策 5 及 M1 增加最小 Nano 修复与正反回归；不改变来源权限或证据编号。
- R1-W2 accepted：按已安装 token-meter 的 signed shadow-price fold，design 可复用能力与风险/M1 明确同步相邻 compaction/prune + replacement，并测量 delta/replay。

## Round 2

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；与 Round 1 相同，非 author。
- target: Nano `a8387ed7b` 对 R1-W1 / R1-W2 的设计修订与 Author Resolutions。
- review_mode: delta。
- mode_reason: 修订限于原生 replacement 的计量协议、Nano 历史配对消费者及对应 M1 窄回归；新增一个明确的 integration 修改落点，因此除问题关闭外核对其影响。用户需求、编号算法、公开接口、单 milestone 的目标/依赖和真实模型验收策略均未改变，不需要重开 full。
- agent_context_mode: Mode A；复查来源冻结边界和预算投影更新两条链路。
- started_at: 2026-11-05T00:03:38+08:00。
- completed_at: 2026-11-05T00:03:44+08:00。
- duration: 6 秒；本轮复查复用 R1 的 API/源码证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1-W1、R1-W2 已在设计层关闭。此结论允许按修订方案实施，不代表实现、计量重放或真实模型长任务已经验收。

### Coverage 与证据

- retained_from: Round 1。短编号与首次交付、History 原文及窗口归属、createHistoryView seq、来源与授权、guidance/预算语义、产品组装、隔离验收与非生产部署边界未改，沿用 R1 full 覆盖。
- 独立检查 `git diff eef6c91c5 a8387ed7b -- design.md`：只有原生计价说明、safeBoundary 落点、相关风险和同一 M1 范围/窄回归发生实质变化，没有偷偷变更编号规则或缩减验收。
- 复核当前 `memory-source-view.ts:58-69`，当前问题确仍需要实施修复；方案选择跳过合法原生 replacement、保留真正未配对 append 的阻断，准确作用于问题来源，不放宽业务来源或时间边界。该函数仍由现有 MemorySources/source_history 切片链路复用，没有新增旁路。
- 复核安装的 `dsh-token-meter/lib/index.js:301-335`：相邻匹配范围 claim 才执行 signed delta。方案现在明确使用当前投影消息的 estimator 价格与紧邻同步追加的原生事件对，和现有 pruner 协议一致；新增标记增加 token 同样可表示，不需要第二套预算补偿。
- M1 增加的验证分别守护“后续完成步骤能推进 / 真正未配对 append 仍阻断”以及“标记 signed token delta / 重放一致”，同时保留原文恢复、预算简洁、最终实际请求和真实模型任务退出标准。未把未完成的功能验证推迟到生产。
- 限制：本轮只审设计 delta；没有新实现，未宣称新增回归已通过。R1 的可选契约 Scenario 格式建议仍可在实施归并前处理，不构成设计阻断。

### 历史问题闭环

- **R1-W1 — closed（设计层）**。Author Resolution 接受并修改决定 5：明确 safeBoundary 忽略合法 tool/result surface replace、继续后续步骤、真正未配对 append 仍阻断；M1 范围列出该文件与正反回归。已消除“仅升级插件即可、Nano 业务源码无须改”的错误实施方向。
- **R1-W2 — closed（设计层）**。Author Resolution 接受并在可复用能力中明确 `compaction/prune` 计价事件与 replacement 同步相邻、旧价取当前投影消息；风险与 M1 明确增量与 replay 一致性。已消除“重新 measure 自动修正”的错误前提。

### Issues

无。

### Recommendations

无新增建议；R1-R1 保留为归并前的非阻断格式建议。

## Round 3

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非 design / implementation author。
- target: Nano implementation worktree `2ac60077e4988ab0db5789841b51f42bab02789c` 的 `design.md` 未提交 delta，以及相关插件公开剥离 API / 所有权元数据。插件读取时 HEAD `21ce6d7c1a3245347616318eebdc8ba12645e00a`。
- review_mode: delta。
- mode_reason: 原始正文保留的实现消歧采用专用 block 所有权元数据，且审批证据消费者新增一个公开归一化 seam；这是有界接口/消费者变化，需独立检查 affected chain，不能只据旧 Approved 放行。核心短编号、预算、恢复范围及 M1 任务目标未改。
- agent_context_mode: Mode A；覆盖原始内容 → 自有标记 → 模型投影 / History 与结构化审批证据两条投影。
- started_at: 2026-11-05T00:18:29+08:00。
- completed_at: 2026-11-05T00:18:59+08:00。
- duration: 30 秒；沿用既有完整审查及独立 code reviewer 的版本化复核证据，另查实际差异与源码。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本次两个局部调整符合既有“只移除自身标记 / 不改变来源与授权语义”的目标；不需要扩大为新编号或审批协议。结论是设计 delta 通过，不代替 Nano 未完成测试与真实模型验收。

### Coverage 与证据

- retained_from: Round 1 / Round 2。短编号来源、原生 replacement 与 shadow pricing、safeBoundary、source_history seq、窗口/重启恢复、预算语义、授权范围和产品装配未发生设计变化，保留既有覆盖与 R1 问题关闭结论。
- **所有权判别：** 插件 `src/item-id.ts:29-44,58-65` 的专用末尾 text block 带 `contextItemId`，剥离/幂等同时要求该字段与精确 marker text 匹配。仅正文形似 `[id: N]` 不再被当成插件标记，因此 legacy 原文与引用样例仍可恢复；去除一个自有块后仍保留原始同形块。`tests/short-ids.spec.ts:74-85` 包含该直接场景。
- **模型成本与持久化：** 安装的 `dsh-llm/lib/index.js:29-30` 使用完整 structuredClone + deepFreeze，字段不因生成消息副本而丢失。pi-ai adapter 的 `flattenText / userContent` (`lib/index.js:1163-1164,1188-1213`) 取 `block.text` 构造模型内容，不把 contextItemId 额外序列化给模型。此处源级判断与独立 code-review Round 2 对 `ba81dc4` 的 JSON replay / 原文 / host seq / 幂等七项复核相符；未据此宣称捕获了真实 provider 请求。
- **结构化证据修正有实证：** `/tmp/nano-id-projection-L6wMZV/approval-result.txt` 明确记录 `approval.test.ts:330` 的 send_message_result 从期望对象变为 `JSON 文本 + [id: 6]` 字符串。`policy/sources.ts:169-225` 从有效 surface 取工具正文，现有 parseJson 失败即返回字符串，证实这条影响链，不能只依赖“原始事件仍存在”来忽略它。
- **最小正确落点：** `src/index.ts:1` 新公开 `stripContextItemId` 复用插件同一所有权规则；Nano `policy/sources.ts` 的 shared text helper 在原有拼接与 JSON parsing 之前调用它。metadata 与字段名只负责识别插件生成的展示块；这一步不修改 callId、source、isError、participant/observer、live/restored 或控制来源判断，不把任意正文中的 `[id:]` 批量删除。已有来源规则仍由原可信机制决定，不通过短编号增授权限。
- **Validation 与限制：** 本轮读到实际失败，未重跑或宣称它已经修复通过。相同日志另有 `approval.test.ts:248` 的 raw tool/result 数量 9→18 失败；原生补标记 replacement 本来增加物理事件，本设计通过不等于该项测试已完成对账。现有 M1 的“必要集成测试 / 审批来源回归”仍需验证修正后的结构化对象和原有权限行为，连同 aggregate Nano 检查及真实模型证据一起在交付前完成。此处不新增生产验收，也不放宽门禁。
- **架构判断：** marker 所有权与剥离规则由插件唯一维护，Nano 消费者通过公开导出复用，比在 policy/sources 再写一套文本正则更直接；类型投影在结构化读取前处理，属于 integration 职责，无 DSH private import 或 runtime patch。

### 历史问题闭环

- R1-W1 / R1-W2 保持 closed；本次未修改其 native replacement、计量或边界方案。
- M1 code-review 的原文尾部 marker collision 属于既有设计要求的实现缺陷；独立 code reviewer 已在其 Round 2 以版本化复核证据关闭。本设计 Round 不覆盖或重写该实现结论，仅确认采用所有权字段落实要求的方向正确。

### Issues

无。

### Recommendations

无新增建议；R1-R1 仍为归并前非阻断建议。

## Round 4

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`，非 author。
- target: Nano worktree `2ac60077e4988ab0db5789841b51f42bab02789c` 的新增 TaskContextDriver 原文回执归一化设计；插件 `21ce6d7` 的公开 stripContextItemId 原则不变。
- review_mode: delta。
- mode_reason: R3 后仅新增 Task 消费证据的有界 integration 消费者；需核对严格匹配、持久化与停启去重影响，不重开未变化的编号/换窗/预算方案。
- agent_context_mode: Mode A；Task 原文 → 带标记持久消息 / 模型输入 → 产品消费回执 → 停启恢复与去重。
- started_at: 2026-11-05T00:23:04+08:00。
- completed_at: 2026-11-05T00:23:17+08:00。
- duration: 13 秒；复用 R3 的 marker 所有权与公开剥离 API 证据。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

在 TaskContextDriver 提交消费证据时还原业务正文，是已通过归一化原则的适当应用。R1/R2/R3 的其余决定与审查结论仍有效；不改变短 ID、持久日志、模型可见标记、来源、Task 控制或业务权限。

### Coverage 与证据

- retained_from: Round 1–3。完整事件日志派生短编号、native replacement 与计价、safeBoundary、History/source_history seq、marker 所有权、模型 text 投影及 policy/sources 归一化未变，本轮不重复完整审查。
- **严格匹配的机制成立：** `packages/personal-assistant/src/task-context.ts:80-105` 在 prepare 时以原 message.content 生成 digest，commit 仅接纳 digest、inputId 与整型 turn/consumedSeq 匹配的证据；`inbox.ts:228-231` 仍严格比较 prepared.content 与回执 content。因此若回传带展示标记的正文，已读取消息也不能完成既有回执，静态代码直接支持本次实际失败的归因。
- **修改 seam 正确且有界：** `packages/dsh-integration/src/task-context.ts:12-20` 从已 flush 的持久事件生成证据，限定 turn 内 nano-system / task-context 原消息；同一 evidence() 供 prepare (`:27-28`) 与 commit (`:60-61`) 使用。只对返回的 content 调用公开 stripContextItemId，保留 inputId、turn、consumedSeq 和既有身份绑定，不在产品端放宽 digest/原文核对，也不把 queue/ACK 当成已消费证据。
- **Context / 控制语义：** 剥离只作用于回执副本，原始持久记录和模型请求仍带短引用；source、humanTaskControl、lifecycle_revision、来源撤销与 unavailable 阻断路径未改。原本的停/启原文仍由相同宿主来源进入模型；恢复与去重由真正的消费回执继续驱动，不把“看见标记”当作额外完成证据。
- **所有权与原文保留：** 沿用 R3 确认的 metadata + 精确末尾 text 检查；原文中形似标记的普通 block 不会删除。无需复制正则或引入 Task 专用短编号规则。
- **验证与限制：** 新 Changelog 明确覆盖停启恢复及已消费去重；`tests/task-context-sync.test.ts:109-125` 现有场景核对回执原文、重启后的单次事件、consumedSeq 与不重复摄取，后续 stop/resume 场景覆盖宿主控制来源。测试正在执行，本轮只确认设计与可验证 seam，不宣称这些测试或 M1 真实模型退出标准已经通过。调用方仍需完成相关回归和交付前整体核对。
- **职责判断：** 展示标记的撤销位于生成业务证据的 integration adapter，保持产品原文严格匹配契约；比修改业务 digest、允许任意尾部文本或更改原始记录更直接，也保持既有包依赖方向。

### 历史问题闭环

R1-W1 / R1-W2 保持 closed；R3 的所有权与结构化审批归一化决定 retained。本次无新增未解决设计问题。

### Issues

无。

### Recommendations

无新增建议；R1-R1 仍为归并前非阻断建议。

## Round 5

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非 author。
- target: Nano unit worktree 的已保存 `design.md` Changelog 首条与决定 2：排除延后提交的 `skill-catalog` / `agent-instructions` 原生控制；插件旧候选 `21ce6d7` 的失败证据及新增回归设计。
- review_mode: delta。
- mode_reason: 实际产品暴露 pre-step 分配与原生日志提交顺序的确定性编号不一致；本轮仅复查这两个控制来源的短 ID / 自身 History 排除与宿主旧视图保留，不重开已通过的其他边界。
- agent_context_mode: Mode A；首次 user 标记 → 原生控制提交 → 日志重建 → 跨窗/重启 History 读取。
- started_at: 2026-11-05T00:34:34+08:00。
- completed_at: 2026-11-05T00:35:44+08:00。
- duration: 70 秒。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING（本次设计 delta）。**

排除这两类非任务原生控制是适当的局部修正；既有编号/恢复设计其余决定仍有效。**此前真实候选的编号稳定性验证失败，不能据本设计通过把该候选视为产品验收通过。** 修订实现、锁定候选与真实模型重新验收仍需完成。

### Coverage 与证据

- retained_from: Round 1–4。用户/工具材料、assistant 占号允许间隔、原生 replacement 与计价、safeBoundary、所有权剥离、Task/审批回执和来源授权边界未变；只调整不应进入短编号域的两类原生控制。
- **独立核对实际事件：** 本机 `/tmp/feat711-review/21d59bd7-22c9-4d73-ba3a-398a8edd3f98-before.jsonl` 记录 seq11 runtime-context、seq12 skill-catalog、seq13 agent-instructions 均无 owned marker；真正 user 在 seq14，末块为 `text="\\n[id: 1]", contextItemId="1"`。只读取事件类型、来源、序号与 marker 摘要用于报告，不复制私人任务/规则全文。
- **机制与红测一致：** 旧 `itemIds` 在 pre-step 按已提交日志 + pending user 分配；稍后重建却把新提交控制的首次 message.id 也计入，原 user 遂从 1 变为 3。`/tmp/nano-id-projection-L6wMZV/late-controls-red.txt` 的新增 `keeps a first admitted input ID stable when native controls are committed before it` 明确失败：JSON replay 后 expected 1 / actual 3。此为实际引用错误，不是模型能力或未完成证据的推测。
- **必要的一致范围：** 保存的决定 2 排除两类控制；Changelog 明确该排除同时作用于短编号及自身 History，并保留 createHistoryView 原 seq 视图。这样 pending 分配、已提交重建和 own short History 的 item 集合一致，read(1) 不会误指控制目录；不能只跳过标记或只在列表隐藏，否则映射仍漂移。
- **宿主与来源边界：** 排除依赖真实 `source.kind`，不是解析正文 `<system-reminder>` 或按 role=user 泛化。原日志和当前模型所见 Skill 目录/工作区规则仍保留；宿主 createHistoryView 沿原 seq 投影继续原行为。Task 的 nano-system、真人/其他 Agent 材料及真实工具加载结果未被这一有限排除扩大删除，既有权限与 Skill 按需读取机制不变。
- **职责与复杂度：** 控制来源选择属于插件的编号/自身恢复投影；复用同一排除规则保持两个时点一致即可。无需新持久索引、迁移、截短 UUID、custom event 或 DSH patch。未发布 draft rc.8 仍是失败候选，修正候选不得覆盖其真实证据。
- **验证方案：** 插件回归在 markInputs 后、原 user append 前插入两类真实来源控制，JSON replay 后检查 user1 与自身 History 原文；Nano `context-short-ids.test.ts` 已加入实际 skillRoots / SKILL.md / AGENTS.md 注入，并计划在 compact / shutdown / restart 后分别恢复工具尾部与首用户1。其覆盖的是本次缺失的真实组装 seam，不靠预先注入正确 History 参数来证明模型自主恢复；真实模型仍须由产品 reviewer 对修正后的锁定候选另行验收。
- **限制：** 本轮确认设计和失败证据，不宣称新增测试已经通过或新候选已修复产品表现。原始失败记录须保留；修正后的请求、重启/换窗与行为证据应独立记录，不能把 stub/replay 成功写成真实模型恢复成功。

### 历史问题闭环

- R1-W1 / R1-W2 保持设计层 closed；R3/R4 的归一化决定 retained。
- 本次实际产品稳定性失败在设计层已明确修正方向与有效验证 seam；其实现及真实产品闭环由 M1 继续完成，本设计报告不提前关闭产品验收问题。
- R1-R1 的 Scenario 格式建议现已落实于 delta-spec，作为非阻断建议关闭。

### Issues

无新增未解决设计问题。

### Recommendations

无。

## Round 6

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非本轮设计 author，不实施产品代码。
- target: Nano `a4533edeaedf34595322ca313b359d2f196d247f` 上冻结的 `spec.md` / `design.md` 未提交修订与新增 `window-local-ids.md`；插件当前 `2fa5911`（已发布 rc.8 的实现链），尚无本次产品实现。
- review_mode: full。
- mode_reason: 尽管改动链路有界，用户已把编号命名空间从“会话”改为“窗口”，并增加已发布 rc.8 引用保留约束，属于核心编号不变量变化；故完整复核当前需求、编号/History/换窗消费链、宿主边界和 M1 补充退出标准。未变化的权限、预算和平台证据复用前轮，不增设门禁。
- agent_context_mode: Mode A / Design Review。
- started_at: 2026-11-05T10:53:09+08:00。
- completed_at: 2026-11-05T10:54:34+08:00。
- duration: 85 秒。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

窗口内重号、旧窗口基数恢复、成功换窗后的 pending 重新标记与现有成对寻址接口闭合，可以进入实施。结论仅为设计通过；不声称新的窗口编号实现、兼容回归或真实模型验收已经完成，也不将该规则归因于未经证实的 Codex 内部算法。

### Coverage 与证据

- **用户目标与兼容边界：** `spec.md` 明确新窗口从 1 开始、不同窗口允许重号、旧引用按原 window_id + item_id 恢复；`window-local-ids.md:5-7` 进一步明确正在运行的 rc.8 旧窗口保留基数，下一成功新窗口才重置。此前不支持旧 seq Notes 的非目标不等于可以重排已经发出的 rc.8 短引用；本补充设计正确区分两者。原文与 Notes 不需要迁移或回写。
- **实际产品入口与发布现状：** Nano `packages/dsh-integration/package.json:87` 已固定不可变 rc.8 URL。`agent-context.ts`、`workspace-tools.ts:67,128` 和 `knowledge/dreaming-agent.ts:51` 仍组装同一插件；本次无需新增 Nano 编号实现或业务协议。补充设计要求新不可变版本与 integrity 接入，并保持生产部署另行授权。
- **现有编号/History 接口：** 插件 `src/item-id.ts:16-27` 当前对完整日志的首次 message.id 分配会话级整数；`history.ts:88-165` 以首次原记录归属窗口，并以 seq 排序、游标及原文定位。`readHistoryItem():263-275` 本来同时匹配 windowId 和 itemId，因此不同窗口的 1 不存在接口歧义。`createHistoryView():298-309` 继续非 short 的宿主 seq 模式，不得把窗口短号混入获准来源的证据接口。
- **窗口与成功事务共用事实：** `history.ts:37-69` 当前只把 start + summary + 无 error 的 end 识别为成功窗口；`rollover.ts:222-323` 使用同一事务写入 start / summary / checkpoint replacement / end，异常分支写 error end。`window-local-ids.md:11` 将这段窗口识别抽到内部 windows.ts、保留 history 导出，避免编号与恢复各自判断边界。失败、不完整事务不重置；正常 pruner 的 compaction/prune 也不成为新窗口。checkpoint.ts 与 countRollovers 的既有消费者可复用该唯一 owner，符合现有公开 DSH 边界。
- **旧 rc.8 编号基数：** `window-local-ids.md:12` 不是把旧窗口重新从 1 排，而是以该窗持久自有 marker 的已发出号减去逻辑消息窗内位置恢复基数。示例：旧窗首个可见工具在窗内位置 3，原 marker 为 43，则基数 40；之前未打印的 assistant 位置 2 仍为 42。后续物理替换保持首次 message.id / 原窗口，不重复占位；后写入的 replacement marker 也应归其原逻辑消息所在窗口。新窗无已提交锚点时基数 0，后续首个持久 marker 又能把相同基数重建出来。现有 metadata + exact text 判定可区分宿主自有 marker 与原文伪标记，无需另建索引或解析正文号码。
- **pending 输入与换窗时点：** 当前 `index.ts:134-175` 在 pre-step 早期 markInputs 后可能 perform 换窗；现行代码直接返回原 marked decision，因此仅改 itemIds 不足以兑现新规则。保存设计在 `window-local-ids.md:13` / `design.md` 决定 2 明确：成功事务后重新计算 pending，旧 pre-step marker 不是已提交锚点，先移除自有旧块再加新块。DSH agent-loop 的 `lib/index.js:1051-1066` 在决定返回后才追加接纳 user，故该 seam 能保证首次实际请求只见新窗口正确号，不篡改历史已提交消息。晚提交的 skill-catalog / agent-instructions 等控制继续不占位，R5 修正没有被撤销。
- **重放、fork 与裁剪：** Session 公共接口允许从完整 seed replay/fork；`dsh-session/lib/types/fork.d.ts` 说明保留精确连续来源前缀并附 synthetic closers。按完整继承日志、逻辑首次出现、持久 marker 与成功窗口边界重建局部编号不依赖进程状态。局部编号不代表 fork 获得跨会话访问权；窗口身份仍沿现有 session/window 契约生成。设计保留原 window_id 和 seq 归属，裁剪副本不能因写入较晚而变成新窗新材料。
- **模型消费与成本：** Consumer 仍是从 user/tool 正文旁读取短标记的 Agent。补充方案提供 A/1 与 B/1 的 Before/After，并要求 guidance 说明“只在窗口内有效”、Notes 成对保存窗口和短号。当前 guidance、reminder、fallback 已要求成对保存，可以局部消歧；不需要新查询步骤或常驻引用表。窗口身份来自可信 checkpoint/动态上下文，模型不需猜测 namespace。短号复用不影响来源、优先级、授权、失败状态、Task/审批证据归一化或 source_history seq。
- **spec / canonical target 与 M1：** 变更仍锚定 gateway/agent-capabilities 的短引用 Requirement，原权限、原文保留和预算场景继续成立。`window-local-ids.md:21,25` 已把同号不同窗、旧引用、首个输入/工具、同一步 pending、失败事务、裁剪、旧 rc.8 与 assistant 的 JSON replay，以及隔离真实模型的旧引用恢复列入原 M1 的补充退出标准；实际 adapter 输入、重启与原文恢复均在范围内。没有增加前端变化或生产写入验证要求。归并前需同步 canonical 的新窗口场景，见非阻断建议 R6-R1。
- **架构判断与保留证据：** 成功窗口事实由内部 windows 模块维护，短号由插件从日志派生，业务证据仍由 integration/产品原接口消费，职责方向合适。R1–R5 已确认的计量、safeBoundary、marker 所有权、原文/Task/审批归一化和控制来源排除保持有效。复用既有事件与 marker 比新增迁移状态或第二套持久映射更简单；本轮没有要求额外抽象、历史修补或无关平台矩阵。
- **未验证项：** 没有运行新产品代码或新模型任务。当前源码仍是会话级编号；上述判断证明方案与实际 seam 一致，不证明新行为已交付。实际版本/integrity、受影响测试、code review / verifier 及真实模型窗口恢复证据由实施后回填。

### 历史问题闭环

- R1-W1 / R1-W2 保持设计层 closed；R3–R5 的原文归一化、控制排除与证据限制 retained。
- 原 R1–R5 对当时会话级方案的结论不回写。本轮批准的是用户后续明确要求的窗口内方案；旧兼容基数不把这次用户决定伪装成原设计本就如此。

### Issues

无。

### Recommendations

- **R6-R1（非阻断）**：本次实施归并时，将“首次阅读”改为窗口内有序，并把 `spec.md` 的新窗口/旧引用 Scenario 同步到 canonical `docs/specs/gateway/agent-capabilities.md`；保留现有恢复原文、业务证据与授权场景。归档 unit 中旧 ADDED delta 属于此前交付记录，不应据它遗漏此次已确认的新行为。

## Round 7

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非 author，不修改产品实现。
- target: `window-local-ids.md` 对 code-review R8-P2 的冻结设计修正：成功原生换窗 metadata 标识新编号规则，旧零 marker 窗口保留会话累计基数。
- review_mode: delta（targeted compatibility correction）。
- mode_reason: 新的真实 rc.8 AgentLoop 反例否定了“无 marker 即新窗”的兼容前提；本轮检查新增持久消歧及直接影响的恢复、事务、后续 provider 和验证范围，其余 R6 决定保留。
- agent_context_mode: Mode A / Design Review。
- baseline: Nano `a4533edeaedf34595322ca313b359d2f196d247f` 加冻结文档；失败候选插件 `1b35100`，本次修正尚未编码。
- started_at: 2026-11-05T11:04:39+08:00。
- completed_at: 2026-11-05T11:05:07+08:00。
- duration: 28 秒；复用已检查的持久化与 adapter 投影契约。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING（修订设计）。**

持久标明新规则的成功起点，能够消除无 marker 旧窗口的实际歧义；原记录与旧引用无须回写。**R6 对完全无锚旧窗口的兼容覆盖不足，该部分判断由本轮反证与修订取代；原历史报告保持不变。** code-review R8-P2 的实现关闭及修正候选验收仍待完成，不因本设计通过而提前关闭。

### Coverage 与证据

- retained_from: Round 6。窗口 + item 成对寻址、首次 message.id 去重、旧 marker 基数优先、同一步 pending 重新标记、控制来源排除、宿主 seq、预算与权限均未变。本轮仅改变无 marker 窗口的默认基数判据及其持久来源。
- **反例已核实：** `/tmp/feat711-static-review-legacy-zero-anchor.log:5-6` 记录 rc.8 原 History 成功读取 `review-legacy-hardcap:26 / 6`，候选读同一对引用为 not_found；摘要 JSON 记录该窗 assistant 6→1、tool 7→2，后窗 assistant 8→1。完整原件为 `/tmp/feat711-static-review-legacy-zero-anchor-events.json`。这是原版 AgentLoop 的连续压力执行与候选重建比较，不是真实 provider 行为，但足以确认确定性兼容缺陷。不能把已有普通/有 marker 回归通过外推到这个实际形状。
- **新增持久来源与选择规则：** 冻结补充设计规定在现有插件原生 checkpoint/summary text block 写自有 `contextItemWindowBase: 0`。成功窗口识别以同一 start + summary + 无 error end 为准，仅该成功边界激活新规则；初始窗原本就是 0。此前无锚旧窗回到 rc.8 原会话累计逻辑位置基数，有 marker 的窗仍优先保留已发基数。这能恢复反例的 6/7/8，并保护旧 assistant 的未打印位置，无须从旧 Notes 或任意正文猜测时代。
- **生效与后续窗口：** 该 flag 标识编号规则从成功边界开始，而非只标识单个窗口。完整日志重放、fork 继承及之后其他 provider 的成功窗口都延续新规则；后继无 marker 窗不能再退回旧全会话基数。失败/未闭合事务里即使已有带 flag 的 summary，也不能激活规则。保存设计已明确这两个条件，避免把失败写入或“非本插件后续 provider”当成新旧判断空洞。
- **事务 seam 与持久化：** 既有 `rollover.ts:265-307` 同步构造 checkpoint、summary、shadow pricing 和物理 replacement，再写成功 end；`windows.ts:11-22` 当前共享成功事务识别。将规则 metadata 附在既有自有块并随同一事务保存，符合该 seam；新 metadata 不是新事件、旁路文件或公开 WindowInfo 字段。编号消费者可读取内部成功边界信息，宿主窗口 API 的外部形状不变。
- **Context Surface / 注意力与授权：** flag 只供宿主重建编号，不需要模型理解或提供；模型继续只看到原窗口文字与短号。已安装 pi-ai `flattenText/userContent`（`lib/index.js:1163-1164,1188-1198`）仅取 block.text；metadata 不追加正文 token。此前完整消息克隆/持久重放会保留字段的契约仍适用。成功事务与来源控制依旧由宿主判定，flag 不影响用户身份、Notes 内容、工具权限或 source_history seq。
- **验证覆盖与限制：** 补充设计现已明确加入“真实 rc.8 零标记连续压力窗口”和“其他 provider 的后续成功窗口”，并保留原同号不同窗、pending、失败事务、裁剪、assistant、JSON replay、实际 adapter / 重启和真实模型恢复覆盖。实施回归应以原件旧 `:26/6` 仍可恢复为兼容断言，验证失败 flag 不激活及后续 provider 继续从 1；不需要扩大无关平台矩阵。本轮未执行修正代码或宣称新回归通过。
- **架构判断：** 实际问题是在持久日志中缺少区分两套编号语义的事实。复用现有 checkpoint/summary 的私有 metadata 是针对该已确认问题的最小持久来源，代价小于新增 migration event、永久索引或公开接口字段；严格限定成功事务生效，保留原 shadow pricing 和恢复机制，职责仍在插件内。

### 历史问题闭环

- code-review R8-P2：设计修订已覆盖其失效机制；**实现问题仍待 code reviewer 依据修正候选与实际回归关闭**。
- R6 的“无已提交锚点即基数 0”只对已知新规则范围成立；旧零 marker 兼容判断不再保留。其余 R6 / R1–R5 决定未受影响，沿用原证据。

### Issues

无新增未解决设计问题。

### Recommendations

无新增建议。

## Round 8

### Metadata

- reviewer: 独立 design reviewer `/root/design_review_711`；非 author。
- target: 用户明确“不需要！不用兼容旧版本”后冻结的 `spec.md`、`window-local-ids.md` 和 gateway delta-spec；Nano HEAD `a4533edea` 加当前文档修订。
- review_mode: delta；只确认取消旧版兼容后的剩余设计闭合。
- mode_reason: 新规则内的窗口编号与恢复语义未变；用户明确撤销兼容要求，R7 metadata / 旧基数回退尚未实施，本轮不追查已取消范围或增加替代兼容机制。
- agent_context_mode: Mode A / Design Review。
- started_at: 2026-11-05T11:07:31+08:00。
- completed_at: 2026-11-05T11:08:02+08:00。
- duration: 31 秒；复用 R6 已核对的成功事务、pending 提交和 History 成对寻址 seam。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

按用户最新裁决，最终简化方案可以实施；无需已发 marker 基数推断、迁移 flag 或旧窗口 fallback。此前旧版兼容缺陷属于 **superseded by requirement change**，不描述为已修复。

### Coverage 与证据

- **需求一致：** 首文档记录用户原话，补充设计明确只保证新规则内的引用稳定，保留旧日志与 Notes 原件但不保证旧会话级编号继续寻址；delta 同步同一边界。没有把保留原件误写为保留旧编号。
- **剩余编号链闭合：** 完整日志按共享 successfulCompactions 判断成功 end，每成功边界将 next 重置为 1；失败/不完整事务不重置。message.id 在全日志去重，物理替换不占号且保留原逻辑消息的窗口与编号。不同窗口重号继续通过 window_id + item_id 区分。
- **首次交付与恢复：** pending 在同一步成功换窗后重新计算，剥离自身旧块再写新号；控制来源排除、原始内容保留、裁剪/重启/JSON replay 的确定性重建，以及宿主 source_history seq 和授权语义保持原已审方案。无新持久状态或模型必填参数。
- **验证范围适当：** 保存设计保留新规则的双窗同号原文恢复、pending、失败事务、裁剪和 JSON replay，以及独立 RuntimeClient 新会话两次公开换窗/进程重启后的两个 item1 恢复；取消旧版兼容测试符合明确需求。既有真实模型证据仅按未变化的新会话编号/文本复用，最终代码与包接线仍需适用验证，本轮不提前宣称交付通过。
- retained_from: R6 的新规则寻址/事务/pending/权限判断、R1–R5 的来源与原文归一化。R6/R7 的旧版兼容约束及其推断/metadata 方案仅保留历史，不再作为实施或验收要求。

### 历史问题闭环

code-review R8-P2 的原始反例与证据仍成立，但用户已明确取消它所对应的旧版兼容要求，故按需求变更 superseded。R7 未实施的 metadata / 回退方案退役；不要求为其补实现或回归。

### Issues

无。

### Recommendations

无。

### Author Resolutions — Round 6

- R6-R1 accepted：归并时在 canonical 恢复引用 Requirement 添加新窗口 Scenario，旧的裁剪恢复、业务证据和授权 Scenario 保留。设计无实质异议；按已冻结设计进入 M1 后续修正。

### Author Resolutions — Round 8

用户明确取消旧版本兼容，R8 无实质异议；R6/R7 的兼容建议仅保留历史，不实施迁移 metadata 或 fallback。最终实现按 R8 最小规则完成。新规则中的原窗口引用保持稳定；旧版会话级编号不再承诺兼容。
