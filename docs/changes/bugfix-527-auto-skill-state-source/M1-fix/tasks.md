# bugfix-527-M1: 修正后台自动 Skill 来源 — Tasks

> 对齐: ../fix.md（Bugfix lite）

## 目标

后台 self-improvement Skill Review 创建 Skill 时，从 Review 触发入口经 fork metadata 到 `skill_manage(create)` 使用记录完整保留自动创建来源 `F3`；仅做 memory Review 时不携带 Skill 来源。

## 退出标准

- [ ] Skill-only 与 combined Review 的 fork metadata 带 `skill_creation_source=F3`，创建记录落盘为 `F3`。
- [ ] memory-only Review 不虚构 Skill 来源；普通 fork 与普通用户创建继续走既有默认 `F1`。
- [ ] 其他 fork/历史蒸馏语义不变，Allowlist 代码、生产配置和既有 `.usage.json` 不修改。
- [ ] fix.md 的“修复 / 验证”完成回填，聚焦与扩展测试全绿。

## 测试策略

- 保护的回归风险与可观察 seam: 后台 `agent_end` Review 入口触发 fork 后，真实 `skill_manage(create)` 生成的 `.usage.json` 来源为 `F3`；memory-only / 普通路径不污染来源。
- 已有保护与处置: `tests/unit/test_self_improvement_hook.py`、`tests/unit/test_background_hook_fork.py`、`tests/unit/test_skill_manage_tool.py`、`tests/unit/test_usage.py` 均保留；它们分别保护触发、通用 fork、创建工具与 usage 原语，但没有同一条跨边界来源链。新增 `tests/integration/test_self_improvement_skill_source.py`，因为该风险跨 platform hook、core fork metadata 与 tool persistence 三个 owner。
- 落层/目录/marker: `tests/integration/`，marker: 无；这是能同时暴露生产者漏标与 fork 丢 metadata 的最低层，不重复测试 usage 原语。
- 文件归属: 新建 `tests/integration/test_self_improvement_skill_source.py`；语义按 self-improvement 自动 Skill 来源命名，不按 milestone 编号命名。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；持久化回归直接从后台 hook 入口走到临时 workspace `.usage.json`，即本缺陷的可重复入口证据。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Review 类型决定工具集合与 fork 调用 | `tests/unit/test_self_improvement_hook.py` | keep | 继续保护 skill/combined/memory-only 分支；新增跨边界测试不重复其完整阈值矩阵 | 聚焦 pytest |
| 通用 fork 继承父 metadata 与后台 origin | `tests/unit/test_background_hook_fork.py::test_fork_inherits_parent_execution_context` | keep | 普通 fork 行为仍存在，且需证明新增 override 不改变既有继承语义 | 聚焦 pytest |
| 普通 create 默认来源 | `tests/unit/test_skill_manage_tool.py`、`tests/unit/test_usage.py` | keep | `source_from_metadata` 与普通创建默认 F1 不变 | 聚焦 pytest |

前端 UI: N/A。

## Roadpoints

### R1 — 建立来源链红测并最小贯通 F3

- 状态: DONE
- 步骤: 从后台 Skill Review hook 入口执行实际 fork wrapper 与 `skill_manage(create)`，先确认 `.usage.json` 错为 F1；再只增加本次 fork 的 metadata override 并让记录变为 F3。
- 验证: 新增 integration regression 红转绿；skill-only 与 combined 两类 Review 均覆盖。

### R2 — 锁定不污染边界并扩大回归

- 状态: DOING
- 步骤: 证明 memory-only Review 不传 Skill 来源，普通 fork 不新增该字段，普通用户 create 仍为 F1；检查其他 fork/蒸馏相关现有测试不变。
- 验证: self-improvement、background fork、skill_manage、usage、skill_view 聚焦测试与 Ruff 全绿。

### R3 — 回填 lite 证据并完成集成

- 状态: TODO
- 步骤: 更新 progress.md 与 fix.md 的修复/验证；rebase unit 分支后重跑门禁，提交并合入 unit worktree。
- 验证: 聚焦测试、扩展 `tests/unit` / `tests/integration` 风险面、`git diff --check` 全绿。
