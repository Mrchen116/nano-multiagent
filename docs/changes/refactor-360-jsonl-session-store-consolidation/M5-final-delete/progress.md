# M5: final-delete — progress

## 开工报信

已读懂 M5，范围 = 删 5 个死代码文件 + 清 `__init__.py` 导出 + 关闭 issue #25，影响文件：
- `src/agent/platform/persistence/session/sqlite_store.py`
- `src/agent/platform/persistence/session/jsonl_store.py`（(B) 平台层）
- `src/agent/platform/persistence/session/base.py`
- `src/agent/platform/persistence/session/serializers.py`
- `src/agent/core/session/store.py`
- `src/agent/platform/persistence/session/__init__.py`（清导出）

基线确认：`pytest tests/`（忽略 acceptance）167 failed, 1983 passed — 167 个均为 pre-existing（main 分支同样失败验证）。开始实施。

---

### R1 — 扫描引用 + 确认等价覆盖 + C1 verification commit

- Context: 删前必须确认没有漏迁的 import，(c) 类等价覆盖必须到位
- Decision: grep 扫 src/ 和 tests/ 全部引用；检查 (c) 类两个文件的等价覆盖状态
- Rationale: design.md 决策 1 说明"最后删 store 时若某处漏迁，直接报错暴露"，M5 作为终删 milestone，必须完成最终确认才能执行删除
- Evidence:
  - `grep -rn "SQLiteSessionStore" src/` → 只剩 sqlite_store.py 内部声明，无外部引用
  - `grep -rn "from .sqlite_store" src/` → `__init__.py` 一处 re-export（待清）
  - `grep -rn "from .base import SessionStore" src/` → 无生产代码引用
  - `grep -rn "from agent.platform.persistence.session import" src/ tests/` → 无 src 引用，tests 扫描确认为零
  - (c) 类等价覆盖：`test_session_store_persistence_integration.py` 第 38-55 行 `test_jsonl_store_persists_session_across_reopen` 已补（M4 工作，用 (A) JsonlSessionStore 验证跨 reopen 持久化语义）
  - (c) 类 test_platform_session_support_location.py serializers 断言：需删 serializers 相关断言，保留 SessionService + legacy root 两条
  - Tests: N/A（C1 只做扫描 + plan commit）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: e6ef3f3e（M4 合并 commit）
- Commits: C1=<待填>
- Next: R2 删 platform 层死文件

---

### R2 — 删 platform 层死文件 + 清 `__init__.py` 导出

- Context: 删 sqlite_store.py, jsonl_store.py(B), base.py, serializers.py；清 __init__.py；修 test_platform_session_support_location.py 删 serializers 相关断言
- Decision: 按文件逐个 git rm + 修 __init__.py 只保留 SessionService re-export
- Evidence:
  - Tests: `pytest tests/ -q --tb=no --ignore=tests/acceptance` → 待填
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R1 C1 commit
- Commits: C2=<待填>, C3=<待填>
- Next: R3 删 store.py + 最终验证

---

### R3 — 删 core/session/store.py + 最终验证 + issue 关闭

- Context: 确认 SessionStore ABC 无生产代码引用后删除；跑最终退出标准检查
- Decision: git rm store.py + 跑全套 grep 退出标准 + 关闭 issue #25
- Evidence:
  - Tests: `pytest tests/ -q --tb=no --ignore=tests/acceptance` → 待填
  - Exit criteria grep: 待填
  - Issue #25: 待关闭
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R2 commit
- Commits: C2=<待填>, C3=<待填>
- Next: 集成到 unit 分支
