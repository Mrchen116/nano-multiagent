# Verification Report: feat-552

实现核验最新结论见 [Round 3](#round-3)：Write 目标状态修复的接线通过，原 W1/W2 保持关闭，verdict=pass；契约收尾见 [Corrected Delta Reconciliation](#corrected-delta-reconciliation)，outcome=aligned。产品 reviewer 的真实 Cron closure 独立进行。以下原始发现与证据保留。

> Validation snapshot: `2fd84b9ac2b1949947ac899b3de7fea1488731ef → 21537b9801732169efc915ca442a5647ecfbd8b9`
> Round 1 · 2026-09-12 · 独立实现对账；源码、测试、配置只读。

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 milestone 已有实现与实施证据；6/6 Requirement 已定位 |
| Correctness | 17/17 Scenario 已核对；R5 的人工否决语义和超限分类存在 2 项 WARNING |
| Coherence | D1–D8 的整体接线遵守设计；D6/D7 的上述细节待修，无架构红线问题 |

Verdict: **fail**。0 CRITICAL / 2 WARNING / 0 SUGGESTION。两项均有范围内的确定性复现，不涉及修改权限配置、运行真实危险动作或推断模型必然误放行。

## Scope and method

- 从远端 `codex/feat-552` detached 创建专用 verify worktree；实际核对 HEAD 与派发的 `validated_at` 一致。产品代码最后修改为 `0fbc85b7b9db8f6ae3f1fd724718c0d1af1c095c`，之后为证据记录。
- 判据：本 unit 的 [spec](spec.md)、[design](design.md)、全部六份 `specs/` delta、[implementation](implementation.md)，以及仓库 `SPEC.md`、`docs/specs/kernel/{runs,tools-hooks,sdk-boundary}.md`、Gateway global/heartbeat 契约和 `docs/development/{testing,coding-guidelines}.md`。
- 沿本 unit 的变化追查 gate、配置、Broker、Bash、来源元数据、tool outcome、SDK/child、PA 入站与 runtime 装配；未扩展为无关全仓审查。未要求不存在的 tasks/progress 文件，也未建立永久 Requirement↔测试机械绑定。
- 本轮独立执行相关永久测试 **237 passed**：共享 gate/config/Broker/来源/真实 SDK/Bash/架构边界 123 项，相关人工反馈、PA/Global/child/模型错误 seam 114 项。固定 Bash 的 2437 条参考决定在其中三个参数化测试内执行，不冒充 2437 个 pytest 测试。
- 另做两次只读定点复现，见 W1/W2。它们证明具体接线结果；没有向真实 LLM 或生产服务发送请求。本轮未重复此前已记录的全量 Python、前端、wheel 或真实模型旅程。

## Completeness

| Milestone | 实现与退出标准核对 |
|---|---|
| M1 shared-auto-migration | 版本化完整 policy/suffix/defaults/source 资产、Bash 命令表及语法适配、共享 gate、3/20 会话计数、来源持久化和子任务快照已落地。CLI/单聊天真实工具旅程与 S1/S2 出站证据可复查；配置、Bash、父子和交互永久回归存在。W1/W2 必须关闭后才能完成本门禁。 |
| M2 global-chat-confirmation | Inbox 多来源、完整 Cron/send_message 动作、Global system wake、共用 runtime 交互字段、拒绝后的三种选择及普通聊天继续工作已落地。真实 Cron 3/3、跨聊天确认 3/3、compact/正常重启、child/follow-up、Heartbeat fallback 与普通 Global/child 故障对照均有持久摘要。 |

没有前端代码或 prototype，原型核对 N/A。CC reference 并非仅有文件占位：[policy adaptation](evidence/policy-adaptation.md)列出固定包/原文哈希、逐项替换及来源模板；[Bash port](evidence/bash-port-implementation.md)列出 53 个命令、1496 项 flags、完整回调映射及固定参考 fixture。运行时只读随包分发的 platform 资产；`pyproject.toml:31`、`:62` 固定解析依赖并打包资产。

## Correctness

以下测试列指永久风险保护；真实模型证据另列，不能以模型一次通过代替永久接线覆盖，也不要求每个模型判断句子各增一条测试。

| Requirement / Scenario | 实现位置 | 永久覆盖与本次判断 |
|---|---|---|
| R1 日常本地开发 | `src/agent/platform/hooks/builtins/_auto_mode_policy.py:36`；`src/agent/platform/tools/builtins/bash_policy.py:109` | `test_auto_mode_policy.py`、Bash policy/reference 与 integration；已授权 CLI/单聊 write、测试、loopback 服务有真实证据。covered |
| R1 明确要求一次 Nano 定时任务 | `src/personal_assistant/tools/cron.py:351`；版本化 defaults 的 Nano Scheduling；`message_context.py:29` | `test_cron_tool_permissions.py:25`/`:35` 保护动作风险及完整 payload；Global runtime 保护入口。创建及触发后实际 write 3/3。covered |
| R1 用户限制仍生效 | `auto_mode_gate.py:546`；独立 policy hard/soft 与用户意图规则 | `test_auto_mode_interaction.py:41` 保护明确 deny 优先级；真实 T4 明确拒绝/未答复文件不变。covered |
| R2 替代、确认和停止 | `auto_mode_gate.py:430`/`:494`；`src/personal_assistant/product.py:202` | `test_auto_mode_interaction.py:61` 保护多次拒绝仍返回且不建人工请求；Global runtime 保护结果交接。covered |
| R2 需要确认时问题可理解 | `product.py:202`；`src/personal_assistant/tools/send_message.py:124` | `test_send_message_tool.py:130` 保护完整目标/正文投影；真实三次 T3 均给出具体删除路径并通过普通聊天回答。covered |
| R3 原问题后的简短同意 | `src/agent/platform/hooks/builtins/_auto_mode_transcript.py:64`；`src/personal_assistant/tools/inbox.py:246` | `test_auto_mode_result_projection.py:18` 与 `test_global_gateway_runtime.py` 保护 CC=1 配对和实际 Inbox/发送历史；T3 三次成功。covered |
| R3 无回答、拒绝或不同事项的回答 | `_auto_mode_transcript.py:64`；`src/personal_assistant/tools/inbox_result.py:9` | 不建立“最近问题”匹配器；`test_global_query_tools.py:13` 保护 target/sender/reply 来源，T4 检查未答、无关同意、明确拒绝的文件状态。covered |
| R3 引用或 Agent 转述同意 | `_auto_mode_transcript.py:88`；`inbox_result.py:9` | `test_auto_mode_result_projection.py:153` 起保护普通、失败、未配对结果不产生 host intent；`test_global_query_tools.py:13` 保留真实来源。T4/T8 有实际读到伪造批准后未越界的证据。covered |
| R3 回复只同意部分内容 | `inbox.py:246`；版本化 policy 的 Path A/B 与范围判断 | 与上一来源 seam 共用保护，范围选择交给模型；真实 T4 只删除获准 B、保留 A/C。covered |
| R4 其他聊天有工作 | `product.py:202`；`auto_mode_gate.py:497`；既有 Global coordinator | `test_auto_mode_interaction.py` 保护不 park；Global runtime 保护持续 session/Inbox。T3 等待 A 时 B 实际返回 391 且 A 文件保留。covered |
| R4 空闲后收到回复 | `src/personal_assistant/gateway/global_run_coordinator.py:216`；`product.py:202` | `test_global_gateway_runtime.py`/`test_global_gateway_lifecycle.py`；T3 普通跨 turn 主会话继续。covered |
| R4 重启或压缩后回复 | `src/agent/core/agent/loop.py:1320`/`:1367`；`message_context.py:178`；`_auto_mode_transcript.py:214` | `test_auto_approval_context.py:204` 保护跨 turn live/重建 kernel restored；已读现有 compact 生命周期覆盖，真实 T5 验证新窗口和重启后旧 host+新 live；允许上下文不足时重述确认。covered |
| R5 审批服务失败 | `auto_mode_gate.py:154`/`:430`/`:494`；`src/agent/core/agent/reject_messages.py:118` | 无结论不执行、不计有效拒绝及 Global/Heartbeat/child 路由均有测试和真实故障对照；但结构化超限分类不符 D7/T6，见 **W2**。 |
| R5 多次拒绝 | `src/agent/platform/permissions/broker.py:233`；`auto_mode_gate.py:624` | `test_permission_broker.py:85`/`:93`/`:102` 与 `test_auto_mode_interaction.py:61` 保护跨 run/工具、独立 child、3/20、成功断连续、总阈值清零及无永久锁。covered |
| R5 其他入口的交互 | `auto_mode_gate.py:338`/`:514`；`reject_messages.py:118` | `test_auto_mode_gate_hook.py:465`/`:547` 与 `test_reject_messages.py:38` 分别保护原 ask/否决；缺少两者组合导致 **W1**。 |
| R6 主任务与子任务 | `src/agent/sdk/kernel.py:153`/`:257`；`src/agent/platform/background_tasks/runtime_runner.py:216`/`:264` | `test_auto_approval_context.py:284` 通过真实 SDK 检查初始/后续原用户上下文、Agent 来源及更新后的父配置；既有子任务 tools/skills 约束保留，T8 两次实际写入经 Terra。covered |
| R6 正常沟通与既有配置 | `send_message.py:124`；`src/agent/platform/config/auto_mode.py:70`；`_auto_mode_policy.py:95` | 原配置根、逐字段覆盖、旧空数组/非空替换、首次 `$defaults`、web_fetch/Bash overrides 保护保留；正常询问和同聊天消息真实可发。covered |

表中省略目录的源码均在上文首次完整路径所属目录，测试均以仓库 `tests/unit/` 或 `tests/integration/` 中对应文件为准。

### Evidence limits

- [Global journeys](evidence/global-real-journeys.md)与其 JSON 记录三次同范围确认、三次 Cron 的输入、动作、请求与结果；这不是误拒率 KPI。[旧/新比较](evidence/old-new-classifier-comparison.md)同一案例每分支一次均 S1 allow，不推导降低误拒率。
- [Child journey](evidence/child-real-journey.md)中越权 write/send_message 没有被模型提出，因此只能证明该旅程未越界，不能记作 gate 实际 deny。永久测试证明来源/有效配置/权限 seam，不证明真实模型的普遍分类准确性。
- T4 第二个 Web owner 的消息在 ingress 返回 404，未进入 Inbox；它证明原 owner 边界仍成立，不证明 classifier 读到了第二人的批准。
- [Heartbeat journey](evidence/heartbeat-real-journey.md)中真实不可达审批端点支持 fallback allow/deny 与普通 Global/child 无结论对照；厂商真正的总上下文超限未实测。本轮 W2 用已支持的 HTTP 错误协议复现，独立于此真实故障证据。
- [CLI journey](evidence/cli-real-journey.md)使用真实 PTY 与现有 kernel factory 注入 seam；个人配置默认工厂读取不在该真实证据覆盖范围。原配置路径和覆盖规则由代码及现有配置/装配测试核对。

## Coherence

| Design 决策 | 结论与代码证据 |
|---|---|
| D1 固定 CC 原文与受限适配 | `_auto_mode_policy.py:20`/`:36` 使用固定 platform 资产和实际路径；完整版本化原文、defaults 与来源模板有逐项适配记录。无上游自动升级或 research 运行时依赖。 |
| D2 单一权限入口与完整 Bash 检查 | gate 先一次 `check_permissions`，明确 deny 先于 Auto 宽许可；Bash 经 `bash_policy.py:109`、`bash_syntax.py` 和 `bash_readonly.py:856` 检查完整原串、语法、重定向、argv/flags、特定回调及 cwd。固定 2437 条差分 fixture 通过；没有平行执行器策略检查。 |
| D3 CC=1 与真实来源 | `_auto_mode_transcript.py:47`/`:64` 采用 UTF-16 上限和 assistant-before-human 条件；工具历史保留原名/args。Inbox 附带应用说明及 sender/target/reply，普通 tool body 不整体提升，当前提议无 outcome。未引入确认实体或全局最近问题绑定。 |
| D4 自动来源 | `message_context.py:29`、Global wake 的明确 system 字段、单聊天 buffered sender 元数据、Cron 调度 origin 保持来源；主模型与 classifier 使用同一组固定来源语义。 |
| D5 compact / live-restored | `loop.py:1054`/`:1111` 物化成功结果；`message_context.py:178` 运行态登记实际消息/call/正文，容量 10000。普通跨 turn 不清空，kernel 关闭清空，重启不信任持久化自报。compact 只取新窗口；conversations 继承投影有 tool-name guard，不复认证旧授权。 |
| D6 计数与产品分流 | `_interaction` 顺序为 global child → heartbeat/cron → global main → 原路由；SDK runtime 创建/重配/读回/identity 与 PA 共用装配一致。3/20 计数按 session、故障不计数、无人值守显式 fallback 和取消协议保留。**W1** 违反故障后人工否决的反馈语义。 |
| D7 配置及多模型 | 原配置位置/覆盖保持，仅扩展 hard_deny/total_deny_limit；S1 2112/stop、S2 10240/no stop、同 policy/transcript、thinking disabled、指定模型不静默替换均有实现与出站证据。**W2** 未消费已有结构化超限信号。 |
| D8 委派入口 | `kernel.py:153` 与 `runtime_runner.py:216`/`:264` 通过既有 subagent control/SessionDirectory 保存原始上下文和有效配置；child 新派发/follow-up 均为 agent，普通 child 关闭自己的 priorAssistantContext 配对。审批模型仍由同一 build-scoped hook 选择，工具副作用逐次过 gate。 |

依赖方向保持 `platform → core`、`sdk → core + platform`；PA 只用 SDK，IM 未直接调用内核，相关 contract 通过。没有新 SDK provider/DTO/配置根、跨机器直读假设或平行授权账本。已有 `SessionRuntimeConfig` 的可选字段已在 SDK delta 记录；其余五份 delta 与本 unit 可观察增量相符，但本轮不是收尾 corrected-delta 的替代。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

#### W1：人工明确否决被先前的分类故障文案覆盖

- 位置：`src/agent/core/agent/reject_messages.py:118`–`:139`；调用链由 `src/agent/platform/hooks/builtins/auto_mode_gate.py:514` 合并既有 `approval=user_deny` 与故障 category，经 `src/agent/core/tools/registry.py:264`、`src/agent/core/agent/tool_executor.py:267` 传入。
- 触发：CLI/单聊天 interactive 的审批模型不可用或解析失败 → 原人工入口实际返回 deny → 结果仍保留先前的 classifier 故障 category。`build_reject_message` 在检查 `approval` 之前进入 fault 分支。
- 本轮只读复现：现有 gate handler，`call_model` 抛出 `RuntimeError("approval endpoint unavailable")`，人工回调返回 `decision=deny, reason="Do not send this report."`。人工入口调用一次，gate 返回 `block=true, approval=user_deny, category=classifier_unavailable`；最终 tool 文本却为 `This action was not executed because automatic approval produced no verdict... do not describe it as a user refusal or a classifier rejection.`
- 影响：动作仍未执行，未发现权限绕过；但明确发生的用户拒绝被告知模型“不要说是用户拒绝”，并丢掉原有停下等待用户的指导。偏离 spec R5「其他入口的交互」、D6，以及 current `docs/specs/kernel/tools-hooks.md:147` 的人工否决契约。
- 修复：fault 专用文案只用于尚无人工否决的无结论结果；已经 `user_deny` 的结果继续走既有用户拒绝/子循环选择，保留用户原理由和故障溯源字段。在现有 `tests/unit/test_reject_messages.py:38`/`:64` 或 gate/工具反馈 seam 合并补充“故障后人工 deny，有/无理由”的回归，不新建测试分类。

#### W2：结构化上下文超限被归为普通审批不可用

- 位置：`src/agent/platform/hooks/builtins/auto_mode_gate.py:199`–`:216`。provider 已由 `src/agent/platform/llm/providers/common.py:40`、`openai_compat/client.py:83` 保留 `ModelError.details.provider_code`；当前 gate 仅搜索 `str(exc)`。
- 本轮只读协议复现：`httpx.MockTransport` 返回 HTTP 400、`error={code: context_length_exceeded, type: invalid_request_error, message: too long}`，经真实 `OpenAICompatClient.generate` 转为 `ModelError(message="openai_compat: too long", retryable=false, details.provider_code="context_length_exceeded")`。Global gate 返回 `decision_source=classifier_unavailable, category=classifier_unavailable`，而非已承诺的 `prompt_too_long`。动作 block，session 拒绝计数为 `(0, 0)`。
- 影响：故障不计拒绝、也未换模型或执行动作，基础路由正确；但已有明确结构化原因丢失，用户/Agent 不能从类别分辨扩大上下文导致的失败与临时不可用。偏离 D7、T6 以及 kernel/tools-hooks delta 的超限分类。现有 `tests/unit/agent/runs/test_model_error_kind.py:103` 已证明仓库把此 provider code 视为 context_length；不是新发明的 provider 协议。
- 修复：消费现有 `ModelError` 的结构化超限信号，可复用已有错误分类或在当前分支读取既有 `provider_code`，保留文本识别作为补充；不增加重试、裁剪或新错误协议。在现有 gate 错误测试加入这一 HTTP/ModelError 形态，断言 `prompt_too_long`、一次模型调用、计数不增加及原入口分流。

### SUGGESTION（可以修）

无。本轮不因测试函数数量或文档文件布局另加流程项。

0 critical issue(s), 2 warning(s) found. Fix before PR.

# Round 2

## Summary

Mode: targeted-closure

Review round: 2

Prior verification: 本文件 Round 1

Validated at: `6bce9c9dc909d2d9da0b481d984e707ded09cfe5`

Effective through: `6bce9c9dc909d2d9da0b481d984e707ded09cfe5`

Executed base: `2fd84b9ac2b1949947ac899b3de7fea1488731ef`

Delta range: `21537b9801732169efc915ca442a5647ecfbd8b9..6bce9c9dc909d2d9da0b481d984e707ded09cfe5`

Focus issues: W1, W2

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 两项修复已实现，原 2/2 milestone 覆盖结论继续有效 |
| Correctness | W1 closed；W2 closed；增量未发现新偏离 |
| Coherence | 原 D1–D8 结论继续有效；D6/D7 原阻塞已解除 |

Verdict: **pass**。0 CRITICAL / 0 WARNING / 0 SUGGESTION。

## Closure evidence

修复提交为 `b218d31e4e27bb2fdad8cbd27bc33e3f92adc817`；`6bce9c9dc` 仅在其上增加本文件 Round 1 报告。本轮重新 detached 签出远端，未修改源码、测试或配置，也未重跑 Round 1 的 237 项全量核验。

| 原问题 | 修复核对 | 独立复验 |
|---|---|---|
| W1 人工否决被故障文案覆盖 | `src/agent/core/agent/reject_messages.py:120` 使 fault 专用文案仅在 `approval != user_deny` 时使用；人工否决仍沿原用户/子循环选择，未清除来源字段。 | 重跑原 gate → 人工回调 → tool 反馈复现：审批先抛不可用异常，人工回调一次并返回 deny；结果仍 block、approval=user_deny，最终文本精确走既有 `REJECT_MESSAGE_WITH_REASON_PREFIX` 并保留 `Do not send this report.`。现有反馈测试覆盖无故障及三类故障后的有/无理由拒绝。closed |
| W2 结构化超限被记为不可用 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:201` 消费已有 `ModelError.details` 中的 provider_code/provider_type，再应用当前超限判据；未添加重试或裁剪。 | 重跑原真实 OpenAICompatClient + MockTransport HTTP 400 协议复现：`context_length_exceeded`、短文本 `too long` 产生 category/decision_source=prompt_too_long；动作不执行、一次分类调用、计数 `(0,0)`、人工入口未调用。新增同 seam 的非超限 provider code 对照仍归 classifier_unavailable。closed |

最窄永久检查：`tests/unit/test_auto_mode_interaction.py`、`tests/unit/test_reject_messages.py`、`tests/unit/test_auto_mode_gate_hook.py`，**48 passed**。这轮结果包含修复的组合回归及原 ask/分流行为；协议复现仍不声称真实厂商超限已经发生。

## Delta and prior-conclusion validity

两处产品修复只纠正分类原因与已发生人工决定的优先级，没有改变工具可用范围、计数、Global/child/Heartbeat/Cron 路由、SDK seam、依赖方向或模型选择。无需升级 full，也无需为这两项重新跑真实副作用旅程。

同提交的 `scripts/e2e-up.sh:245` 在脚本原本创建全新 IM 数据库的清理段，同步清理 worktree 内的旧 Global journal 及 WAL/SHM；它修复隔离验收重用遗留状态，与正常同数据 Gateway 重启是不同入口。只核对该两行与既有隔离重置范围一致，并运行 `bash -n`，未启动服务。该改动未改变 Nano 生产运行/审批契约，不影响 Round 1 产品对账结论。

`git diff --check` 通过。当前存活问题为空；收尾 corrected-delta 仍由后续单独对账处理。

All checks passed. Ready for PR.

## Corrected Delta Reconciliation

Mode: corrected-delta

Validated at: `d4a83f34769e289bc234176bbf9357cfd917b56f`

Effective through: `79c83080a50479776838ac4d62a1a2d8aa185e76`（Round 3 对 Write 目标状态增量的有界核对）

Executed base: `2fd84b9ac2b1949947ac899b3de7fea1488731ef`

六份 delta 共 **16 条 Requirement、47 个 Scenario**，逐项核对完成。`kernel/runs.md` 的三项 MODIFIED 现在是完整条目：原 12 个 Scenario 均保留，其中投影来源两项及分类故障一项按已批准设计更新；另加全局返回场景。无 REMOVED Requirement。首次对账快照 `d4a83f347` 的源码与已通过 Round 2 的 `b218d31e4` 完全相同；后续 Write 状态增量及结论有效范围见 Round 3。

下表按 Requirement 合并列出其全部 Scenario，路径以本 unit 的 `specs/` 为根；实现与测试定位沿用并复查 Round 1/2 的最终代码。测试列是已有永久覆盖及对应实际断言，不表示本轮重跑；真实模型结果仍受上文 Evidence limits 限制。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `kernel/runs.md:7` 工具使用权限回调：采纳 allow/deny、interrupt 解挂、全局返回（3） | `src/agent/core/agent/runtime.py:1639` 回调与 Broker 竞争；`src/agent/sdk/kernel.py:2193` 中断取消；`src/agent/platform/hooks/builtins/auto_mode_gate.py:436`/`:508` 按实际入口返回 | `tests/unit/test_permission_requester_cancel.py:27`/`:165`；`tests/unit/test_auto_mode_gate_hook.py:611`/`:665`；`tests/unit/test_auto_mode_interaction.py:26`/`:62`，校验无需人工调用且不锁住后续动作 | aligned |
| `kernel/runs.md:25` 稳定工具动作描述：缺失 fail closed、动态通用描述、历史不改写、只读 skill 免审、显式成功投影、普通/失败结果不升级（6） | `auto_mode_gate.py:267`/`:288`/`:571` 保留原始动作及单次投影；`src/agent/core/agent/loop.py:1054`/`:1111` 物化；`src/agent/platform/hooks/builtins/_auto_mode_transcript.py:64` 校验配对 | `tests/unit/test_auto_mode_gate_dispatch.py:180`/`:201`；`tests/unit/test_auto_mode_gate_hook.py:313`/`:361`/`:416`；`tests/unit/test_skill_manage_tool.py:83`/`:121`；`tests/unit/test_auto_mode_result_projection.py:126`/`:141`/`:153`/`:172`/`:197`，覆盖真实正文、未配对/失败及投影异常阻断 | aligned |
| `kernel/runs.md:64` 分类模型选择：显式只用于分类、省略用当前模型、catalog 校验、故障不降级（4） | `src/agent/sdk/kernel.py:442` 校验；`auto_mode_gate.py:155`/`:201`/`:625` 使用选定模型并区分超限、不可用和不可解析，保持入口分流 | `tests/contract/test_sdk_kernel_wiring.py:239`/`:257`；`tests/unit/test_auto_mode_gate_hook.py:237`/`:254`/`:278`/`:293`；`tests/unit/test_auto_mode_interaction.py:101`。Round 2 W2 的真实 provider 协议复现通过 | aligned |
| `kernel/runs.md:93` 来源独立于承载角色：真人回复前 assistant、自动与 Agent 输入、跨轮/compact/恢复（3） | `_auto_mode_transcript.py:47`/`:64`/`:214`；`src/agent/core/agent/message_context.py:29`/`:178`；`loop.py:1320`/`:1367`，UTF-16 2000、真人配对与 live/restored 生命周期均符合条目 | `tests/unit/test_auto_mode_result_projection.py:19`/`:46`；`tests/integration/test_auto_approval_context.py:119`/`:161`/`:206`，覆盖输入来源、同 turn 混合以及跨轮 live/重启 restored；T5 实际 compact/重启证据已核对 | aligned |
| `kernel/runs.md:107` 会话拒绝计数与分流：主会话/独立 child、阈值/服务故障（2） | `src/agent/platform/permissions/broker.py:233`；`auto_mode_gate.py:436`/`:639`，3/20、成功清连续、总阈值清总数、无永久锁；child 先于自动 origin 判路由 | `tests/unit/test_permission_broker.py:85`/`:93`/`:102`；`tests/unit/test_auto_mode_interaction.py:26`/`:62`，覆盖跨 run/工具和 fault 不计数；Heartbeat 真故障对照见既有 evidence | aligned |
| `kernel/runs.md:117` 子任务约束与原始来源：新派发/follow-up、委派或结果声称批准（2） | `src/agent/sdk/kernel.py:153`/`:257`；`src/agent/platform/background_tasks/runtime_runner.py:216`/`:264`；`_auto_mode_transcript.py:64`，原始父上下文与更新配置继承，child 输入是 Agent，关闭 child 自身文本配对 | `tests/integration/test_auto_approval_context.py:284`；`tests/unit/agent/test_kernel_create_subagent.py:92`，父子真实 SDK 接线及原 tools/skills 约束保留；T8 真实结果的未提出越权动作边界不扩大为模型实际 deny | aligned |
| `kernel/tools-hooks.md:7` 宽许可不得忽略工具明确拒绝：deny 与整工具 allow 同时存在（1） | `auto_mode_gate.py:526`/`:562` 单次工具自检，明确 deny 先于 Auto 宽许可；`src/agent/core/tools/registry.py:264` 保持单一 hook 执行入口 | `tests/unit/test_auto_mode_interaction.py:45`；`tests/unit/test_auto_mode_gate_dispatch.py:124`/`:141`，直接验证宽许可下仍拒绝及不进入分类器 | aligned |
| `kernel/tools-hooks.md:13` Bash 免审按语法参数：读写参数、复合命令（2） | `src/agent/platform/tools/builtins/bash_policy.py:109` 组合 `bash_syntax.py` 与 `bash_readonly.py:856` 的完整解析、argv/flags/cwd 决策 | `tests/unit/agent/platform/tools/builtins/test_bash_policy.py:31`/`:41`/`:50`，固定参考 2437 条含参数与复合语法，检查 malformed、Git cwd 及 overrides | aligned |
| `kernel/tools-hooks.md:23` 应用提供来源说明：显式宿主投影/固定说明、稳定历史/live 属性（2） | `auto_mode_gate.py:591` 只从已注册工具取固定说明；`loop.py:1054`/`:1111` 与 `message_context.py:178` 绑定真实结果；`src/personal_assistant/tools/inbox.py:152` | `tests/unit/test_auto_mode_policy.py:78`；`tests/unit/test_auto_mode_result_projection.py:46`/`:126`/`:153`；`tests/integration/test_auto_approval_context.py:206`，正文篡改/恢复不能自报 live，固定 system 说明与用户规则分开 | aligned |
| `kernel/tools-hooks.md:33` 区分授权/执行/故障：动作未执行、历史 outcome（2） | `auto_mode_gate.py:450`；`src/agent/core/hooks/runner.py:150`；`src/agent/core/tools/registry.py:267`；`src/agent/core/agent/reject_messages.py:120`；`_auto_mode_transcript.py:64` 保留决定来源、故障类别与实际 outcome | `tests/unit/test_reject_messages.py` 的有/无理由人工 deny 及故障组合；`tests/unit/test_auto_mode_interaction.py:101`；`tests/unit/personal_assistant/test_global_query_tools.py:93`；Round 2 W1/W2 原复现已通过 | aligned |
| `kernel/sdk-boundary.md:7` 完整 runtime 选择交互：创建/重配/读回/identity、省略/清除（2） | `src/agent/sdk/runtime.py:44`/`:78`/`:122` 既有类型可选字段、identity 与完整替换清除；`src/agent/sdk/kernel.py:1588` 读回默认 None；不新增入口类型或 build 参数 | `tests/integration/test_session_run_coordinator_real_kernel.py:341` 以真实 SDK 验证初始 None、完整替换后的 runtime 精确读回及稳定会话；`tests/unit/personal_assistant/test_pa_time_prompt_policy.py:102`；`tests/integration/test_global_gateway_lifecycle.py:86` 保护产品创建/恢复装配 | aligned |
| `cli/interactive-repl.md:7` 多轮确认与原人工入口：正常工作、具体提议回复、阈值、故障、原配置（5） | `src/agent/platform/hooks/builtins/_auto_mode_policy.py:36`/`:95`；`_auto_mode_transcript.py:64`；`auto_mode_gate.py:336`；`src/agent/platform/config/auto_mode.py:70`，固定策略、原路径和逐字段覆盖保持 | `tests/unit/test_auto_mode_policy.py:35`/`:54`；`tests/unit/test_auto_mode_config.py:57`/`:81`；`tests/unit/test_auto_mode_result_projection.py:19`；`tests/unit/test_auto_mode_gate_hook.py:465`/`:547`；CLI/单聊真实旅程已核对，工厂 seam 限制不变 | aligned |
| `gateway/global-agent.md:7` 未获准由主 Agent 处理：拒绝/故障返回、正常发送询问、创建/恢复/刷新（3） | `src/personal_assistant/product.py:202`；`src/personal_assistant/tools/send_message.py:124`；`src/personal_assistant/gateway/session_composition.py:52`；`global_run_coordinator.py:216`，共享完整 runtime 装配及实际入口优先级 | `tests/unit/test_auto_mode_interaction.py:26`；`tests/unit/personal_assistant/test_send_message_tool.py:47`/`:130`；`tests/integration/test_global_gateway_runtime.py:307` 和 lifecycle 覆盖恢复；T3 具体询问与普通回复三次闭环 | aligned |
| `gateway/global-agent.md:22` Inbox 多来源：同页真人/Agent、多聊天提议/简短回复、system wake（3） | `inbox.py:246`；`src/personal_assistant/tools/inbox_result.py:9`；`global_run_coordinator.py:238`，目标/身份/原话/reply 保留；主模型与 classifier 共用应用说明 | `tests/unit/personal_assistant/test_global_query_tools.py:13`/`:186`；`tests/integration/test_global_gateway_runtime.py`；T3/T4 同范围/无关/部分同意与来源反例；不以第二 owner 入站 404 冒充 classifier 证据 | aligned |
| `gateway/global-agent.md:37` 等待与恢复：其他聊天继续、跨轮/重启/compact 回复、连续拒绝（3） | `product.py:202`；`auto_mode_gate.py:508`；`global_run_coordinator.py:216`；`_auto_mode_transcript.py:214`，无权限挂起/计数放行/历史复认证；按可见上下文续办 | `tests/unit/test_auto_mode_interaction.py:62`；`tests/integration/test_auto_approval_context.py:206`；global runtime/lifecycle；T3 等待 A 时 B 实际完成、T5 compact/重启证据 | aligned |
| `gateway/heartbeat-cron.md:7` 已配置任务与实时同意：Cron 工具、Heartbeat/后台通知、调度管理与任务动作、global Heartbeat 分流（4） | `message_context.py:29`/`:91`；`src/personal_assistant/tools/cron.py:340`/`:351`；`session_composition.py:93`；`auto_mode_gate.py:436`，完整调度参数、CC scheduled/system 来源、隔离 Cron 与复用 global Heartbeat 的路由一致 | `tests/unit/test_auto_mode_policy.py:92`；`tests/integration/test_auto_approval_context.py:161`；`tests/unit/personal_assistant/test_cron_tool_permissions.py:25`/`:35`；`tests/unit/test_auto_mode_interaction.py:26`；既有 Cron 3/3 与 Heartbeat 真故障 allow/deny/普通 global-child 对照 | aligned |

表内省略目录的源码沿用同行或本报告已给出的完整目录；测试与实现代码行号均针对本轮快照。共享 Scenario 复用同一层的长期回归，不为收尾文档增加重复测试。本轮只做文本/源码/断言对账以及文档与 diff 检查，未重跑 237 项、48 项或真实模型旅程。

### Uncovered Observable Behavior

None。按最终 unit diff 逐组核对：权限结果与原人工否决、Bash 行为、完整 policy/原配置、来源持久化与 provider 输出边界、SDK runtime 与 child 继承、Global Inbox/发送/恢复、Cron/Heartbeat 均由上述 delta 覆盖。内部 `LLMMessage` 来源字段与 `ToolResult.permission_context` 是这些行为的传递实现；Anthropic stop 映射用于已批准的两阶段机制，不新增产品选择入口。打包资产、固定依赖、参考 fixture 和 `e2e-up.sh` 隔离验收数据库/journal 同步重置不构成遗漏的产品运行契约。

未发现与 unit 首文档 R1–R6 或 design D1–D8 冲突。普通 full + targeted-closure 结论继续有效；本结论只准许将这六份最终契约增量交给 orchestrator 后续归并，不替代仍在进行的独立产品旅程验收。

首次对账时 `git diff --check` 通过，`./scripts/docs-check` 因 `implementation.md:38` 的 `acceptance.md` 尚未 tracked 而未通过。至 Round 3 快照，reviewer 已提交原始验收报告，文档检查恢复通过：244 maintained Markdown sources / 72 required routes。

Round 3 确认新增的目标存在性观察属于 `kernel/runs.md:25` 的当前工具动作描述细化，符合 design D2 新增说明；只附于当前动作，不进入历史 outcome 或宿主授权来源，不改变无人值守路由。六份 delta 字节均未修改，无新增 SDK 或产品配置入口，原 aligned 结论继续有效。

Outcome: **aligned**

# Round 3

## Summary

Mode: targeted-closure

Review round: 3

Prior verification: 本文件 Round 2 和 Corrected Delta Reconciliation

Validated at: `79c83080a50479776838ac4d62a1a2d8aa185e76`

Effective through: `79c83080a50479776838ac4d62a1a2d8aa185e76`

Executed base: `2fd84b9ac2b1949947ac899b3de7fea1488731ef`

Delta range: `7c9f5ee37bfdec983445f55610f2b8195d32fc65..79c83080a50479776838ac4d62a1a2d8aa185e76`

Focus issues: 产品 acceptance Round 2 I2 的实现修复——审批缺少当前 Write 目标存在性事实

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 目标存在性观察及当前动作传递已实现；原 milestone 覆盖结论保留 |
| Correctness | I2 的事实接线修复通过，新增 4 项参数化回归及原 gate/写入约束通过；真实 Cron 产品结果由 reviewer closure 判定 |
| Coherence | 符合 R1、R5 和 D2 的已记录细化；原两阶段、来源、路由与六份 delta 结论继续有效 |

Verdict: **pass**。0 CRITICAL / 0 WARNING / 0 SUGGESTION。

## Closure evidence

修复提交 `10bf12c446929aa02b9a22a5c01f26a7b1ae5f6b` 只修改 Write、共享 gate 及现有 dispatch 测试，另补 design D2 和 implementation 说明；随后 `79c83080a` 仅加入产品验收原始报告。独立 detached 签出并核对完整增量，未修改源码、测试或配置，未使用模型请求或生产服务。

| 核对项 | 实现与证据 | 结果 |
|---|---|---|
| 实际 cwd 与目标状态 | `src/agent/platform/tools/builtins/write.py:143` 优先读取 ToolContext cwd / HookContext metadata cwd；`src/agent/core/agent/runtime.py:481` 将真实 session workspace 放入该 metadata。`:162` 的 expanduser、cwd 和 resolve 与既有 `ToolSafety.normalize_path` 语义一致，观察存在性后仍返回 passthrough。 | 相对/绝对路径、存在/不存在四种组合都使用正确的实际目标；没有写入副作用。 |
| 状态进入当前动作且不变成许可 | `src/agent/platform/hooks/builtins/auto_mode_gate.py:584` 在已验证的动作投影后附上工具检查原因，再用原 `:303` 生成以当前 tool_use 结尾的 transcript；没有增添 history outcome、host_context 或 human 消息。 | `tests/unit/test_auto_mode_gate_dispatch.py:270` 四项均让真实 WriteTool 产生状态，并断言 S1/S2 均收到该状态、仍可 block、目标内容/不存在状态不变。 |
| 保留原工具门禁与实际写入约束 | 危险路径仍先返回 safety_check ask；共享 gate 的 allow/deny/ask 路由没有改动。`write.py:172` 后的实际 run 与 Read-Before-Write 代码没有改动。 | 原 dispatch 的直接允许/明确拒绝/必须人工/缺投影回归通过；`tests/unit/test_tools_write_edit.py:179` 起验证未读/陈旧文件拒绝、新文件创建、读后覆盖与后续自写。 |
| 原结论继续有效 | 本轮 diff 未修改 CC policy/scheduled 资产、两阶段参数、计数、身份来源、SDK/child 或入口优先级。目标状态说明明确限制为 permission-check time，不承诺审批后文件状态不变。 | 与 R1 已授权新建任务和 D2 动作描述一致；六份 delta 不需要为了该内部事实接线新增重复条目，corrected-delta 保持 aligned。 |

独立执行最窄相关检查：`tests/unit/test_auto_mode_gate_dispatch.py` **11 passed**；`tests/unit/test_tools_write_edit.py` **22 passed**，合计 **33 passed**。未重跑此前 117、237 或全量测试。`./scripts/docs-check`、`git diff --check` 通过。

本报告关闭的是 I2 所需的目标事实传递与约束保持核验；不把脚本分类器返回 block 的永久测试记作真实 Cron 已成功，也不把执行者的一次 Terra 请求回放替代 reviewer 的原失败入口 closure。acceptance 的最终产品 verdict 仍由 reviewer 更新。未扩展到其独立记录的 I3 通知路由旁支。

All checks passed. Ready for PR.
