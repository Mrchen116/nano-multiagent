# M1 Kernel / SDK 实施证据

## 实现边界

- 删除 core/SDK 的 `OutputCandidate`、`OutputResult`、`OutputControl`、`OutputHandler`、`BoundOutputControl` 及 `build_kernel(output_handler=...)`。内核不再依据产品交付结果决定续跑。
- 恢复 main 基线 `0014ee0b0` 的输入 revision 复核、草稿持久状态与原始 reminder。逐字断言落在真实复核结果，不以模板自比较替代行为验证。
- `model_round_end` 在完整 stream、工具结果与输入复核之后，下一次模型调用之前发布；携带 session/run/turn/group、该轮输入的 context_revision 快照与 completed，不等待产品处理。空正文轮也有唯一 group；异常/取消轮不报告正常完成。
- 新增 `await Kernel.authorize_tool(session_id, tool_name, arguments, operation_id, *, workspace_root=None, run_id=None) -> PermissionOutcome`。真实会话加载与权限检查通过 KernelExecutor 的生命周期任务在所属 event loop 执行；使用真实工作区 registry、运行来源/模型与 transcript，不占模型 turn gate，不执行工具。调用者取消会取消所属循环里的人工批准任务；已结束 run 仍可作为经验证的来源。

## 验证

命令：

```sh
.venv/bin/pytest -q tests/unit/agent tests/unit/test_agent_loop.py tests/contract/test_sdk_tool_authorization.py tests/contract/test_agent_sdk_surface_guard.py tests/contract/test_sdk_kernel_wiring.py tests/contract/test_kernel_sdk_behavior_contract.py
```

结果：**663 passed in 23.90s**。其后移除权限 classifier history 中不存在的新空白 user 输入，重跑 `tests/contract/test_sdk_tool_authorization.py`：**2 passed in 1.26s**。`ruff check src/agent` 与 `git diff --check` 通过。

新增覆盖：多 chunk 与工具交错、下一模型调用前的轮边界、空正文轮、流异常/取消/中止、扣住草稿后的 round_end 顺序；跨工作区/会话并发 allow/deny、真实 HookContext、无工具执行、跨 event loop 取消及人工批准清理、已完成 run 的来源与历史保留。

首次扩大测试有一条既有 terminal-window steer 时序失败：测试仅等 running 而非第一轮 LLM 进入，输入可能在首轮开始前已消费。未修改该契约或测试；单测复跑及最终完整 663 项复跑均通过。

## 旧测试处理

- 删除 `tests/unit/agent/test_output_callback.py`：其断言专属于已撤回的产品回调与同 run 业务恢复，Gateway 恢复由产品测试覆盖。
- `test_output_permission.py` 改为测试通用 registry permission-only 拦截链；删除 BoundOutputControl 提交测试，其输入复核职责保留在既有 revalidation 测试。
- `test_output_revalidation.py` 保留全部原复核行为，并将旧共享模板测试移为真实草稿 reminder 的逐字校验，增加复核/轮结束/新输入消费顺序断言。
- `tests/unit/test_agent_loop.py` 的事件清单断言纳入两次正常 model_round_end；SDK surface guard 删除已撤回的四个输出类型，保留 PermissionOutcome。

Canonical 契约见 [kernel runs](../../../../specs/kernel/runs.md) 与 [kernel 入口](../../../../specs/kernel/spec.md)。本记录仅描述 Kernel 实施与验证，不替代产品交付验收。


## 复核后补充：准备期间的新输入

`model_round_end.context_revision` 暴露本轮模型实际消费的 pending revision，复用已有输入复核事实，不把产品交付状态加入内核。测试同时证明无 controller 时为 0，以及工具等待期间接受新输入后，前一轮/后续轮分别报告 0/1，而非都读发送时最新接受值。SDK 的既有 `RunInfo.pending_id` 是不透明身份，不能将产品本地真人输入计数误当内核跨来源 revision。
