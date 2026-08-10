# refactor-463: 收回 InboundPipeline 状态所有权

## Relations

- Depends on: refactor-461（已由 PR #197 合入 main，实施基线已满足）
- Related: refactor-460, refactor-462

## 原始诉求

> docs/research/architecture-reviews/architecture-review-20260714-144212-d33025cf.html
> 你审下
> 1. Platform Tool Registry 透传 shim
> 4. InboundPipeline 是 Gateway 入口 god class
> 是不是真问题，他推荐的solution是不是真合理的好方案

> 好，你更新下html

> 做了候选4，是不是有望大大减少两个巨石代码文件

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 开始解决候选4。候选8有refactor 461在搞。你独立进行spec和design。最后交给design reviewer进行review

## 澄清记录

- Q1: 本单元是否只治理候选 4，由 Agent 独立收敛 spec/design，并把候选 8 与 refactor-461 明确排除在实施范围外？
  A(原话):
  > [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 开始解决候选4。候选8有refactor 461在搞。你独立进行spec和design。最后交给design reviewer进行review

  Agent 解读: 用户已授权 Agent 按推荐答案独立完成需求与设计收敛，不需要中途逐项确认；本单元必须保持既有 Gateway 用户行为，只治理候选 4 的入站职责与状态所有权。候选 8 的进程生命周期、daemon、PID 与死 kernel subprocess seam 继续由 refactor-461 负责。设计完成后必须交给独立 design reviewer 审查。

## 现状痛点

Gateway 当前已经支持直聊与群聊路由、同会话串行与运行中插话、`/stop`、图片输入、后台任务回信、外部通道影子会话和运行终态投递。终端用户看到的是一条完整的消息处理链，运维者看到的是一个可启动、可停止并能重连的 Gateway。

候选 4 的问题不在于 `InboundPipeline` 文件长，也不在于其只有一个主要入口；窄入口背后隐藏复杂实现本可以是深模块。真正的问题是入站处理所依赖的可变状态、回调和生命周期没有清晰且唯一的所有者：装配代码要在构造后修改私有字段，其他运行时组件直接读取其内部 agent、会话与队列状态，大量测试也必须穿透私有方法和字段才能构造场景。结果是任何涉及 active run、插话、`/stop`、终态 reconcile、群背景 drain、图片预处理或后台订阅的改动，都要求维护者同时理解多个隐含不变量。

这会带来三类风险：

1. 同一份会话或运行状态可能被多个调用方协同维护，容易在并发、停止和终态竞争中失配。
2. `main.py` 必须知道过多入站实现细节，候选 8 即使清理进程生命周期后，也无法单独消除这部分装配复杂度。
3. 测试依赖内部布局，重构一个局部职责会引发大面积测试改写，却仍不能证明对用户可观察行为没有回归。

## 目标状态

Gateway 继续以同一个稳定入站入口处理消息，但每类会跨 `await`、跨消息或跨运行存活的状态都有唯一、可说明的所有者。composition root 只显式构造并连接这些运行时能力，不再通过事后修改私有字段完成接线；其他组件也不再把 InboundPipeline 的私有容器当作共享状态仓库。

完成后，维护者可以分别修改 agent/session 管理、单会话运行协调、图片解析或后台订阅生命周期，而不必掌握其余职责的内部状态。测试通过稳定的行为接口验证结果，不再以私有字段和私有方法作为主要测试表面。

本重构不以减少文件行数作为成功标准。`inbound_pipeline.py` 和 `main.py` 的入站相关代码预计会明显缩小，但只有当复杂度随旧的隐式 interface 一起消失、没有转移成一组薄 wrapper、兼容 shim 或跨模块共享字典时，才算达到目标。

## 用户侧验收标准（不变性）

当前用户可以从 Web IM 或外部 channel 与 Agent 直聊或群聊，在运行中继续插话或停止操作，发送图片，并在原会话收到中间、最终与后台回复。运维者可以重启 Gateway 后续接既有会话；IM 暂时离线时，外部 channel 的本地执行主路径仍可用。重构后这些既有行为与可见失败反馈必须保持一致。

### Requirement: 入站路由、会话与回复位置保持一致

#### Scenario: 直聊消息仍由正确 Agent 在原目标回复
- **GIVEN** Gateway 已配置可用 Agent 与消息通道
- **WHEN** 终端用户从 Web IM 或外部 channel 发送直聊消息
- **THEN** 消息仍按显式 Agent、通道绑定与默认 Agent 的既有优先级路由，回复出现在原通道原目标，与变更前一致

#### Scenario: Gateway 重启后续接原会话
- **GIVEN** 用户已在某通道会话与 Agent 交谈并形成历史
- **WHEN** Gateway 重启后用户在同一通道会话继续发送消息
- **THEN** Agent 仍续接原会话和上下文，不创建一段用户可感知的新历史，与变更前一致

#### Scenario: 未知 Agent 路由仍被拒绝
- **WHEN** 入站消息显式指向一个 Gateway 未注册的 Agent
- **THEN** 该消息仍被拒绝，不创建会话或执行，也不误投递给其他 Agent，与变更前一致

#### Scenario: 动态 Agent 配置在下一轮生效
- **GIVEN** IM 已向 Gateway 同步某 Agent 的模型、提示词、工具、技能或自动化开关更新
- **WHEN** 用户随后向该 Agent 发送下一条消息，或到达下一次 heartbeat/cron tick
- **THEN** 对应路径仍读取同一份最新配置，其他 Agent 不受影响，与变更前一致

#### Scenario: Agent 工具投递仍同步到正确直聊会话
- **GIVEN** Agent 在运行中通过 `send_message` 等产品工具向用户投递消息
- **WHEN** Gateway 内部 dispatch 收到 IM 对该投递的确认
- **THEN** 消息仍绑定到来源 Agent 的正确直聊会话并写入其连续历史，动态更新后的 workspace 配置也被正确使用，与变更前一致

### Requirement: 群聊门控与背景上下文保持一致

#### Scenario: 未点名群消息只积累背景
- **GIVEN** Agent 使用 MENTION 群回复策略
- **WHEN** 群成员发送未 @Agent、未回复 Agent 且不是控制命令的消息
- **THEN** Agent 不发起运行也不回复；该消息仍作为该 Agent 的群背景供后续点名轮次使用，与变更前一致

#### Scenario: 点名后带入此前群背景
- **GIVEN** 群聊中已有若干未点名 Agent 的背景消息
- **WHEN** 群成员随后 @Agent 发送消息
- **THEN** Agent 的本轮回复仍能使用此前背景，并保留各发言人的身份与顺序，与变更前一致

### Requirement: 单会话并发、插话与停止保持一致

#### Scenario: 同会话串行且跨会话并行
- **GIVEN** 某会话已有一轮运行，同时另一个会话也收到消息
- **WHEN** 用户继续发送消息
- **THEN** 同会话工作仍按既有 FIFO/插话规则推进，不同会话仍可并行，用户看不到丢消息、乱序或跨会话阻塞

#### Scenario: 运行中插话被及时采纳
- **GIVEN** Agent 正在处理一轮用户消息
- **WHEN** 用户在同一会话继续发送一条或多条消息
- **THEN** Agent 仍按发送顺序及时纳入这些消息，不硬中断正在执行的当前步骤，回复位置与变更前一致

#### Scenario: /stop 中断活动运行
- **GIVEN** 当前会话存在活动运行
- **WHEN** 用户发送 `/stop`、`@agent /stop` 或 `/stop @agent`
- **THEN** 当前运行仍被中断，用户收到既有停止确认，终态与历史不悬空或重复

#### Scenario: 空闲会话收到 /stop
- **WHEN** 用户在没有活动运行的会话发送 `/stop`
- **THEN** 用户仍收到既有友好提示，不触发新运行或报错

#### Scenario: 活着但安静的运行不被误杀
- **GIVEN** Agent 正在执行静默长工具、等待 LLM 或等待用户权限决定，并持续产生既有 liveness 信号
- **WHEN** 等待时间超过 idle 判定窗口
- **THEN** 运行仍不被误判卡死；真正失去 liveness 的运行仍会失败收尾并释放后续队列，与变更前一致

### Requirement: 图片与可见失败反馈保持一致

#### Scenario: 有效图片正常进入本轮
- **WHEN** 用户通过受支持的通道发送大小允许且可读取的图片
- **THEN** Agent 仍能在本轮理解该图片并回复，与变更前一致

#### Scenario: 图片下载、超限或损坏
- **WHEN** 图片无法下载、超过限制或内容损坏
- **THEN** 用户仍在原会话及时收到对应的既有可读失败反馈，不启动错误的 Agent run，也不把失败误投递到其他通道

### Requirement: 运行过程、终态与后台回复保持一致

#### Scenario: 中间与最终回复不重不漏
- **WHEN** 一轮运行产生中间可见回复、工具过程和最终回复
- **THEN** 用户仍只看到应当可见的内容；最终回复不重复，`NO_REPLY` 等静默 token 不泄漏，失败原因及时归属到正确消息

#### Scenario: 后台任务完成后回到原会话
- **GIVEN** 用户从某会话启动后台任务且主轮已经结束
- **WHEN** 后台任务稍后产生用户可见结果
- **THEN** 结果仍回到触发任务的原会话；重放或 Gateway 重启不造成重复回复，与变更前一致

#### Scenario: 外部 channel 与影子会话投递边界不变
- **GIVEN** 外部 channel 对话已映射到内部 IM 影子会话
- **WHEN** 外部 channel 或内部影子会话分别触发 Agent 运行
- **THEN** 外部触发的可见结果仍回到原外部对话并同步影子会话，影子会话触发的结果仍不反写外部 channel，与变更前一致

#### Scenario: IM 离线时外部 channel 仍可用
- **GIVEN** IM 服务暂时不可达但外部 channel 可用
- **WHEN** 用户从外部 channel 发送消息
- **THEN** Gateway 仍在本地执行 Agent 并回发原 channel，IM 同步失败不阻断主路径，与变更前一致

### Requirement: Gateway 生命周期的用户结果不受本重构影响

#### Scenario: 启动、停止和重连结果保持一致
- **WHEN** 运维者按现有方式启动、停止、重启 Gateway，或 Gateway 经历 IM 断线重连
- **THEN** 服务管理与恢复结果遵循 refactor-461 完成后的当前契约；本单元不新增另一套进程、配置或 readiness 语义

#### Scenario: 停止时已接纳的入站工作有明确结局
- **GIVEN** Gateway 停止时既有已提交的活动 run，也可能有已进入同会话 FIFO 但尚未提交到 Kernel 的消息
- **WHEN** Gateway 进入优雅关闭
- **THEN** 活动 run 仍有机会完成终态投递；尚未提交的排队消息不会在 Kernel 关闭后偶然提交，而是经既有失败终态明确收尾；IM transport 只在这些已接纳工作及其投递任务被收拢后关闭

## 影响范围

- Gateway 入站消息从路由、会话绑定、运行协调到回复投递的完整行为面。
- Gateway 对 live Agent 配置、会话持久化、群背景、图片输入、后台 session event 与运行终态的协作方式。
- `main.py` 中只与入站管线实例化和依赖接线直接相关的 composition root 代码。
- 直接验证上述行为的 Gateway 单元、集成、契约和关键路径 e2e 测试。
- 不改变 IM、Kernel 或 channel 的对外协议，不改变持久化数据格式，不新增用户功能。

## 迁移与回滚策略

1. **以 refactor-461 为实施基线**：该依赖已由 PR #197 合入；本单元从合入后的 `main.py` 与 Gateway 生命周期结构开始实施，不再兼容或回接 461 之前的 composition root。
2. **按完整行为切片迁移**：每个迁移步骤都必须保持稳定入站入口和现有用户行为，不允许在中间状态引入第二套运行状态或双写路径。
3. **状态单一所有权**：迁移完成后删除旧私有接线、共享容器访问和只为兼容旧内部布局存在的 wrapper；不把旧问题挪到新模块之间。
4. **测试表面同步替换**：新增稳定接口级测试后，删除对等的私有实现测试，不在两套测试表面上长期叠加维护成本。
5. **原子回退**：任一实施步骤若无法证明并发、停止、终态、图片或后台回复不变，则整体回退该步骤；不得用长期 feature flag 或兼容 shim 掩盖未完成迁移。
