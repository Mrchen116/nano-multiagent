<!--
模板说明（定稿后删除本块）

本 milestone 的可执行步骤 + 验收方式。
禁止：再次讨论设计决策（→ design.md，已锁定）。
roadpoint = milestone 内最小可提交单位（一次 commit 或一次 worktree push）。
-->

# <milestone_id>: <短描述> — Tasks

> 对齐: ../design.md v<n>

## 目标

<!-- 完成后外部观察者能看到什么变化。 -->

## 退出标准

- [ ]

## 测试策略

<!-- 规范见 docs/development/testing.md。以下逐项必填（逼出"该不该写/写在哪/归谁"的决策）。 -->

- 被测行为（来自退出标准）：<逐条列>
- 已有测试在：`<file>`（扩展） / 无，新建 `<file>`，理由：___
- 落层/目录/marker：tests/<unit|integration|contract|e2e>/ ，marker：<e2e|无>
- 可选依赖 importorskip：<有，哪些> / 无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：<列出> / 无

### 受影响的既有测试处置

<!--
只列本 milestone 影响的既有测试，不建全仓台账。处置只填 keep / rewrite-merge / delete。
没有受影响覆盖时不造占位行，在表后写“无”及搜索范围和理由。
-->

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| <当前应防的回归> | `<path::test>` | keep / rewrite-merge / delete | <为何这样处置；若风险仍在，最低层保护在哪里> | <命令或证据> |

无受影响既有测试时：<无；搜索范围：___；理由：___>

<!--
前端 UI milestone 额外填写；非前端可写 N/A。

用户路径分类：
- critical-path：核心业务路径，必须有可重复 regression 保护；若项目已有浏览器 E2E 体系，优先落库 E2E
- normal-ui：普通 UI 改动，必须真实浏览器临时验收，不一定落库 E2E
- visual-only：视觉/样式细节，必须真实浏览器截图验证，不强行写 E2E
- bug-regression：历史 bug 修复，必须补 regression case

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default |  |
| loading |  |
| empty |  |
| error |  |
| disabled |  |
| submitting |  |
| permission denied |  |
| long content |  |
| missing/nullable data |  |
| mobile viewport |  |
| desktop viewport |  |
| dark mode（如项目支持） |  |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
|  |  |  |

Prototype / Reference Contract（仅 design.md 含前端原型 / reference 时填写；非前端写 N/A）：
| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| <prototype.html 区域或 reference 名> | <must-match / may-adapt / out-of-scope 结论> | <截图/录屏/对照表计划，证据需落 unit 目录> | worker/reviewer |
-->

## Roadpoints

### R1 — <短描述>

- 步骤:
- 验证:

### R2 — <短描述>
