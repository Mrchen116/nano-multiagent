# refactor-489-M9 — Progress

## R1 — 删除历史和重复断言

- 状态: DONE
- Context: M9 基线 11 文件共收集 32 个 case；其中 idle 文件复制生产格式化逻辑而不调用生产入口，kernel skeleton 文件锁定旧迁移 golden 字节，bash signal、read truncation、registry validation 已有更低层同路径保护。
- Decision: 删除 3 个低信号文件和 4 条 unit/contract 重复用例，同时移除仅服务被删断言的 fixture/import；M9 收集数从 32 降为 18。
- Rationale: 永久 integration 资产应只为跨 seam 的独立风险付费；实现复制品、迁移终态和下层已拥有的细节不增加回归信号。
- Evidence:
  - Tests: 删除前 M9 基线 `32 passed in 9.01s`；删除后替代保护 `tests/unit/agent/platform/tools/builtins/test_bash_policy.py tests/unit/test_tool_validation_errors.py tests/unit/test_tools_read.py tests/unit/test_idle_callback.py tests/contract/test_tools_bash_contract.py tests/unit/agent/prompt_sections` 为 `116 passed in 0.67s`，M9 `--collect-only` 为 `18 tests collected` 且无已删 node。
  - Entry: 保留集合仍从 `build_kernel`、ToolRegistry、workspace loader 和 provider mapper seam 观察结果；本 unit 无产品行为变化。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: N/A（无外部服务/真浏览器风险；永久回归由上述 unit/contract 与 R2 保留的 integration 承担）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到计划提交 `33cf0581c`。
- Commits: 本 R1 提交（SHA 以 Git history 为准）。
- Next: R2 收敛保留用例的断言高度与时序等待。

## R2 — 收敛保留的跨 seam 保护

- 状态: DONE
- Context: 删除重复用例后，留存测试仍有三类腐烂点：compaction fake client 靠 prompt 原句识别摘要请求；bash stream 用固定尾部 sleep 和额外 noop run 解锁 collector；hook/tool/read 断言了下层文件名、字节和 classifier 投影细节。
- Decision: 摘要请求改以“不暴露工具”的 request seam 识别；bash collector 直接读取指定 run 的 terminal `run_status`；bash safe policy 用一条参数化 registry 路径表达；loader/read 仅保留加载后可 dispatch/execute 与 multipart shape 结果。
- Rationale: 这些观测点只在 seam 断开时失败，不再因 prompt 改写、fixture 改名、ReadTool 字节细节或 collector 调度时机而红。
- Evidence:
  - Tests: M9 全切片 `18 passed in 5.64s`；`test_bash_engine.py` 连续 3 轮均 `3 passed`（每轮约 5.17s）；M9 文件 ruff `All checks passed!`；`git diff --check` 通过。
  - Entry: fake LLM 仍经 `build_kernel`→ToolRegistry/ShellRunner→`kernel.stream`；workspace fixture 仍经 loader→registry/runner；read image 仍经 registry/hook/provider mapper。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: `tests/integration/test_bash_engine.py`、`test_conversation_*`、`test_tools_*`、`test_hooks_loader_integration.py`、`test_empty_tool_allowlist_wiring.py` 为永久 regression；本切片无外部依赖，不升级为 E2E。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 提交，保留 R1 的删测收敛。
- Commits: 本 R2 提交（SHA 以 Git history 为准）。
- Next: R3 运行收尾门禁，复核范围与处置表。

## R3 — 门禁与范围收尾

- 状态: DONE
- Context: R1--R2 已完成删测和断言收敛，需要用与基线同口径的 M9 切片、可执行的下层替代保护和静态/文档门禁证明没有保护缺口或越界。
- Decision: 复用 7 类文件 glob 重跑全 M9，单独运行 bash policy、tool validation、ReadTool、idle、bash contract 与 prompt section 替代保护；同时执行 ruff check/format、docs check、diff check、collection 与 baseline changed-path 对账。
- Rationale: 同口径 `32 → 18` 量化了测试资产收敛；独立替代保护命令防止“删掉高层重复后下层也不存在”的误判。
- Evidence:
  - Claim: M9 在不改产品/spec 的前提下净减 14 个重复/历史 case，保留的 kernel/tool 跨 seam 保护和下层独立保护全绿。
  - Baseline: `origin/unit/refactor-489@6d4ebd793`；M9 同口径 `32 passed in 9.01s`。
  - Method: 运行收敛后 M9 切片、6 类 lower seam/contract，再执行 ruff check/format、`scripts/docs_check.py`、`git diff --check 6d4ebd793...HEAD`、collect-only 和 changed-path 白名单检查。
  - Result: PASS；M9 `18 passed in 5.74s`（`32 → 18`）；替代保护 `116 passed in 0.62s`；ruff `All checks passed!`；format `8 files already formatted`；docs check `202 maintained Markdown sources / 65 routes`；collect `18 tests`；diff/scope 通过。
  - Locator: `tasks.md` 的逐风险处置表；保留的 8 个 M9 test 文件；下层替代保护路径见 R1 Tests。
  - Limit: fake LLM、临时文件与本地短子进程证明进程内 kernel/tool seam；本 milestone 无用户面变化，未调用真实外部 LLM/浏览器/常驻服务，不将此证据升级为 live E2E。
  - Tests: M9 `18 passed`；lower seam/contract `116 passed`；ruff/docs/diff/collect 全绿。
  - Entry: `build_kernel`→session/run→tool/compaction→LLM request/event stream，及 workspace loader→registry/runner；零产品 delta。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 收敛后 M9 18 项 integration 与 116 项可执行替代保护全绿；无新增 E2E。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Scope: baseline diff 仅含 M9 `tasks.md` / `progress.md` / `.gitkeep` 及 10 个归属 M9 的 integration test 文件；`test_empty_tool_allowlist_wiring.py` 处置为 keep 且无需改动；产品源码、current spec、M13 运行时测试和其他 milestone 产物均未改。
- Rollback: 按 R2 `01fed5d36`、R1 `21a52e594`、plan `33cf0581c` 逆序回退；零产品数据或运行时回滚需求。
- Commits: plan `33cf0581c`；R1 `21a52e594`；R2 `01fed5d36`；R3 本提交 SHA 以 Git history 为准。
- Next: 按 worker 协议 rebase 最新 `origin/unit/refactor-489`，重跑门禁后在 unit lock 下合并。

## Promotion Candidates

None.
