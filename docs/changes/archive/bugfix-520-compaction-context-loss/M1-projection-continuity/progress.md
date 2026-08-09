# bugfix-520-M1 — Progress

## Baseline

- Context: unit 分支与远端同步，milestone worktree 从 `origin/unit/bugfix-520` 创建；M1/M2 范围无交叉。
- Evidence:
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_session_persistence_fidelity.py` → 20 passed。
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py` → 2 passed。

## R1 — canonical recoverable projection 与字段对称

- Context: `load()` 已按 latest boundary、active branch 和 recovery 物化消息；compaction event path 却逐 raw turn 投影，既包含废弃分支/旧 boundary 前历史，又丢失 parent/tool/group/reasoning，且没有合成 recovery result。
- Decision: 让两条读取路径共用 `_project_recoverable_messages()`；event path 先保留 compaction audit/control entries，再把 canonical Messages 对称适配为 turn events。`new_turn_appended_entry()` 与 `message_from_turn_entry()` 对称承载当前 durable Message 字段。
- Rationale: active/recovery 规则仍只有 transcript 一个 owner，planner 与 provider 不需要理解 raw JSONL schema，也不增加第三套 DTO。
- Evidence:
  - Tests: 红测在旧代码稳定显示 projected 首项仍是 `pre-user`、而 `load()` 首项是 `compact-summary`；修复后相关 persistence/transcript/planner/audit/manual compact 共 37 passed。
  - Entry: N/A；本 roadpoint 修复最低层投影 seam，真实 IM/Gateway 入口由 R2 覆盖。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/test_session_persistence_fidelity.py::test_compaction_projection_matches_latest_recoverable_transcript` 同时比较双路径语义、排除 abandoned branch，并把 normal/recovery tool pair 送入 Anthropic mapper。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 `a9b1a1885`。
- Commits: `191d34a6f`。
- Next: R2 recording fixture 与真进程 compaction/restart journey。

## R2 — recording fixture 与真进程压缩/重启旅程

- Context: 现有 fake-LLM stack 只支持固定 ACK script 和静态 usage，无法产生真实 tool use/result、只在指定响应抬高 usage、校验 summary wire shape 或控制 context window。
- Decision: 保留 `stub_llm_stack` 为唯一 IM/Gateway 生命周期 owner，只增加 recording script 文件名、额外 env 和正整数 context window 三个测试参数；专用短状态机执行 `read -> high usage -> summary validation -> continued -> restarted`。
- Rationale: E2E 仍走真 IM/Gateway、真内核事务和 Anthropic mapper，但无需真 proxy、生产 JSONL 或 200K 输入；fixture 只记录/返回当前旅程所需的最短完整结构。
- Evidence:
  - Tests: 初始红测使用旧 ACK fixture 时第一轮只返回 `ACK-1`；接线后新 E2E `1 passed in 26.46s`。
  - Entry: IM HTTP/WS 首轮真执行 `read` 并收到目标 sentinel；第二轮 recording request 收到闭合 `compaction-read-1` tool pair，IM 收到压缩后 sentinel；同 node/workspace 重启 Gateway 后第三轮再次收到 sentinel。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；该关键路径按 catalog 的产品 seam 使用 Web IM 客户端同源 HTTP/WebSocket 接口，不涉及前端渲染。
  - E2E/Regression: `tests/e2e/critical_paths/test_context_compaction_continuity_critical_path.py::test_tool_history_compacts_and_survives_gateway_restart`；同时断言 recording summary request 与隔离 session JSONL 中唯一有效 boundary/summary。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debugging: 首次接线后第二轮先观察到空 `message.completed`。边界取证显示 recording 已收到合法 summary + post-summary 请求，JSONL 已持久化 `CONTINUED ...`；根因是 compaction 期间存在一个中间 completed 帧，而测试 predicate 误把它当最终回复。最小修正为等待同 conversation 且含 sentinel 的用户可见完成帧，没有改产品逻辑或增加 sleep。
- Rollback: 回退到 `191d34a6f`。
- Commits: `be7f09779`。
- Next: R3 catalog 与 milestone 全门禁。

## R3 — catalog 与 milestone 全门禁

- Context: 真进程旅程需要进入长期 catalog 并证明共享 fake-LLM harness 没有破坏已有配置连续性和 cache 告警路径。
- Decision: v1 必保活仅新增 #16“含工具历史的上下文压缩与重启连续”，总数 14→15；删除同名 backlog，保留现有数字 identity 不重排。
- Rationale: catalog 按用户旅程计数而不是按测试函数编号；#7 仍在 backlog，因此新增旅程使用下一个稳定编号 #16。
- Evidence:
  - Tests: M1 相关 persistence/transcript/planner/audit/manual compact 37 passed；Ruff 和 `git diff --check` 通过。
  - Entry: 新 compaction E2E `1 passed in 26.46s`；既有 fake-LLM #14/#15 `2 passed in 15.12s`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 新旧三条均由真实 IM/Gateway 子进程执行；`pytest --collect-only` 收集 3 tests。fixture teardown 后 pytest runtime 内无 `.im.pid`、`.gateway.pid` 或 `.e2e-ports.env` 残留。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Docs: `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` → 220 maintained Markdown sources、67 required routes。
- Rollback: 回退到 `be7f09779`。
- Commits: 本 roadpoint commit。
- Next: rebase 最新 unit 分支，重跑门禁后合入 `unit/bugfix-520`。

## Promotion Candidates

None.
