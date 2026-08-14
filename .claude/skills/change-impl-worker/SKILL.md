---
name: change-impl-worker
description: 仅当 `change-orchestrator` 明确派发一个需要独立实现 owner 的 milestone 或修复时使用；在规划的 milestone worktree 中完成实现、测试和适用的真实入口验证。
---

# Change Implementation Worker

## 目标

在规划的 milestone worktree 中完成一个 implementation assignment：遵循已确认的需求和设计，在现有架构的正确位置实现，留下与风险相称的回归保护和真实入口证据，并集成进 unit branch。

## 1. 路由

是否派 worker 由 orchestrator 结合完整上下文判断，不使用固定分类表或行数阈值。worker 的职责是
承担一个独立 owner、隔离现场或深入实现/验证确实能提高交付可靠性的 assignment。

如果收到的 assignment 显然可以在 unit 中直接安全闭环，且独立 worker 不会增加有价值的 ownership
或验证，回报 `ROUTE_BACK` 和简短事实理由；不要为适配本 skill 硬造 milestone。

## 2. 输入和所有权

派发包必须包含：

```yaml
unit_id: <type-id>
unit_dir: <type-id-short-desc>
milestone_id: <unit-id-MN>
milestone_dir: <MN-short-desc>
unit_worktree_dir: <absolute-unit-worktree-path>
worktree_dir: <absolute-path>
branch: <planned-milestone-branch>
mode: full | lite
assignment: milestone | substantive-fix
```

orchestrator 提供 unit 与 milestone 的精确路径和 branch 名，不预建 milestone worktree。worker 是自己
milestone worktree/branch 的 creator-owner，负责：

- 从 `unit_worktree_dir` 当前 checkout 的分支创建或安全恢复 `worktree_dir` / `branch`，只在该现场写本 assignment 的文件；
- 提交实现；DONE 时把结果集成并 push 到 unit branch，HANDOFF 时 push milestone branch；
- 清理自己启动的进程和临时运行资源；
- DONE 后删除自己创建的 milestone worktree/branch；HANDOFF/BLOCKED 时保留可恢复现场。

缺字段、目录/branch 不符，或存在来源不明的 dirty 内容时停止并报告；禁止 reset 或覆盖现场。

在 `docs/changes/`、`docs/changes/archive/` 中按 `unit_dir` 唯一解析 unit。retired unit 不实施。

## 3. 渐进读取上下文

只读取支持当前 assignment 决策所需的内容：

1. unit 首文档；Full 再读 `design.md` 中相关决策、milestone 行、退出标准和 reference contract；lite 读 `fix.md`。
2. 仓库及受影响目录的 `AGENTS.md` / `CLAUDE.md`。
3. 相关 current spec、现有实现、调用方和现有测试；先查同类能力，避免平行实现。
4. 写测试前读 `docs/development/testing.md`；写产品代码时遵循 `docs/development/coding-guidelines.md`。
5. 创建/恢复 milestone 现场或进入 DONE 集成前，读取 [worktree 创建、集成与清理](references/worktree-integration.md)。
6. 涉及浏览器、真实入口、跨进程或外部系统时，读取 [真实入口与运行证据](references/real-entry-validation.md)。
7. 需要实施台账、复杂任务恢复或 HANDOFF 时，读取 [按需实施记录](references/implementation-records.md)。

同一 worker 被续跑、相关文档版本未变时复用已有上下文，不重新完整读取。无需发送固定“开工”消息；只有意图/范围不清、设计问题或阻塞时联系 orchestrator。

## 4. 规划与基线

根据任务本身组织实施顺序、commit 边界和必要记录。

测试基线按它能回答的问题选择：

- 有同一代码树、相同环境的可信近期结果时复用，不重跑。
- 需要区分既有行为与本次回归时，跑能暴露该风险的最窄 baseline。
- 不为了“基线仪式”先跑全仓测试；完整 unit/CI gate 由 orchestrator 在集成树上统一执行。
- baseline 已有无关失败时记录命令和证据并报告，不顺手扩大范围。

## 5. 实施与验证

### 5.1 架构与范围

- 遵循 design 已确认的关键决策、接口、数据流、范围和退出标准。
- design 未规定的实现细节默认扩展已有 service/repository/adapter/component/fixture，不新造平行机制。
- 禁止吞错、神秘 fallback、临时常量和只绕过症状的 heuristic。
- 只改 milestone 范围；实现正确性必需但 design 未列出的文件先报告，由 orchestrator 判断是否修订范围。
- `docs/specs/`、unit delta-spec 和已确认设计不由 worker擅自改写。

### 5.2 Red / Green 是验证纪律，不是提交结构

- 可测试的新行为或 bug 修复，先获得能复现缺失能力的失败证据，再完成 Green。
- 纯重构使用既有行为保护证明前后不变，不制造虚假的红测。
- 视觉/交互变更可用明确的前态复现、状态清单或截图对照代替没有意义的自动化红测。
- 测试可观察行为和稳定 seam；不要把 milestone 编号或私有实现写成永久测试契约。
- 先跑最窄相关测试，再按实际风险扩大。不要在每个内部步骤后重复同一完整 gate。

按可审查边界组织 commit。

### 5.3 真实入口

新功能、用户报告的运行时 bug、前端 UI、跨进程/投递/调度等集成缝必须按 [真实入口与运行证据](references/real-entry-validation.md) 完成适用验证。纯内部、无用户入口影响的重构不强制制造 live 验收。

环境无法满足必需证据时报告 `BLOCKED`，不要用 mock、stub 或低一层测试冒充真实链路。

### 5.4 测试失败分流

先分类，再决定是否使用 `systematic-debugging`：

- 预期 TDD 红测：确认失败点正确后继续。
- 已知环境/操作错误或直接遗漏：修正环境/操作，或报告阻塞。
- 根因仍不明确的异常、flaky、运行时或集成失败：调用 `systematic-debugging`，稳定复现并定位根因后再修。

不要把所有非零退出都升级成完整调试流程；也不要用 skip、xfail、放宽断言、sleep 或重试掩盖真实失败。

## 6. 设计问题与范围外发现

发现已确认 design 错误、遗漏或不可执行时：

1. 停止受影响编码，保留已完成的安全工作。
2. 向 orchestrator 报告原决策、直接证据、建议修订和波及范围。
3. 不自行修改 design/spec；等待对应 owner 更新并确认后续路径。
4. 恢复时只重读变更过的相关内容。

范围外问题只报告证据、严重度和建议 owner；是否建立 issue 由 orchestrator 决定，不由 worker 自动扩大外部写入。

## 7. 验证结果的有效性

一次 gate 的结论绑定到：代码树、命令和会影响结果的环境。三者未变时可以复用；发生以下任一情况才重跑受影响范围：

- 实现或测试树变化；
- rebase/merge 实际改变相关文件或依赖；
- 配置、依赖、服务或运行环境变化；
- 原 gate 未覆盖新风险，或无法证明仍有效。

worker 不因未来可能 rebase 而提前重复 gate。orchestrator 集成后根据实际 delta 决定保留、局部重跑或扩大验证。

## 8. DONE、HANDOFF 与 BLOCKED

### DONE

退出标准全部满足后：

1. 在最终 worker HEAD 上运行受影响的最窄测试和风险要求的扩展/真实入口验证。
2. 确认只有本 assignment 的修改，没有 secret、本机状态或临时运行文件。
3. 获取 `unit_worktree_dir` 当前分支，rebase milestone branch；只对实际失效的 gate 重跑受影响范围。
4. 按 [共享锁协议](references/worktree-integration.md#共享-unit-集成锁) 获取 unit 集成锁，复核
   unit HEAD 未在步骤 3 后前移；若前移，释放锁并重复 rebase/失效判断。确认未变后才在
   `unit_worktree_dir` 合入、push；需要新实现判断的冲突先报告，不用覆盖或 reset 绕过。
5. 确认提交和 evidence 从 unit HEAD 可达，清理运行资源与自己创建的 milestone worktree/branch。
6. 回报：

```yaml
milestone_id: <id>
status: DONE
head: <sha>
unit_head: <integrated-and-pushed-sha>
commits: [<sha>, ...]
changed_files: [<path>, ...]
test_strategy:
  risk_and_seam: <what can regress and the stable seam exercised>
  existing_coverage:
    - disposition: <keep | rewrite-merge | delete | none>
      locator: <path::test or searched scope>
      rationale: <why this preserves or replaces the risk owner>
  lowest_layer_and_owner: <test layer and file owner>
tests:
  - command: <command>
    result: <pass summary>
    tested_head: <commit sha>
    tree: <git tree sha>
entry_evidence: <durable path/locator or N/A with reason>
implementation_records: [<optional paths>]
design_deviations: []
env_caveats: <none or limitation>
promotion_candidates: []
```

`head` 是最终 rebased milestone commit，`unit_head` 是已 push 的集成 commit；每条测试同时报告
实际受测 commit 与 Git tree。rebase 后 tree 等价时，保留原测试并在结果中说明等价证据。

### HANDOFF

任务可继续但当前 worker 无法完成时，提交并 push 可恢复的 milestone branch；仅在聊天不足以恢复时创建精简 `progress.md`。回报当前 head、已完成内容、下一步、blocker 和必要环境定位。保留 worktree，由 orchestrator 接管。

### BLOCKED / ROUTE_BACK

缺输入、设计决策、权限、必需外部资源或真实入口环境时回报 `BLOCKED`。任务不值得独立 worker
ownership 时回报 `ROUTE_BACK`。两者都不得伪报 DONE，也不得为证明“做过流程”创建空文档或无意义 commit。

## 完成标准

- 实现位于现有架构的正确 owner，没有平行机制或静默兜底。
- milestone 每条退出标准可追到代码、测试或真实入口证据。
- 测试和证据与风险相称，没有用重复 gate、样板文档或 Git 仪式替代判断。
- 结果已集成并 push 到 unit branch，worker 创建的运行资源和 milestone worktree/branch 已清理。
