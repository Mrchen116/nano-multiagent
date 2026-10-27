# feat-654 交付记录

## Final sync 与门禁有效性

- 实施版本：`a75a88781758515ab2644386c997c1d6503d8f42`。
- 三项独立实施门禁的 `executed_base`：`d2cad8d59bb7025cacdd546d7fc9e0949fe13916`；`validated_at`：上述实施版本。产品 reviewer、verifier、code review 均 pass。
- `effective_base`：`1c9d5583fb1e15c2bdf00c15d1b6efa818891e4e`；最终集成树 `effective_through`：`befbb6ef1da06dd96918d95d56f6821d086cea47`。
- 主干增量只有 `docs/changes/refactor-655-retire-usage-rollup/motivation.md`，不涉及 fixture、启动脚本、产品代码或本 unit 的需求/设计。集成无冲突；三项门禁均 retained，依据是完整 diff 的影响范围与原报告覆盖，不以无冲突代替审查。
- 实施版本之后本分支仅新增独立报告、合并上述无关文档、整体归档本 unit 并新增本记录。没有改变被测行为、体验判据、配置或代码；Gate 2 与三项实施门禁继续有效。归档提交的精确 SHA 在 PR Validation Summary 中登记。

## M1 与验证

- 固定 P/E/Q + 真实 PA、日常群、三份项目资料和每轮独立 owner/workspace 均已完成；两个 orchestrator、设计 runbook、reviewer 交接默认采用 daily。
- 真实产品 7/7 Scenario 通过：普通群消息交 P，E 实际写文件，Q 独立读取核验，PA 引用真实群结果；新副本空历史、固定资料和场景增量隔离已独立观察。
- daily/catalog 单测 8 passed；daily/default 真实进程回归 5 passed（57.80s），含同根重新启动和 owner 全局 Skill 隔离。
- 完整本地 CI：后端 132 files / 703 tests，前端 107 files / 1017 tests，Python 非 E2E 70 passed / 32 deselected；build、typecheck、iOS runtime check、Ruff、format 和 docs-check 通过。
- `npm audit --audit-level=critical` exit 0；仍报告既有 4 low / 2 moderate / 5 high，不将门禁通过表述为无漏洞。
- no spec delta 已由独立 verifier 确认；长期操作规则归并于 `docs/development/worktree-runtime.md`，相关入口同步。

## 边界

生产只读核对，未改配置、发测试消息、重启或部署。设置页 Group Reply Policy 显示与公开配置不一致为非阻塞 unit 外观察，见 acceptance；本次未修改客户端。PR 交付后由人审查合并。
