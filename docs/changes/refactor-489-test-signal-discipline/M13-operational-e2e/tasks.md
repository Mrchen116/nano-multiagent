# refactor-489-M13: operational-e2e — Tasks

> 对齐: ../design.md 的 refactor-489-M13 行与决策 1、2

## 目标

保留真实进程、端口/config/workspace/node identity 隔离、恢复与关键用户旅程的自动化保护；让 catalog 只引用可收集的真实 critical-path pytest node，删除退役入口、一次性 fixture 与对脚本文本、轮询次数、测试 helper 内部步骤的断言。

## 退出标准

- [ ] 真 IM + 真 Gateway 的启动、隔离、清理、重启恢复与关键用户旅程仍有实际进程证据。
- [ ] `docs/development/e2e-critical-paths.md` 的守护节点全部可由 pytest 收集；已知产品 bug #126 的 strict xfail 不被删测掩盖。
- [ ] E2E 测试层级、marker、可选依赖和 live/fake-LLM gate 与成本相称。
- [ ] 不再通过脚本文本、固定轮询次数、test helper 私有调用或退役 `--mode managed` 入口推断成功。
- [ ] M13 全域门禁与至少一条无真 LLM 的 live 真栈旅程通过；本次进程、端口和 runtime 文件已清理。

## 测试策略

- 被测行为（来自退出标准）：真实栈能在隔离端口/config/data/workspace/node identity 下启动并清理；Gateway 在 IM 瞬态故障/启动顺序变化后自动恢复 online；关键路径 catalog 节点可收集；前台子进程中断不留孤儿；session finalizer 只清理本 pytest session 的泄漏。
- 已有测试在：`tests/e2e/critical_paths/`、`tests/e2e/conftest.py`、`tests/unit/test_e2e_*`、`tests/unit/test_worktree_runtime.py`、指定 integration tests（改写/合并）；新建 `tests/e2e/test_worktree_stack_lifecycle_e2e.py`，理由：替代 unit/source-shape/down-loop 断言，从真实脚本入口观察一套栈的隔离与清理结果。
- 落层/目录/marker：真实进程落 `tests/e2e/`，由 conftest 自动加 `e2e` marker；纯 config/filesystem 规则留 unit；真实 Kernel + bash 进程树留 integration。
- 可选依赖 importorskip：critical-path WebSocket helper 保留 `pytest.importorskip("websockets")`；live proxy 路径保留显式 env + health gate；fake-LLM 与连接韧性不依赖真 proxy。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离 worktree/tmp 下 IM/Gateway PID、端口、日志、config、DB 与 workspace；以 progress 的 Claim/Baseline/Method/Result/Locator/Limit 摘要保存，runtime 文件不提交。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| catalog 中 13 条必保活用户旅程 | `tests/e2e/critical_paths/test_*_critical_path.py` 的 catalog node | keep | 真 IM/Gateway + HTTP/WS/LLM seam 的唯一黑盒保护；heartbeat #126 strict xfail 是合规活复现资产 | docs_check + collect-only + live 子集 |
| fake LLM 下配置更新后上下文连续 | `test_agent_config_context_continuity_critical_path.py` | keep | 不烧 token 但经过真 IM/Gateway 并观察上游请求与消息完成；是可稳定默认运行的真实进程路径 | 单 node + M13 全域 |
| 动态 critical agent 的模型 catalog | `test_e2e_catalog.py` | rewrite-merge | 保留纯配置 add/idempotent/error；删除读取 shell 文本判断 wrapper 接线，实际 critical wrapper/栈负责接线 | unit test + live critical collect |
| E2E helper 自测 | `critical_paths/test_im_client.py`、`test_restart_session_continuity_critical_path.py::test_restart_readiness_rejects_old_process_shutdown_heartbeat` | delete | 前者全桩且只测测试 helper；后者在 e2e 层 mock helper。实际消息历史与重启旅程已直接经过这些 helper | critical-path live nodes |
| hook loader/runner | `tests/e2e/test_hooks_pipeline_e2e.py` | delete | 未起进程、浏览器或模型，且重复 `tests/integration/test_hooks_loader_integration.py` 的 loader→runner seam；closure state 只是测试脚本自身 Python 状态 | integration owner + collect |
| Coding CLI resume 手工脚本 | `tests/e2e/termwright_repl_resume_test.sh` | delete | 硬编码主仓和 `/tmp`、调用已退役 `--mode managed`，不被 pytest/CI/catalog 消费；current CLI 入口由 M5 owner 保护 | scope search + M13 collect |
| live provider proxy smoke | `test_anthropic_generate_e2e.py`、`test_openai_compat_generate_e2e.py` | keep | 两个 provider adapter 的真 proxy 连接风险独立；不在本 unit 改动，缺 proxy 时显式 skip | collect + 可用时 live gate |
| worktree 栈隔离与清理 | `test_gateway_im_resilience_e2e_wrapper.py` 的 prepare/yq/source tests、`test_e2e_down_script.py`、`e2e-up/down.sh` | rewrite-merge | 删除 test-only prepare、脚本文本和固定 25 次 sleep；新 e2e 从脚本入口观察 PID/port/config/static+dynamic workspace/credential cleanup | 新 lifecycle e2e |
| Gateway-IM 瞬态恢复 | `test_gateway_im_resilience_critical_path.py`、`e2e-resilience.sh`、wrapper timeout unit | rewrite-merge | 保留真进程两场景；删除 wrapper 私有调用/monkeypatch 测试，以 live resilience + session finalizer 保证失败可收口 | resilience live node |
| session 结束兜底进程清理 | `tests/e2e/conftest.py`、`test_e2e_conftest_finalizer.py` | rewrite-merge | 风险真实，但旧测试直接 import/call 私有 helper，且 scanner 会误杀并发 pytest session；改为 nested pytest 生命周期黑盒并限定本 session basetemp | finalizer black-box regression |
| worktree shared lock/private data | `test_worktree_runtime.py` | rewrite-merge | 保留 public filesystem 结果；合并 idempotency 到真实转换场景，去掉历史 milestone 目录名 | unit test |
| foreground interrupt 进程树 | `test_foreground_interrupt_reap.py` | rewrite-merge | 保留真 bash child 被回收、run cancelled、同 session 自愈；删除高层重复的 JSONL recovery 实现与 CC 逐字文本断言 | integration test |
| protocol fixture | `tests/fixtures/gateway_runtime_protocol.json` | keep | 被 IM protocol contract 直接消费，是 schema 输入而非一次性证据 | consumer contract / tracked-reference search |
| HTTP/fault fixtures | `scripts/fixtures/*.py`、`README.md` | rewrite-merge | 保留当前 fake-LLM critical path实际消费的 recording stub；删除 5 个只在 README 手工说明、无自动消费者的一次性交付 fixture | tracked-reference search + fake-LLM live node |
| 端口/catalog/关键栈脚本 | `free-ports.sh`、`e2e_catalog.py`、`e2e-critical.sh`、`e2e-up/down/resilience.sh` | keep | 是真实栈与 catalog 的可执行入口；只删测试专用 prepare 分支和历史噪声，不替换当前入口 | shell syntax + real invocation |

## Roadpoints

### R1 — 删除退役、错层与一次性测试资产

- 状态: DONE
- 步骤: 删除 retired managed-mode Termwright、全桩 helper/mislayered hooks 测试和未消费 fault fixtures；保留其 current owner 或真实旅程。
- 验证: reference/search 对账；collect-only、相关 integration/fake-LLM node 通过。

### R2 — 用真实栈结果取代脚本文本与轮询实现断言

- 状态: DONE
- 步骤: 新增 worktree stack lifecycle e2e，观察进程、端口、config/static+dynamic workspace/credential 与 down 后清理；删除 source scan、prepare-only、固定 poll-count guard，并移除已修复的主目录 workspace 清理。
- 验证: lifecycle e2e 真进程通过，down 后 PID/端口/runtime secret 均释放。

### R3 — 收敛 finalizer 与 interrupt 的进程所有权保护

- 状态: DOING
- 步骤: finalizer 限定当前 pytest basetemp，改为 nested pytest 黑盒；worktree unit 合并；foreground interrupt 只守进程/终态/自愈结果。
- 验证: 新 finalizer regression、worktree unit、foreground integration 通过，无测试进程残留。

### R4 — catalog、全域与 live 证据收口

- 状态: TODO
- 步骤: 校验 catalog 引用节点可收集；运行 M13 全域、ruff/shell/docs/scope；真跑 fake-LLM context continuity、Gateway-IM resilience 与 stack lifecycle，确认清理。
- 验证: 所有门禁通过，progress 记录 live evidence 与环境限制。
