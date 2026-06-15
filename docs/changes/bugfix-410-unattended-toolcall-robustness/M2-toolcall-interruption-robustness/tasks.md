# bugfix-410-M2: toolcall-interruption-robustness — Tasks

> 对齐: ../design.md v1

## 目标

无人值守工具轮 + 权限门的三个收口面成立：①工具轮中断后会话不再永久污染、下次发消息照常回复（#82）；②等人工权限决策不被 120s idle 看门狗误杀、pending 显示「等待批准」、Deny 显示「已拒绝」（#98）；③run 异常终止时在飞 tool_call 徽标按原因收口（执行超时/已中断），已完成工具不被改写（#97）。贯穿一条 reason_code 旁路字段链：denied/timed_out/interrupted 端到端透传到前端文案。

## 退出标准

- [x] R1 #82：eager-recovery 移入 finally，无条件扫 `all_messages` 未闭合 tool_call；`invalidate_session_cache` 放 finally 最前（同步原子 pop、I/O 前），`append_tool_call_recovery`+flush 其后 best-effort shield；CancelledError 穿透（无 turn_meta）也补闭合，reason 合成 interrupted。单测覆盖 CancelledError 路径。
- [x] R2 #98：Gateway run-idle 看门狗见 `permission_request` 进豁免态、见后续事件退出；IM relay 加 `awaiting_permission` marker 靠 liveness（`awaiting_permission_at` 列 + IM heartbeat touch + run 终态/permission_response 清 + relay 对 stale 超崩溃阈值照常 reap）。单测覆盖豁免 + 崩溃兜底。
- [ ] R3 #97：observer 跟踪 running tool_call 集合，run_status 终态对在飞 tool_call 补发 `tool_call_completed` 带 reason（看门狗 cancel→timed_out / 其他→interrupted），已完成不改写。单测覆盖 reconcile + 不改写已完成。
- [ ] R4 reason_code 全链：`base.py`/`types.py` 字段 + `registry.py:172` 盖 `reason_code="denied"`（与给模型看的自由文本 reason 并存）+ tool_executor/loop/realtime_stream/main observer/IM gateway_handler/event_types/repositories/前端 透传 + 前端 denied→已拒绝 / timed_out→执行超时 / interrupted→已中断 / pending→等待批准 文案。deny/timeout/interrupt 三态徽标单测 + 前端浏览器视觉自测。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - 中断（CancelledError 穿透）后 finally 补 recovery + invalidate cache（R1）
  - Gateway run-idle 在 permission_request 后不超时、后续事件恢复计时（R2）
  - relay 看门狗对 awaiting_permission marker 不 reap，但 stale 超崩溃阈值照常 reap（R2）
  - run 终态 reconcile 在飞 tool_call 带 reason、已完成不改写（R3）
  - reason_code 端到端透传 + 前端三态文案（R4）
- 已有测试在：`tests/unit/test_agent_runtime*.py`（R1 扩展）、`tests/unit/test_inbound_pipeline_streaming.py`（R2/R3 扩展）、`tests/im_service/unit/test_relay_watchdog.py`（R2 扩展）、`tests/unit/test_streaming_tool_executor.py`（R4 reason 提取扩展）、前端 `tool-calls-panel.test.tsx`（R4 扩展）
- 落层/目录/marker：tests/unit/ + tests/im_service/unit/ + 前端 vitest，marker：无（非 e2e）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：前端浏览器三态徽标截图（progress.md 记录路径）

前端 UI（tool-calls-panel.tsx + i18n）：

用户路径分类：bug-regression（#97 徽标永久 running 是历史 bug）+ visual-only（三态文案/配色）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | tool_call completed/running 既有渲染不回归 |
| running | 既有 ◌ pulse 不变 |
| empty | N/A（panel 在 0 calls 时 return null，既有） |
| error | failed ✕ 既有 |
| permission denied | 新增 reason=denied → 「已拒绝」文案 + 配色 |
| timed_out | 新增 reason=timed_out → 「执行超时」 |
| interrupted | 新增 reason=interrupted → 「已中断」 |
| pending | 新增 permission pending → 「等待批准」徽标 |
| long content | 既有 pre 滚动不回归 |
| mobile/desktop viewport | 真实浏览器两 viewport 自测 |
| dark mode | 项目暗色主题，配色 oklch 对照 |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| reason→文案映射 | vitest 组件测试三态断言 | 是 |
| 三态徽标真实渲染 | 浏览器截图 + viewport | 否（一次性证据） |
| 既有 running/completed/failed 不回归 | vitest + 浏览器 | 是 |

## Roadpoints

### R1 — #82 恢复式 finally 覆盖 CancelledError

- 步骤: runtime.py 包 try 主体的 except/finally；finally 无条件扫未闭合 tool_call、invalidate 在前、append+flush shield 在后；reason 合成不依赖 turn_meta
- 验证: 单测构造 CancelledError 穿透路径，断言 cache invalidated + recovery 条目落盘；既有 aborted/cancelled 路径不回归

### R2 — #98 看门狗豁免（Gateway run-idle + IM relay liveness marker）

- 步骤: inbound_pipeline run-idle 见 permission_request 不超时 / 后续事件恢复；IM 加 awaiting_permission_at 列 + heartbeat touch + 终态/resolved 清 + relay stale 崩溃阈值 reap
- 验证: pipeline 单测（permission_request 后超 120s 不 cancel）；relay 单测（marker 内不 reap、stale 超阈值 reap）

### R3 — #97 终态在飞 tool_call reconcile

- 步骤: main.py observer 跟踪 running tool_call（tool_start 记 / tool_end 清），run_status 终态遍历在飞补 tool_call_completed 带 reason，已完成不动
- 验证: 单测断言终态补发 + reason 正确 + 已完成不改写

### R4 — reason_code 全链 + 前端文案

- 步骤: base.py/types.py 加 reason 字段；registry:172 盖 denied；tool_executor 提取 details.reason_code；loop/realtime_stream/main observer/IM 全链透传；前端 ToolCall TS + panel 文案 + i18n
- 验证: 后端链路单测 + 前端 vitest 三态 + 浏览器视觉自测
