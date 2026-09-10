# SDK Boundary — feat-552 delta

目标：`docs/specs/kernel/sdk-boundary.md`。依据 design D3/D4/D7。

## MODIFIED Requirements

### Requirement: 装配与会话分两层,内核产品中立

本 Requirement 采用逐 Scenario patch：除以下两个 global config root Scenario 外，原正文仅增加可选参数并替换 Auto 配置来源说明；其余参数、方法与行为不变。以下八个原 Scenario 全文保留：「应用零前置调用直接装配」「三类应用对内核同构」「工具目录共享、会话选子集」「Kernel 暴露稳定的对外方法集」「消费者选择已注册的自动分类模型」「消费者省略自动分类模型」「消费者选择未注册的自动分类模型」「消费者配置 Workflow child 模型覆盖」。后面的「注入消息来源」「旧规则数组升级」为新增 Scenario。

SDK 增加可选 `approval_context_provider`。它提供经消费者核验的消息事实、根会话交互方式及完整性，不直接决定动作是否允许；core 类型经 SDK 导出，产品不 import platform 内部。

`global_config_root` 为消费者显式提供的可信 Auto 配置根。Auto 不再读取 workspace auto_mode 放宽策略；没有 global root 时使用内置默认，不隐式读取用户 HOME 或任意部署路径。

#### Scenario: 消费者提供 global auto-mode config root
- **WHEN** 应用显式提供 G，而 workspace 同时含 auto_mode
- **THEN** 若 workspace auto_mode 含非空配置，Auto 决策以明确迁移配置错误阻止动作，不静默忽略可能更严格的旧规则；清除旧项并由用户显式迁移至 G 后采用 G 和内置默认。

#### Scenario: 消费者省略 global auto-mode config root
- **WHEN** 应用未提供 G
- **THEN** 无非空 workspace auto_mode 时 Auto 使用内置默认；发现旧非空配置则返回明确迁移配置错误并阻止 Auto 动作，不能因缺少 G 而忽略旧限制；workspace 其他配置发现不变。

#### Scenario: 注入消息来源
- **WHEN** 消费者提供经原记录核验的人工消息或已投递提议
- **THEN** Auto 可使用它们理解范围；未注入时普通 tool result 不获得相同身份。

#### Scenario: 旧规则数组升级
- **WHEN** 应用使用旧空数组或包含 `$defaults` 的规则数组
- **THEN** 空数组保持默认含义；单个 `$defaults` 按位置继承当前内置规则，配置诊断可说明有效策略版本。

### Requirement: 内核对外只经 agent.sdk 暴露,产品不得依赖内核内部

逐 Scenario patch：正文的精确允许名单增加且只增加 `ApprovalContextRequest`、`ApprovalContext`、`ApprovalConversationEvent` 三个公开符号，均由 `agent.core.hooks.approval_context` 拥有并由 SDK 根包 re-export。公开 provider 参数使用 Callable 注解，不新增公开别名或包装类型。

「产品绕过 SDK 根入口被拦」「agent.sdk 不上行依赖产品」「core 不依赖 platform / products」「新增导出未进允许名单」「导出对象由内核内部模块拥有」「sdk-owned typing 别名不计入豁免」六个 Scenario 原文保留。

#### Scenario: 豁免名单容纳内核必拥有的边界对象
- **WHEN** 导出属于显式豁免名单：RunOrigin / PermissionDecision / TERMINAL_RUN_STATUSES / ToolPresenter / ToolPresentationEvent / USER_INTERRUPT_RECOVERY_CONTENT / ApprovalContextRequest / ApprovalContext / ApprovalConversationEvent
- **THEN** 所有权守卫放行；名单及三个新增类型的 core owner 路径逐字钉死，其他增删或 owner 漂移失败
- **AND** 同步更新 `tests/contract/test_agent_sdk_surface_guard.py` 的 EXPECTED_SURFACE 与 _OWNERSHIP_EXEMPT，并用 `test_agent_sdk_boundary_contract.py` 保持产品只从 SDK 根包导入、core 不反向依赖的契约。
