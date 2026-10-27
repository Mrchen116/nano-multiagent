# feat-668: Auto 审核内有界恢复

> 本任务在独立基线原创时编号625；final sync发现main已有另一625设计目录，按原子分配规范迁至668。不是复用或替换main旧设计；沿革与新基线门禁见 [sync-review.md](sync-review.md)。

## 来源与生命周期

- 需求：[GitHub #361](https://github.com/Mrchen116/nano-multiagent/issues/361)，本次直接 `gh issue view 361 --repo Mrchen116/nano-multiagent` 读取；不以其中旧基线调查作为本次源码验证。
- Full feature；本文件只收口目标，独立设计审查、实施与产品门禁尚未执行。设计见 [design.md](design.md)。

## 原始需求

Issue 原话（问题、范围与验收）：

> 为 Auto 自动审核模型请求增加有界、可取消的失败重试。临时模型服务故障应优先在一次审核内恢复，避免立即变成工具拒绝，再让主 Agent 反复调用同一个工具。此 issue 仅记录后续实现，不在本轮修改代码。
>
> - 对 429/503、传输错误等可恢复故障，在同一审核内进行有限重试；明确次数、总时长、退避和取消边界。
> - 对超时和非法/空判定明确独立策略，不把所有失败都盲目重试。
> - 真实策略 deny、认证/配置错误不作为临时故障重试；不改变授权边界，不自动放行。
> - 重试期间不得执行工具体；仅有效 allow 后执行一次。耗尽后保留现有人工/return_to_agent/unattended 路由，明确标注技术不可用。
> - 复用 DSH 公开的错误分类/重试策略能力（若适用），不 private import 或 patch DSH。
> - 审计能区分一次审核内的 attempts 与主 Agent 再次发起的工具调用，记录模型、最终原因、耗时及可得 usage。
>
> - [ ] 503 后成功：审核自动重试后 allow，工具恰好执行一次，主 Agent 不必重新调用。
> - [ ] 持续 503：在预算内停止，工具零执行，最终路由和原因准确。
> - [ ] 有效 deny、永久错误不误重试；取消中断请求/退避且不启动后续尝试。
> - [ ] 非法判定、超时策略有针对性验证；两阶段审核语义不改变。
> - [ ] 使用真实全局 Agent 重跑自建插件→安装→两次真实调用，Work 保留可检查轨迹；真实服务可用性与确定性故障注入证据分别报告。

## 澄清记录

委派中已明确的约束原话，不虚构额外 Q/A：

> Requirements: CC and Codex strategies retained; transient service/transport/timeout combined maximum2 EXTRA attempts; each gets normal full90s budget independently; blank/invalid recovery max1 and shares2 extra cap; deny/auth/config no retry; cancel active request/backoff and no next; tool0 during retry then exactly1 on allow; exhausted existing routing retained; audit distinguish internal attempts from new tool calls and service/invalid/timeout.

> Ground design in actual baseline public DSH exports. No code implementation.

Agent 解读：上限是一次工具审核内首次之外最多两次恢复，不是每类错误各两次；有效最终 deny 不能因重试翻成 allow。CC 的正常两阶段判定与 Codex 的证据预算恢复不等同于服务失败重试。90 秒是每次完整审核尝试的新预算，不是所有尝试共享的截止时间。保留既有无人值守显式 fallback，不新增默认放行。

## 用户场景

1. 用户让全局 Agent 自建核算插件、安装并计算两组数据。审核服务短暂失效时，Agent 不应为了恢复审核重复安装调用；成功审核后该调用执行一次。
2. 服务持续失败、返回空白/无效答案或响应超时，用户获得有界且准确的技术不可用结果，而不是无限等待或安全拒绝计数增长；真正不允许的操作仍被阻断。
3. 用户在等待审核或退避时停止任务，操作不发生，迟到的审核结果不能复活它。
4. 运维者查看同一工作的审核记录，分清同一次调用的内部恢复、Agent 发起的新调用与故障类别；实际模型用量可查，不把缺失用量当成零。

## 验收标准

### Requirement: 临时故障在同一审核内有限恢复

#### Scenario: 服务恢复后继续原操作
- **WHEN** 审核先遇到暂时服务故障，随后在恢复额度内有效允许原操作
- **THEN** 原操作只执行一次；主 Agent 不需重新调用该工具来恢复审核。
- **AND** 恢复等待期间不发生该操作的副作用，CC 和 Codex 原有授权标准均不降低。

#### Scenario: 持续故障耗尽
- **WHEN** 审核连续遇到可恢复服务、传输或超时故障
- **THEN** 首次之外最多两次尝试，每次可使用独立的正常 90 秒审核预算；有界退避后仍无结果则停止自动恢复。
- **AND** 非放行分流中工具不执行，用户获得技术不可用而非安全拒绝；既有人工、交回 Agent 与无人值守配置分流保留，不新增自动放行。

### Requirement: 空白、无效与永久失败采用不同边界

#### Scenario: 空白或非法判定
- **WHEN** 审核未给出有效判定
- **THEN** 最多进行一次此类恢复，并与服务、传输和超时恢复共用两次额外尝试上限；仍无有效判定则按技术不可用分流。

#### Scenario: 明确拒绝或认证配置错误
- **WHEN** 审核给出有效最终拒绝，或服务因认证、配置错误不可用
- **THEN** 不为了改变该结果而自动重试；真实拒绝沿原策略处理，认证配置错误明确为技术不可用。
- **AND** CC 正常两阶段审查仍可完成第二阶段，不被误称为失败恢复。

### Requirement: 停止优先于恢复和执行

#### Scenario: 请求中或退避时停止
- **WHEN** 用户在请求中或退避等待时停止工作
- **THEN** 当前审核及等待被取消，不再发起下一次尝试，工具不执行；迟到的结果不会恢复操作或弹出新审批。

### Requirement: 工作结果与审核恢复可核查

#### Scenario: 分清恢复与新调用
- **WHEN** 用户或运维者检查一次工具操作的审核记录
- **THEN** 可区分内部尝试与新工具调用，并看到审核模型、服务故障/无效判定/超时/取消等原因、实际耗时及可获得的用量。

#### Scenario: 全局 Agent 插件真实旅程
- **WHEN** 用户让真实全局 Agent 自建核算插件、安装并执行两组计算
- **THEN** Work 中保留可检查的创建、安装与两次真实调用轨迹和结果；独立报告真实服务可用性与确定性故障注入结果，不用模拟成功冒充真实模型成功。

## 范围与非目标

- 范围：Auto 审核请求的恢复、取消、结构化失败归因与审计；CC、Codex 及共享分类路径的兼容性；真实产品验收。
- 非目标：更换策略或审核模型、修改授权依据、主 Agent 通用防循环、供应商可用性治理、插件 preview/API 重设计、DSH fork/patch、生产运行时或 4000 端口环境变更。
- 本 author 只产出文档；Full 后续阶段由 executor 负责，不能把设计交接等同于最终交付。
