# M1-prep Progress

## 启动记录

基线：211 个 pre-existing 测试失败（非本 M1 范围），1924 pass。

---

### R1 — test-migration-plan.md 产出

- Context: design.md 说 76 处，实际 grep 结果是 33 行 import（从 `agent.platform.persistence.session.*`），另有 26 行已是正确的 (A) 路径。
- Decision: 产出 `test-migration-plan.md`，含 33 行全量分类（a/b/c）+ Milestone 分派映射表 + (A) API 变更注意事项。
- Rationale: 实际行数 < 设计估算，但分类质量更重要。逐文件人工分析目的后分类。
- Evidence:
  - Tests: N/A（纯文档产出）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: cd110493（plan commit）
- Commits: C1=cd110493（plan.md 即 C1+C2 合一，无代码实现步骤）

### R2 — app.py:46 类型签名修正

- Context: `create_app` 参数 `session_store: SessionStore | None` 引用了即将被删除的 ABC `SessionStore`（来自 platform/persistence/session/base.py），而 (A) `JsonlSessionStore` 不继承此 ABC。
- Decision: 将 import 从 `agent.platform.persistence.session.base import SessionStore` 改为 `agent.core.session.jsonl_store import JsonlSessionStore`，参数类型改为 `JsonlSessionStore | None`。
- Rationale: 决策 3 — 删完 (B)(C) 后只有一个 store，不引入 Protocol，直接具化类型。
- Evidence:
  - Tests: `pytest tests/ -m "not e2e"` 208 failed（基线 211，无新增失败）
  - Entry: `python -c "from agent.platform.http_api.app import create_app; import inspect; sig = inspect.signature(create_app); print(sig.parameters['session_store'].annotation)"` → `agent.core.session.jsonl_store.JsonlSessionStore | None` ✓
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 2d0d3339
- Commits: C1=（inline verify），C2=2d0d3339

### R3 — 内核设计SPEC.md 4处 stale 修正

- Context: `docs/内核设计SPEC.md` 第 48、71-72、346-348 行描述的是老的 store 架构（SessionStore ABC + SQLiteSessionStore + JSONLSessionStore）。F-330 未更新此文档。
- Decision: 按决策 4 精确修改 4 处：删第 48 行 store.py 行，合并 71-72 行为 core/session/jsonl_store.py 行，合并 346-348 行三件套为单行 JsonlSessionStore。
- Rationale: 最小改动，只改与 (A)(B)(C) 直接相关的部分。
- Evidence:
  - Tests: `grep "SQLiteSessionStore|SessionStore 持久化抽象接口" docs/内核设计SPEC.md` 返回零 ✓
  - Entry: 文档修正，无运行时入口
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 4b7fe9c1
- Commits: C1=（grep verify），C2=4b7fe9c1，C3=（本文档 commit）
- Next: 本 milestone 已完成，准备合入 unit 分支

