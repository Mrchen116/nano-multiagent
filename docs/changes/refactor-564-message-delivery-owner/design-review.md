# Design Review — refactor-564-message-delivery-owner

## Round 1

### Metadata

- reviewer: `/root/design_review_564`（后续复审沿用）
- target: main `43a022558` 上冻结的 motivation.md、未提交 design.md 与 M1-delivery-owner/.gitkeep；候选代码只读基线 `6ee4c71ab`，位于 `.worktrees/preview-feat-563`。
- review_mode: full
- mode_reason: 首轮 Gate 2，覆盖完整需求、核心边界、共享接口、delta 和 milestone。
- started_at: 2026-09-16T12:05:00+08:00
- completed_at: 2026-09-16T12:11:00+08:00
- duration: 约 6 分钟（分钟级记录）

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING**。所有权方向合理，但完整候选接口、跨 run 终止边界与实际 delta 尚未收口，不满足 Gate 2。

### Coverage 与证据

以下源码路径均相对候选 checkout，非 main 已上线事实。

- **实际组装与单一 owner**：`src/personal_assistant/gateway/composition.py` 的 300、548、913、1035、1133、1265、1304 行分别连接内核回调、ImageReplyConnection、恢复、PaReplyDelivery、background delivery 与普通/global coordinator；设计所有权表及删除清单覆盖这些真实重叠入口。要求 composition 只接线，internal_dispatch 只适配、shadow 只恢复映射，普通/显式/恢复共用内部提交，足以约束避免只加 facade。此次不要求新增总线或另一数据库。
- **内核边界与来源**：`agent/core/agent/output.py:22-46` 的 BoundOutputControl 确实混合权限与输出提交；`agent/core/agent/loop.py:674-849` 确实根据 Gateway 交付状态改变 loop。撤回方向正确。`agent/core/agent/message_context.py:29-89` 已支持逐 part 的 context_origin；`personal_assistant/gateway/global_run_coordinator.py:242-261` 已有 system part 的 idle admission 真实使用。无需新 SYSTEM 枚举，也不应通过 append_message 代替运行调度。
- **权限接口可行性**：registry.evaluate_permission 的既有提取与 runtime._build_hook_context 可作为窄 SDK 能力基础；设计明确真实 session/runtime 上下文、权限请求通路、取消及 operation identity，不向 HTTP 暴露跳过审批标志。显式只审批一次、快照恢复不重新审批的界限合理。实现必须兑现已结束模型 run 下仍有效的产品取消门禁，这里不要求恢复输出回调。
- **候选与生命周期**：核对 loop 的 stream、message hooks、早启动工具与 turn_end，发现现有“message/group 完成边界”不能按当前描述直接复用，见 R1-W1。`session_run_coordinator.py:1680-1764` 现有路径在 kernel terminal 后关闭 active handle 并最终发 completed；设计已识别需要以逻辑请求延长生命周期，但修正次数边界尚缺，见 R1-W2。
- **用户约束与迁移**：motivation 的 Runtime、workspace 内外图片、多轮图文、私有反馈、停止/新输入、离线先飞书后 IM、删源恢复、ACK 不确定要求均映射到设计。保留已批准快照、原输出身份和每目标回执可避免重生成副本；不承诺跨服务 exactly-once 是准确边界。未合并候选替换、不操作生产、最终待审 PR、不合并/部署均保留。
- **delta / canonical target**：读了 main `docs/specs/kernel/runs.md`、`docs/specs/gateway/global-agent.md` 及旧候选 `docs/changes/archive/feat-563-device-context-image-delivery/specs/`。当前新 unit 没有 specs delta，不能核对 canonical requirement/scenario 替换完整性，见 R1-W3。
- **milestone 与验收前置**：单 M1 与 `.gitkeep` 符合设计阶段，不要求提前写 tasks/progress；退出标准覆盖 owner 入口、竞态、权限、恢复、真实产品及全量测试。无布局改动，无 prototype/must-match 新增要求；现有隔离脚本、LLM 代理及专用飞书授权由派发上下文与设计明确，验收时仍需记录真实证据，不能用旧候选通过替代本次验收。

### 历史问题闭环

首轮，无历史问题。

### Issues

#### R1-W1 — 完整候选的事件边界仍为待调查分支

- 位置：`design.md:46`。
- 证据：候选 `agent/core/agent/loop.py:533-571` 为同一 LLM stream 的各 chunk 分配不同 message_id、共用 group_id；`_dispatch_message_hooks`（1000-1055 行）对每条 chunk 派发 message_end。工具从 stream 内 `executor.add_tool`（约 627 行）即可开始；工具事件不保证在最后一个正文 chunk 之后。turn_end（964-991 行）在整个 AgentLoop 收口后才发，并非每次 LLM call 边界。因此“message/group 完成边界、工具边界冲刷；若不足再补事实”尚不是可执行的已定稿决定。
- 未修后果：按 message_end/tool_start 冲刷会将分片图文提前发布或误报缺图；等整个 turn_end 则把多模型轮候选合并/延迟，破坏每个实际输出一次及多轮工具过程语义。
- 收口要求：选定一种准确方案，写清每次模型轮结束事实或已存在等价事件的名称、真实 identity、完整/异常/取消语义及生成位置；说明 group revalidation 聚合事件与普通聚合如何避免再次重复。只需接口/时序，不要求实现代码。

#### R1-W2 — “沿用产品现有预算”缺少实际可复用的跨 run 终止策略

- 位置：`design.md:63-67`。
- 证据：现有 `agent/core/agent/loop.py:377-389` 在每次 loop 新建 api_round_count 并用 max_turns 约束本 run；SessionRunCoordinator 和 GlobalRunCoordinator 的既有 admission/stop 机制不是交付修正次数预算。设计选择失败后新建同 session run，但未指明可复用的请求级预算对象、剩余额度或终止计数归属。
- 未修后果：模型每轮继续引用同一缺图时，每次新 run 都重置 loop 预算；“反馈去重”按候选 identity 又无法消除不同 run 的新失败候选，可能持续自启动且逻辑请求永不完成。
- 收口要求：明确一个最小、可验证的产品请求级修正上限/已有预算传递方案，指出由谁持有及何时终止；额度耗尽时用户气泡/请求如何真实结束，停止/reset 如何清除，后续真人输入是否开始新预算。不要新增通用调度平台。

#### R1-W3 — 缺少本轮受审 delta，旧 SDK 业务契约尚未被可审材料替换

- 位置：`design.md:85-87`；新 unit 缺少 `specs/`。
- 证据：`docs/development/change-workflow.md:108-109` 将 canonical delta 与 milestone 列为设计产物。旧候选 `specs/kernel/runs.md` 明确要求产品输出回调、同 run 继续与已交付/部分/未知内核状态，均与本设计冲突；新 design 仅承诺“delta 在实现前明确”，目前没有替换文本。旧 Gateway delta 还含 MODIFIED requirements，不能仅概述保留原需求就保证原 Scenario 不丢失。
- 未修后果：实施/归并者仍可能保留旧 callback 契约，或者撤回时连同合法 Runtime、图片与来源场景一并漏掉；新增通用权限及可能的模型轮事实也没有消费者可验收契约。
- 收口要求：提供本 unit 的具体 delta 或精确引用仍生效旧 delta 的清单，明确 canonical target、保留/撤回项；新增窄 SDK 行为写成消费者契约，MODIFIED 保留未改变 Scenario。只审最终仍成立的行为，不把 Gateway 实现状态重新写进 kernel spec。

### Recommendations

无额外建议；关闭上述实际缺口即可，不扩展重构范围。

### Author Resolutions

- R1-W1 accepted：明确新增产品无关 model_round_end，指定run/group身份、正常/空/异常语义与在现有group复核之后、下一模型轮之前的发出位置；Gateway仅此边界冲刷，message_end/tool_start不作为轮结束。
- R1-W2 accepted：明确coordinator请求级最多两次反馈准入，首次修正、再次只作文字说明；计数/稳定submission保存，busy不消耗、停止重置撤销，最后仍失败如实结束而不强发/无限运行。
- R1-W3 accepted：新增kernel/runs与gateway/routing-delivery具体delta；精确撤回旧候选SDK业务回调要求，增加通用轮结束事实/权限接口，逐项保留原Runtime、统一图文、relay与Web IM契约。

## Round 2

### Metadata

- reviewer: `/root/design_review_564`（同 Round 1）
- target: main `43a022558` 上冻结的修订 design.md、新增 specs/kernel/runs.md、specs/gateway/routing-delivery.md，以及未改变的 motivation.md、M1 骨架。
- review_mode: full
- mode_reason: 新增中立模型轮共享事件、明确跨 run 请求预算并补齐消费者 delta；这些涉及共享接口和生命周期，不仅是旧问题的措辞闭环，因此重新覆盖完整设计。未变化源码 grounding 沿用 Round 1，并复查相应 loop/SDK 准入位置及旧候选全部 delta 标题/Scenario。
- started_at: 2026-09-16T12:13:45+08:00
- completed_at: 2026-09-16T12:14:02+08:00
- duration: 17 秒

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。R1-W1、R1-W2、R1-W3 均关闭。此结论只批准冻结设计进入实施，不代表实现、测试或真实产品验收已通过。

### Coverage 与证据

- **现状与实际接线**：retained_from: Round 1。候选仍为 `6ee4c71ab`，普通/global/background、ImageReplyConnection、PaReplyDelivery、recovery 的真实 composition 入口未改；设计仍要求迁移正文决策而保留协议能力。没有将多条旧路径套进新 facade 的设计退让。
- **完整候选与共享接口**：重新核对候选 `agent/core/agent/loop.py:850-965` 的复核后 retry/terminal 分支。设计 `46-48` 行现在指定每次 LLM 轮在工具结果及原 group 复核处理后、下一轮之前发一次中立事实；Gateway 只按该事实冲刷同 group 正文，既不以 tool_start/message_end 推测结束，也不从 withheld draft 重建公开候选。该事实不 await 产品处理且没有渠道字段，因此保留库/产品依赖边界。异常/取消不构造完整正文，空轮不产生 delivery；现有 turn_end 继续承担整个运行终结。
- **调度、权限和来源**：retained_from: Round 1 的 message_context、runtime 权限构造与产品 admission grounding；本轮复查 `agent/sdk/kernel.py:1841-1885`，try_submit_idle 具有 busy 零副作用、稳定 submission 收据复用，能承接设计新增的请求级计数语义。修正运行仍经原 coordinator，system part 不变成真人授权；准备/提交权限与停止代次继续由真实上下文和 Gateway admission 约束。
- **用户约束及数据流**：重新通读全设计。普通、显式、恢复继续共用 MessageDelivery；未发布错误走有限模型反馈，部分/未知走原身份对账；快照不重读源文件、飞书先交付/IM 后补、成功目标不重发仍保持。新增上限只约束自动修正，不改变明确已成功消息；取消和新输入优先，不会以反馈启动无限链。
- **delta 与消费者视角**：新 kernel delta 明确以包含旧候选的集成树为替换基线，精确 REMOVED 旧业务回调 requirement、保留 main 原运行/复核能力，并 ADDED 中立轮事实与不执行工具的权限检查。新 gateway delta 完整保留原恢复 requirement 的三个 Scenario 并补有限修正/停止；精确指名保留旧 routing-delivery 的 Runtime 与统一图片两个 requirements，以及 relay-protocol、im/web-chat-ux 全部 delta。已对照候选归档 delta 的 requirement 和 Scenario 清单，无漏删未改变场景。两文件路径分别映射 canonical kernel/runs、gateway/routing-delivery，SDK 中没有重新引入业务送达状态。
- **milestone、验收和交付**：retained_from: Round 1。单 M1 的统一入口、竞态、权限、多轮工具、恢复及真实 Web/专用飞书验收范围未缩减；新增完整轮和有限修正属于相应退出标准内的实现/验证要求。没有布局变化，无新增 prototype/must-match；隔离验收前置保持，最终全量测试和独立实现/代码/产品门禁仍必须完成，不合并、不部署。

### 历史问题闭环

| Issue | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R1-W1 | accepted：明确 model_round_end 身份、时序与正常/异常语义 | design.md:46-48；kernel delta「消费者能够观察完整模型轮的结束」；loop 复核后/下一轮前确有可插入中立事实的位置 | closed |
| R1-W2 | accepted：请求最多两次反馈，持久计数和稳定 submission，最后如实终结 | design.md:64-71；gateway delta「有限修正与停止」；try_submit_idle 收据和 busy 行为支撑不重复扣计数 | closed |
| R1-W3 | accepted：新增两份 delta，撤回旧 SDK 业务契约并保留其余场景 | 新 specs/kernel/runs.md、specs/gateway/routing-delivery.md，与旧 feat-563 四份 delta 的实际要求名/场景核对一致 | closed |

### Issues

无。

### Recommendations

无。

## Round 3

### Metadata

- reviewer: `/root/design_review_564`（沿用 Round 1–2）
- target: `.worktrees/unit-refactor-564`，HEAD `150fbe30d`；design.md 的 Changelog/权限澄清与 specs/kernel/runs.md 的宿主操作 Scenario。
- review_mode: delta
- mode_reason: 本次是已批准权限接口的有界、兼容性来源说明扩展；不改变调用方准入、返回值、权限策略、交付 owner 或 milestone。按派发范围核查这项澄清及其来源/权限波及面，源码只用于确认方案接线与可行性，不执行完整代码审查。前轮全局设计结论保留。
- started_at: 2026-09-16T13:10:25+08:00
- completed_at: 2026-09-16T13:10:47+08:00
- duration: 22 秒

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。宿主操作说明修正了权限分类所观察的动作身份，没有形成权限豁免，也没有把渠道交付状态引回内核。结论仅覆盖本轮设计 delta，不代替代码 review、测试和产品验收。

### Coverage 与证据

- **实际触发与接口落点**：设计 Changelog 明确本次针对普通回复被误判为调用 send_message 的验收问题；`src/personal_assistant/gateway/delivery_permission.py:48-60` 确认 Gateway 仍复用 send_message 策略和真实 target/text，但从宿主接线传入固定普通回复说明。它是对动作事实的纠正，不是从用户正文推断批准。
- **信任与数据流**：`src/agent/sdk/kernel.py:2214-2250` 将可选 operation_description 作为独立 SDK 参数；`src/agent/core/agent/runtime.py:390-412` 将其写入 typed HookContext 字段，再沿原 registry.evaluate_permission 执行。`src/agent/platform/hooks/builtins/auto_mode_gate.py:318-342` 仅从该字段构建 host_operation，保留 permission_policy 与完整 proposed_action；不会从 arguments 或 session metadata 取同名字段。可选参数为空时维持原投影。SDK 接收消费者描述，未内置普通回复/图片/渠道特判。
- **权限与消费者契约**：新 kernel delta 的「宿主操作与模型工具调用可区分」锚定既有通用权限 requirement，旧两项 Scenario 保留；说明不是授权、不改变拒绝/审批规则及模型不能伪造的约束明确。对照 `tests/contract/test_sdk_tool_authorization.py` 的受限范围测试定义，可观察的检查点覆盖 classifier allow/deny、target/text/image sources 完整投影、伪造 arguments 不升级及显式 tool policy deny 不被绕过。本 reviewer 未运行这些测试，不以测试定义冒充通过证据。
- **此前实施澄清的相容性**：design 的 context_revision/pending_ids 说明继续使用内核已提供的输入身份事实，公开准入由 Gateway 决定；权限事件 pump 只呈现同 run 审批、去重并随撤销取消，不成为第二条正文 owner。它们与本次操作说明不改变彼此权责；本轮不重复认证其实现或已报告代码验证。
- **保留范围**：retained_from: Round 2。单一 MessageDelivery、有限修正、快照/回执恢复、系统来源、完整轮聚合、canonical delta 保留清单、M1 退出标准、真实验收前置及不合并/部署边界未因本次澄清变化。无新增布局、prototype 或跨包业务状态。

### 历史问题闭环

R1-W1、R1-W2、R1-W3 在 Round 2 已关闭；本次未改变其解决决定，保持 closed。Round 2 无开放问题，本轮无新 Author Resolution 待核。

### Issues

无。

### Recommendations

无。
