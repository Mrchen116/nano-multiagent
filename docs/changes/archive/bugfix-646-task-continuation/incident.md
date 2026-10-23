# bugfix-646: Global Task 续跑、等待与反馈闭环

## Relations

- Related: archived feat-635（Task 自动执行）、feat-645（配置与工具契约，独立推进）。

## 原始报告与澄清

用户在生产 Global Agent 的 Task 长期 doing、连续输出 NO_REPLY 后要求调查并对齐修复，随后确认：

> “可以，把我们刚才对齐的这些改动整理成一个完整方案，配置契约留给另一个thread，这里先把Global和Task续跑、等待、失败处理及反馈这条链路收口。并且想一下还有什么矛盾，或者还有什么问题没解决。”

> “还有一个默认值这么牛逼的吗？现在就有这个设计吗？最长不超过一个小时吧。”

> “DSH有考虑过goal pause会失败吗，他咋处理？我们照学过来”

> “我觉得这个合理啊。但是它的目标不是用户。他原本在哪个聊天就是哪个聊天，有可能他任务也不是用户给他派的，是Agent给他派的。”

> “已有五天后的 waiting 安排怎么办？”这个问题不用考虑，现在没有。我觉得现在差不多了，你继续推进吧，你自己决定这些问题吧，根据我之前做的决策。设计好之后，开始做

Agent 对已对齐决定的整理：续跑基于 DSH Goal 原始提示的“读取当前事实、具体推进、验证结果”，不把设计约束当模型提示；Global 移除 NO_REPLY 指引并保持非空私有收尾；真正受阻前尝试合法替代路径；waiting 用真实 Schedule，首次和续期均不超过一小时、不设固定默认间隔；定时回看重新判断阻塞是否必要，相关答复可提前恢复；失败停止无效自动重复但不伪造业务状态；成功进入 waiting 后提示实际交付阻塞说明到任务固定所属聊天；不因某项等待结束其他独立工作。

## 现象与复现

2026-10-23 只读调查生产聊天的同一图 rev27：工程 Agent 的任务仍为 doing、wait 为空，另有本人可执行与已提交任务。19:05 报告阻塞后到 21:24 仍约每 12 秒收到 Task 续跑；21:30 快照中当天已有 745 次 NO_REPLY、747 次自动输入。没有 Schedule 调用。轨迹还记录一次 task_graph apply 被共享资源审批拒绝；实际配置中 Schedule 工具名单与 Cron 功能不一致。计数是当时快照，不是当前状态。

复现条件：Global 拥有 doing Task，模型判断暂时不能推进，按续跑提示输出 NO_REPLY，既不建立 waiting 也未完成任务。运行时仍发现 doing，下一轮继续同一输入。

期望：做真实工作，或核实阻塞并建立有效 waiting、向所属聊天交付必要反馈；运行故障/拒绝不形成无效自动重复。

## 影响范围

Global 与 SingleThread 的 Task 自动执行、原生 Schedule 等待安排、IM waiting 写入校验及 Global 显式反馈。没有证据表明数据损坏。选择 Full 是因为根因横跨提示、原生执行边界和服务端任务状态，需独立场景矩阵。

非目标：Feature/Tool 配置映射（feat-645）、生产部署或修复现存生产任务、旧超长 waiting 迁移、第二执行循环、轮次或 token 限额、审批规则豁免/安全分类器重构、前端改版。

## 根因分析（RCA）

- `packages/dsh-integration/src/task-execution.ts` 的续跑提示直接要求 unchanged progress 返回 NO_REPLY，混入无预算约束，却缺少 DSH 原始“检查当前工作区与持久状态、推进并验证”的核心引导；回复结束不改变 doing，形成循环。
- shared Intelligent UI 提示和 Skill 同样要求 NO_REPLY，与 Global 非空有意义私有收尾契约冲突。
- waiting 已要求原生 Schedule，但只检查未来时间，未限制下次复查距离；缺少成功 waiting 后的专门交付提醒。
- driver 已有 interrupted 屏障，但所有普通输入都清空它，同名工具任意成功也清掉拒绝，无法区分新输入处理和旧动作自动重试。
- 原有测试保护调度、状态和静默路由，未覆盖真实模型在“持续 doing 但无新行动”时如何形成等待与反馈。配置能力缺失是并发因素，交给 feat-645；审批拒绝按真实拒绝处理，不据此改成无审查放行。

## 修复方向与验收

### Requirement: Task 续跑 SHALL 检查事实并推进仍可执行的责任

#### Scenario: 多项任务与合法替代
- **GIVEN** Agent 同时拥有多项 doing/waiting Task
- **WHEN** 自动续跑或到期复查触发
- **THEN** 检查当前任务、工具结果与工作区，推进可执行部分并验证，必要时读取详情；阻塞不必要时采用合法替代；其他独立任务继续。
- **AND** 定时触发不重开 paused/closed/done/in_review，也不带来新的人工授权。

### Requirement: waiting SHALL 有一小时以内的真实复查和实际阻塞

#### Scenario: 建立及更新等待
- **WHEN** 确认暂时没有合法可执行步骤，且所需请求已经实际送达或有真实外部前置
- **THEN** 先创建/更新有效 Schedule，再关联 waiting，下一次检查必须在未来一小时内；超限拒绝且原任务保持原状。
- **AND** 通用 Schedule 不受这个 Task 限制；没有统一默认复查间隔。

#### Scenario: 到期与提前恢复
- **WHEN** 相关回复提前到达或 Schedule 到期
- **THEN** 重读状态与外部条件，重新评估原阻塞是否必要；可执行则继续，否则续设一小时以内的复查；相同阻塞不重复刷屏。

### Requirement: 等待和完成反馈 SHALL 到达 Task 固定所属聊天

#### Scenario: Agent 派发与跨聊天
- **GIVEN** Task 属于聊天 A，可能由 Agent 派发，最近输入在聊天 B
- **WHEN** 成功进入 waiting 或提交完成结果
- **THEN** Global 用 send_message 向 A 实际交付；等待说明包含已完成、具体阻塞、已尝试路径、需要谁提供什么与下次检查；不把私有结语当公开交付。

#### Scenario: 交付或状态操作失败
- **WHEN** waiting 已保存但反馈失败/未知，或 Schedule 已建而 waiting 写入失败
- **THEN** 不捏造送达、不回退为 doing 来重发；保留真实状态与原有确认/未知处理，按原请求键核实结果并修复；已确认相同反馈不重复发送。

### Requirement: 执行失败 SHALL 停止无效自动重复并允许相关恢复

#### Scenario: 校验错误与运行故障
- **WHEN** 普通参数/版本错误或真实读取、持久化、模型错误发生
- **THEN** 前者允许同轮修正；后者停止受影响自动重复，不伪造 paused/done/waiting；修复运行配置或获得相关新责任/输入后可重新评估。

#### Scenario: 审批拒绝与无关唤醒
- **WHEN** 动作被拒绝，随后有心跳、重复通知、无关聊天或不同参数的同名工具成功
- **THEN** 不将其当旧动作授权或无条件恢复信号；仍允许处理新输入、合法替代与独立工作；拒绝后的动作继续经过原审批链。

### Requirement: Global SHALL 使用有意义私有收尾

#### Scenario: 无新公开信息或卡片已发
- **WHEN** Global 结束本轮
- **THEN** 以非空私有结语说明已交付/已沟通或无需公开更新，不要求 NO_REPLY；SingleThread 原有静默交付协议保留。
