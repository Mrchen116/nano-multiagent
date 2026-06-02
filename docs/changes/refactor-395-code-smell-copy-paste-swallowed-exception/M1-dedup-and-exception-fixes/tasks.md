# refactor-395-M1: dedup-and-exception-fixes — Tasks

## 目标

消除全仓 14 处 Copy-paste 重复（生产 9 + 测试 3 + 常量 2）、10 处吞异常修复、11 处废弃 API 替换、4 项死代码删除（含 ~28-31 个测试 import 重定向），所有正常路径行为逐字节不变。

## 退出标准

- `pytest -m "not e2e"` 全绿（除基线已有的 `/private/tmp` vs `/tmp` 路径差异一处）
- `pytest tests/contract` 全绿（依赖方向未破）
- 14 处重复每处仅剩单一真源（跨包 `_require_text`/`_optional_text` 收敛到每包一份），旧副本已删
- 单测锁定 `TERMINAL_RUN_STATUSES == frozenset({"completed","failed","cancelled"})`
- 10 处吞异常各有日志/报错/fallback，既有测试不变更通过
- `grep -r "logger.warn(" src/` 源码零残留（dist/ 不计）
- `grep -r "from IM.models\|from IM.repositories\|smoke_runtime" src/ tests/` 零残留
- `pytest --collect-only` 无 import 错误

## 测试策略

纯行为保持重构，无新对外行为，测试目标是"所有现有测试继续通过"。

新增测试：
1. R1：单测锁定 `TERMINAL_RUN_STATUSES` 派生集合与原字面量一致
2. 各 roadpoint 的实现以"现有测试通过" + 手工 grep 确认为验收门禁

## Roadpoints

| ID | 标题 | 状态 | 文件范围 |
|---|---|---|---|
| R1 | core utils + TERMINAL_RUN_STATUSES + sdk 暴露 + 废弃 API | DONE | agent/core/utils/(new), agent/core/types.py, agent/core/background_tasks/, agent/core/runs/, agent/core/agent/runtime.py, agent/core/agent/loop.py, agent/core/tools/registry.py, agent/sdk/__init__.py |
| R2 | platform 共享 helper 提取 | DONE | agent/platform/llm/providers/(common.py new + anthropic + openai_compat), agent/platform/tools/(base.py, presentation.py, builtins/write.py, builtins/edit.py, builtins/read.py, builtins/bash.py, builtins/task_stop.py, builtins/task.py, builtins/agent.py) |
| R3 | IM 死代码删除 + 三件套提取 + 测试 import 重定向 | DONE | IM/models.py(del), IM/repositories.py(del), IM/domain/__init__.py, IM/infra/_helpers.py(new), IM/infra/db.py, IM/infra/repositories.py, IM/application/event_service.py, IM/ws/gateway_handler.py, tests/ 中 ~31 个文件 import 重定向 |
| R4 | personal_assistant _utils.py 提取 + coding_cli TERMINAL_RUN_STATUSES | TODO | personal_assistant/_utils.py(new), personal_assistant/main.py, personal_assistant/ws/im_connection.py, personal_assistant/config/sync_client.py, personal_assistant/channels/web_relay_adapter.py, personal_assistant/gateway/inbound_pipeline.py, personal_assistant/smoke_runtime.py(del), coding_cli/text_runner.py, coding_cli/commands.py, coding_cli/events/repl_events.py |
| R5 | 吞异常 10 处修复 | TODO | coding_cli/commands.py, agent/core/agent/compaction/summarizer.py, agent/products/personal_assistant/tools/web_search.py, agent/core/agent/runtime.py, personal_assistant/main.py, personal_assistant/gateway/background_session_events.py |
| R6 | 测试去重（3 对） | TODO | tests/unit/personal_assistant/test_inbound_pipeline_session.py + _dispatch.py, tests/unit/personal_assistant/test_gateway_im_connection.py + _behavior.py, tests/unit/test_background_hook_fork.py + _conversation.py |
