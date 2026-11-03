# Gateway Personal Agent Specification (delta for feat-703)

## ADDED Requirements

### Requirement: 主 PA 按主人明确交办创建长期 Agent

#### Scenario: 创建前对齐并交付
- **WHEN** 主人明确要求 PA 创建独立 Agent
- **THEN** PA 按需取得创建指导和目标电脑真实选项，在聊天中与主人确定配置后执行；已有选择不重复询问，主人可接受推荐值。
- **AND** 默认推荐 PA 所在电脑，不擅自替换主人指定的电脑；真实成功后说明 Agent、职责、电脑和使用入口。

#### Scenario: 讨论与执行边界
- **WHEN** 用户只是讨论需求、PA 提出建议、观察聊天出现相关内容，或用户在提交前撤回
- **THEN** 不据此创建；普通 Agent 和内部子 Agent 不获得该管理入口。

#### Scenario: 固定工具与按需细节
- **WHEN** 主 PA 查询选项、提交创建或确认原创建结果
- **THEN** 使用同一固定短工具入口，详细指导与配置选项按需读取；不因加载 Skill 或操作进度动态增删工具定义。
- **AND** Skill 选择与工具执行权限继续生效，无法取得指导或选项时如实说明。
