# bugfix-640 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review_640`，独立于设计作者；仅写本报告。
- reviewer_target: `incident.md`、`design.md`、`specs/gateway/personal-agent.md`、`M1-review/.gitkeep`。
- review_mode: `full`。
- mode_reason: 首轮 Gate 2，按现行 workflow 检查全部需求、关键决定、实际装配入口、契约增量与 milestone。
- started_at: `2026-10-23T13:09:56+08:00`。
- completed_at: `2026-10-23T13:10:28+08:00`。
- duration: `32s`（正式结论核对与记录阶段；此前已完成的只读源码、文档取证纳入下述 Coverage，不计入该计时）。
- executed_base: `85a6bbaa1da57974a20fcdaccdc2e5c3dad7bb38`，checkout `main`。
- grounding_base: 派发时 `5462b7217421a2c27871c1c5951c1e48644e54ba`；本轮现场推进到 executed_base 的唯一提交为新增本 unit 的 `incident.md`，无产品代码增量，不影响已读运行路径。
- validated_at: executed_base 加工作区冻结设计文件；SHA-256：
  - `incident.md`: `3fdeea8453596e920d6f11611151a66e42fee739525757528ff54cd5c7f25e0e`
  - `design.md`: `4598e5bf3032d0d65853b02b56f7557b4a801cf42281d4e31a30a155bdc58658`
  - `specs/gateway/personal-agent.md`: `eaec5870b319cf14344449f5a41417b7030c2e73714bf6d3f55b7f6d7304bfe8`
- effective_base / effective_through: 同本轮 validated_at；不提前覆盖实施或后续设计修改。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案能在现有包职责和 DSH 公开接口内实现用户确认的方向。复用的是 Codex 审核执行机制；披露专用 policy、输入投影和 verdict parser 是必要适配，设计已经明确不能原样套用普通工具审核的风险默认值和证据截断。未发现会使实施实质走偏的未解决设计问题。

本结论是 Gate 2 文档与可行性结论。未执行产品实现、真 LLM 重放、生产部署或本地 CI，不代表这些门禁已经通过。

### Coverage 与证据

#### 1. 事故根因与用户范围

已从实际调用链核实：`PersonalAssistant.send/task/external` 经 `pa.action.prepare` 得到 IM evidence，再把 `pa.evidence` 返回的运行上下文追加给 `pa.review`；`reviewPersonal` 将整份 JSON 一次送入模型，并在本地窗口预检超限时返回 unavailable。IM `PersonalActions.prepare` 同时枚举 `pa_source_reads`、既往外发和 `PersonalAgents.authorization`；后者枚举可访问主人消息及其会话历史。这支持 incident 的“无关历史展开造成体积膨胀，缩短待发正文无济于事”的因果链。

生产具体字符数和失败结果沿用首文档取证，本轮未重新读取生产数据库。设计删除的是外发审核的全库正文入口，保留真实动作与访问事实，符合不新增授权记忆、数据库授权检索链或第二套执行运行时的约束。输入风险分类、私人工作、生产部署和清理指令执行均不在修改范围。

#### 2. Codex 生命周期复用

`packages/dsh-integration/src/policy/codex.ts` 的实际 `CodexApproval.review` 已有单父会话 trunk、busy fork、checkpoint 前缀比较、配置 fingerprint、90 秒共享 deadline、最多一次 recoverable rebuild 和 dispose；`create` 使用 DSH `agents.create` 及受限的 host-owned inspection tools，没有另起产品 Agent loop。`codex-approval-lifecycle.test.ts`、`codex-approval-native.test.ts` 对重写上下文、配置变化、并发 fork、溢出重建、取消、超时和只读能力有现成验证入口。

因此 design 54 的共享执行循环、披露用途独立缓存键、父会话或配置改变时释放，是对真实既有能力的扩展，优于复制一份审核执行器。实施时仍需使 `release(sessionId)` 覆盖两种用途，不能只给缓存 key 加后缀后留下旧释放行为；该要求已由设计明确，不列为开放问题。披露 parser 的四态结果和严格 JSON 与普通 `parseCodexDecision` 的两态及默认值不同，design 31、90 已明确分离。

#### 3. PA 当前上下文、host provenance 与私有信息

当前 `index.ts` 的 `pa.evidence` 已验证 root/child 绑定，遍历祖先，并通过 `systemPrompt.assemble`、`renderPrompt`、`renderContextSnapshot` 和有效 `deriveMessages()` 采集 system/private context；`personalEvidenceMessages` 过滤 reasoning。`sources.ts` 具备原生来源投影和只针对有效 PTC 根恢复持久工具结果的逻辑；`input-source.ts` 要求 host identity 字段，不能把普通 child `source.kind=user` 当真人。

但普通 `ApprovalSources.history/restoreEntries` 会丢弃 runtime/skill 快照，`codexEntries` 又会合并结构化 Inbox/send 证据。design 30、52、56、66、73 已明确保留系统/私有上下文、工具正文、父子执行范围及历史来源，不能只把现有 history 原样接过来。当前系统组装和有效消息这两个输入面都有可复用的真实入口，未要求读取整份私有磁盘记忆库。

设计把身份、参与/观察关系、实际发布的提案、主人原话与记忆分开：主人身份不自动授权，观察消息不升级为直接请求，助手文本和历史恢复不生成新许可。它同时允许恢复真实原始授权后重试，与 current Gateway/IM 的原始授权和观察者契约一致。运行时校验 sessionId 与 PA root 绑定，产品模型不能自行选择另一个上下文。

#### 4. 预算与缺失语义

`codex-context.ts::reviewInput` 当前会预先把工具正文缩至 1000 tokens，并限制工具/非用户条目，随后才做完整输入预算。故普通模式的输入选择不能无差别用于披露。design 56 已把“能装下就完整保留”定为披露模式契约，同时复用 policy/schema/history/output reserve 和最终请求检查，完整 payload、受众与附件不截断。

预算缩减必须留下缺失标记；已恢复的原话可用于核对既有许可，缺失原话或限制不能当作不存在。design 56、58、62、90 对 unavailable、needs_owner 与无合法 verdict 不放行的分工已经收口。累计披露明确限于实际有效上下文，不虚构全生命周期记忆。通过正常历史工具补足证据，符合用户选择的方案；本轮不要求另造检索 Agent 或授权摘要。

#### 5. IM freshness 与实际写入

`personal-actions.ts::validate` 当前检查 profile、附件快照、任务 revision、owner guard、policy/disclosure revision、实际 recipients、联系人限制、来源访问和主人后续回复；`review` 校验 payload/evidence digest；`commit` 在事务中再次校验并消费许可；外部发送先 claim 再记录 provider receipt。设计明确保留这些协议与检查。

`PersonalAgents.directOwnerMessage` 的现有直接主人消息集合及 `messageAllowed` 可作为固定大小指纹的来源，替换 `authorization.guard_messages` 全文比较，不需要授权数据模型迁移。正文变化、原集合成员新增/移除及当前可见性变化都必须影响指纹；observer 中面向他人的普通更新不自动变为新约束。`personal-disclosure.test.ts` 已有 observer 不失效、主人私聊/被点名群约束失效、audience/source/attachment/revision 与重复提交的测试入口。

设计的“去重来源会话及当前访问状态”与正文拆开，避免重新注入所有已读消息；私有内容仍来自 runtime 上下文，而最新访问限制仍来自 IM。指纹只检测冻结条件变化，不被审核器当作授权。该职责划分闭合，未削弱 IM 对实际发布、共享任务和渠道目标的权威。

#### 6. canonical delta 与 milestone

delta 正确修改 `docs/specs/gateway/personal-agent.md` 的“独立披露检查限定于对外行为”，完整保留原“对外发送与私人工作” Scenario，并新增长期使用和换窗证据不足两个消费者场景；未拿 active design 覆盖 current。IM 身份、回执和权限契约保持，no IM spec delta 合理。无前端布局或交互改动，不需要 prototype 或各平台视觉设计。

M1 是同一条 IM → PA → runtime → IM 闭环的单 milestone；职责虽跨包，但不存在必须独立并行的子交付。骨架仅有 `.gitkeep`，未预造 tasks/progress。退出标准同时要求旧路径增长证明、上下文保真、预算/缓存/冻结检查和真实发送，能对照首文档核验。Full 的后续 verifier、产品 reviewer、code review 与 CI 仍按 workflow 执行。

#### 7. 真栈验收可执行性与边界

已读取 `scripts/e2e-up.sh`：它建立隔离 IM 端口、数据库、Gateway 配置、workspace、node identity，默认不开 Feishu；默认模型 catalog 已包含 Codex 模型。该脚本只在构建产物存在时启动，实际运行须先构建本 unit，并从对应 worktree 执行，不能用主仓脚本配 `--wt` 冒充测试新版本。`/im/v1/personal-agent` 的真实创建入口存在；默认 e2e Agent 不等于已创建 PA，须按 runbook 的新测试主人/PA 前置完成创建。

作者在本轮补充了只读源材料位置 `/tmp/nano-pa-review-640/source-chat.json`；本轮确认文件存在、17,121 bytes、权限 `0600`，两个会话分别含 11 与 17 条记录，没有在报告复制私有正文。来源 PA DM 为 `c_kuthz6vx`、目标群为 `c_fqyj3bvq`，最终授权消息为 `d1a65a71c05f4f95b9a31024ed4f669a`。按作者的现场取证，重放必须截止 `2026-10-23T04:28:00.810Z` 的授权，排除后续主人已经自行处理的消息；失败 operation 为 `e1b1d035-7886-4abe-ac39-fca3b48cfc80`。这些定位解决了独立 reviewer 获取本次真实材料的前置，不构成新增授权记忆。

未在本轮启动测试服务或请求真实审核模型；模型代理健康状态为作者提供的执行前信息，实施验收时仍要检查。后续需由产品 reviewer 观察真 LLM 输入、准确测试群、实际回执与不重复发布，不能用固定 allow 的 fixture 或 IM 单测替代。只读测试参与者与隔离配置足以支持不执行清理指令、不连接生产渠道的验收范围。

### 历史问题闭环

首轮，无历史 issues 或 Author Resolutions。

### Issues

无。

### Recommendations

- **R1-R1（可选）**：M1 将上下文保真断言做成易读的差分记录：同一完整工具结果、私有上下文与主人限制在预算足够时进入审核；主动压小预算时记录缺失标记及 unavailable；恢复原话后再核对重试。现有 milestone 已要求这些性质，此建议只改善验收证据的可读性，不扩大产品范围。
- **R1-R2（可选）**：M1 验证报告记录源材料截止点、匿名身份映射、被测 commit/build 与最终回执位置；私人原文仍留本机受限目录。特别注明过滤了授权之后主人自行处理的消息，便于后续 reviewer 复验同一事故而不混入另一个事实状态。

### Author Resolutions

- R1-R1: accepted。按既定 M1 范围记录充足预算、缺失材料与恢复后重试的证据；不增加产品机制。
- R1-R2: accepted。M1 记录原聊天截止点、测试身份映射、实际版本和回执定位。原文仅留本机运行目录。
- Author 核实本轮 0 CRITICAL / 0 WARNING；受审 incident、design、delta 与骨架无实质改动，Gate 2 保持有效。
