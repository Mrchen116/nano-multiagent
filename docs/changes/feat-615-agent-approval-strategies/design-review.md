# feat-615 Design Review

## Round 1

### Metadata

- reviewer: `/root/design_review_615`（独立 reviewer，未参与受审设计编写）
- target: `feat-615-agent-approval-strategies`，main `59b7b3dc9` 的 spec 与工作区 design/prototype/deltas；本轮中新增 `prototype-review.md` 作为验证证据，受审方案未改。
- review_mode: full
- mode_reason: 首轮审查，涉及新审批插件、运行时权限、会话生命周期与逐 Agent 配置，需要覆盖完整设计。
- started_at: 2026-10-16T00:18:54+08:00（首次记录时钟；静态阅读已在此之前开始）
- completed_at: 2026-10-16T00:22:18+08:00
- duration: 约 7 分钟（包含计时记录前的静态阅读）

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING。Gate 2 未通过。**

整体架构可实施；不需要 DSH 私有导入或第二套执行循环。需要收口整次审查的执行时限，并把 Gateway MODIFIED delta 改为可直接归并的完整契约。原型视觉缺口已在本轮结束前补充独立观察，不作为未决问题。

### Coverage 与证据

1. **现状与产品组装入口。** 核实 `packages/dsh-integration/src/index.ts:151` 注册 NanoApproval，`agent/created` 在 nano preset 上挂载配置、审批与模型策略；`policy/approval.ts` 当前在 downstream allow 后执行 CC/DSH 分类、人工和无人值守分流，CC 两阶段现有每阶段 30/60 秒限制。`policy/sources.ts` 负责真实 Inbox/发送结果、继承恢复来源投影。设计保留一个 facade 作为产品来源/审计/人工分流所有者，独立插件分别承担判定与各自上下文，职责划分合理，避免复制两套产品交付链。
2. **原生 DSH 可实施性。** 本机安装 `@deepseek-ai/dsh-agent` 0.2.1-alpha.1 的 public 根 export 暴露 `CreateAgentOptions.seed/inheritedEventCount/setup`、`AgentHandle.dispose`、`followup/whenIdle/cancel`；setup 在发布前组装 scope。`dsh-tools` public `restrict` 过滤继承工具，`guard` 在 pre-execute 后提供不能被其他 allow 放宽的拒绝；`agent/request` 与 `agent/request-error` 是公开 scoped 事件。故原生审查会话、成功 checkpoint fork、严格工具表、预算请求适配均有实际 API 支撑。只列工具名不足以隔离，但 design 已要求屏蔽继承工具、guard 兜底及防同名替换；实施必须兑现这些约束。独立审查 Agent 应避免 nano 产品 preset 的普通配置/消息挂载，设计已明确不走 PA 聊天与普通 subagent 通知路径。
3. **需求与权限边界。** CC 普通 write/edit fastpath 保留原生 downstream、真实路径、敏感目标、自定义策略及工具实际执行检查。Codex 保留风险/授权判定、工具结果上下文、只读调查、完整 action、真实来源和已验证人审；不会因工具正文自称而获得授权。共用 facade 保留 Auto、危险跳过、人工及子 Agent never 边界，high/critical 不走拒绝次数放宽。独立插件而非只换提示词的用户要求得到覆盖。
4. **Guardian 机制核对。** 本地参考 Codex HEAD `806d9732c9`；`guardian-context/src/profile.rs` 的 sync 5000/1000、20000/10000、40 条规则与设计相符。`core/src/guardian/review.rs`、`ext/guardian-reviewer/src/conversation.rs` 支持 idle trunk、最后已提交 checkpoint 派生 fork 与 cursor 成功后推进；设计明确配置/历史改写、compaction/overflow 重建与一次紧预算恢复，不能将 30000 当总窗口。保留供应商缓存可观测性限制合理。执行 deadline 尚未覆盖，见 R1-W1。
5. **配置与 canonical contract。** `product-contracts/src/configuration.ts` 是规范化和 fingerprint 入口；`apps/im-server/src/control.ts` 的 operation、apply receipt/recovery 和 rollback，以及 `gateway.ts` registration seed 是真实路径。current `docs/specs/im/agents-nodes.md` 要求成功 apply 后持久化、冲突恢复和每聊天下一轮采用；新增 nullable mode、PATCH 省略保留与清空继承能兼容现有 DSH/Auto 关闭配置。两个 delta 的 canonical 文件选对，但 Gateway MODIFIED 尚不可直接替换，见 R1-W2。
6. **前端独立观察。** 作者先补充 `prototype-review.md`；reviewer 随后经其受限 localhost 服务新开自己的原型 tab（未接管作者 tab），亲自观察桌面画面、选择 Codex、模拟离线保存失败、恢复重试成功，并在实际 `innerWidth=390` / `scrollWidth=390` 查看 CC 说明。策略与解释相邻，保存后的下一轮提示可见；失败红字和可继续保存/放弃的草稿状态共同表明未生效。手机单列中解释正常换行，没有横向溢出。另只读新开当前生产配置页，对照了 Agent rail、身份/行为卡及顶部保存；把选择放在行为卡、自定义指令前符合现有层级，避免埋在长工具列表下。原型省略的其他配置标为背景，不要求实施删减。截图已实际查看于本轮工具输出，未导出私人生产内容；临时 viewport 已 reset，reviewer 新建 tabs 已关闭。初始 file:// 限制没有被绕过；独立观察使用的是用户后来授权的受限 HTTP 预览。
7. **milestone 与验收资源。** design 中单 M1 覆盖配置→下一轮→所选插件→真实文件/消息结果，以及 worker 原生隔离、并发、失败、预算恢复和来源测试；没有仅按包切层。固定 action/transcript 对照与自然语言端到端分别报告，可以区分审批差异与执行模型随机性；固定初始 fixture、模型/推理档、保留首次失败、0 judge calls 与 usage unavailable 都有明确要求。Runbook 给出隔离启停和健康入口；作者报告两个模型最小请求 OK/end_turn，本 reviewer 未重新发送模型请求，该证据只证明资源连通，不是完整策略验收。原生 iOS 设置明确不在 scope。

### 历史问题闭环

首轮，无历史 issue。审查开始时的视觉未验证状态已由作者补证及 reviewer 独立渲染交互在本轮内解除，不冒充产品实现验收。

### Issues

#### R1-W1 — 原生审查循环缺少整次 deadline 与到期收尾契约

- 位置：`design.md:55-58`、接口 `:64`、M1 退出标准 `:116`。
- 证据：设计限制上下文、单工具读量和一次 overflow 重建，却未规定整个审查（创建、模型调用、多次只读调查、重建重试）的共享时限及父调用取消如何传到 reviewer。公开 `AgentOptions.maxTokens` 是每个模型请求上限，`whenIdle()` 本身不是超时机制。当前 Nano 单次分类已有 30/60 秒 timeout；Codex 上游 `ext/guardian-reviewer/src/lib.rs` 的 `REVIEW_TIMEOUT=90s`、`deadline.rs` 与 `retry.rs` 明确让创建/准备及重试共享 deadline。
- 后果：正常模型若连续发只读工具、某次调查或 provider 请求长时间不结束，主工具审批可长期等待；trunk 一直 busy 会把后续审查导向更多 fork。token admission 不能保证结束，也不能替代用户取消传播。这是从单模型分类变成可调查 Agent 后的直接运行成本。
- 所需修订：明确有界总 deadline（可沿用上游 90 秒），父 `exec.signal` 取消传播，重建共享剩余时限；区分用户取消与 timeout unavailable；到期/取消停止并 dispose 未提交审查实例、不推进 cursor/checkpoint，阻止迟到判定执行原动作。把慢调查/持续工具调用和取消时的收尾列入 M1 验证。不要求新增调度框架。

#### R1-W2 — Gateway MODIFIED 未提供完整替换条目，预算行为边界无法直接归并

- 位置：`specs/gateway/agent-capabilities.md:5-7`。
- 证据：目前只有“保留本 Requirement 原有全部场景”的说明，没有任何 Scenario；`docs/specs/CONTRIBUTING.md:133-154` 明确 MODIFIED 写修改后完整条目，归并时替换同名 Requirement。canonical `docs/specs/gateway/agent-capabilities.md:508-540` 包含去重/来源、窗口超限、子 Agent、规则切换与审核模型失败多个场景，且旧“完整输入超窗不裁剪并直接 unavailable”不适用于新 Codex budget recovery。
- 后果：按既定归并方式会丢失原有场景；人工拼接又可能留下对所有策略生效的旧超窗条款，与 Codex 重建恢复冲突。实施者和 verifier 无法从一个确定的目标条目判断适用规则。
- 所需修订：写出修改后完整 Requirement 及全部保留场景，对旧 CC/DSH 上下文与超窗规则明确适用范围，补充逐 Agent 选择/继承/下一轮的具体场景，并与新增 Codex Requirement 用引用协调。不要用“保留原文”代替契约正文。

### Recommendations

无额外阻断项。上述两项关闭后可作有界 closure/delta 复审；无需为未变的原型再次全量走查。

### Author Resolutions

- R1-W1: accepted。design 决策7新增全流程90秒共享deadline、父取消传播、重试剩余时间、await dispose、cursor/checkpoint不提交及迟到判定抑制；只读检查限常规文件和有界目录，防止特殊文件长阻塞。依据上游 REVIEW_TIMEOUT 和当前 DSH cancel/dispose public API。
- R1-W2: accepted。Gateway delta 的 MODIFIED 已替换为完整原条目与全部保留场景；去重投影和直接超窗不可用明确只限 CC/DSH，新增逐Agent选择/继承及下一轮切换场景并指向 Codex 独立预算规则。未更改原型、需求或 milestone 组织。
