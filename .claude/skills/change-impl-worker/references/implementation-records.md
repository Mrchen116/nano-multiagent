# 按需实施记录

默认依靠 design 的 milestone 行、Git commits、测试结果和 DONE 回报恢复，不创建过程文档。只有下列信息无法由这些来源清楚表达时才写记录。

## 什么时候创建

创建 `tasks.md`：

- assignment 有多个相对独立、需要跟踪完成状态的实施块；
- 预计跨较长时间或需要换人；
- 多个验证前置之间有不直观依赖。

创建 `progress.md`：

- 需要 HANDOFF，聊天和 commits 不足以恢复；
- 发现 design issue，需要保存证据和恢复条件；
- live/visual evidence 需要持久 locator；
- 存在会影响后续维护、但不适合写进代码注释的非显然决策。

两者都不是 milestone 完成的固定条件。一个自包含 assignment 可以都不创建；只有恢复记录需要时也可以只创建 `progress.md`。

## 记录原则

- 不复制首文档、design 或测试规范全文，只引用对应段落。
- 不要求固定 roadpoint 数量；按真实实施块记录。
- 不填写与任务无关的状态矩阵或 `N/A` 字段。
- 不创建 plan commit；记录和相关实现一起提交。
- 不让文档记录其所在 commit 的自身 hash；用 branch/head 或后续 DONE 回报定位。
- 截图、录屏和报告放在 `<unit>/<milestone>/evidence/`，记录相对路径。

## 精简 tasks.md

```markdown
# <milestone-id> Tasks

目标/退出标准：<引用 design 行>

- [ ] <实施块> — 验证：<最窄命令或 evidence>
- [ ] <实施块> — 验证：<最窄命令或 evidence>

测试策略：<风险、可观察 seam、已有保护与处置、最低有效层>
```

## 精简 progress.md

```markdown
# <milestone-id> Progress

## <日期/阶段>

- 当前 head：<sha>
- 已完成：<结果>
- 关键决定/设计问题：<决定、证据或 N/A>
- 验证：<命令、结果、tree>
- Evidence：<持久 locator 或 N/A>
- 下一步/恢复条件：<仅 HANDOFF/BLOCKED 时填写>
```

Promotion candidate 只有在已经有本 assignment 证据支持、且确实应归并到唯一长期 owner 时才记录；没有则省略整个段落。
