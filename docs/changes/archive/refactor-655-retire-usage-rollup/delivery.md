# refactor-655 delivery

2026-10-25。累计用量链退役、Work 持久处理位置与原生关系元数据恢复、同步状态提示均已完成。旧累计表不 DROP，Work/bubble/Workflow budget 各自统计保留；变化分支的上游 JSONL 全文解码成本仍存在。生产未部署，PR 不自动合并。

## Gate validity and final sync

| Gate | validated_at | executed_base | Result |
|---|---|---|---|
| Design Gate 2 | 已批准设计，冻结于 `063b0742f` | `1c9d5583f` + 被审设计树 | Approved，0 CRITICAL / 0 WARNING；见 design-review |
| Independent code review | `0d3a762fed52fe14a93fcb03ba4de72532a5887a` | `063b0742f` | findings `[]` |
| Independent product review | `0d3a762fed52fe14a93fcb03ba4de72532a5887a` | `063b0742f` | Round 2 pass，0 产品问题 |
| Independent verification / corrected-delta | `0d3a762fed52fe14a93fcb03ba4de72532a5887a` + Round 2 证据及链接校正 | `063b0742f` | PASS，0 CRITICAL / 0 WARNING，aligned |

- effective_base: `648e263d2373985a088cce55222901ef7c420cb5`。
- effective_through（实际集成树）: `38a945c37ae1455a38b536bf8989d60934eef344`。
- 后续提交仅把已核对 delta 归并到 canonical、补充交付记录和完整归档；产品代码/配置/测试与被审实现相同，所有门禁 retained 到本文件所在最终归档提交。PR 明确列出该最终 head，避免把实际执行快照误写为新 head。

静态审查者独立检查 main 的 feat-654 增量：仅日常验收模板、脚本、相关测试和文档/skill 路由，无应用代码或依赖/CI变更。默认专项 fixture 路径保留。此次已完成的冻结版本真实 Work 专项验收结果有效；之后建立新常规环境遵循 daily 默认模板。无冲突 merge 的实际应用树与 `0d3a762fe` 一致，不以无冲突本身替代判断。

三份 delta 已逐条映射代码与测试，未新增语义调整；auth-tenancy 两个链接修正只修复目标路径。归并范围为 `docs/specs/im/{agent-work,auth-tenancy}.md` 与 `docs/specs/gateway/service-lifecycle.md`。

## Validation and ownership

完整操作与证据见 `M1-retire-and-recover/acceptance.md`，独立结果见该目录 review/verification/code-review。后端703、前端1022、iOS24及Release archive通过；真实 token critical path、原生冷恢复0/1/0、旧库/原生日志副本升级与回滚通过。同步main后 Python工具/架构检查扩展到 **70 passed / 32 deselected**，ruff check/format全部通过（88 files）；应用与浏览器全量证据按上述失效判断保留。

所有自有隔离服务、Vite、原型服务已停止，精确 PID 与监听端口核对无残留。runtime、截图、日志、临时脚本和数据库只保留本机证据，不纳入提交。主仓无本任务未提交变更。保留 managed worktree `/Users/czj/.codex/worktrees/refactor-655-work-recovery/nano-multiagent` 与 `codex/refactor-655-work-recovery`，用于 PR 审阅及后续修订；PR 合并后可归档。此次完成不等于生产上线。
