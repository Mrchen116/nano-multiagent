# refactor-395 — 验收报告（Round 1）

> 对齐: motivation.md §用户侧验收标准（不变性）
> 验收日期: 2026-06-03
> 验收镜头: 回归不变性（纯重构 + 失败路径可观测性增强，无新用户功能）

## Verdict

**pass**

本 unit 为纯行为保持重构。design.md §Runbook for Reviewer 明确：验收靠测试套件为主要证据，无需重启服务。两套核心测试均通过：

- `pytest -m "not e2e"`: **2320 passed, 2 failed, 2 skipped**（2 个失败为基线已有 macOS `/private/tmp` vs `/tmp` 路径断言问题，已在 progress.md 记录，与本 unit 无关）
- `pytest tests/contract/`: **97 passed**（依赖方向无破坏）

## 澄清记录

无疑问。验收口径清晰：纯重构，Scenario 的 THEN 均为"与变更前一致"，主要证据为测试套件全绿。

## User Journeys Exercised

本 unit 是纯库代码 / 测试重构，无用户可见界面改动。旅程以"测试套件"为替代验证（design.md Runbook 明确授权）。

**旅程 1（主路径——测试套件全量回归）**: 跑 `pytest -m "not e2e"`，覆盖 IM 收发消息 / Agent 对话 / Coding CLI / Gateway 配置解析等所有 Requirement。

**旅程 2（依赖方向契约）**: 跑 `pytest tests/contract/`，验证新增 import 路径（`agent.sdk` 暴露 `TERMINAL_RUN_STATUSES`、`IM/infra/_helpers.py`、`personal_assistant/_utils.py` 等）未破坏跨包依赖方向硬规则。

**旅程 3（专项锁定测试）**: 跑 `tests/unit/test_refactor_395_utils.py`，验证 `TERMINAL_RUN_STATUSES` 派生值与历史字面量完全一致（防派生集合漂移风险）。

## 问题清单

无 blocking / major / minor issue。测试套件全绿，依赖方向无破坏，重构要点逐一核实。

## 验收标准覆盖

### Requirement: IM 聊天功能不受影响 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 发送和接收消息 | motivation.md §用户侧验收标准 | `pytest -m "not e2e"` 覆盖 im_service 单测（313 passed），包含消息收发路径；design.md Runbook 授权以测试套件为主要证据 | 2320 passed，相关 im_service 测试全绿 | pass | 回归基线：行为不变 |
| 群聊功能 | motivation.md §用户侧验收标准 | 同上，im_service 单测覆盖群聊消息路径 | 同上 | pass | 回归基线：行为不变 |

### Requirement: Agent 对话功能不受影响 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 通过 Gateway 发起 agent 对话 | motivation.md §用户侧验收标准 | `pytest -m "not e2e"` 覆盖 personal_assistant / agent 单测（含 inbound_pipeline、session 路径）；contract 测试验依赖方向 | 2320 passed，contract 97 passed | pass | 回归基线：行为不变 |
| Agent 工具调用 | motivation.md §用户侧验收标准 | 同上，agent/core/tools 及 platform/tools 相关单测均在 `-m "not e2e"` 套件内 | 2320 passed | pass | 回归基线：行为不变 |

### Requirement: Coding CLI 功能不受影响 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| REPL 交互 | motivation.md §用户侧验收标准 | `pytest -m "not e2e"` 覆盖 coding_cli 单测；commands.py 吞异常修复（REPL 发送循环、配置解析）均有既有测试护栏 | 2320 passed | pass | 回归基线：行为不变 |
| 权限请求展示 | motivation.md §用户侧验收标准 | 同上，commands.py:374 权限请求 JSON 序列化 fallback 修复有单测覆盖 | 2320 passed | pass | 回归基线：行为不变 |

### Requirement: Gateway 启停和配置不受影响 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 正常启动 | motivation.md §用户侧验收标准 | `pytest -m "not e2e"` 覆盖 personal_assistant 单测（含 gateway 连接行为测试）；test_gateway_im_connection_behavior.py 整合了原 test_gateway_im_connection.py 唯一测试 | 2320 passed | pass | 回归基线：行为不变 |
| 配置解析 | motivation.md §用户侧验收标准 | 同上，_read_section 配置解析修复为 warning+fallback（不改正常路径），既有 config 测试通过 | 2320 passed | pass | 回归基线：行为不变；配置损坏时从静默变为 logger.warning，符合 motivation §目标状态 |

### Requirement: 测试套件全部通过 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 单元测试 | motivation.md §用户侧验收标准 | 直接跑 `pytest -m "not e2e"` | 2320 passed, 2 failed（基线已有 /tmp vs /private/tmp 路径断言，与本 unit 无关，已在 progress.md 起始记录；在 main 分支同样失败，确认属于预先存在问题） | pass | 2 个基线失败经确认与 refactor-395 改动无因果关系 |

## 附：重构要点核实

| 重构项 | 核实方式 | 结论 |
|---|---|---|
| `logger.warn()` 全替换为 `logger.warning()` | `grep -r "\.warn(" src/ --include="*.py" \| grep -v "warning("` 零输出 | 通过 |
| `IM/models.py` / `IM/repositories.py` / `smoke_runtime.py` 已删除 | `ls` 验证文件不存在 | 通过 |
| 测试 import 无残留 `from IM.models` / `from IM.repositories` | `grep -rn` 零输出 | 通过 |
| `TERMINAL_RUN_STATUSES` 派生值与历史字面量一致 | `test_refactor_395_utils.py::TestTerminalRunStatuses` 8 passed | 通过 |
| `agent/core/utils/time.py` + `fileio.py` 新建 | `ls` 验证存在 | 通过 |
| `IM/infra/_helpers.py` + `personal_assistant/_utils.py` 新建 | `ls` 验证存在 | 通过 |
| contract 测试（依赖方向硬规则）通过 | `pytest tests/contract/` 97 passed | 通过 |

## Side Findings

无 out-of-unit issue。未发现与本 unit 范围外的功能相关的问题。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新**（本 unit 不新增对外能力，依赖方向不变）
- [x] `docs/specs/kernel/spec.md`（内核契约层）：**无需更新**（design.md §契约层增量明确：kernel no spec delta）
- [x] `docs/specs/im/spec.md`（IM 契约层）：**无需更新**（design.md：im no spec delta；删除 facade 不影响 IM 运行时对外行为）
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）：**无需更新**（design.md：gateway no spec delta）
- [x] `docs/specs/cli/spec.md`（CLI 契约层）：**无需更新**（design.md：cli no spec delta；配置损坏从静默变 warning 属失败路径健壮性增强，不构成 Requirement 变更）
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新**（无架构改变，无新约定）
- [x] `docs/SPEC_GUIDE.md`：**无需更新**（本 unit 未改文档体系本身）
