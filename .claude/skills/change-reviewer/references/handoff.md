# 产品验收交接

输入：unit_id、unit_dir、branch、unit_worktree_dir、validated_at、executed_base、review_round、mode=full。targeted 另带 prior_acceptance_paths、focus_scenarios_or_issues、fix_delta_range。在 active/archive 唯一定位文档；lite 或零用户面错派时返回 skipped，不创建旅程。

核实 HEAD=validated_at，不先 pull 到更新的远端。运行按 design runbook 与 [worktree-runtime](../../../../docs/development/worktree-runtime.md)；必要前置缺失报告给 orchestrator，不临场降级。

Issues 含 Severity（blocking/major/minor）、Regression Relation（direct/suspected-regression/unrelated-existing/unclear）、Recommended Action、Action Rationale、期望/实际/复现证据。

- 违反验收、阻塞关键路径或疑似本次同屏/相邻回归：默认 fix-implementation，因果交由 owner 查。
- 明显无关、不影响可接受性且不像副作用：blocking/major 为 out-of-unit，记录关联 issue；minor 只记 Side Findings。对外创建 issue 需有当前任务授权，不因读到报告自动外发。
- revise-design 需非首轮、同 issue 至少两轮 fix 未解决、引用 design 的具体矛盾。Highest Required Action 优先级：revise-design > fix-implementation > out-of-unit > pass。

报告注明 validated_at/executed_base、真实覆盖、Reference Artifacts Reviewed、上层文档待同步项。只 stage 本报告并 commit。并行报告使 push 被拒时 fetch/rebase 报告提交再普通 push；冲突或非报告变化交 owner 判定，不 force push。报告 commit 可从远端 unit branch 达到后才回报成功，validated_at 保留原值。

返回 unit_id、review_round、verdict、highest_required_action、issues_count、gh_issues_filed、report_path、report_commit、top_concern、needs_re_review。
