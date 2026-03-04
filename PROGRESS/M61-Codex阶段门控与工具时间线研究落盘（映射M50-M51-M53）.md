# M61 - Codex阶段门控与工具时间线研究落盘（映射M50-M51-M53）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M61 为研究型里程碑，硬约束是不改实现代码；交付物是可执行研究结论与迁移清单。
  - 目标聚焦 codex 的阶段门控、工具时间线/orphan、summary 去重，并映射到 M50/M51/M53。
- Decision:
  - 拆分为三轮研究：`R1 阶段门控`、`R2 工具时间线与去重`、`R3 迁移清单与验收模板收口`。
  - 每轮补充“新问题 -> 新锚点 -> 迁移决策 -> 风险”闭环，及时写入 PROGRESS。
- Rationale:
  - 多轮递进能确保研究不是静态摘录，而是可被后续里程碑直接执行的工程清单。
- Evidence:
  - Tests: baseline gate 全绿。
  - Entry: 必读文件已完成（`LOGBOOK.md`、`内核设计蓝图.md`、`PROGRESS/M44-Codex-CLI-研究补充-输入历史-事件折叠-去重策略.md`、`tdd-execution-worker`）。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：补全 STREAMING/FINALIZING/FINALIZED 与 frame coalesce 关键锚点。

### R1 阶段门控与渲染调度锚点深挖（STREAMING/FINALIZING/FINALIZED）
- Context:
  - Red 问题清单（待解）：
    - `STREAMING/FINALIZING/FINALIZED` 在 codex 中的真实门控条件是什么（而非命名推断）？
    - status line 在流式阶段何时隐藏、何时恢复，是否受 commentary/final-answer phase 双重约束？
    - commit tick 与 frame coalesce 的边界在哪里（谁负责“节流”，谁负责“排空”）？
- Decision:
  - 结论（含推断）：
    - `STREAMING`（推断）：`stream_controller/plan_stream_controller` 非空且 commit tick 持续排空，期间 status row 被隐藏。
    - `FINALIZING`（推断）：`MessagePhase::Commentary` 完成后设置 `pending_status_indicator_restore=true`，等待“队列空闲 + task 仍运行”再恢复 status row。
    - `FINALIZED`（推断）：final-answer 或 turn 终态触发 `finalize_turn`/`flush_answer_stream_with_separator`，控制器清空并重置 chunking 状态。
  - `phase` 语义锚点：
    - `MessagePhase::{Commentary, FinalAnswer}`：`protocol/src/models.rs:156`
    - commentary 完成门控：`tui/src/chatwidget.rs:2293`
  - commit/drain 与 redraw 分层：
    - commit 计划与排空：`tui/src/streaming/commit_tick.rs:69`
    - 阈值与滞回策略：`tui/src/streaming/chunking.rs:85`
    - frame coalesce（最早 deadline + 120fps 限速）：`tui/src/tui/frame_requester.rs:110`
  - M50 迁移建议（可执行）：
    - 建立 `TurnRenderPhase` 显式状态机：`STREAMING -> FINALIZING -> FINALIZED`。
    - 把“流式排空策略”和“重绘调度策略”分层：前者在 `events/stream_runtime`，后者在 `render/frame_scheduler`。
    - status row 恢复必须与 `phase=Commentary` + `queue_idle` 双门控绑定，禁止仅凭“收到一次 completed”切换。
- Rationale:
  - codex 并非依赖单一状态字段，而是“phase + queue idle + task running”组合门控；这比简单 done flag 抗抖动更强。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `113 passed, 42 warnings`
  - Entry:
    - 关键锚点：
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/protocol/src/models.rs:156`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:913`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1269`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2293`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/streaming/commit_tick.rs:69`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/streaming/chunking.rs:85`
      - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/tui/frame_requester.rs:110`
- Rollback:
  - `a9b9dc4`（计划提交）。
- Commits: C1=`4c9a55c`, C2=`768519e`, C3=`本提交`
- Next:
  - 进入 R2：围绕 tool timeline/orphan 隔离与 summary 去重继续深挖。

### R2 工具时间线聚合/orphan隔离与summary去重研究
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 迁移总清单与managed CLI观感验收模板收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
