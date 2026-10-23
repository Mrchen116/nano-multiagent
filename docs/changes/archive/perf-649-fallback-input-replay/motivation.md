# perf-649: 线性归属回放降低 ModelFallback 收尾开销

## 原始诉求

> 用户已授权：“前三项适合开多少个unit，你就开多少个thread做。没有相互依赖关系吧？”

本聊天收到的明确分工（原文）：

> 你的范围：审计第2项，ModelFallback turn/end对全部历史input ID逐一调用inputEvidence(history,id)，即O(inputs×events)，成功且未fallback也执行。主要所有权 packages/dsh-integration/src/model-fallback.ts、input-evidence.ts及对应runtime测试；如果需要共享输入索引，由本unit负责，保持现有inputEvidence/session.lookup语义兼容。
>
> 目标：去除每轮全输入×全历史回放，用最简单的单遍或增量处理保持当前输入证据语义。不要为了本项强制其他unit消费新API。保持inbox splice、取消/未消费、恢复、逻辑turn、多attempt fallback、输入归属与错误重试等真实契约；按current代码建立必要回归，不机械保留坏实现。
>
> 验收：普通成功轮、无fallback配置、实际fallback及关键恢复/取消场景正确；长历史增长实验说明同步工作量改善、状态/内存边界。优先可复现合成fixture，不把私有生产历史提交仓库。

## 澄清记录

范围、Full 流程、独立门禁、归档及 Ready for review PR 已授权；不自动合并或部署。没有待澄清项。实施细节由本任务决定。

## 现状痛点

审计报告 `/Users/czj/.codex/reports/nano-performance-audit-20261023-2247/runtime/findings.md` R2、fallback-bench.ts 与 fallback-cost.jsonl 记录：4960 / 9921 / 19843 events 的同步循环为 28 / 138 / 670ms，最后仅一个本轮 input。此为离线回放测量，不能推断生产延迟占比。审计基线 236a4698c7a8a2d03efa00c35049914d2422771d；开工 main 893d903a00dff83c47b08310ed528b71eaae6786 的 model-fallback.ts 仍有该循环。

## 目标状态

每轮输入归属计算随历史事件及实际 inbox 变更量线性增长，消除历史 inputs 与 events 相乘的回放。合成 500/1000/2000 历史输入、固定每轮事件数与一个当前输入，统计等价结果及事件访问数；2000 输入场景目标至少减少 95% 事件访问、同机中位耗时至少改善 5 倍。不把绝对毫秒变成跨机器测试阈值。

## 用户侧验收标准（不变性）

### Requirement: 普通回复与未配置备用的行为不变
#### Scenario: 普通成功
- **WHEN** 用户在已有历史的会话发消息且主模型成功
- **THEN** 正常收到本轮回复，不将历史请求再次执行或归入本轮。
#### Scenario: 无备用失败
- **WHEN** 没有备用模型且主模型失败
- **THEN** 保持原失败结果，不自动借用其它模型。

### Requirement: 备用继续原请求并保留恢复与取消边界
#### Scenario: 备用成功
- **WHEN** 主模型可用性失败且符合现有切换条件
- **THEN** 自动继续原请求，成功后仍保持原有粘性与切换说明语义，不重复用户输入。
#### Scenario: 恢复或取消
- **WHEN** 备用成功后的会话重启，或备用执行中用户取消、发来新请求
- **THEN** 已接受请求继续按原持久记录恢复，取消不被重新唤醒，新请求不被旧请求抢占。

## 影响范围

仅 dsh-integration 输入归属回放及对应测试；不改变持久模型、协议、inputEvidence/session.lookup 返回语义、账单、安全审核和 DSH 公开 API 边界。无依赖其它在途 unit；不处理 descendants、PA lookup 调用次数、single-thread/store 对账或 usage。

## 迁移与回滚策略

无数据迁移，不重写已有历史；用现有公开事件重放。行为回归或性能目标未满足不交付；回滚本 unit 的代码即可恢复旧算法，持久记录仍兼容。
