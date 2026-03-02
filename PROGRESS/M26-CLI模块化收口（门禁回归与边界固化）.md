# PROGRESS (Milestone: M26)

- Title: CLI模块化收口（门禁回归与边界固化）
- Goal: 对 M24 重构结果做收口，移除残留耦合并补齐文档与回归门禁，确保符合 CLI 边界原则。
- Exit Criteria:
  - 清理 `commands.py` 冗余桥接与死代码，形成稳定入口编排层。
  - README 与 CLI 帮助说明补齐新的模块边界与开发约定。
  - 增加/更新 contract + integration，验证 HTTP-only 边界与关键交互链路无回归。
  - `pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M26`

### Baseline
- Context:
  - execution_mode=`serial`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M26`；branch=`milestone/M26`。
  - 已读取 `LOGBOOK.md`：重点沿用“CLI 仅 HTTP 调用”“单命令 JSON 契约隔离”“错误分层稳定”规则。
  - prevention_rules：行为保持一致；CLI 仅 HTTP；单命令 JSON 契约稳定；不引入空转发层；每个 Roadpoint C1/C2/C3。
  - allowed/forbidden scope 已确认：仅改 `cli/tests/TASKS/PROGRESS/README/LOGBOOK`，不触碰 runtime/tool/session/llm 核心逻辑与 HTTP API 行为契约。
- Decision:
  - 按三条 Roadpoint 串行收口：R26.1 代码边界清理，R26.2 文档帮助补齐，R26.3 契约与链路门禁固化。
  - 使用“先红后绿+全量门禁”的 C1/C2/C3 节奏，保证可回滚与可验收。
- Rationale:
  - 收口任务以“边界稳定”优先，需要先把测试门禁写成可执行契约，再做最小改动。
- Evidence:
  - Tests: `pytest -q`（baseline：`327 passed, 4 skipped`）
  - Entry: 基线全绿，可进入 R26.1 Red。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R26.1 Red：先补“去桥接/去死代码”边界测试。

### R26.1 清理 `commands.py` 冗余桥接与死代码
- Context:
  - `commands.py` 仍暴露 `_build_repl_input_reader/_read_interactive_line` 等输入桥接符号，属于空转发耦合点。
  - unit/integration 中部分脚本化输入测试仍穿透 `cli_commands` 访问输入引擎实现，导致边界回流风险。
- Decision:
  - 移除 `commands.py` 对输入引擎函数的桥接暴露，改为在编排层内部直接使用 `repl_input.build_repl_input_reader`。
  - 测试改为直接依赖 `repl_input.read_interactive_line`，不再通过 `cli_commands` 透传符号访问。
- Rationale:
  - 输入编辑属于 `repl_input` 的稳定职责，编排层只保留“读输入并驱动流程”，可降低模块耦合与误用概率。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_refactor_boundaries.py`（桥接符号仍存在导致断言失败）
    - Gate: `pytest -q`（`327 passed, 4 skipped`）
  - Entry:
    - `commands.py` 不再导入/暴露输入引擎桥接符号，REPL 仍保持原有交互行为。
    - `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 已切换到 `repl_input` 直接调用。
- Rollback:
  - `8f22cee`（R26.1 C1）
- Commits: C1=`8f22cee`, C2=`99fb4dc`, C3=`e23a8d9`
- Next:
  - R26.2 Red：先补 CLI 帮助与 README 边界说明门禁断言。

### R26.2 README 与 CLI 帮助补齐边界约定
- Context:
  - M24 后 CLI 模块分层已成形，但 README 与 `--help` 未明确“模块职责 + HTTP-only + 单命令 JSON 契约”。
  - 缺少文案门禁会导致后续重构时边界约定被弱化。
- Decision:
  - 在 CLI help epilog 增加两条硬约束提示：`HTTP-only boundary` 与 `single final JSON object on stdout`。
  - 在 README 新增 `CLI module boundary` 小节，明确 `main.py/commands.py/repl_input.py/repl_commands.py/http_client.py` 的职责。
  - 补充开发约定：HTTP-only、避免空转发层、保持单命令 JSON 机读稳定。
- Rationale:
  - 文档与帮助文字是边界治理的第一入口，缺少显式声明会使后续协作中边界松动。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_main.py::test_cli_help_mentions_repl_editing_budget_and_error_layers tests/contract/test_cli_http_only_contract.py::test_readme_documents_cli_module_boundaries_and_json_contract`（新增文案断言失败）
    - Gate: `pytest -q`（`328 passed, 4 skipped`）
  - Entry:
    - `build_parser().format_help()` 已包含 `HTTP-only boundary` 与 `single final JSON object on stdout`。
    - README 已声明 CLI 模块职责与收口约定。
- Rollback:
  - `773846d`（R26.2 C1）
- Commits: C1=`773846d`, C2=`3ec0818`, C3=`<pending>`
- Next:
  - R26.3 Red：补 contract/integration 门禁，清理剩余命令桥接符号。

### R26.3 contract + integration 门禁固化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
