# refactor-395: 消除 Copy-paste 重复 + 修复吞异常 — 技术方案

> 对齐: motivation.md v1

> Unit branch: `unit/refactor-395` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

### 涉及范围

本 unit 改动落在四个包，按 motivation §影响范围 + 审查报告核实后的真实分布：

**Copy-paste 生产代码（提取共享，纯 agent 内部，无跨包问题）**
- `agent/core/`：`_utc_now_iso`（runtime/events.hub/runs.registry/session.jsonl_store/session.entries ×5）、`_log_hook_diagnostics`（runtime/loop/runs.registry/tools.registry ×4）、atomic-write 模式（skills/writer + memory/store ×2）
- `agent/platform/`：`_extract_non_negative_int`（llm/providers 下 anthropic·openai_compat 的 mapper+client ×4）、`_display_path`（tools/builtins write/edit/read ×3）、`bind_wiring`+`_require_wiring`（tools/builtins bash/task_stop/agent ×3）、`_normalize_optional_text`（tools/builtins task/agent ×2）

**Copy-paste 生产代码（跨包，"统一一处"不成立）**
- `_require_text`：4 处在 `personal_assistant/`（main/sync_client/im_connection/web_relay_adapter）+ 1 处在 `agent/products/personal_assistant/tools/send_message.py`。两包不能互 import。
- `_optional_text`：4 处在 `IM/`（infra.db/infra.repositories/application.event_service/ws.gateway_handler）+ 1 处在 `personal_assistant/channels/web_relay_adapter.py`。IM 与 PA 互不 import。
- IM 内三件套 `_is_no_reply_protocol_token`/`_optional_text`/`_preview_from_event`：infra.db + infra.repositories ×2，同包。

**Copy-paste 常量 `_TERMINAL_STATUSES`（审查报告误判为"同一常量 7 处"，实为三组语义不同的集合）**
- RunStatus 枚举版 `{COMPLETED,FAILED,CANCELLED}`：仅 `runs/registry.py` 1 处——**无重复**。
- BackgroundTaskStatus 枚举版 `{COMPLETED,FAILED,KILLED}`（成员异于上组）：`core/background_tasks/registry.py` + `platform/background_tasks/task_store.py` ×2。
- 字符串版 `{"completed","failed","cancelled"}`：`coding_cli`（text_runner/commands/events.repl_events ×3）+ `personal_assistant/gateway/inbound_pipeline.py` ×1。

**吞异常修复（motivation 锁定 5 处，非 fire-and-forget）**
- `coding_cli/commands.py`：`_read_section` 配置解析 `except Exception: pass`、REPL 发送循环 `traceback.print_exc()` 混入 broad except
- `agent/core/agent/compaction/summarizer.py`：`except Exception: return _fallback_summary()`
- `agent/products/personal_assistant/tools/web_search.py`：`_search_duckduckgo` + `_search_brave` 两处裸 except
- `personal_assistant/main.py`：`_consume_task_exception` 静默丢后台任务异常

**测试去重（3 对）**
- `tests/unit/personal_assistant/test_inbound_pipeline_session.py` ↔ `test_inbound_pipeline_dispatch.py`（15 函数 ~700 行）
- `tests/unit/personal_assistant/test_gateway_im_connection.py` ↔ `test_gateway_im_connection_behavior.py`（9 函数）
- `tests/unit/test_background_hook_fork.py` ↔ `test_background_hook_fork_conversation.py`（6 函数）

### 既有约束

- **依赖方向硬规则**（`tests/contract/` 自动验收）：`coding_cli`/`personal_assistant` **只能 import `agent.sdk`**，禁止 import `agent.core`/`agent.platform` 内部；`IM` 不 import `agent`；三产品包互不 import。
- `agent.sdk/__init__.py` 是唯一对外面，当前 re-export kernel + 若干 LLM config / profile 类型。任何 products 需要消费的 core 符号必须经此 re-export。
- agent 内核四层依赖：`platform → core + products`；`sdk → 全部`；`core` 不依赖 `platform`/`products`。共享模块落点不得逆转此方向。
- COMMENTING_GUIDE：提取出的 public helper 须写 Google 风格 docstring。

### 可复用能力

- `agent/platform/tools/base.py` **已存在** → `bind_wiring`/`_require_wiring` 的 mixin 落点，无需新建文件。
- `agent/platform/tools/presentation.py` **已存在** → `_display_path` 可并入（路径呈现属同一关注点）。
- `agent/core/ids.py` 是 core 既有 utils 风格参照；但 core **无 `utils/` 目录**，`_utc_now_iso` / atomic-write 需新建 `agent/core/utils/`（不硬塞进 ids.py，职责不同）。
- `coding_cli/commands.py` 内 line 663 已有 `_print_repl_turn_error_block` → REPL 吞异常修复直接复用，不新造错误展示。
- `RunStatus` 枚举（core）是字符串版终态集合的天然真源 → 派生而非另立字面量。

### 相关历史

无近期 unit 改动这些工具函数 / 常量区域。来源唯一：本目录 `code-review-report.md`（2026-06-02，7 维度并行扫描）。

## 架构总览

纯重构：不新增对外能力，只把"散落的同款代码收敛到单一真源 + 让 5 处静默失败可观测"。落点严格遵守分层与跨包边界——**能在单包内收敛的就单包收敛，跨包的接受 N→2 而非强凑 N→1**。

```
                    ┌──────────────────────── agent ────────────────────────┐
 收敛后新增/复用真源：                                                          │
                                                                              │
   core/utils/time.py      (new)  ← _utc_now_iso ×5                           │
   core/utils/fileio.py    (new)  ← atomic_write ×2                           │
   core/hooks/<shared>            ← _log_hook_diagnostics ×4                  │
   core/ : TERMINAL_RUN_STATUSES (frozenset[str], 由 RunStatus 派生) ──┐      │
   core/background_tasks/ : BG terminal set 收 ×2                      │      │
                                                                       │      │
   platform/llm/providers/common.py (new) ← _extract_non_negative_int ×4     │
   platform/tools/presentation.py  (复用) ← _display_path ×3                  │
   platform/tools/base.py          (复用) ← bind_wiring/_require_wiring ×3    │
   platform/tools/builtins/<shared>       ← _normalize_optional_text ×2      │
                                                                       │      │
   sdk/__init__.py : re-export TERMINAL_RUN_STATUSES ─────────────────┘      │
   └────────────────────────────────────────┬───────────────────────────────┘
                                             │ (products 只许走 sdk)
        ┌────────────────────────────────────┼────────────────────────────┐
        │ coding_cli                          │ personal_assistant          │
        │  text_runner/commands/repl_events   │  _utils.py (new):           │
        │   → import TERMINAL_RUN_STATUSES    │    _require_text ×4 收      │  IM (独立)
        │     from agent.sdk                  │    _optional_text ×1 收      │   infra/_helpers.py (new):
        │  commands.py 吞异常 ×2 修            │  inbound_pipeline → sdk 终态 │    _optional_text ×4 收
        │                                     │  main.py _consume_task 修    │    _is_no_reply_token 收
        └─────────────────────────────────────┘  send_message(agent 侧)     │    _preview_from_event 收
                                                   _require_text 留 agent    │   gateway_handler/event_service
                                                                             │    → import _helpers
        agent/products/.../web_search.py 吞异常 ×2 修
        agent/core/.../compaction/summarizer.py 吞异常 ×1 修
```

before：每类同款代码在 N 个文件各持一份副本，改一处要同步改 N 处（`_require_text` 已因此出现 RuntimeError/ValueError 不一致）；5 处静默 `except: pass` 让失败完全不可见。
after：单包内收敛到唯一真源；跨包按边界收敛到每包一份（N→2）；字符串终态集合经 sdk 单一来源；5 处失败路径有日志 / 报错 / sentinel。**正常路径行为逐字节不变**。

## 关键决策

### 决策 1: `_TERMINAL_STATUSES` 字符串版去重 — 经 sdk 暴露 RunStatus 派生的 canonical

- **选择**: 在 `agent/core` 从 `RunStatus` 派生 `TERMINAL_RUN_STATUSES: frozenset[str]`（如 `frozenset(s.value for s in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED))`），经 `agent.sdk` re-export；`coding_cli`（×3）+ `personal_assistant/inbound_pipeline`（×1）改为 `from agent.sdk import TERMINAL_RUN_STATUSES`。
- **理由**: 字符串集合是 `RunStatus` 的序列化形态，真源在枚举。派生 + sdk 单出口让 products 不再各持字面量，且自动随枚举演进。符合"products 只走 sdk"硬约束。
- **拒绝**: ①审查报告建议"放 `core.types` 让所有人 import"——违反 products 不得 import core 内部。②products 各留字面量——本 unit 目标就是消除它。③把三组集合合并为一个常量——三组语义/成员（CANCELLED vs KILLED）/类型（str vs enum）都不同，合并引 bug。
- **风险**: 派生表达式必须与原字面量集合逐元素一致（`{"completed","failed","cancelled"}`），需单测锁定。

### 决策 2: BackgroundTaskStatus / RunStatus 枚举版 — 各自就地收敛，不并入决策 1

- **选择**: BG 枚举版（`core/background_tasks/registry` + `platform/background_tasks/task_store` ×2）收敛到 `core/background_tasks/` 单一定义（platform 侧 import core 合法，方向正确）；RunStatus 枚举版（`runs/registry` 1 处）**原地不动**（无重复）。
- **理由**: 成员不同（KILLED≠CANCELLED），与字符串版/RunStatus 版语义不可互换。强行合并是制造 bug。
- **拒绝**: 三组统一——见决策 1 拒绝项③。
- **风险**: 无。

### 决策 3: 跨包重复 `_require_text` / `_optional_text` — 接受 N→2，每包一份本地真源

- **选择**: `_require_text` → Gateway 包 4 处收敛到新建 `personal_assistant/_utils.py`，agent 侧 `send_message.py` 1 处留在 agent（或并入 agent 既有就近共享，不与 Gateway 共享）。`_optional_text` → IM 4 处收敛到新建 `IM/infra/_helpers.py`（连同 `_is_no_reply_protocol_token`/`_preview_from_event`），PA 侧 web_relay 1 处并入 `personal_assistant/_utils.py`。
- **理由**: 依赖硬规则禁止 IM↔PA、products↔agent 内部互 import，物理上无法 N→1。每包一份已是该约束下的最优收敛。
- **拒绝**: 为共享强行新建跨包公共包——会引入新的依赖边，破坏现有干净分层，得不偿失。
- **风险**: ⚠️ **行为差异**。报告指出 `_require_text` 各副本 RuntimeError vs ValueError 不一致、`_optional_text` 各副本"抛 ValueError vs 静默 None"不一致。**本 unit 是纯重构，不在此修 bug**：提取时按**每个调用点**核对它当前依赖哪种行为，若同包内副本行为一致则取该行为；若同包内副本已有分歧，保持各调用点语义不变（必要时保留两个命名变体而非强统一）。任何"统一行为"的动作都要确认无调用点依赖旧分歧，否则属行为变更，超范围。

### 决策 4: 5 处吞异常 — 只动错误路径，正常路径零改动

- **选择**: 各处策略——
  - 配置解析（`commands.py _read_section`）：捕获后 `logger.warning` 含异常详情再返回 fallback（或对不可恢复者直接 raise）；不再静默当文件不存在。
  - REPL 发送循环（`commands.py`）：去掉 `traceback.print_exc()`，改走既有 `_print_repl_turn_error_block`，错误归入结构化展示层。
  - compaction summarizer：捕获后 `logger.exception` 记录，**保持返回 `_fallback_summary()` 不变**（不改返回值契约，只加可观测）。
  - web_search 两 provider：捕获后 `logger.warning` 含 provider + 错误，再返回空列表（保持空列表契约）。
  - `_consume_task_exception`：`except asyncio.CancelledError: pass` + `except Exception: logger.exception(...)`。
- **理由**: motivation Q3 锁定"只修真正隐藏问题处，策略因情况而异（raise/log/sentinel），不一刀切"；fire-and-forget 不动。compaction/web_search 保留原返回值是为不破坏调用方正常路径。
- **拒绝**: ①给所有 broad-except 加日志——超 motivation 锁定的 5 处范围。②compaction 改 sentinel 让调用方区分真摘要/fallback——会改变调用方契约，属行为变更，本 unit 仅加日志可观测。
- **风险**: 配置解析改 raise 需确认无调用方依赖"坏配置当不存在"的旧行为；以现有测试为护栏。

### 决策 5: milestone 颗粒度 — 单 M1，worker 内按包走 roadpoint

- **选择**: 单 M1，不拆 multi-milestone。worker 内部按 R1 core utils + sdk 暴露 → R2 platform → R3 IM → R4 personal_assistant → R5 吞异常 → R6 测试去重 顺序推进。
- **理由**: 纯行为保持重构无任何用户可观察里程碑（§4.4 试金石两条均不满足）；跨包共享符号 `TERMINAL_RUN_STATUSES`（core→sdk→products）使"按包并行"的模块并非真独立；并行 worktree 集成历史上不可靠。单 worker 持全局上下文一致落跨包决策、一次性可审 PR、无并行合并风险。
- **拒绝**: 按包拆 4-5 个并行 milestone——横切式拆分变体，每片无独立价值，且被跨包共享符号耦合。
- **风险**: 单 PR 体量较大（~40 文件）。缓解：worker 按 roadpoint 分多次 commit（每包一组），reviewer/architect 可逐 commit 审。

## 接口与数据流

本 unit 不新增对外 API、不改任何函数签名的对外契约。新增/变动的仅是**内部共享符号的可见性**：

- `agent/core/utils/time.py`：`def utc_now_iso() -> str`（替代 5 处私有 `_utc_now_iso`）。
- `agent/core/utils/fileio.py`：`def atomic_write(path: Path, data: str | bytes, *, ...) -> None`（替代 2 处行内 atomic-write）。
- `agent/core`：`TERMINAL_RUN_STATUSES: frozenset[str]`（由 `RunStatus` 派生）。
- `agent/sdk/__init__.py`：`__all__` 增 `TERMINAL_RUN_STATUSES`，新增 `from agent.core... import TERMINAL_RUN_STATUSES`。
- `agent/platform/llm/providers/common.py`：`def extract_non_negative_int(...) -> int | None`（签名沿用现私有版）。
- `agent/platform/tools/base.py` / `presentation.py`：新增 `bind_wiring`/`require_wiring`/`display_path` 共享 helper（mixin 或模块级函数，签名沿用现版）。
- `personal_assistant/_utils.py`（new）：`require_text(...)`、`optional_text(...)`（行为按决策 3 逐调用点核对）。
- `IM/infra/_helpers.py`（new）：`optional_text(...)`、`is_no_reply_protocol_token(...)`、`preview_from_event(...)`。

数据流无变化——所有提取都是"把 N 份相同实现换成 1 份 import"，调用顺序、参数、返回值在正常路径上逐字节等价。

## 契约层增量 (delta-spec)

纯行为保持重构。对 `agent.sdk` / 各产品入口的**正常路径**消费者可观察行为零变化；5 处吞异常修复只增强**失败路径**可观测性（日志 / 报错），不新增/改/删任何对外 Requirement。

- kernel: no spec delta
- im: no spec delta
- gateway: no spec delta
- cli: no spec delta

> 边界案例说明：决策 4 中 coding_cli 配置损坏从"静默忽略"变"warning/报错"，属 CLI 失败路径健壮性增强，不构成 CLI 契约层 Requirement 变更，故不产 cli delta-spec。

## 风险与回退

**已知风险**
- **行为差异陷阱**（决策 3）：`_require_text`/`_optional_text` 各副本错误处理本就不一致，提取时若想当然取一个版本会悄悄改变某些调用点行为。缓解：逐调用点核对 + 以现有测试为护栏 + 必要时保留命名变体。
- **派生集合漂移**（决策 1）：`TERMINAL_RUN_STATUSES` 派生表达式与原字面量不一致会引入隐性 bug。缓解：单测断言 `TERMINAL_RUN_STATUSES == frozenset({"completed","failed","cancelled"})`。
- **配置 raise 越界**（决策 4）：配置解析改 raise 若有调用方依赖旧"静默当不存在"会破坏启动路径。缓解：以现有 config 测试护栏，倾向 warning + fallback 优先于直接 raise。
- **contract 测试**：跨包 import 落点错误会被 `tests/contract/` 拦截——这是护栏不是风险，但 worker 须先跑 contract 验证落点合法。

**降级路径**：纯重构无运行时降级概念——若某处提取导致测试红，原地回退该处副本即可，不影响其余收敛。

**回滚**：每个重复点的提取彼此独立，可单独 `git revert` 对应 commit（worker 按包/按 helper 分 commit 即支持此粒度）；5 处吞异常修复亦可逐个回退恢复原 `except` 块。

## Runbook for Reviewer

本 unit 是纯库代码 / 测试重构，**不改任何常驻服务的启停或对外行为**。reviewer 验收靠跑测试套件即可，无需重启服务。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 无常驻服务 | — | — | `pytest -m "not e2e"` 全绿 + `pytest tests/contract` 全绿（验依赖方向未破） |

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-395-M1 | dedup-and-exception-fixes | — | A | 全部 14 处 Copy-paste 收敛（生产 9 + 测试 3 + 常量 2）+ 5 处吞异常修复；涉及 `agent/core`、`agent/platform`、`agent/products`、`IM`、`coding_cli`、`personal_assistant` 及 `tests/unit` 对应文件 | `[worker]` `pytest -m "not e2e"` 全绿、`pytest tests/contract` 全绿（依赖方向未破）；`[worker]` 14 处重复每处仅剩单一真源（跨包 `_require_text`/`_optional_text` 收敛到每包一份），`grep` 确认旧副本已删；`[worker]` 单测锁定 `TERMINAL_RUN_STATUSES == frozenset({"completed","failed","cancelled"})`；`[worker]` 5 处吞异常各有日志/报错且**正常路径返回值不变**（既有测试不变更通过）；`[reviewer]` IM 收发消息 / 群聊、agent 对话 / 工具调用、Coding CLI REPL / 权限请求、Gateway 启停 / 配置解析 全部与变更前一致（motivation 验收标准全部 Scenario） |
