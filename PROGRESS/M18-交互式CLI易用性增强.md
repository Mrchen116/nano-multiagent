# PROGRESS (Milestone: M18)

- Title: 交互式 CLI 易用性增强
- Goal: 在 M17 基础上增强交互可用性，补齐历史/错误提示/输出体验，使 CLI 可日常使用。
- Exit Criteria:
  - 支持 `/history [n]` 查看最近会话消息（最简文本视图）。
  - `/tools` 与 `/compact` 输出人类可读摘要，错误提示包含可操作建议。
  - 支持空输入忽略、Ctrl-D 退出、命令参数错误提示。
  - 关键交互路径 unit + integration 覆盖，`pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M18`

### Baseline
- Context:
  - 已按要求先读取 `LOGBOOK.md`；当前仅记录可复用规则，不记录过程性实现细节。
  - 执行模式：`serial`；`use_worktree=false`；分支：`milestone/M18`。
  - 允许范围：`src/nano_multiagent/cli/**`、`src/nano_multiagent/sdk/**`、`tests/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`（仅新增可复用规则时）。
  - 禁止范围：`ROADMAP.md`、`data/dev-tasks.json`（仅可用脚本更新）。
  - 预防规则：命令错误提示必须给可执行建议；每个 Roadpoint 必须 C1/C2/C3；不做超出 M18 的架构重写。
- Decision:
  - 一次性拆分 3 个 Roadpoint：R18.1 history 视图、R18.2 摘要与错误体验、R18.3 交互鲁棒性收口。
- Rationale:
  - 先补核心功能（history），再统一可读输出与错误建议，最后补齐鲁棒性测试，降低返工概率。
- Evidence:
  - Tests: `pytest -q` -> `236 passed, 3 skipped`
  - Entry: 基线全绿，可进入 Red 阶段。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R18.1 Red

### R18.1 `/history [n]` 最近会话消息视图
- Context:
  - M17 REPL 尚无历史查看入口，用户无法回看当前会话最近消息。
  - 本 Roadpoint 仅在 CLI 本地增强，不改服务端接口。
- Decision:
  - 在 REPL 中引入按 `session_id` 维护的本地历史缓存（`user`/`assistant`）。
  - 新增 `/history [n]`：默认窗口 `20`，支持 `n` 指定最近条数，输出最简文本行。
  - 发送消息后记录 user 输入与 assistant 回复内容；`/new`、`/use` 复用会话隔离历史。
- Rationale:
  - 不依赖后端新增消息查询接口即可满足“最近消息可查看”，实现最小、风险最小。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py` -> 2 failed（`/history` unknown command）
    - Green: 同命令 -> `8 passed`
    - Gate: `pytest -q` -> `238 passed, 3 skipped`
  - Entry:
    - `/history` 与 `/history 2` 可输出 `History for session ...` 及 `role: content` 行。
- Rollback:
  - `b6ac8ae`（R18.1 C1）
- Commits: C1=`b6ac8ae`, C2=`a82a5c9`, C3=`<pending>`
- Next:
  - R18.2 Red
