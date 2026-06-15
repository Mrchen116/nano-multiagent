# feat-409-M1: 内核 presenter 补齐/改人话 + task 收尾 + 透传链打通 — Tasks

> 对齐: ../design.md v1

## 目标

内核 presenter 端到端补齐并改人话，Gateway 把 `presentation.detail` 透传给 IM，IM 的 `ToolCall`
增 `detail` 字段并贯穿 parse/serialize/persist。完成后：经 `agent.sdk` 的消费者能在 `tool_end` 事件
拿到 agent/memory/skill_manage/task_stop 的结构化 detail（含 agent 完整未截断 prompt）+ 人话 summary；
Gateway→IM 链路 summary（人话）+ detail 到达前端可观测（WS/DB）。死代码 `task.py` / `_TaskPresenter` 删除。

## 退出标准

- [ ] 补 agent/memory/skill_manage/task_stop 四个工具的 presenter（挂 `presenter` 属性，随工具走）
- [ ] `_TaskPresenter` 重写为 `_AgentPresenter`（agent result schema：content/agent_id/output_file），含完整不截断 prompt 且排结果前
- [ ] bash summary 改人话（args.description，空降级命令首段）；agent→description、web_fetch→title 等同理
- [ ] web_fetch detail body 放宽截断
- [ ] 删除 task.py + `_TaskPresenter` + TASK_PRESENTER
- [ ] Gateway tool_end 透传 `presentation.detail` 进 streaming_delta.tool_call
- [ ] IM ToolCall 加 `detail` 字段，贯穿 domain/parse/serialize/persist
- [ ] 全测试树绿（contract + `-m "not e2e"`）

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. 各 presenter format_end 产出正确 summary（人话）+ detail schema（覆盖各 status 路径）
  2. agent presenter detail 含完整未截断 prompt 且排结果前
  3. bash summary = description（空降级命令首段）
  4. Gateway tool_end 把 pres.detail 透传进 tool_call.detail
  5. IM ToolCall.detail 序列化/持久化往返一致；历史无 detail 行降级不报错
- 已有测试在：`tests/unit/platform/tools/test_presentation.py` / `test_presentation_golden.py` / `test_presentation_cap.py`（扩展：bash summary 改人话需改 golden；task→agent 替换；新增 4 presenter 用例）
- IM 往返：定位现有 ToolCall 编解码测试扩展；Gateway tool_end 定位现有 streaming 测试扩展或新建最窄单测
- 落层/目录/marker：tests/unit/，无 e2e marker（本 milestone 是数据链单测；live e2e 由 reviewer 走）
- 可选依赖 importorskip：无
- 一次性验收证据：无（presenter/透传均为永久回归价值）

前端：N/A（M1 纯后端数据链，前端渲染在 M2）

## Roadpoints

### R1 — 内核 presenter 补齐/改人话 + task 收尾

- 步骤:
  - bash presenter summary 改为 args.description（空降级命令首段）
  - 新增 `_AgentPresenter`（重写自 `_TaskPresenter`，agent schema + 完整 prompt 排结果前）、
    `_MemoryPresenter`、`_SkillManagePresenter`、`_TaskStopPresenter` + 对应 singleton
  - 给 AgentTool/MemoryTool/SkillManageTool/TaskStopTool 挂 `presenter` 类属性
  - web_fetch detail body_excerpt 放宽（走 _enforce_cap content 字段，不再 _truncate 500）
  - 删除 task.py、`_TaskPresenter`、TASK_PRESENTER
  - 更新 test_presentation.py / golden：task→agent，bash summary 断言改人话，补 4 presenter 单测
- 验证: `pytest tests/unit/platform/tools/ -q` 全绿；contract 全绿（task 删除后无悬挂引用）

### R2 — Gateway tool_end 透传 detail

- 步骤: main.py tool_end 把 `pres.get("detail")` 放进 streaming_delta.tool_call.detail
- 验证: 单测断言含 detail 的 presentation 经 tool_end 后 tool_call 含 detail；无 detail 时不带该键

### R3 — IM ToolCall.detail 贯穿 parse/serialize/persist

- 步骤:
  - domain/models.py ToolCall 加 `detail: dict | None = None`
  - gateway_handler._parse_tool_call 读 detail
  - event_types.tool_call_to_dict 序列化 detail（省略未设）
  - repositories._tool_call_to_dict / _decode_tool_calls 持久化 detail
- 验证: 序列化/持久化往返单测含 detail；历史无 detail 行 decode 不报错（降级 None）

### R4 — 文档收尾

- 步骤: progress.md 补齐各 R 证据；体量上限复核结论记入 progress
- 验证: 全测试树（contract + `-m "not e2e"`）绿
