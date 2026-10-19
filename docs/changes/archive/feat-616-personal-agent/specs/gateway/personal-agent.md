# Gateway personal-agent Specification (delta for feat-616)

## ADDED Requirements

### Requirement: PA 复用完整 Global 执行能力
#### Scenario: 主人请求与普通工具
- **WHEN** 主人交办工作或查询历史
- **THEN** 直接进入 Global 主上下文，复用普通工具、Skills、插件、任务、子 Agent 与调度；不增加主人输入审核或 PA 目标引擎。

### Requirement: PA 双身份消息保留可信来源
#### Scenario: 合并历史与新消息
- **WHEN** 查询或接收主人授权聊天和 PA 自己聊天的消息
- **THEN** 当前权限有效的两者并集可见，重复消息只处理一次，主人发出的消息也摄入，PA 自发消息不引起循环。

### Requirement: 来源控制仅改变未来访问
#### Scenario: 排除聊天
- **WHEN** 主 PA 按主人要求调用来源工具
- **THEN** 后端拒绝后续访问并撤销待处理输入，不清空记忆、成果或运行上下文。

### Requirement: 独立披露检查限定于对外行为
#### Scenario: 对外发送与私人工作
- **WHEN** PA 发出消息或修改共享内容
- **THEN** 实际外发核对真实授权、完整 payload 与受众；主人私聊和私人工作不加 PA 审核，原工具权限继续生效。
- **AND** 不把该检查声明为任意代码/插件的完整网络隔离。

### Requirement: 默认服务指导复用普通配置和 Skill
#### Scenario: 用户调整服务方式
- **WHEN** 主人修改或清空 PA 的 custom_prompt
- **THEN** 沿用普通 Agent 的配置和 Persona 加载机制，运行时不暗中补回默认服务文案；固定主人身份、来源、权限及对外披露规则仍有效。
#### Scenario: 跨轮次持续工作
- **WHEN** Global 或 PA 接续已接受的持续事项
- **THEN** 可按普通 Skill 发现、选择和加载机制使用随包 nano-ongoing-work，复用已有工作记录、任务、子 Agent、Heartbeat 和 schedule；不新增 PA 账本服务或调度器，不覆盖用户已有 ongoing-work Skill，也不绕过用户禁用选择。
