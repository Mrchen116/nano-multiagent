# refactor-489-M2 — Progress

## Baseline

- Context: M2 清理 contract 与 CI/quality gate，不能在已有失败上判断测试价值。
- Decision: 先在 `unit/refactor-489` 的 M1 集成基线 `8d6cfb3e8` 上运行整个派发切片。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract tests/unit/test_docs_check.py tests/unit/test_agents_md_loader.py tests/unit/test_change_spec_author_next_unit_id.py` → `236 passed, 2 warnings`。
  - Entry: `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed: 190 maintained Markdown sources, 65 required routes`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: N/A；本 milestone 零产品行为与常驻服务。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: N/A（尚未修改实现）。
- Commits: N/A。
- Next: R1 Contract 架构 seam 收敛。

## R1 — Contract 架构 seam 收敛

- 状态: DONE
- Context: contract 树同时包含 current public/schema/import 保护和迁移终态、私有源码/文件布局扫描；删除前必须证明真实风险仍在最低 seam 被保护。
- Decision: 共享 AST helper 只解析真实 absolute import，四个 current 边界文件分别拥有 SDK、顶层包、core 与 platform 依赖；删除 10 个历史/内部布局 contract，移除 cron 文件位置、SDK cron-name negative 与旧 prompt-seed 档案测试；capability baseline 改名并重写为 current wire contract。
- Rationale: import AST、公开 SDK/协议调用和所属域行为测试会在风险发生时直接失败；已删除路径、私有属性、源码字符串、整棵目标树和行号白名单只会让等价重构变红。个人助手 packaging 继续检查 pyproject build 声明；首轮尝试导入 `setuptools.find_packages` 稳定复现 `.venv` 无 setuptools 的 collection error，系统化定位到 setuptools 仅为 PEP 517 build 依赖而非 dev/runtime 依赖，因此没有扩大运行依赖，回到 declarative build seam。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract` → `135 passed`；受影响 contract 最窄集合 → `36 passed`。
  - Entry: 当前 import 边界由 `tests/contract/import_rules.py` 经 AST 验证；SDK/schema/capability/package/cron 直接调用公开 seam，无产品入口变化。
  - Frontend State Matrix: N/A（非前端变更）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 替代保护 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/agent/session/test_session_directory.py tests/integration/test_session_directory_reopen_integration.py tests/unit/personal_assistant/test_gateway_build_runtime.py tests/im_service/unit/test_event_repository_queries.py tests/im_service/integration/test_user_stream_auth.py` → `29 passed`；`npm run test -- --run src/realtime/user-stream/user-stream.test.ts` → `17 passed`。这些证明被删源码扫描对应的 session/Gateway/IM/user-stream 风险仍由行为 seam 保护。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 R1 提交，计划提交 `9298b0e42` 保持不变。
- Commits: 本提交，SHA 以 Git history 为准。
- Next: R2 收敛 workflow/template/docs catalog/test-file/CI/hook quality gate。

## R2 — CI 与 quality gate 收敛

TODO

## R3 — 切片回归与证据闭环

TODO

## Promotion Candidates

None.
