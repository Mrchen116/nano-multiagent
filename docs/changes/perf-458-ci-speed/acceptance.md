# perf-458 — 验收报告

> **Post-review closure (2026-07-11):** 本报告原始验收对应 `31c41576`。后续内部 code review 发现并修复两处测试信号缺口：新增 connected-silent live timeout unit 回归，并为 ShellRunner stopper 增加 monitor 完成等待。当前 head 因此包含一处内部 `src/agent/.../shell_runner.py` testability seam，原验收的“`src/` 零修改”描述已不再成立；生产 timeout、stop 异步返回、用户可见终态与四包契约均未改变。完整串行/n4 non-e2e 已分别以 3445 passed / 2 skipped 复验。

> 对齐: `motivation.md` 用户侧验收标准与最终 `design.md`
>
> Review round: 1（2026-07-10）

## Verdict

- **Verdict**: `pass`
- **Highest Required Action**: `pass`
- **验收口径**: 最终采用简单稳定的 4-worker 方案。真实 GitHub Actions 三次成功结果为 94/91/96 秒，未满足原始 90 秒数字；`design.md` 的 Changelog、关键决策 2、风险与回退和 Milestone 退出标准均记录了用户明确接受该例外并停止继续调参。本轮按这一最终用户口径验收。
- **Issues**: blocking 0 / major 0 / minor 0

## 用户旅程体验

### 旅程 1：合法 PR 连续获得完整成功反馈

入口为临时 [PR #184](https://github.com/Mrchen116/nano-multiagent/pull/184) 的真实 GitHub Actions。对同一 4-worker 提交连续查看三次普通 hosted runner 结果：

| Attempt | Python checks | Frontend checks | 贡献者看到的最终结果 |
|---|---:|---:|---|
| [1](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967/attempts/1) | 13:43:04–13:44:38，94 秒，success | 13:43:03–13:44:00，57 秒，success | workflow success |
| [2](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967/attempts/2) | 13:46:08–13:47:39，91 秒，success | 13:46:07–13:47:14，67 秒，success | workflow success |
| [3](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967/attempts/3) | 13:49:11–13:50:47，96 秒，success | 13:49:10–13:50:21，71 秒，success | workflow success |

Attempt 1 的用户可见输出显示 Python 仍执行完整 `pytest -m "not e2e"`，创建 4 个 worker，最终 `3444 passed, 2 skipped`；Frontend 显示 `63 passed`。两门名称和结果都保持清晰。与约 3 分 34 秒基线相比，等待时间已缩短一半以上；94/91/96 秒按最终用户决策作为 90 秒目标的明确例外接受。

### 旅程 2：现有门禁捕获失败并指出失败类别

查看真实失败 [run 29097895298 attempt 2](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097895298/attempts/2)：`Frontend checks` 为 success，`Python checks` 为 failure，workflow 整体为 failure。失败明确落在 `pytest (not e2e)` step，输出为 `2 failed, 3442 passed, 2 skipped` 并列出两个失败测试；贡献者能直接判断是 Python 测试门禁失败，而不会把失败误认成格式或前端门禁。

该 run 属于已放弃的 8-worker 探索，不是最终配置；它作为真实失败信号证明现有检查仍会标红并阻止“全绿”。最终 n4 方案恢复到三次全绿配置，相关并发敏感问题已另记 #185。

### 旅程 3：产品既有行为与最终提交范围回归

本 unit 的 Reviewer Runbook 明确以真实 Actions 为端到端入口、无需启动产品常驻服务。三次成功 run 均完成完整 non-e2e Python 套件和完整 Frontend vitest；post-review closure 只在 ShellRunner 内部 stopper 增加 monitor 完成等待，并新增对应回归测试。该 seam 不进入 `agent.sdk`，也不改变 stop/timeout、前端或任何用户可见行为。

因此本轮没有观察到 IM、Gateway、Coding CLI、agent 内核或前端用户行为被本次 CI 提速改变；该 Scenario 按 design 明确授权的替代验证口径通过。

### 旅程 4：贡献者直接重跑，无额外运维准备

Attempts 2、3 是在同一 PR 上直接 rerun 的真实 hosted runner 结果。每次均从 checkout、官方 setup action、依赖安装进入既有 Python/Frontend checks，没有人工准备专用机器、启动额外服务或改变贡献者查看 PR checks 的方式，且两次均独立完成并成功。

## Reference Artifacts Reviewed

N/A。本 unit 不涉及原型、视觉稿、reference screenshot 或前端 must-match 契约。

## 验收标准覆盖

### Requirement: 常规代码 PR 获得显著更快的完整反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 合法代码变更通过全部门禁 | `motivation.md` 目标状态与该 Scenario；`design.md` Changelog、关键决策 2、Milestone 退出标准中的最终例外 | 旅程 1：查看同一 n4 提交三次真实 hosted runner success | [run 29097094967 attempts 1–3](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967)，Python 94/91/96 秒；Frontend 57/67/71 秒；两门均 success | pass | 原始 90 秒不是事实达标；按用户明确接受的 n4 例外通过。相对约 3:34 基线已大幅提速。 |

### Requirement: CI 质量信号保持不变 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 代码违反现有检查要求 | `motivation.md` 该 Scenario；`design.md` CI 执行契约与 Reviewer Runbook step 4 | 旅程 2：查看真实失败 workflow 的 job/step/summary | [run 29097895298 attempt 2](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097895298/attempts/2)：Python checks / `pytest (not e2e)` failure；workflow failure；Frontend success | pass | 门禁失败未被吞掉，失败类别可由 job 与 step 直接识别。 |
| 产品既有行为回归 | `motivation.md` 不变性 Scenario；`design.md` Reviewer Runbook、delta-spec、Milestone 退出标准 | 旅程 3：真实 Actions 全套回归 + post-review mutation/串行/n4 复验 | n4/串行均 3445 passed / 2 skipped；Frontend 63 files passed；唯一产品源码 delta 是内部 monitor wait seam | pass | seam 不进入 SDK、不改变 stop/timeout 或用户可见终态；两处回归信号均由 mutation 证明。 |

### Requirement: 优化后的门禁不增加日常运维负担 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 贡献者重跑 CI | `motivation.md` 该 Scenario；`design.md` Reviewer Runbook | 旅程 4：观察同一 PR 的 attempt 2/3 hosted rerun | [attempt 2](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967/attempts/2)、[attempt 3](https://github.com/Mrchen116/nano-multiagent/actions/runs/29097094967/attempts/3)：标准 checkout/setup/install/test 流程，两门均 success | pass | 无专用机器、额外服务或人工预热步骤；贡献者仍使用现有 PR checks。 |

## 问题清单

原始验收轮未发现问题；后续 code review 发现的两处测试信号缺口已由 `894cf2f9` 关闭，并有 mutation red 与完整串行/n4 green 证据。

## Side Findings

- 已放弃的 n8 配置会暴露并发敏感测试；该配置未进入最终方案，已有 GitHub issue #185 跟踪，不影响最终 n4 验收结论。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；CI job 拓扑与产品架构均未变化。
- [x] `docs/specs/kernel/spec.md`、`docs/specs/im/spec.md`、`docs/specs/gateway/spec.md`、`docs/specs/cli/spec.md`：无需更新；四包均无消费者可观察行为增量，`design.md` 已记录 no spec delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；贡献者命令与 PR checks 使用方式保持不变。
- [x] `docs/SPEC_GUIDE.md`：无需更新；本 unit 未改变文档体系。
- [x] `docs/TESTING_GUIDE.md`：无需更新；门禁范围与测试分层语义未变化。

## Recommended Action

`pass`。可以进入 unit→main PR；无需 fix-implementation、revise-design 或 out-of-unit 阻断处理。
