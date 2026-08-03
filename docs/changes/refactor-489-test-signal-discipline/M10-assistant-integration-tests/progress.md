# refactor-489-M10 — Progress

## Baseline

- Claim: 清理前 M10 切片可稳定运行，后续删除/改写的差异可与同一范围对照。
- Baseline: `milestone/refactor-489-M10` rebased onto `origin/unit/refactor-489@3c6d0dd7e`（已含 M1--M9；本分支 plan commit 为 `ef7bc0982`）。
- Method: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration/background_tasks tests/integration/test_channel_bootstrap.py tests/integration/test_channel_reconcile.py tests/integration/test_channel_removal_reconcile.py tests/integration/test_foreground_single_channel.py tests/integration/test_group_mention_routing.py tests/integration/test_prompt_sections_golden.py tests/integration/test_send_message_restart_routing.py tests/integration/test_session_directory_reopen_integration.py tests/integration/test_session_run_coordinator_real_kernel.py`。
- Result: PASS；初始 base 为 `44 passed, 2 warnings in 9.50s`，M9 合入后同一 44-node 范围为 `44 passed, 2 warnings in 6.96s`；warnings 均来自 `lark_oapi` dependency deprecation。
- Locator: 本 milestone `tasks.md` 处置表与上述 pytest nodes。
- Limit: fake LLM/local SQLite/loopback HTTP/WS/local shell integration；不证明真 IM/Gateway 长驻进程、外部 Feishu、浏览器或真实 LLM。

## R1 — 删除迁移路径与低层重复

- 状态: DONE
- Context: 44 个 M10 case 混有 legacy channel bootstrap、M9 已退役的 prompt golden fixtures、直接 registry/SessionDirectory 内部测试，以及在 integration 重复 unit 解析和 FIFO 步骤的断言。
- Decision: 删除 `background_tasks/`、`test_channel_bootstrap.py`、私有 directory reopen test 与 7 个零引用 golden fixture；移除 fake websocket FIFO、纯 runtime canonicalization case；将六条 group mention 重复收敛为一个 real repository/RelayService 同名 identity 路由 case，将 13 条 prompt golden/片段断言收敛为两个 PA product→kernel assembler 输入输出 case。M10 从 44 个 case 收敛为 13 个。
- Rationale: current 风险是跨模块连接后的最终路由、通知、配置和持久结果，不是旧桥接路径、私有 submit 参数、自然语言原文或相同 parser 在更高层再测一遍。M9 合入后 `rg` 证明 golden fixture 已无测试引用，满足 orchestrator 的删除前置。
- Evidence:
  - Tests: 删除前替代保护 `tests/unit/agent/background_tasks/`、bash/task-stop、IM mention、prompt、SessionDirectory 与 PA IMConnection 共 `129 passed, 2 warnings in 3.73s`；收敛后的 M10 为 `13 passed, 2 warnings in 6.12s`；新 group/prompt case + 最低层 prompt alternatives 为 `28 passed in 0.20s`；ruff 与 `git diff --check` 通过。
  - Entry: 保留的真实 HTTP/WS channel、SQLite relay、real Kernel/local shell、loopback dispatch 与 cold restart 测试继续从公开或跨模块 seam 观察结果；本 unit 不改产品运行时。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面测试资产重构）。
  - E2E/Regression: 永久 regression 为保留的 13 个 M10 integration；真进程 background journey 仍由 M13 所有的 `tests/e2e/critical_paths/test_bash_background_notify_critical_path.py` 承担，本 milestone 不运行/修改 M13。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复原 M10 测试树与 fixtures，不影响产品代码或数据。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 去除保留测试中的私有 run registry、旧 metadata、change 叙事与无条件异步等待，只保留最终跨 seam 断言。

## R2 — 收敛当前跨 seam 保护

- 状态: DONE
- Context: 清理后的 13 个 current case 中，foreground 文件仍以历史 change 叙事解释实现，restart test 直接断言旧 session metadata，terminal-overlap test 从 `kernel._c.runs_registry._runs` 读取私有状态，foreground negative case 还靠固定 0.5 秒等待。
- Decision: foreground/background 只从 tool terminal event 与下一轮模型输入判定单/双通道，后台通知使用 condition polling；restart 只断言旧 listener 零请求、新 listener 收到消息且历史/绑定续接；terminal overlap 从公开 observer event 捕获 run identity，不再读取 Kernel 私有组件。
- Rationale: 这些最终结果正是 Gateway、Kernel、HTTP listener 与 session persistence 接缝失效后消费者会看到的症状；旧 metadata 值、registry 容器和迁移故事不是长期契约。
- Evidence:
  - Tests: 定向 foreground/restart/session 为 `7 passed, 2 warnings in 5.03s`；完整 M10 为 `13 passed, 2 warnings in 5.62s`；全部 M10 Python 文件 ruff 和 `git diff --check` 通过。
  - Entry: real `build_kernel` 执行 local shell 后从 tool event/模型下一轮输入取证；restart 用两个真实 loopback HTTP listener 证明 live endpoint；Gateway coordinator 用公开 event observer + dispatch result 证明 terminal overlap 只产生一条 fallback run。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面测试资产重构）。
  - E2E/Regression: 本 R 只重写永久 integration regression；不新增临时验收脚本。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复原断言，不影响产品实现。
- Commits: 本 R2 提交（SHA 以 Git history 为准）。
- Next: R3 rebase 最新 unit，复核 M9 golden 零引用、运行替代保护和完整收尾门禁。

## R3 — Rebase、golden 归属确认与门禁收尾

- 状态: DOING（等待 M9→M13 collection 回归修复后复验）
- Context: rebase `origin/unit/refactor-489@d0e5ea669`（新增 M8）无冲突，M10 13 nodes、替代保护、docs/ruff 均绿；扩大到完整 `tests/integration` 时 collection 在 M13-owned 文件失败。
- Decision: 不修改/绕过 M9 或 M13，不以 selected M10 绿替代 unit collection；保留失败证据并等待责任 milestone 修复合入后再次 rebase。
- Rationale: `test_foreground_interrupt_reap.py` 不属 M10，越界复制 helper 或 skip 会掩盖并行切片依赖；unit 分支必须先恢复可收集性。
- Evidence:
  - Tests: rebase 后替代保护 `129 passed, 2 warnings in 3.56s`；M10 `13 tests collected`；`scripts/docs_check.py` 为 `208 maintained Markdown sources / 65 routes`；M10 ruff 与 `git diff --check` 通过。
  - Gate hold: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration` 与 `--collect-only tests/integration/test_foreground_interrupt_reap.py` 均稳定报 `ImportError: cannot import name '_SUPPRESS_STREAM_STOP' from tests.integration.test_bash_engine`。
  - Root cause: M9 commit `8cd1d2808` 删除 `test_bash_engine.py` 的 `_SUPPRESS_STREAM_STOP` / `_collect_stream`，M13 `test_foreground_interrupt_reap.py:24-28,150,154` 仍导入/使用；这是 M9 helper 与 M13 consumer 的跨切片依赖回归，已通知 orchestrator。
- Next: 等 M9/M13 owner 修复并合入 unit；随后 rebase、重跑 M10 + alternatives + full integration + docs/ruff/diff，再完成 R3 与集成。

## Promotion Candidates

None.
