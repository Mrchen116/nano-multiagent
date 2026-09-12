# Verification Report: feat-552

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
