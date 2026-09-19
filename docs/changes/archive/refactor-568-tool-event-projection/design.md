# refactor-568: Gateway 工具事件投影单一归属 — 技术方案

> 对齐 motivation.md

## Changelog

- 2026-09-19 (M1): 真实验收 A1 发现 stop 的终态清理被正文 suppression 阻断；补充仅限已存在气泡的终态清理准入，修复 current drift。

## 现状分析
### 涉及范围
`src/personal_assistant/gateway/runtime_delivery/observer.py` 的 shadow tool 分支、live process 分支和 abnormal reconcile 分支。shadow 在离线门控前落盘；live 在门控后发送。相同的 start/end 在线 shadow 路径目前转换并更新在途表两次。
### 既有约束
产品只依赖 agent.sdk；不改变协议、sender、权限绑定、bubble ACK、task tracker 或 reset 可见性。保持 shadow-before-live。
### 可复用能力
复用 RunDeliveryContext、ExternalShadowBubbleEvent、RuntimeDeliveryTaskTracker 和既有 shadow_store。新增的是私有 in-process 投影 owner，不添加网络 adapter 或存储机制。
### 相关历史
refactor-480 的单 dispatch owner 与 await/detach 区分保持不变；refactor-564 的 MessageDelivery 发布归属保持不变。bugfix-567 不在文件范围内。

## 架构总览
Before: shadow parser + live parser + shared mutable dict + two terminal parsers。
After: observer dispatch → ToolCallProjector → ToolCallProjection(shadow, live) → existing shadow writer / live sender。

## 关键决策
1. **一份状态 owner，不统一两个历史 wire schema。** `ToolCallProjector` 管理 in-flight map，`project(event, context)` 返回工具投影；shadow/live 共享参数、presentation 解析，最终 dict 保留已有差异（live end 的 null 字段、trim reason/approval、live-only pending_revalidation detail）。不新增配置开关。
2. **每个事件最多一次状态转换。** shadow 路径在现有记录点调用 project，并通过 event scope 将结果传递给 live；没有 shadow 的事件仅在原 live 门控点调用。不能提前处理被过滤的事件。正常 turn_end 使用 owner.finish(run_id)，异常 reconcile 使用 owner.reconcile(event) 同步取走在途记录并生成两种失败投影。
3. **保持发布时序。** 工具生命周期 owner 同步、无 I/O；返回的 dict 不共享可被 writer 修改的顶层对象。shadow-only/offline start 保留原 presentation；同时有 live 时，异常终结保留 live pending_revalidation 覆盖后的 detail。Workflow binding、visible marker 和任务命名原样留在 observer。
4. **保持注入接口。** 工厂现有 running_tool_calls 参数仍接受同一个 map，由 projector 独占读写；无需新增调用方参数。异常 bare-name fallback 作为现有行为保留，不新增其他兼容分支。

## 接口与数据流
内部 `ToolCallProjection` 包含 shadow/live 字典。`ToolCallProjector.project(event, context, *, live: bool)` 解析 start/end，维护在途表并返回投影；live 参数只表达实际旧路径是否进入，用于既有 pending_revalidation 差异。shadow 先投影，live 只使用结果或通过轻量 owner 方法应用 live-only detail，禁止再次 start/end。`reconcile(event)` 返回按 call_id 的 shadow/live 失败投影并移除该 run；`finish(run_id)` 清理正常终态。observer scope 保存当前投影及异常批次。reason/output/duration/approval 的缺省和 whitespace 行为逐字段与旧实现比较。

## 契约层增量 (delta-spec)
no spec delta。`docs/specs/im/tool-timeline.md`、`docs/specs/gateway/routing-delivery.md` 的消费者行为保持不变。

## 风险与回退
主要风险是把 shadow/live 既有差异错误抹平、离线门控前提前改状态、normal/abnormal 清理遗漏。保留现有 observer 场景测试，增加缺失的双目的地比较场景；所有产品代码可整体 revert，无数据库变化。

## Runbook for Reviewer
按 docs/development/worktree-runtime.md 隔离。产品 reviewer 运行既有 `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py` 真 IM + Gateway + LLM 用例，检查持久化工具结果；中断与离线回归使用既有实际 shadow store / IM transport seam 的集成证据，明确未覆盖的真飞书网络范围。不操作生产。测试进程由 fixture 清理。

## Milestones
| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-tool-projection | 工具投影单一归属 | 无 | 单组 | runtime_delivery tool projector、observer、相关测试 | [worker] start/end/reconcile 的解析与 in-flight mutation 只有 projector owner；无 wire schema 和执行时序变化；窄回归和本地 CI 通过。[reviewer] 正常/失败工具可回看、中断收口、离线 shadow 不变性证据完整。 |

## A1: 停止后的终态清理归属

根因：`SessionRunCoordinator.stop` 先 suppress，再 interrupt；observer 对 revoked context 丢弃所有事件，导致后续 `run_terminal_reconcile` 不执行。即使允许该事件，ImageReplyConnection 的普通 `_publish` 仍会因 await_visibility=False 拒绝工具和气泡终态帧。两者均存在于基线。

修正：RunDeliveryContext 增加 `terminal_cleanup_allowed`，默认 false；`suppress(run_id, terminal_cleanup=True)` 由明确 user stop 授权；coordinator 收到 cancelled run_status 时传入 `terminal_cleanup=(run_id in _user_interrupted_runs)` 保留同次 stop。store 只在 context 原为 active 或已有 cleanup 授权且 session_generation 未失效时授予/保留 true；普通 reset/generation revoke 的 suppress 保持 false 并覆盖旧授权。迟到 cancelled 不能从 reset 后 revoked+false 重新授权。observer 只允许带该 context 授权的 `run_terminal_reconcile` 越过 revoked gate，其它正文/tool_start/turn_end 仍丢弃。ImageReplyConnection 在同一 context 授权、message_id 非空且等于当前 context.message_id 时，仅允许 `tool_call_completed` 和 `message_completed` 清理旧记录。工具必须 failed（不接纳新的成功结果），message_completed 只允许 `final_content is None` 且发送时保持 None，不从缓存填回正文，不创建 turn_start、不发布新候选；其它帧仍走原 admission。新 session reset 清除此授权，旧 cleanup 不能重新创建消息。

该窄清理是既有 stop 生命周期的终结，不恢复公开正文准入，不改变 message_delivery、图像上传或权限策略。无 wire 新字段/无新网络接口/无数据库迁移；current spec 已要求中断收口，因此 no spec delta。文件范围追加 context.py、image_connection.py 与 coordinator.stop 和 cancelled 分支的两处授权调用（不触及 bugfix-567 入站附件区）。在既有 image delivery 测试文件验证 stop cleanup 与 reset 反例，在既有 reconcile 文件验证 suppressed stop 的 terminal event；产品 reviewer 重跑真实 stop 并检查原字段、已完成工具和晚到正文隔离。

R2-W1 回归：stop→cancelled→reconcile 必须关闭原工具和气泡；stop→reset/generation advance→late cancelled 不得恢复 cleanup 或任何正文发布。
