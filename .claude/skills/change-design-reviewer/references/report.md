# Design review report

每轮包含：

- `## Round N`
- Metadata：reviewer target、review_mode、mode_reason、started_at/completed_at（ISO 8601 + 时区）、duration。
- Verdict：Approved 或 Issues Found，以及 CRITICAL/WARNING 数。
- Coverage 与证据：full 覆盖现状、决定、用户约束、delta、milestone，并说明架构判断；delta 只展开变化和波及范围，注明 `retained_from: Round N` 与理由；closure 只给历史问题关闭证据。
- 历史问题闭环：原 issue ID、Author Resolution、本轮证据、closed/still-open。
- Issues：`R<N>-C<n>` / `R<N>-W<n>`、具体位置、证据、未修后果。
- Recommendations：`R<N>-R<n>`，仅可选改进。

不以表格数量代替覆盖质量；相同证据可在多个要求间引用。旧 Round 只允许 author 末尾追加 `Author Resolutions`；纠错写新 Round。
