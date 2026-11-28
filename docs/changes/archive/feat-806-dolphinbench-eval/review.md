# feat-806: Review

## 范围与版本

- 本次问题与需求/设计位置：[spec.md](spec.md)、[design.md](design.md)
- 实际 executed_base / validated_at：`890d74f70d1444f2fd961a7e60d02b858821abaa..940e4a56f25cbe4411bfbf9047bd419459ed8ebe`（R1 审 `890d74f70..2a9e1f086`，R2 closure/patch 审 `2a9e1f086..940e4a56f`）
- 最终 effective_base / effective_through 与保留依据：`890d74f70..HEAD`；归档提交仅移动 `docs/changes/feat-806-dolphinbench-eval` 至 `docs/changes/archive/` 并写入本报告，不改变任何评测或运行时代码。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 跨包依赖边界、工具沙箱隔离、断点续跑一致性、`--dream-min-interval-days` 多日巩固消融、多人物时区及契约增量判定 | `change-code-review` · 独立审查子 Agent（`f7f48806-3955-4624-92b7-672b418d5714`，只读 full + closure） | Pass | R1 发现 6 项问题均已在 `940e4a56f` 修复并经 R2 独立复核关闭；`no spec delta` 判为 `aligned` |
| 真实 DolphinBench 小切片三路消融与长程运行可用性 | 用户验收（快速开发实跑） | Pass | Morgan `1:10` 三路消融（`product` 3/3、`memory-only` 3/3、`search-only` 2/3）与 `1:753` 轮长周期摄入快照已由用户确认保留 |

## Findings 与关闭

1. **F1 (`high`, CONFIRMED -> `closed`)**：`docs/changes/feat-806-dolphinbench-eval/design.md` 初稿缺少 `>= 800` Full unit 必需的 `## 五端对齐矩阵`，导致入库后 `./scripts/docs-check` 与 `scripts/check_platform_parity.py` 失败。
   - **Resolution (`940e4a56f`)**：在 `design.md` 补齐完整五端对齐矩阵（全部标 `platform-exempt` 并说明离线评测范围），R2 独立运行 `./scripts/docs-check` 与 `check_platform_parity.py` 均通过（`rc=0`）。
2. **F2 (`high`, CONFIRMED -> `closed`)**：`--dream-min-interval-days > 1` 的上次巩固水位仅保存在进程内存中，遇到 250 轮进程重启、瞬时重试或断点恢复时丢失，且缺少自动化测试。
   - **Resolution (`940e4a56f`)**：在 `dolphinbench-runtime.ts` 将 `lastConsolidationAt` 持久化至 `clock-state.json`，`run.py` 在进程轮转与重试时传入 `last_completed_ts` 而非下一轮时间戳，并在 `dolphinbench-evaluation.test.ts` 新增跨进程重启 `dreamMinIntervalDays: 3` 集成测试通过，R2 复核关闭。
3. **F3 (`medium`, CONFIRMED -> `closed`)**：重试/恢复仅回滚 `chat-checkpoint.sqlite`，未同步快照和回滚 `inbox.sqlite`、`node.sqlite` 与模拟应用 `state.json`。
   - **Resolution (`940e4a56f`)**：`dolphinbench.ts` 仅在 `terminal.kind === 'completed'` 时通过 `node:sqlite` `backup()` 同步原子快照三份 SQLite 并在启动时成套恢复，`run.py` 为单轮摄入落盘 `state.json.ckpt` 并在中断重跑时先行恢复，R2 复核关闭。
4. **F4 (`medium`, CONFIRMED -> `closed`)**：`run.py` 汇总摄入统计使用 `*.json`，会混入历史遗留的 `<sid>.failed.json`。
   - **Resolution (`940e4a56f`)**：成功后清理对应 `.failed.json`，且汇总仅匹配 6 位数字 `[0-9][0-9][0-9][0-9][0-9][0-9].json`，R2 复核关闭。
5. **F5 (`low`, CONFIRMED -> `closed`)**：`dolphinbench-runtime.ts` 直接对目标调用 `realpathSync`，导致读取 `.nanoassistant/memory` 下不存在文件时误记为沙箱越界拒绝。
   - **Resolution (`940e4a56f`)**：新增 `resolveExistingOrChildRealpath` 向上解析最近已存在父目录的真实路径再拼接子路径，既拦截越界符号链接又不误拦库内缺失文件，R2 复核关闭。
6. **F6 (`low`, CONFIRMED -> `closed`)**：`run_suite.py` 硬编码 `/System/Volumes/Data` 磁盘统计路径，非 macOS 环境不可运行。
   - **Resolution (`940e4a56f`)**：改为统计 `local_state_root` 所在卷空间，R2 复核关闭。

无存活 findings。

## 流程收口

- **重要目标和关键设计覆盖**：计划输出、按时区推进摄入、`03:00` 自动及多日合并巩固、冷上下文三路消融隔离与评分均已实现并通过测试验证。
- **开放问题 / pending / inconclusive**：无（真实外部模型网关调用在自动化 CI 中由确定性 fixture 替代，真实模型链路已在用户验收的 `1:10` 与 `1:753` 运行中证实）。
- **最终 delta 校对**：`no spec delta`（`aligned`）。
- **版本变化后保留 / 补验的判断与依据**：`940e4a56f` 修复后重跑 `vitest`（2 passed）、`pytest`（53 passed）、`ruff`、`docs-check` 与 `check_platform_parity.py` 全部通过。
- **测试资源回收结果 / 例外保留项、owner 与回收触发**：单测临时目录已全部自动清理，无残留评测后台进程；用户明确要求保留 `/Users/czj/.cache/nano-evals/runs/morgan-v0-baseline-s1-753-20261128` 与对应 `dolphinbench-state` 快照（owner：当前评测工作流，回收触发：完成 `feat-822` 记忆升级对比验收且用户不再需要 v0 基线后清理）。
- **交付范围与剩余事项**：归档本单元并推送分支 `unit/feat-806-dolphinbench-eval`，创建指向 `develop` 的 PR，开发 worktree 按规范保留至 PR 合入后清理。
