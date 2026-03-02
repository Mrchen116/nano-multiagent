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
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R26.2 README 与 CLI 帮助补齐边界约定
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

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
