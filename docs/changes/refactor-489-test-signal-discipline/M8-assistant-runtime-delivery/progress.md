# refactor-489-M8 — Progress

## Baseline / Audit

- Claim: M8 派发范围基线可稳定收集运行，并已定位完全重复、源码形态、退役实现和跨层重复候选。
- Baseline: `origin/unit/refactor-489@6d4ebd793`。
- Method: 枚举 4 个 root 文件与排除 M6/M7/M13 后的 85 个 `tests/unit/personal_assistant/` 文件；运行完整 pytest；用 AST 比较测试函数体并搜索 source/private/historical 断言。
- Result: PASS；`634 passed`（23.18s）；发现 26 组完全重复函数，另有 source scan、退役 setter/singleton 缺席、CC 逐字提示词及合成 thinking 断言。
- Limit: 本 unit 零产品行为变更，不以 unit 测试替代 M13 的真实进程/E2E 证据；M8 只维护派发的 unit 测试资产。

## R1 — 收敛完全重复测试

- 状态: DONE
- Context: 基线 AST 发现 26 组函数体完全相同的测试，分散在聚合文件与按 seam 拆分后的 owner 文件中；继续双跑不会增加独立风险覆盖。
- Decision: 把外部会话 key 合入 `test_gateway_pipeline_channel.py`；保留专属 auth/relay/upstream/dedup/metadata/agent-session owner；删除聚合文件或其中的重复函数。authenticated IM owner 的 shadow sync 是唯一风险，继续保留。
- Rationale: 完全相同的 Arrange/Act/Assert 不可能提供第二种失效信号；按 channel、auth、relay、metadata、agent-session seam 保留一份可让失败直接定位 owner。
- Evidence:
  - Tests: 相关 10 个 owner 文件 `70 passed`；AST 再扫描 M8 全域不再发现任何完全重复函数体；`git diff --check` 通过。
  - Entry: N/A（零产品行为重构）；外部 identity、IM auth header、relay dedup/restart、session metadata/lifecycle 仍从各自公开调用结果观察。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 现有 unit regression 原位保留；真实进程/E2E 归 M13，本 milestone 不复制。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复计划提交 `15fef707a` 的测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 删除退役实现缺席断言与源码形态扫描，把仍存在的风险改写到公开结果。

## R2 — 移除退役实现与源码形态断言

- 状态: TODO

## R3 — 把高层重复收敛到最低行为 seam

- 状态: TODO

## R4 — 全量门禁与证据对账

- 状态: TODO

## Promotion Candidates

None.
