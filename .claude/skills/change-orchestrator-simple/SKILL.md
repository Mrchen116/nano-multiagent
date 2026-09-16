---
name: change-orchestrator-simple
description: "实施已完成事前对齐的 Full 或 Bugfix lite change unit 并交付 PR 时默认使用；用户点名 $change-orchestrator 时改用原流程。"
---

# Change Unit Delivery

在一个专属 unit worktree 自主完成实施、适用独立门禁和 CI 全绿的 PR。准入、门禁选择、归并和归档遵循 [change-workflow](../../../docs/development/change-workflow.md)，不改变已确认的需求、关键设计与交付标准。

## 实施

- 唯一解析 active unit；Full 需要未失效的 Gate 2，lite 需要已确认的现象与根因。恢复时核实 branch/head/dirty；保留主仓工作，不 reset 不明现场。
- 从最新 origin/main 建立或恢复 `.worktrees/unit-<unit-id>` / `unit/<unit-id>`。lite 保持唯一 `M1-fix`，不因此强制创建 `tasks.md` 或 `progress.md`。
- 默认主 Agent 端到端实施与集成，仅将可独立交付且收益足够的具体任务派给 subagent，不按层机械拆 worker。微小修复、环境命令和格式收尾直接完成。派发/复用遵循 workflow 的上下文规则；每个 milestone 退出标准须可从代码、测试、commits 和证据复核。
- 按受影响区域读取相关实现、current specs、[测试规范](../../../docs/development/testing.md)；复用带版本、命令和结果的有效证据。先稳定 fixture 并完成窄测试，再跑本地全量与 CI，不因角色交接重复全量。
- 对可测试的新行为/bug 取得有意义的失败复现，再实现并跑最窄验证。真实用户入口、跨进程链路、前端交互及适用原型对照须有真实证据；mock 不替代它们。
- 服务按 [worktree-runtime](../../../docs/development/worktree-runtime.md) 隔离。lite 回填 fix 的修复/验证；关键设计变化交回 author，需求或范围变化重新与用户对齐。

## 门禁与交付

- Full 有用户旅程：独立 `$change-reviewer`、`$change-verifier` 和 `$change-code-review`。
- Full 零用户面：verifier 和 code review，不派产品 reviewer。
- Bugfix lite：只执行 `$change-code-review`，不派 verifier 或产品 reviewer。

默认同一独立静态审查者执行 code review 与 verification，分别给结论；产品 reviewer 独立于实现和静态审查。是否追加候选核验按 code-review 的风险/争议规则。批量修复成立的阻塞问题后冻结版本，一次复验失效范围；证据不足或边界不清时扩大，不以提交号变化机械触发全审。复验字段与 retained 证据见 [validation](../change-orchestrator/references/validation.md)。

完成 final sync、门禁有效性判断、delta 校正（可并入静态审查；未覆盖的校正补做 corrected-delta，无 delta 记录 no spec delta）、canonical 归并、本地 CI 和完整 archive，再创建 Ready for review PR，正常交付不得使用 `--draft`。用户明确要求提前查看时可先 Draft，交付前 `gh pr ready` 并等 required CI 全绿。

每个 worktree 由创建/接管者清理；完成核对本次实际路径与进程。用户要求保留时说明路径和清理触发，阻塞时保存可恢复证据。输出 PR、head、验证与剩余事项；不自动 merge。
