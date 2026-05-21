# M3 unit-cli — Tasks

## 目标

修复 `tests/unit/` cli 簇的所有漂移，使 `pytest tests/unit -k "cli or sdk_client or managed_server or refactor_boundaries" -m "not e2e"` 退出 0；拆分 `test_cli_main.py`(2754 行) 为行为聚类的多个文件，拆前后用例数/通过数一致；该子树无 >400 行文件。

## 退出标准

- `pytest tests/unit -k "cli or sdk_client or managed_server or refactor_boundaries" -m "not e2e"` 退出码 0
- `test_cli_main.py` 已按行为聚类拆分，无单文件 >400 行
- 拆分前后用例数和通过数一致
- 所有漂移（send_message→submit_message、ManagedServerConfig 去 token、build_release_playbook_report 去 token、CLI 命令裁剪为 health/llm-config 子集、supported_commands 期望更新）已对齐现码

## 测试策略

被测行为来源：regression.md 的 1.2（sdk_client）、1.4（managed_server token）、1.5（build_release_playbook_report token）、1.6（CLI commands 裁剪）

所有测试已在 tests/unit/ 套件中：这是**已有测试对齐现码**的修复 milestone，不新建文件。
- 修漂移：直接修对应文件里的测试用例
- 拆巨型：test_cli_main.py(2754) 按行为聚类拆分为 ≤400 行/文件

入口验证：单元测试全是 mock，无真实进程，验证方式为 `pytest -k "cli or sdk_client or managed_server or refactor_boundaries"` 全绿。

## Roadpoints

| ID | 标题 | 状态 | 描述 |
|---|---|---|---|
| R1 | 修 sdk_client 漂移 | DONE | send_message → submit_message，删旧测试，验证用例数一致 |
| R2 | 修 managed_server 漂移 | DONE | ManagedServerConfig 去 token 参数 |
| R3 | 修 refactor_boundaries 漂移 | DONE | build_release_playbook_report 去 token、CLI commands 裁剪 |
| R4 | 拆 test_cli_main.py | DONE | 按行为聚类拆分，拆前后用例数/通过数一致 |
