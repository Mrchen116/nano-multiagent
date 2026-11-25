# feat-788-agy-worker-runtime: Review

## 范围与版本

- 本次问题与需求/设计位置：`spec.md`、`design.md`、`specs/gateway/global-agent.md`、`specs/gateway/tool-approval.md`、`specs/im/agent-work.md` 及 `M1-antigravity-worker/verification.md`
- 实际 executed_base / validated_at：
  - `executed_base`: `4ff83afda84a2ba67047524cb559e8b2f8655fb1` (`origin/develop`)
  - Round 1 `validated_at`: `54daf6be88be72a782d36b7dacc54153f69d737e`
  - `pre_fix_head`: `54daf6be88be72a782d36b7dacc54153f69d737e`
  - Round 2 `validated_at`: `4550b5e9efda3f073e47f362ac3c628b425e55cf`
- 最终 effective_base / effective_through 与保留依据：`effective_base = 4ff83afda84a2ba67047524cb559e8b2f8655fb1`（`origin/develop` 无新增提交），代码与测试实现冻结于 `effective_through = 4550b5e9efda3f073e47f362ac3c628b425e55cf`；其后仅执行 canonical spec 归并、本报告落盘与 change unit 归档移动，不改变运行时或前端行为。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 配置枚举收敛、跨包导入边界、ACP 进程生命周期、`auto` 强校验、白名单放行、权限/提问缓存合并脱敏、steer 早结与乱序收敛、单路径非空统计、`TMPDIR` 回收及前端展示 | `change-code-review` · 独立审查者 `Gate 4 Code and Context Reviewer` (`17522ffd-d611-4b98-9f08-b62c2c07f739`) · Round 1 `full` (`4ff83afda..54daf6be8`) + Round 2 `patch` & `closure` (`54daf6be8..4550b5e9e`) | `pass` | 全量通读 31 个变更文件与调用方，独立运行 `local-worker-{drivers,antigravity,conformance,manager}.test.ts`（`4 passed / 18 tests`）、`test_runtime_dependency_contract.py` + `test_test_naming_and_size_contract.py`（`15 passed`）与 `./scripts/docs-check`；Round 1 检出的 F1–F3 在 `4550b5e9e` 全部 `closed`，patch 无新增缺陷；全仓后端 258 套单测与前端 129 套单测验证通过。限制：本机 `agy` 版本为 `1.5.16`，旧版无 `_meta.antigravity.systemPrompt.append` 降级分支与 `interaction_*` 权限分支由协议单测覆盖。 |
| 3 份 delta-spec 与 current specs、相邻 `no spec delta` 文档及最终实现/测试的一致性 | `change-code-review` · 独立审查者 `Gate 4 Code and Context Reviewer` (`17522ffd-d611-4b98-9f08-b62c2c07f739`) · `corrected-delta` | `pass` (`aligned`) | 合读 `specs/gateway/global-agent.md`、`specs/gateway/tool-approval.md`、`specs/im/agent-work.md` 与对应 `docs/specs/` 及声明 `no spec delta` 的 `agent-capabilities.md`、`service-lifecycle.md`、`ios-client.md`、`response-metrics.md`；F1/F2 修复后最终实现、测试与契约承诺完全对齐（`aligned`）。 |
| Antigravity Worker 与父 Global 的角色提示词注入、`nano-parent` MCP 工具面、长期记忆隔离与越界拒批/提问回报语义清晰度 | `agent-context-review` · 独立审查者 `Gate 4 Code and Context Reviewer` (`17522ffd-d611-4b98-9f08-b62c2c07f739`) · `实施模式`（Round 1 全量 + Round 2 拒批回报 delta） | `pass` | 独立审查者亲自通读真实 `agy 1.5.16` 原始往返帧（`scratch/live-agy-acp-wire.jsonl` Session `73ee5484-...` 第 1–60 帧、复测 Session `8455281a-...` 第 1–58 帧，并独立补跑只读 `ask_question` 探针 Session `b635ff55-...`）及 `scratch/live-agy-captured.json` 全文：确认新建与 `session/resume` 均注入精炼角色说明、仅暴露 `nano-parent` `send_message`、剥离 `SSH_*`/`BROWSER`、保留工作区 `AGENTS.md` 且隔离 Nano `MEMORY.md`/Dreaming；复测第 51–52 帧与 `reports2[1]` 确认越界写拒批回报为 `Antigravity declined write_file. {"kind":"edit","input":{"Path":"..."}}`，动作与类别清晰、敏感文件内容已剥离且无重复路径噪音。 |

## Findings 与关闭

- **F1 (`CONFIRMED`, `warning`) — 越界权限拒批回报忽略 `toolCall.name` 与 `kind`，在真实 `agy` 文件操作上退化为 `File <path>`**
  - 位置：`packages/dsh-integration/src/local-workers/drivers.ts` (`session/request_permission` 拒批分支)
  - 触发条件与影响：真实 `agy 1.5.16` 对文件工具发送 `title: "File <相对路径>"`（同时携带 `name: "write_file"`、`kind: "edit"`），旧实现仅读取 `title` 且未输出 `kind`，使拒批回报丢失读写动作区分且路径重复三次。
  - Resolution（`4550b5e9e`）：按 `rawCall.name ?? rawCall.toolName ?? cached?.name` 优先提取真实工具名，详情附带 `kind` 与脱敏 `input`，并在单路径与主路径一致时去重 `locations`；补齐 `local-worker-antigravity.test.ts` 回归与真实 `agy 1.5.16` 复测。
  - 独立关闭依据（`closed` @ `4550b5e9e`）：审查者核读 `drivers.ts:727-808`、`local-worker-antigravity.test.ts:35-41,94-100` 及真实轨迹 `live-agy-captured.json` `reports2[1]`，确认输出 `Antigravity declined write_file. {"kind":"edit","input":{"Path":"..."}}` 且敏感正文未泄露。

- **F2 (`CONFIRMED`, `warning`) — 二次 `session/prompt` steer 轮次中尾请求缺失 `usage` 时将前序早结请求的局部 token/cache 误报为整轮完整 `usage`**
  - 位置：`packages/dsh-integration/src/local-workers/drivers.ts` (`freshStats` / `buildTurnUsage` / `send`)
  - 触发条件与影响：steer 首请求带 `usage` 早结而续发请求因 `session/cancel`、`refusal`、RPC 错误或进程退出无 `usage` 结束时，旧逻辑仍写出首请求的局部 `total_tokens`/`output`/`cache_*`，掩盖下游 `missing_turns`。
  - Resolution（`4550b5e9e`）：新增 `settledPrompts` 与 `allPromptsReportedTokens`，任一已结算请求缺 token、报错或在途退出时置 `false`，仅当 `inFlightPrompts === 0 && settledPrompts > 0 && allPromptsReportedTokens` 时写出 `output`/`total_tokens`/`cache_*`；新增 `local-worker-antigravity.test.ts` steer 取消回归测试。
  - 独立关闭依据（`closed` @ `4550b5e9e`）：审查者核读 `drivers.ts:629-675,704-708,995-1064` 并运行 `local-worker-antigravity.test.ts:176-182` 通过。

- **F3 (`PLAUSIBLE`, `warning`) — 运行中 steer 双请求受 `rpcId !== latestPromptId` 与 `inFlightPrompts > 0` 双重门控，乱序失败/返回时可能导致轮次不收尾**
  - 位置：`packages/dsh-integration/src/local-workers/drivers.ts` (`send`)
  - 触发条件与影响：若续发请求 `P2` 先于 `P1` 拒绝或返回（或 `sendRequest` 抛错），两侧回调分别因 `inFlightPrompts > 0` 与 `rpcId !== latestPromptId` 早退，导致轮次无法调用 `events.end`。
  - Resolution（`4550b5e9e`）：移除 `rpcId !== latestPromptId` 早退判断，使用 `highestSettledId` 记录最新请求终态 `outcome`，统一由 `finishIfDrained(turnId)` 在 `inFlightPrompts === 0` 时唯一下发 `events.end`；新增乱序报错回归测试。
  - 独立关闭依据（`closed` @ `4550b5e9e`）：审查者核读 `drivers.ts:677-690,983-1041` 并运行 `local-worker-antigravity.test.ts:183-188` 通过。

当前存活 findings：**无存活 findings（0 open）**。

## 流程收口

- 重要目标和关键设计覆盖：`spec.md` 与 `design.md` 全部目标、关键决策及 M1 退出标准均已实现并经单测、契约测试与本机真实 `agy 1.5.16` 验证覆盖。
- 开放问题 / pending / inconclusive：0 项。
- 最终 delta 校对（适用时）：`aligned`（`docs/specs/gateway/global-agent.md`、`docs/specs/gateway/tool-approval.md`、`docs/specs/im/agent-work.md` 已按校正后的 delta-specs 归并）。
- 版本变化后保留 / 补验的判断与依据：全量实现与专项复验在 `4550b5e9efda3f073e47f362ac3c628b425e55cf` 通过；后续提交仅包含 canonical spec 归并、本 `review.md` 与 `docs/changes/archive/` 归档移动，经 `./scripts/docs-check` 与 `check_change_unit_archived.py` 校验，前序代码与 Context 审查结论保持有效（`retained`）。
- 测试资源回收结果 / 例外保留项、owner 与回收触发（适用时）：全部临时工作区、MCP socket 目录、shim 目录、`nano-agy-tmp-*` 解压目录及测试子进程已回收清零；开发 worktree `/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-788-agy-worke-553f266333579ba9` 按仓库规则保留至 PR 合入 `develop` 后由执行合并或接手后续工作的 Agent 清理。
- 交付范围与剩余事项：归档 `feat-788-agy-worker-runtime`、推送 `unit/feat-788-agy-worker-runtime` 并创建指向 `develop` 的 PR，等待远端 CI 与人工审阅合并。
