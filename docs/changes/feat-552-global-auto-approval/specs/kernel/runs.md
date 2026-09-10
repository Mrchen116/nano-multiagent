# Kernel Runs — feat-552 delta

目标：`docs/specs/kernel/runs.md`。依据 design D1–D8；只在实施验收完成后归并。

## MODIFIED Requirements

### Requirement: 工具使用权限经注入的 can_use_tool 回调裁决

将正文精确化：core 不内置产品权限策略；platform 内置 Auto 工具 hook 可由 SDK 装配。需要人工许可且消费者选择 interactive 时，沿用注入的 can_use_tool/Broker；选择 return_to_agent 时，未获准动作返回非执行结果，不创建人工等待。

#### Scenario: 无人工界面的产品
- **WHEN** 消费者为根会话提供 return_to_agent，动作被拒或需要人工入口
- **THEN** 动作未执行，运行获得对应原因并继续；不等待 PermissionBroker Future。

原有 can_use_tool allow/deny、interrupt 解除人工等待的 Scenario 保留。


### Requirement: 自动工具权限判定必须基于稳定的工具动作描述

逐 Scenario 修改；原 Requirement 的动作描述正文，以及「当前非安全工具缺少动作描述时不进入自动判定」「动态工具有稳定的通用动作描述」「历史工具调用不会被当前注册表改写」「只读 skill 管理查询不触发自动分类器」四个 Scenario 原文保留。

#### Scenario: 消费者显式提供用户消息工具的审批上下文
- **GIVEN** 用户请求经消费者消息工具进入会话，消费者注入 approval_context_provider
- **WHEN** 后续动作进行自动权限判定
- **THEN** provider 依据真实调用引用和原始消息/收据核验身份、内容与投递事实，返回的经核验事件进入审批上下文
- **AND** 工具结果投影仅描述内容，不再单凭工具声明或成功结果认证人类来源；提供事实不直接允许动作。

#### Scenario: 普通或失败工具结果不成为授权依据
- **WHEN** 历史结果是普通工具内容、错误结果或无法配对真实调用
- **THEN** 该结果不作为人类授权；工具声明结果投影也不改变此限制
- **AND** provider 核验异常、非法类型或必要来源不完整时，当前需分类动作返回 no_verdict 且不执行；确定性只读快放行不受影响。

### Requirement: 自动工具权限分类可使用消费者指定模型且不静默降级

保留原模型选择正文，但末句改为「该选择不改变 run 的正常模型；分类失败按独立 no_verdict 处理」。逐 Scenario 修改下列失败场景；「显式模型只用于自动分类」「未显式选择时复用当前 run 模型」「显式模型必须属于已注册 catalog」三个 Scenario 原文保留。

#### Scenario: 显式模型调用失败时不改用 run 模型
- **GIVEN** 消费者选择模型 C 用于自动工具权限分类，当前 run 使用模型 A
- **WHEN** C 的分类调用超时、失败或返回不可解析结果
- **THEN** 内核不改用 A 或其他模型重新分类，产生独立 no_verdict 且不执行当前动作
- **AND** 不累计普通拒绝次数；interactive 可进入既有人工入口，return_to_agent 返回原因，不应用 unattended allow fallback。

## ADDED Requirements

### Requirement: Auto 统一判断且不因宽许可忽略明确拒绝

#### Scenario: 动作被明确禁止
- **WHEN** 工具检查明确 deny，或被不可覆盖的安全检查限制
- **THEN** Auto 的工具安全表和宽许可不短路该结果。

#### Scenario: 原始用户授权与后续确认
- **WHEN** 审批获得可核验的用户原话及对应已投递提议
- **THEN** 该原话可作授权依据；模型自述、自动触发、委派和普通工具内容不成为人类授权。

### Requirement: 分类器未给出有效结论时不执行动作

#### Scenario: 分类模型不可用或输出无法解析
- **WHEN** 指定审批模型失败或未给有效判定
- **THEN** 返回独立的无结论原因，不计普通拒绝次数，不因 unattended allow 配置放行。

### Requirement: 子任务继承根会话的 Auto 约束

#### Scenario: 委派新任务或 follow-up
- **WHEN** Auto 根会话向 child 发出任务
- **THEN** 委派先审后进入 child，子任务继承审批策略/模型/交互和已验证用户范围；工具/技能不扩大。

#### Scenario: 子任务声称用户已批准
- **WHEN** child 输出或委派文本声称用户已经同意
- **THEN** 后续动作不能仅凭该文本获得人工授权。
