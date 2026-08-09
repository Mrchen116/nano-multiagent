# feat-519-M1 Tasks

## Goal

Deliver workspace Claude/Codex Skill compatibility and truthful grouped Skill selection as one end-to-end slice across the SDK/kernel, PA/CLI product composition, Gateway/IM configuration, and Web IM.

## Baseline

- Executed base: `1d0c2cb45`
- Python focused baseline: 27 passed.
- Frontend focused baseline: 37 passed; existing React `act(...)` warnings only.

## Implementation checklist

- [x] Add an ordered workspace Skill layout to `agent.sdk` and share one root sequence across list, preview, runtime, `skill_view`, and `skill_manage` reads while retaining the native writer root.
- [x] Configure PA and Coding CLI with their required workspace/global root priority and add shared-only capability discovery.
- [x] Add PA capability `source_group` and preserve old capability payload fallback.
- [x] Persist `skills_selection_mode` across IM profiles, Gateway YAML/config operations/live snapshots, session projection, Feishu reconciliation, and `skill_created` mutations.
- [x] Make SlashPicker and runtime distinguish default discovery from explicit allowlists, including explicit empty.
- [x] Implement default-to-explicit grouped tri-state selection in create/detail pages with keyboard/focus/mobile behavior and invisible-name preservation.
- [x] Add focused Python, contract, repository/API, Gateway, and frontend tests.
- [ ] Run focused validation, real CLI/PA/browser journeys, full verifier/reviewer/code-review gates, CI-equivalent checks, canonical spec merge, and archive.

Worker-side automated validation is complete; real product journeys, independent gates,
canonical spec merge, and archive remain owned by the orchestrator.

## Test strategy

- 保护的回归风险与可观察 seam: Skill root 顺序和同名覆盖、默认与显式空选择、跨版本 config operation、自动写回、API/runtime/SlashPicker 一致性；失败时分别表现为候选与运行时不一致、选择被扩宽、409、旧配置被迁移或 UI 展示陈旧候选。
- 已有保护与处置: resolver、PA/CLI product、IM/Gateway operation/contract、frontend integration 测试（rewrite-merge）；在既有责任文件中扩展同一 seam，未为同一失败原因另建重复套件。
- 落层/目录/marker: `tests/unit/`、`tests/integration/`、`tests/contract/` 与 `src/IM/frontend/src/**/*.test.ts(x)`，marker: 无；纯解析在 unit，跨边界状态与恢复在 integration/contract，用户交互在 frontend，是分别能暴露对应失败原因的最低层。
- 文件归属: 扩展既有 resolver、产品布局、IM/Gateway operation、API contract、chat/settings 测试；仅在既有文件无法表达新的独立边界时新增测试文件，避免继续堆叠超长文件。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): reviewer 隔离 workspace、Gateway YAML、IM DB、浏览器截图与运行日志；不提交仓库。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 有序 roots、同名 first-root-wins、writer root 不变 | resolver 与 PA/CLI product 测试 | rewrite-merge | 同一 discovery/read/write seam 扩展兼容 roots，保留原生路径断言 | focused Python suites |
| legacy/default/explicit-empty 经 API、operation 与 runtime 保持同一语义 | IM/Gateway operation、contract 与 session 测试 | rewrite-merge | 在既有持久化与跨进程边界加入 mode、恢复及滚动升级矩阵 | focused operation/contract suites |
| 分组三态、首次编辑、隐藏 names、保存后 SlashPicker | Agent detail/create 与 chat integration 测试 | rewrite-merge | 共用现有页面和 QueryClient seam，保护保存与回到聊天的真实状态转换 | focused frontend suites |
| 真实 CLI/PA/浏览器旅程 | 无（搜索 `tests/e2e/` 与既有 acceptance report） | keep as one-off evidence | 环境与视觉/运行时事实由独立 reviewer 验收，不把机器态脚本固化进套件 | `acceptance-report.md` |

## Exit criteria

- The single M1 reviewer and worker exit criteria in `design.md` are met.
- `change-verifier`, `change-reviewer`, and `change-code-review` all pass with no unresolved blocking findings.
- Canonical specs are merged, the unit is archived, local CI-equivalent commands and required GitHub checks pass, and the PR is Ready for Review.
