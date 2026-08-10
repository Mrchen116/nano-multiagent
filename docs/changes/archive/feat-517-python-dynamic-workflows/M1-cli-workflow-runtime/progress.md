# feat-517-M1 — Progress

## Baseline / Coordination

- Context: M1 在 unit shared worktree 实施；M2 同时修改 IM/PA 范围。
- Decision: 仅修改并按路径提交 agent core/platform/sdk、coding_cli、M1 tests/docs；不暂存任何 M2 dirty 文件。
- Evidence:
  - Tests: 实施前 M1 targeted baseline `276 passed`；实现后扩大 M1 regression `598 passed`，最终新增 TTY seam focused `108 passed`，全量非 E2E `3277 passed, 26 deselected`。
  - Entry: `coding_cli` 默认启用精确名 `Workflow`，global/workspace/env 可禁用；交互输入标记 `RunOrigin.HUMAN`，支持 named/bundled command、`/workflows` 显式命令与 TTY `p/x/r/s` 控制、`/config workflowSizeGuideline`、`/effort ultracode|high` 及长驻 child permission 消费。
  - Frontend State Matrix: N/A（M1 无前端）。
  - Browser QA: N/A（M1 无前端）。
  - E2E/Regression: Luna 一 Agent lifecycle 归 reviewer；worker 不做规模实验。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A；Web must-match 状态归 M2，M1 只稳定数据契约。
- Rollback: 所有 M1 commit 均只含 M1 paths，可逐 commit revert；不影响并行 M2 dirty。
- Commits: `5129cf11e`, `bb35f83a3`, `1f1eca7c5`, `c675a4e61`, `4899f5d03`

## R1 — 稳定共享公开契约与后台 carrier

- Context: M2 需要在不解析 XML 的前提下，把后台 Agent/Workflow 原始返回绑定到消费通知后产生的同一条 assistant message；tool 的异步 launch metadata 也必须独立于 model-facing output。
- Decision: `BackgroundReturnInfo` 由 core notification projection 与 model XML 同源生成；active injection、held flush、terminal continuation 和 idle submit 搬运同一 typed carrier。新 continuation 的 opening `run_status=running` 在 turn events 前携带 `background_returns`，active path 则由 `injection_consumed.background_returns` 给出 consume boundary。`ToolResult.event_metadata` 由 tool registry 的可选 extractor 进入 realtime `tool_end`，不混入输出。
- Rationale: 单一 record projection 保证 XML/sidecar 字段与 terminal 状态一致；registry 原子 claim 保证多 writer 只通知一次；opening run event 让产品在创建 message bubble 时即可获得 sidecar。
- Evidence: `106 passed`（background tasks、runs、tool executor/metadata、realtime hook、SDK/core contracts focused）；最终纳入 M1 `598 passed` 与全量非 E2E `3277 passed` 回归。
- Rollback: scoped R1 commit 可独立 revert；新增字段均有默认值，既有 bash/subagent 与普通 tool 行为保持兼容。
- Commits: `bb35f83a3`

## R2 — 实现受限 Python compiler、primitives 与 resume 状态

- Context: Python 版必须保留上游的“AST 限制与插桩后真实执行”语义，并把确定性 admission、组合原语和最长相同前缀复用固定为 core 纯逻辑。
- Decision: 新增 `agent.core.workflows` 深模块：literal meta/top-level policy、私有/动态/OS authority 禁止、async checkpoint 插桩、restricted globals、run-global ordinal、FIFO dispatch、parallel barrier、per-item pipeline、硬上限、状态机和 chained-v2 signature。child effect 只通过注入的 async runner port 发生。
- Rationale: core 不依赖线程、文件系统或 platform child runner；同一套纯 runtime 可被 platform manager 放入私有 loop，并可用 fake child 永久验证调度与恢复。
- Evidence: `17 passed`（compiler policy/real execution、primitives、state machine、resume prefix）。Red 证据为三文件 collection 均 `ModuleNotFoundError: agent.core.workflows`；最终纳入扩大回归。
- Rollback: scoped R2 commit 只新增 core 模块与纯 unit tests。
- Commits: `1f1eca7c5`

## R3 — 接入 platform manager、Workflow 工具与持久化

- Context: core runtime 需要落到可后台执行、可诊断、可查询/控制的 platform 实现，同时不能把脚本或 child session 对象泄漏给产品层。
- Decision: 新增精确名 `Workflow` 工具与完整 Python prompt/schema；manager 在私有线程事件循环中执行 compiler/runtime，持久化 revisioned snapshot、journal、script 与 transcript locator；child 通过普通 Agent session 执行，支持 structured output、one-level nested Workflow、selected/whole stop/restart、saved/bundled/plugin discovery 与 detached worktree isolation。
- Rationale: manager 是 terminal 与 snapshot 的单一 writer；SDK 和产品只消费不可变 projection，后台 task registry 只承载通用生命周期/一次通知。
- Evidence: platform manager/tool/saved/structured-output focused tests覆盖 completed/failed/stopped、child `None`、stop-wins、nested phase、worktree 与 prompt clause inventory；最终 `598 passed` M1 regression。
- Rollback: `c675a4e61` 的 platform/runtime 部分可与 R1/R2 公开契约分层回退；已落 artifact 不删除。
- Commits: `c675a4e61`

## R4 — 接入 turn activation、provider golden 与 SDK 管理方法

- Context: Workflow active/inactive、可信人工 reminder、共享预算、模型解析和 M2 消费的事件/SDK seam 必须由同一 runtime snapshot 决定。
- Decision: `SessionRuntimeConfig` 仅在 Workflow active 时投影 guideline；provider 原位映射 `turn_system`；human `ultracode`/session mode 生成对应 reminder；父子共享可信人工 output budget。`Kernel` 提供五个 SDK 方法和 SDK-owned DTO，并发布带 `workflow_run_id`/`parent_session_id` 的 revisioned run event；child permission 事件携带 parent session、run 与 agent call correlation，launch `tool_end.event_metadata` 独立提供 task/run locator。
- Rationale: 产品不 import platform；active-tool snapshot 同时控制 tool、prompt、reminder 和命令发现，关闭时没有隐藏残留。
- Evidence: provider 四态 golden、runtime snapshot、SDK management、event metadata、shared budget/model substitution focused tests均通过；Gateway/IM 下游已直接消费这些字段。
- Rollback: SDK 新字段带兼容默认值；禁用 Workflow 可阻止新 launch，同时保留已启动 run 的查询/收口。
- Commits: `bb35f83a3`, `c675a4e61`

## R5 — 完成 coding_cli 产品旅程

- Context: CLI 要在主轮结束后继续呈现后台进度与 child permission，并为 TTY/非 TTY 提供等价控制能力。
- Decision: CLI 默认创建含 Workflow 的 session；配置/env 可关闭。`/workflows` 非 TTY 使用显式 list/detail/pause/resume/stop/restart/save，TTY 打开 phase/Agent/usage 选择视图并以 `p/x/r/s` 控制；named、bundled `/deep-research`、ultracode/guideline 和后台 revision progress 接入既有 REPL，parent stream 长驻处理 child permission。
- Rationale: 保留现有异步 REPL 与 slash surface，不新增独立产品进程或管理服务。
- Evidence: TTY seam 先以缺少 `_run_workflow_tty_controls` 的 collection error 固定预期，随后 CLI focused `108 passed`；全量非 E2E `3277 passed`。
- Rollback: CLI 两个 scoped commit 可回退产品入口，内核已启动 Workflow 仍可经 SDK 收口。
- Commits: `c675a4e61`, `4899f5d03`

## R6 — M1 回归、静态门禁与交付记录

- Context: M1 与并行 M2 共用 unit branch，需要证明完整 repository 回归且不夹带 M2 文件。
- Decision: M1 分 roadpoint scoped commit；最终仅 stage M1 code/tests/docs。真实 LLM 成本旅程按 design 明确留给 reviewer，以 Luna/low/单 Agent 执行。
- Rationale: permanent tests固定确定性语义；reviewer 的真实旅程只验证 provider/model 与交互集成，不把昂贵实验复制进 worker。
- Evidence: M1 `598 passed`；最终 focused `108 passed`；`pytest -m 'not e2e' tests/ -q` 为 `3277 passed, 26 deselected, 22 warnings`；全仓 Ruff check、M1 scoped Ruff format、docs-check、`git diff --check` 通过。全仓 format-check 剩并行 M2 的 `src/personal_assistant/gateway/workflow_permission_bindings.py`，已通知 orchestrator，M1 不跨 scope 修改。
- Rollback: 见各 roadpoint；本 milestone 无前端、运行数据、LLM Proxy payload 或本机配置提交。
- Commits: `5129cf11e`, `bb35f83a3`, `1f1eca7c5`, `c675a4e61`, `4899f5d03`

## Promotion Candidates

None.
