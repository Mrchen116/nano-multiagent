# bugfix-678 Design Review

## Round 1

### Metadata

- reviewer target: `/root/bugfix678_design_review`（独立于 design author 的 Codex reviewer）
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖全部已确认需求、跨包接口、Context 生命周期、delta、迁移与 M1。
- started_at: `2026-10-29T20:10:39+08:00`（首次显式计时记录；此前文件阅读未计入 duration）
- completed_at: `2026-10-29T20:14:52+08:00`
- duration: `4m13s`（记录时段；不估算前序阅读时长）
- baseline: `c61b7629aa1a599dda23ea6b09f4bd230440168c`，`/Users/czj/Repos/nano-multiagent`，`main`。
- reviewed tree: 已暂存但未提交的 `incident.md`、`design.md`、三份 `specs/gateway/*.md`、`deployment-prompt.md` 和 `M1-permission-boundaries/.gitkeep`；审查期间保持冻结。没有修改受审文件、产品代码、依赖或 current specs，没有提交。
- Context mode: `agent-context-review` Mode A — Design Review；本 reviewer 直接执行，结果并入本报告，没有新增角色或 Gate。

### Verdict

**Issues Found — 1 CRITICAL / 1 WARNING。Gate 2 未通过。**

需求取舍与职责方向基本清楚，当前稿也诚实标出了 D1，而没有把假设接口写成现成功能。但统一全部模型调用恢复是本 unit 的必需交付，当前锁定 DSH 缺少所需公共执行器，无法据此放行 M1。另有两处既有 canonical Scenario 未由 delta 修改，归并后会与新设计同时生效并相互冲突。应分别关闭 R1-C1 和 R1-W1 后复审；本结论不授权上游开发、依赖升级或产品实施。

### Coverage 与证据

#### 需求、范围与现状

已阅读 `incident.md` 全部用户决定，并逐项对照设计 A/B/C、输入审核、事件处置、外发凭证、图片和 D1。设计覆盖取消工具拒绝驱动的隐藏 Task 限制、复用四个原生只读工具、保留完整原始指令及缺失标记、单消息隔离、确定的 20 条前文与直接回复、PA 主动完成安全沟通、删除全局披露计数和 60 秒过期、冻结图片审核、所有模型用途统一恢复。公开群真实受众、搜索词前置审核、额外记忆绑定、精细攻击分类、披露侧补报和 Bash 均仍明确暂缓，没有借本次设计扩入。

关键 current 断言由实际组装路径确认，而非仅核引用文件：

- `apps/node/src/main.ts:348` 起装配 ExternalChannels/Global 产品入口、`TaskExecution` 和共享 RuntimePort；`packages/dsh-integration/src/index.ts:227` 装配 `TaskExecutionDriver`。该 driver 的 `tools/result` 和人工审批监听在 `task-execution.ts:72` 起写 denied，`runnable()` 读取 held tasks，说明删除职责耦合的位置正确。保留普通权限链、用户停止和正常任务状态符合用户决定。
- `packages/personal-assistant/src/personal-assistant.ts:55` 的 `admit()` 目前返回 boolean、仅非主人 participant 执行输入审核，并直接编排风险通知；`global-agent.ts:180` 在接收路径调用它，`:281` 的恢复路径将 false 扩成 revokeSource。设计改消息级结果和持久状态，能够针对当前问题收窄影响，仍应保留主人/observer 的既有准入范围。
- `apps/im-server/src/personal-agent.ts:269` 起的 incident 目前聚合事件并插入主人模板消息；`global-agent.ts:356` 起已有来源事件读取、生命周期门禁和系统输入交付。设计让 IM 维护事件事实，PA 使用现有发送工具完成沟通，复用位置合理；不能只改模板文字而留住后台代发。
- `packages/dsh-integration/src/index.ts:562` 起的 `pa.review` 在 input 路径调用 `reviewPersonal()`，action 路径调用 Codex disclosure reviewer，并从实际 lineage 组装有效证据。`personal-security.ts:116` 起直接调用 `llm.stream()`；`policy/codex.ts:198` 的 request-error 前置监听不委派 next。两种 current 恢复缺口均确认。
- `apps/im-server/src/personal-actions.ts:29` 起仅允许非主人文本附件；`:74` 起校验实际条件与 disclosure_revision，`:164` 起写入 60 秒期限并在 commit 检查。设计删除计数与期限而保留绑定、内容、权限、受众和回执，符合范围；不会凭计数器删除自动解决用户暂缓的真实受众问题。

#### 架构、接口和维护代价

按 `SPEC.md` 核对：IM 仍持有聊天、资源、事件及外发权威；PA 持有 Inbox、业务状态、沟通和交付；integration 承担 DSH 工具、模型请求和审核上下文；product-contracts/RPC 不传 DSH 执行对象。没有新增第二套 Agent Loop 或跨包 private import。

原生工具复用优于维护专用 stat/read/list：公开 `dsh-tools` 提供 ToolDefinition、scope restriction/guard、register/get 和输出投影，允许在专属 reviewer scope 固定宿主执行器；设计还明确同名 workspace 插件不得替换、间接调用同受 guard、取消/路径/多模态沿用原生能力。因此不需要为本次引入 Shell 沙箱或复制四个工具。对 dynamic Git/进程事实保持未知是用户接受的限制。

消息状态、review_generation、fault delivery ID、incident publication 身份和既有 operation 回执各有实际用途，未见必须另建通知调度器或授权账本的理由。新增 `inbox(action="review")` 仅对 failed 消息重审，身份和原文由宿主取得；`pa.input.context` 从可信 binding 与 source_message_id 推导范围。`incident_ref` 限定绑定、目的地、self 表达和发送次序，不直接授予任意内容 allow。变化前未提交与发送后 unknown 的区分进入契约，避免错误提示诱导重复发送。这些接口的设计语义已达到指导实施的程度；字段名称不是当前已经存在的 API。

唯一不能由现有公共能力完成的关键接缝是 D1，见 R1-C1。替换本仓几个 stream 入口不足以覆盖 `compaction.ts` 的 `BasicCompactionEngine`/preset engine 和依赖内部摘要；设计已识别这一点，仍须用真实上游契约关闭。

#### Agent Context Design Review

覆盖以下消费者和受影响 Surface：

1. **工具/披露 reviewer 的 System、tool schema、history 和 image blocks。** 原始指令保留单元携带身份、来源、顺序及必要公开问答；撤回同等保留；父 Agent、memory、摘要不升级为真人授权。保留有界预算和整单元缺失提示，比保留半条许可安全。以 deriveMessages/checkpoint 判断补送，覆盖 full/delta/fork/rebuild/重启。该目标与 current spec 的对应改写尚未闭合，见 R1-W1。
2. **输入 reviewer 的可信元数据和原聊天证据。** 稳定截止点、20 条窗口、直接回复一次和预算省略顺序明确；原文中的身份标签不能覆盖宿主身份。未来消息、缺失回复和当前消息装不下的情况有显式语义，拒绝历史进入背景不自动准入为新任务。
3. **主 PA 的安全/故障系统事件与工具发现。** 安全事件和技术失败分开，例子提供真实引用、未准入事实、当前已送达事实和下一操作；失败事件明确给出 inbox review 入口，check 可发现未完成故障，read 不返回未准入正文。风险原文作为外部证据而非系统处置指令，模型不必猜 owner/binding；生命周期与未完成事件恢复均写出。
4. **执行主/子 Agent 的工具错误和 Task 状态。** 合法替代、独立工作及显式暂停由 Agent 决定，动作权限仍由宿主检查；没有通过 prompt 放行被拒动作。
5. **待审图片与重复请求。** 设计要求冻结 bytes/hash/MIME/尺寸、能力检查和每次实际请求完整 manifest；最终发送消费同一字节快照，不能用旧历史图片、URL 或描述替代本次待审图。公开 DSH ImageBlock 与 inputModalities 可支持该方向，但预算、offload 和最终 provider 请求仍须在实现期核实。

设计的 R2–R7/W1–W3 要求最终模型输入和代表性真模型行为，不以 helper、UI 卡片或源码字段作为送达证据，验证层级合适。本轮未运行产品或模型，没有证明 PA 已能正确选择新工具、图像已进入 provider 或故障恢复已实现。除 R1-W1 的契约冲突外，未发现另一个有足够证据的独立 Context finding；不以尚未发生的实现验收制造缺陷。

#### Delta、milestone 与迁移

- 三份 delta 的 Target 分别指向正确 gateway canonical 文件，消费者视角正确；但全部为 ADDED，未覆盖受改变的旧 Scenario，见 R1-W1。
- `M1-permission-boundaries/` 仅有空 `.gitkeep`，没有设计期伪造 tasks/progress；单 M1 不设并行组，避免共享审批、事件和提交接口产生中间语义。R1–R8 与 W1–W5覆盖用户结果、失败分支、模型证据、真实接线和部署副本；D1 明确列为启动依赖。
- `deployment-prompt.md` 明确只适用已验收目标版本、需要版本化 plan/apply 命令和复审；当前设计不冒充可执行迁移。旧消息不猜测准入、旧真实回执和 sending/unknown 保留、未提交旧 allow 一次性失效，保留旧列历史值；无限 always 的用户配置列为冲突而非静默覆盖。
- 迁移安排明确备份/WAL、停止写入、事务标识、幂等、原生命周期恢复、新旧契约匹配，以及新数据产生后的回滚限制。功能、重复 apply、中断和恢复验证留在隔离副本，生产仅版本/计数/不变量/健康窗口，不借部署做聊天或任务测试。设计阶段没有确切迁移脚本本身不另报问题；交付时必须兑现已写出的命令与副本证据要求。
- 本轮无新增页面或交互控件，未要求无关前端原型；聊天中的提示、发送状态和风险处置仍纳入 R4/R5 的可见验收。

### 历史问题闭环

无历史 Round、无既有 issue ID 或 Author Resolution。本轮不继承其他 unit 的 Approved 或旧 PR #419 的验收。

### Issues

#### R1-C1 — 统一全部模型调用恢复所需公共能力尚不存在，核心实施依赖未闭合

- Severity / evidence: **CRITICAL / CONFIRMED**（依赖缺口；不是已实现产品的运行故障）。
- 位置：`design.md:181–202`、`:225`；`specs/gateway/agent-capabilities.md` 的“所有模型调用使用统一 DSH 有界技术恢复”。
- 证据：当前 package.json/lock 固定 `0.2.1-alpha.1`；安装包 `@deepseek-ai/dsh-llm-retry/package.json` 仅公开根入口、types 和 package.json。根 `.d.ts` 公开 apply/RetryId/事件类型，无独立请求恢复执行器；随包 `README.zh.md:12,32,72,131` 明确 direct `ctx.llm.stream()` 仍单次尝试、恢复边界是 Agent loop。integration 的输入分类、网页提炼、模型验证直接 stream；压缩还会进入依赖拥有的 engine。Codex request-error 不委派 next 也是独立需修的接线，修它不能补出 direct-call 能力。
- 未修后果：用户要求的“所有模型调用共用 DSH 恢复”仍不可实现。实施者只能遗漏 direct/internal 调用、把简单分类改造成 Agent，或在本仓复制恢复循环；后两者偏离已确认架构，第一种则缺少核心需求。当前稿明确阻塞是正确表达，但“承认缺口”不等于本轮已具备 Gate 2 可放行的接口。
- 要求：按已有 D1 关闭判据，取得可锁定版本的公开执行契约及最小使用样例，确认 Agent/独立调用/内部 summarizer 的覆盖、90 秒完整审核与逐请求预算的组合、取消、结果验证 hook、attempt 遥测及不重放副作用；补入设计后独立复审。上游未满足前保留依赖阻塞，不通过新增本仓重试层绕过。本轮不要求擅自修改上游或对外联系。

#### R1-W1 — Delta 只增加新约束，留下与新设计相反的 current Scenario

- Severity / evidence: **WARNING / CONFIRMED**（契约归并与 Context 设计冲突）。
- 位置：`specs/gateway/task-graphs.md:5`、`specs/gateway/agent-capabilities.md:5` 的 ADDED-only delta；对照 canonical `docs/specs/gateway/task-graphs.md:221–229`、`docs/specs/gateway/agent-capabilities.md:560–570`；设计 A/C。
- 证据一：current“自动失败屏障 SHALL 与 Task 业务状态分离 / 拒绝与新输入”要求不自动解除拒绝动作的重试屏障。新设计则删除 denied 状态、监听和成功解除机制，调度仅依据正常状态；仅追加新 Requirement 会让同一 current 文档同时要求保留与删除该屏障。
- 证据二：current“普通工具审批遵守当前有效执行上下文 / 主会话压缩后延续”要求“不从消息库重放已被压缩移除的原文”。新设计从持久原始 user 事件/可信 Inbox 原话保留指令，并对实际缺失的历史补送。新增独立原始指令 Requirement 没有定义这一旧禁令的受控例外，也没有限定仅影响 Codex 的部分，实施和后续归并无法同时按原文满足两者。
- Context Surface / expected / observed：受影响的是调度提醒和审核 history 恢复；主 Agent 应收到不附隐藏任务限制的拒绝结果，reviewer 应能够得到有界完整原始指令。设计正文支持该目标，delta 却保留相反 canonical 约束。
- 未修后果：worker/verifier 会在保留旧屏障、恢复原话和不读取被压缩消息之间作出互斥选择；直接追加归并使 current 契约与验收依据继续冲突。此为确定性文档冲突，不推断模型一定误解。
- 要求：补充准确锚定原 Requirement 的 MODIFIED delta，完整保留未改变的 Scenario；明确删除拒绝驱动调度屏障，同时保留真实运行故障、生命周期及动作权限检查；对原始指令保留写明 Codex 的有界例外和现行 CC/DSH 有效上下文规则的保留范围。不要在本轮直接改 current specs，也不要用新增一个相反 Requirement 代替修改。

### Recommendations

无额外可选建议；先关闭以上两个实质问题，不扩入已暂缓范围。

### Author Resolutions — Round 1

- **R1-C1 — accepted, unresolved / dependency blocked。** 已核对锁定版本与 npm alpha `0.2.2-alpha.2` 的公共声明，均无所需独立恢复执行器。保留 D1 和 Gate 2 未通过；不擅自改用复制重试或把分类包装成 Agent。设计 D1 增加公开 alpha 核查证据。需要真实上游公开契约后才能关闭，此轮不伪造接口、实现或通过结论。
- **R1-W1 — accepted, fixed pending review。** 在 task-graphs delta 增加原“自动失败屏障 SHALL 与 Task 业务状态分离”的完整 MODIFIED Requirement，保留主执行/读写故障屏障、删除审核拒绝/故障驱动隐藏任务限制；在 agent-capabilities delta 增加原“普通工具审批遵守当前有效执行上下文”的完整 MODIFIED Requirement，保留未变化 Scenario 和 CC/legacy DSH 有效历史规则，明确 Codex 的有界原文保留例外。design B/C 同步限定为 Codex 工具/披露 reviewer。current specs 未改。

## Round 2

### Metadata

- reviewer target: `/root/bugfix678_design_review`（同一独立 reviewer）
- review_mode: `closure`
- mode_reason: 变化只落实 R1-W1 要求的 canonical 契约修改及 Codex 范围消歧，并为仍未关闭的 R1-C1 补充依赖取证；没有新需求、共享接口、恢复机制或 milestone 决定，不需要重做 full 审查。
- started_at: `2026-10-29T20:16:26+08:00`
- completed_at: `2026-10-29T20:16:50+08:00`
- duration: `24s`（证据核对时段，不含随后报告写入）
- baseline: `c61b7629aa1a599dda23ea6b09f4bd230440168c`，`main`；受审修改已暂存、未提交。
- Context mode: Mode A — Design Review，局部复核原始指令补送的消费者范围及错误返回与调度规则的一致性。

### Verdict

**Issues Found — 1 CRITICAL / 0 WARNING。Gate 2 仍未通过。**

R1-W1 已关闭；R1-C1 仍为未关闭的关键依赖阻断。本轮没有新增问题。不因为其他部分已对齐而放行仍依赖不存在公共执行器的 M1，也不将补充查询新版本解释为已经升级或完成技术恢复。

### Coverage 与 retained 依据

- 已重新读取 Author Resolutions、完整 task-graphs/agent-capabilities delta、design B/C 和 D1，并与 current 两个原 Requirement 逐 Scenario 对照。
- `retained_from: Round 1`：需求及暂缓项、产品组装入口、消息状态/事件/外发/图片职责、R1–R8/W1–W5、迁移和生产验证边界沿用 R1。本次变化没有修改这些决定；current specs、`packages/dsh-integration/package.json` 和 `pnpm-lock.yaml` 相对 HEAD 均无变化。无需重复运行产品、模型或迁移验证。
- Context 的局部修订现在明确四个原生只读工具与原始指令保留属于 Codex 工具/披露 reviewer；CC/legacy DSH 不新增持久原文补送。该范围与原用户确认、现有两条独立审核路径和 R1 证据一致。来源、整单元保留、撤回与缺失标记的设计未放松。
- 对新版依赖的补充声明，独立只读检查了 `/tmp/nano-678-dsh-public/deepseek-ai-dsh-llm-retry-0.2.2-alpha.2.tgz` 与同目录 `deepseek-ai-dsh-llm-0.2.2-alpha.2.tgz` 中的 package.json exports 和根公开类型。未执行包代码、未安装或改依赖；registry dist-tags 是 author 的有日期查询记录，本轮不将其当作持续最新状态的独立确认。

### 历史问题闭环

#### R1-W1 — closed

- Author Resolution：accepted，补充完整 MODIFIED Requirement，并在 design B/C 限定 Codex 范围。
- 本轮证据：`specs/gateway/task-graphs.md:17–29` 使用 canonical 原 Requirement 名称，保留“故障与修复”和“拒绝与新输入”两个 Scenario。主执行/读取/持久化故障的正常屏障仍保留；审核子调用失败及拒绝明确不得建立任务或整批任务隐藏限制；等价禁止影响仍受原审批链约束，与 design A 一致。
- 本轮证据：`specs/gateway/agent-capabilities.md:36–53` 使用 canonical 原 Requirement 名称，完整保留“PA 长期跨聊天历史”“主会话压缩后延续”“PA 消息安全保持独立”三个 Scenario。仅压缩后规则增加 Codex 有界保留层的受控例外，明确不重放全库；CC/DSH 仍保持有效历史及原超窗规则。design C 同步限定消费者，新增 Requirement 标题也明确为 Codex。
- 结论：原先两个互斥 canonical 约束已有正确归并位置，不再让实施者自行选择相反契约。R1-W1 关闭；这仅确认设计修订，不表示 current spec 或实现已经改变。

#### R1-C1 — still-open

- Author Resolution：accepted，unresolved / dependency blocked；新增公开 alpha 包取证，保留 D1 关闭判据和不实施边界。
- 本轮证据：锁定依赖仍为 R1 的 `0.2.1-alpha.1`。补充检查的 `0.2.2-alpha.2` llm-retry 根公开声明仍是 apply、RetryId 和恢复事件类型；llm 服务公开 stream 与 providerRetryPolicy，没有所需独立请求恢复执行器。该证据支持“简单升级至此 alpha 不能关闭 D1”，没有形成版本/API/样例/覆盖证明的关闭材料。
- 结论：仍为 **CRITICAL / CONFIRMED**。原生 Agent 恢复与独立调用的统一执行、内部 summarizer 覆盖、完整审核预算组合及结果校验 hook 仍待真实公共契约解决。沿用 R1-C1 的关闭要求；不另建同因 issue。

### Issues 与 Recommendations

存活问题仅 R1-C1；新增问题 0。无额外建议，无需为已关闭 R1-W1 扩大设计范围。

### Author Resolutions — Round 2

- **R1-W1 — accepted, closed。** 复审确认两处 canonical 冲突已由完整 MODIFIED delta 消除，无后续实质修改。
- **R1-C1 — accepted, unresolved。** 维持 D1 依赖阻塞及 Gate 2 未通过；本次提交保存完整范围设计稿、接口/验收安排和准确门禁状态，不代表设计已满足实施准入或功能已实现。不为追求通过继续无变化复审；取得真实公共能力证据后再更新并复审。
