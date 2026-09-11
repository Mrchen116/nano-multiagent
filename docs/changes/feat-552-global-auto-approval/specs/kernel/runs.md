# Kernel Runs — feat-552 delta

目标：`docs/specs/kernel/runs.md`。依据 spec R1–R6、design D3–D8；仅在实施验收后归并。

## MODIFIED Requirements

### Requirement: 工具使用权限经注入的 can_use_tool 回调裁决

正文改为：core 不内置产品权限策略；platform 的 Auto hook 由 SDK 装配。需要人工许可的 interactive 入口沿用 can_use_tool / Broker，按实际运行入口选择 return_to_agent 时把未获准结果返回 Agent，不创建人工等待；Heartbeat/Cron 的原无人值守例外见本文件分流条目。原「需要许可时 can_use_tool 被调用并采纳其决定」「等待许可期间 interrupt 解除挂起」两个 Scenario 保留。

#### Scenario: 全局入口返回未获准结果
- **WHEN** 当前运行按入口优先级选择 return_to_agent，Auto 未允许当前动作
- **THEN** 返回明确原因，动作不执行，不创建权限 Future；该设置由应用元数据传入并由普通 child 继承。

### Requirement: 自动工具权限判定必须基于稳定的工具动作描述

保留动作描述正文以及「当前非安全工具缺少动作描述时不进入自动判定」「动态工具有稳定的通用动作描述」「历史工具调用不会被当前注册表改写」「只读 skill 管理查询不触发自动分类器」四个 Scenario。仅修改以下两项：

#### Scenario: 消费者显式提供用户消息工具的审批上下文
- **GIVEN** 消费者消息工具显式声明结果审批投影，且真实成功结果与调用匹配
- **WHEN** 后续动作进行自动权限判定
- **THEN** 保留工具动作与附加上下文，实时宿主内容以 host_context_live 呈现，恢复内容以 host_context 呈现
- **AND** 来源由应用和 runtime 提供；明确真人原话可表达意图，Agent/系统/引用不因此成为真人；结果本身不直接允许动作。

#### Scenario: 普通或失败工具结果不成为授权依据
- **WHEN** 工具未声明投影、结果失败、或无法配对真实调用
- **THEN** 不产生实时宿主授权上下文；历史工具状态仍可作为执行事实
- **AND** 显式投影异常保留可区分的失败结果，不隐式改成人类输入或 classifier allow。

### Requirement: 自动工具权限分类可使用消费者指定模型且不静默降级

保留原模型选择正文，以及「显式模型只用于自动分类」「未显式选择时复用当前 run 模型」「显式模型必须属于已注册 catalog」三个 Scenario。失败项补充可观察原因：

#### Scenario: 显式模型调用失败时不改用 run 模型
- **GIVEN** 分类选模型 C，主 run 使用 A
- **WHEN** C 超时、不可用、输出无法解析或请求上下文超限
- **THEN** 不换 A 或其他模型、不隐式裁剪重判，保留 no_verdict 原因且不计有效拒绝
- **AND** interactive 进入原人工入口；global wake 与普通 child 返回原因；Heartbeat（包括复用 global 主 session 的运行）及 Cron 按 unattended_fallback（默认 deny，可显式 allow）处理，配置放行不标成模型 allow。

## ADDED Requirements

### Requirement: Auto 来源语义独立于消息承载角色

#### Scenario: 真人回复前保留 assistant 文本
- **WHEN** 主会话中的真人回复跟在 assistant 文本之后
- **THEN** 按固定 CC 的启用分支保留最近文本末尾 2000 UTF-16 单位用于解释回复；尚无真人回复的当前旁白不加入。

#### Scenario: 自动触发与 Agent 输入
- **WHEN** user-role 内容实际来自 Cron、heartbeat、后台通知或 Agent
- **THEN** 审批保留对应非真人来源及 CC 说明，不能把该内容当作新的人工确认或触发真人回复配对。

#### Scenario: 同会话跨轮与恢复
- **WHEN** 实时宿主上下文经历普通跨 turn、compact 或进程恢复
- **THEN** 普通跨 turn 保留实时来源；compact 只使用新窗口；恢复的宿主内容降为 host_context，不通过查询历史提升为实时授权。

### Requirement: Auto 有效拒绝按会话计数并保留产品分流

#### Scenario: 主会话与普通 child
- **WHEN** 多个 run 或工具产生有效自动拒绝
- **THEN** 同一主 session 跨 run 累计 consecutive/total；普通 child 各自计数；默认 3/20，成功清连续数，总阈值处理清总数，不新增永久暂停锁。

#### Scenario: 达阈值与服务故障
- **WHEN** 达到拒绝阈值，或分类服务未给有效结论
- **THEN** interactive 使用既有人工入口，global wake/普通 child 返回原因，Heartbeat/Cron 等原无人值守运行使用其 fallback；global Heartbeat 的自动入口不被同 session 的全局交互设置覆盖，child 的 BACKGROUND_TASK/USER 调度值不改写其继承的全局交互；故障不计为用户未授权。

### Requirement: 子任务保留更新后的 Auto 约束与原始来源

#### Scenario: 新派发与 follow-up
- **WHEN** 父 Agent 创建或继续 child
- **THEN** agent 调用保持免审；工具/skills 不扩大，继承有效审批设置和带原始来源的父已读上下文；child 的实际动作继续过 gate。

#### Scenario: 委派或结果声称用户批准
- **WHEN** Agent 文本声称获得了用户同意
- **THEN** 不把该主张本身提升为人工授权，普通 child 自身的非真人消息也不形成确认配对。
