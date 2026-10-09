# gateway agent-capabilities Specification (delta for refactor-581)

## ADDED Requirements

### Requirement: 可替代能力采用原生工具名称与用法并允许受控升级

#### Scenario: 使用通用工具
- **WHEN** 助手使用已由DSH提供的等价工具或Skill调用入口
- **THEN** 使用其原生名称、参数及命令方式；迁移后的既有Skill仍能完成工作，不依赖旧名字或旧schema兼容层。

#### Scenario: 截断读取与后台输出
- **WHEN** 文件超过单次读取范围，或后台工具完成
- **THEN** 截断明确可继续读取；助手通过原生输出工具读取后台结果后正常向用户交付，不要求用户手动操作内部工具。

#### Scenario: 升级上游工具
- **WHEN** 维护者升级受支持的DSH版本并完成产品接入验证
- **THEN** 可使用更新后的原生工具能力；身份、权限、Skill引用及结果交付仍有效，不被复制的旧实现固定住。

### Requirement: 自建工具支持节点全局与workspace两层

#### Scenario: 共享、局部及同名覆盖
- **GIVEN** 本节点owner共享工具和workspace A的同名工具，另有workspace B
- **WHEN** A或B的主会话及被允许的子任务使用工具
- **THEN** A优先使用局部版本，B使用共享版本；A的私有工具不出现在B，工具名单继续限制可用能力。

#### Scenario: 重启和同workspace多会话
- **WHEN** 同一workspace建立多个会话或服务重启
- **THEN** 按该workspace的同一份持久扩展声明装配，局部工具不因为包已安装而自动全局启用。

### Requirement: Auto默认沿用Nano规则且可配置为DSH规则

#### Scenario: 默认审核规则
- **WHEN** 用户未选择其他Auto规则
- **THEN** 工具权限审核沿用Nano当前判定规则，保留可信来源、短确认、拒绝计数、人工审批和无人值守分流。

#### Scenario: 配置切换规则
- **WHEN** 运维者选择DSH默认规则并重启节点完成生效
- **THEN** 后续工具权限判定使用DSH规则；独立审核模型选择仍按既有契约，不能改用另一条并行审批链或绕开产品来源规则。
- **AND** 配置生效前已发出的审批仍对应原请求，迟答不复活取消调用。

#### Scenario: 规则切换不改变审核模型失败处理
- **GIVEN** 节点配置了独立审核模型
- **WHEN** 该模型在已有重试后仍失败或无有效判定
- **THEN** 不自动换回执行Agent模型复审；有人值守/无人值守分别走既有分流。

### Requirement: Feature可独立启停并撤销其后续影响

#### Scenario: 关闭和重新开启单项能力
- **WHEN** 用户对某Agent关闭再开启Task Graphs、Memory Curation、Skill Creation、Cron或Heartbeat
- **THEN** 该Feature的工具、提示、命令和未来触发按有效配置撤销或恢复，其他Feature及其他Agent不受影响；重新开启不累积重复监听或任务。
- **AND** 已有任务/记忆/Skill保留，Skill Creation关闭不等于禁用已有Skill加载。

#### Scenario: 关闭期间重启与在途工作
- **WHEN** 关闭的Feature经历节点重启，或关闭时已有工作被接收
- **THEN** 重启不擅自重新启用；在途工作依原产品契约收口；未完成卸载显示pending，不伪报effective或回滚已发生副作用。
