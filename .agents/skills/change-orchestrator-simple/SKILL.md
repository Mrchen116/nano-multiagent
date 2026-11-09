---
name: change-orchestrator-simple
description: "实施已完成事前对齐的 Full 或 Bugfix lite change unit 并交付 PR 时默认使用；用户点名 $change-orchestrator 时改用原流程。"
---

# Change Unit Delivery

在一个专属 unit worktree 自主完成实施、适用独立门禁和 CI 全绿的 PR。准入、门禁选择、归并和归档遵循 [change-workflow](../../../docs/development/change-workflow.md)，不改变已确认的需求、关键设计与交付标准。

## 实施

- 唯一解析 active unit；Full 需要未失效的 Gate 2，lite 需要已确认的现象与根因。恢复时核实 branch/head/dirty；保留主仓工作，不 reset 不明现场。
- 按 [分支规则](../../../docs/development/change-workflow.md#开发基线与-pr-目标)确定基线和 PR 目标，建立或恢复专属 worktree，分支使用 `codex/<unit-id>`。lite 保持唯一 `M1-fix`，不因此强制创建 `tasks.md` 或 `progress.md`。
- 默认主 Agent 端到端实施与集成，首轮仅将可独立交付且收益足够的具体任务派给 subagent，不按层机械拆 worker。微小修复、环境命令和格式收尾直接完成。派发/复用遵循 workflow 的职责边界与下述派发适配；Codex 派发前读取 [适配表](../change-orchestrator/references/codex-execution-notes.md)；每个 milestone 退出标准须可从代码、测试、commits 和证据复核。
- 按受影响区域读取相关实现、current specs、[测试规范](../../../docs/development/testing.md)；复用带版本、命令和结果的有效证据。先稳定 fixture 并完成窄测试，再跑本地全量与 CI，不因角色交接重复全量。
- 对可测试的新行为/bug 取得有意义的失败复现，再实现并跑最窄验证。真实用户入口、跨进程链路、前端交互及适用原型对照须有真实证据；mock 不替代它们。
- 按本次执行安排使用选中能力自检并交接有效证据，记录实际范围与未验证项；界面、Context 等专项方法由对应能力维护，不能用文件存在或测试通过替代其必要观察。
- 实施中发现新增影响时补充本次问题与能力选择；专项可与代码审查合并或按工作量分开，不能因最初未选而遗漏。
- 服务按 [worktree-runtime](../../../docs/development/worktree-runtime.md) 隔离。lite 回填 fix 的修复/验证；关键设计变化交回 author，需求或范围变化重新与用户对齐。
- 涉及一次性部署迁移时，按 [部署提示词约定](../../../docs/changes/README.md#一次性部署提示词) 核对 `deployment-prompt.md` 与最终实现；lite 由主 Agent 编写并从 fix 链接，Full 设计变化交回 author。隔离迁移验证在交付前完成，不把功能回归留给生产部署；提示词随最终 diff 交现有 code review，无迁移不生成。
- 选择的真实团队旅程需要起栈时，集中用 [固定日常模板](../../../docs/development/worktree-runtime.md#固定日常验收模板) 的 `--profile daily` 起栈，交接 `.e2e-daily.json`、版本和本次场景增量。复用固定 P/E/Q + PA 基线，每个需求独立实例；专项 profile 仅作为有明确目的的补充。

## 审查与交付

按 [workflow 的审查阶段](../../../docs/development/change-workflow.md#阶段-4selected-validation-gates) 执行当前生命周期底线，按 [能力组合](../../../docs/development/skill-composition.md) 将本次问题组合给未参与受审实现的审查者；不复制固定角色套餐。代码正确性、需求/设计覆盖和最终 delta 校对由同一次独立代码审查承接，专项按问题选择。

派发前读取 [输入与收口](../change-orchestrator/references/validation.md)，只给必要目标、版本、问题、能力和证据。执行者返回结果，由主 Agent 串行归集 `review.md`；不为等待另一项结果再启动复审。后续问题由主 Agent 修复，冻结后一次补验失效判断，不新派修复 worker。

默认完成目标分支 sync、证据有效性判断、delta 校正与 canonical 归并、本地 CI、完整 archive，再创建 Ready for review PR 并等待 required CI 全绿。未覆盖的契约校正由代码审查者补 corrected-delta，无 delta 不空跑。用户明确要求仅推送试验分支、暂不 PR 或提前 Draft 时遵循其交付范围；尚待用户试验的 unit 保持 active，不能宣称试验通过。

PR 提交后保留开发 worktree；确认 PR 合入后，由执行合并或接手后续工作的 Agent 在本轮结束前按 [合入后清理规则](../../../docs/development/change-workflow.md#pr-合入后的-worktree-清理)完成清理并核实结果。验证结束按 [测试资源回收](../../../docs/development/worktree-runtime.md#测试资源回收) 回收本轮资源并核实；例外保留须交代 owner 和回收触发。输出 PR、head、验证、worktree 保留/清理状态与剩余事项；不自动 merge。
