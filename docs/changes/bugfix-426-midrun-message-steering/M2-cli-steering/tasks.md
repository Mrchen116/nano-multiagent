# bugfix-426-M2: cli-steering — Tasks

> 对齐: ../design.md（决策4）

## 目标

CLI REPL 在一个 run 执行期间，用户输入的新消息不再阻塞、不再排到 run 结束后才作为新 run 处理，而是经 `kernel.submit(steer=True)` 注入当前 run 的下一轮 LLM 调用。空闲时输入照常开新 run。abort 侧（Ctrl-C / `_on_sigint`）维持既有 `interrupt()` 语义不变。

## 退出标准

- [ ] CLI run 执行中输入 → 走 `submit(steer=True)`，注入当前活跃 run（不另起新 run、不阻塞输入）
- [ ] 空闲时输入 → 仍 `submit`（无 steer 或 steer 退化）开新 run，行为与现状一致
- [ ] run 进行中连发多条 → 全部按序经 steer 注入（FIFO，依赖内核 pending 队列保序）
- [ ] abort 侧（Ctrl-C/SIGINT）仍走 `interrupt()`，未被非阻塞改造破坏
- [ ] 最窄相关 CLI 单测全绿；真实 CLI 端到端跑通「run 中输入→当前 run 下一轮被注入、不阻塞」

## 测试策略

- 被测行为（来自退出标准）：
  1. run 活跃期输入 → `submit` 被以 `steer=True` 调用
  2. 空闲期输入 → `submit` 开新 run（非 steer 路径）
  3. run 活跃期连发多条 → 多次 `steer=True` 调用按序
  4. Ctrl-C/SIGINT 仍触发 `interrupt()`
- 已有测试在：`tests/unit/test_cli_repl_async.py` / `tests/unit/test_cli_async_repl_sdk.py`（扩展——已有完整的 `run_cli` + stub kernel + input_fn 驱动基础设施）。新建一个聚焦 steer 行为的文件 `tests/unit/test_cli_repl_steering.py`，理由：steer 路由是新行为主题，与现有「事件渲染/去重」主题正交，独立文件更清晰且不撑爆现有 800+ 行文件。
- 落层/目录/marker：`tests/unit/`，marker：无（纯进程内 stub kernel，无真进程/真 LLM）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 CLI live 验收脚本/手动会话日志，路径记 progress.md，不进 `tests/`
- 死代码处置：`src/coding_cli/runtime/repl_runtime.py`（`ReplRunQueue`，全仓无实例化者）随本 milestone 删除；`tests/unit/test_cli_structure.py` 中断言其模块位置的那条用例同步删除（测死代码位置，无回归价值，符合 TESTING_GUIDE §1）。

非前端 milestone：UI 状态矩阵 / 浏览器 QA 写 N/A（CLI 终端交互验收以真实 REPL 会话为准，见 live 证据）。

## Roadpoints

### R1 — 非阻塞 REPL 输入循环 + 运行中 steer 路由 — DONE

- 步骤:
  1. 红测：在 `tests/unit/test_cli_repl_steering.py` 断言「run 活跃期输入走 `submit(steer=True)`、空闲走新 run、连发按序、SIGINT 仍 interrupt」。
  2. 实现：`_run_repl` 不再同步 await 整个 run；run 推进作为 asyncio task，输入读放 executor future，二者 `FIRST_COMPLETED` 竞争。run task 未终态时读到输入 → `submit(steer=True)`；空闲读到输入 → 新 run task。复用既有 stream 渲染管道（`_send_message_async` 的事件渲染逻辑）。
- 验证: `pytest tests/unit/test_cli_repl_steering.py` 全绿 + 既有 CLI 单测不回归。

### R2 — 清理死代码 + 修结构断言 — DONE

- 步骤:
  1. 删 `src/coding_cli/runtime/repl_runtime.py` 与 `runtime/__init__.py` 对它的导出。
  2. 删 `tests/unit/test_cli_structure.py` 里断言 `ReplRunQueue.__module__` 的那条。
- 验证: 全 CLI 单测树绿；`grep -r ReplRunQueue` 无残留引用。
