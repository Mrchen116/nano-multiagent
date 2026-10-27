# gateway/agent-capabilities 增量

## ADDED Requirements

### Requirement: PA 通用能力遵守选择与知识归属
#### Scenario: 默认与禁用
- **WHEN** 用户选择或禁用 PA 的记忆、关注或相关 Skill
- **THEN** 真实 callable 面与自动行为一致，关闭不经别的 Skill 恢复；个人偏好留在私人受控记忆，不进入全局共享 Skill。
#### Scenario: 升级与迁移
- **WHEN** 旧 PA 采用记录记忆或新默认指导
- **THEN** 迁移保留原资料与不确定来源，重复执行不增副本，已有自定义和空指令不自动覆盖；关闭自动维护或回退不会丢新记录。
#### Scenario: 内部角色
- **WHEN** PA 创建观察或事项执行者
- **THEN** 观察者仅获得受限只读输入/能力，任务执行者只获得相关 handoff；root 身份、私人历史与代表发送资格不默认继承。

## MODIFIED Requirements

### Requirement: self-evolution 创建的 Skill 跨前台 terminal 仍完成配置调和

Gateway 对 self-evolution review 成功产生的知识更新事实保持 session 级消费，不依赖已经结束的前台 run context。事件无论在前台 terminal 前后到达或经可恢复 stream 重连重放，都保留真实来源与通知，不为新技能修改禁用名单。

后台 Memory/Skill review fork 保留父会话历史，逐字节继承父请求已渲染的 system prompt 和完整工具定义，维护指令追加在继承历史之后；不因后台工具白名单重建请求前缀。白名单在工具执行前独立拦截，工具可见不代表获准执行。这样保留上游前缀缓存的复用条件；实际命中仍以 provider usage 为准，不承诺每次命中。

非 PA 的 Memory 注入在首次请求惰性读取，当前会话内保持快照，原生 fork 继承快照，压缩完成后再读取最新内容。PA 主上下文按受控记忆版本在下一安全模型边界刷新，明确纠正/遗忘不等待压缩；普通任务 child 不默认继承私人概览或全量历史，可信知识维护 fork 保留必要证据并受当前版本及执行白名单约束。禁用 memory_curation 时均不自动读取或注入，工具的独立选择仍按既有规则。后台反思分别按主会话轮次和模型迭代累计，单轮并行工具不放大计数；前台对应维护工具的成功结果重置提醒读数，失败不重置。后台 review 仅完成后推进重置点，失败或取消不消耗提醒周期。

#### Scenario: fast review 与 slow review 使用同一调和结果

- **GIVEN** Agent 的 self-evolution review 成功创建 agent-scope 或 global-scope Skill
- **WHEN** 创建事件发生在前台回答 terminal 之前或之后
- **THEN** 新 Skill 由原生发现变为可用，前后台通知按真实结果投递
- **AND** 已存在的同名禁用选择保持，不因创建事实被覆盖

#### Scenario: 后续前台轮次与 stream 重连不重复调和

- **GIVEN** 同一 session 的持久后台事件消费已建立，随后又完成前台轮次或发生可恢复 stream 重连
- **WHEN** self-evolution 创建事件被实时接收或重放
- **THEN** 同一创建结果不会被前台与后台两条路径重复处理
- **AND** 未禁用的新 Skill 在相关 Agent 的后续 session 中保持可用

