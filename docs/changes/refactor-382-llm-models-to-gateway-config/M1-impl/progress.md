# refactor-382-M1 progress

## 启动说明

- unit branch 与 remote 同步（17ef42b6）
- 基线全绿后开始实施

---

### R0 — 基线修复（预存在 test mock 缺 reasoning_signature）

- Context: 主线上 3 个测试失败，均为 mock 类缺少 `reasoning_signature` 属性（loop.py 新增字段）以及 contract test 未同步 `Message` 新字段。这些与本 milestone 无关，但阻塞基线验证。
- Decision: 在 worktree 内修复这 3 个测试文件的 mock 类，以及 contract test 断言。同时为原始 `_CapturingContextFork` mock 缺少 `hook_ctx` 参数立 issue #55。
- Rationale: §7.2 规定测试失败必须修复不能 skip；基线红不能在红色基线上开工。
- Evidence:
  - Tests: `pytest -m "not e2e" -q` → 2365 passed, 22 skipped, 3 xfailed
  - Entry: N/A（纯测试修复）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert R0 commits
- Commits: C1+C2+C3=plan commit（含基线修复，单一 commit）
- Next: R1 新 agent.core.llm.config 模块

