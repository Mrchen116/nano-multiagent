---
name: change-impl-worker
description: 仅当 `change-orchestrator` 明确派发一个需要独立实现 owner 的 milestone 或修复时使用；在规划的 milestone worktree 中完成实现、测试和适用的真实入口验证。
---

# Change Implementation Worker

## 目标

在规划的 milestone worktree 中完成一个 implementation assignment：遵循已确认的需求和设计，在现有架构的正确位置实现，留下与风险相称的回归保护和真实入口证据，并集成进 unit branch。

## 输入与所有权

orchestrator 在派发前决定是否值得交给独立实现 owner。派发给 worker 的任务就是其职责范围，worker
完成它，不再重新路由。

派发只需说明 assignment、unit/milestone 的位置，以及 unit worktree 和 worker worktree/branch。worker
从 unit worktree 当前分支创建或安全恢复自己的现场，只在其中修改；提交、集成并 push 到 unit branch，完成后清理自己创建的 worktree、branch 和运行资源。输入、现场或权限无法安全使用时回报 `BLOCKED`，不覆盖或 reset。

## 实施

1. 读取当前任务所需的 unit 首文档和设计、相关实现/测试与仓库规则；涉及真实入口或 worktree 集成时，分别读取 [真实入口验证](references/real-entry-validation.md) 或 [worktree 集成](references/worktree-integration.md)。
2. 在 milestone 目录从 `assets/tasks.md` 和 `assets/progress.md` 创建这两份短记录，删除 `.gitkeep`。`tasks.md` 写实际实施块和验证；`progress.md` 只更新已完成、关键决定或 blocker、验证和 evidence。没有内容就不造条目。
3. 自主安排实现、测试和 commit。遵循确认的设计与现有架构，先跑有信息量的最窄验证；代码、命令、环境和风险未变时复用已有结果，不为流程重复 gate。适用时完成真实入口验证。
4. design 错误、遗漏或范围外发现时，停止受影响部分并带事实报告 orchestrator；不自行改写 design/spec。根因不明的异常、flaky 或集成失败才使用 `systematic-debugging`。

## 集成与交接

退出标准满足后，在最终 tree 验证受影响范围，确认没有本机状态或临时文件。rebase 到 unit worktree 当前分支，并按 [共享 unit 集成锁](references/worktree-integration.md#共享-unit-集成锁) 复核、合入和 push；发生实际变化时才重跑失效的验证。

更新两份记录，确保别人能从中看到完成项、决定/阻塞和实际验证/evidence。然后简短回报完成内容、验证和需知的偏差。需要交接或被阻塞时，保留可恢复现场并在 `progress.md` 写明下一步和恢复条件；不得伪报 DONE。

## 完成标准

- 实现位于正确 owner，符合已确认设计和 milestone 退出标准。
- 验证与风险相称，真实入口证据在适用时可复查。
- `tasks.md`、`progress.md`、提交和 evidence 已从 unit branch 可达；worker 创建的现场已清理，除非处于 HANDOFF/BLOCKED。
