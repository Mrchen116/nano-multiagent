# Codex 派发适配

以当前暴露的 collaboration 工具契约为准，不按历史版本推断能力。

- `spawn_agent` 创建后台子 agent，保存稳定 task_name/target；task_name 用小写字母、数字、下划线。
- `send_message` 发送消息；`followup_task` 让已有 agent 续跑；沿用已建立的上下文。
- 无独立工作可做时 `wait_agent` 等完成/attention 通知，不反复 list 或催进度；静默和超时不代表卡住。
- 模型与 effort 按下表由派发方选择。独立审查使用 `fork_turns: "none"` 和中性事实包；继承模型不等于复制主会话上下文。固定型号显式传 `model` 与 `reasoning_effort`，不要因省略参数继承主模型。
- worktree 生命周期由角色 owner 管理，不叠加自动 isolation。中断只用于真实失败/越界、用户要求或工作流停损，不因等待超时接管。

缺少必需的独立审查能力时报告具体阻塞，不静默变成自审或新造兼容协议。

## 执行任务的模型配置

用户明确指定优先；下表是 Codex 默认，不写进能力 skill。先按共享材料、工作量与独立性组合任务，再选能完成该组合的配置。

| 执行任务 | model | reasoning_effort |
|---|---|---|
| 首轮实施、架构/复杂调查、设计审查 | 继承主 Agent | 继承 |
| 代码与契约审查、非视觉 Context/旅程/性能判断、首文档审查 | `gpt-6.1-sol` | `high` |
| 单独的视觉/客户端体验观察 | `gpt-6-astra` | `low` |
| 视觉观察与代码/Context 深度判断合并 | `gpt-6-astra` | `high` |
| 具体候选的二次核验 | `gpt-6.1-sol` | `medium` |

不因能力名称不同强迫拆 Agent；合并需要较高配置时，结合共享证据收益和工作量决定是否值得，不默认升级所有审查。后续修复由主 Agent 完成。

派发前核对可用型号和 effort。固定配置用 `fork_turns: "none"`，继承模型也只交中性必要材料。指定型号不可用时报告差异，不静默换型。复用前确认已有 Agent 配置；无法满足本次任务时新建合适配置，仅交接目标、版本、问题和证据。按真实变化派发，不为报告到齐重新唤醒。
