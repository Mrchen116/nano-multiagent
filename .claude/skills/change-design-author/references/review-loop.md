# 独立设计审查闭环

已有 `design-review.md` 时恢复最后 Round 的 reviewer target，从 N+1 继续。没有历史才创建 R1，使用独立上下文（Codex `fork_turns: "none"`）与中性输入，保存稳定 target。客观无法恢复时允许 failover，记录旧/新 target 和原因，替代者做 full。

R1 full；R2+ 的 `closure | delta | full` 由 reviewer 按实际修订选择，author 不指定期望结论或限制其发现范围。派发包含 unit、轮次、修改文件/段落、历史 issue 与 resolution。

author 对 findings 和 recommendations 判真，在该 Round 末尾追加 `Author Resolutions`：稳定 issue ID、`accepted | rejected | escalated`、证据及修改位置。保留 reviewer 原文；无需为了可选润色继续循环。真实问题修正所有受影响产物；需求变化交回 spec-author，推翻已确认关键架构决定先找用户。

复审只核变化及其影响，无法保留旧证据时扩大范围。停止需最后 Round Approved、0 CRITICAL / 0 WARNING、author 无实质异议且受审产物此后未改。缺少独立 reviewer 能力时报告门禁阻塞，不自己签字。
