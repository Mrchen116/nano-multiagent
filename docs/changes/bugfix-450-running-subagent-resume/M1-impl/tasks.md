# bugfix-450-M1: impl — Tasks

> 对齐: ../design.md

## 目标

修复 running subagent follow-up 假 queued：`Agent(agent_id=..., prompt=...)` 只在原 running subagent 的 live `RunController` 注入链路接受消息后返回 `message_queued`，消息在下一安全点进入同一个 subagent runtime；live delivery 不可用时显式失败，不静默新开第二个 subagent。

## 退出标准

- [ ] running subagent follow-up 不再假成功：主 agent 发送 follow-up 后，原 subagent 后续能实际响应或在可读输出中体现收到 follow-up。
- [ ] live delivery 不可用时，主 agent 不看到“已成功排队”，也不会静默开第二个 subagent。
- [ ] terminal subagent resume 与 `output_file` 读取体验不退化。
- [ ] explicit background 和 foreground auto-background 两条 running subagent 路径都注册 live message handle。
- [ ] `_ControllerStopper` 改造/重命名为 `_ControllerHandle`，同一对象实现 stop 与 send_message，registry 不暴露裸 `RunController`。
- [ ] `_message_handles` 受 registry `_lock` 保护，terminal transitions 清理 message handle，并顺手清理 stop handle。
- [ ] `set_stop_handle` 参数注解改为 `BackgroundTaskStopper` Protocol，不继续依赖 concrete `_StopHandle`。
- [ ] running follow-up 测试验证 `RunController` / runtime 消费链路，而不是直接 `drain_agent_messages()`。
- [ ] 最窄测试通过：`pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py`。
- [ ] 相关后台任务回归通过：`pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py`。

## 测试策略

- 被测行为（来自退出标准）：running follow-up 进入 live `RunController` 并被 runtime 在下一安全点消费；live handle 缺失/拒绝时 `AgentTool` 显式失败且不新开第二个 subagent；terminal resume、output_file、task_stop 和 auto-background watcher 不退化。
- 已有测试在：`tests/integration/background_tasks/test_agent_continuation.py`（扩展 explicit background runtime 消费链路）；`tests/unit/agent/tools/test_agent_tool.py`（扩展 continuation failure 和 auto-background handle 注册）；相关回归复用 `tests/integration/background_tasks/test_agent_background.py`、`tests/integration/background_tasks/test_auto_background.py`、`tests/unit/agent/tools/test_task_stop_tool.py`。
- 落层/目录/marker：tests/integration/ 与 tests/unit/，marker：无；本 milestone 不起真进程/浏览器/真 LLM，live-critical 另以真实入口临时验收记录到 progress。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：用真实 `AgentTool` + `RuntimeRunner` + `AgentRuntime` 等价入口验收 running follow-up 可见输出；如需临时脚本，收尾删除并只记录命令/输出。

## 前端 UI

N/A，本 milestone 不改前端 UI。

## Roadpoints

### R1 — live subagent follow-up delivery

- 状态: TODO
- 步骤:
  - C1: 更新任务计划；把旧 registry pending-list 测试改为 live controller/runtime 消费链路红测，并补 live delivery 不可用的显式失败红测。
  - C2: 增加 `BackgroundSubagentMessageHandle` 协议、registry live message handle、runner `_ControllerHandle`、AgentTool continuation 投递语义，并覆盖 explicit background 与 foreground auto-background 注册。
  - C3: 更新本文件状态与 `progress.md`，记录测试和真实入口验收证据。
- 验证:
  - `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py`
  - `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py`
  - live-critical 等价入口验收：真实 `AgentTool` 调用启动 running subagent、发送 follow-up、观察同一 runtime 消费消息并输出。
