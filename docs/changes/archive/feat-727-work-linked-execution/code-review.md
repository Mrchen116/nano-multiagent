# feat-727: Code Review

## Review scope

- Base / executed_base: `70d781d6197ccc918dd943f4743df5fe3bfc3719`。
- Head / validated_at: `1edf0c00148a7fe301334d6572a0679199d55ba4`。
- Review mode: `full`。
- Included commits: `cd7f7f62d8e55a7943740f3d5150022a7b1bfe90`、`1edf0c00148a7fe301334d6572a0679199d55ba4`。
- Included uncommitted files: 无；派发时工作树 clean。
- 独立 reviewer: `code_review`（Codex `gpt-6.1-sol` / `high`，未参与实现），执行 `change-code-review`。

## Round 1

- Result: Passed。
- Findings: `[]`。
- 范围：完整 7 文件差异，包含源码、CSS、测试和快速开发 unit 文档。
- 核对：消息使用各自真实来源，工具与后台结果入口位于卡片内且不受明细折叠控制；操作与折叠按钮为兄弟，既有导航、关联匹配和权限不变。
- Context 判断：仅人类阅读 UI，无模型可见 Context 生命周期影响，不触发完整 Context Review。
- Resolutions: 无阻塞项、无需修复。
- 复用证据：32 项相关测试和 frontend build；reviewer 未重复运行，也未执行真实后台或生产验证。

## Closure

- Follow-up mode: N/A；没有 finding 或源码修复。
- Remaining findings: None。
- Final result: Passed。
- 后续变更限定为已审 delta 的 canonical 归并、area 索引计数、整套 unit 移入 archive 和本审查/检查记录；由主会话核对精确内容与文档检查，不扩展为新实现。
- 用户确认沿用：main 同步只增加聊天占位消息恢复，Work 源码和预览补丁不变；本轮未改变用户已确认的可观察结果。

## 本地检查与交付覆盖

检查执行于 Node 24.22.1，代码树为 `1edf0c001` 至 `36e21cbf0`；两者之间只有已审 delta 的 canonical 归并与审查记录，没有源码或测试变更。

| 检查 | 结果 |
|---|---|
| Work panel / presenter 最窄反馈 | 2 文件、32 tests 通过 |
| 前端完整 `npm --prefix src/IM/frontend test` | 113 文件、1,078 tests 通过 |
| 前端 `npm --prefix src/IM/frontend run build` | TypeScript 与 Vite 构建通过 |
| `npm --prefix src/IM/frontend audit --audit-level=critical` | 通过，无 critical；既有较低等级依赖报告不属于本次改动 |
| `pnpm build` / `pnpm typecheck` / `pnpm check:ios-runtime` | 均通过 |
| `pytest -m "not e2e" -q` | 135 passed、28 deselected |
| `ruff check .` / `ruff format --check .` | 均通过 |
| `scripts/docs-check` | canonical 归并后通过；归档后再次核对 |

### 后端套件的失败与复跑

初次 `pnpm test` 与前端完整检查同时运行，多个 DSH 集成用例发生超时/失败。该运行被中止，保留原始日志；中止后的 6 个本任务孤立 DSH 子进程已核对并停止。

其他检查结束后执行 `pnpm test --maxWorkers=2`，未修改用例或超时标准，结果为 **214 文件通过、1 文件失败；1,169 tests 通过、1 test 失败**。失败为 `packages/dsh-integration/tests/global-child-tools.test.ts` 中 `single_thread` 冷恢复用例，后代记录返回 `diagnostic/unavailable`，断言期望 `child`（79 行），不是本次前端断言。

随后单独执行：

```bash
pnpm exec vitest run packages/dsh-integration/tests/global-child-tools.test.ts -t single_thread
```

结果 **1 passed、5 skipped**，耗时 2.98s；跳过的是同文件中不匹配过滤条件的其他用例，它们已在完整运行中通过。没有代码变化。`git diff --exit-code origin/main -- apps packages evals package.json pnpm-lock.yaml vitest.config.ts` 通过，确认相关后端源码、测试与基线完全一致。

这证明失败在单项复跑中没有稳定复现；资源竞争和后代读取时序是调查方向，尚未证明根因，也没有声称修复了后台缺陷。保留失败与复跑两份证据，不将这次全量结果改写成一次全绿。远端完整 CI 的状态与固定 head 记录在 PR Validation Summary。

### 最终有效范围

- effective_base: `70d781d6197ccc918dd943f4743df5fe3bfc3719`；最终 fetch 后核实 main 未推进。
- 审查实际执行于 `1edf0c00148a7fe301334d6572a0679199d55ba4`；原始用户确认基于 `84eb50074` 的示例预览，rebase 后实现补丁经逐字比较相同。
- 后续仅 canonical 精确归并、索引派生计数、检查记录与整个 unit 归档；独立代码审查和用户确认保留有效。
- effective_through 的最终准确提交 SHA 在 PR Validation Summary 固定；此报告的结果回填和路径归档不改变受审源码。
- 本机日志：`~/.codex/reports/work-linked-execution-475/` 下 `backend-tests.log`、`backend-tests-limited.log`、`backend-cold-resume-replay.log`、`frontend-tests.log`、`frontend-build.log`、`backend-build.log`、`backend-typecheck.log`、`ios-runtime.log`、`python-tests.log`、`ruff-check.log`、`ruff-format.log`。
- 生产未部署；预览服务已停止，开发 worktree 按开放 PR 的规则保留。
