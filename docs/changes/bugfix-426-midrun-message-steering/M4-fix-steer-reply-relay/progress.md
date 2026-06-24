# bugfix-426-M4 — Progress

> #140 修复：决策5（同 run 续轮，消除 continuation 新 run_id）+ 决策6（消费点滚动气泡）+ 决策3 收窄。

## 启动澄清

- 派发包指向 design.md 的 M4 行 + 决策5/6，但主仓 cwd 的 design.md 是旧版（只有 M1/M2）；
  权威版本在 unit/bugfix-426 分支（commit de317913 `docs(bugfix-426/M4): 新增 #140 修复方案`）。
  M4 worktree 从 origin/unit/bugfix-426 创建，读到完整 M4 决策 + delta-spec。无需问 leader。
- venv：worktree 无法 editable install（pyproject 非 setuptools editable）；用 main 仓 .venv 的 pytest +
  `PYTHONPATH=src` 跑，已确认 `agent` import 解析到 worktree src。

## R1 — 决策5：loop 末轮 re-drain 续同一 run + commit_terminal 原子化

- Context: #140 根因 = steer 落在 loop 末轮已决定退出（drain 不再执行）的窗口 → stranded →
  registry `_settle_terminal_pending` 起 continuation 新 run_id → relay 锚旧 run_id 丢全部事件。
  根因在「终止决策」与「inject 入队」之间没有原子性。
- Decision:
  - `RunController` 加 `_terminal_lock` + `_terminal_committed`；`try_commit_terminal()` 持锁 re-drain：
    非空→返回待消费消息且**不** commit（run 续活）；空→set committed 返回 []。`enqueue_message` 改返
    bool：持同锁，已 commit→False 不入队。
  - `loop.py` 终止决策处（原 `if not iteration_tool_calls` 直接 break）：先 `try_commit_terminal()`，
    非空则 append 进 llm_messages + `continue`（续跑同一 run，run_id 不分裂）；空才 break。
  - 决策6 钩子：loop 在 round-start drain 与终止 re-drain 两个**消费点**都发
    `pending_injection_consumed` observe 事件（带 run_id）。realtime_stream 转发 + 事件类型注册留 R3。
  - `registry.inject_pending_message` 透传 `enqueue_message` 的 bool（lost-race→False→Gateway fallback 新 run）。
- Rationale: 在 loop 终止决策处原子「还有 pending 就再跑一轮」从源头消除 continuation 新 run_id
  （= CC 单 queryLoop「轮边界检查队列、非空继续」的等价，但保留 run_id 给多 run 源 demux）。锁让
  inject vs commit 无第三态：要么 inject 赢（续同 run），要么 commit 赢（inject=False、Gateway 开新 run + 新气泡）。
- Evidence:
  - Tests: `tests/unit/agent/runs/test_run_control_terminal_commit.py`（4 例：非空不 commit / 空 commit /
    commit 后 enqueue=False / 200 轮并发 inject-vs-commit 不变式）+ `test_agent_loop.py::test_loop_redrains_at_terminal_and_continues_same_run`（终态前 inject → 2 round 同 run 续跑、终态 answer-to-steer）。
    全绿；广测 118 passed（loop/runs/registry/runtime/cancel/contract）+ background_tasks 88 passed（enqueue 签名改动无回归）。
  - Entry: N/A（R1 内核纯逻辑；真端到端 #140 旅程在 R4 e2e + reviewer 轨）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 决策5 续同 run 的端到端验证延到 R4（需 gateway 气泡滚动一起才有用户可见结果）。
  - Visual/Interaction: N/A
- Rollback: `git revert` R1 C2 回排队/stranded-continuation 旧行为；纯加法，无数据迁移。
- Commits: C1=红测, C2=决策5 实现, C3=本次 docs。

## R2 — 决策3 收窄：continuation 仅兜异常终止

## R3 — 决策6 信号：消费点发 pending_injection_consumed → injection_consumed

## R4 — 决策6 气泡滚动 + #140 e2e
