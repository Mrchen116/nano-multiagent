# feat-552 实施与验证记录

实施方式：用户授权的 change-orchestrator-simple；精简重复台账和大规模 code review，保留相关回归、真实产品旅程与聚焦改动的独立检查。

- Unit branch：`codex/feat-552`。
- 实施基线：`origin/main=2fd84b9ac2b1949947ac899b3de7fea1488731ef`。
- Gate 2：实施前准入核对 [design-review.md](design-review.md) Round 5，Approved，0 CRITICAL / 0 WARNING；当时 17 个受审输入哈希未变。后续范围内 runtime 接线与写入事实细化由独立实现对账核验。相对审查代码基线的新 main 只合入 JPEG 修复及旧 active 文档清理，无权限代码交叉。
- 现场：专属 unit worktree 与独立 Python 3.12.9 虚拟环境；主 checkout 的既有改动保留。

## 基线验证

2026-09-12，在任何产品修改前运行 Auto gate/config/Broker/dispatch/allowlist/result projection 及 Bash unit/integration 相关套件：148 passed。按本次新增/删除文件计算的整仓文档检查：0 issues。

## 实施范围与测试策略

- M1：共享策略/默认规则、来源投影与实时登记、拒绝计数/入口分流、子任务继承、Bash 语法和命令参数等价检查。
- M2：PA Inbox/send_message、共同 runtime 场景装配、global wake、Heartbeat/Cron 来源和交互接入。
- 优先更新已有 gate/config/Broker/result-projection、Bash、runtime/child、PA 入站与调度测试；新风险放在最低能暴露它的模块/集成边界，不重复保护同一失败原因。
- 固定 CC 规则/语法迁移需有完整映射和差分证据；协议层 fixture 与真实模型旅程分别记录，不能互相替代。

## 实现与已观察到的修正

M1/M2 产品实现、真实旅程、独立产品验收和实现对账均已完成：

- 固定策略、来源模板、defaults 和 Bash 命令/参数表成为随 wheel 分发的版本化资产；Bash 使用 tree-sitter 语法树与固定 CC fixture 对照。见 [policy adaptation](evidence/policy-adaptation.md) 和 [Bash port](evidence/bash-port-implementation.md)。
- 共享 gate 按原工具决定、Auto 分类、session 的 3/20 计数和实际入口分流；Global 普通主会话/child 返回 Agent，Heartbeat/Cron 仍按显式无人值守 fallback。PA runtime 装配见 [PA integration](evidence/pa-integration.md)。
- 输入和工具结果沿现有 metadata 持久化来源、物化 host context 和实际 outcome；内存中的 message/call/content 登记区分 live 与恢复。真实 SDK 测试暴露 transcript 原先丢弃这些新字段，已在既有 metadata 读写边界修正。普通跨 turn 保持 live，重新构建 kernel 后使用 restored，投影不重复调用。
- child 创建与 follow-up 从父会话取得当时可见上下文及有效 Auto 配置，并沿已接纳的委派输入保留快照；没有新增公开 provider/DTO。既有 `SessionRuntimeConfig` 增加可选 `auto_mode_interaction`，覆盖 PA 创建、读回、重配和恢复。
- 混合真人/通知输入拆分时保留同轮标记；主请求和审批请求使用相同的 CC 来源模板。系统通知没有升级为真人。
- HookRunner 原有 intercept 聚合只转交 approval，导致新决定来源丢失，已补齐既有返回映射；工具错误因此区分自动拒绝与审批无结论，后者不表述为用户否决。
- 聚焦代码审查发现并由独立 verifier 确认 fallback replay 会丢失已提交输入来源。新增 system、agent、mixed 三例均先 Red；修正重放入口复用已持久化的分段来源，并与 stranded pending continuation 共用现有恢复逻辑，相关 58 项 Green。只复验该 finding 及修复增量，不重跑大规模 finder。
- 真实 CLI 发现 Anthropic mapper 未传出 gate 已提供的 S1 停止序列；最小 mapper 回归先 Red（缺少字段），修复后相关 37 项 Green，随后真实 Terra 请求确认 `stop_sequences=["</block>"]`、2112 token 预算、禁用 thinking 和完整 policy 均已出站。见 [CLI journey](evidence/cli-real-journey.md)。

## 独立验收发现与修正

独立实现对账 Round 1 的两项 WARNING 已在 `b218d31e4` 修复，保留原报告和定点 closure：审批故障触发人工入口后，用户实际否决必须保留用户拒绝语义；结构化 `ModelError` 的 `context_length_exceeded` 必须归为上下文超限。现有反馈/gate 测试扩展先得到 4 个有效失败，修复后相关 84 项通过。只消费已有标准错误字段，未增加模型替换、重试或新协议。

产品 reviewer 的新隔离栈还暴露旧 Global journal 与全新 IM 数据混用：此前 `e2e-up.sh` 清理了其他运行数据库，却遗漏 `global_agent.sqlite3`，旧 work 同步得到 `scope_not_allowed`，使新 Global 请求无法开跑。同一提交在原有新数据清理边界补齐 journal 及 sidecars；reviewer 重启后新真人请求已进入主 session，完整旅程结论由 [acceptance](acceptance.md) 记录。未调整生产数据或 Gateway 运行逻辑。

## 当前验证快照

2026-09-12，实施 worktree：

- 最终代码 `10bf12c44` 的 CI 等价 Python 两组检查：agent/PA 1870 passed；其余 1923 passed，共 3793 项。未运行标记为 e2e 的套件作为这些计数的一部分；真实旅程另列。
- Ruff check / format check、`git diff --check` 通过；将本 unit 新文档纳入待跟踪集合的 docs-check 为 0 issues。
- `uv build --wheel` 成功，逐项比对 wheel 包含全部 11 个策略/命令资产。
- 前端依赖安装完成；critical 级 dependency audit 通过，79 个测试文件 / 745 tests passed。未改动前端代码或 lockfile。
- T1 的真实 CLI 写文件、unittest、loopback HTTP 服务和停止清理通过；使用现有 CLI kernel factory 注入点的隔离真实 SDK 装配，默认 CLI factory 的个人配置读取不在该证据覆盖内。
- T1 的[真实单聊天](evidence/single-chat-real-journey.md)也完成文件创建、unittest 和 loopback HTTP 服务清理；实际捕获一个 S1 block → S2 allow，六份审批请求保留正确阶段参数。
- T6 的[真实 Global Heartbeat 对照](evidence/heartbeat-real-journey.md)通过：真实 Sol 在 Global main 发起写入，审批端点无监听并在 S1 超时；显式 allow 实际生成文件，显式 deny 未执行，均保留 classifier_unavailable 故障类别且无 pending permission。代理修复后普通 Global wake/child 对照也完成：即使配置 fallback=allow，两次真实 write 均无结论而未执行，独立事项仍被委派处理；故障未被说成用户否决。T6 其余矩阵以确定性契约测试为证。
- [T2–T5 全局真实旅程](evidence/global-real-journeys.md)：跨聊天确认 3/3、明确一次性 Cron 创建和实际 write 3/3；无关同意、引用伪造、拒绝和部分批准组合通过；真实 compact 及同数据 Gateway 重启后可继续。结构化证据明确不同 Web owner 的额外消息被 ingress 404 拒绝，并未声称模型实际判读过它。
- [T8 真实 child/follow-up](evidence/child-real-journey.md)完成两次经 Terra 审批的写入，原真人范围及 Agent 来源保留；伪造批准文件未扩大范围，无关聊天零消息。未发生的越权工具提议没有被写成 gate deny。
- 首次 T3 的外部代理 strict 问题已在用户授权后修复并重启本机代理，外部提交 `016f32e`；持久回归先 Red，转换与路由 56 项通过，实际 `/v1/messages` 转换恢复可选参数语义。见[完整证据](evidence/proxy-strict-blocker.md)。
- 对同一真实 Cron 用户原话、当前动作和此前历史完成[旧/新审批 A/B](evidence/old-new-classifier-comparison.md)：每分支一次，两者均 S1 allow。没有为得到拒绝反复试探，也不据此声称误拒率下降。

收尾状态：实现及适用独立验收已完成，已核对的 delta 归入 canonical，整个 unit 随 PR 归档。所有验收服务均已停止；交付以对应 PR 的 required CI 结果为准。未合并、未部署 Nano。

## 独立 Cron 误拒的事实补齐

产品 reviewer 的独立 Cron 注册成功，但到点写入被 Terra 拒绝。S1 说可能覆盖既有文件，S2 直接断言目标已存在；注册后和触发前的观察均表明该文件不存在。实际审批输入没有文件存在性事实，不能将此失败写成用户未授权。

修复在现有 Write permission check 中核对实际 cwd 下的目标，并以既有 passthrough reason 附到当前动作。原参数、CC policy、scheduled 模板、阶段规则和权限决定保持不变，没有新增 DTO、工具方法或免审路径。现有 gate dispatch 以真实 WriteTool 覆盖存在/不存在及相对/绝对路径，4 项先 Red，相关 117 项 Green；分类器仍可 deny，新建和已有目标均不会提前写入。

一次有界真实请求复验保留原失败的 scheduled 原文、动作、路径、内容和 policy，仅加入实际工具检查的目标不存在事实：Terra S1 返回 `<block>no</block>`。未执行工具，不能代替真实 Cron 入口 closure。记录位于本机代理 `2026-09-12_13-00-40_247_feat552-write-state-fixed-replay`，响应 ID `msg_c9a1b7141a274a6bab9dfe135f100e4c`。临时客户端最初把 SSE 当 JSON 读取而报解析错误；实际模型响应由代理原始记录核对，没有重试挑样本。

独立验收同时发现 Cron 无法遵循“只回发起聊天”的结果目标要求。已核对执行/投递文件与 `origin/main=2fd84b9ac` 完全一致，当前路径使用 owner-direct 目标，非本 unit 引入的权限回归。按范围边界另记 [issue #293](https://github.com/Mrchen116/nano-multiagent/issues/293)，保留同 owner 两聊天的观察，不将期间 compact 与目标选择推断为因果。

## 最终里程碑与验收有效性

| 目标 | 退出证据 |
|---|---|
| M1 shared-auto-migration | 固定 CC policy/来源/Bash 资产、配置与计数、SDK 来源/子任务接线均已核对；完整 Python 3793 项、前端 745 项和 wheel 11 资产验证通过。独立 reviewer 追加原生默认工厂 CLI 创建/读回，单聊天真实人工 allow_once 与带理由 deny 均闭环。 |
| M2 global-chat-confirmation | 独立 reviewer 真实确认、跨聊天独立工作、部分批准、引用边界、child、compact/正常重启均通过；修复后原 Cron 请求仅改时间即真实创建目标文件，三次有效策略拒绝后仍能处理另一聊天且无 pending permission。 |

- 产品验收：[acceptance](acceptance.md) 最终 Round 3 保留前轮失败与逐项 closure；已知范围外 Cron 投递目标缺口跟踪 #293。
- 实现对账：[verification](verification.md) 完整核验、W1/W2 closure、写入事实增量 closure 均通过；六份 delta 的 corrected-delta `aligned` 结论随最后增量继续有效。
- 代码审查：[code review](code-review.md) 初始完整范围及 replay、审批语义、写入事实的必要增量均无存活 findings，有效产品代码为 `10bf12c44`。
- 收尾只展开完整 delta、归并对应 canonical 条目/派生数量、增加配置操作指南并移动归档位置；没有改动产品代码、测试或策略资产，因此不使上述通过范围失效。
- 最终同步基线 `origin/main=2fd84b9ac2b1949947ac899b3de7fea1488731ef`，没有新的 main 增量需要整合。主 checkout 保留原分支和所有原有改动。

## 同一 PR 追加：工作区 Write/Edit 直接放行

用户在同模型 CC 对照后明确要求修正 Nano。恢复 PR #294 的独立干净 worktree，主 checkout 不变。此增量补齐 M1 的 acceptEdits 直接放行分支，同时共用 write/edit 的路径判断并保留敏感路径、目录外分类与执行时读取约束。范围、8 个 Red / 135 个 Green、固定 CC 来源及历史证据失效说明见 [补漏证据](evidence/workspace-file-fastpath.md)。独立 patch review、实现对账和真实 Cron 增量验收分别追加到现有报告。

`b9a61941a` 实现路径补漏，`1cf086696` 在实际复现 macOS `/var` 与 `/private/var` 同目录别名后补齐 CC 的系统别名规则；额外 2 个 Red，最终聚焦 137 passed。最后代码上的独立真实 Cron Write/Edit 成功，5 次 Sol / 0 次 Terra；目录外仍发出 Terra 请求。产品 Round 5 pass、实现 Round 4 pass / aligned、聚焦代码审查无 findings，`validated_at=1cf086696`，`executed_base=effective_base=2fd84b9ac`。此前完整范围继续有效，但旧 inside 文件分类轨迹按证据说明被新行为替代。

新增 delta 与 canonical 已逐字核对，Tools and Hooks 派生数量同步为 16；其后提交只含报告和契约。两轮真实验收进程均清理，主 checkout 保持原状；原 PR #294 承接本次增量，未合并、未部署。
