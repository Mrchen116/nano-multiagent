# DSH 插件扩展调查

日期：2026-10-13。状态：设计输入；不是 Gate 2 通过的方案，也不是实现或验收证据。

## 用户约束与结论修正

用户明确要求不修改 DSH 代码仓，并要求先学习其“一切皆插件”的设计。此前把默认轨迹组件没有专用控制参数推导成必须扩展上游，是错误的推论。

DSH 的默认 UI 也是插件。Nano 可以通过公开的事件、服务、projection、store 和 slot 接口实现自己的能力，并按需替换默认 UI 插件。**不改上游、不 fork、不 patch、不使用私有导入**仍是本项约束。

需要分清两个命题：插件可以实现本项产品能力；当前默认轨迹视图是否已向其他插件公开全部所需的局部扩展点。前者成立，后者不能由“一切皆插件”直接推导。

## 核对基线

- Nano 锁定的运行时及查看器依赖：`0.2.1-alpha.1`。
- 本地 DSH 只读参考源码：`5badb15009ae1756c3afe0ae0cef1faafc290ccc`。
- 核对了已安装 npm 包的公开 exports、类型声明及默认视图源码。没有修改参考仓、依赖包或构建后的官方 bundle。
- 官方文档：[Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)、[Cordis primer](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cordis-primer.md)、[Slots](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/slots.md)、[Conversation](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/conversation.md)、[Session](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/session.md)。这些 master 链接可能变化；实现判断以当前锁定依赖为准。

## 已确认的公开能力

| 扩展面 | 当前证据 | 对 feat-589 的含义 |
|---|---|---|
| Cordis plugin、service、effect 生命周期 | architecture、Cordis primer | 能力由插件声明、注入和释放，新增产品观察能力不需要修改内核。 |
| `subagent/start`、`subagent/end` | `@deepseek-ai/dsh-subagent` 公开 `SubagentRunInfo` / `SubagentRunEndInfo` | `runId` 对应一次 one-shot run 或 continuable residency epoch，结束事件带真实 `stopReason`。不能把启动工具返回当作结束。 |
| 可扩展 Session 事件与 projection | Session 文档的 `SessionEventMap` declaration merging、`session.append()`；公开 projection registry | 插件可定义自己的持久事实与确定性读模型。新增事实必须带自身类型，不伪造原生工具、输入或模型事件。 |
| 视图 slot | `conversation.view` 为 session scope 的 list，按 `id` 定址，支持 priority 遮蔽 | 插件可新增自己的视图，或有意替换默认 `trajectory` cell；没有要求修改默认插件源码。 |
| 视图数据与状态 | `useTrajectory`、`useSession`、`useProjection`、注册项 `store` / `inject` | 自有视图可以消费官方数据模型，显式持有执行范围、选择、缩放和导航栈。数据模型复用不等于默认 UI 内部状态可控。 |
| scope 与所有权 | `SessionProvider`、slot children 的单 owner 约束 | 按 session 绑定数据；组件只通过自己声明的 child slot 组合 UI，不能绕过所有权抓取内部组件。 |

## 默认轨迹视图的确切限制

锁定版本的 `@deepseek-ai/dsh-client-ui-trajectory/client` 公开 `apply`、依赖声明及轨迹数据类型，没有导出 `TrajectoryView`、`TrajectoryTimeline` 或记录检查器组件。

默认视图注册 `conversation.view` 的 `trajectory` cell，目前声明的 child slot 是 `conversation.trajectory.images`，没有公开记录行附加入口。`ConversationViewRequest` 在该视图中把 `focus` 解释为工具 `callId`；它不是任意 seq 区间或可恢复视图状态。

区间选择、缩放、搜索、折叠和选中记录分别保存在默认组件内部。原有 Nano 宿主只保存数值滚动书签、行选择与详情 tab，切换 session 时重建 iframe。保留已挂载父视图能保留其现有内存状态，但单独这样做仍不能增加行内入口或自动选择区间。

因此以下做法不能作为已成立的公开插件方案：修改 slot registry 中的组件对象、依赖私有 React state、模拟鼠标拖选来驱动内部状态、把 Nano 记录伪装为原生工具事件，或复制上游私有组件作为本地 fork。

## 可评审的方案选择

| 方案 | 能完成什么 | 成本与约束 |
|---|---|---|
| Nano 自有轨迹视图插件 | 自己拥有行内发起入口、区间、缩放、选择和逐级返回；通过官方数据模型保留完整检查能力。 | Nano 需要维护受影响的 UI。需逐项兑现原生输入、模型请求、工具、system、thinking、compaction、图片、raw/source、schema、请求选项、usage/timing、搜索、折叠和时间概览；不能用简化事件列表冒充等价交付。 |
| 保留默认轨迹插件，只增加外部导航壳 | 可以保留官方完整视图、显示真实运行关系，以及通过保留挂载恢复父视图。 | 当前公开接口不足以完整兑现 R1 行内发起入口与 R2 原生区间自动选择。选择此方案需先明确调整产品验收，不能在实现中暗降范围。 |

用户已确认产品目标并授权 Agent 决定技术路线。选择自有导航视图插件，复用官方轨迹数据并并列保留官方完整检查视图；受控区间只属于 Nano 导航视图，不宣称改变了默认官方时间线内部状态。完整体验及维护边界由后续 design 明确，既定验收目标不降级。不修改 DSH 上游。

## 与视图选择无关的运行事实设计

运行事实插件放在 `packages/dsh-integration`；后端依旧只有该包 import DSH 公开 exports。PA、Channels、IM 仅消费产品 DTO，浏览器扩展留在已有隔离查看器边界。

身份至少包含父 session、子 session、真实 `runId`、发起来源和用途。主动工具调用保存真实 `callId`；后台维护由现有 knowledge runtime 显式提供 `memory` / `skills`，不解析 `nano-review:<UUID>`。fork 方式取真实 descriptor / provider 事实。

需要在实施前验证的准确性约束：

1. `subagent/start` 是 observe-only 边沿，不携带起始 seq；one-shot 与 continuable 的发布时机不同。不能简单在该回调里用“当前最新 seq”当作所有执行的开始。应结合公开 agent 创建、子日志事件与发起上下文取得真实边界，并用并行及重复唤醒用例证明。
2. continuable 的 run 是 residency epoch，不自动等同于每一条发给子 Agent 的消息；唤醒与驻留期间继续收信必须区分。产品“同一会话再次唤起”需映射真实 epoch。
3. 结束状态取 `subagent/end`，尾部记录边界取对应子执行实际产生的日志；子对象释放前后不能丢失尾界。
4. 重启后只有 start 而没有 end 的历史不能被标作仍在运行或成功完成；显示结束未知／更新中断，保留已知记录。
5. 记录及刷新读取沿用固定 root 授权和父链验证，不因新增导航而取得启动、取消、审批或聊天附件权限。

以上是调查时形成的约束；现已纳入 [design.md](design.md)、delta-spec 与交互原型。运行事实尚待实施验证；独立 Gate 2 状态以 [design-review.md](design-review.md) 最后一轮为准。
