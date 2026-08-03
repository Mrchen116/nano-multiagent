# refactor-489-M1: test-discipline — Tasks

> 对齐: ../design.md 的 refactor-489-M1 行与决策 1

## 目标

把“只审本 milestone 受影响的既有测试，并明确 keep / rewrite-merge / delete”写成简洁、可执行且不重复的长期规范；让 worker 实际复制的任务模板包含处置表。

## 退出标准

- [x] `docs/development/testing.md` 成为处置判据的唯一完整 owner。
- [ ] `change-impl-worker` 在规划和交付时要求审视受影响的既有测试，不要求全仓台账。
- [ ] `assets/tasks.md` 含风险/行为、既有测试、处置、理由与保留或替代保护、验证五列。
- [ ] 文档路由、skill 格式和现有 workflow contract 校验通过。

## 测试策略

- 被测行为（来自退出标准）：testing owner 能独立给出处置判断；worker 能从触发条件进入处置动作；实际任务模板能承载处置证据；既有 change workflow 路由不漂移。
- 已有测试在：`tests/contract/test_change_workflow_documentation_contract.py`（保留，用作 lifecycle 路由基线）；没有直接覆盖处置表内容的既有测试，已搜索 `tests/contract/`、`tests/unit/` 与 skill scripts，不为文档措辞新增永久测试。
- 落层/目录/marker：既有 contract test，marker：无；本 milestone 不新增测试文件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无；验证命令与结果摘要写入 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| 修改 worker 指引时，change workflow 的既有生命周期与门禁路由仍成立 | `tests/contract/test_change_workflow_documentation_contract.py` | keep | 该 contract test 仍直接验证 current workflow 文档与 change skills 的一致性；本 milestone 不改变它保护的风险，也没有更低层重复保护 | `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_change_workflow_documentation_contract.py` |

直接覆盖处置表内容的受影响既有测试为“无”：搜索未发现这类保护，而精确锁定文档句子或表头会把实现措辞变成契约，因此不新增文本快照测试，改用本次结构校验作为交付证据。

## Roadpoints

### R1 — 固化唯一处置规范

- 状态: DONE
- 步骤: 在 `docs/development/testing.md` 定义触发范围、三类处置、删除前提与精确文本例外，并保持既有章节不重复。
- 验证: 用结构搜索确认当前缺口，再检查规范能够独立回答“何时审、审哪些、如何处置、何时可删”。

### R2 — 接入 worker 与实际模板

- 状态: DOING
- 步骤: 让 `change-impl-worker` 引用唯一 owner 并把处置动作接入规划/执行/交付；在 `assets/tasks.md` 加入实际处置表。
- 验证: `quick_validate.py` 通过，模板五列与三种处置值可从复制后的文件直接填写。

### R3 — 校验格式、路由与去重

- 状态: TODO
- 步骤: 对三处规范做交叉审读，删除重复解释并记录最终证据。
- 验证: `scripts/docs_check.py`、workflow documentation contract、`git diff --check` 和范围检查通过。
