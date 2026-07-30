---
name: change-fast-close
description: 用户明确选择快速开发模式，已经边对齐边完成实现，需要在交付前补齐 change unit 文档并执行 code review 时使用。
---

# Change Fast Close：快速开发收尾

快速开发把需求对齐、编码和用户体验验证放在同一段交互中。本 skill 接手已经存在的实现，将对话、代码和真实验证整理成可追溯的 change unit，并通过强制 code review 后收尾。

## 进入条件

同时满足以下条件才执行：

- 用户明确选择了“快速开发模式”，或明确要求为已经完成的改动事后补齐 unit 文档；
- 当前 checkout 中已经有属于本次需求的实现 diff 或 commits；
- 用户已经亲自测试并确认用户可观察结果符合预期。

任一条件不满足时不要伪造完成状态：

- 尚未开始实现：按 `docs/development/change-workflow.md` 选择 Full 或 Bugfix lite；
- 用户尚未完成体验验证：暂停收尾，请用户先完成实际体验并确认结果；
- 已存在对应 active unit：恢复该 unit 的既有生命周期，不创建第二个 unit；
- diff 混有其他任务或用户已有修改：先划定本次范围，只处理和提交明确属于本次需求的文件。

## 1. 锁定实现范围

先读取 `AGENTS.md`、`docs/README.md`、`docs/development/change-workflow.md`、`docs/changes/README.md` 和受影响包的 current specs，再核对：

- 当前 checkout、branch、worktree、base commit、HEAD、upstream 和 `git status`；
- 本次需求对应的 commits、已暂存和未暂存 diff；
- 对话中用户的原始诉求、后续纠正、范围决定和明确验收结论；
- 改动触及的代码、测试、配置与长期文档。

不要从最终代码反推并改写用户意图。代码说明“实际实现了什么”，对话中的用户决定说明“本来要解决什么”。

## 2. 建立事后 unit

根据实际变更选择 `feat`、`bugfix`、`refactor` 或 `perf`，执行：

```bash
python3 .claude/skills/change-spec-author/scripts/next_unit_id.py <type>
```

创建以下目录。若本次没有 observable behavior 变化，可以省略 `specs/`：

```text
docs/changes/<unit-dir>/
├── spec.md | incident.md | motivation.md
├── design.md
├── specs/
│   └── <package>/<target>.md
└── code-review.md
```

使用本 skill 的 `assets/design.md` 和 `assets/code-review.md`。首文档的字段骨架复用 `.claude/skills/change-spec-author/assets/` 中对应的 `spec.md`、`incident.md` 或 `motivation.md`，删除模板注释后按已经确认的事实填写。

快速开发 unit 不创建 milestone 目录、`tasks.md`、`progress.md`、`design-review.md`、`verification.md` 或 reviewer 产出的 `acceptance.md`。没有发生过的过程不能事后补造。

如果收尾不能在当前 session 完成，将 unit 留在 `docs/changes/` 活动区；后续从已有首文档、as-built design、code review 记录和 Git diff 继续。

## 3. 回填真实知识

### 首文档

- 原样保留用户最初提出的需求或问题；
- 按发生顺序记录改变范围或行为的关键澄清；
- 用最终确认的用户场景、范围和验收结果表达“做什么”；
- bugfix 写清现象、复现、根因和期望行为；
- 不用代码结构替代用户意图。

### As-built design

`design.md` 必须明确标记为 implementation 后形成的 as-built design，并只记录可由当前代码、diff 和对话决定验证的内容：

- 实际修改的模块及职责；
- 真实调用链、数据流、状态变化与边界；
- 已采用的关键决策、理由和约束；
- 兼容性、失败路径、风险与回滚办法；
- 实际 commits、测试和运行证据的定位；
- 初始设想与最终实现存在差异时，记录最终选择及原因。

不要使用未来时态伪装成事前方案，不创建虚构的候选方案、milestone 或 review Round。

### Current spec

逐项比较实现后的 observable behavior 与 `docs/specs/`：

- 行为发生变化：编写 delta-spec，并在 code review 通过后归并到 canonical spec；
- 只有内部实现变化：在 `design.md` 记录“无 canonical spec 变更”及具体理由；
- current spec 与真实实现存在无关漂移：不要顺手决定预期，把它记录为独立问题交给用户审核。

## 4. 确认用户验收

确认当前对话中用户已经亲自测试并认可结果。用户验收替代快速开发路径中的 `change-reviewer`，不另写 reviewer 报告；本路径也不调用 `change-verifier`。代码级测试仍按改动风险运行，但不重复执行一轮产品验收。

## 5. 强制 code review

在主会话调用 `$change-code-review`：

1. 首轮使用 `review_mode: full`，范围覆盖从 base 到当前实现的全部 commits，以及属于本次需求的未提交改动。
2. 把 review 的 base、head、dirty 范围、结果和 findings 写入 `code-review.md`。
3. 当前主会话核实并修复成立的 findings，运行最窄相关测试。
4. 修复只影响内部实现时继续收尾；修复改变用户可观察行为时，暂停并请用户重新确认受影响旅程。
5. 有 findings 时按 `$change-code-review` 的 `patch` / `closure` 模式复审，直到没有阻塞 finding；每轮结果和 resolution 追加到 `code-review.md`。

code review 未通过时 unit 保持 active，不能归档。

## 6. 收尾与交付

满足以下条件后才归档：

- 用户已经在当前对话确认结果；
- 首文档和 as-built design 与最终实现一致；
- 必要的 delta-spec 已归并，或已说明无 canonical spec 变更；
- 强制 code review 通过；
- 受影响的最窄测试、文档检查和按风险选择的本地 CI 通过；

将整个 unit 移入 `docs/changes/archive/<unit-dir>/`。提交、push 和 PR 只做到用户当前明确授权的范围；用户要求先审文档时，在归档或 commit 前停下汇报。
