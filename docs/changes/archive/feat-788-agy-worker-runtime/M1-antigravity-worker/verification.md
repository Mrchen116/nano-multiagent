# M1-antigravity-worker Verification Evidence

- **Unit**: `feat-788-agy-worker-runtime`
- **Branch / Base**: `unit/feat-788-agy-worker-runtime` (merge-base `origin/develop` `4ff83afda`)
- **Host / CLI**: macOS, `/Users/czj/.local/bin/agy` (`Antigravity ACP Server 1.5.16`), Node `v25.8.2`, pnpm `11.7.0`

## 1. Build, Typecheck & Narrow / Contract Tests

在专属 worktree 根目录执行：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全仓编译与类型检查 | `pnpm build && pnpm typecheck` | Pass（0 errors） |
| 独立工具与架构/测试大小契约 | `pytest -m "not e2e" -q`（含 `test_runtime_dependency_contract.py` 与 `test_test_naming_and_size_contract.py`） | `136 passed` |
| 后端窄单测与集成测试 | `pnpm exec vitest run apps/node/tests/configuration.test.ts packages/dsh-integration/tests/local-worker-conformance.test.ts packages/dsh-integration/tests/local-worker-drivers.test.ts packages/dsh-integration/tests/local-worker-antigravity.test.ts packages/dsh-integration/tests/local-worker-manager.test.ts packages/personal-assistant/tests/inbox.test.ts apps/im-server/tests/e2e/work-summaries.test.ts` | `7 passed (61 tests)` |
| 前端 Work 与展示组件测试 | `cd src/IM/frontend && npx tsc -p ../../../packages/product-contracts/tsconfig.json --typeRoots ./node_modules/@types && npx vitest run src/features/settings/agents/agent-work-panel.test.tsx src/features/settings/agents/agent-work-presenters.test.tsx src/features/chat/components/agent-activity-popover.test.tsx` | `3 passed (59 tests)` |

覆盖要点：
- `gateway.worker_runtime` 支持 `dsh` / `codex` / `claude` / `antigravity` 并拒绝未知枚举；
- `cliWorkerRuntimes` / `workerRuntimes` 统一驱动 `work-event-codec`、`LocalWorkers`（含 `isWorker` 为 `true` 以保持长期记忆与原生子轨迹隔离）、`inbox.ts` 删除清理排除、`work-records.ts` 明细准入与前端 `Antigravity` 框架显示；
- ACP 握手、强制 `session/set_mode('auto')`（缺失 `auto` 或未登录时快速报错并回收 `TMPDIR`）、`nano-parent` MCP `send_message` 白名单放行、越界动作缓存合并与工具名/`kind`/参数脱敏拒批（含真实 `File <path>` 标题下的 `write_file` / `edit` 识别）、`interaction_` 提问取消回报、`ask_question` 跨轮迟到 `tool_call_update` 隔离、运行中二次 `session/prompt` steer 早结与乱序异常收敛、部分请求缺失 `usage` 时不伪报半截 `total_tokens`/`cache_*`、`refusal` 映射 `failed`、以及前端 `WorkUsage` 上下文窗口展示。

## 2. 本机真实 `agy 1.5.16` 端到端与 Context 实测

通过真实 `openCliWorker({ runtime: 'antigravity', ... })` + `workerReportBridge` Unix socket MCP + `WorkRecords` SQLite 投影驱动本机已登录 `/Users/czj/.local/bin/agy`（`1.5.16`）执行实测取证（最新复测 Session `8455281a-ab00-48a4-96e6-7a4e7043b579`，时间 `2026-11-25T10:00:06Z`–`10:01:02Z`；前序 `ask_question` 单轮行为核实 Session `9c854ef7-8bd0-4e47-91ef-ac08043879b5`）：

1. **环境净化、新建会话、`nano-parent` MCP 白名单与记忆解耦（Session `8455281a-ab00-48a4-96e6-7a4e7043b579`）**：
   - 父进程预设 `SSH_CONNECTION`、`SSH_TTY`、`BROWSER=/usr/bin/false` 时，子进程环境实测已剔除 `SSH_*` 与 `BROWSER`，设置 `AGY_CLI_DISABLE_AUTO_UPDATE=true`、`NO_COLOR=1` 及独立 `nano-agy-tmp-*` `TMPDIR`；`agy` 正常读取宿主机系统登录态且未拉起浏览器。
   - `initialize` 返回 `_meta.antigravity.systemPrompt.append: true` 与 `sessionCapabilities.resume: {}`；`session/new` 通过 `_meta.antigravity.systemPrompt.append` 注入固定内部 worker 说明并挂载唯一 MCP `nano-parent`，随后调用 `session/set_mode({ modeId: 'auto' })` 将初始 `default` 切换为 `auto`（默认模型 `gemini-4-neon`）。
   - Turn 1 读取工作区 `ledger.txt` 并调用 `mcp_nano-parent_send_message`：ACP 发出 `session/request_permission`（`id: "jetski-acp-front:2"`, `title: "Run mcp_nano-parent_send_message"`），驱动自动选择 `allow_once`，父级 Unix socket 收到 `"Progress: read ledger.txt"`；最终回答 `sum=42, rule=FEAT_788_WORKSPACE_RULE, memory_injected=no`，确认工作区 `AGENTS.md` 生效且未注入 Nano `MEMORY.md`。
   - `worker1.close()` 后，`os.tmpdir()` 中本次创建的 `nano-agy-tmp-*` 目录数从 `1` 立即归 `0`。

2. **原会话 `session/resume` 续做、MCP 新 socket 重绑、越界写拒绝脱敏与 `ask_question` 收尾**：
   - 使用新 `workerReportBridge` socket 对原 `sessionId`（`8455281a-...`）调用 `openCliWorker`，`session/resume` 返回相同 `sessionId` 并再次强制切换 `modeId: 'auto'`。
   - Worker 在不重读 `ledger.txt` 的情况下记住前序 `alpha=17`，经新 socket 成功调用 `mcp_nano-parent_send_message` 送达 `"Resumed: alpha=17"`。
   - 尝试向工作区外临时路径调用 `write_file`（含测试敏感正文 `"SECRET_PROBE_788"`，ACP 原始 `title` 为 `"File ../nano-feat788-shim-LTUETD/outside-workspace-probe.txt"`）时，驱动立即回复 `reject_once`；目标文件未写入，父级收到清晰含动作名与类别的脱敏回报：`Antigravity declined write_file. {"kind":"edit","input":{"Path":"/Users/czj/.../outside-workspace-probe.txt"}}`，正文 `"SECRET_PROBE_788"` 未泄露且无重复路径噪音。
   - 调用原生 `ask_question` 时（Session `9c854ef7-...`），问题与选项随 `agent_message_chunk` 返回且工具在当轮结算时闭合，下一轮首帧迟到的同 `toolCallId` 更新被隔离，未污染后续轮次。

3. **活跃轮次 `stop()` 中断与 IM `WorkRecords` 上下文/Token 投影**：
   - Turn 3 执行中调用 `worker2.stop()` 发送 `session/cancel`，`agy` 返回 `{ stopReason: "cancelled" }`（不含 `usage`），轮次以 `interrupted` 结束且 `usage: null`（计入 `missing_turns: 1`）；`worker2.close()` 后 `nano-agy-tmp-*` 目录再次归 `0`，无残留 `agy acp --process-per-session` 进程。
   - 真实事件写入 `WorkRecords` 后，`delegation` 节点显示 `runtime: "antigravity"`、`has_work_records: true`、累计 `usage: { total_tokens: 67386, reported_turns: 2, missing_turns: 1 }`；已完成轮次保留真实上下文与缓存指标（Turn 1：`context_used: 16819`, `context_window: 1048576`, `output: 488`, `cache_read_tokens: 28282`, `cache_total_input_tokens: 49087`, `total_tokens: 49575`；Turn 2：`context_used: 17811`, `context_window: 1048576`, `output: 650`, `cache_read_tokens: 14650`, `cache_total_input_tokens: 17161`, `total_tokens: 17811`）。

## 3. 临时资源回收状态

- 实测创建的临时工作区（`nano-feat788-live-ws-*`）、shim 目录（`nano-feat788-shim-*`）、MCP Unix socket 目录（`nano-w-*`）及 `agy` 解压目录（`nano-agy-tmp-*`）均已回收删除；`ps` 核实无残留子进程。
- 最新脱敏 ACP 原始帧记录与事件快照保存在会话暂存目录（`scratch/live-agy-acp-wire.jsonl`、`scratch/live-agy-captured.json`），供独立审查直接核对，不进入 Git 仓库。
