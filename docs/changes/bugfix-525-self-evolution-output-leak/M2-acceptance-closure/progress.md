# bugfix-525-M2 — Progress

## Baseline

- Branch / commit: `milestone/bugfix-525-M2` / `639a5813cb9d17d7cd43c60c51864ca11e76aa84`。
- Context read: `incident.md`、`design.md`、`design-review.md`、全部 delta-spec、Round 1 `regression.md`（R1-I1/R1-I2）、current Gateway/IM contracts、testing/evidence/worktree-runtime/critical-path 规范与现有 fixture/helpers。
- Tests:
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m 'not e2e'` → `3193 passed, 26 deselected, 22 warnings in 170.03s`。
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -m e2e tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py::test_agent_config_update_keeps_chat_context_with_stub_llm` → `1 passed in 8.03s`。
- Scope guard: M2 只建立 acceptance harness / runbook / E2E；M1 production classification、source marker、persistent unique owner 与 structured notice schema 均不修改。

## R1 — controlled no-save 真栈

- Context: Round 1 reviewer 能看到 raw 文本缺席，却无法证明 no-save review 真执行；验收还必须经过真 IM + production Gateway，而不是把 integration test 当产品证据。
- Decision: 新增 stateful OpenAI-compatible HTTP fixture；routing 只使用显式 scenario、非 classifier request 序号、message roles 与 tool result ids。fixture 的 `/state` 只提供 branch-independent 正向执行事实，用户可见结果仍从 IM REST/WS 断言。
- Rationale: fixture-owned 正向事实解决“没执行”和“执行但私有”不可区分；不新增 production debug/telemetry，也不读取 private review prompt 文案。
- TDD / debug:
  - Red 1: fixture 缺失，E2E 在 setup 明确失败：`missing fixture script: scripts/fixtures/openai_self_evolution_recording.py`。
  - Green attempt 1: 前台完成但 fixture 仅收到 1 个 request，30 秒内无 review。系统化取证：isolated session JSONL 的 metadata 已正确含 `memory_nudge_interval: 1`，但 runtime 的 `turn_count` 在 run 开始前从既有 history 统计；首轮为 0。既有 Kernel integration 同样用两个 foreground replies 触发 memory review。根因是 harness 错把首次 turn 当 nudge=1，不是 M1 路由缺陷。
  - Root fix: no-save scenario 先完成 seed turn，再在第二个 foreground turn 后进入 review；没有改生产代码或放宽等待窗。
- Evidence:
  - Tests: 新 no-save E2E + 既有 controlled Anthropic E2E → `2 passed in 15.10s`; changed-file Ruff 与 `git diff --check` 通过。
  - Entry: 真 IM HTTP/WS 发两条用户消息；第二条 foreground `FOREGROUND-NO-SAVE-COMPLETE` 以 `delivery_status=completed` 完成；fixture state 出现 `no_save_review_completed`；IM 历史只有两条 foreground Agent 消息与一条 structured memory system notice，`Nothing to save.` / `Traceback` 为 0。
  - Frontend State Matrix: N/A（无客户端变更）。
  - Browser QA: N/A（无 UI 变更；产品入口为 Web IM 使用的同一公开 REST/WS relay）。
  - E2E/Regression: `tests/e2e/critical_paths/test_self_evolution_visibility_critical_path.py::test_no_save_review_stays_private_after_foreground_completion`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 会同时移除 fixture 与对应 critical-path test，不影响 M1 production behavior。
- Commits: `fix(bugfix-525/M2/R1): 建立 no-save 确定性真栈验收`。
- Next: R2 在同一 fixture/真栈上加入 terminal gate、真实 Skill create 与 replay fault。

## R2 — terminal 后 Skill create + replay + 新 session 使用

- Status: TODO

## R3 — reviewer 入口、清理与质量门禁

- Status: TODO

## Promotion Candidates

None.
