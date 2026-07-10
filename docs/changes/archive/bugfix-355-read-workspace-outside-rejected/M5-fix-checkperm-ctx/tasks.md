# bugfix-355-M5 tasks

## 目标

修复 R2-#1（blocking）：`auto_mode_gate.py:673` 以 `ctx=None` 调用 `check_permissions`，
导致 WriteTool/EditTool 路径检查抛 `AttributeError`，被 hook runner 静默吞掉，
安全链路等价 passthrough。

修正 R2-#2（minor）：design.md Anchor O Corrigendum 仍指向错误路径；
应为 kernel CWD（`<repo_root>/.nanocode/config.yaml`），而非 agent workspace_root。

## 退出标准

- `[reviewer]` R2-#1 / R2-#2 在 round 3 复验通过：`~/.bashrc.test.bak` 弹卡片不再被吞 AttributeError；Anchor O 路径与 kernel 实际读取一致
- `[worker]` 新增/扩展集成测试：WriteTool.check_permissions 在 hook ctx 注入完整路径下被调用时，不抛 AttributeError、能真正命中 ask 分支；反向断言 hook runner 不会静默吞工具权限检查异常（再出 ctx 不全可立刻红）

## 测试策略

- 后端修复，补集成测试（扩展 test_tool_registry_injection_integration.py）
- 新增反向回归测试：传 None ctx 给 check_permissions 应该 fail-loud（log + ask），不静默 passthrough
- 测试命令：`pytest tests/integration/test_tool_registry_injection_integration.py -xvs`

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 集成测试 — 反向断言 ctx=None 时 check_permissions 崩溃可观测（Red） | DONE |
| R2 | fix auto_mode_gate：传真实 ctx + fail-loud 机制 | DONE |
| R3 | 文档修正：design.md Anchor O Corrigendum 路径 | DONE |

