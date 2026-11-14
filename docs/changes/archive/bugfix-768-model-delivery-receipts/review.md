# bugfix-768 交付审查

## 范围与证据

执行基线 `9f900ff3ba355414cb442f9211c3a8e17e391428`；独立审查者 `/root/review_recovery`（gpt-6.1-sol / high），组合 change-code-review 与 agent-context-review。首次冻结 `e8cdd54b9`，集中修复 `b0e4f4c82`，最后迁移修复 `9bfbb7d3d`；后续不改变本 unit 行为的集成、记录和归档沿用结论。

实际模型输入通过真实锁定 DSH 与受控 HTTP provider 捕获，检查提醒出现在实际出站 messages，再核对响应与持久 outbox／PA 回执／IM 投影。此证据证明装配与时点，不宣称验证了模型内部理解、实体合盖或生产部署。

## 独立问题与闭环

- P2：空文本 block-end 也被当成有效模型内容。审查者用真实 Anthropic SSE 空块加提前 EOF 复现。修复要求非空文本／思考／工具参数增量或实际内容块；参数化回归同时证明非空部分响应即便随后失败仍可成为模型收到提醒的证据。CLOSED。
- P2：中心迁移误降级 single_thread 的真实回执。修复仅迁移当前 Global Agent 收件人；独立 SQLite CLI 测试证明保留 single_thread、真人与已读，重复迁移不回退新送达。CLOSED。
- P2：未被接纳的后台冻结快照在来源撤销后仍被复用。明确 busy 或 lookup 确认未接纳后丢弃旧快照，再按当前来源授权冻结；新回归保留一个 observer 并撤销另一个，实际提交摘要不再含撤销 target。已接纳快照仍保留原身份。CLOSED。
- P2：旧回执恢复标记在原生入队时过早清除。修复为模型送达投影后按尚未送达的历史消息结算；进程中断在原 acceptedSeq 后建立恢复身份，有限技术错误只在显式恢复时建立下一代，用户 aborted 不自动重启。新的普通提醒覆盖迁移消息时也可清标记。独立 closure 对 `9bfbb7d3d` 判定 CLOSED、契约 aligned。

## 验证记录

初始七文件 105 项通过（`/tmp/nano-768-green.log`），旧 Gateway accepted 红测和禁用模型响应 hook 的原生红测均失败于目标断言。三种 provider 回应（HTTP 错误、空块提前结束、非空部分回应）与队列、取消、持久 ACK、重启覆盖见 `packages/dsh-integration/tests/inbox-delivery.test.ts`；当前复验日志 `/tmp/nano-769-stop-green.log`。来源撤销、冻结消息映射与投影 ACK 回归见 personal-attention、inbox、global-work-recovery；六文件联合定向 48 项通过（`/tmp/nano-769-final-narrow.log`）。最后迁移两文件 32 项通过，后续完整回归还包括 aborted 终态保护。

迁移脚本不在生产运行。隔离 SQLite 功能／幂等验证通过，正式部署顺序与备份、跨库失败恢复要求见 [deployment-prompt.md](deployment-prompt.md)。本轮测试进程与临时数据库由 fixture 回收。

## 最终集成验证

源码冻结 `2f420460fa54666a9b18dc651a223e24922089e2`：全仓 build、typecheck、iOS shared runtime 通过；后端全量 244 文件／1391 测试全部通过（`/tmp/nano-final-backend.log`）。Python 136 通过、28 e2e 排除，Ruff check/format 通过；文档检查通过。前端沿用本批次构建、critical audit 与全量加失败项单独复验的有效证据，前端源码未改。executed_base 与 effective_base 均为 `9f900ff3ba355414cb442f9211c3a8e17e391428`，最后 fetch 无目标分支推进；之后仅报告与整 unit 归档，源码及独立审查结论 retained。
