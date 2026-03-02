# PROGRESS (Milestone: M20)

- Title: CLI 实时事件与输出契约收口
- Goal: 在不改内核前提下，仅通过 CLI 层完成实时事件可视化与输出契约稳定：REPL 展示中间 tool 调用过程，单命令模式保持纯 JSON 可机读。
- Exit Criteria:
  - REPL 默认使用 async events，逐步展示 run/tool/text 事件与工具输出预览。
  - 单命令 `send-message` 输出仍为单个 JSON（不混入事件行）。
  - `/v1/llm-config` 路径契约一致（CLI client 与 server 路由一致）。
  - unit + integration 覆盖上述行为，指定 test command 全绿。
- Test command: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_sdk_client.py tests/unit/test_cli_managed_server.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py`
- Branch: `milestone/M20`

### Baseline
- Context:
  - execution_mode=`serial`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M20`；branch=`milestone/M20`。
  - 已读取 `LOGBOOK.md`，本 Milestone 适用规则：外部依赖优先归因、先最小复现再扩改；LOGBOOK 仅记录可复用经验。
  - 当前 CLI REPL 仍使用同步 `send_message`，尚未消费 async run 与 SSE 事件流；单命令输出为单 JSON。
  - 当前 worktree 下不存在 `data/dev-tasks.json`（后续按主流程通过脚本更新共享派工板状态）。
- Decision:
  - 一次性拆分 3 个 Roadpoints：R20.1 先收口契约、R20.2 再上实时事件、R20.3 最后加固失败容错与回归。
- Rationale:
  - 先稳住机读契约与接口路径，再改 REPL 体验，降低“体验修复破坏脚本兼容”的风险。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_sdk_client.py tests/unit/test_cli_managed_server.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py` -> `42 passed`
  - Entry: 基线全绿，可进入 R20.1 Red。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R20.1 Red（先固化单命令 JSON 与 llm-config 路径契约）
