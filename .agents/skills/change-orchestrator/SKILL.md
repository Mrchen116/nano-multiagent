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
- 自主实施或派发 Context 相关任务时按 [通用规范](../../../docs/development/agent-context-engineering.md) 明确消费链和最终请求/适用行为证据；签收不能仅看内部 API、类型、UI 或文件存在。现有 code reviewer 按 [agent-context-review](../agent-context-review/SKILL.md) 的 Implementation Review 检查同一范围，不增加角色或 Gate。
- 签收以最终 unit tree 的退出标准证据为准。worker 的记录、commits 和真实入口证据必须可达；界面按 [共同体验标准](../change-design-author/references/prototype-and-runbook.md#共同判断标准) 核对整体体验与设计兑现，功能接通和口头 DONE 不足以签收。整体体验反馈由主 Agent 查明共同成因、集中修正并按影响复验。

## 独立门禁

真实产品验收环境由主 Agent 集中按 [固定日常模板](../../../docs/development/worktree-runtime.md#固定日常验收模板) 使用 `--profile daily` 准备，交接 `.e2e-daily.json`、版本和本次场景增量。每需求独立实例，专项 profile 作为有明确目的的补充，不每次重新发明角色阵容。

| Unit | Product reviewer | Verifier | Code review |
|---|---|---|---|
| Full，有用户可观察旅程 | full | full | full |
| Full，零用户面 | skipped | full | full |
| Bugfix lite | skipped | skipped | full |

对冻结的同一 unit HEAD 按 workflow 组织独立门禁：向同一静态审查者明确派发 code review/verifier 的各项职责、范围与输出，产品 reviewer 与两者独立；收到高风险、有争议或关键条件未确认的发现时，再派发独立候选核验。验收角色只写规定报告；产品 reviewer 的隔离测试配置例外遵循其 Skill。判真 findings，修复成立的阻塞问题；超出上述允许范围的写入使该轮失效。

[门禁输入与修复](references/validation.md) 定义固定字段、复验模式与升级条件；进入验收时读取。只重跑受实际 delta 影响的检查，证据不足或高风险时 full，不把 inherited 结论写成重新执行。

## 交付与恢复

按 change-workflow 完成 final sync 与门禁有效性判断、delta 校正及适用的 corrected-delta 核对（可并入静态审查，无 delta 不空跑）、canonical 归并、本地 CI、完整 archive、PR 和 required CI。组装 PR 时读 [PR 模板](references/pr-body-templates.md)。有真实 Promotion Candidates 才归并到唯一权威位置，不强制生产新知识。

PR 提交后保留 unit 开发 worktree；确认 PR 合入后，由执行合并或接手后续工作的 Agent 在本轮结束前按 [合入后清理规则](../../../docs/development/change-workflow.md#pr-合入后的-worktree-清理)完成清理并核实结果。验证结束停止自建测试服务，用户明确要求保留预览时例外；阻塞时保留恢复证据并停掉自己启动的进程。milestone 临时现场仍由 worker 在集成后清理。未经授权不 merge。

开放 PR 恢复和现场规则见 [recovery](references/recovery.md)；在 Codex 派发且需工具适配时读 [execution notes](references/codex-execution-notes.md)。输出 PR、最终 head、有效门禁摘要、worktree 保留/清理状态和残留事项；required CI 未绿不报完成。
