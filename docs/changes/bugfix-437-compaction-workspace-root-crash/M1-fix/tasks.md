# bugfix-437-M1: 修压缩落盘漏传 workspace_root + 失败反馈只到 relay-task 级 — Tasks

> 对齐: ../design.md v1

## 目标

- 超长对话触发压缩(threshold / overflow)时,在生产 workspace-aware(`data_dir=None`)模式下不再因会话存储定位失败而崩溃,run 透明继续出完、不失忆。
- 压缩落盘单一路径(无双写),压缩后内存 `_session_histories` 不含已摘要轮次。
- 任意 run 失败时,IM 占位气泡数秒内翻 failed 并带真因(message 级 node.report),归属正确 agent,不再干等 120s watchdog 兜底。

## 退出标准

- [x] 新增 `data_dir=None`(workspace-aware)下触发 threshold 压缩的回归用例,断言落盘成功且会话可由事件重放重建(R1)
- [x] 新增 `data_dir=None` 下触发 overflow 压缩的回归用例,断言落盘 + retry 成功 + 不失忆(R2)
- [x] 压缩后内存 `_session_histories` 不含已摘要轮次(磁盘重放断言照不到的内存回归)单独断言(R2)
- [x] 压缩落盘单一路径(无双写,`apply()` 不持久化),`compact_boundary` 仍先于 summary turn(R2)
- [x] B 面:run 失败 → 发出 message 级 `node.report(status=failed, message_id, summary=真因)`,既有 delivery_receipt 保留(R3)
- [x] 全测试树 `pytest -m "not e2e"`(含 im_service)不回归;`ruff check` + `ruff format` 绿(收尾门禁)

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为(来自退出标准):
  1. data_dir=None 下 threshold 压缩不崩、可重放重建(A 面决策1)
  2. data_dir=None 下 overflow 压缩不崩、retry 成功、不失忆(A 面决策1+2)
  3. 压缩后内存 `_session_histories` 仅含 summary 轮(A 面决策2 内存回归)
  4. 压缩单写 + compact_boundary 先于 summary(A 面决策2)
  5. run failed → message 级 node.report 带真因(B 面决策3)
- 已有测试在:`tests/integration/test_compaction_runtime_integration.py`(A 面,扩展:全用 data_dir 旁路,新增 data_dir=None 平行用例 + 内存/单写断言);`tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`(B 面,扩展 failed 分支)
- 落层/目录/marker:tests/integration/(A 面跨 runtime↔store) + tests/unit/personal_assistant/(B 面 callback 单元),marker:无
- 可选依赖 importorskip:无
- 本 milestone 产生的一次性验收证据:无(全部沉淀为回归用例)
- 前端:N/A(无 UI 改动)

## Roadpoints

### R1 — A 面决策1:workspace_root 显式贯穿压缩读取点

- 步骤:`loop.run`/`_execute_loop` 加显式 `workspace_root` 参数,穿到 `_maybe_compact` → `list_entries`;runtime 两处 `_execute_loop` 调用点传 `session_workspace_root`;overflow @668 `list_turn_messages` 带根。
- 验证:C1 新增 data_dir=None threshold 压缩回归(红:漏根崩溃);C2 修后绿、可重放重建。

### R2 — A 面决策2:消双写,apply() 降纯结果构造 + 内存断言

- 步骤:`_compact_session` 保留含 `_session_histories[session_id]=[summary_msg]` 的直写路径(经已解析 path);`CompactionApplier.apply` 去 `append_compaction` 持久化副作用,改纯构造 `CompactionResult`,`entry_id` 对齐直写 `summary_uuid`。
- 验证:C1 新增 data_dir=None overflow 压缩回归 + 压缩后内存 history 仅含 summary 断言 + 单写(磁盘仅一对 compact_boundary+summary)+ compact_boundary 先于 summary 断言;C2 修后绿。

### R3 — B 面决策3:失败 message 级即时反馈

- 步骤:`main.py` `_build_relay_lifecycle_callback` 的 `failed` 分支镜像 `completed`,补发 `send_report(status="failed", message_id, summary=update.error)` → `node.report`,保留既有 delivery_receipt。
- 验证:C1 扩展 relay lifecycle 测试,断言 failed 分支发出 message 级 node.report 带真因 + message_id;C2 修后绿。
