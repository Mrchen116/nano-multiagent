# bugfix-426-M1: sdk-im-steering — Tasks

> 对齐: ../design.md（Changelog 见 design.md；多模态措辞 vs text-only 现实对齐见 progress.md R1）

## 目标

恢复 feat-338 的 `priority="next"` 注入语义，以进程内 SDK 形态接出：
- `Kernel.submit(steer=False)` 默认；`steer=True` 时内核原子地「有活跃 run 则注入下一轮、否则建新 run」，返回 `RunInfo.injected` 标志。
- Gateway `inbound_pipeline` 在入队前对运行中消息走 `submit(steer=True)`：injected→不入队、由活跃 run 的 SSE 流 surfacing；非 injected→照现状入队。
- stranded 续跑 origin 跟随注入来源（用户 steer→USER，非硬编码 BACKGROUND_TASK）。

## 退出标准

- [ ] `Kernel.submit` 新增 `steer: bool = False`，`steer=True` 有活跃 run→注入并返回 `injected=True`（复用其 run_id）、无活跃 run→建新 run 返回 `injected=False`。
- [ ] `RunInfo` 新增 `injected: bool = False` 字段，SDK 消费者可观察。
- [ ] 注入消息复用 submit 同款 `parse_input_parts + render_user_text`（content 为 str；带不带附件路径完全相同）。
- [ ] `inject_pending_message` + pending 队列承载 `origin`；stranded 续跑（registry.py:638-648）按注入来源传 origin，不再硬编码 BACKGROUND_TASK。
- [ ] Gateway inbound 运行中 steer 接线：parts 构建复用 `_run` 同源 helper（group buffer drain + `_format_sender_text` 发言人前缀 + 附件组装）；injected=True 不入队、injected=False 照现状入队。
- [ ] 群聊运行中 steer 保留发言人前缀与缓冲上下文。
- [ ] 最窄相关单测全绿（test_runs_registry / test_run_control / kernel submit steer / inbound steer）+ live IM 端到端验证「运行中发消息当前 run 下一轮被消费」。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - `RunController` pending 队列承载 origin（enqueue+drain 保 origin/FIFO）。
  - `RunsRegistry.inject_pending_message(origin=...)` 返回 True/False 语义；stranded 续跑 origin=USER 不再 BACKGROUND_TASK。
  - `Kernel.submit(steer=True)`：有活跃 run→injected=True 注入；无活跃 run→injected=False 新 run。content 经 render_user_text 渲染（图片→placeholder）。
  - Gateway inbound：运行中 steer 不入队（injected）、空闲照常入队；群聊 steer 保发言人前缀+缓冲。
- 已有测试在：
  - `tests/unit/test_runs_registry.py`（扩展：inject origin + stranded 续跑 origin）。
  - 新建 `tests/unit/agent/test_run_control_pending_origin.py`（RunController pending origin，现无专测文件）。
  - `tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py`（扩展：steer 接线 + 群聊保真），其 `_FakeKernel.submit` 需支持 steer/injected。
  - Kernel submit steer：扩展或新建 `tests/unit/agent/test_kernel_submit_steer.py`（SDK 面真 Kernel，沿用 build_kernel）。
- 落层/目录/marker：tests/unit/，marker：无（live IM e2e 走真栈手动验收，不落 pytest e2e）。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：live IM 端到端 run-中-steer 截图/log → progress.md 记录，不落套件。

前端：N/A（本 milestone 无前端改动）。

## Roadpoints

### R1 — RunController pending 承载 origin + RunsRegistry inject origin + stranded 续跑修正（决策3）— DONE

- 步骤:
  - `run_control.py`：`enqueue_message` / `drain_pending` 承载 origin（pending 队列存 (origin, LLMMessage) 或并行结构），loop.py drain 消费侧适配。
  - `registry.py`：`inject_pending_message(session_id, message, origin)` 加 origin 参数；stranded 续跑（:638-648）按 drain 出的 origin 续跑、不硬编码 BACKGROUND_TASK。
  - `background_tasks/wiring.py` 调用点补传 origin=BACKGROUND_TASK（保持其现状语义）。
- 验证: test_run_control pending origin；test_runs_registry stranded 续跑 origin=USER；全绿。

### R2 — Kernel.submit(steer) + RunInfo.injected（决策1/2）— DONE

- 步骤:
  - `dto.py`：`RunInfo` 加 `injected: bool = False`。
  - `kernel.py`：`submit` 加 `steer: bool = False`；steer=True → 用 `parse_input_parts+render_user_text` 建 `LLMMessage(role="user", content=text)`，`inject_pending_message(origin=origin)` 有活跃 run→injected=True 返回活跃 run_id；否则 submit 新 run injected=False。`_to_run_info` 透传 injected。
- 验证: test_kernel_submit_steer 有/无活跃 run injected 正确 + content placeholder；全绿。

### R3 — Gateway inbound steer 接线 + parts helper 抽取（决策1，群聊保真）

- 步骤:
  - 抽 `_build_parts`（group buffer drain + 发言人前缀 + 附件组装）共用 helper，submit 路径与 steer 路径同源。
  - `handle_inbound`：在进 `_run_queue` 之前（仿 /stop 走 `_active_runs` 的位置）检查活跃 run；运行中走 `submit(steer=True)`，injected=True 不入队（发 accepted/steer lifecycle，由活跃 run SSE 流 surfacing），injected=False 照现状入队 `_run`。
- 验证: test_inbound steer 不入队/空闲入队 + 群聊保发言人前缀；全绿。

### R4 — live IM 端到端验收 + 文档

- 步骤: 真栈起 IM+Gateway（e2e-up.sh），运行中发消息看当前 run 下一轮是否消费；连发保序；空闲开新 run；群聊保发言人。证据落 progress.md。
- 验证: live 旅程过；全测试树窄相关 + contract 绿。
