# refactor-489-M13 — Progress

## Baseline / Audit

- Claim: M13 派发域在正确 worktree venv PATH 下可稳定收集/运行，并已定位退役入口、错层 helper 自测、脚本文本/轮询次数断言、并发误杀风险和无自动消费者的一次性 fixtures。
- Baseline: `origin/unit/refactor-489@52af340769`（初始测试基线在同步前 `ce66aa759`，其后仅吸收相邻 milestone）。
- Method: 完整读取 motivation/design/M1 处置规范、testing/worktree-runtime/e2e catalog 与 Gateway current specs；枚举 49 个 M13 tracked paths；运行 scoped pytest 与 collect-only；搜索 script text/private/test-import/retired mode/fixture consumers。
- Result: PATH 按文档加入主仓 `.venv/bin` 后 PASS：`23 passed, 18 skipped`（41 collected）；默认 skip 为显式 live-proxy gate。首轮未带该 PATH 时 fake-LLM fixture 因 `python3` 缺 PyYAML 报错，属已纠正的运行环境前置条件，不是测试回归。
- Limit: 基线未启动 `:4000` 真 LLM proxy；fake-LLM 真栈已执行。R4 将另跑不依赖真 proxy 的 lifecycle 与 resilience live paths。

## R1 — 删除退役、错层与一次性测试资产

- 状态: DONE
- Context: `tests/e2e/` 混有不启动任何外部资源的 helper/hook 自测，另有一个硬编码主仓、固定 `/tmp` 且调用退役 `--mode managed` 的手工 Termwright 脚本；5 个 fault fixture 只被自己的 README 描述，没有 current 自动消费者。
- Decision: 删除 Termwright、hook/helper/restart-mock 测试；hook loader→runner 由现有 integration owner 保留，IMClient/restart helper 由真实 critical journeys 消费；fixtures 只保留 fake-LLM context continuity 实际使用的 recording Anthropic stub，并把 README 收敛到该 owner。
- Rationale: 测试 helper 自身与任意 Python closure 不构成产品 E2E；不被 pytest/CI/catalog 消费且绑定退役入口或单次故障注入的脚本是历史验收资产，不应永久占据测试树。真实用户风险仍由 live critical nodes 与 current integration owner 保护。
- Evidence:
  - Tests: catalog unit + hooks integration + fake-LLM 真栈 node `5 passed`；critical-path collect-only `17 tests collected`；ruff/diff check 通过。
  - Entry: fake-LLM node 经 `e2e-up.sh` 启动真 IM/Gateway、从 IM 发两轮消息并观察 `message.completed` 与上游 request；删除项没有 current 可执行入口。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: `test_agent_config_update_keeps_chat_context_with_stub_llm` 真栈通过；17 个 catalog/critical node 仍可收集。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复 plan `833e160e4` 的测试树。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 建立真实 worktree stack lifecycle E2E，替代脚本文本、prepare-only 与固定 poll-count 断言。

## R2 — 用真实栈结果取代脚本文本与轮询实现断言

- 状态: DONE
- Context: 旧 guard 通过读取 `e2e-up/down.sh` 文本、测试专用 `--prepare-only` 分支、mock wrapper 私有函数和“5 秒必须恰好 sleep 25 次”来推断运维结果；同一 fixture 还保留了已被 `node.workspace_base` 修复的主目录 Agent 清理逻辑。
- Decision: 新增 `test_worktree_stack_lifecycle_e2e.py`，实际运行 up/down：观察 IM/Gateway PID、OpenAPI/监听端口、随机 node identity、隔离 DB、preset/dynamic Agent workspace 与 channel credential，并在 down 后验证 PID/端口/config/secret/credential 释放；删除旧 source/poll/prepare guards。所有子进程 fixture 以 active `sys.executable` 的 venv 作为 PATH，去掉主目录 workspace 删除与全局 agent-id 追踪。
- Rationale: up/down 的价值是“真实栈可用且资源归还”，不是 shell 如何循环；动态 Agent 真落入 worktree 比搜索 yq 字符串更能证明隔离。修正 venv PATH 也让 fake-LLM node 不再依赖调用者手工 export PATH。
- Evidence:
  - Tests: lifecycle 真栈 `1 passed`（5.17s）；不额外设置 PATH 的 fake-LLM context node `1 passed`（6.49s）；changed files ruff、4 个 shell `bash -n`、diff check 通过。
  - Entry: `scripts/e2e-up.sh --wt <pytest tmp>` 启动真 IM/Gateway；经 IM HTTP 新建动态 Agent，返回 workspace 位于 `.gateway-workspace`；`e2e-down.sh` 后进程、监听端口和敏感 runtime 文件均消失。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（API/进程级运维路径）。
  - E2E/Regression: `tests/e2e/test_worktree_stack_lifecycle_e2e.py` 与 fake-LLM critical path 均真跑通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复 R1 提交 `90d7c9288` 的 harness。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R3 把 session finalizer 改成当前 basetemp 的 nested-pytest 黑盒，并收敛 interrupt/worktree unit 断言。

## R3 — 收敛 finalizer 与 interrupt 的进程所有权保护

- 状态: DOING

## R4 — catalog、全域与 live 证据收口

- 状态: TODO

## Promotion Candidates

None.
