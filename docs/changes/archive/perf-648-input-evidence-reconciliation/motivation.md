# perf-648: 已结束输入的对账证据复用

## 原始诉求

用户授权：“前三项适合开多少个unit，你就开多少个thread做。没有相互依赖关系吧？”

本聊天派发范围原文：

> 目标：常态对账仅查尚未终结或证据缺失的输入，可靠复用已最终确定证据；长历史完成输入不再引发线性RPC。
> 注意物理attempt的turn/end或store.terminal非空未必等于fallback逻辑run终结，不能凭这个字段草率跳过；利用现有权威modelRuns/evidence语义保持正确，不把新共享runtime API作为依赖。
> 验收：全部已终结且零新事件时不逐个lookup，少量新增/待定输入时查询只随待处理规模增长；fallback切换/逻辑终态、receipt未确认、重启恢复、取消/输入未消费等适用情形不漏交付不重复交付。
> 本项不修流式逐片ACK、usage或其他审计项。

## 澄清记录

范围、Full 流程、独立门禁、Ready for review PR 和 required CI 全绿已授权；不自动 merge 或部署。没有待澄清项。Agent 解读：只优化 PA 输入对账选择，不改变 runtime 协议、执行或交付语义，不依赖其他并行 unit。

## 现状痛点

审计基线 `236a4698c7a8a2d03efa00c35049914d2422771d`，报告 `/Users/czj/.codex/reports/nano-performance-audit-20261023-2247/root/findings.md` R1、同目录 `lookup-probe.mts` 与 `results.jsonl`。真实 SingleThread/NodeStore 搭配模拟 runtime：1000 个已经完成交付和 receipt 的输入、零新事件，仍执行 1000 次 lookup；每次人为延迟 1 ms 时共 1155 ms。这不是生产 RTT 或生产耗时占比。

开工核实 main/origin/main 均为 `893d903a00dff83c47b08310ed528b71eaae6786`，`single-thread.ts` drain 仍 observe 后全量串行 lookup，问题仍在。

## 目标状态

稳定历史输入的已确定事实可以跨对账和重启复用；全部最终结束且证据齐全时零逐输入回查，1000 个历史输入加 K 个未定输入时回查规模至多 K。升级前没有可信终态证据的输入允许一次补证据，此后不反复回查。未结束或不能确定的输入保持恢复能力，不以性能目标牺牲正确交付。

## 用户侧验收标准（不变性）

### Requirement: 同一聊天持续回复且历史结果不重复

#### Scenario: 长聊天继续发送和恢复
- **WHEN** 用户在已有完成回复的聊天中继续发送消息，或节点重连后继续聊天
- **THEN** 新回复仍回到原聊天，旧回复不重复，新输入不遗漏，与变更前一致。

### Requirement: 运行和投递的中间状态不冒充完成

#### Scenario: 备用模型和交付恢复
- **WHEN** 一次回复需要切换备用模型，或回复完成时回执连接中断后恢复
- **THEN** 用户仍得到最终有效回复和既有切换提示；恢复不会重复回复，也不会把备用尝试中的临时失败当成整次回复完成，与变更前一致。

## 影响范围

PA single_thread 对账和必要的 NodeStore 证据查询、持久化及其测试。保持账单、恢复、安全审核、DSH 公开 API 边界。未消费输入及取消行为属于实现层回归面，不新定义产品取消/receipt 语义。不改 runtime 的 input-evidence/model-fallback、轨迹 descendants、流式 ACK 和 usage。

## 迁移与回滚策略

旧 NodeStore 数据保留，历史输入按缺失证据处理并逐步收敛；不得依据已有 terminal 字段批量猜测完成。回滚 PA 实现恢复原全量查询，新增的内部证据不能改变旧版数据库读取和交付记录。出现漏查或错误收敛即停止交付并修正。
