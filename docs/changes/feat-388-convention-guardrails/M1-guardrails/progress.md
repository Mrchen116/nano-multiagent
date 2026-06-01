# feat-388-M1 — Progress

## R1 — pyproject.toml 加 ruff 配置

- Context: 项目无任何 lint/format 工具，需新增 ruff 配置作为 B-1/B-2 规则的单一真源
- Decision: 在 pyproject.toml 加 [tool.ruff] target py311 + [tool.ruff.lint] select F/B006/E722 ignore B008；dev 依赖加 ruff==0.15.*；per-file-ignores 处理 tests/ 放宽和 F821 forward-ref 豁免
- Rationale: B008（FastAPI Depends/Query）107 处误报排除（决策 D4）；F821 为 string annotation forward ref 模式（循环 import 避免），ruff 不识别；bridge 导入文件（commands.py）需具名豁免
- Evidence:
  - Tests: `ruff check .` 全绿 / `ruff format --check .` 全绿
  - Entry: N/A（配置文件，无运行时入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert 3475b492`
- Commits: C2=b75f971e (ruff 配置), C2+=3475b492 (per-file-ignores 补充)

## R2 — 全仓存量违规清理（独立机械 commit）

- Context: 存量 441 文件需格式化，src/ 下 10 处不可自动修违规需手动处理
- Decision: `ruff format .` + `ruff check --fix .` 一次性清存量；手动修 F841/F811/F401/F821；更新契约测试行号白名单；恢复 bridge 导入
- Rationale: 机械重排独立 commit 便于 review 和回滚（格式噪声与逻辑改动分开，决策 D5）；bridge 导入被 ruff autofix 误删（F401），需恢复并加 per-file-ignore
- Evidence:
  - Tests: `pytest -m "not e2e"` 2341 passed，1 个无关基线失败（test_dispatch_handler_build_aiohttp_handler_returns_callable）
  - Entry: N/A（机械重排，无业务逻辑改动）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert 2e2c490b`
- Commits: C2=2e2c490b

## R3 — 契约测试复核（R1/R2/R3 状态确认）

- Context: refactor-387 已落地，需确认契约测试状态
- Decision: 两个契约测试文件已在 refactor-387 中完成改写（R1 新语义 + R3 正向断言，无 xfail），本 milestone 无需额外改动
- Rationale: 直接确认状态即可，不重复改动
- Evidence:
  - Tests: `pytest tests/contract/ -m "not e2e"` 97 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 97 个契约测试全通过
  - Visual/Interaction: N/A
- Rollback: N/A（本 roadpoint 无改动）
- Commits: N/A

## R4 — stop-require-explicit-ok.py 自门控改造

- Context: disableAllHooks=true 翻转后会激活此 hook，需确保普通会话不被干扰
- Decision: 新增自门控：检查 session 是否在 active-subagents.json 中有登记（orchestrator 受管会话标识），无登记则 exit 0 放行
- Rationale: "有登记" = orchestrator 通过 SubagentStart hook 写入的 session，保证只有受管会话进入 gate 逻辑；普通编码会话零影响（决策 D2）
- Evidence:
  - Tests: 逻辑 review + orchestrator 实测确认（team-lead 在 unit 分支上亲自运行 hook）：无登记 session → exit 0（普通会话正常停止）；空 session（session_id 存在但 agent_ids 为空）→ exit 0（同样放行）；有登记 active=0 → block；有登记 active>0 → exit 0。实测结论：普通会话可正常停止，gate 行为仅作用于 orchestrator 受管会话。
  - Entry: orchestrator 实测通过（非仅代码 review）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（行为/逻辑改动，但 hook 自身无单测）
  - Visual/Interaction: N/A
- Rollback: `git revert 8dca8b8d`
- Commits: C2=8dca8b8d

## R5 — ruff-guardrail.py PostToolUse hook

- Context: 触点 (a) 需要在 Edit/Write 后即时 autofix + 回喂不可修违规；边界违规需即时反馈
- Decision: 新建 ruff-guardrail.py；对 src/|tests/ 下 .py 文件依次跑 ruff format/check --fix；用 returncode 判断是否有余下违规（不用 stdout）；src/ 下额外跑边界契约测试；settings.json 加 PostToolUse[Edit|Write] + disableAllHooks: false
- Rationale: returncode 比 stdout 可靠（ruff "All checks passed!" 会输出 stdout 但 exit 0）；边界契约测试 AST 扫描极快（0.4s）
- Evidence:
  - Tests: 实测 1 - 含 F401 文件 → exit 0（自动修）；实测 2 - 加 import agent.core → exit 2 + stderr 含 ruff 违规 + 契约测试失败详情
  - Entry: 手动实测 hook 脚本（见 Evidence Tests）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（hook 行为通过手动实测验证）
  - Visual/Interaction: N/A
- Rollback: `git revert 9a4b8ad3`
- Commits: C2=9a4b8ad3

## R6 — GitHub Actions CI

- Context: 触点 (c) 需要 push/PR 时前后端双门兜底，现状无任何 CI
- Decision: 新建 .github/workflows/ci.yml：python job(py3.11 + ruff check/format --check + pytest -m "not e2e") + frontend job(Node20 + npm ci + npm run test)，并行，任一红阻止合并；前端不跑 npm run build
- Rationale: 两 job 并行缩短等待时间、失败定位明确；Node 20 满足 vitest3+jsdom27 要求；不引入 tsc 类型检查（与 Python 侧不做 mypy 对称，决策 D3）
- Evidence:
  - Tests: yaml 结构 review 正确；前端基线确认 345 passed；python 侧 ruff+pytest 全绿
  - Entry: CI 在 PR push 后远端执行（本地 yaml lint 通过）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（CI 本身由 GitHub 执行，merge 后在 PR 上可观察）
  - Visual/Interaction: N/A
- Rollback: `git revert 3dbd86d7`
- Commits: C2=3dbd86d7

## 最终状态

- `ruff check .` 全绿
- `ruff format --check .` 全绿
- `pytest -m "not e2e"` 2341 passed（1 个无关基线失败保持不变）
- `cd src/IM/frontend && npm run test` 345 passed 全绿
- PostToolUse hook 实测：F401 自动修（exit 0）+ import agent.core exit 2 回喂
- stop-require-explicit-ok.py 自门控：普通会话放行，受管会话 gate 不变
- .github/workflows/ci.yml 两 job 并行，前端不含 tsc
