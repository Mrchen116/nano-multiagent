# Design Review — bugfix-626-approval-context-fidelity

## Round 1

### Metadata

- reviewer: `/root/design_review`，独立 reviewer
- target: `incident.md`、`design.md`、`specs/gateway/agent-capabilities.md`、`M1-fidelity/` 骨架及现有产品组装链
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖用户约束、现状、完整方案、delta、milestone 和验收前置。
- started_at: `2026-10-20T14:45:38+08:00`（首次记录时钟；此前的源码阅读未计时）
- completed_at: `2026-10-20T14:54:12+08:00`
- duration: `8m 34s`（仅可核实计时区间，不冒充完整阅读耗时）
- executed_base: Nano `bea22ef0ee3215e2498ac653ad4ee1082657f07e`；固定本地 Codex `806d9732c974bc8a51b8317c1bd8985544fe627c`
- changes: 只新建本报告；未改代码、设计、canonical spec 或其他 dirty 文件，未提交。

### Verdict

**Issues Found — 0 CRITICAL / 4 WARNING。**

撤掉普通审批的额外授权取数与保留 PA 两条独立检查的方向正确；Codex 保真设计仍有会改变实际证据或结果的未收口差异，不宜直接实施后再以现有测试通过判定保真。

### Coverage 与证据

1. **实际入口与根因。** `packages/dsh-integration/src/index.ts` 装配 `CcApproval`、`CodexApproval`、`NanoApproval`，`policy/approval.ts:128-129` 对普通受审 PA 动作请求 `pa.authorization`；`classifier.ts`/`sources.ts` 注入 transcript，`codex.ts` 注入 planned_action。设计决策 1 能覆盖生产所述额外输入来源。报告中的生产数值沿用 incident 取证，本轮未访问生产，未将离线代码核查声称为生产复现。
2. **CC 投影与边界。** `policy/cc.ts` 使用 workspace fastpath 与 `classify`；`sources.history` 从 `deriveMessages()` 构造有效历史，PTC 仅关联仍在该有效历史中的 root，普通结果正文默认省略，Inbox 与发送回执另外保留。`sources.restoreEntries`、`inboxSourceInstructions` 明确 live/restored 和真实送达语义。决策 2 与 current `gateway/agent-capabilities.md` 的 CC/DSH 场景一致。此处核查了既有 Nano 对齐落点，未重新运行 Claude Code 二进制，未宣称逐字节等价。
3. **Codex 上游。** 本轮直接阅读固定 SHA 的 `guardian-context/src/{transcript,profile,enforcement}.rs`、`core/src/guardian/{review,review_session,input_budget,review_session_context,reviewer_config}.rs`、`ext/guardian-reviewer/src/{conversation,assessment,retry}.rs`。两份本仓 Codex policy 资产与固定上游 `cmp` 一致；资产一致不能替代输入分类、final admission 与 parser 等价。授权计入消息成本、成功纳入才计 40 项、已选最近 5 个工具项 required、preserve/recovery 分层与一次恢复方向有源码依据。剩余缺口见 W1/W2/W4。
4. **PA 正交性。** `packages/personal-assistant/src/personal-assistant.ts` 的 `admit` 只对非主人 participant 调用 input review，observer 通过 source 准入；`send`/`executeReviewed` 对外披露另走 prepare → review-result → commit，主人 DM 走既有直达。`apps/im-server/src/personal-actions.ts` 仍独立构造授权证据并核对提交状态；DSH `index.ts` 的 `pa.evidence`/`pa.review` 与普通审批分开。保留 `pa.authorization` 的这些消费者是正确选择。未把本 unit 当作独立消息审查大证据问题的修复。
5. **职责与依赖。** 普通审批取数撤销放在 DSH policy facade，来源投影在 `sources.ts`，纯保留/admission 在 `codex-context.ts`，原生 Agent 生命周期在 `codex.ts`，符合现有职责；不需新框架、服务、数据库或执行循环。PA/IM 继续提供产品身份/提交屏障。只读调查工具宿主选择需要修正依据，见 W3。
6. **delta 与 milestone。** delta 路径准确映射 `docs/specs/gateway/agent-capabilities.md`，采用 ADDED，不会遗漏被替换 Requirement 的旧 Scenario；PA current 契约保留无须重复改写。M1 单 milestone 依赖闭合，包含红测、原生 fixture、真实模型产品旅程与独立交付门禁。`M1-fidelity/` 目前为空骨架，退出标准在 design 明列，非虚构已完成任务。
7. **验收前置。** `config/e2e/gateway.yaml` 与 `scripts/e2e-up.sh --wt/--main-config`、`e2e-down.sh` 均存在，健康路径与隔离配置命名可执行；本轮未启动服务或执行产品旅程。author 补充提供本机代理模型探针成功信息，此报告仅将其视为作者证据，未独立复测。无客户端改动，无需前端原型。真实验收须确认 CC 动作实际进入 classifier：普通 workspace write 可能 fastpath，不足以复现额外包问题。

### 历史问题闭环

R1 首次审查，无旧 Round 问题。

### Issues

#### R1-W1：Codex 来源投影尚未定义，现有投影会重复正文并改变上游保留类别

- 位置：`design.md:43,53,65`（profile 决策、保真表及接口）。
- 证据：`sources.ts:163-168` 在 `toolResults=true` 时将一次 Inbox/send_message 结果同时写入 `tool_result` 与专用 result，`codex.ts` 正是如此调用。`codex-context.ts:29` 又把“含任意真人消息”的整个 live Inbox 页归为授权项；该页可能混有 agent/system、observer 或普通背景，不能仅用“用户原文完整保留”解释整页无单项限制。固定上游 `transcript.rs` 以单条角色/消息类别建 entry，`profile.rs` 据类别保留；还区分 ProtectedAssistant，Nano 当前仅有普通 assistant row。
- 未修后果：同一原文重复消耗工具预算/最近项名额；混合页的非授权内容随整页进入历史授权保留路径，即使删除全库包仍与所声明的上游 profile 不一致。单改 token 数和计数不会解决。
- 必需修订：明确 Codex 独有来源映射与单次正文原则，决定混合 Inbox 的分类粒度及共享来源标签、公开/私有 assistant 与 protected 类别的宿主映射；可信身份保留与授权意图判定分开。不能改变 CC 既有投影。M1 对照至少覆盖混合 Inbox、发送回执无重复、恢复来源和相关保留类别；不要求新增通用消息框架。

#### R1-W2：最终 admission 的淘汰顺序遗漏上游的超大可选项预剔除

- 位置：`design.md:43,54`。
- 证据：固定上游 `enforcement.rs` 在按 `(priority, source order)` 淘汰前，先计算 required/notice 后的 `optional_allowance`，移除任何单项（含 framing）已无法放进此 allowance 的 optional evidence。代码注释明确此举避免为了大项牺牲可保留的小项。当前设计仅写“消息早于工具，同级旧记录先淘汰”。
- 未修后果：扣除 required 后可选空间为 700、旧 commentary 为 500、可选工具项为 900 时，设计文字会先丢 commentary，再丢工具，二者皆失；上游先丢根本放不下的工具，保留 commentary。最近五项 required 以外的工具足以形成该实际边界，影响可供判断的证据。
- 必需修订：把 oversized optional 的预剔除、omission/framing 成本与后续优先级淘汰写清，保持 preserve 不截历史、recovery 才允许旧历史缩短。加入对应上游 fixture/语义对照，而非仅断言结果未超 token。

#### R1-W3：保留受限调查工具的宿主冲突依据不准确

- 位置：`design.md:45,56` 的“DSH 本宿主没有 Codex 的只读命令沙箱”。
- 证据：锁定 DSH `0.2.1-alpha.1` 的公开 `@deepseek-ai/dsh-sandbox-policy` 导出 `setSandboxMode(session, 'read-only')`，文档说明 bash/fs 执行读取同一 policy；`@deepseek-ai/dsh-sandbox` 的公开 `SandboxMode` 文档同时明确这是 file-effect policy，Network and process visibility 在该 vocabulary 之外。Codex `review.rs`/`reviewer_config.rs` 还涉及受管网络配置。因此“没有只读命令沙箱”不成立，而“不能只凭该 API 获得与上游同等调查隔离”有更精确的证据。
- 未修后果：用户明确要求只接受必要宿主差异，错误前提会使调查能力的限制被误当作无需核查的必要适配；或者反向误以为一个 read-only 开关足以安全恢复任意 shell。
- 必需修订：基于公开 API/实际组装说明文件只读能力与网络/进程副作用边界，记录为何选择 stat/read/list，以及它们相对上游调查覆盖的限制。不要求为本修复新建沙箱；也不能把未经证明隔离的 shell 放给 reviewer。

#### R1-W4：固定上游的输出契约与当前“四字段严格解析”不同，设计尚未处理

- 位置：`design.md:45,52` 的“policy/risk/authorization/outcome 保留”“完整 verdict”。
- 证据：固定上游 `ext/guardian-reviewer/src/assessment.rs` 的 `guardian_output_contract_prompt()` 明确低风险返回 `{"outcome":"allow"}`，schema 仅 required outcome；parser 接受外围 prose，缺省 allow risk=low、deny risk=high、authorization=unknown，并填默认 rationale。其 `assessment_tests.rs` 明确覆盖 bare allow/bare deny/embedded JSON。Nano `codex-context.ts:10-16,25` 则要求四字段齐全、非空 rationale 和纯 JSON；设计未登记这项差异的宿主冲突。
- 未修后果：固定上游认可的普通低风险输出在 Nano 被记录为 unavailable；仅保持 policy 文件或同名字段不等于 outcome 机制保真，也会误导实施保留现有 parser。
- 必需修订：明确跟随固定上游的 output prompt/schema/parser 默认值与可接受包装，保留既定风险规则但独立核对额外运行时判定是否有上游依据。M1 用固定上游三类样例及非法输出对照；如有真实宿主冲突必须具体列明，不能以“更严格”自动豁免用户的保真要求。

### Recommendations

- R1-R1：真实 PA 普通文件旅程使用会进入审核器的动作，并记录审核 source，避免只验证 CC workspace fastpath；该提醒不要求扩大场景矩阵。
- R1-R2：在 M1 保真表标明采用的同步 context mode/feature 分支。固定上游还有 Legacy/ThreadOwned/Independent 以及可选 checkpoint reuse，当前“同步上游”不足以表示所有 feature 组合同时等价；不要求移植未选择的异步预测入口。

### Author Resolutions

- R1-W1 accepted：design「接口与数据流」新增 Codex 专用来源映射表，逐 Inbox message 分类、单次正文、恢复标记、历史角色与授权意图区分；DSH 无 phase，依上游 None 分支映射 ProtectedAssistant。当前/继承历史在 cursor 前规范化，不修改 CC 投影。加入 M1 对照。
- R1-W2 accepted：决策 3 / 保真表明确 required、notice、framing 和 oversized optional 预剔除，preserve/recovery 区分与源序缩短；M1 以可观察证据保留差异对照。
- R1-W3 accepted：决策 5 改正无沙箱断言，引用 DSH 公开 file-effect policy 不含网络/进程边界，记录 stat/read/list 的具体限制，不新增沙箱或开放未经证明隔离的 shell。
- R1-W4 accepted：决策 6 与保真表恢复固定上游 assessment prompt/parser 默认及包装支持；删除自加 parser 判定。DSH 缺 final-output schema 公共参数作为唯一输出宿主限制明确记录。
- R1-R1 adopted：真实任务须经过 classifier 并记录 source，不以 workspace fastpath 代替。
- R1-R2 adopted：明确使用同步 Legacy retained transcript / 无父 checkpoint reuse；记录 DSH 缺 Codex ThreadOwned provenance/checkpoint 的宿主限制，不声称实现所有 feature 分支。


## Round 2

### Metadata

- reviewer: `/root/design_review`，与 R1 同一独立 reviewer
- target: 修订后 `design.md` 关键决策 3/5/6、来源映射表、同步 Legacy 分支、M1 对照与验收条件；R1 Author Resolutions
- review_mode: `delta`
- mode_reason: 变更限于 Codex 证据分类、admission、宿主限制、输出解析及相应验收；incident、delta、模块职责、公共接口和单 milestone 范围未变。超出单纯关闭问题，复查新增 ProtectedAssistant/Legacy/schema 依据；不重做未变链路。
- started_at: `2026-10-20T14:57:29+08:00`
- completed_at: `2026-10-20T14:59:09+08:00`
- duration: `1m 40s`
- executed_base: Nano `bea22ef0ee3215e2498ac653ad4ee1082657f07e`；Codex `806d9732c974bc8a51b8317c1bd8985544fe627c`；DSH `0.2.1-alpha.1`
- retained_from: `Round 1`；保留其实际审批入口、PA 正交检查、CC 当前对齐、架构依赖、canonical target 与隔离 runbook 证据。此次这些设计内容未改变。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1 四个问题均在设计层闭合。该结论允许进入实施，不代表代码已修复、上游对照已通过、真实模型旅程完成或生产部署。

### Coverage 与证据

- **来源投影。** 修订 `design.md:66-75` 将 normalization 明确置于 cursor 前，仅作用于 Codex；逐条真人 Inbox 采用 User retention，其他来源采用 Tool，保留页级来源、live/restored 与实际 sender。User retention 和授权意图区分，避免整页混合内容统一提升；同 call id 的明确 generic 重复正文单独移除，不把不同调用合并。当前与继承路径均纳入，CC 默认投影不变。
- **ProtectedAssistant。** 直接核对锁定 DSH `dsh-llm/lib/types/message.d.ts`：AssistantMessage 无 phase；固定 Codex `transcript.rs` 的 phase=None 分支是 ProtectedAssistant，`profile.rs` 先走非用户软保留，选中后才成为 Required。设计表与决策 3 均按“已选 ProtectedAssistant”处理，未把私稿当作已发送提议或授权，因此映射有具体依据。
- **admission。** 决策 3/保真表明确 notice/framing、optional_allowance 的不可容纳单项预剔除、剩余项优先级、preserve/recovery 区分以及 required 放不下即 unavailable，对应 `enforcement.rs` 的流程与 R1 反例。M1 要求对照证据保留结果，覆盖目标不是只有请求大小不超限。
- **宿主隔离。** 决策 5 正确认可公开 read-only file-effect policy，同时说明不覆盖网络/进程边界；受限工具只暴露现有 stat/read/list，具体 4096 bytes/200 entries 与 `codex-inspection.ts` 相符。它是已披露的能力缩减，不是“上游支持的任意只读命令均已移植”的承诺。
- **输出契约。** 决策 6 与 `ext/guardian-reviewer/src/assessment.rs` 的 prompt、默认值、包装 JSON 和非法 enum/type 失败一致，删除当前额外四字段强制/风险再判定。独立读取锁定 DSH 的公开 `GenerateOptions` 和 `CreateAgentOptions`：提供 messages/system/tools 与 Agent setup，未提供 Codex 的 final_output_json_schema。使用相同 prompt/parser 且不绕开 DSH public API 的适配成立。文中类型名有可选纠正，见 R2-R1，不影响能力结论。
- **Legacy 分支。** 固定上游 `review_session_context.rs` 的 Legacy 路径确实不加载 parent compaction payload；设计选择 DSH 有效历史/来源投影并在父有效历史改写后重建，明确不支持 ThreadOwned/Independent 的来源证明协议。此次没有引入数据库回放作为缺失协议的替代。
- **验收与职责。** M1 补齐混合 Inbox、发送回执不重复、恢复来源、protected assistant、oversized optional、bare/embedded/非法 verdict 对照。真实 PA 操作要求有 classifier source 证据，排除 fastpath 假阳性；独立 PA 消息检查在无超大独立证据的隔离场景验证，既保留原机制，也不声称修复其尚未纳入范围的证据体积问题。来源、纯预算与 Agent 生命周期仍分别归现有模块，未增加抽象或服务。

### 历史问题闭环

| 原 issue | Author Resolution | 本轮核对证据 | 状态 |
|---|---|---|---|
| R1-W1 | 接受并新增来源映射、逐消息分类、去重、ProtectedAssistant、cursor 前规范化 | design 来源表；上游 transcript/profile；DSH AssistantMessage 类型；M1 对照项 | closed |
| R1-W2 | 接受 oversized optional/framing/notice/preserve-recovery | design 决策 3、保真表；固定 enforcement.rs；M1 对照项 | closed |
| R1-W3 | 接受文件只读与网络/进程边界区分，披露调查能力限制 | design 决策 5；锁定 sandbox policy/type 与现有 inspectionTools | closed |
| R1-W4 | 接受上游 bare/embedded/default parser 与公开 schema API 限制 | design 决策 6；固定 assessment.rs；锁定 DSH GenerateOptions/CreateAgentOptions | closed |

R1-R1/R1-R2 亦已采用：真实 classifier 证据与明确 Legacy 分支均落实。

### Issues

无新增 CRITICAL / WARNING；无仍开放的历史问题。

### Recommendations

- R2-R1（非阻断文档纠正）：决策 6 的 `LlmRequestOptions` 建议改为实际核查的公开 `GenerateOptions`（`@deepseek-ai/dsh-llm`）及 Agent 配置表面。锁定版本中未找到前者；没有 final-output schema 参数的判断已通过后者核实。此类符号名纠正可 retained，不需新一轮设计审查。

### Author Resolutions

- R2 accepted：无实质问题。R2-R1 corrected：仅将 DSH 类型符号 LlmRequestOptions 更正为 GenerateOptions 与 Agent 配置表面，能力结论和设计语义不变，保留 R2 审查有效性。
