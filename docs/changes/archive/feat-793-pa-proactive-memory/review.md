# Validation Review — feat-793-pa-proactive-memory

- status: approved
- validated_at: 80a3c3a804ec78f32ef8db59d4faed5b1680a25e

## Scope

- Change unit: `feat-793-pa-proactive-memory`（Personal Agent 主动性记忆偏好校准与反馈演化闭环）
- Branch: `unit/feat-793-pa-proactive-memory`（forked from `unit/feat-785-pa-proactivity` @ `3499b08b6`）
- Design baseline: `a813cd916`
- Validated implementation range: `a813cd916..80a3c3a80`

## Validation Summary

| Gate | Mode | Verdict | Notes |
| --- | --- | --- | --- |
| `change-code-review` | Independent subagent (Round 1 -> Round 2 closure) | **Approved** (`0 blocking / 0 warning / 0 nit`) | Round 1 发现 `1 blocking`（`B1` 离线 `TaskContext.sync` 先于 `relay.message` 抵达时的共享群输入审核闭环）、`1 warning`（`W1` 非创建者其他 Agent 变更 `proposed` 卡的中性文案）及 `2 nit`（`N1` `Dreaming.status` 去重对齐、`N2` 目录级搜索隔离与 `saveRun` 落盘裁剪），均在 `80a3c3a80` 完整修复并通过 Round 2 复审确认关闭；3 份 `delta-spec` 全部 `aligned`。 |
| `agent-context-review` | Independent subagent (`implementation` mode on real 5-day wire payloads) | **Pass / Approved** (`0 blocking / 1 warning / 2 nit`) | 亲自核验源码与 5 日真实模型联调 99 条请求载荷：PA 主会话首轮稳定装载 `## 主动性与介入偏好`、跨 5 日同窗口 `{system, tools, messages[0..1]}` 前缀 SHA-256 零漂移（实测缓存命中稳定）、`03:45` `proactive_nightly` 通过 `<updated-formal-memory>` 即时感知当夜 `03:10` Dreaming 变更、`knowledge/proactivity-signals.md` 前台与夜间筹划零泄漏、三道归因护栏实证自洽；所提目录级 `grep`/`glob` 穿透 `warning` 已在 `80a3c3a80` 一并加固关闭。 |
| Automated unit, runtime & contract suites | Local deterministic verification | **Passed** | `@nano/im-server`、`@nano/personal-assistant`、`@nano/dsh-integration`、`@nano/node` 全量构建通过；相关 17 个 Vitest 测试文件（151+ 用例）、`tests/contract/test_runtime_dependency_contract.py`（13 passed）与 `./scripts/docs-check` 全部通过。 |
| Isolated 5-day real-LLM E2E (`daily` profile + logical clock) | End-to-end behavioral & wire verification | **Passed** | 在独立临时栈（`codexOAuth:gpt-6.2-sol` + 逻辑时钟跨 5 自然日推进）完整跑通：Day 1 显式双周盯紧规则与 `21:30–08:30` 免打扰时机护栏当夜入驻 `MEMORY.md` 四桶且不误封 Q4 复盘目标；Day 2 零聊天纯点击「不采纳」唤醒 Night 2 Dreaming 记入 `proactivity-signals.md`（`seen: 1`）且不提前封杀；Day 4 第 2 次纯点击「不采纳」唤醒 Night 4 Dreaming 升格入 `### 免打扰禁区` 并清空观察池；Night 5 面对第 3 个同类健康打卡点子保持 0 提议卡、0 夜间打扰并正常推进 Q4 复盘与 `09:00` 早间汇总；验证结束后临时栈进程、端口与目录完整回收。 |

## Findings Closure Log

| ID | Source Gate | Severity | Summary & Resolution | Status |
| --- | --- | --- | --- | --- |
| `B1` | `change-code-review` R1 | `blocking` | 离线追赶下 `TaskContext.sync` 先于实时 `relay.message` 入库时未打 `personal_unclassified: true`。已在 `TaskContext.sync` 对个人主体非 `revoked` 通知暂存待审，并在 `prepare()` 与 `peekPendingForDreaming()` 返回前经 `GlobalAgent.settleSyncedTaskContext` 执行 `personal.admit` + `flushPendingReviews`，补齐离线注入拒绝回归测试。 | `closed` (`80a3c3a80`) |
| `W1` | `change-code-review` R1 | `warning` | 非创建者的其他协作 Agent 关闭 `proposed` 卡时仍输出人类裁决文案。已在 `task-notifications.ts` 限定仅人类操作者输出 `未采纳 / 暂存待定 / 已批准`，其他 Agent 采用中性 `从待拍板转为...`，且创建者自流转在所有状态分支清理自身关注避免自循环。 | `closed` (`80a3c3a80`) |
| `CW1` / `N2` | `agent-context-review` & `change-code-review` R1 | `warning` | 目录级 `grep`/`glob` 搜索记忆库可能返回 `proactivity-signals.md` 匹配项。已在 `DocumentMemory` 的 `tools/execute` 拦截提及该文件的非 Dreaming `bash` 命令，并在工具渲染前从覆盖该路径的 `grep`/`glob` 结构化结果（`matches`/`paths`）中剥离 `proactivity-signals.md`，同时在 `Dreaming.saveRun` 清空持久副本的 `pendingTaskContext[].text`。 | `closed` (`80a3c3a80`) |
| `N1` | `change-code-review` R1 | `nit` | `Dreaming.status` 未向 `sources.freeze` 传入 `excludeTaskContextIds`。已补齐传入，与 `Dreaming.execute` 去重口径完全一致。 | `closed` (`80a3c3a80`) |

## Delta-Spec Alignment (`corrected-delta`)

- `specs/gateway/agent-capabilities.md`: `aligned`
- `specs/gateway/personal-agent.md`: `aligned`
- `specs/im/task-graphs.md`: `aligned`
