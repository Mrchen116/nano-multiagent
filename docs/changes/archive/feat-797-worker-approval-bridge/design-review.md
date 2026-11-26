# feat-797 设计审查

## Round 1

- reviewer：独立 design_review Agent，审查对象为 unit/feat-797-worker-approval-bridge 的 4ea1cb730。
- review_mode：full。首次 Gate 2，覆盖首文档、设计、两份 delta 和 M1。
- started_at：2026-11-27T00:31:20+09:00。completed_at：2026-11-27T00:33:52+09:00。duration：2 分 32 秒。
- Verdict：Issues Found。0 CRITICAL / 3 WARNING。

### Coverage

- 切法 A 与主人私聊已收口。业务问题交回绑定父级，Codex/Claude 内置 Auto 的升级直接走人工分流，Antigravity 单次调用宿主 Auto，人工答案只解锁原活动调用。仅有持续授权的协议走拒绝，取消、超时、退出和重复答复均有终局。三驱动真实组装位于 `local-workers/manager.ts` 的 `activate` 和 `local-workers/drivers.ts`；父级回报进入 `packages/dsh-integration/src/index.ts` 中的 LocalWorkers 回调。精确宿主 MCP 绑定可留在 integration 内，未增加运行时依赖方向。
- 原生审批在 `packages/dsh-integration/src/index.ts` 的 `approval/request` 中排除 Global；Node 的 `runtime-partitions.ts` 已按 requestId 转回所属进程。现有 PA `single-thread.ts` 的审批绑定到当前输出；IM 建卡及答卡分别在 `chat-streaming.ts` 和 `conversation-actions.ts` 限制 single_thread。设计采用独立消息，服务端解析 owner、核对参与者与生命周期，能跨越根 turn 结束并复用现有答卡入口。M1 为单一组装，无相互竞争的实现里程碑。
- Gateway MODIFIED 保留了默认规则、证据处理、原生子 Agent 与策略切换等同级场景。IM ADDED 将主人与一般 Work 观察者区分；换成另一种 pending 存储也能满足两份 delta。另有一处现行 channel 契约须限定，见 R1-W3。
- Context 与前端按设计模式核实。已核对最终用户、父级与审核模型各自需要的来源和结果；待决卡可以复用双方既有控件，当前没有需要 HTML 原型才能决定的布局。分 CLI 的协议 fixture、真实 IM + 临时库适合覆盖单次答复和身份拒绝。尚未运行新实现，跨根轮次证据与卡片终态的判断限于以下源码和设计。无一次性迁移。

### Issues

- **R1-W1 · Antigravity 的授权证据需关联到具体委派。** `design.md` “协议与生命周期”冻结了值守状态，规定审查开始后证据变化使结果失效，却未说明派工到审查开始之间根会话已经处理其他聊天时，如何辨认本次委派的原始人类依据。现有 `policy/codex.ts` 的 `review` 按传入的父会话与原生 callId 取 history，`policy/sources.ts` 的 `transcript` 也这样读取；外部请求没有根会话内对应的原生 tool call。`humanInputs` 则仅选最近一次根 turn 开始后的输入。直接复用其中任一入口均不能证明后来的其他聊天是该委派的授权。设计需交代受托来源的定位、相关修订或撤回如何生效、来源不足如何分流。M1 用“聊天甲派工，根处理聊天乙，旧 Worker 才请求”的模型实际出站输入核对授权归属，并核对证据变化后的结果。
- **R1-W2 · 独立消息需要可辨认的终态。** `design.md` “主人私聊卡”复用现有 Web/iOS 展示且建独立消息。Web 的 `components/message-pane.tsx` 过滤 resolved，`permission-card.tsx` 收到 resolved 也直接返回空，原生工具审批靠关联的工具行显示已授权或已拒绝。新消息没有这种工具行。原样复用时，主人答卡或请求超时后，刷新聊天就无法从该条消息知道哪项请求如何结束。iOS 的 `ChatMessageView.swift` 只把 resolved 和 submitted 当作专用状态，其他值走选项分支。补充独立消息在放行、拒绝、取消或过期后的可见内容和无按钮行为，允许用现有消息正文或对应卡状态实现。M1 从代表性客户端完成一次答卡与一次取消或超时，回看历史核实终态；如沿用 iOS 原组件，同时核对实际状态值可正确展示。
- **R1-W3 · 飞书审批回原聊天的现行契约需要 Worker 例外。** `docs/specs/gateway/external-channels.md` 的“外部 channel 用户可见控制与后台文本投递”明确将权限卡和完成状态列为飞书触发时须回原 chat 并同步 shadow 的事项；当前两份 delta 未限定该条。飞书群触发 Global 再委派时，依此执行会把主人私聊审批投往群内。`packages/personal-assistant/src/external.ts` 也确有按输出转发 permission_request 和 permission_resolved 的路径。补充该 canonical 的有界 delta 或等效的限定，保留普通渠道审批场景，并把飞书来源的 Worker 请求及其终态仅在主人 Nano IM 私聊出现纳入投递验收。

无历史问题待核销，无额外建议。

### Author Resolutions

- R1-W1 accepted。设计明确派工证据快照、后续限制及出站验证。
- R1-W2 accepted。结案写入独立消息正文，保持 resolved 以及历史可读。
- R1-W3 accepted。新增 external-channels delta，并验收飞书来源的私聊投递。

## Round 2

- reviewer：独立 design_review Agent。审查对象为 `6cb490e18`。
- review_mode：delta。修订增加了外部渠道 delta，并调整派工证据归属、既有审批卡终态及对应的 M1 验收。retained_from: Round 1；用户选择、三种驱动的单次决策、私聊身份校验、跨包职责与里程碑拆分沿用 R1 的覆盖证据。
- started_at：2026-11-27T00:35:01+09:00。completed_at：2026-11-27T00:35:33+09:00。duration：32 秒。
- Verdict：Approved。0 CRITICAL / 0 WARNING。

### 历史问题闭环与变化证据

- **R1-W1 closed。** Author Resolution 接受派工证据快照。`design.md` 将现场取证绑定到派工根 turn、调用与宿主所见原话，保留 Inbox 的发送者、目标及消息 ID，明确后续聊天只能提供约束。作用域不清有人工或拒绝分支，并在决策返回与审计写入后复核。相比 R1 所查 `ApprovalSources.humanInputs` 的最近轮语义，M1 现用甲派工、乙后到的实际出站输入以及审查期间撤回来检验两类证据。
- **R1-W2 closed。** Author Resolution 接受同一消息写入结案正文。设计以 resolved 收起操作，消息正文保留 Worker、动作和实际终态。核对 Web 的 `message-pane.tsx:3005` 及 iOS 的 `ChatMessageView.swift:351`，该方法兼容 Web 过滤已决控件和 SwiftUI 的已决展示分支。M1 增加代表性客户端答卡、取消后重读历史，覆盖具体用户操作。
- **R1-W3 closed。** Author Resolution 接受飞书来源隔离。新增 `specs/gateway/external-channels.md` 限定了外部 Worker 请求和终态的唯一目的地。逐字对照 canonical 的同名 Requirement，原正文及 15 个既有 Scenario 均保留；原生审批的回原聊天语义继续成立。M1 已包含飞书来源隔离。

本轮为设计复审。实际审核请求、客户端展示和端到端投递由 M1 验证。
