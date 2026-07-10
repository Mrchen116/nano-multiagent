# Design 评审:bugfix-437-compaction-workspace-root-crash

**结论**:Issues Found(2 WARNING,无 CRITICAL;均不推翻架构方向,但应回 author 补清后再进 orchestrator)

整体方向正确:两面(A 面压缩落盘漏传 workspace_root / B 面失败反馈只到 relay-task 级)定位准确,决策都在治本(系统性贯穿 workspace_root、消双写、message 级即时反馈 + watchdog 退兜底),分层与契约用法干净,delta-spec 的 MODIFIED/ADDED 用法正确。问题集中在决策 2「收敛写入路径」漏说了被删代码块里一处 load-bearing 的内存副作用,以及决策 1 的现状前提表述不精确。

---

**核实台账**(逐条核过的承重原子;结论附证据):

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状:loop._maybe_compact 调 list_entries 漏传 workspace_root | 读 loop.py | ✓ 成立 `loop.py:871` `list_entries(session_id)` 无 workspace_root;_maybe_compact 自身只读+重写内存,不落盘,崩在读取 → 解释 JSONL 0 条 compact_boundary |
| 现状:loop 层「结构性拿不到」workspace_root,AgentState 无该字段 | 读 state.py + loop.run 签名 + runtime wiring | ✗ **不精确**:`AgentState`(state.py:21-30)确无该字段,但 `loop.run` 已收 `current_working_directory_override`(loop.py:160),其值 = session_workspace_root(runtime.py:601 ← config.workspace_root @391),且在 `_maybe_compact` 调用点(loop.py:289)在作用域内。值已到 loop,只是叫别的名字 → 见 WARNING-2 |
| 现状:AgentState 是 frozen @dataclass,加字段需核构造点 | grep `AgentState(` | ✓ 成立,生产构造点 3 处:context_fork.py:201、runtime.py:1771、summarizer.py:53 |
| 现状:runtime._compact_session 已算出 compaction_workspace_root 却没传 apply() | 读 runtime.py:1898-2025 | ✓ 成立 `compaction_workspace_root` @1907-1909 用于 list_entries(@1910),但 `apply()`(@2005)未收到 → 生产 data_dir=None 崩点 |
| 现状:runtime.py 666 行 list_turn_messages 漏传 workspace_root → 静默清空 history | 读 runtime.py:668 | ✓ 成立(实际 @668)`list_turn_messages(session_id)` 无 workspace_root;manager 内 catch 后返回 () → 失忆 |
| 现状:1962-1998 直接 enqueue 与 apply() 构成双写 | 读 runtime.py:1966-2010 | ✓ 成立:直写 compact_boundary(@1986)+summary(@1999),apply()→append_compaction 又写一对(@2005)。生产因 apply 崩第二写未完成 |
| 现状:applier.apply 无 workspace_root 形参 → append_compaction 默认 None 抛 | 读 applier.py | ✓ 成立 `applier.py:16-23` 签名无 workspace_root,@39 `append_compaction` 不传 |
| 现状:manager 已支持 workspace_root 形参,无需改签名 | 读 manager.py | ✓ 成立:list_entries(@280)、append_compaction(@227,默认 None)、list_turn_messages(@212)均已带形参 |
| 现状:main.py failed 分支只发 delivery_receipt,completed 还发 node.report | 读 main.py:3114-3173 | ✓ 成立:completed(@3114)发 send_report→node.report(message 级,message_id/agent_id/summary)+delivery_receipt;failed(@3165)仅 delivery_receipt |
| 现状:node.report failed 翻消息已是 IM 现有契约(IM 不改) | 读 gateway_handler.py | ✓ 成立 `_persist_report_event` @2298 映射 status→failed,@2337 追加 conversation.notice;`send_report` 支持 status/message_id/agent_id(upstream_reporter.py:276) |
| 决策 1:系统性贯穿 workspace_root | 四问 | ✓ 拍死、无歧义、与决策 2 不冲突、由 spec「压缩不崩」驱动;唯前提表述不精确(见 WARNING-2) |
| 决策 2:压缩落盘收敛为单一带根写入路径(经 append_compaction) | 四问 + 核被删块副作用 | ✗ 拍死但**不完整**:被删的直写块(1966-2002)含 `_session_histories[session_id]=[summary_msg]`(@1982),该内存态被下一轮 cache-first 消费(runtime.py:357/386);append_compaction 不复刻它,决策 2 未交代须保留 → 见 WARNING-1 |
| 决策 3:失败 message 级即时反馈,watchdog 退兜底 | 四问 + message_id 可得性 | ✓ 拍死、镜像 completed、由 spec「失败即时反馈」驱动;message_id 与 completed 同源(message.metadata)可得;error 真因经 summary 字段渲染(IM @2347 读 summary)— 镜像即得,无歧义 |
| 决策 4:单 M1 | 拆分门槛 | ✓ 单 M1 是默认,无需举证;反而过度举证。无横切问题 |
| spec Req「超长对话仍能正常回复 / 不失忆」 | design 有落点吗 | ✓ 决策 1+2 覆盖(list_entries 带根止崩 + list_turn_messages 带根止失忆) |
| spec Req「失败即时反馈真实原因 / 归属正确 agent」 | design 有落点吗 | ✓ 决策 3 覆盖(node.report status=failed + message_id + agent_id + summary) |
| spec 非目标「不恢复历史卡死会话 / 不重设压缩策略 / 保留 watchdog」 | design 越界吗 | ✓ 未越界:forward-fix only,决策 3 显式保留 watchdog 作兜底,不调腾挪阈值 |
| 澄清 Q1=full / Q2=含失败反馈 / Q3=以后不再发生 | design 对齐吗 | ✓ full 体量、B 面纳入失败反馈、forward-fix 一致 |
| kernel delta-spec MODIFIED「压缩可恢复」 | 锚 canonical?保留原 Scenario? | ✓ 忠实保留 canonical 正文(docs/specs/kernel/spec.md:299-316)+3 个原 Scenario 逐字,增第 4 个 Scenario,MODIFIED 用法正确;THEN 写消费者可观察(run 成功终态),无实现符号 |
| gateway delta-spec ADDED「失败即时反馈」 | 该 ADDED 还是 MODIFIED? | ✓ 真·平行新增:canonical 无「message 级失败反馈时效」既有 Req;与 Req「在飞 tool_call 收口」(@479)、Req 28 互补不冲突,ADDED 正确;THEN 消费者可观察 |
| im / cli no spec delta | 该不该有 delta? | ✓ IM 已支持 failed 翻消息(实测 gateway_handler);cli 不涉及。注明正确 |
| milestone 范围文件 | 与他组交集?可验? | ✓ 单组单 M,无并行交集;退出标准两轨齐(reviewer 引 spec Scenario / worker 含 data_dir=None 回归 + 单写守 + 全树) |

---

**架构进攻**(四角度逐个走):

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 决策 1 把 workspace_root 加到 per-turn `AgentState`(core);B 面改只落 personal_assistant | ✓ 无反向依赖:A 面全在 core,B 面只在 PA 的 relay callback(不碰 agent.core)。唯 workspace_root 是 session 级概念却挂到 per-turn state,略有归属张力,但 core 内、可接受。组合无内层反依赖 |
| 该不该存在 | 决策 1 新增 `AgentState.workspace_root` 字段 | △ 删除测试:loop.run 已收 `current_working_directory_override`(=workspace_root),`_maybe_compact` 调用点已在作用域 → 该字段把一个已在手的值重新立了第二个名字。代价:loop 内同值双名(cwd-override / workspace_root)邀请未来 drift;3 处构造点须长期维护该字段。详见 WARNING-2(决策可成立,但应权衡复用) |
| 深还是浅 | 两面是否新造抽象/重造轮子 | ✓ 走完无存活发现:A 面复用 manager.append_compaction/list_entries,B 面复用 reporter.send_report,无新封装、无新间接层 |
| 治本还是补丁 | 三条决策是否打补丁绕问题 | ✓ 走完无存活发现:决策 1 从源头贯穿(非逐点 hack)、决策 2 消双写(非补根了事)、决策 3 message 级正面反馈 + watchdog 退兜底,均治本;不弱化 stateless 契约 |

---

**Issues**(按 CRITICAL > WARNING):

- **[WARNING] [决策 2]**:决策 2 把压缩落盘「收敛为单一路径(经 append_compaction)」并删除直写块(runtime.py:1966-2002),但该块含一处 load-bearing 的内存副作用 `self._session_histories[session_id] = [summary_msg]`(@1982),它被下一轮 `_execute_loop` **cache-first 消费**(runtime.py:357 命中即用内存、@386 不回盘)。`append_compaction` 只写盘、不碰 `_session_histories`。**不改→坏事**:worker 若按字面把直写块整段删掉、只留 append_compaction,压缩后内存 history 缓存仍是旧的全量 → 下一轮(及 overflow retry 内复用缓存路径)继续用未压缩上下文 → 压缩在内存层失效 / overflow 复发;而决策 2 唯一规定的守护是「事件重放重建一致」测试,它从**磁盘**重建、照不到这条内存态回归——恰是本 unit 要消灭的「测试旁路遮蔽生产」同型盲区。建议决策 2 明确:收敛时须保留 `_session_histories` 重置(及 summary_uuid/parent 链接语义),或把「要删的冗余第二写」定义为 apply() 的持久化副作用、保留已带这些副作用的直写路径(即 incident 修复方向 1 的「改由已写好的直接路径构造 CompactionResult」),并补一条断言压缩后**内存** history 不含已摘要轮次的用例。

- **[WARNING] [现状分析 / 决策 1]**:现状断言「loop 层结构性地拿不到 workspace_root」不精确——`loop.run` 已通过 `current_working_directory_override`(loop.py:160)收到该值(runtime.py:601 传入 = config.workspace_root),且在 `_maybe_compact` 调用点(loop.py:289)处于作用域内。**不改→坏事**:决策 1 在此略失真前提上选择给 `AgentState` 加字段(需维护 3 处构造点 + loop 内同值双名),却未权衡「把已在手的 current_working_directory_override 直接穿进 _maybe_compact」这一更省的复用路径。决策仍可成立(显式 workspace_root 在语义上比借用 cwd-override 定位会话存储更干净),但请把现状改成「值已以 cwd-override 之名到 loop,本 unit 选择以显式 workspace_root 表达以免概念混用」,并说明为何不复用——否则 worker 只能照字面加字段,埋下双名 drift。

---

**Recommendations**(不阻断):

- 决策 3 正文用「error」指代失败原因字段,而 `send_report` 无 `error` 形参、IM 失败气泡文案实际读 `summary`(gateway_handler.py:2347)。镜像 completed 分支即可得(completed 用 `summary=reply_text`),建议在决策 3 或接口段一句点明「真因经 summary 字段承载」,省 worker 一次回查。
- 现状里多处行号(@659/@666/@2001/@1962-1998)与当前 runtime.py 实际行(663/668/2005/1986-2001)有小幅漂移,不影响定位,收尾归并时据实际 diff 校正即可。
