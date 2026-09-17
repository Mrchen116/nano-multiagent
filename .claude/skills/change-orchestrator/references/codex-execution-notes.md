# Codex 派发适配

以当前暴露的 collaboration 工具契约为准，不按历史版本推断能力。

- `spawn_agent` 创建后台子 agent，保存稳定 task_name/target；task_name 用小写字母、数字、下划线。
- `send_message` 发送消息；`followup_task` 让已有 agent 续跑；沿用已建立的上下文。
- 无独立工作可做时 `wait_agent` 等完成/attention 通知，不反复 list 或催进度；静默和超时不代表卡住。
- 模型与 effort 按下表由派发方选择。独立审查使用 `fork_turns: "none"` 和中性事实包；继承模型不等于复制主会话上下文。固定型号显式传 `model` 与 `reasoning_effort`，不要因省略参数继承主模型。
- worktree 生命周期由角色 owner 管理，不叠加自动 isolation。中断只用于真实失败/越界、用户要求或工作流停损，不因等待超时接管。

缺少必需的独立审查能力时报告具体阻塞，不静默变成自审或新造兼容协议。

## 角色模型表

用户明确指定优先；以下是 Codex 的默认映射，不修改主 Agent 配置。

| 子任务 | model | reasoning_effort |
|---|---|---|
| 首轮实施、专项架构分析/复杂根因调查 | 继承主 Agent | 继承 |
| `change-design-reviewer` | 继承主 Agent | 继承 |
| `change-spec-reviewer`、`change-code-review`、`change-verifier` | `gpt-5.6-terra` | `high` |
| 候选问题二次核验 | `gpt-5.6-sol` | `medium` |
| `change-reviewer` | `gpt-6-astra` | `low` |

后续修复由主 Agent 直接完成，不派修复子任务。代码审查与一致性验证合并派发时仍使用 Terra/high；不同档位的职责分开派发。

派发前核对工具支持的型号和 effort。继承档可省略覆盖字段；固定档使用 `fork_turns: "none"` 或工具允许的有限历史，不能用禁止模型覆盖的完整历史 fork。指定型号不可用时报告差异，由用户决定替代，不静默换型或升级。

复用前核对已有 Agent 的实际模型与 effort。若 `followup_task` 无法覆盖不匹配的旧配置，创建符合本次职责的新 Agent，仅交接目标、版本、历史发现与证据位置；不要仅因旧 Agent 还在就沿用其模型。
