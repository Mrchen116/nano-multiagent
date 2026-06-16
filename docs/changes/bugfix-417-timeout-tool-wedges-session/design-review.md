# Design 评审:bugfix-417

**结论(第三轮 / 最新)**:Approved(delta-spec 维度)

> 第三轮复审:作者已把三份 delta 全面重做。逐条核对 canonical:
> - ✅ gateway 两条 CRITICAL 已解——改为 MODIFIED 精确锚定 canonical「入站消息按四步决策路由…」(:28)与「run 进入终态时对在飞 tool_call 按原因收口」(:391),原 Scenario 全保留,watchdog-reap 失败态正确从「执行超时」重映射为「已中断」。
> - ✅ IM WARNING 已解——REMOVED 旧「等人工权限决策…」(:355,标题精确匹配)+ ADDED 统一 liveness;旧契约两项保证(批准后可继续 / 崩溃兜底回收)在新条保留无丢失。
> - ✅ 作者额外发现并修了同源遗漏:canonical IM「工具徽标按中断原因显示终态」(:376)也有「看门狗→执行超时」混淆,这轮一并 MODIFIED 改对(两个渲染面都改)。
> - ✅ kernel MODIFIED「运行可被中断与取消」(:166)忠实保留 3 原 Scenario + 净增 2 条,并把偏内部的「锁释放」措辞改成纯可观察表述。
> - ✅ 三份 delta 头部均加「对 canonical 做 diff」说明,意图清晰。
> delta-spec 可进 change-orchestrator。下方为前两轮历史结论留痕。

---

**结论(第二轮历史)**:Issues Found(2 CRITICAL + 1 WARNING,均在 delta-spec 整合层)

> 第二轮专项复审 delta-spec(vs 既有 canonical 而非仅 vs incident Req)。更正第一轮:
> - **收回**第一轮「Req D 无 delta-spec」CRITICAL——evergreen kernel spec(`docs/specs/kernel/spec.md:218-220`)本就有「bash 超时 → 暴露稳定超时细节,而非静默挂起或丢失」,Req D 是该既有契约对派生子进程命令没成立的 bug,M2 是恢复符合,合理 no spec delta。仅建议 design delta-spec 段对 C/bash 层显式写一句「no spec delta」(Recommendation)。
> - 第一轮的权限 liveness WARNING 已被作者对齐(权限 liveness 统一进 kernel,Gateway/IM 不对称消除)。
> - 新撞出下面两条 CRITICAL + 一条 WARNING:delta 没正确对齐它实际在改/在矛盾的既有 canonical 契约。

**[CRITICAL] [gateway delta] 与既有 canonical 直接矛盾却只列 ADDED、缺 MODIFIED。** evergreen gateway「run 进入终态时对在飞 tool_call 按原因收口」的 Scenario「看门狗超时终止后在飞工具收口为执行超时」(`docs/specs/gateway/spec.md:396-399`)明确把 watchdog-reap 原因标「执行超时」;本 unit 决策5 + gateway delta「看门狗收尸标记为中断」要求 watchdog-reap → 「中断/卡死」、把「耗时过长/执行超时」留给工具自身 deadline——正是 incident RCA 说的「旧契约把 idle 与 max-duration 混为一谈」的契约化身。**不改的坏事**:收尾并入后 canonical 同一事件既标「执行超时」(:399)又标「中断」,自相矛盾。**修法**:delta 增一条 MODIFIED 改写该既有 requirement,把 watchdog-reap 原因从「执行超时」改「中断」。

**[CRITICAL] [gateway delta] 重定义既有 idle 看门狗判据却只列 ADDED。** evergreen gateway 既有 Scenario「静默运行失败后释放同会话队列」(GIVEN「持续120秒无任何内核事件且不处于等人工权限决策态」)+「等人工权限决策期间不被 idle 看门狗误杀」(`docs/specs/gateway/spec.md:44-52`)= 旧判据(输出静默 + permission 特例豁免)的契约。本 unit 把判据重定义为「无 liveness 心跳才收」+ 取消 permission 特例,是对既有 requirement 的 MODIFIED 而非平行 ADDED。**不改的坏事**:收尾后 canonical 同时留旧「无内核事件→收尾」(会误杀静默长命令,正是本 bug)与新「无 liveness 才收」,矛盾。**修法**:把这条既有 requirement 写成 MODIFIED 完整条目。

**[WARNING] [im delta] MODIFIED 标题没锚定它顶替的既有 canonical requirement。** IM delta MODIFIED 标题「relay 存活看门狗按最近事件判定，含 liveness 心跳」,实际顶替的是 canonical「等人工权限决策的消息不被中继看门狗误判为失败」(`docs/specs/im/spec.md:355` + 三个 awaiting_permission Scenario);delta 自述「不再有 permission 专用 `awaiting_permission_at` 特例」=把旧 requirement 泛化掉,但标题不匹配,收尾软对账可能对不到旧条目 → 旧 permission-特例 requirement 留存与新条矛盾。**修法**:MODIFIED 锚到既有标题(写改后完整条目),或 `REMOVED` 旧「等人工权限决策…」+ `ADDED` 新统一 liveness requirement。

> 根因:delta 上一版只做到「镜像 incident 验收标准」,没「diff 既有 canonical」。本 unit 恰在**重定义** watchdog 判据与失败态映射,这些行为 evergreen 早有契约(其一正是 bug 的契约化身),故 ADDED 不够,必须 MODIFIED 顶替/改写既有条目。

---

以下为首轮(design 文档质量)结论:

总体:现状分析扎实(文件表 / 既有约束 / 可复用能力 / 相关历史齐全且与代码核对一致),契约 grounding 做了,7 条决策全部"拍死"非悬而未决,三层垂直切片(A 锁 / B watchdog / C bash)文件零重叠、并行组合规,delta-spec 三包齐全且 THEN 都是消费者可观察结果,两轨退出标准齐。逐项核验通过的 grounding:`_owned_tasks`(registry.py:126)、`cancel`(:464)、`_async_loop`+`call_soon_threadsafe`、`kernel.cancel`(:959)、`cancel_all_pending`(broker.py:194)、`_map_kernel_event_to_run_activity` 未映射事件返回 None(inbound_pipeline.py:970)、`_await_terminal_run_async`(:822)、`awaiting_permission`(:853/:892)、`_pending_updates` 缓冲(tools/registry.py:204-247)、runtime CancelledError 恢复(:577)、relay_watchdog `permission_crash_threshold_seconds=600`(:27)。

**Issues**:

- [WARNING] [决策 4 + 接口与数据流 #permission 心跳]:permission liveness 的数据流没闭合,会让 M3 worker 在"等权限不被误杀"这条 P 相关场景上走偏。具体:watchdog 伪逻辑(design:208)写 `anext(stream)` 收到"业务/心跳/**permission_pending**"任意事件都重置,但决策 4 又写 permission_pending 心跳"**由 Gateway 周期发**"。Gateway watchdog 读的是 `kernel.stream` 的 `anext`,Gateway 自己 emit 的事件并不在 `kernel.stream` 里——两种说法对不上:要么 permission_pending 由内核 emit 进 stream(那就不是"Gateway 发"),要么 Gateway 在 wait 循环里 out-of-band 自 tick(那就不是 `anext` 的 event)。design 把这两条路糊在了一起。**不改的坏事**:worker 移除 `awaiting_permission` 分支(design:213)后,若按字面"Gateway 自发心跳"实现,而该心跳又进不了 watchdog 的 `anext`,parked-on-permission 的 run 会在 N 秒后照样被收——恰好重新引入本 unit 要消灭的"等权限被误杀"(incident Req B 第三场景)。建议在决策 4 / 数据流段补一句把这条路画死:既然 runtime(core)本就持有 permission_requester 端口、知道自己 parked 在权限上(现有 `permission_request` 事件即由内核 emit 进 stream,见 inbound_pipeline.py:892),最自洽的走法是**让内核在 parked-on-permission 期周期 emit liveness 进 stream**,与决策 2/3 的工具/LLM liveness 同一通路——这样 kernel delta-spec 的 liveness 源补上"等权限"一项,两个 watchdog 都自动复用现有判据,也消掉了下面的 Gateway/IM 机制不对称。

**Recommendations**(不阻断):

- [决策 4 / IM delta-spec] Gateway 侧改"心跳驱动",IM 侧却"沿用 `awaiting_permission_at` marker"——两个本被 incident 要求"镜像同步改"的 watchdog 在 permission 维度用了不同机制。各自内部自洽、design 也给了理由(marker 本就是 Gateway 刷新的存活标记),不阻断;但若按上条把 permission liveness 统一下沉内核 emit,这处不对称可一并消除,两侧重新真正镜像。
- [决策 5 / 数据流] 现有代码 `_emit_terminal_reconcile` 除 :869 的 `reason="timed_out"`,在 :913/:920 已有 `reason="interrupted"`。决策 5 拟引入 `tool_timeout`/`stalled` 两个新常量,提示 worker 实施时盘点既有 `interrupted` 的语义归属(是否就是"卡死/中断"、要不要合并),避免新增常量与旧常量语义重叠、留下孤儿。
- [M3] M3 跨 core/platform/gateway/IM 五文件,是本 unit 最重的一块。这是 B 重设计的内聚垂直切片(心跳 liveness 端到端),**不应**横切拆分;仅提示 orchestrator 派发时留足 worker 窗口、或在派发包里按 roadpoint(心跳源解缓冲 → publisher → LLM ticker → 两 watchdog 重定义)给出推进顺序。
