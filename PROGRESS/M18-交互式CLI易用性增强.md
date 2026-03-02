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
- Commits: C1=`b6ac8ae`, C2=`a82a5c9`, C3=`821d4a1`
- Next:
  - R18.2 Red

### R18.2 `/tools` 与 `/compact` 可读摘要 + 可操作错误提示
- Context:
  - 当前 `/tools` 与 `/compact` 直接打印 JSON，交互性弱；命令错误仅有原始报错，缺少下一步建议。
  - 需保持 HTTP API 调用语义不变，仅增强 CLI 交互输出层。
- Decision:
  - 增加统一错误输出函数：`Error: ...` + `Suggestion: ...`，覆盖无会话、缺参、未知命令、请求失败。
  - 将 `/tools` 改为文本摘要（会话 + 数量 + 工具列表）。
  - 将 `/compact` 改为文本摘要（无变化或 compacted 结果摘要）。
  - REPL 命令集合契约更新为包含 `/history`。
- Rationale:
  - 输出层增强可显著降低日常使用成本，同时避免改动后端契约带来的集成风险。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_main.py tests/contract/test_cli_http_only_contract.py tests/integration/test_cli_http_flow_integration.py` -> 3 failed（摘要与建议未实现）
    - Green: 同命令 -> `12 passed`
    - Gate: `pytest -q` -> `239 passed, 3 skipped`
  - Entry:
    - `/tools` 输出 `Tools for session ...` 和 `- <tool>: <description>`。
    - `/compact` 输出 `Compaction for session ...`。
    - `/unknown`、`/use` 缺参、无 active session 均输出 `Suggestion` 行。
- Rollback:
  - `a5f39c2`（R18.2 C1）
- Commits: C1=`a5f39c2`, C2=`af90901`, C3=`<pending>`
- Next:
  - R18.3 Red
