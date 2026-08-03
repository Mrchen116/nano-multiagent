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

- 状态: DONE
- Context: E2E session finalizer 旧实现以宽泛的 `pytest-of-*/pytest-N/` 正则扫描所有 pytest 临时目录，两个并发会话会互相 SIGKILL Gateway；对应 6 个 unit tests 直接 import 私有 helper。worktree runtime 测试绑定历史 milestone 名，foreground interrupt 在真实进程结果之外还扫描 JSONL 私有 recovery entry 与逐字内容。
- Decision: 用 nested pytest 黑盒回归启动“本 session leak + 另一 session Gateway marker”，先复现旧 finalizer 误杀，再将 owner 限定为 `tmp_path_factory.getbasetemp()`；保留 leak 回收但验证另一会话仍存活。worktree runtime 把幂等性并入本地 lock-dir 转换行为；foreground integration 只验证真 bash child 消失、run cancelled、同 session 下一轮 completed。
- Rationale: finalizer 是失败路径安全网，必须以当前 session 的 runtime root 建立所有权，不能把“看起来像 pytest 路径”当全局处置权限；中断的运营风险是孤儿进程和 session 不可恢复，内部 JSONL 形状与特定文案由更低层 owner 负责。
- Evidence:
  - Tests: 新 regression 在修复前稳定失败于“one E2E pytest session killed another session's Gateway process”，修复后连同 worktree runtime、foreground interrupt 共 `4 passed`（1.46s）。
  - Entry: nested pytest 真实触发 session teardown；foreground test 经真实 in-process Kernel 启动带唯一 argv marker 的 `sleep` 并调用公开 `kernel.interrupt`。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（进程生命周期路径）。
  - E2E/Regression: 当前 session 的 Gateway marker 被 finalizer 回收，另一 pytest basetemp 下 marker 保持存活并由测试自身清理；中断后无 marker PID 残留。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交，恢复 R2 提交 `ee57bcb49` 的 finalizer 与 integration guards。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R4 真跑 resilience/lifecycle/fake-LLM，校验 catalog、全域门禁和 runtime 清理。

## R4 — catalog、全域与 live 证据收口

- 状态: DONE
- Claim: 精简后的 operational E2E 仍从公开脚本/API 跑真实进程，覆盖 worktree 隔离与清理、Gateway-IM 瞬态恢复、fake-LLM 消息上下文连续；catalog 引用均是当前可收集 pytest node。
- Baseline: R3 提交 `6cd54055a`；本机 `127.0.0.1:4000/health` 不可连接，因此 18 个真 provider/LLM 项保持显式 skip，没有把不可用环境伪报成通过。
- Method: 分别真跑 resilience、stack lifecycle、fake-LLM critical node；再运行全部 `tests/e2e` 加指定 unit/integration owner、全 E2E collect-only、`docs_check.py`、全域 ruff、所有 `e2e-*.sh`/`free-ports.sh` 的 `bash -n`、diff check、runtime 文件和进程扫描。
- Result:
  - Live resilience: `test_gateway_recovers_node_online_after_transient_faults` `1 passed`（22.53s）；真实覆盖 IM online → kill/restart → Gateway 自动恢复，以及 Gateway 先起/IM 后起。
  - Live lifecycle + fake LLM: `2 passed`（11.71s）；真实观察 IM/Gateway PID、端口、隔离 config/node/workspace/DB、动态 Agent 落盘、down 后释放，以及两轮消息跨配置更新仍进入同一上游上下文。
  - M13 full: `9 passed, 18 skipped`（13.09s）；skip 均为显式 live proxy gate。
  - Catalog/docs: E2E `20 tests collected`（其中 critical paths 17 nodes）；`documentation integrity passed: 212 maintained Markdown sources, 65 required routes`，13 条 v1 catalog 引用可解析，heartbeat #126 strict-xfail node 保留。
  - Static/cleanup: scoped ruff、shell syntax、`git diff --check` 全通过；worktree 根无 PID/ports/config/secret residue，进程表无指向本 milestone worktree 的 IM/Gateway 进程。
- Locator: 自动守护在 `tests/e2e/test_worktree_stack_lifecycle_e2e.py`、`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py`、`tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py`；catalog 权威为 `docs/development/e2e-critical-paths.md`。
- Limit: 本次没有真跑需要本地 LLM proxy 的 token 消耗路径；它们仍可收集且保留显式 health gate。无真 LLM 的三条真栈路径已满足本 milestone 的 live 退出标准。
- Rollback: 回退本 roadpoint 提交；R1-R3 的独立提交仍可分别保留或回退。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: 同步最新 unit branch 后重跑 M13 关键门禁，合并 milestone 分支并清理 worktree/临时分支。

## Promotion Candidates

None.
