# bugfix-443-M1: sidechain-model-inherit — Tasks

> 对齐: ../design.md v1

## 目标

bugfix-429 per-run model 机制的两个收尾根因补全，外部可观察：

- 根因 A：以 `model=mimo` 提交的 run 派发的 subagent（后台/前台/resume 三条路径），其 LLM 请求模型 = mimo，不回退全局默认；连带 subagent 脚下的压缩/fork/hook 侧链也跟随 mimo。
- 根因 B：以 `model=mimo` 提交的 run 触发主动阈值压缩（`loop.py`）时，summarizer 用 mimo；配了独立 `summary_model` 时仍用独立模型。

## 退出标准

- [x] `AgentRuntime.resolve_run_model(session_id)` 返回该 session 已登记的 run 模型（无则 None）。
- [x] 三派发点（后台 start / 前台 submit_foreground / resume）都用 `resolve_run_model(父 session)` 取父模型并透传到 `runtime.run(model=...)`，单测验证 runner/run 收到父模型。
- [x] `BackgroundSubagentRunner.start` Protocol + `RuntimeRunner.start` 加 `model: str | None = None`，透传 `runtime.run(model=model)`。
- [x] 根因 B：`loop.py:910` 补 `model_override=(None if summary_model else active_model)`，单测两态（无 summary_model 用 active_model、有 summary_model 传 None）。
- [x] 全测试树 `pytest -m "not e2e"` 不回归（3044 passed）；contract line-pin 不移位（129 passed，runtime.py:208 在新增 accessor 之上）。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. `resolve_run_model` 取值语义（登记则返回、未登记返回 None、session_id=None 返回 None）。
  2. 三派发点把父模型透传给 runner.start / runtime.run。
  3. `RuntimeRunner.start` 把 `model` 透传到 `runtime.run`。
  4. `loop` 主动压缩 summarize 的 `model_override` 两态。
- 已有测试在：
  - `tests/unit/agent/tools/test_agent_tool.py`（扩展：三派发点已有 `llm_session_id` 同构测试，照模式加 model 断言）
  - `tests/unit/test_agent_runtime.py`（扩展：加 `resolve_run_model` 行为测试）
  - `tests/unit/test_loop_compact.py`（扩展：已有 `_FakeCompactionSummarizer` 记录 model_override 范式，加 loop 主动压缩两态）
  - `RuntimeRunner.start` 透传：新建小测 `tests/unit/test_runtime_runner_model.py`（现无 runtime_runner 专属测试文件，adapter 行为独立于 agent tool）
- 落层/目录/marker：tests/unit/，marker 无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据：reviewer 轨真栈 proxy 日志（归 reviewer，不进套件）。

非前端 milestone，UI 状态矩阵 / 浏览器验收 = N/A。

## Roadpoints

### R1 — runtime accessor + subagent 三派发点透传（根因 A）

- 步骤:
  1. `runtime.py` 加 `resolve_run_model(session_id) -> str | None`（决策 1）。
  2. `interfaces.py` `BackgroundSubagentRunner.start` 加 `model: str | None = None`；`runtime_runner.py` `RuntimeRunner.start` 同步并透传 `runtime.run(model=model)`（决策 3）。
  3. `agent.py` 三处：后台 `start()`（:289）、前台 `submit_foreground(runtime.run(...))`（:358）、`_resume_subagent` 的 `start()`（:557）取 `runtime.resolve_run_model(ctx.session_id)` 透传。
- 验证: test_agent_tool 三派发点断言 model；test_agent_runtime resolve_run_model 行为；test_runtime_runner_model 透传。

### R2 — loop 主动阈值压缩 model_override（根因 B）

- 步骤: `loop.py:910` summarize 补 `model_override=(None if self._compaction_settings.summary_model else active_model)`。
- 验证: test_loop_compact 两态（无 summary_model → active_model；有 summary_model → None）。

### R3 — 全树回归 + contract + 文档

- 步骤: 跑 `pytest -m "not e2e"`、contract；补 progress.md。
- 验证: 全绿、contract line-pin 不移位。
