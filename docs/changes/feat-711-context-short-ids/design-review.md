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
