# feat-552 实施与验证记录

实施方式：用户授权的 change-orchestrator-simple；精简重复台账和大规模 code review，保留相关回归、真实产品旅程与聚焦改动的独立检查。

- Unit branch：`codex/feat-552`。
- 实施基线：`origin/main=2fd84b9ac2b1949947ac899b3de7fea1488731ef`。
- Gate 2：[design-review.md](design-review.md) Round 5，Approved，0 CRITICAL / 0 WARNING；17 个受审输入哈希未变。相对审查代码基线的新 main 只合入 JPEG 修复及旧 active 文档清理，无权限代码交叉。
- 现场：专属 unit worktree 与独立 Python 3.12.9 虚拟环境；主 checkout 的既有改动保留。

## 基线验证

2026-09-12，在任何产品修改前运行 Auto gate/config/Broker/dispatch/allowlist/result projection 及 Bash unit/integration 相关套件：148 passed。按本次新增/删除文件计算的整仓文档检查：0 issues。

## 实施范围与测试策略

- M1：共享策略/默认规则、来源投影与实时登记、拒绝计数/入口分流、子任务继承、Bash 语法和命令参数等价检查。
- M2：PA Inbox/send_message、共同 runtime 场景装配、global wake、Heartbeat/Cron 来源和交互接入。
- 优先更新已有 gate/config/Broker/result-projection、Bash、runtime/child、PA 入站与调度测试；新风险放在最低能暴露它的模块/集成边界，不重复保护同一失败原因。
- 固定 CC 规则/语法迁移需有完整映射和差分证据；协议层 fixture 与真实模型旅程分别记录，不能互相替代。

## 实现与已观察到的修正

M1/M2 的产品实现已落入本 worktree，实际旅程已取得下列证据，待独立产品验收和实现对账：

- 固定策略、来源模板、defaults 和 Bash 命令/参数表成为随 wheel 分发的版本化资产；Bash 使用 tree-sitter 语法树与固定 CC fixture 对照。见 [policy adaptation](evidence/policy-adaptation.md) 和 [Bash port](evidence/bash-port-implementation.md)。
- 共享 gate 按原工具决定、Auto 分类、session 的 3/20 计数和实际入口分流；Global 普通主会话/child 返回 Agent，Heartbeat/Cron 仍按显式无人值守 fallback。PA runtime 装配见 [PA integration](evidence/pa-integration.md)。
- 输入和工具结果沿现有 metadata 持久化来源、物化 host context 和实际 outcome；内存中的 message/call/content 登记区分 live 与恢复。真实 SDK 测试暴露 transcript 原先丢弃这些新字段，已在既有 metadata 读写边界修正。普通跨 turn 保持 live，重新构建 kernel 后使用 restored，投影不重复调用。
- child 创建与 follow-up 从父会话取得当时可见上下文及有效 Auto 配置，并沿已接纳的委派输入保留快照；没有新增公开 provider/DTO。既有 `SessionRuntimeConfig` 增加可选 `auto_mode_interaction`，覆盖 PA 创建、读回、重配和恢复。
- 混合真人/通知输入拆分时保留同轮标记；主请求和审批请求使用相同的 CC 来源模板。系统通知没有升级为真人。
- HookRunner 原有 intercept 聚合只转交 approval，导致新决定来源丢失，已补齐既有返回映射；工具错误因此区分自动拒绝与审批无结论，后者不表述为用户否决。
- 聚焦代码审查发现并由独立 verifier 确认 fallback replay 会丢失已提交输入来源。新增 system、agent、mixed 三例均先 Red；修正重放入口复用已持久化的分段来源，并与 stranded pending continuation 共用现有恢复逻辑，相关 58 项 Green。只复验该 finding 及修复增量，不重跑大规模 finder。
- 真实 CLI 发现 Anthropic mapper 未传出 gate 已提供的 S1 停止序列；最小 mapper 回归先 Red（缺少字段），修复后相关 37 项 Green，随后真实 Terra 请求确认 `stop_sequences=["</block>"]`、2112 token 预算、禁用 thinking 和完整 policy 均已出站。见 [CLI journey](evidence/cli-real-journey.md)。

## 当前验证快照

2026-09-12，实施 worktree：

- 修复并独立复验 replay 后重新运行 CI 等价 Python 两组检查：agent/PA 1870 passed；其余 1914 passed，共 3784 项。未运行标记为 e2e 的套件作为这些计数的一部分；真实旅程另列。
- Ruff check / format check、`git diff --check` 通过；将本 unit 新文档纳入待跟踪集合的 docs-check 为 0 issues。
- `uv build --wheel` 成功，逐项比对 wheel 包含全部 11 个策略/命令资产。
- 前端依赖安装完成；critical 级 dependency audit 通过，79 个测试文件 / 745 tests passed。未改动前端代码或 lockfile。
- T1 的真实 CLI 写文件、unittest、loopback HTTP 服务和停止清理通过；使用现有 CLI kernel factory 注入点的隔离真实 SDK 装配，默认 CLI factory 的个人配置读取不在该证据覆盖内。
- T1 的[真实单聊天](evidence/single-chat-real-journey.md)也完成文件创建、unittest 和 loopback HTTP 服务清理；实际捕获一个 S1 block → S2 allow，六份审批请求保留正确阶段参数。
- T6 的[真实 Global Heartbeat 对照](evidence/heartbeat-real-journey.md)通过：真实 Sol 在 Global main 发起写入，审批端点无监听并在 S1 超时；显式 allow 实际生成文件，显式 deny 未执行，均保留 classifier_unavailable 故障类别且无 pending permission。代理修复后普通 Global wake/child 对照也完成：即使配置 fallback=allow，两次真实 write 均无结论而未执行，独立事项仍被委派处理；故障未被说成用户否决。T6 其余矩阵以确定性契约测试为证。
- [T2–T5 全局真实旅程](evidence/global-real-journeys.md)：跨聊天确认 3/3、明确一次性 Cron 创建和实际 write 3/3；无关同意、引用伪造、拒绝和部分批准组合通过；真实 compact 及同数据 Gateway 重启后可继续。结构化证据明确不同 Web owner 的额外消息被 ingress 404 拒绝，并未声称模型实际判读过它。
- [T8 真实 child/follow-up](evidence/child-real-journey.md)完成两次经 Terra 审批的写入，原真人范围及 Agent 来源保留；伪造批准文件未扩大范围，无关聊天零消息。未发生的越权工具提议没有被写成 gate deny。
- 首次 T3 的外部代理 strict 问题已在用户授权后修复并重启本机代理，外部提交 `016f32e`；持久回归先 Red，转换与路由 56 项通过，实际 `/v1/messages` 转换恢复可选参数语义。见[完整证据](evidence/proxy-strict-blocker.md)。

当前状态：共享实现和聚焦代码审查已提交到 `codex/feat-552`；外部阻塞已解除，执行者真实旅程已完成，进入独立产品验收和实现对账。Heartbeat 独立测试栈及 CLI/单聊天临时服务已停止；主 unit 隔离栈由集成者管理，验收接管前及最终交付前清理。尚未归档或创建 PR，未合并、未部署 Nano。
