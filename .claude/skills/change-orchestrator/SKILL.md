---
name: change-orchestrator
description: "已通过 Gate 2 的 Full unit 或首文档已收口的 Bugfix lite 需要实施并交付 PR 时默认使用；simple 流程仅由用户点名选择。"
---

# Change Orchestrator

把确认的 unit 实施为 required CI 全绿、可审查的 PR。生命周期、准入与收尾权威见 [change-workflow](../../../docs/development/change-workflow.md)。

## 实施边界

- 在专属 unit worktree 操作，保留主仓 branch、dirty/untracked；唯一解析 active/archive/retired 中的 unit。依赖未完成、准入缺失、来源不明现场或 retired unit 不启动。
- Full 要求 Gate 2 通过且受审产物未变；lite 保持唯一 `M1-fix`，超出小范围或需要独立设计时升级 Full。
- 已设计的 milestone 派发 `change-impl-worker`；给 assignment、退出标准、unit 与 milestone 路径和精确 worktree/branch 计划。worker 自建并拥有现场，不设置 harness 自动 worktree isolation，不接管已派出的实施。
- 仅在无依赖和写冲突时并行。自包含小闭环按独立 owner 的实际收益选择直接完成或派 worker；直接修复仍需适用的独立验收。
- 复用原 worker/reviewer 上下文；等待完成或 attention 通知，不轮询催进度。收到 blocker 后处理授权范围内问题，已确认需求或关键设计变化交回 author。
- 签收以最终 unit tree 的退出标准证据为准。worker 的两份短记录、commits 和适用真实入口/prototype 对照证据必须可达；假入口、未完成验证和口头 DONE 不足以签收。

## 独立门禁

| Unit | Product reviewer | Verifier | Code review |
|---|---|---|---|
| Full，有用户可观察旅程 | full | full | full |
| Full，零用户面 | skipped | full | full |
| Bugfix lite | skipped | skipped | full |

对冻结的同一 unit HEAD 派独立 reviewer/verifier；主会话调用 code-review 组织独立发现与验证。验收角色只写规定报告。判真 findings，修复成立的阻塞问题；报告之外的写入使该轮失效。

[门禁输入与修复](references/validation.md) 定义固定字段、复验模式与升级条件；进入验收时读取。只重跑受实际 delta 影响的检查，证据不足或高风险时 full，不把 inherited 结论写成重新执行。

## 交付与恢复

按 change-workflow 完成 final sync 与门禁有效性判断、delta 校正及 Full corrected-delta 核对、canonical 归并、本地 CI、完整 archive、PR 和 required CI。组装 PR 时读 [PR 模板](references/pr-body-templates.md)。有真实 Promotion Candidates 才归并到唯一权威位置，不强制生产新知识。

正常完成清理本 unit 进程与创建/接管的 worktree，按实际路径核对；不通配清理他人现场。用户要求保留时报告路径、原因和清理触发；阻塞时保留恢复证据并停掉自己启动的进程。未经授权不 merge。

开放 PR 恢复和现场规则见 [recovery](references/recovery.md)；在 Codex 派发且需工具适配时读 [execution notes](references/codex-execution-notes.md)。输出 PR、最终 head、有效门禁摘要和残留事项；required CI 未绿不报完成。
