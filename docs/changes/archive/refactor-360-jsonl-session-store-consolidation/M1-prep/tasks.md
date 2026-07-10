# M1-prep Tasks

## 目标

产出 test-migration-plan.md（含所有 import 的逐行分类），修正 app.py:46 类型签名，修正内核设计SPEC.md 4处 stale 描述。

## 退出标准

- `test-migration-plan.md` 存在，列出所有涉及 `agent.platform.persistence.session.(jsonl_store|sqlite_store|serializers|base)` 的测试文件，每条标 a/b/c 分类，(c) 类注明等价覆盖来源或 "needs new test before delete"
- `mypy` 不再为 app.py 该行报错
- `grep "SQLiteSessionStore\|SessionStore 持久化抽象接口" docs/内核设计SPEC.md` 返回零
- `pytest tests/ -m "not e2e"` 不回归（base: 211 失败）

## 测试策略

本 milestone 是纯文档 + 代码结构修改（无逻辑改动），测试策略为：
- R1: test-migration-plan.md 是文档产出，无需 C1 测试。提交含分类表的 plan 文件。
- R2: app.py:46 类型签名修改 — 写一个 mypy 检查脚本作为 C1（确认当前有 stale 类型），C2 修改 import + 签名，C3 文档。
- R3: SPEC.md stale 修正 — 写 grep 命令确认 stale 存在作为 C1，C2 修正，C3 文档。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 产出 test-migration-plan.md（逐行分类） | DONE |
| R2 | app.py:46 类型签名 SessionStore → JsonlSessionStore | DONE |
| R3 | 内核设计SPEC.md 4处 stale 修正 | DONE |
