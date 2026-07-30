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
- Commits: C1=N/A（无独立测试文件）, C2=a0fff27, C3=（含入计划提交 ca9b671）
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

- Context: 需要一个"产品解析入口"，接收 ProductProfile + repo_root 输出可注入对象；runtime 不能感知 Profile。
- Decision: `bootstrap_product(profile, repo_root) -> ResolvedProductConfig`；内部调用 `build_hook_registry` + `build_tool_registry`；`session_store=None`（M75 补 store path）。
- Rationale: 复用现有 loader；bootstrap 是 platform 层唯一知道 Profile 的地方，runtime/loop 完全不变。
- Evidence:
  - Tests: pytest -q → 5 pre-existing failed, 470 passed (+6 new green)
  - Entry: `bootstrap_product(profile=LOCAL_CODING_PROFILE, repo_root=Path.cwd())` 可用，返回 tool_registry/hook_registry 非空
- Rollback: 回退到 ae9492b (R74.1 C1)
- Commits: C1=e24479d, C2=0dcfc3d, C3=pending
- Next: R74.3 local_coding ProductProfile stub

---

### R74.3 local_coding ProductProfile stub

- Context: 需要一个与当前行为完全等价的 ProductProfile，使 app.py 迁移后无行为变化。
- Decision: `platform/products/local_coding.py` 中 `LOCAL_CODING_PROFILE`，`default_system_prompt=DEFAULT_SYSTEM_PROMPT`，`config_namespace="nanocode"`，tool/hook ids=None（继承平台全量默认）。
- Rationale: None 语义"使用平台全量默认"与当前 `build_tool_registry` 调用等价，零行为差。
- Evidence:
  - Tests: pytest -q → 5 pre-existing failed, 475 passed (+5 new green)
  - Entry: `from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE` 可用
- Rollback: 回退到 3744a85 (R74.3 C1)
- Commits: C1=3744a85, C2=b8e90b3, C3=pending
- Next: R74.4 server/app.py 接受 ProductProfile

---

### R74.4 server/app.py 接受 ProductProfile

- Context: `create_app` 当前手动拼装 tool/hook registry；需要支持通过 ProductProfile 驱动，同时保持无 profile 调用行为不变。
- Decision: 新增 `product_profile: ProductProfile | None = None`，当非 None 时调用 `bootstrap_product`；explicit registry 参数优先级 > profile > 平台默认（三档兜底链）。
- Rationale: TYPE_CHECKING guard 避免在 import 时拉入 platform 层；延迟 import `bootstrap_product` 保持启动开销不变。原有 9 个测试全绿。
- Evidence:
  - Tests: pytest -q → 5 pre-existing failed, 480 passed (+5 new green)
  - Entry: `create_app(product_profile=LOCAL_CODING_PROFILE)` 返回 FastAPI app，`app.state.tool_registry` 非空
- Rollback: 回退到 02bd18e (R74.4 C1)
- Commits: C1=02bd18e, C2=b9c1c61, C3=pending
- Next: Milestone 整体集成到 main
