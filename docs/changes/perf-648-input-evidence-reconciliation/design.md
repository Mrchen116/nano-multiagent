# perf-648: 已结束输入的对账证据复用 — 技术方案

> 对齐: motivation.md

## Changelog

## 现状分析

### 涉及范围

`packages/personal-assistant/src/single-thread.ts` 的 drain 在 durable observe 后回查全部输入，再依据逻辑事件准备交付和发送 receipt。`store.ts` inputs 持久化 accepted/turn/terminal，但未记录这些值是否已由权威逻辑运行最终确定。`global-agent.ts` 共用 inputEvidence，但其对账策略不在本项范围。

### 既有约束

PA 仅经 RuntimeClient 使用公开 session.observe/session.lookup；不引入 DSH 依赖，不修改 runtime。最终证据和交付 ACK 是两件事，不能因证据已固定跳过交付或 receipt 恢复。既有数据库可升级可回滚，不覆盖业务状态。

### 可复用能力

使用 lookup 返回的 accepted/pending/turn/terminal 和 observe 的 modelRuns；后者可按逻辑 turn 及 attempts 关联。runtime `model-fallback.ts` evidence 对运行中的逻辑 run 隐藏 terminal、映射 logical turn；completed run 才返回最终 terminal。`input-evidence.ts` 对取消未消费输入给出 cancelled-before-consumption；pending 表明输入仍在 inbox。复用 store 已有 inputEvidence、交付表、receipt 幂等逻辑，不增加 runtime API。只保留轻量终态标记，不重复存储整个 modelRuns 或事件历史。

### 相关历史

现有模型切换逻辑来自仓库已有 fallback 实现和 `docs/specs/gateway/agent-capabilities.md` 的“备用模型”契约；回执恢复遵循 `routing-delivery.md`。本轮并行审计 unit 分别负责 usage/fallback 历史重放及 descendants 同步，本 unit 不依赖其未合并代码。开工基线 893d903a0 的全量回查与审计基线一致。

## 架构总览

从“每次读取所有 payload 并逐个 RPC”变为“SQL 选择尚未固定证据的 input id 并逐个 RPC”。交付阶段仍使用所有输入及现有逻辑事件，不把本次优化扩大到交付算法或事件历史重放。

## 关键决策

**只缓存 fresh lookup 的最终证据，不能推断旧 terminal。** 新增 inputs.evidence_final 默认 0。历史行不回填猜测；首次对账逐行查询并收敛。fresh evidence 必须 accepted=true、pending=false、terminal 非空。若 observe 中存在关联 logical turn 或 attempt turn 的 run，还必须 state=completed；running/switching 一律不收敛。不存在关联 run 时，lookup 的既有权威语义允许普通/旧会话终态或 cancelled-before-consumption 收敛；非空旧 store.terminal 不参与判断。lookup 晚于 observe、看到已完成而 observe 仍 running 时延迟一个 drain 收敛，保守而安全。

**证据收敛独立于 delivery/receipt。** 在同一 SQL UPDATE 写入 accepted/turn/terminal 和 evidence_final，receipt 未确认时也可缓存最终运行证据，但每次 drain 仍经过原交付恢复路径。取消未消费且没有 turn 的输入可收敛证据，维持现有无 turn 交付行为，不新增完成 receipt。

**用一个可索引字段，不建立另一套运行状态机。** 创建/升级数据库时为 inputs 添加缺失的 evidence_final INTEGER NOT NULL DEFAULT 0；建立 (session_id,evidence_final) 索引。receive 保持默认待查询；inputEvidence 的可选 final 参数缺省 false，Global 原有调用行为保持。新增 lookupInputIds(sessionId) 仅返回 evidence_final=0 的 id，避免历史 payload 反序列化。无定时失效、重试框架、缓存 TTL 或新共享协议。

## 接口与数据流

1. durable observe、recordEvents、记录 modelRuns 保持原序。
2. 遍历 lookupInputIds，只执行待定 input 的 session.lookup。
3. 依据上述 final 判据，原子持久化证据与标记。
4. 原交付遍历、logicalEvents、modelNotices、delivery 和 receipt 路径照常运行。
5. 重启从同一 SQLite 恢复标记；未固定的 pending、未消费、证据缺失、fallback switching 继续 lookup。

## 契约层增量 (delta-spec)

no spec delta：纯内部性能优化，保留 `docs/specs/gateway/routing-delivery.md`、`agent-capabilities.md` 的可观察行为。不承诺生产延迟百分比。

## 风险与回退

最大的风险是错误缓存物理终态或忽略回执恢复；以 switching/multiple-attempt/最终逻辑终态、同一 DB 重开、ACK 故障的集成测试保护。旧数据库升级只加字段和索引；回滚应用会忽略字段并恢复全量查询。缺少 pending 的证据不收敛，避免将不完整 evidence 当最终事实。若 protocol 无法证明目标，先报告最小缺口，不改其他 unit 的 runtime。

## Runbook for Reviewer

本 unit 修改 Node 内 PA，无客户端面变化。caller 在专属 unit worktree 用 `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <worktree>` 准备真实 IM + Node + DSH；停止使用 `./scripts/e2e-down.sh --wt <worktree>`。健康检查 `.e2e-ports.env` 对应 IM /health 与 Node online，并核实 PID/cwd/构建版本。

**Review 驱动方式**：端到端真栈；使用客户端同一 IM API 发送和读取消息。按 motivation 两个场景验证同一聊天连续回复、重启不重发，以及在隔离配置中触发备用模型和连接恢复。复杂的未消费取消/精确 RPC 数量属于 worker 协议测试，不以模拟计时代替产品体验。

**验收前置**：仓库 config/e2e/gateway.yaml 专用测试身份和已配置本地 LLM proxy；由 caller 检查可用性并准备。所有端口、config、数据、workspace、owner/node identity 独立，禁止使用生产实例。不引入外部收件人。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-pending-evidence | 可信最终证据复用 | 无 | 单一 | PA single-thread.ts/store.ts 与 PA tests | [worker] 1000 历史完成输入补证据后零事件 drain 为 0 lookup，加 K 待定输入仅 K lookup；fresh 终态和 receipt 未确认可独立恢复；fallback switching/多 attempt、未消费/取消、旧 DB 升级与重启覆盖；窄测试、构建及适用本地 CI 通过。[reviewer] motivation 两个 Scenario 保持原聊天回复、fallback 最终结果和恢复不重复。 |
