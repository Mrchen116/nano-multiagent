---
name: change-orchestrator-simple
description: "用户点名 $change-orchestrator-simple，要求实施已完成事前对齐的 Full 或 Bugfix lite change unit 并交付 PR 时使用。"
---

# Change Unit Delivery

在一个专属 unit worktree 自主完成实施、适用独立门禁和 CI 全绿的 PR。准入、门禁选择、归并和归档遵循 [change-workflow](../../../docs/development/change-workflow.md)，不改变已确认的需求、关键设计与交付标准。

## 实施

- 唯一解析 active unit；Full 需要未失效的 Gate 2，lite 需要已确认的现象与根因。恢复时核实 branch/head/dirty；保留主仓工作，不 reset 不明现场。
- 从最新 origin/main 建立或恢复 `.worktrees/unit-<unit-id>` / `unit/<unit-id>`。lite 保持唯一 `M1-fix`，不因此强制创建 `tasks.md` 或 `progress.md`。
- 自主选择实现组织、subagent、提交与记录形式。每个 milestone 退出标准须可从代码、测试、commits 和证据复核；只处理本 unit。
- 按受影响区域读取相关实现、current specs、[测试规范](../../../docs/development/testing.md)；未变的上下文和有效验证可复用。
- 对可测试的新行为/bug 取得有意义的失败复现，再实现并跑最窄验证。真实用户入口、跨进程链路、前端交互及适用原型对照须有真实证据；mock 不替代它们。
- 服务按 [worktree-runtime](../../../docs/development/worktree-runtime.md) 隔离。lite 回填 fix 的修复/验证；关键设计变化交回 author，需求或范围变化重新与用户对齐。

## 门禁与交付

- Full 有用户旅程：独立 `$change-reviewer`、`$change-verifier` 和 `$change-code-review`。
- Full 零用户面：verifier 和 code review，不派产品 reviewer。
- Bugfix lite：只执行 `$change-code-review`，不派 verifier 或产品 reviewer。

reviewer/verifier 独立于实现且彼此独立；code review 在主上下文组织独立 finder/verifier。只修成立且阻塞的问题，后续 delta 仅重验失效范围；高风险或边界不清时 full。复验字段与 retained 证据见 [validation](../change-orchestrator/references/validation.md)。

完成 final sync、门禁有效性判断、delta 校正（Full 使用 corrected-delta verifier）、canonical 归并、本地 CI 和完整 archive，再创建 Ready for review PR，正常交付不得使用 `--draft`。用户明确要求提前查看时可先 Draft，交付前 `gh pr ready` 并等 required CI 全绿。

每个 worktree 由创建/接管者清理；完成核对本次实际路径与进程。用户要求保留时说明路径和清理触发，阻塞时保存可恢复证据。输出 PR、head、验证与剩余事项；不自动 merge。
