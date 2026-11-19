# feat-778 本机 Global worker 支持多种代码 Agent

## 原始需求

> 因为我想支持router派发各种worker agent，比如codex cli，claude code。

> 更接近是配置死，每台机子配置死

> 所以，我们的global agent派发subagent，我觉得不适合用现有的dsh工具，应自己造一个。

> 这里我给你派了两个活，一个是支持worker在各种codeagent。二是跨机。你分开做，第一个做完先提pr，第二个在第一个基础上做。我的亲自测过第一个好用，我再决定第二个。

> 这种你得参考raft针对我们场景思考，首先现在各种agent都有auto模式，你开的时候要auto，然后剩下还要审核的你就看raft的处理，和我们的产品理念来思考。我觉得大概是交给global agent来处理，现在好像也是这个逻辑

> 我想到的，memory现在还用worker的轨迹做总结，然后memory最终也给worker消费？我觉得这两项都可以去掉。worker完全不碰我们的记忆，不写不消费。不然跨机，跨agent框架很麻烦。

> 不是，只是说不注入，他非要去读，我也不管他呀。你不注入，他就不会去读了，所以不需要强加这种无谓的设计。

> 那也就是，明确点就是，先不支持看worker的轨迹，global agent的轨迹依旧显示。派工关系呢，我还是希望能看到的

## 澄清记录

- 本次交付本机 worker 的 PR。跨机是后续独立决策，等待用户亲测本次体验。
- worker 框架为机器配置。首批讨论 DSH、Codex CLI、Claude Code。一级由 Nano 派工，内部 helper 由执行框架组织。
- 用户指定外部 worker 启动时采用 Auto。初步处理方案是把需要决策的具体动作、目标、原因送回 Global。Global 按已有授权澄清、缩小范围或向原 IM 用户征询决定。明确拒绝的动作保持拒绝。参照现有[Global 未获准动作处理](../../specs/gateway/global-agent.md)。
- Raft 参考版本为 5214e34e。其 [Claude 启动](https://github.com/botiverse/raft-source/blob/5214e34e/packages/daemon/src/drivers/claudeLaunch.ts#L127) 和 [Codex 启动](https://github.com/botiverse/raft-source/blob/5214e34e/packages/daemon/src/drivers/codex.ts#L1224) 使用无人值守的宽权限配置。该参考仅说明原生驱动方式；用户对 Nano 的要求是 Auto。
- 已确认现状。文档记忆会给普通一级 worker 注入所属 Agent 的记忆入口或快照；Dreaming 从一级工作轨迹提炼会话摘要，并可依来源回看后代。见[现行能力契约](../../specs/gateway/agent-capabilities.md)、[上下文装配](../../../packages/dsh-integration/src/knowledge/document-memory.ts)和[提炼输入](../../../packages/dsh-integration/src/knowledge/dreaming.ts)。
- 用户要求对所有工作 worker 取消 Nano 记忆消费和写入，并停止把工作 worker 轨迹作为 Dreaming 的材料。worker 使用自己的会话续做，Router 交办时提供任务需要的具体约束。
- 记忆按产品集成边界处理。Nano 不向工作 worker 注入记忆正文、目录或读写指引，Dreaming 不用工作 worker 轨迹做总结。普通文件读取沿用当前工作环境的权限，无需为 Nano 记忆增加文件拦截或沙箱。
- Global 自身的工作记录与原生轨迹保持可查看。Web Work 的「派工关系」显示 Global 对真实一级 worker 的委派，区分不同事项；对同一 worker 的后续补充和结果归回原委派。新派工入口创建的一级 worker 只显示委派关系，不提供内部轨迹查看入口。历史 DSH 子执行沿用已有轨迹入口，见[现行 Work 契约](../../specs/im/agent-work.md#requirement-web-work-可以从派工关系进入同一工作记录)。
- Raft 参考补充。其[活动页](https://github.com/botiverse/raft-source/blob/5214e34e/packages/web/src/components/agent/AgentActivityLog.tsx#L633)默认展示概览，工具行使用操作与输入摘要，近期内部子执行根据明确的父子标识归组。完整请求走另行启用的 [View Context](https://github.com/botiverse/raft-source/blob/5214e34e/manual/agent-knowledge/context.md)。本机临时文件的只读探针从 Codex CLI 0.169.1 取得命令、输出、退出码、最终答复和回合用量，回合结束后进程到达探针时限而被终止。Claude Code 2.1.325 的 Auto 尝试收到账号验证错误，未实测成功的工具调用。本次只以 Global 自身记录与一级派工关系作为新派工的 Work 展示范围。

## 用户场景

用户在本机为 Global 配置 worker 框架，在 IM 交办一项工作。原 Global 继续接收消息、转发更正并交付。用户想知道两件并行事项分别派给了谁时，在现有 Work 派工关系中查看，需要回看 Global 做过的决定时，仍从 Global 的轨迹进入。

## 验收标准

### Requirement: 在本机使用所选 worker 完成事项

#### Scenario: 配置、派工与原会话续做
- **WHEN** 用户使用本机配置的 DSH、Codex CLI 或 Claude Code 交办工作，并在 IM 补充要求
- **THEN** 原 worker 接到更正并继续工作，用户从原 Global 收到交回的结果；用户要求停止该事项时，Global 能反馈实际停止结果。

#### Scenario: 外部 worker 需要决定
- **WHEN** 本机框架的 Auto 遇到需要澄清、需要新授权或明确拒绝的动作
- **THEN** Global 得到具体事项和原因，能在已有权限内处理或在原聊天向用户提问。明确拒绝继续生效。

### Requirement: 保留 Global 的轨迹与真实的一级派工关系

#### Scenario: 从 Work 辨认并行委派
- **WHEN** Global 派出两个 worker，又向其中一个追加说明
- **THEN** 用户在「派工关系」可辨认 Global 及其两项委派；追加说明与回传归属原 worker。用户可继续查看 Global 原生轨迹中的派工与沟通过程。
- **AND** 对新派出的一级 worker，查看这段关系无需打开子轨迹，也不提供会进入空白轨迹的链接。

### Requirement: 工作 worker 与 Nano 长期记忆解耦

#### Scenario: 派工与事后整理
- **WHEN** 用户把事项交给 worker，之后 Global 整理长期记忆
- **THEN** worker 收到任务和交办约束；Nano 不注入记忆正文、路径或读写指引，Dreaming 不从 worker 内部轨迹取材。

## 范围与非目标

本次仅覆盖本机 Global 一级派工，新派出的一级 worker 的逐步活动、工具记录和内部 helper 轨迹不纳入 Work 展示。不额外限制用户目录的普通文件访问。
