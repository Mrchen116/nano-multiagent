# feat-517-M1 — Progress

## Baseline / Coordination

- Context: M1 在 unit shared worktree 实施；M2 同时修改 IM/PA 范围。
- Decision: 仅修改并按路径提交 agent core/platform/sdk、coding_cli、M1 tests/docs；不暂存任何 M2 dirty 文件。
- Evidence:
  - Tests: 实施前 M1 targeted baseline `276 passed`；随后全量 `pytest -m 'not e2e' tests/ -q` 因并行 M2 Red tests 缺 `IM.domain.models.BackgroundReturn` 在 collection 阶段出现 3 errors，已通知 orchestrator，待 M2 变绿后补跑。
  - Entry: N/A（尚未实现）。
  - Frontend State Matrix: N/A（M1 无前端）。
  - Browser QA: N/A（M1 无前端）。
  - E2E/Regression: Luna 一 Agent lifecycle 归 reviewer；worker 不做规模实验。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A；Web must-match 状态归 M2，M1 只稳定数据契约。
- Rollback: 所有 M1 commit 均只含 M1 paths，可逐 commit revert；不影响并行 M2 dirty。
- Commits: pending

## R1 — 稳定共享公开契约与后台 carrier

- Context: M2 需要在不解析 XML 的前提下，把后台 Agent/Workflow 原始返回绑定到消费通知后产生的同一条 assistant message；tool 的异步 launch metadata 也必须独立于 model-facing output。
- Decision: `BackgroundReturnInfo` 由 core notification projection 与 model XML 同源生成；active injection、held flush、terminal continuation 和 idle submit 搬运同一 typed carrier。新 continuation 的 opening `run_status=running` 在 turn events 前携带 `background_returns`，active path 则由 `injection_consumed.background_returns` 给出 consume boundary。`ToolResult.event_metadata` 由 tool registry 的可选 extractor 进入 realtime `tool_end`，不混入输出。
- Rationale: 单一 record projection 保证 XML/sidecar 字段与 terminal 状态一致；registry 原子 claim 保证多 writer 只通知一次；opening run event 让产品在创建 message bubble 时即可获得 sidecar。
- Evidence: `106 passed`（background tasks、runs、tool executor/metadata、realtime hook、SDK/core contracts focused；修正一个 fixture 后复跑见下一 commit）。
- Rollback: scoped R1 commit 可独立 revert；新增字段均有默认值，既有 bash/subagent 与普通 tool 行为保持兼容。
- Commits: pending

## R2 — 实现受限 Python compiler、primitives 与 resume 状态

- Context: Python 版必须保留上游的“AST 限制与插桩后真实执行”语义，并把确定性 admission、组合原语和最长相同前缀复用固定为 core 纯逻辑。
- Decision: 新增 `agent.core.workflows` 深模块：literal meta/top-level policy、私有/动态/OS authority 禁止、async checkpoint 插桩、restricted globals、run-global ordinal、FIFO dispatch、parallel barrier、per-item pipeline、硬上限、状态机和 chained-v2 signature。child effect 只通过注入的 async runner port 发生。
- Rationale: core 不依赖线程、文件系统或 platform child runner；同一套纯 runtime 可被 platform manager 放入私有 loop，并可用 fake child 永久验证调度与恢复。
- Evidence: `17 passed`（compiler policy/real execution、primitives、state machine、resume prefix；最终数字在 roadpoint commit 前复跑）。Red 证据为三文件 collection 均 `ModuleNotFoundError: agent.core.workflows`。
- Rollback: scoped R2 commit 只新增 core 模块与纯 unit tests。
- Commits: pending

## R3 — 接入 platform manager、Workflow 工具与持久化

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R4 — 接入 turn activation、provider golden 与 SDK 管理方法

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R5 — 完成 coding_cli 产品旅程

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R6 — M1 回归、静态门禁与交付记录

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## Promotion Candidates

None.
