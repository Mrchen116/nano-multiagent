# Workflow：多 Agent 协作任务

Workflow 用多个相互隔离的子 Agent 处理一项明确的大任务：例如并行调研后综合、从多个角度审查变更，或分阶段迁移和验证。它适合需要覆盖面、交叉核验或单个上下文难以容纳的工作；普通问答和小修改通常不需要它。

Workflow 会消耗比单次聊天更多的模型资源。因此 Agent 只会在你明确要求时使用，不会因为任务“看起来复杂”就自行启动。

## 启用与启动

1. 在 Agent 的设置中启用 `Workflow` 工具并保存。它从该 Agent 下一轮新回复开始生效；未启用时，Workflow 命令和 `ultracode` 都不会出现。
2. 在聊天中直接说明意图，例如“用 Workflow 研究这个问题”“让多个 Agent 并行审查这组改动”或“用子 Agent 编排完成”。这让 Agent 可以据此规划并启动 Workflow。
3. 在输入框输入 `/` 可查看当前 Agent 提供的 Workflow 命令。`/deep-research <问题>` 是内置的深度调研 Workflow；已保存、对当前 Agent 可用的 Workflow 也会显示为各自的 slash 命令。实际列表以面板为准。

启动时若当前权限设置要求确认，聊天中会出现与其他工具相同的批准卡。允许后才会创建后台运行；子 Agent 后续需要批准的工具，也会回到发起这项 Workflow 的同一聊天。

## 运行期间与完成后

Workflow 在后台运行。启动消息里的工具行显示“已启动”只表示编排已创建，并不表示任务已经完成。

- 输入 `/workflows` 查看当前会话的运行列表。
- 输入 `/workflows <run-id>` 查看一个运行的阶段、子 Agent、结果、错误、耗时、资源使用和诊断信息。
- 需要控制时使用 `/workflows <run-id> pause`、`resume` 或 `stop`；可以用 `/workflows <run-id> restart <agent-call-id>` 重启一个子 Agent。
- 完成、失败或停止时，Agent 会在原聊天发送一次普通总结。Web IM 的同一消息“过程”区域可展开查看原始结果、错误、run/task 标识、资源使用和恢复提示。

Workflow 不会为每一个中间子 Agent 消息刷屏；运行中想了解进度时，使用 `/workflows` 查询即可。页面也不会新增独立的 Workflow 面板，所有信息仍在原聊天、工具行和权限卡中。

## 保存与复用

已完成或正在运行的编排可以保存为可复用命令：

- `/workflows <run-id> save project [名称]` 保存到当前项目范围；
- `/workflows <run-id> save personal [名称]` 保存到个人范围。

保存后，名称会作为 slash 命令出现在可用它的 Agent 聊天中。保存并不自动执行；仍需由你选择或输入该命令。

## `ultracode` 与规模

当 Agent 启用了 Workflow，且当前模型支持 `xhigh` 推理档位时，`/effort` 候选会额外提供 `ultracode`。

- `/effort ultracode` 为**当前会话**打开高强度的持续 Workflow opt-in：后续实质性任务默认优先采用多 Agent 编排，因此会带来更高的时间和模型成本。
- 选择任一普通 `/effort <档位>` 会关闭该会话的 ultracode 模式；新会话也从 Agent 的默认设置开始。
- `/config workflowSizeGuideline <unrestricted|small|medium|large>` 可设置 Agent 后续 Workflow 的规模提示，未设置时为 `medium`。它是对编排规模的引导，不会替代你的明确 Workflow 授权。

群聊中从 slash 面板选择某个 Agent 的 `/effort ultracode` 候选时，选择显示该 Agent 来源的一项；输入框会保留对应的 @Agent 指向，避免把这一会话设置发送给群内其他 Agent。
