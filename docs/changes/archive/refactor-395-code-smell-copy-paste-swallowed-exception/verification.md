# Verification Report: refactor-395

Round: 1 | Verifier: verifier-r1 | Date: 2026-06-03

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 6/6 Roadpoints complete，spec 所有 requirement 有实现 |
| Correctness | 所有核心场景覆盖，行为保持验证通过 |
| Coherence | 7/7 关键决策遵守 |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks: 6/6 complete

M1-dedup-and-exception-fixes 的全部 6 个 Roadpoint（R1-R6）均已标 DONE，代码核实与文档一致：

- R1: `agent/core/utils/time.py` + `fileio.py` 新建，`hooks/runner.py` 新增 `log_hook_diagnostics()`，`TERMINAL_RUN_STATUSES` 经 sdk re-export，11 处 `logger.warn()` → `logger.warning()`
- R2: `platform/llm/providers/common.py` 新建（`extract_non_negative_int`），`platform/tools/presentation.py`（`display_path`）、`base.py`（`WiringMixin`）扩展，`builtins/_shared.py` 新建（`_normalize_optional_text`）
- R3: `IM/models.py`、`IM/repositories.py` 已删，`personal_assistant/smoke_runtime.py` 已删，`IM/domain/__init__.py` re-export 清空，`IM/infra/_helpers.py` 新建，~27 个测试文件 import 重定向
- R4: `personal_assistant/_utils.py` 新建（`_require_text` ValueError 变体 + `_optional_text`），main.py 内 RuntimeError 变体留原地，`coding_cli` 改用 `from agent.sdk import TERMINAL_RUN_STATUSES`
- R5: 10 处吞异常全部修复（见 Correctness §3.2）
- R6: `test_inbound_pipeline_dispatch.py`、`test_background_hook_fork_conversation.py`、`test_gateway_im_connection.py` 已删，唯一测试迁入 `_behavior.py`

### Spec 覆盖

- 14 处 Copy-paste 重复：已消除（生产 9 + 测试 3 + 常量 2）
- 10 处吞异常：已修复
- 11 处废弃 API：0 残留（`grep -r "logger.warn(" src/` 零结果）
- 4 项死代码：全删，测试 import 0 残留（`grep -r "from IM.models|from IM.repositories|smoke_runtime" src/ tests/` 零结果）

退出标准验收：
- `pytest -m "not e2e"`: 2321 passed, 2 failed（均为基线已有 `/tmp` vs `/private/tmp` 路径差异，与本 unit 无关）
- `pytest tests/contract/`: 97 passed
- `pytest --collect-only`: 无 import 错误

---

## Correctness

### 行为保持验证（spec Scenarios）

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| IM 聊天 / 发送接收消息不受影响 | 重构未动 IM 消息路径；IM 三件套收敛到 `_helpers.py` | `tests/im_service/` 313 passed | covered |
| 群聊 @mention 功能不受影响 | gateway_handler.py `_optional_text` ValueError 变体保留原地 | 现有 group 相关测试通过 | covered |
| Agent 对话 / 工具调用不受影响 | `utc_now_iso`/`atomic_write` 等提取后行为等价 | `tests/unit/agent/` 全绿 | covered |
| Coding CLI REPL 交互不受影响 | REPL send loop 改走 `_print_repl_turn_error_block`（既有展示层） | `tests/unit/coding_cli/` 全绿 | covered |
| 权限请求展示不受影响 | `commands.py:415-420`：JSON 序列化失败改 repr fallback | 现有权限测试通过 | covered |
| Gateway 启停 / 配置解析不受影响 | `_read_section` 改 warning+fallback（不 raise），控制流不变 | config 相关测试全绿 | covered |
| 测试套件全部通过 | `pytest -m "not e2e"` 2321 passed | — | covered |

### 吞异常修复 10 处核实

| 位置 | 修复策略 | 正常路径不变 |
|---|---|---|
| `commands.py` `_read_section` | `logger.warning` + 返回 `{}`（`commands.py:1158`） | 是 |
| `commands.py` REPL send loop | 改走 `_print_repl_turn_error_block`（`commands.py:723-733`） | 是 |
| `commands.py:415-420` 权限请求 JSON 序列化 | `repr(tool_input)` fallback | 是 |
| `compaction/summarizer.py:72-74` | `logger.exception` + 保持返回 `_fallback_summary()` | 是 |
| `web_search.py:74-78` `_search_brave` | `logger.warning` + fallback to duckduckgo | 是 |
| `runtime.py:1248-1254` permission_resolved 发布器 | `logging.getLogger(...).warning(...)` | 是 |
| `main.py:_consume_task_exception`（`main.py:2844-2850`） | `asyncio.CancelledError: pass` + `Exception: logger.exception` | 是 |
| `main.py` IM observer 4处（`2116,2171,2245,2312`） | `_send()` helper 统一加 `logger.warning`，保持 suppress 语义 | 是 |
| `main.py:1053-1058` gateway shutdown | `try/except` 替换 `suppress(Exception)`，加 `logger.warning` | 是 |
| `background_session_events.py:89-95` subscriber stop | `CancelledError: pass` + `Exception: logger.debug` | 是 |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策1: `TERMINAL_RUN_STATUSES` 由 `RunStatus` 派生，经 sdk re-export | 是 | `runs/registry.py`: `frozenset(s.value for s in (RunStatus.COMPLETED, ...))` → `sdk/__init__.py` re-export；`coding_cli/*.py` 均改 `from agent.sdk import TERMINAL_RUN_STATUSES` |
| 决策2: BG terminal set 枚举版各自就地收敛，不与字符串版合并 | 是 | `background_tasks/registry.py` + `platform/background_tasks/task_store.py` 独立处理；未合并 |
| 决策3: 跨包 `_require_text`/`_optional_text` 接受 N→2，按调用点行为保留分歧 | 是 | `personal_assistant/_utils.py` ValueError 变体；`main.py:2556` RuntimeError 变体留原地；`IM/infra/_helpers.py` 静默版；`gateway_handler.py:2033` ValueError 变体留原地（progress.md R3 注：不替换）|
| 决策4: 只动错误路径，正常路径零改动 | 是 | 10 处修复均在 except 块内加 log/repr，返回值/控制流不变（见 Correctness §3.2） |
| 决策5: `logger.warn()` → `logger.warning()` 机械替换 | 是 | `grep -r "logger.warn(" src/` 零结果 |
| 决策6: 死代码删除 + 测试 import 重定向 | 是 | 3 个文件已删，`IM/domain/__init__.py` 仅余 docstring，`grep ... tests/` 零残留 |
| 决策7: 单 M1，worker 内按包走 roadpoint | 是 | 单 PR，6 roadpoint 顺序推进 |

### 模块边界遵守

- `personal_assistant/_utils.py` 未 import `agent.core`/`agent.platform`（只定义纯函数）
- `IM/infra/_helpers.py` 未 import `agent`/`personal_assistant`
- `coding_cli` 仅经 `agent.sdk` import `TERMINAL_RUN_STATUSES`，未 import core 内部
- `tests/contract/` 97 passed，依赖方向未破

---

## Issues

### CRITICAL（提 PR 前必须修）

无

### WARNING（应该修）

- **progress.md R4 段缺失**：`M1-dedup-and-exception-fixes/progress.md` 中 R4 的 progress 记录缺失（R3 结尾写 "Next: R4"，之后直跳到 R5）。代码实现已完成，但文档断档使 reviewer 无法通过 progress.md 追溯 R4 决策。
  - 建议：在 `docs/changes/refactor-395-code-smell-copy-paste-swallowed-exception/M1-dedup-and-exception-fixes/progress.md` 的 R3 和 R5 之间补充 R4 小节，格式与其他 roadpoint 一致（Context / Decision / Rationale / Evidence / Commits）。

### SUGGESTION（可以修）

- **`runtime.py:1251` 临时 import logging**：permission_resolved 发布器的修复使用了 `import logging`（行内 import）而非文件顶部已有的模块级 logger。
  - 建议：在 `runtime.py` 顶部已有 logger 的文件中，改用模块级 `_log = logging.getLogger(...)` 或既有 logger 名称，去掉行内 `import logging`（`runtime.py:1251-1253`）。

---

All checks passed (test suite 2321/2321 non-e2e, contract 97/97). Ready for PR, with 1 warning (progress.md doc gap) noted above.
