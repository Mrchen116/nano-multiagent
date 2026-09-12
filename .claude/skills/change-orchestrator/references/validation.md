# 门禁输入与修复

冻结 clean unit HEAD：`validated_at` 是实际验证的 unit tree；`executed_base` 是与当时 origin/main 的 merge-base。给角色 unit_id、unit_dir、branch、这两个 SHA 和普通轮次 review_round。

- reviewer：unit_worktree_dir、mode=full、revalidation_mode=full|targeted；targeted 附 prior_acceptance_paths、focus_scenarios_or_issues、fix_delta_range。
- verifier：verify_worktree_dir、verification_mode=full|targeted-closure|delta；复验附 prior_verification_path、fix_delta_range；closure 附 focus_issues。
- code review：review_mode=full|patch|closure、diff_range、focus_findings。range 分别为 executed_base...validated_at、pre_fix_head..validated_at、finding_origin_head..validated_at。
- corrected-delta：Full 校正并 push delta 后提供 unit、branch、verify_worktree_dir、validated_at/executed_base、verification_mode=corrected-delta；不要求普通复验字段。

等 selected gates 返回再整合报告，确认报告来自本轮 SHA 且没有范围外写入。发现越界使该角色本轮 verdict 失效，保留合法并行工作后移除越界 delta，修复并重验。

每次修复前记录 pre_fix_head；判定问题是否成立、属于本 unit、阻塞交付、根因在哪里，合并同因项。明确的小修可直接闭环；需要独立 owner、隔离或深入探索时派 worker。旧问题用 closure；新源码用 patch；可能偏离 spec/design 时 verifier delta；无影响的结论注明 prior report、SHA、delta 与保留理由。

权限、持久化、迁移、协议、跨进程、共享运行时、并发或部署变化可能使整条链失效；无法界定影响时对适用 gate 做 full。final sync、冲突解决、文档/CI fix 同样判断影响；记录 effective_base/effective_through，保留原 executed_base/validated_at。

revise-design 建议需非首轮、同一 issue 至少两轮实施修复无效且引用 design 的具体矛盾；真实需求/关键设计变化仍交回 author。out-of-unit blocking 暂停交 triage，major 记录关联，minor 只记 side finding。

同一 issue 经 5 个有效修复轮或 unit 经 7 个有效验收轮仍未收口，保留现场交人。轮次上限是停损保护，不要求做满轮数；不为可选润色反复审查。
