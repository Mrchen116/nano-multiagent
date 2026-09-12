# Kernel Runs — feat-552 delta

目标：`docs/specs/kernel/runs.md`。依据 spec R1–R6、design D3–D8；仅在实施验收后归并。

## MODIFIED Requirements

### Requirement: 工具使用权限经注入的 can_use_tool 回调裁决

消费者在 `build_kernel` 时可注入 `can_use_tool` 异步回调；启用 Auto 时由 SDK 装配共享自动权限判定。需要人工许可的交互入口调用该回调并采纳其决定；选择 `return_to_agent` 的普通运行将未获准原因返回 Agent，不进入人工等待。实际 Heartbeat/Cron 运行保持本文件规定的无人值守分流。

#### Scenario: 需要许可时 can_use_tool 被调用并采纳其决定
- **GIVEN** 一个注入了 `can_use_tool` 的 Kernel
- **WHEN** 运行中触发一次工具许可请求
- **THEN** `can_use_tool(tool_name, tool_input, ...)` 被调用;它返回 `allow` 则该次工具被放行, 返回 `deny` 则被拒绝

#### Scenario: 等待许可期间 interrupt 解除挂起
- **GIVEN** 一次许可请求正阻塞在 `can_use_tool`(模拟用户迟迟未决)
- **WHEN** 消费者对该会话调 `kernel.interrupt(session_id)`
- **THEN** 挂起的许可请求被解除为拒绝(deny),等待者立即返回而不会无限挂起

#### Scenario: 全局入口返回未获准结果
- **WHEN** 当前运行按入口优先级选择 return_to_agent，Auto 未允许当前动作
- **THEN** 返回明确原因，动作不执行，不创建权限 Future；该设置由应用元数据传入并由普通 child 继承。

### Requirement: 自动工具权限判定必须基于稳定的工具动作描述

当消费者启用自动工具权限判定时,内核在判定一次非安全工具调用前必须提供当前工具动作的可解释描述; 找不到当前工具、当前工具无法提供动作描述、或动作描述为空时,该次工具调用必须 fail closed 到显式权限决策,不得用空当前动作继续自动判定。历史 transcript 中的工具调用必须按当时记录的工具名与输入稳定描述, 不得被当前注册表中同名工具的替换实现改写或丢弃。

#### Scenario: 当前非安全工具缺少动作描述时不进入自动判定
- **GIVEN** 消费者启用自动工具权限判定,且某会话尝试执行一个非安全工具
- **WHEN** 内核无法解析该工具的当前动作描述
- **THEN** 该工具调用不会被自动允许或按空当前动作交给分类器
- **AND** 消费者收到显式权限决策路径(ask / deny 等 fail-closed 结果)

#### Scenario: 动态工具有稳定的通用动作描述
- **GIVEN** 消费者或工作区注册了一个未提供专用动作描述的动态工具
- **WHEN** 该动态工具进入自动权限判定
- **THEN** 当前动作描述包含该工具名及其原始输入的结构化表示
- **AND** 该工具不会因为缺少专用描述而被视为安全或以空动作判定

#### Scenario: 历史工具调用不会被当前注册表改写
- **GIVEN** 会话历史中已有一个动态工具调用记录
- **WHEN** 后续该工具被卸载、改名,或同名工具被替换后,消费者继续推进同一会话
- **THEN** 自动权限判定中的历史 transcript 仍保留那条历史工具调用的工具名与输入
- **AND** 不会用当前同名工具的新描述重写那条历史记录

#### Scenario: 只读 skill 管理查询不触发自动分类器
- **GIVEN** 会话可用 `skill_manage` 工具
- **WHEN** 消费者触发 `list` 或 `view` 这类只读 skill 查询动作
- **THEN** 该动作由工具级权限检查直接放行,不进入自动分类器
- **AND** `create` / `edit` / `patch` / `write_file` / `remove_file` 等变更动作仍需带当前动作描述进入权限判定

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

消费者可在装配 Kernel 时选择一个已注册模型,专用于自动工具权限分类;未选择时,分类复用
当前 run 的模型。该选择不改变 run 的正常模型,也不改变分类失败后的既有权限处理。

#### Scenario: 显式模型只用于自动分类
- **GIVEN** 消费者以已注册模型 C 装配 Kernel,并以模型 A 提交一个 run
- **WHEN** 该 run 触发自动工具权限分类、执行工具并继续运行
- **THEN** 自动分类使用 C
- **AND** 分类前后的正常 run 请求继续使用 A

#### Scenario: 未显式选择时复用当前 run 模型
- **GIVEN** 消费者未在装配 Kernel 时选择自动工具权限分类模型
- **WHEN** 一个以模型 A 提交的 run 触发自动分类
- **THEN** 分类使用 A

#### Scenario: 显式模型必须属于已注册 catalog
- **GIVEN** 消费者提供的自动工具权限分类模型不在 Kernel 的 LLM catalog 中
- **WHEN** 消费者经 `agent.sdk` 装配 Kernel
- **THEN** 装配失败并明确指出无效模型

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
