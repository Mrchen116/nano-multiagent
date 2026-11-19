# feat-778 本机 Global worker 支持多种代码 Agent

## 原始需求

> 因为我想支持router派发各种worker agent，比如codex cli，claude code。

> 更接近是配置死，每台机子配置死

> 所以，我们的global agent派发subagent，我觉得不适合用现有的dsh工具，应自己造一个。

> 这里我给你派了两个活，一个是支持worker在各种codeagent。二是跨机。你分开做，第一个做完先提pr，第二个在第一个基础上做。我的亲自测过第一个好用，我再决定第二个。

> 这种你得参考raft针对我们场景思考，首先现在各种agent都有auto模式，你开的时候要auto，然后剩下还要审核的你就看raft的处理，和我们的产品理念来思考。我觉得大概是交给global agent来处理，现在好像也是这个逻辑

> 我想到的，memory现在还用worker的轨迹做总结，然后memory最终也给worker消费？我觉得这两项都可以去掉。worker完全不碰我们的记忆，不写不消费。不然跨机，跨agent框架很麻烦。

> 不是，只是说不注入，他非要去读，我也不管他呀。你不注入，他就不会去读了，所以不需要强加这种无谓的设计。

## 澄清记录

- 本次交付本机 worker 的 PR。跨机是后续独立决策，等待用户亲测本次体验。
- worker 框架为机器配置。首批讨论 DSH、Codex CLI、Claude Code。一级由 Nano 派工，内部 helper 由执行框架组织。
- 用户指定外部 worker 启动时采用 Auto。初步处理方案是把需要决策的具体动作、目标、原因送回 Global。Global 按已有授权澄清、缩小范围或向原 IM 用户征询决定。明确拒绝的动作保持拒绝。参照现有[Global 未获准动作处理](../../specs/gateway/global-agent.md)。
- Raft 参考版本为 5214e34e。其 [Claude 启动](https://github.com/botiverse/raft-source/blob/5214e34e/packages/daemon/src/drivers/claudeLaunch.ts#L127) 和 [Codex 启动](https://github.com/botiverse/raft-source/blob/5214e34e/packages/daemon/src/drivers/codex.ts#L1224) 使用无人值守的宽权限配置。该参考仅说明原生驱动方式；用户对 Nano 的要求是 Auto。
- 已确认现状。文档记忆会给普通一级 worker 注入所属 Agent 的记忆入口或快照；Dreaming 从一级工作轨迹提炼会话摘要，并可依来源回看后代。见[现行能力契约](../../specs/gateway/agent-capabilities.md)、[上下文装配](../../../packages/dsh-integration/src/knowledge/document-memory.ts)和[提炼输入](../../../packages/dsh-integration/src/knowledge/dreaming.ts)。
- 用户要求对所有工作 worker 取消 Nano 记忆消费和写入，并停止把工作 worker 轨迹作为 Dreaming 的材料。工作轨迹在 Work 中展示、原 worker 续做时使用自己的历史、Router 交办任务所需的具体约束，分别有独立的用途。
- 记忆按产品集成边界处理。Nano 不向工作 worker 注入记忆正文、目录或读写指引，Dreaming 不用工作 worker 轨迹做总结。普通文件读取沿用当前工作环境的权限，无需为 Nano 记忆增加文件拦截或沙箱。
- 待对齐外部 worker 在 Work 中的可见明细。现有 DSH 子执行可从派工展开到实际工具调用、结果和已报告的用量，见[Work 契约](../../specs/im/agent-work.md)。外部框架内部 helper 的展示范围也受此决定影响。

## 用户场景

## 验收标准

## 范围与非目标
