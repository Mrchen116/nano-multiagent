# refactor-364: change-concurrent-isolation

> **回顾性 spec**:本 unit 在改动落地后补写,记录"主仓 + 默认端口被并发 agent 互相踩"的两类隔离问题以及最终采纳的最简方案。无 design.md / 无 milestone / 无 orchestrator,改动已直接在 main 上完成。

## Relations

- Related: change-orchestrator / change-impl-worker / change-reviewer 三个 skill

## 原始诉求(用户原话)

> 当前 change-orchestrator,change-worker change-review skill 体系有两个问题阻碍了无法多个 orchestrator 并发做不同的需求。1. 直接把主仓切了分支。这个好改,主仓不切,change 新建 worktree。2. 端口冲突。当两边都在做 review(worker 也可能),启动 IM 都是同样的端口,可能存在杀了对方的可能性。

后续在讨论中反复收紧复杂度:

> 我觉得还是太复杂了。有没有更简单的思路,比如自己开的服务,自己关,这就解决了留下错误服务的问题。

> 我思考决定,这种增加代码方式不可取,增加了复杂性。我觉得可以做的是:如何快速找到几个空闲端口(这个或许可以写一个脚本),然后所有服务是否支持环境变量或者传参指定端口。

> 这些 skills 是面对通用的软件开发场景,不单是这个仓库。所以我们应该把修改分为两部分,一部分是 AGENTS.md 中要写出来每个服务如何指定端口。然后 skill 中只开服务需要考虑到并行的问题,需要指定端口。

## 现状痛点

1. **orchestrator §2.3 在主仓 checkout unit 分支**(`git checkout main && git checkout -b unit/<id>`)。多 orchestrator 并发时主仓 HEAD 被反复切换,用户也可能正在主仓做别的事。
2. **reviewer §2 直接在主仓 checkout unit 分支**走旅程。同一冲突放大一倍——worker(milestone worktree)、orchestrator、reviewer 三方在主仓争抢 HEAD。
3. **worker §6.1 集成 merge 时回主仓 checkout 后 push**。又一处主仓 HEAD 写入。
4. **reviewer §2.5"无脑重启"全部硬编码默认端口**(IM 8011 / Gateway / Vite 5173)。两个 reviewer 同时跑,后到者 kill 先到者的进程。
5. **服务起完不 kill 留下孤儿**。下次用户 `lsof :8011` 看到的可能是某个分支跑的 IM,误以为是主仓,在分支代码上测半天。

## 目标状态

**两类隔离,最简实现:**

### A. 主仓 HEAD 不动

- orchestrator 拥有"unit worktree"概念:`.worktrees/unit-<unit_id>/`。`git worktree add` 替代 `git checkout -b`,所有针对 unit 分支的 rebase / merge / push / PR 都 `git -C "$unit_worktree" ...`。
- reviewer 和 worker(合并 unit 时)接收 `unit_worktree_dir` 派发字段,在该 worktree 内工作。
- 主仓 HEAD 在整个 unit 生命周期内不动,Sync Gate 的 main 操作除外。
- 退出前清理 unit worktree(`git worktree remove`)。

### B. 服务运行时隔离

**分两层**:

- **skill 层(通用纪律)**:在 worktree 内起任何监听端口的服务,必须分配空闲端口、退出前 kill 自己起的进程。不写本仓服务名。
- **项目 AGENTS.md 层(本仓特化知识)**:列每个服务的端口/URL 参数化方式(IM `--port`、Gateway `--im-service-url`、Vite `--port`、Coding CLI `--base-url`)+ 端口分配 helper(`scripts/free-ports.sh`)+ PID 文件命名约定(`.im.pid` 等)+ 标准退出清理 snippet。

**不做的事**(被用户明确否决,作为约束记录):

- ❌ 全局 runtime 注册表(`~/.nano-assistant/runtime/<unit>/`)
- ❌ 专用 `nano-runtime` CLI 工具 + service registry yaml
- ❌ orchestrator 拥有 service 生命周期 / setup 时统一分配端口
- ❌ Gateway / IM 代码改造支持 env override DB 路径、workspace_root(Gateway `--im-service-url` 已天然支持,无需改;IM DB 跨 unit 共享暂时接受)

## 影响范围

- `.claude/skills/change-orchestrator/SKILL.md`:新增 §0.15 主仓 HEAD 不动硬规则;§2.3 改写为 `git worktree add`;§2.4 注释 reviewer 落点;§3.1 / §5 派发包加 `unit_worktree_dir`;§5.2 / §6.6 / §7.1 改 `git -C`;§7.4 加 worktree teardown。
- `.claude/skills/change-impl-worker/SKILL.md`:§1 派发契约加 `unit_worktree_dir`;§6.1 集成段 cd 到 unit worktree;§0.11 末尾指向 AGENTS.md 端口 helper。
- `.claude/skills/change-reviewer/SKILL.md`:§1 派发契约加 `unit_worktree_dir`、删"不需要 worktree"语句;§2 启动 / §8.1 提交两处 cd 到 unit worktree;§2.5 加并发隔离要求 + per-round secret;§8.1 后加自起自 kill 铁律。
- `AGENTS.md`:新增"运行时服务并行启动"段,含端口 helper、参数化表、PID 文件清单、退出清理 snippet、已知未参数化点。
- `scripts/free-ports.sh`:新增(~15 行 bash),一次性分配 N 个互不重复的空闲端口。

## 迁移与回滚策略

- **存量 unit**:旧的 design.md `§Runbook for Reviewer` 仍是 bash 命令格式,reviewer 按现有 runbook 跑即可——新 skill 的并发隔离要求是"如果项目 AGENTS.md 有则按它来",老 unit 不强制迁移。
- **未来 design-author**:design.md runbook 应改用 `$IM_PORT` 等占位符,这是 change-design-author skill 的后续微调,不在本 unit 范围。
- **回滚**:三个 skill + AGENTS.md 一并 revert 即可,无代码改动,无数据迁移。`scripts/free-ports.sh` 可独立保留(无副作用)。

## 验证

- `scripts/free-ports.sh 3` 输出三个空闲端口,无重复,已 smoke。
- 真实并发场景验证留待下一次双 orchestrator 跑不同 unit 时观察。
