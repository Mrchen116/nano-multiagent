# PROGRESS/M74 - 多产品架构重构一期：产品装配契约与 bootstrap 入口

## Milestone 概述
- milestone_id: M74
- branch: milestone/M74
- worktree: .nano_multiagent/worktrees/M74
- test_command: pytest -q
- baseline: 5 个预存失败（contract x2, integration x2, unit x1），与 M74 无关

---

### R74.0 修复测试集合错误（__init__.py 命名冲突）

- Context: `tests/unit/test_app_factory.py` 与 `tests/im_service/unit/test_app_factory.py` 同名导致 pytest collection 报 import mismatch；需要给所有 test 目录加 `__init__.py`。
- Decision: 在 tests/ 下所有 10 个目录（含 im_service 子目录）创建空 `__init__.py`。
- Rationale: pytest 默认 rootdir 模式下同名模块冲突，加 `__init__.py` 使目录成为 package 后可用全限定名区分。
- Evidence:
  - Tests: pytest -q 无 collection error，457 passed + 5 pre-existing failed
  - Entry: `touch tests/__init__.py tests/unit/__init__.py ...`（10个目录）
- Rollback: 删除所有 __init__.py 文件
- Commits: C1=pending, C2=pending, C3=pending
- Next: R74.1 ProductProfile dataclass

---

### R74.1 ProductProfile + ResolvedProductConfig 数据契约

- Context: 引入产品装配契约，为后续多产品路由建立"接缝"；不做 runtime 内 product 分支。不引入 ABC/Protocol，用简单 dataclass 保持低耦合。
- Decision: `platform/product.py` 两个 dataclass：`ProductProfile`（10字段，全有默认值）+ `ResolvedProductConfig`（5字段）。使用 `TYPE_CHECKING` guard 避免在 import 时拉入具体注册表。
- Rationale: dataclass 比 TypedDict 易扩展，比 pydantic 依赖轻；`TYPE_CHECKING` guard 保持 platform 层不强依赖 tools/hooks/session 模块。
- Evidence:
  - Tests: pytest -q → 5 pre-existing failed, 464 passed (7 new green)
  - Entry: `from nano_multiagent.platform.product import ProductProfile` 可用
- Rollback: 回退到 ae9492b (C1 commit)
- Commits: C1=ae9492b, C2=33cf429, C3=pending
- Next: R74.2 platform/bootstrap.py

---

### R74.2 platform/bootstrap.py

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: C1=pending, C2=pending, C3=pending
- Next: R74.3

---

### R74.3 local_coding ProductProfile stub

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: C1=pending, C2=pending, C3=pending
- Next: R74.4

---

### R74.4 server/app.py 接受 ProductProfile

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: C1=pending, C2=pending, C3=pending
- Next: Milestone 集成
