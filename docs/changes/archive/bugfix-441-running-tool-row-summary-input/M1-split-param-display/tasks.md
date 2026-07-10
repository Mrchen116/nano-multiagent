# bugfix-441-M1: split-param-display — Tasks

> 对齐: ../design.md v1

## 目标

工具调用开始时就把 presenter 产出的参数侧 summary/detail 透传到 IM，前端 running 态展开只显示参数、不显示结果/完成标记；工具完成后除 send_message/cron 的结构化改善外保持既有完成态展示。

## 退出标准

- [x] 真栈 IM Web UI: 长 bash / agent 子任务 / web_search 执行中，折叠出摘要且展开出命令 / prompt / query。
- [x] 真栈 IM Web UI: 上述工具执行中展开不显伪完成态，无 `✓ completed` / `无结果` 空态，折叠仍保持 running 脉冲。
- [x] 真栈 IM Web UI: 上述工具执行完折叠+展开为参数+结果；除 send_message/cron 外与旧完成态逐项一致。
- [x] send_message/cron 执行中显示参数，执行完显示参数+结果，落 GenericCard 且为结构化 key/value。
- [x] 内核 9 个 builtin + web_search 的 format_start 都产参数片 detail，字段名与 format_end 对齐。
- [x] send_message/cron 新 presenter 的 format_start=format_end 参数/结果切分有单测。
- [x] write/memory 等含 content 的 start detail 复用 cap，超限时 `truncated` 为 true。
- [x] gateway tool_start delta 带 `output=summary` + `detail=参数片`，对照 tool_end 有单测。
- [x] 前端 gate: running 只渲参数区，completed/failed 完成态不变；reducer 的 tool_end output/detail 覆盖 tool_start。
- [x] `pytest -m "not e2e"`、前端 `npm run test`、`npm run build` 全绿。

## 测试策略

- 被测行为（来自退出标准）：presenter start 参数片、PA presenter 新增、gateway tool_start 透传、前端 running gate、reducer 覆盖、真栈 IM 用户可见 running/完成态。
- 已有测试在：`tests/unit/platform/tools/test_presentation.py`、`tests/unit/platform/tools/test_presentation_cap.py`、`tests/unit/personal_assistant/test_web_search_presenter.py`、`tests/unit/personal_assistant/test_send_message_tool.py`、`tests/unit/personal_assistant/test_cron_tool_closure.py`、`tests/unit/personal_assistant/test_tool_end_detail_passthrough.py`、`src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx`、`src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts`（均扩展，不新建测试文件）。
- 落层/目录/marker：unit/vitest，无 e2e marker；真浏览器 IM 验收作为一次性证据记录到 progress，不提交临时脚本。
- 可选依赖 importorskip：无新增。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真栈 IM Web UI 截图/日志路径，记录 running 与 completed 状态；若需要临时浏览器操作脚本，收尾删除。

用户路径分类：bug-regression

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | completed tool cards 保持原渲染，vitest 覆盖。 |
| loading | running tool cards 只显示参数区，vitest + 真栈覆盖。 |
| empty | web_search running results 缺失时不显“无结果”；completed 空 results 仍显示空态。 |
| error | failed completed detail 仍走 ErrorCard/失败卡，现有测试 + 新 gate 完成态覆盖。 |
| disabled | N/A，本 milestone 不改输入控件。 |
| submitting | N/A，本 milestone 不改表单。 |
| permission denied | N/A，权限 gate 区域不在本 milestone 范围。 |
| long content | write/memory start detail content cap 单测；长输出完成态现有 long-output 测试继续覆盖。 |
| missing/nullable data | running 参数片缺结果字段时不显示结果区；detail 缺失仍 output fallback。 |
| mobile viewport | 真栈验收至少记录桌面；移动不涉及本次布局变更，按 existing responsive 继承。 |
| desktop viewport | 真栈 IM Web UI 桌面截图覆盖。 |
| dark mode（如项目支持） | N/A，未发现本组件有独立 dark mode 分支。 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| presenter start detail 漏工具/字段错位 | 扩展 presenter 单测逐工具断言 | 是 |
| start detail 大字段撑爆链路 | cap 单测覆盖 write/memory start content | 是 |
| gateway tool_start 丢 summary/detail | 扩展 gateway observer 单测 | 是 |
| running 展开显伪完成态 | 扩展 ToolCallsPanel vitest + 真栈 UI | 是/证据 |
| tool_end 覆盖 tool_start | 扩展 reducer vitest | 是 |
| 用户原始 IM 症状 | 真栈 IM Web UI 长 bash / agent / web_search 截图与日志 | 否，progress 证据 |

## Roadpoints

### R1 — presenters and gateway relay

- 状态: DONE
- 步骤: 给 builtin/web_search/send_message/cron presenter 补 start detail；gateway tool_start 透传 output/detail；补后端单测。
- 验证: 相关 pytest 文件红转绿，字段/大字段 cap/gateway payload 均有断言。

### R2 — frontend running gate and reducer overwrite

- 状态: DONE
- 步骤: ToolDetailBody 将 running 态传入 bespoke 卡；agent/memory/skill/task_stop/web_search 结果区 gate；reducer 补 output/detail 覆盖断言。
- 验证: 相关 vitest 红转绿，completed/failed 不被 gate 改变。

### R3 — full gates and live IM Web evidence

- 状态: DONE
- 步骤: 跑全量 pytest/vitest/build；启动 worktree 真栈 IM+Gateway+Vite，驱动长 bash、agent、web_search，记录 running/完成态可见证据。
- 验证: pytest/vitest/build 全绿；真栈 IM Web UI 证据见 progress.md R3（bash / agent / web_search running 与 completed 截图）。
