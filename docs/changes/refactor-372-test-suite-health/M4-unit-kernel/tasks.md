# M4-unit-kernel Tasks

## 目标

修复 `tests/unit/` 非-cli 文件的漂移测试，删除一次性快照，去流水号重命名，拆分超 400 行文件，使
`pytest tests/unit -m "not e2e" --ignore=tests/unit/personal_assistant --ignore=tests/unit/IM -k "not (cli or sdk_client or managed_server or refactor_boundaries)"` 退出 0。

## 退出标准

- 测试命令退出 0（无 failed，xfail 计预期失败）
- `test_rerun_acceptance_runtime_helpers.py` 已删除（659 行 importlib-exec 反模式）
- `test_m170_runtime.py` 已删除（同属一次性快照，依赖 personal_assistant 内部不可用于单测）
- 流水号文件重命名：`test_m236_*` → `test_session_metadata_hookcontext.py`，`test_refactor353_corrigendum.py` 合并到语义上最近的文件
- 4 个 >400 行文件已拆分，拆前后用例数一致
- 该子树无 >400 行文件（或列明豁免原因）

## 测试策略

本 milestone 改的是测试文件本身，不改产品逻辑。
- 修漂移：对齐产品现码，不放宽产品契约
- 删快照：删前确认不贡献唯一回归价值
- 重命名/拆分：行为保持，用例数不变
- 后端纯逻辑，无前端 UI，所有验收通过 `pytest` 命令行确认

## 基线

`pytest tests/unit -m "not e2e" --ignore=tests/unit/personal_assistant --ignore=tests/unit/IM --ignore=tests/unit/test_m170_runtime.py -k "not (cli or sdk_client or managed_server or refactor_boundaries)"` → 16 failed, 1138 passed

（`test_m170_runtime.py` 在基线中因缺少 `websockets` 模块报收集错误，归入一次性快照待删）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 修漂移：create_app/run_cancel/task_tool/app_factory | DONE |
| R2 | 删一次性快照：test_rerun + test_m170_runtime | DONE |
| R3 | 去流水号重命名：test_m236 / test_refactor353 | DONE |
| R4 | 拆 test_tools_builtins (923→≤400) | DONE |
| R5 | 拆 test_background_hook_fork (843→≤400) | DONE |
| R6 | 拆 test_agent_loop (723→≤400) | DONE |
| R7 | 拆 test_auto_mode_gate (698→≤400) | DONE |

## 详细漂移清单（R1 范围）

| 文件 | 失败数 | 根因 | 修法 |
|---|---|---|---|
| `test_server_global_routes.py` | 5 | `create_app(auth_token=...)` 已去参数 | 改用无 `auth_token` 的签名 |
| `test_run_cancel.py` | 1 | 测试等待 `FAILED\|COMPLETED`，产品实际设为 `CANCELLED` (stop_reason=aborted) | 等待条件加 `CANCELLED` |
| `test_app_factory_with_profile.py` | 1 | `_RuntimeStub.create_session()` 缺 `parent_session_id` 参数 | mock 加该参数 |
| `test_task_tool_with_resolver.py` | 1 | `_RuntimeStub.create_session()` 缺 `parent_session_id` | mock 加该参数 |
