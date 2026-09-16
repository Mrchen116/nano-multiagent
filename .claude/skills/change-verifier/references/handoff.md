# Verifier 现场与报告

输入：unit_id、unit_dir、branch、verify_worktree_dir、validated_at、executed_base、verification_mode。普通模式另有 review_round；targeted-closure/delta 带 prior_verification_path、fix_delta_range，closure 再带 focus_issues。corrected-delta 不需要这些普通复验字段。

可使用 caller 已冻结的 unit worktree，与 code review 共用现场；需要隔离时才在给定路径创建/安全恢复 detached worktree。核对 HEAD=validated_at，不在共享现场切换版本，不默认为最新远端。来源不明的修改不可覆盖。unit 文档从 active/archive 唯一解析。

普通报告后续追加 Round，记录覆盖证据、mode、delta、focus、requires_full_verification、critical/warning/suggestion。corrected-delta 更新唯一 Corrected Delta Reconciliation 段，Git 保存旧结果；可与普通报告同次完成；没有 delta 时核对不存在遗漏的行为变化后记录 no spec delta，不单独派发空任务。

只写 verification.md；兼任 code review 时可另写该结论到 code-review.md。共享现场由 caller 提交报告；自建现场只提交这些报告，detached HEAD 推送使用 caller 给定的实际 branch（`HEAD:<branch>`）。并行报告推进时 fetch/rebase 自己的报告提交后普通 push；冲突或源码变化交 orchestrator 判断，不 force push。report_commit 要在远端可达；报告的 validated_at/executed_base 不因 rebase 改成新值。

普通返回 unit_id、review_round、verification_mode、verdict、issues、validated_issues、requires_full_verification、report_path/report_commit、top_concern。corrected-delta 返回 unit_id、verification_mode、outcome、report_path/report_commit。自建 worktree 自清理，续验可保留但要移交所有权。
