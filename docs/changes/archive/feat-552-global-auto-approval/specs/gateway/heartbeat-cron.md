# Heartbeat and Cron — feat-552 delta

目标：`docs/specs/gateway/heartbeat-cron.md`。依据 design D1/D4/D6。

## ADDED Requirements

### Requirement: 自动任务执行保留配置任务与实时人工同意的区别

#### Scenario: Cron 触发后执行工具
- **WHEN** 定时或原生 run 操作启动已保存的 Cron 任务
- **THEN** 主模型及 Auto transcript 收到固定 CC scheduled 标记和完整说明；任务作为已配置任务执行，触发本身不是用户实时输入或新的人工同意。

#### Scenario: Heartbeat 与后台通知
- **WHEN** 周期唤醒、任务完成或失败信息进入会话
- **THEN** 使用 CC 系统通知说明，不能充当待确认问题的回答；与真人同轮到达时各段保持来源。

#### Scenario: 创建任务与任务内动作
- **WHEN** Agent 管理产品内置 Cron 或执行任务内工具
- **THEN** 审批取得调度操作的完整参数（包括实际 schedule/payload），不裁剪为摘要；调度操作使用已映射的 CC 例外，任务内动作继续走共享 Auto。
- **AND** Cron 继续使用隔离 session，不因所属 Agent 为 global 就取得主会话交互选择；原无人值守 fallback、投递与不补跑行为不变。

#### Scenario: 全局 Heartbeat 与普通全局运行区分交互
- **WHEN** Heartbeat 复用全局主 session，且审批没有有效结论或达到拒绝阈值
- **THEN** 仍按原无人值守 fallback 处理：显式 allow 可执行，默认/显式 deny 不执行，结果区分配置决定与模型判断
- **AND** 提交前的共享 runtime 刷新保留全局主 session 的交互选择，但它不覆盖本次 Heartbeat 的实际自动入口；仅读取恢复绑定不重配忙碌运行。
- **AND** 普通 global wake 与 global child 仍把未获准原因返回主 Agent；不能只凭 session 归属或 BACKGROUND_TASK 枚举混用这两类交互。
