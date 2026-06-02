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

### R3 — IM 死代码删除 + 三件套提取 + 测试 import 重定向

- Context: `IM/models.py`+`IM/repositories.py` 是零生产引用的 facade，27个测试经它们绕道；`smoke_runtime.py` 全仓零引用；`IM/domain/__init__.py` re-export 无消费者；db.py/repositories.py/event_service.py 各持私有 `_optional_text` + db/repositories 各持 `_is_no_reply_protocol_token`/`_preview_from_event`。
- Decision: 新建 `IM/infra/_helpers.py`（含静默版 `_optional_text`/`_is_no_reply_protocol_token`/`_preview_from_event`）；删除三个死代码文件；清空 `IM/domain/__init__.py` re-export；27 个测试文件 import 重定向到 `IM.domain.models`/`IM.infra.repositories`；注意 `gateway_handler.py` 的 `_optional_text` 抛 ValueError（行为差异），不替换为共享版。
- Rationale: 遵循决策 3（行为差异保留），遵循决策 6（死代码删除）。
- Evidence:
  - Tests: IM tests 313 passed (2 个基线失败)；collect-only 316 tests 无 import 错误
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: R3 commit hash（本次）
- Commits: C1=（同 R1）, C2=（本次 R3 实现）, C3=（本次文档）
- Next: R4 personal_assistant _utils.py 提取

### R5 — 吞异常 10 处修复

- Context: commands.py 3 处(silent pass/traceback混用/json silent)；summarizer.py 1 处；web_search.py 1 处；runtime.py 1 处；main.py 6 处（_consume_task+4个observer+shutdown）；background_session_events.py 1 处。
- Decision: 各处按 design 策略处理（warning+fallback保持/日志可观测/repr fallback），所有正常路径返回值和控制流不变。
- Rationale: motivation Q3："不一定是加日志，有的可能是需要直接报错"——按情况处理，不一刀切。
- Evidence:
  - Tests: `pytest -m "not e2e"` 2321 passed (2 baseline fails)；contract 全绿
  - Entry: N/A（失败路径修复，不影响正常用户流程）
  - Frontend State Matrix: N/A; Browser QA: N/A; E2E/Regression: N/A; Visual/Interaction: N/A
- Rollback: c6e77592
- Commits: C1=（同 R1）, C2=c6e77592, C3=（文档）

### R6 — 测试去重（3 对）

- Context: 3 对重复测试文件总计 ~4000 行。
- Decision: 删 `test_inbound_pipeline_dispatch.py`（session 的严格子集）；删 `test_background_hook_fork_conversation.py`（fork 的严格子集）；删 `test_gateway_im_connection.py` 并将其唯一测试 `test_im_connection_does_not_disconnect_on_downstream_error_frame` 合并到 `_behavior.py`。
- Rationale: 严格子集直接删；有唯一测试的先迁移再删，保留测试覆盖。
- Evidence:
  - Tests: 3 个整合后文件共 52 passed；全套 `pytest -m "not e2e"` 2321 passed
  - Entry: N/A; Frontend/Browser/E2E/Visual: N/A
- Rollback: R6 commit（本次）
- Commits: C1=（同 R1）, C2=（本次）, C3=（本次文档）

<!-- 每个 roadpoint 完成后在此追加 -->
