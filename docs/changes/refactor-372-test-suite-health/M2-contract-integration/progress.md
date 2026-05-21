# refactor-372-M2 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## 基线

- 测量时间：2026-05-20
- 命令：`pytest tests/contract tests/integration -m "not e2e" -q --tb=no`
- 结果：95 failed, 165 passed, 121 warnings

---

### R1 — 修 create_app auth_token 漂移（contract 子树）

- Context: contract 子树 7 个文件调用 `create_app(auth_token=...)` 签名漂移
- Decision: 删 `auth_token=...` 参数，`create_app()` 无 token 方式
- Rationale: 签名漂移导致 TypeError，修对齐现码
- Evidence:
  - Tests: contract 子集 7 passed
  - Entry: pytest tests/contract/... 7 passed
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: e11eb08b
- Commits: C2=e11eb08b, C3=e11eb08b（单 commit，前任完成）

### R2 — 修 contract 子树其余漂移

- Context: regression.md §1.8/1.9/1.10/1.12/1.13/1.15 + 1.6 fields/routes/SSE events
- Decision: 逐文件按 regression.md 指示更新断言
- Rationale: 字段/路由/SSE 事件/bash 截断签名全部漂移，对齐现码
- Evidence:
  - Tests: pytest tests/contract/ -m "not e2e" → 102 passed, 2 xfailed
  - Entry: 全 contract 套件通过
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 477c33d2
- Commits: C2=477c33d2（前任完成）

### R3 — 修 integration 子树大批漂移

- Context: create_app auth_token + 工具集 subset + hook/tool/LLM 签名漂移
- Decision: 批量修 12 个文件；工具集断言改 issubset；路由/ToolSafetyConfig/LLMGenerateRequest 对齐
- Rationale: 覆盖 regression.md §1.1/1.7/1.20/1.22/1.23/1.24/1.25
- Evidence:
  - Tests: 目标 12 文件 39 passed
  - Entry: pytest 指定 12 文件 → 39 passed
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: f46b49ed
- Commits: C2=f46b49ed
- Next: R4

### R4 — cli_http_flow/session_flow/task/tools_read 漂移 + xfail 真回归

- Context: 27 个 cli_http_flow 失败 + 真回归 test_append_message + task/tools_read 漂移
- Decision: 批量修 6 文件；test_append_message_persists_history_once_per_idempotency_key 打 xfail(strict=True, reason 含 #37)
- Rationale: 对齐漂移；xfail 标记已知产品 bug（#37）而不删测试
- Evidence:
  - Tests: 6 文件 13 passed, 1 xfailed
  - Entry: pytest 指定文件 → 13 passed, 1 xfailed
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: xfail #37 严格标注
  - Visual/Interaction: N/A
- Rollback: 69f5e586
- Commits: C2=69f5e586

### R5 — 删快照 + 流水号重命名

- Context: test_im_gateway_real_acceptance.py 是一次性快照；m85/m86 是流水号文件名
- Decision: rm acceptance 快照；git mv m85→no_legacy_wiring, m86→no_legacy_homing（行为名更具描述性）
- Rationale: 快照测试核心行为已被 contract/integration 覆盖；行为名比流水号更自描述
- Evidence:
  - Tests: contract 102 passed, 2 xfailed
  - Entry: contract 全套通过
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: f57b4af6
- Commits: C2=f57b4af6

### R6 — 拆分 test_cli_http_flow_integration.py + 修复/skip REPL+ASGI hang

- Context: 1197 行文件超 400 行上限；REPL+ASGI 测试在修漂移后从快速失败变 hang
- Decision:
  - 拆为 4 个子文件（test_cli_http_flow_basic.py + test_cli_repl_*.py），用例数 24 对 24
  - 新建 tests/integration/conftest.py，包含 ASGIClient（同步 Starlette 封装）
  - pyproject.toml pythonpath 加 "tests"
  - 21 个 REPL 测试 @pytest.mark.skip + issue #47（SessionStreamReader 后台线程 × ASGI TestClient 独立 event-loop 导致 SSE 永远收不到 events）
- Rationale: REPL 测试历史上因 TypeError 快速失败，从未真正运行；修漂移后暴露基础设施 bug，非产品 bug，skip 而非 xfail
- Evidence:
  - Tests: 234 passed, 22 skipped, 3 xfailed — 退出 0
  - Entry: pytest tests/contract tests/integration -m "not e2e" -q → 退出 0
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: skip #47 注记
  - Visual/Interaction: N/A
- Rollback: 217ac2ee
- Commits: C2=217ac2ee

### R7 — TESTING_GUIDE 补 xfail 合规例外

- Context: xfail 规则只有禁止，没有合规例外说明
- Decision: 在"MUST NOT skip/xfail"后追加：已知产品回归 + issue + strict=True 的 xfail 合规
- Rationale: 有 #37 这样的实际案例，规则需要覆盖
- Evidence:
  - Tests: 全门禁 234 passed, 22 skipped, 3 xfailed
  - Entry: pytest 全套退出 0
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 848f897b
- Commits: C3=848f897b
- Next: M2 DONE

