# M4: tests-e2e — tasks

## 目标

将 `tests/e2e/` 下 10 个引用 `(C) SQLiteSessionStore / (B) JsonlSessionStore(platform 层)` 的文件改为走 `SessionService(store=JsonlSessionStore(data_dir=...))` 真实路径（(A) 核心层）。同时去掉 `test_personal_assistant_main_e2e.py` 中 2 个 workspace_root 测试的 `@pytest.mark.xfail` 标记，验证 issue #25 bug 已通过 (A) 路径修复。

## 退出标准

- 10 个 e2e 文件不再 import `agent.platform.persistence.session` 的 store
- 2 个 workspace_root 测试去掉 xfail 标记且 pass
- `pytest tests/e2e/` 全绿（含 workspace_root 转 pass）
- 整套 `pytest tests/` 不回归

## 测试策略

这是重构类迁移：行为不变，只改 session store 注入路径。
- C1: 确认当前基线状态（10 fail + 2 xfail），记录失败原因
- C2: 批量迁移 10 文件 + 修复 _runtime_pwd_for_workspace 函数 + 去 xfail
- 验证：`pytest tests/e2e/<file>` 逐个绿，最后整套 `pytest tests/` 全绿

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测试基线确认 + tasks.md | DONE |
| R2 | 迁移 8 个简单 e2e 文件（直接替换 store 构造） | DONE |
| R3 | 迁移 test_personal_assistant_main_e2e.py + 去 xfail | DONE |
| R4 | 整套回归确认 | DONE |
