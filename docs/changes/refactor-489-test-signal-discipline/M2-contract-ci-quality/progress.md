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

- 状态: DONE
- Context: docs catalog 曾把标题措辞和 prose 计数当成 CI 契约，workflow/template tests 固定整句或链接数量，新增测试 gate 在拿不到 `origin/main` 时静默返回空集合，ruff hook 只覆盖部分 current import 边界。
- Decision: E2E catalog 只按五列结构寻找表格并验证行/schema/pytest node，不读标题或重复 count；workflow 以语义关键词与对应 table rows 对账，PR 模板提取所有 change links 验证 blob 形态；测试命名检查覆盖全树，大小 gate 以 merge-base 比较并在 base 缺失时大声失败；Python CI checkout 获取完整 history，hook 使用自身解释器运行四个 import contract。
- Rationale: 这些 gate 现在各自对应一个可执行风险：悬空 E2E node、workflow consumer 漂移、PR 相对链接、低质量新增测试、真实 import 违规。重写标题、增加模板链接或缺失 Git ref 不会再被误判为成功或无关回归。
- Evidence:
  - Tests: 修改前 `test_e2e_catalog_accepts_collectable_full_and_shorthand_node_ids` 以 `E2E_CATALOG_TABLE: missing '## v1 必保活路径' section` 稳定失败；修改后 quality focused suite `17 passed`。
  - Entry: `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed: 192 maintained Markdown sources, 65 required routes`；真实 CLI 入口消费重写后的 checker。
  - Frontend State Matrix: N/A（非前端变更）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: `NANO_TEST_BASE_REF=refs/heads/refactor-489-missing-base ...::test_new_test_files_under_400_lines` → pytest exit `1`，保留 Git fatal 证据，证明 gate 不再静默跳过；ruff hook JSON 入口针对 `src/agent/core/ids.py` → exit `0`，实际运行四个 import contract。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 R2 提交；R1 contract 清理提交 `bde3f62e3` 可独立保留。
- Commits: 本提交，SHA 以 Git history 为准。
- Next: R3 运行完整 M2 门禁、核对 scope 与处置闭环。

## R3 — 切片回归与证据闭环

- 状态: DONE
- Claim: M2 已逐项处置派发范围内的 contract 与 CI/quality gate；保留项只保护 current 公开/schema/import/文档/构建或可执行质量 seam，删除项不再把迁移终态、私有源码步骤、历史整句与行号白名单当回归信号。
- Baseline: `unit/refactor-489@8d6cfb3e8` 的派发切片为 `236 passed, 2 warnings`；M2 计划、R1、R2 提交依次为 `9298b0e42`、`bde3f62e3`、`39bd7553e`。
- Method: 按 tasks 处置表逐文件审计；用 `origin/unit/refactor-489...HEAD` 列出 tracked diff 并逐路径匹配派发 allowlist；运行完整 M2 pytest、真实 docs CLI、ruff check/format、ruff hook JSON 入口与 `git diff --check`。
- Result:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract tests/unit/test_docs_check.py tests/unit/test_agents_md_loader.py tests/unit/test_change_spec_author_next_unit_id.py` → `170 passed`。
  - Entry: `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → `documentation integrity passed: 192 maintained Markdown sources, 65 required routes`；ruff hook 针对 `src/agent/core/ids.py` → exit `0`。
  - Quality: ruff check → `All checks passed!`；ruff format → `40 files already formatted`；`git diff --check` → exit `0`。
  - Scope: diff allowlist 审计 → exit `0`，无越界路径；10 个低信号 contract 删除、1 个 capability contract 改名、真实 import/quality seam 改写均已列入 tasks 处置表。
  - Frontend State Matrix: N/A（零 UI 行为变化）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: R1 已运行 session/Gateway/IM focused tests `29 passed` 与 user-stream Vitest `17 passed`；本轮完整切片覆盖最终回归。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Locator: `tests/contract/import_rules.py`、四个 import-boundary contract、`scripts/docs_check.py`、test naming/size contract、CI checkout 与 ruff hook；完整文件处置见 `tasks.md`。
- Limit: 本 milestone 不修改产品运行时、public API 或 current spec；没有需要 live service/browser 验收的行为面。CI workflow 仅在 PR runner 上最终执行，本地以同一 pytest/docs/ruff/hook 入口验证。
- Rollback: R3 仅补齐说明与证据；按 `39bd7553e`（R2）、`bde3f62e3`（R1）、`9298b0e42`（plan）逆序回退可恢复基线。
- Commits: 本提交，SHA 以 Git history 为准。
- Next: 同步最新 `origin/unit/refactor-489`，重跑门禁后合并并 push unit 分支。

## Promotion Candidates

None.
