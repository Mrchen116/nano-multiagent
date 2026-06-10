---
name: change-code-review
description: 提 PR 前对代码 diff 做精确率导向的多角度 code review,与 change-reviewer / change-verifier 并列的验收闸。由 change-orchestrator 在主会话内执行(不派给 subagent);用户要求"review 这个 diff / 提 PR 前把代码过一遍"时也可触发。
---

# Change Code Review

`medium effort → 3+4 个角度 × 6 个候选 → 1 票验证 → ≤8 条发现`

你正在以 **medium effort / 中等强度** 进行以 **precision / 精确率** 为目标的代码审查：你暴露的每一条 finding，都应该是 maintainer 会采取行动处理的问题。

> 执行环境约束：本 skill 在主会话(orchestrator)内执行。Phase 1 的 finder 角度和 Phase 2 的 verifier 都通过 Agent 工具派发(`run_in_background: true`、model sonnet),由你汇总。

## Phase 0 — 获取 diff

运行 `git diff @{upstream}...HEAD`，如果没有 upstream，则运行 `git diff main...HEAD` / `git diff HEAD~1`，获取本次待审查范围的 unified diff。

如果存在未提交修改，或者 range diff 为空，也运行 `git diff HEAD`，并将工作区改动纳入审查范围——审查经常发生在提交之前。

如果传入了 PR 编号、分支名或文件路径作为参数，则审查该目标。

将这个 diff 视为本次审查范围。

## Phase 1 — 寻找候选问题

### 3 个 correctness 角度 + 3 个 cleanup 角度 + 1 个 altitude 角度，每个最多 6 个

通过 Agent 工具运行 **7 个彼此独立的 finder 角度**。每个角度最多产出 **6 个候选发现**，每个候选包含 `file`、`line`、一句话 `summary`，以及具体的 `failure_scenario`。

### Angle A — 逐行 diff 扫描

逐个 hunk、逐行阅读 diff。然后读取每个 hunk 所在的完整函数上下文——被改动函数中未改动的行也属于审查范围，因为这个 PR 重新暴露了它们，或者未能修复它们。

对每一行都问：什么输入、状态、时序或平台会让这一行出错？

重点寻找：反向条件 / 错误条件、off-by-one、null / undefined 解引用、遗漏 `await`、falsy-zero 判断、变量复制粘贴错误、catch 中吞掉错误、未转义的正则元字符。

### Angle B — 被删除行为审计

对 diff 中每一行被删除或替换的代码，说明它原本维护了什么 invariant 或行为，然后在新代码中搜索这个 invariant 是否被重新建立。

如果找不到，就把它作为候选问题：被删除的 guard、被丢弃的错误路径、被缩窄的校验、被删除但原本覆盖真实场景的测试。

### Angle C — 跨文件追踪

对 diff 改动的每个函数，找到它的调用方（Grep 该符号），检查这次改动是否破坏了某个调用点：新增的前置条件、变化的返回值形状、新抛出的异常、时序 / 顺序依赖。同时检查被调用方：同一 PR 中的并行改动是否让某次调用变得不安全？

### Reuse

上面的角度找 bug；这个角度和接下来两个在被改动的代码中找 cleanup。标记重新实现了 codebase 中已有能力的新代码——Grep 共享 / 工具模块和改动点邻近的文件，并指名应该改用的既有 helper。

### Simplification

标记 diff 引入的不必要复杂度：冗余或可推导的状态、带细微变化的复制粘贴、深层嵌套、遗留的死代码。指名能完成同样工作的更简形式。

### Efficiency

标记 diff 引入的浪费：重复计算或重复 I/O、本可并行却串行执行的独立操作、加进启动路径或热路径的阻塞工作。也要标记由闭包 / 捕获环境构建的长生命周期对象——它们会让整个外围作用域在对象存活期内无法释放（当作用域持有大值时就是内存泄漏）；应改用只拷贝所需字段的 class/struct。指名更便宜的替代方案。

### Altitude

检查每个改动是否实现在正确的深度，而不是脆弱的 bandaid。在共享基础设施上叠特例是修得不够深的信号——优先泛化底层机制，而非添加特例。

> cleanup 和 altitude 的候选沿用同样的 `file`/`line`/`summary` 结构；`failure_scenario` 里写具体代价（什么被重复、被浪费、变得更难维护），而不是崩溃。当输出上限迫使取舍时，correctness bug 永远优先于 cleanup 和 altitude 发现。

凡是能说出 failure scenario 的候选都要传递到验证阶段——finder 悄悄丢弃自己半信半疑的候选,等于绕过了 verify 步骤,这是漏报的主要来源。

## Phase 2 — 验证

### 1 票制，3 种状态

对指向同一行 / 同一机制的候选进行去重，保留 failure scenario 最具体的那个。

对每个剩余候选，通过 Agent 工具运行 **一个 verifier**：给它 diff、相关文件以及候选问题，让它只返回以下三种结果之一：

- **CONFIRMED** —— 能说清触发它的输入 / 状态，以及错误输出或崩溃。引用对应代码行。
- **PLAUSIBLE** —— 机制真实存在，但触发条件不确定，例如时序、环境、配置。说明还需要什么才能确认。
- **REFUTED** —— 事实错误，例如代码并非如此，或其他地方已有 guard。引用能证明它被反驳的代码行。

保留投票结果为 **CONFIRMED** 或 **PLAUSIBLE** 的候选。

## Output

以 JSON 数组返回最多 8 个对象：

```json
[
  {
    "file": "path/to/file.ext",
    "line": 123,
    "summary": "一句话说明这个 bug",
    "failure_scenario": "具体输入 / 状态 → 错误输出 / 崩溃"
  }
]
```

按严重度从高到低排序。如果验证后存活的发现超过 8 条，保留最严重的 8 条。如果没有任何发现通过验证，返回 `[]`。
