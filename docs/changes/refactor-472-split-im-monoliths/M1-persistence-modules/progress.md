# refactor-472-M1 — Progress

## 基线

- 已阅读 motivation、design、项目约定、IM 长青契约与测试规范。
- `PYTHONPATH=src pytest -m "not e2e"` 基线通过：3676 passed, 21 deselected。

## R1 — 锁定最终 package 边界与导入契约

- Context: 本次重构必须 replace-don't-layer，最终结构不允许旧 module 或聚合 re-export 继续成为事实入口。
- Decision: 先以 architecture contract 固定 package、私有 primitive 和禁止旧入口的可观察结构，再迁移 concrete importer。
- Rationale: contract 的失败可证明当前缺失的是最终边界，不把后续实现细节锁进测试。
- Evidence:
  - Tests: `PYTHONPATH=src pytest tests/contract/test_im_persistence_seam_contract.py -q` 失败 4 项，原因仅为 final package 尚未创建、legacy file 尚在。
  - Entry: N/A；本 roadpoint 为内部 architecture contract，HTTP 入口回归在 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/contract/test_im_persistence_seam_contract.py`，待执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C1 commit。
- Commits: C1=6ef66468f，C2=待提交，C3=待提交。
- Next: 写入 red contract 并确认只因最终 package 尚未实现而失败。

## [暂停] R1: 机械分段迁移遗漏 aggregate 私有依赖

- 现象: 首次聚焦仓库测试的 collection 暴露 `messages`/`agents`/测试 import 三类分段边界错误；修复后仍先后暴露 Message retry key、Conversation active delivery status 等原文件顶部/尾部 helper 的实际归属。
- 根因: 以原文件静态行区间复制 class 区段，将跨 class 定义位置的类型与 helper 错归/漏归；这不改变 design 的 aggregate/transaction ownership 决策，但证明该迁移方式不可靠。
- 已验证: `PYTHONPATH=src pytest <7 个 repository 聚焦测试> -q` 当前 10 failed, 43 passed；失败统一源于 `ConversationRepository._resolve_run_state()` 缺少原 module-level `_ACTIVE_AGENT_DELIVERY_STATUSES`。
- 决策请求: 已通知 orchestrator，等待确认改用 class range + 实际引用依赖图逐 aggregate 移动的迁移方式；暂停继续编码，避免在红色实现上叠加补丁。
- Next: 等待 orchestrator 继续信号；获准后从 R1 C1 基线重新执行可审计的 aggregate migration。
