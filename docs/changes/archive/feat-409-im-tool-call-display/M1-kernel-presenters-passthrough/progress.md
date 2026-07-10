# feat-409-M1 — Progress

## 体量上限复核（M1 grounding 项，决策 6）

256KB 内核 `_enforce_cap` 是唯一绑定约束，无更小隐藏上限：
- Gateway→IM：uvicorn `ws_max_size` 默认 16MB（IM 用 Starlette `websocket.receive_text()`，无自身上限）
- IM→浏览器：同上 uvicorn 16MB；浏览器 WebSocket API 无消息上限
- 持久化：`messages.tool_calls_json` 为 SQLite TEXT（实际上限 ~1GB）
- realtime_stream 已正确带 detail（`_presentation_dict` 含 detail 键），断点确在 Gateway，符合 design

结论：无需为本 unit 新增传输层裁剪。

## R1 — 内核 presenter 补齐/改人话 + task 收尾

- Context: agent/memory/skill_manage/task_stop 四工具无 presenter（消费者只拿到截断参数）；
  bash summary 为裸 `exit=N elapsed=Xms` 无信息量；task.py 是死代码（从不注册）。
- Decision:
  - bash summary 改人话：`args.description`，空时降级命令首段（新增 `_summarize_bash` helper）
  - `_TaskPresenter` 重写为 `_AgentPresenter`，按 agent 真实 result schema
    （content/agent_id/output_file，非 task 的 summary/artifacts），完整未截断 prompt 进 detail 且排结果前；
    in-band 失败（output.status=="failed"）也标红
  - 新增 `_MemoryPresenter`（action/target/content/message/success）、
    `_SkillManagePresenter`（action/name/message/path/success）、
    `_TaskStopPresenter`（task_id/status）
  - 四工具挂 `presenter` 类属性（决策 12 随工具走）
  - web_fetch detail body 放宽：`content` 字段走 `_enforce_cap`（256KB）替代硬截 500 字
  - 删 task.py + `_TaskPresenter` + TASK_PRESENTER；删 test_task_tool_non_blocking.py（纯测死 TaskTool）
- Rationale: agent prompt 不进 `_enforce_cap` 截断集（它截 stdout/stderr/diff/content），派发 prompt
  体量恒小、保持完整——这是用户判断派发准确性的关键信号（spec Scenario）。
- Evidence:
  - Tests: `pytest tests/unit/platform/tools/` 全绿（含 agent 完整 prompt 单测、bash summary 人话/空降级单测、
    memory/skill_manage/task_stop 各 status 路径）；golden 同步改（bash summary、task→agent）
  - Entry: N/A（内核 presenter 单测即真实产出验证；live e2e 由 reviewer 走）
  - Frontend State Matrix: N/A（M1 纯后端）
  - Browser QA: N/A
  - E2E/Regression: presenter 单测为永久回归
  - Visual/Interaction: N/A
- Rollback: revert C2（feat feat-409/M1/R1）
- Commits: C1=test feat-409/M1/R1, C2=feat feat-409/M1/R1

## R2 — Gateway tool_end 透传 detail

- Context: Gateway observer 的 tool_end 块只读 `pres["summary"]`，`detail` 被丢弃（断点）。
- Decision: 把 `pres.get("detail")` 原样放进 `node.streaming_delta` tool_call.detail（决策 1：纯透传管道，
  不二次截断、不按工具重组）；无 detail 时省略该键。
- Rationale: 内核 presenter 是 detail 结构的唯一权威；256KB cap 已兜底，Gateway 无需再设阈值。
- Evidence:
  - Tests: `tests/unit/personal_assistant/test_tool_end_detail_passthrough.py`（驱动真实 observer 闭包，
    断言含 detail 的 presentation → tool_call.detail；无 detail 省略键）；`tests/unit/personal_assistant/` 全绿（558）
  - Entry: N/A（observer 单测驱动真实事件路径；live 由 reviewer）
  - 其余: N/A（后端）
- Rollback: revert C2（feat feat-409/M1/R2）
- Commits: C1=test feat-409/M1/R2, C2=feat feat-409/M1/R2

## R3 — IM ToolCall.detail 贯穿 parse/serialize/persist

- Context: IM `ToolCall` 无 detail 字段，detail 链在 IM 侧无承载。
- Decision: 决策 2——`ToolCall` 增 `detail: dict | None`；贯穿
  `_parse_tool_call`（读）/ `tool_call_to_dict`（序列化，省略未设）/
  `_tool_call_to_dict` + `_decode_tool_calls`（持久化往返）。summary 不另立字段（已由 output 承载）。
- Rationale: 历史行无 detail → decode 降级 None，前端回退 output 串，不报错。
- Evidence:
  - Tests: `tests/im_service/unit/test_tool_call_detail.py`（parse 含/缺 detail、tool_call_to_dict 含/省略、
    completed payload 携带、encode/decode 往返、旧行无 detail 降级 None、SQLite 全链路持久化往返）；
    `tests/im_service/` 全绿（303 passed / 1 skipped）
  - Entry: SQLite create_message → list_messages 真实往返单测断言 detail 保真
  - 其余: N/A（后端）
- Rollback: revert C2（feat feat-409/M1/R3）
- Commits: C1=test feat-409/M1/R3, C2=feat feat-409/M1/R3

## R4 — 文档收尾 + 全树验证

- 全测试树（`pytest tests/ -m "not e2e"`）：2590 passed, 1 skipped, 4 deselected(e2e)
- 全仓 ruff check + ruff format --check：clean
- contract target-tree 引用 task.py → agent.py（task 退役）
- 连带清理：test_task_tool_blocking.py 删除；test_tools_bash_task.py / test_tools_builtins.py 去除死 TaskTool 引用

## 给 orchestrator 的契约层提示（worker 不写 spec）

- kernel delta-spec / im delta-spec 已由 design 阶段产出（specs/kernel、specs/im），实现与其一致，无需改动。
- 对外可观察行为变化：内核 `tool_end` 的 presentation 现覆盖 agent/memory/skill_manage/task_stop
  且 summary 为人话；IM tool_call WS payload / 持久化新增 detail 字段。canonical spec 工具清单
  task→agent 订正归 orchestrator 收尾归并。
