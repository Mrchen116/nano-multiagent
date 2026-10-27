# bugfix-626：恢复工具审批上下文边界 — 技术方案

> 对齐：[incident.md](incident.md)，用户已确认恢复 CC/Codex、保留 PA 两道独立消息检查。

## Changelog

## 现状分析

### 涉及范围

`packages/dsh-integration/src/policy/approval.ts` 是普通工具审批公共入口；它额外读取 `pa.authorization`，再由 `classifier.ts` / `sources.ts` 或 `codex.ts` 加入最终模型请求。`personal-security.ts` 和 PA/IM 的入站、提交时披露检查是另一条链，不通过此参数执行。

`codex-context.ts` 负责 Guardian 的策略与历史投影；`codex.ts` 使用 DSH 原生 Agent 承载复用、并发分支、预算恢复及取消。现有测试分别位于 approval、approval-sources、codex-approval、codex-approval-lifecycle、personal-security 及 PA/IM personal 测试。

### 既有约束

仅使用已声明 DSH public exports；不引入第二套执行循环。主仓已有大量非本任务 dirty 内容，设计阶段仅提交本 unit；实施在专属 worktree。普通审批、PA 入站检查、对外披露各自保留职责。生产不在本次修改范围。

### 可复用能力

- 用：`deriveMessages()` 提供的有效历史和已有 PTC 结果关联；不再增加数据库授权通道。
- 用：CC 固定规则、两阶段、来源适配、fastpath 和失败分流；删除 PA 额外证据参数。
- 改：Codex 历史 profile / 全请求预算选择的偏差，沿用既有 DSH reviewer 会话宿主。
- 用：已有独立 PA 审查。`pa.authorization` 暂留给它自己的调用方；普通工具审批不再引用它。
- 不用：摘要服务、授权账本、全库检索、调大审核窗口或更换审核模型。

### 相关历史

feat-552 / bugfix-613 确立 CC 规则与 Inbox 特例；feat-615 引入同步 Codex Guardian；feat-616 / 621 / 623 引入并扩大 PA 授权取数。复盘见 [retro](../feat-623-pa-message-context/retro-pipeline-rootcause.md)。

另有 active feat-625 已对齐审核失败重试，尚未在本基线实现；它不是本问题的解决方案。本 unit 不撤销其独立需求，final sync 若包含该实现，保留其有界重试与取消契约并复验交叉路径。

## 架构总览

普通动作：有效执行历史 → CC/Codex 来源投影 → 精确待审动作 → 所选审核器 → 原有审计/执行/阻断。

PA 消息：非主人 participant 请求 → 独立入站检查；对外提交 payload → 独立披露检查。两者可以使用产品身份与受众事实，不能因此向每个普通工具动作附加全库历史。observer 背景仍不当作直接请求；真实主人私聊沿用现有豁免。

## 关键决策

1. **直接撤销普通审批的额外取数，而非给它增加裁剪器。** 删除 facade 调用、`ApprovalReviewRequest.personalAuthorization`、transcript/action 注入及不再被使用的专用说明。保留 `personal-security` 的原有取证接口和消息提交屏障。
2. **CC 仅做已确认的宿主适配。** 固定 `cc-2.1.267-nano-v1` 资产不改；普通工具正文省略，Inbox 原话/可信身份/参与关系和真实发送回执保留；运行快照与 Skill 内容仍不重复附加，压缩移除的 PTC 结果不复活。人工/无人值守/子 Agent 分流及现有明确工具免审不借本修复改变。
3. **Codex 固定参考 `806d9732c974bc8a51b8317c1bd8985544fe627c`，纠正证据选择偏差。** 依 `guardian-context/src/{transcript,profile,enforcement}.rs` 分开软保留和最终请求预算，具体来源映射见下表。User/ManualApproval 原文在软保留阶段完整计入消息成本；非用户记录从新向旧扫描，成功纳入才计入 40 条上限；普通消息/工具分别 5000/1000 单项、20000/10000 聚合。已选 ProtectedAssistant 与最近已选中的 5 条工具证据受最终预算保护。最终 admission 先计入 required、历史、notice 与序列化 framing，先剔除单项已无法放入 optional allowance 的可选项，再按消息早于工具、同级旧记录先淘汰。只有 recovery 可在 optional 全部不占额度后仍放不下时，按源顺序缩短旧历史，保留来源、首尾和显式遗漏标记；preserve 不截历史。完整动作和 required 证据放不下即 unavailable，不能静默牺牲它们。
4. **复用与恢复沿用同步上游，删除任意缩放预算。** delta 保留历史授权，放不下则从当前父有效上下文重建；全量重建按实际模型剩余预算选择，去除现有第二次尝试 `0.65` 乘数。保留一次上下文恢复、配置/父历史失效、空闲 trunk、最后成功 checkpoint 的并发 fork、90 秒和父取消约束。审核不可用不当作安全拒绝。
5. **必要适配必须有具体宿主冲突依据。** Rust → TypeScript、Codex runtime → DSH 原生 Agent 是接口适配；Inbox 来源与实际投递是消息传输适配。锁定 DSH 具有公开 `setSandboxMode(...,'read-only')` 和文件效果沙箱，但 `@deepseek-ai/dsh-sandbox` 的公开 SandboxMode 明确不覆盖网络与进程可见性，不能用该开关把任意 shell 声称为同等受限调查。保留宿主执行的 stat/read/list；相对上游不能执行 git/任意命令或调查远端状态，单次仅读本地文件前 4096 bytes/目录前 200 项，遗漏显式报告；模型不能凭缺失部分推断完整事实。本次不新建沙箱。独立审核模型、low 推理及产品交付沿用已明确的 Nano 配置。不得把这组有理由的适配宣传为逐字节或任意任务行为等价。
6. **输出 prompt 与解析直接遵守上游 assessment。** 按 `ext/guardian-reviewer/src/assessment.rs`：低风险使用 bare allow，schema 仅要求 outcome；接受外围文字中的 JSON，缺省 allow risk=low / deny risk=high，authorization=unknown，空/缺 rationale 使用上游默认文字。非法 outcome/enum/type 仍 unavailable。删除当前额外的四字段强制与 parser 风险再判定；critical deny 仍由原封不动的 policy 约束，不能把自己新增的 parser 规则冒充上游。锁定 DSH `GenerateOptions` 与 Agent 配置表面 没有 final-output schema 参数，故使用同一 output prompt 和 parser，不调用 provider 私有接口伪造 schema 支持。

## 保真核对

| 机制 | 固定上游/既有对齐依据 | 本次处理 |
|---|---|---|
| CC 历史与 Inbox | feat-552 的 2.1.267 证据，bugfix-613 | 不改规则；去掉额外 PA 证据，验证压缩边界 |
| Codex 风险、授权和 outcome | `prompts/templates/guardian/{policy_template,policy}.md`、`ext/guardian-reviewer/src/assessment.rs` | 保持 policy，恢复上游 output prompt、bare allow/deny、包装 JSON 和默认值，不添加 parser 判定规则 |
| Codex profile | `guardian-context/src/profile.rs` | 修正授权成本、40 条计数、最近工具保护 |
| Codex 全请求 admission | `guardian-context/src/enforcement.rs` | 先剔除根本放不下的 optional，再按优先级；recovery 才缩旧历史；保留来源首尾；完整 action，不做任意百分比缩放 |
| Codex 复用、fork、恢复 | `core/src/guardian/{review,review_session,input_budget}.rs`、`ext/guardian-reviewer/src/conversation.rs` | 保留现有原生会话映射，复验父压缩、并发、取消及预算恢复 |
| Codex 调查 | 上游 `review.rs` 的 sandbox/managed network；DSH 公共 file-effect policy | 记录网络/进程副作用隔离不受该 API 覆盖，维持受限可执行工具及明确的调查覆盖限制 |
| PA 入站/出站 | gateway/personal-agent current spec；PA/IM 提交路径 | 原机制与可信豁免保持，普通工具审批不再混入其取证结果 |

本次同步上下文采用上游 `ReviewContextPolicy::Legacy` 的 retained transcript 路径，不启用 `GuardianReuseParentCompaction`。DSH 的公开会话表面没有 Codex ThreadOwned 的 retained-source acceptance metadata / compaction checkpoint payload，不能把其内部 checkpoint 搬进 DSH reviewer，也不能以遍历数据库重建相同来源证明。使用 DSH 当前有效历史及既有委派来源；父历史变更使 reviewer 失效。ThreadOwned/Independent 和异步预测不声明为已支持。核对材料及行为测试结论写入 M1 实施证据；发现其他影响判定的差异时更新设计及受影响审查，不以“移植适配”默许保留。

## 接口与数据流

`ApprovalReviewRequest` 只接收实际调用、冻结配置、有效历史来源与必要的消息目标事实。CC 与 Codex 不接受额外 PA 授权包。普通审批失败不会调用独立消息检查作为备用审核。

Codex 来源投影由 `sources.ts` 维护，只作用于 Codex 的当前/继承历史，规范化后再计算 reviewer cursor：

| 原生/宿主记录 | Codex entry 映射 | 来源与限制 |
|---|---|---|
| DSH user / 项目指令 / 已验证 manual approval | User / ManualApproval 的 historical retention | 保留 origin。保留类别不是授权判定：schedule、summary、parent、restored 内容仍按其真实来源理解，不能升为新真人同意 |
| Inbox 结果 | 每条 message 一项，保留页级 target、conversation_type、delivery、channel、pagination 和原 sender/reply | 真人 message 采用 User retention；agent/system/unknown 采用 Tool retention。observer/owner 身份只提供事实，不由程序推断授权意图。live/restored 标记保留。空页/错误仍有结果记录 |
| 普通工具调用/结果、发送回执 | Tool | 一次正文只出现一次；Inbox/send_message 不再同时生成一份完整 generic tool_result。旧继承记录以同一 call id 去掉明确重复 generic 正文，不能删除不同调用 |
| DSH assistant 文字 | ProtectedAssistant | DSH 无上游 phase 字段，按上游 phase=None 分支映射。global 私稿继续标 private，保留不等于已经送达或授权；其 tool calls 另为 Tool |

对单项正文裁剪保留结构化来源外壳与正文首尾，不把 source labels、当前动作或恢复记录改成新授权。同步 profile 与 final admission 是两个清楚的步骤，置于现有 `codex-context.ts`，不新建通用预算框架。现有 `codex.ts` 负责选择 preserve/recovery 阶段，纯投影不负责创建 Agent。

## 契约层增量 (delta-spec)

- gateway：[specs/gateway/agent-capabilities.md](specs/gateway/agent-capabilities.md) 新增当前有效上下文边界要求。
- gateway/personal-agent 已定义独立入站/外发边界，本次保持，无重复增量。

## 风险与回退

压缩后的信息缺失可能让策略要求澄清；不能借恢复全库原文绕过压缩。Codex 的必需证据放不下时允许明确 unavailable，不能以通过率为目标削弱规则。PA 独立消息检查仍可能受到自身证据体积影响，本 unit 不宣称已修复该问题。

回退为撤销本 unit 的代码提交；不会改变数据库、用户策略或生产进程。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | `./scripts/e2e-down.sh --wt "$UNIT_WT"` | `./scripts/e2e-up.sh --wt "$UNIT_WT" --main-config "$UNIT_WT/.approval-e2e.yaml"` | `.e2e-ports.env` 中 IM_URL `/health`；owner node online |

**Review 驱动方式**：本次不改客户端面。走 Web IM 客户端同一登录、消息及配置接口，端到端真栈、真实模型；不得以直接调用审批函数替代产品旅程。

**验收前置**：复用 secret-free `config/e2e/gateway.yaml`，实施时生成忽略的 `.approval-e2e.yaml` 并固定可用的执行与审核模型；先验证本机 `127.0.0.1:4000` 模型代理。所有身份、工作区、聊天及大量历史仅使用隔离合成数据，不复用生产聊天或凭据。前置不可用明确报告，不用 mock 冒充真实验收。

通过同一 PA 会话分别选 CC/Codex，在隔离 IM 写入大量不在有效执行上下文内的历史后交办具体小文件操作，使用目录外隔离目标或 bash 等确实进入分类器的动作，记录审核 source，不能仅凭 workspace fastpath 成功验收。观察实际文件、最终回复及审核证据体积；另在没有超大独立消息证据包的隔离场景核非主人 participant、observer、主人 DM、对外目标四类接线，保留 PA 独立检查。压缩、预算、并发和取消的确定性回归由原生 DSH fixture 验证。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-fidelity | 恢复普通审批上下文与上游证据选择 | 无 | 单 milestone | dsh-integration policy/tests、必要 PA/IM 回归、canonical 和本 unit | [worker] 先取得额外授权读取/输入污染的红测，再使普通 PA 动作在有巨量库内历史时成功；[worker] 混合 Inbox/发送回执单次正文、恢复来源、protected assistant、upstream oversized optional 与预算恢复、bare/embedded/非法 verdict 样例对照；[worker] 压缩、full/delta/fork/取消测试通过，逐项记录必要适配；[reviewer] CC/Codex 真实 PA 普通文件任务完成且确实经过分类器，输入不受库内历史放大；[reviewer] PA 入站/出站、observer/owner 豁免边界保持；[worker] 独立 code review、verification、适用本地 CI 和远端 CI 通过 |
