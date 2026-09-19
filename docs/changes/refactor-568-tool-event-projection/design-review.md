# Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`（独立 change-design-reviewer）
- review_mode: full
- mode_reason: 首轮 Gate 2，覆盖全部现状、职责决定、消费者契约与唯一 milestone。
- started_at: 2026-09-19T13:30:51+08:00（本轮显式时钟记录起点；此前已开始阅读）
- completed_at: 2026-09-19T13:31:23+08:00（证据采集结束）
- duration: 显式计时区间 32 秒，不包含此前阅读与报告写入。
- baseline: `/Users/czj/Repos/nano-multiagent`，branch `main`，HEAD `c5f1d5620c6323821a430fc3d53feefeb180fd89`。working tree dirty；相关源码当时没有 tracked 修改，unit 未跟踪。其他既有 dirty/untracked 内容未修改。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### Coverage 与证据

1. **需求与授权**：核对 `original-request.md`、`motivation.md`、`design.md`。当前范围是 Gateway 工具 start/end/异常终结的解释与在途状态归属；正常展示、权限 verdict、中断保留参数、已完成工具不变、离线历史恢复均有明确不变性要求。无协议、Kernel、数据库或 UI 改动；不触及附件入站问题。当前方案足够独立交付，无待决用户产品选择。
2. **真实现状与生产接线**：`composition.py:724-774` 实际构造 `build_kernel_event_observer`，注入 `shadow_sync.record_bubble_event`、reconcile、process tracker 和 workflow permission dependencies，并将 observer 作为 `MessageDelivery.writer`。`message_delivery.py:128-135` 的 `observe_process` 把过程事实交给该 writer，因此所选 observer 是生产路径而非测试替身。`observer.py:784-852` 的 shadow start/end 与 `1749-1938` 的 live start/end 确实重复解析 presentation、构造 tool payload 并修改同一在途表；`730` 先取走异常记录，再由 `903-923` 与 `2161-2225` 分别解释失败投影。
3. **架构判断**：工具参数/presentation 转换与在途生命周期共同构成一个内存状态职责，放在 runtime_delivery 私有 projector 合理；无需提升至 Kernel、IM transport 或新持久层。已有 typed context、shadow store、task tracker、MessageDelivery 发布 owner 均可直接复用。observer 保留事件路由、Workflow permission binding、可见性和发布次序，避免把业务 I/O 搬入 projector。一个同步 owner 和双目的地数据投影足以解决具体重复解释代价，没有引入配置、存储、网络 adapter 或新兼容协议。
4. **数据流与历史约束**：`observer.py:642-731` 先处理 context/visibility/reset，再进入 shadow；`995-1040` 的 offline gates 与 `1823-1834`、`1936` 起的 shadow await/live detach 差异应保留。设计明确通过 event scope 复用已生成投影，未走 shadow 的事件只在既有 live 分支准入后投影，异常同步取走状态、正常终结由 finish 清理。refactor-480 archive design 的单 dispatch owner、await/detach 与 process tracker 约束，以及 refactor-564 archive design 的 MessageDelivery 发布归属均被保留；本 unit 不重新拥有正文交付。
5. **字段兼容**：现有 live end 会写 `reason/output/duration_ms` 的 null 值，shadow 按条件省略；reason/approval whitespace 规则不同。live start 还可覆盖同群 send_message 的 pending_revalidation detail，随即成为异常清理所用快照。设计显式保留这些差异，区分 shadow-only 与经过 live 的状态；terminal bare-name 兼容面也保持。此处是复用共同解析后分别投影，不应强行统一 wire shape。
6. **delta 与消费者**：no spec delta 与行为保持目标一致。canonical `docs/specs/im/tool-timeline.md` 明确中断终态、保留命令/描述、已完成工具不被改写及 presenter 展示；`docs/specs/gateway/routing-delivery.md` 保持离线 shadow 恢复和业务交付规则。无前端变更，无新增 must-match 页面。
7. **Milestone 与验收**：唯一 M1 将解析/状态 ownership、兼容性、回归与真实产品证据放入退出标准，无并行文件冲突。现有 `test_reconcile_preserves_tool_input.py:66-306` 覆盖异常 input/presentation/content override；`test_gateway_shadow_sync.py:651-727,909-955` 覆盖离线 rich snapshot 与异常工具收口。真实关键路径 `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py` 走 IM/Gateway/LLM，设计要求补查持久化结果，能与 seam 回归组成所需证据。隔离与清理要求明确，不操作生产。本轮为设计审查，未运行测试，不把这些现有测试宣称为本轮通过结果。

### 历史问题闭环

首轮，无历史 issue。

### Issues

无。

### Recommendations

- R1-R1（可选验收记录提醒）：现有真实关键路径测试只断言最终回复含 sentinel、不含内部 markup；其本身未断言持久化 tool row。产品验收应按设计 Runbook 另外查询同一会话的工具历史字段并记录证据，避免仅凭该用例通过宣称完整展示不变性。

## Author Resolutions

- 接受 R1 Approved；核实无实质未决项。采纳 R1-R1：真实验收另查同一聊天持久化工具记录。
- 实施将接口具体化为 `project(event)` 与 `for_live(projection, context)`，对应设计已允许的“轻量 owner 方法应用 live-only detail”；没有新增职责或行为，保留 Gate 2。

## Round 2

### Metadata

- reviewer target: `/root/design_review`（同一独立 reviewer）
- review_mode: delta
- mode_reason: A1 将既有 stop 终态不收口纳入有界修复；复审新的 cleanup 准入与其调用链，未变化的 projector 设计 retained_from: Round 1。
- started_at: 2026-09-19T13:43:21+08:00（本轮显式时钟记录起点）
- completed_at: 2026-09-19T13:43:43+08:00
- duration: 显式计时 22 秒，不含此前阅读及报告写入。
- baseline: worktree `/Users/czj/Repos/nano-multiagent/.worktrees/unit-refactor-568`；HEAD `3b4ff2ad945b49bc8a41ea8674b8be2af4b91812`；design/motivation dirty，code-review/verification 未跟踪；本轮未修改产品代码。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**

### Coverage 与证据

- 已读 A1 真实验收报告、motivation current drift、新增设计段。stop 应答成功但在飞工具不收口违反既有 tool-timeline，中断收口仍是原 M1 用户侧退出标准；no spec delta 合理。当前设计 A1 对文件范围的补充与单 milestone 可共同阅读；无需扩展产品协议或 UI。
- 生产路径沿用 Round 1 已核实的 composition → MessageDelivery → observer，并核实 `ImageReplyConnection._send/_publish` 当前在 message_completed 分支从 `_Bubble.raw` 填充正文，随后调用 await_visibility；因此仅放行 observer 不足，新增的 bodyless 清理旁路必须在正文回填之前，并且保持 message identity 限制。设计已覆盖此点。
- observer 当前 `is_suppressed` 门控确实在 projector/reconcile 之前。`SessionRunCoordinator.stop:1317-1323` 确实先标记 user interrupted、suppress，再 interrupt。新 terminal_cleanup_allowed 状态由 context store 拥有，observer 只分发已授权异常终态，image connection 在最终出口限制失败工具与 bodyless terminal，职责合理；不需要新通道或重新开放普通发布。
- reset 的 `advance_generation:350-360`、register/seed generation fence 和普通 suppress 必须撤销 stop cleanup 授权；本轮设计已明确 reset 覆盖语义。但从 stop 到 reconcile 的完整 cancelled 事件链还有一个重复 suppress，见 R2-W1。这个调用是当前正常生产链的一部分，不是推测竞态。
- 原 projector 的 shadow/live schema 差异、状态 owner、依赖边界、正常回看及离线恢复 retained_from: Round 1：A1 不修改这些决定。新增验收已要求真实 stop、保留已完成工具、晚到正文拒绝和 reset 反例；补齐 R2-W1 后应在同一组回归验证真实 cancelled event 顺序，而非只直接调用 observer。

### 历史问题闭环

- Round 1 无阻断问题；R1-R1 的历史字段检查已在 acceptance.md 正常/失败 read 旅程中落实。
- 产品 A1 仍未闭环：本轮审设计，不以提出修复代替实施与真实复验。

### Issues

#### R2-W1 — cancelled 事件再次 suppress 会撤销刚授予的 stop cleanup 权限

- 位置：`design.md`「A1: 停止后的终态清理归属」中“默认 false / 普通 suppress 覆盖旧授权 / coordinator.stop 的单处授权调用”。
- 证据：`session_run_coordinator.py:3101-3107` 在 `_await_terminal_run` 消费 `run_status(status=cancelled)` 时无条件执行 `self._delivery_context_store.suppress(run_id)`；随后 `3150-3154` 调用 `_emit_terminal_reconcile`。按本设计，仅在 `stop` 授予 true，但这个普通 suppress 会先覆盖为 false，observer 仍丢弃 reconcile。`_fence_recovery_for_control:3539-3544` 也存在对未完成 successor 的 suppress，设计修订时应明确其既有 stop/reset 区分。
- 后果：只按当前“stop 单处授权”的改动范围实施，正常 `/stop` cancelled 路径仍可复现 A1；直接给 context 授权再调用 observer 的窄测试会漏掉。
- 所需修正：明确同一次 user stop 的 cancelled 事件如何保留已经授予的 cleanup，且 reset/generation revoke 始终清除、不被迟到 cancelled 重新授权；把涉及的 coordinator 调用点纳入设计范围。无需增加通用机制，沿已有 user-interrupted/reset 事实或明确的 context 操作语义即可。回归包含 stop → cancelled run_status → reconcile，以及 stop → reset → cancelled/reconcile 的反例。

### Recommendations

无额外建议。

## Author Resolutions R2

- R2-W1 accepted：A1 设计补齐 cancelled 分支传递同次 user-stop 事实；store 根据既有授权/active 状态及 generation 限制授权，reset 默认 false 撤销后不能由迟到 cancelled 恢复。补充两条完整生命周期回归。未开始 A1 产品代码修改。

## Round 3

### Metadata

- reviewer target: `/root/design_review`（同一独立 reviewer）
- review_mode: closure
- mode_reason: 仅核实 R2-W1 的 Author Resolution 与修订后的 A1 授权链；其余设计无实质变化，retained_from: Round 1 / Round 2。
- started_at: 2026-09-19T13:45:00+08:00
- completed_at: 2026-09-19T13:45:35+08:00
- duration: 显式计时 35 秒；不包含最初阅读。
- baseline: 同 unit worktree，HEAD `3b4ff2ad945b49bc8a41ea8674b8be2af4b91812`；审阅未提交的 design A1 与 Author Resolutions R2；A1 产品代码尚未修改。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### 历史问题闭环

- **R2-W1 — closed（设计层）**。
- Author Resolution：cancelled 分支根据既有 `_user_interrupted_runs` 传入同次 stop 事实；store 限定 active 或已有 cleanup 授权，并要求 generation 未失效；普通 suppress 清除授权，revoked+false 不得因迟到 cancelled 重新授权。
- 本轮证据：`design.md` A1 修订段已明确 coordinator 的 stop 与 cancelled 两处调用，最后新增完整生命周期正反两条回归。与现有 `session_run_coordinator.py:3101-3107,3150-3154` 调用顺序对照后，stop 首次授予、cancelled 保留、reconcile 使用的链路已闭合。
- reset 反例：reset/generation advance 以普通 suppress 撤销授权后，context 为 revoked+false；迟到 cancelled 即使还携带 user-interrupted 事实，也不满足授权前态。generation 条件另外阻止旧代次获准。因此不依赖清空标记集合的时机来防止旧回复恢复。
- 普通正文准入仍是 revoked；observer 例外仅为 terminal reconcile，最终 image connection 例外仍限定现存 message identity、failed tool 和 final_content=None。R2 已审的正文缓存不回填约束保持。

### Retained coverage

Round 1 的 projector ownership、shadow/live schema、生产接线与 canonical 无变更结论保留；Round 2 除 R2-W1 外的 A1 出口限制、职责与真实复验要求保留。此结论只解除设计门禁，不宣称 A1 产品验收通过；实施后仍须执行新增生命周期回归与真实 stop 复验。

### Issues

无。

### Recommendations

无。
