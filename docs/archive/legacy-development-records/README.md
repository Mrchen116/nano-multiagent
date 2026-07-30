# Legacy Development Records

这里冻结 2026 年 2 月至 7 月间旧 TDD control-tower 流程留下的任务、进度、验收和经验记录。它们曾以
`M<number>` roadpoint/milestone 为工作单位，已经被 `docs/changes/<unit>/` 的 change unit 体系取代。

## 原路径与内容

| 原路径 | 归档位置 | 冻结内容 |
|---|---|---|
| `/ROADMAP.md` | [`ROADMAP.md`](ROADMAP.md) | 早期全局 milestone 路线 |
| `/TASKS.md` | [`TASKS.md`](TASKS.md) | 当时的根级当前任务视图 |
| `/PROGRESS.md` | [`PROGRESS.md`](PROGRESS.md) | 当时的根级进度时间线 |
| `/LOGBOOK.md` | [`LOGBOOK.md`](LOGBOOK.md) | 未完成 owner 归并的经验集合 |
| `/TASKS/` | [`TASKS/`](TASKS/) | 196 份 milestone/roadpoint 任务记录 |
| `/PROGRESS/` | [`PROGRESS/`](PROGRESS/) | 202 份实施过程与证据记录 |
| `/ACCEPTANCE/` | [`ACCEPTANCE/`](ACCEPTANCE/) | 114 份报告、脚本、截图和运行快照 |

这些路径已停止写入。当前工作状态、milestone 进度和验收证据只写入
[`docs/changes/<active-unit>/`](../../changes/README.md)；跨任务规则经过验证后归并到对应的架构、spec、
development、operations、代码、测试、CI 或 skill owner。

## 使用边界

- 记录中的 `TODO`、`Active`、`Next` 和失败项不构成 current backlog；需要继续的问题应基于当前代码和 specs
  重新立项。
- 历史测试结果、截图和日志只证明当时基线上的一次运行，不能代替当前验证。
- `LOGBOOK.md` 中看似通用的规则仍需核对现状；成立的内容应进入唯一 canonical owner，而不是恢复通用日志写入。
- 原目录整体移动，文件内容和相对层级保持不变，便于按旧 milestone id 取证。
