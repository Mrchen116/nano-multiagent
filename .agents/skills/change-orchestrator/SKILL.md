---
name: change-orchestrator
description: "用户点名 $change-orchestrator，要求按原流程实施已通过 Gate 2 的 Full unit 或首文档已收口的 Bugfix lite 并交付 PR 时使用；默认实施入口为 change-orchestrator-simple。"
---

# Change Orchestrator

把确认的 unit 实施为 required CI 全绿、可审查的 PR。生命周期、准入与收尾权威见 [change-workflow](../../../docs/development/change-workflow.md)。

## 实施边界

- 在专属 unit worktree 操作，保留主仓 branch、dirty/untracked；唯一解析 active/archive/retired 中的 unit。依赖未完成、准入缺失、来源不明现场或 retired unit 不启动。
- Full 要求 Gate 2 通过且无未经审查的实质变化；lite 保持唯一 `M1-fix`，超出小范围或需要独立设计时升级 Full。
- 涉及一次性部署迁移时，按 [部署提示词约定](../../../docs/changes/README.md#一次性部署提示词) 核对 `deployment-prompt.md` 与最终实现；lite 由主 Agent 编写并从 fix 链接，Full 设计变化交回 author。隔离迁移验证在交付前完成，不把功能回归留给生产部署；提示词随最终 diff 交现有 code review，无迁移不生成。
- 首轮仅在独立交付收益明确时将 milestone 派发 `change-impl-worker`；给 assignment、退出标准、unit 与 milestone 路径和精确 worktree/branch 计划。worker 自建并拥有现场，不设置 harness 自动 worktree isolation，不接管已派出的实施。
- 仅在无依赖和写冲突时并行。后续审查、验收、CI 或用户反馈发现的问题由主 Agent 修复，不新派或唤醒修复 worker；修复后仍需适用的独立复验。
- 派发与复用遵循 workflow 的职责边界与下述派发适配；Codex 派发前读取 [适配表](references/codex-execution-notes.md)；等待完成或 attention 通知，不轮询催进度。收到 blocker 后处理授权范围内问题，已确认需求或关键设计变化交回 author。
- 实施中发现新增影响时补充本次问题与能力选择；专项可与代码审查合并或按工作量分开，不能因最初未选而遗漏。
- 签收以最终 unit tree 的退出标准和所选能力证据为准，commits 与运行产物必须可达；口头 DONE 不足以签收。整体体验或判据反馈按受影响流程查明共同成因，集中修正后复验。

## 独立审查

按 [workflow 审查阶段](../../../docs/development/change-workflow.md#阶段-4selected-validation-gates) 保持本生命周期底线，使用 [能力组合](../../../docs/development/skill-composition.md) 根据本次问题派发。代码正确性、实现覆盖与 delta 校对一次完成；专项按影响组合，不固定每项一个 Agent。

真实团队旅程需要起栈时，由主 Agent 集中按 [固定日常模板](../../../docs/development/worktree-runtime.md#固定日常验收模板) 准备，交接 `.e2e-daily.json`、版本、授权与场景增量；局部问题不自动扩大为团队全栈。共享有效构建和证据，必要观察仍由独立执行者判断。

读取 [审查输入与收口](references/validation.md) 后对冻结版本派发；执行者只返回结论或写 caller 指定的独占结果位置，由 owner 串行归集 `review.md`。判真实际问题，主 Agent 批量修复后一次复验失效判断。检查尚在执行记 pending，不能为等待另一份报告再制造 findings 或复审。

## 交付与恢复

沿 [分支规则](../../../docs/development/change-workflow.md#开发基线与-pr-目标)确定的基线/交付分支按 change-workflow 完成 final sync 与门禁有效性判断、delta 校正及适用的 corrected-delta 核对（可并入静态审查，无 delta 不空跑）、canonical 归并、本地 CI、完整 archive、PR 和 required CI。组装 PR 时读 [PR 模板](references/pr-body-templates.md)。有真实 Promotion Candidates 才归并到唯一权威位置，不强制生产新知识。

用户明确要求仅推送试验分支或暂不 PR 时只完成授权交付，尚待试验的 unit 保持 active，不自动推 main 或创建 PR。

PR 提交后保留 unit 开发 worktree；确认 PR 合入后，由执行合并或接手后续工作的 Agent 在本轮结束前按 [合入后清理规则](../../../docs/development/change-workflow.md#pr-合入后的-worktree-清理)完成清理并核实结果。验证结束按 [测试资源回收](../../../docs/development/worktree-runtime.md#测试资源回收) 回收本轮资源并核实；例外保留须交代 owner 和回收触发；阻塞时保留恢复证据并停掉自己启动的进程。milestone 临时现场仍由 worker 在集成后清理。未经授权不 merge。

开放 PR 恢复和现场规则见 [recovery](references/recovery.md)；在 Codex 派发且需工具适配时读 [execution notes](references/codex-execution-notes.md)。输出 PR、最终 head、有效门禁摘要、worktree 保留/清理状态和残留事项；required CI 未绿不报完成。
