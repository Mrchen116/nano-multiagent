# refactor-395-M1 Progress

## 启动备注

基线测试：`pytest -m "not e2e"` 有 1 处已存在失败（`test_get_agent_config_prefers_live_gateway_snapshot`，macOS `/tmp` vs `/private/tmp` 路径符号链接差异，与本 milestone 无关）。其余全绿。

---

### R1 — core utils + TERMINAL_RUN_STATUSES + sdk 暴露 + 废弃 API

- Context: 5 个模块各有私有 `_utc_now_iso`，4 个类各有私有 `_log_hook_diagnostics` static method，2 处 `_atomic_write`，3 处字符串终态字面量，11 处废弃 `logger.warn()`。`HookLogger` 只有 `warn()` 不是标准命名。
- Decision: 新建 `agent/core/utils/time.py` + `fileio.py`；在 `hooks/runner.py` 新增模块级 `log_hook_diagnostics()`；在 `runs/registry.py` 新增 `TERMINAL_RUN_STATUSES`（frozenset[str]，由 RunStatus 派生）并经 sdk re-export；background_tasks `_TERMINAL_STATUSES`（枚举版）platform 侧 import core；`HookLogger` 添加 `warning()` 别名；11 处 `logger.warn()` → `logger.warning()`。
- Rationale: 各副本逐字节等价，提取后唯一真源。`HookLogger.warning()` 与标准 `logging.Logger` 命名对齐，旧 `warn()` 保留向后兼容。
- Evidence:
  - Tests: `pytest tests/unit/test_refactor_395_utils.py` 8 passed; `pytest -m "not e2e"` 2349 passed, 2 failed（均为基线已有 `/tmp` vs `/private/tmp` 问题）; `pytest tests/contract/` 97 passed
  - Entry: N/A（纯库代码重构，无对外 HTTP/CLI 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（重构，现有测试覆盖）
  - Visual/Interaction: N/A
- Rollback: C2 = b777ab67
- Commits: C1=26fdcc44, C2=b777ab67, C3=（本次）
- Next: R2 platform 共享 helper 提取

### R2 — platform 共享 helper 提取

- Context: 4 个 LLM provider 各有私有 `_extract_non_negative_int`；write/edit/read 各有 `_display_path`；bash/task_stop/agent 各有 `bind_wiring`/`_require_wiring`；task/agent 各有 `_normalize_optional_text`。
- Decision: 新建 `providers/common.py`（`extract_non_negative_int`）、`builtins/_shared.py`（`_normalize_optional_text`）；扩展 `presentation.py`（`display_path`）、`base.py`（`WiringMixin`）。
- Rationale: 各副本逐字节等价，落点遵守模块职责（presenters → presentation.py，工具 mixin → base.py）。
- Evidence:
  - Tests: 相关单测全绿（tools_builtins/write_edit/read/llm_mappers/task/agent/memory/skill_writer）；contract 97 passed
  - Entry: N/A（内部实现）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: fde3894c
- Commits: C1=（R2 无新失败测试，复用 R1 的 C1 作为进入态），C2=fde3894c, C3=（本次）
- Next: R3 IM 死代码删除 + 三件套提取 + 测试 import 重定向

<!-- 每个 roadpoint 完成后在此追加 -->
