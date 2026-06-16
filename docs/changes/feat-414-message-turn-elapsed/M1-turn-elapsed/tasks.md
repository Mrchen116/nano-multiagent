# feat-414-M1 tasks

## 目标

消息气泡显示本轮墙钟耗时：`elapsed_ms` 字段端到端贯穿 IM 后端与前端。

## 退出标准

- IM 后端单测覆盖 `on_message_completed` 写入 `elapsed_ms` + REST/WS payload 含该字段
- 前端 `tool-calls-panel` 折叠态无聚合时长、reducer `message.completed` 写入 `elapsed_ms`、message-pane 气泡显示耗时
- `pytest -m "not e2e" tests/`（含 im_service）与 `cd src/IM/frontend && npm run test` 全绿
- reviewer 6 条 Scenario 可验收（含多工具慢任务、纯文本、进行中、用户气泡无耗时、折叠工具徽标去求和）

## 测试策略

- R1(后端 DB/domain/repo)：在 `tests/im_service/unit/test_message_runtime_state.py` 扩 `elapsed_ms` 持久化 round-trip 测试
- R2(event_bridge + WS payload)：在 `tests/im_service/unit/test_event_bridge.py` 扩 `on_message_completed` 写入 + 在 `test_ws_event_types.py` 扩 `build_message_completed_payload` 含 elapsed_ms
- R3(REST route)：在 `tests/im_service/integration/test_messages_api.py` 扩历史消息列表返回 `elapsed_ms`
- R4(前端 tool-calls-panel)：vitest — 在 `chat-stream-reducer.test.ts` 扩 `elapsed_ms` 写入；tool-calls-panel 视觉改动用浏览器验收（删总时长）
- R5(前端 message-pane 气泡计时)：vitest — message-pane 计时状态（running tick / completed 定格），浏览器验收截图对照 prototype.html

### UI 状态矩阵

| 状态 | 覆盖方式 |
|---|---|
| running（进行中，实时 tick） | 浏览器验收 + vitest 状态断言 |
| completed（定格） | 浏览器验收 + vitest 状态断言 |
| failed（无计时显示） | vitest 状态断言 |
| 用户气泡（不显示耗时） | vitest 状态断言 |
| 工具徽标折叠（无总时长） | 浏览器验收 |
| 工具徽标折叠（有 running 标） | 浏览器验收 |
| 展开单工具 duration 保留 | 浏览器验收 |
| mobile viewport | N/A（status 行宽度随气泡自然缩减，不触发特殊布局） |
| dark mode | N/A（项目无 dark mode 切换） |

### 用户路径分类

- 气泡耗时显示：`normal-ui`（无历史 bug，浏览器临时验收 + vitest 回归）
- tool-calls-panel 去求和：`normal-ui`（浏览器临时验收，视觉改动）

## Roadpoints

| ID | 标题 | 范围 | 状态 |
|---|---|---|---|
| R1 | 后端 DB/domain/repo | db.py DDL + models.py Message + repositories.py | TODO |
| R2 | event_bridge + WS payload | event_bridge.py on_message_completed + event_types.py build_message_completed_payload | TODO |
| R3 | REST route | messages.py MessageResponse + to_message_response | TODO |
| R4 | 前端类型 + reducer + tool-calls-panel | chat-types.ts + chat-stream-reducer.ts + tool-calls-panel.tsx | TODO |
| R5 | 前端 message-pane 气泡计时 | message-pane.tsx running tick + completed 定格 | TODO |
