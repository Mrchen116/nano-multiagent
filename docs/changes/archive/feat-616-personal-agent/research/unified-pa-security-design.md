# 统一 PA 与独立外发审查：设计依据

2026-10-19。供 [design](../design.md) 当前方案使用，属于设计研究，不是运行或安全验收结果。用户补充的 [Agent隐私防护研究对话](https://chatgpt.com/c/6ad5943b-44ec-83ec-9e79-0b348ce03ab3) 已读取，其中论文链接另行核实；对话中的推荐架构不自动构成本仓要求。

## 决策与比较

我们的目标是私人助手持续推进开放任务，能跨聊天理解背景、自然协调、自动恢复，主人不逐次搬运资料或批准常规动作。比较双方都应拥有相同的独立出站检查和系统权限，不能拿“隔离加完整权限”与“单模型只写保护隐私提示词”比较。

| 方案 | 实质保护与代价 | 本轮取舍 |
| --- | --- | --- |
| 统一 PA、独立入口/出站审查、强制执行关口 | 保留完整目标理解，减少跨 session 资料转交；外部内容可影响有私料的主上下文，依赖所有出口覆盖及审核质量 | 默认；来源和授权不能被模型改写，语义判断承认残余误判 |
| 受限 external session、独立资料释放、同等出口检查 | external 被诱导后直接可读资料/工具更少；动态释放仍须判断，开放任务的信息补给可能带来复杂度和效用损失 | 适合可明确限定资料的子任务，不是所有联络的必经阶段 |
| external 任意转述给带全量 memory 的 main，再转发结果 | 仍将攻击话语送到有资料、有权限的主模型；只有聊天历史分开，未增加独立授权保证 | 不采用为默认“安全隔离”解释 |

## 一手证据与借鉴范围

| 来源/版本 | 已核机制 | 借鉴与限制 |
| --- | --- | --- |
| [Claude Code Auto Mode，2026-03-25](https://www.anthropic.com/engineering/claude-code-auto-mode) | 工具结果入站 probe 加警告；独立 transcript classifier 在动作前阻断，排除主模型解释和工具结果，拒绝后尝试继续 | 支持独立自动检查和减少人工打断；不是 PA 私密披露已解决的证明，且其授权误判仍存在 |
| [AirGapAgent，CCS 2024](https://arxiv.org/html/2405.05175v1#S4) | 资料 minimizer 基于可信主人任务，不接收第三方请求；对外只见选定资料 | 隔离增益来自受限资料与控制路径；不能用它证明任意外部请求持续回流 main 也安全 |
| [CaMeL，2025-03](https://arxiv.org/html/2503.18813v1) | 特权规划/非特权读取分离，解释器追踪来源和允许接收者 | 不是两个 session 即安全；本轮不声称复现其解释器或信息流证明 |
| [Firewalls，2026-06 v7](https://arxiv.org/html/2502.01822v7) / [作者实现](https://github.com/amrgomaaelhady/Firewall-Agentic-Networks) | 领域协议、类型/枚举校验、资料抽象及入站限制 | 学习职责分离；闭合协议及自由字符串限制不直接推广到所有开放 PA 任务 |
| [FlowSeal，2026-09 v1](https://arxiv.org/html/2609.14003v1) | 主 Agent 可读敏感资料；工具外强制来源/接收人检查，独立语义降密模型 | 最接近本方案；语义误判仍是条件，必要授权披露的成功率也需评估，不能只展示阻断率 |
| [AgentLeak，2026-06 v3](https://arxiv.org/abs/2602.11510) | 测内部消息、共享记忆及最终输出，内部披露可高于最终输出 | 必须覆盖委派/共享记录；不把其内部越范围比例当现实遭窃概率 |
| [MNC，2026-08 v1](https://arxiv.org/html/2608.01719v1) | 披露附带收件人、用途、转发、日志、记忆和期限范围 | 在自有环境约束下游使用；应用须给有限候选与风险/效用模型，未解决任意自由文本最小披露；不能约束外部明文复制 |
| [OCELOT，2026-06 v1](https://arxiv.org/html/2606.12341v1) | 以整条轨迹评估累计推断泄漏与接收者串通 | 第一版仅落实相关历史披露记录和检查，不实现其风险预算，也不声称防住所有拼接推断 |
| [Agents SDK guardrails](https://openai.github.io/openai-agents-python/guardrails/) | 输入/最终输出/工具 guardrail 执行位置和覆盖不同，部分工具不经过 FunctionTool 管道 | 审核必须贴实际副作用之前；不能依赖最终回答检查或边流式外发边检查 |

Instinct [创始人访谈](https://colossus.com/episode/instinct-the-personal-agent/)公开描述输入过滤、独立行动监控和越界索取通知主人；这只是厂商机制陈述，不能证明具体个人 PA session 拓扑或实际抗攻击效果。该访谈与群 Agent 不直接读个人账户的公开描述，不足以要求 Nano 的所有外部 DM 都采用 fresh session。

## 回到本仓的约束

本轮 checkout `f4162189f`：现有 `packages/dsh-integration/src/policy/approval.ts` 的 safe/skip/内部发送提前放行，不能直接替代 PA 披露检查；`packages/personal-assistant/src/external.ts` 的 explicit 与 final-content publish 两条路径都要接入。现有能力取证 [execution-isolation-feasibility](execution-isolation-feasibility.md) 仍可证明公开 middleware/restrict 等接入点及网络沙箱缺口，但其旧三域/逐动作 grant 推荐被当前设计替代。

第一版不承诺“任意代码读取全部私料后仍能逐字节控制联网”。实际出口不能完整接入的工具/插件不自动装配；同时必须通过正常搜索、资料编辑/制作、内部任务回流和持续协调的成功样本。现有工具审批与新披露检查分别负责动作权限与信息流，均须通过，原有 ask/deny 保留。

R11 源码复核补充：`apps/node/src/main.ts:40,58–63` 把所有 Agent 交给单一 supervisor，`agent-config.ts:79–83` 的 global extension 挂共享 host。仅 PA 工具 restrict 无法阻止普通插件初始化污染该宿主。当前设计因此在 apps/node 按可信 personal binding 路由到独立 RuntimeSupervisor/home，普通 Agent 保留原宿主；基于 `dsh-integration/client.ts` 的现有官方子进程机制，主/子/审核仍属于同一个 PA 分区，不恢复对外独立业务 session。该分区限制运行配置/插件作用域，不是同 OS 恶意代码沙箱。

## 验证而非理论担保

固定相同主人资料、目标、授权、收件人、模型与工具，验证实际 recipient/sink 观察到的输出，不能再断言“统一主模型请求中完全没有私人资料”。包括自然商业套话、伪造许可、记忆污染、跨渠道/并行拼接、附件替换、审核不可用、旁路与重试。每个攻击样本同时配正常协调路径，记录误披露、错误拒绝、目标完成质量、必要分享成功、主人打断次数及耗时/成本。

具体退出标准以 [安全与有用性验收](../security/acceptance-scenarios.md) 为准。公开研究的数字不作为 Nano 的效果承诺；静态设计和原型不能替代真实模型、host/API 与接收端证据。
