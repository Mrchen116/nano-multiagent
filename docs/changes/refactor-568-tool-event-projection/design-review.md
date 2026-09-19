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
