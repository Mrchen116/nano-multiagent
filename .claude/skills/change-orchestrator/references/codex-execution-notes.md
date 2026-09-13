# Codex 派发适配

以当前暴露的 collaboration 工具契约为准，不按历史版本推断能力。

- `spawn_agent` 创建后台子 agent，保存稳定 task_name/target；task_name 用小写字母、数字、下划线。
- `send_message` 发送消息；`followup_task` 让已有 agent 续跑；沿用已建立的上下文。
- 无独立工作可做时 `wait_agent` 等完成/attention 通知，不反复 list 或催进度；静默和超时不代表卡住。
- 实现可继承必要上下文；独立审查使用 `fork_turns: "none"` 和中性事实包。模型/effort 默认继承当前设置；用户要求覆盖时遵守工具对 fork_turns 和可用模型的限制。
- worktree 生命周期由角色 owner 管理，不叠加自动 isolation。中断只用于真实失败/越界、用户要求或工作流停损，不因等待超时接管。

缺少必需的独立审查能力时报告具体阻塞，不静默变成自审或新造兼容协议。
