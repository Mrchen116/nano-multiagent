# bugfix-511: Unit PR 缺少归档 CI 门禁

## Relations

- Related: bugfix-497
- Related: feat-501
- Related: feat-503

## 原始报告

用户发现 `docs/changes/` 中存在已经实现、已经合入或已经具备归档条件的 active unit，
并要求分析对应 Codex session 为什么漏掉最终归档。确认问题后，用户指定修复：

> 还要加一层 CI。PR 分支为 unit/feat-501，CI 提取 feat-501；如果该 unit 还在
> docs/changes/feat-501-*，CI 直接失败；只有它位于 docs/changes/archive/feat-501-* 才通过。

用户同时确认不增加本地 preflight，并要求 `change-orchestrator-simple` 默认创建 Ready for
review 的 PR，而不是 Draft。

## 澄清记录

- 不增加本地 preflight；远端 CI 是本次唯一新增的交付门禁。
- 门禁只约束 `unit/*` PR，其他分支不需要 change unit。
- unit 必须在 archive 中唯一存在；active、retired、缺失或多处重复都不能交付。
- `unit/<unit-id>-<suffix>` 仍按前缀中的 `<unit-id>` 定位 change unit。
- 不重复修改 skill 的“完成条件”；只明确 PR 创建状态与 Draft 例外。
- 用户授权完成实现、补齐本 unit 文档并创建 PR。

## 现象与复现

1. 从 `unit/feat-501` 等 unit 分支创建 PR。
2. 对应目录仍位于 `docs/changes/feat-501-*`，没有移动到 archive。
3. 既有 CI 只运行文档完整性、Python 与前端检查，不检查分支对应 unit 的生命周期位置。
4. PR 因而可能显示全绿，并被误称为可以合入；PR 的 Draft/Ready 状态也没有被 simple
   orchestrator 明确约束。

期望：`unit/*` PR 只有在对应 unit 唯一位于 `docs/changes/archive/` 时 CI 才通过；simple
orchestrator 正常交付时创建 Ready for review PR。

## 影响范围

- 影响所有通过 `unit/*` 分支交付的 change unit。
- 不改变产品运行时代码或用户数据。
- 风险是生命周期历史与实现脱节、未归档 unit 被误判为可合入，以及 Draft PR 被误报为正式交付。

## 根因分析（RCA）

归档此前只由 orchestrator skill 的自然语言步骤约束，没有进入 GitHub CI 执行面。
Agent 即使遗漏归档，仍可直接调用 `gh pr create`，而既有 CI 无法从分支名反查 unit 状态。
`change-orchestrator-simple` 也只要求“创建 PR”，没有明确正常交付必须是 Ready for review，
因此 Draft/Ready 状态依赖执行者临场选择。session 取证表明长会话压缩后曾发生这种末端步骤遗漏；
根本缺口是交付约束没有硬门禁，而不是缺少另一段重复提醒。

## 修复方向

- 在现有 `Python checks` job 中增加无依赖脚本：解析 PR head branch，定位 active、archive、
  retired 三处的 unit 目录，只有唯一 archive 命中时返回成功。
- 用行为级契约测试覆盖跳过、通过和各失败状态，并锁定 CI wiring。
- 在 `change-orchestrator-simple` 的 PR 创建步骤中明确默认 Ready for review；只有用户明确要求
  提前查看未完成 diff 时才允许中间 Draft，正式交付前必须转 Ready。
- 同一 PR 一并归档已经完成的 bugfix-497、feat-501，并把 bugfix-497 的遗漏 delta 归并到
  canonical IM specs；feat-503 保持 active。

## 验收标准

- `unit/feat-501` 对应目录唯一位于 archive 时检查通过。
- 同一 unit 位于 active 或 retired、完全缺失、或多处重复时检查失败并指出原因。
- 非 `unit/*` 分支跳过检查。
- CI 从 `github.head_ref` 调用该检查，失败会使现有 `Python checks` 变红，从而阻止 PR
  全绿以及 orchestrator 将其称为可交付。
- simple orchestrator 的正常 PR 明确为 Ready for review，不能使用 `--draft`。
