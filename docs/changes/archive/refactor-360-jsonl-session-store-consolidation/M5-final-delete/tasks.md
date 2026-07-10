# M5: final-delete — tasks

## 目标

终删 (B)(C) 死代码文件 + 抽象基类 + 清包导出 + 关闭 issue #25。

## 退出标准

- `grep -rn "SQLiteSessionStore|from agent.platform.persistence.session import |from .sqlite_store|from .base import SessionStore" src/ tests/` 返回零
- `ls src/agent/platform/persistence/session/` 只剩 `__init__.py` + `service.py`
- `ls src/agent/core/session/store.py` 不存在
- `mypy src/` 不为本 unit 触及代码报新错
- `pytest tests/` 全绿（允许 pre-existing failures，不新增）
- issue #25 关闭

## 测试策略

重构删除型任务，行为不变。现有测试套不回归即达标。
C1：先扫所有引用，确认无漏，补 (c) 类等价覆盖已到位的确认文档（verification commit）。
C2：删除 + 清包。
C3：文档（progress.md 补齐 + issue 关闭）。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 扫描引用 + 确认等价覆盖 + C1 verification commit | DONE |
| R2 | 删 platform 层死文件 + 清 `__init__.py` 导出 | DONE |
| R3 | 删 `src/agent/core/session/store.py` + 最终验证 + issue 关闭 | DONE |
