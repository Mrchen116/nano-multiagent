# bugfix-437: 超长对话中 agent 回复卡死黑屏 + 失败干等两分钟才报笼统超时

## Relations

- 无（未发现相关 unit / issue）

## 原始报告

> http://127.0.0.1:8011/chat/4549b2bd294744129dfea6bdb5f64703 报了[error] relay idle for 120s with no new event，进行 debug，分析到底问题在哪？

> 也有可能是不是触发了压缩呀？

> 对应的 Jsonl是不是还在？你能看到吗？

Agent 解读（取证已完成，作为下文 RCA 的事实基础，非用户原话）：报到 IM 上的「relay idle for 120s with no new event」是 IM 侧 `relay_watchdog` 的兜底文案/症状，不是病根。

## 澄清记录

- Q1: 这个 bugfix 建成 full 还是 lite?
  A(原话): full

- Q2: 验收要不要把「真正失败时的反馈」也算进来（(a) 修好崩溃让回复正常出完 + (b) 真失败时秒级带真实原因反馈，而不是干等 120s）?
  A(原话): 好

- Q3: 已经卡死的那条会话要不要在本 unit 里「恢复」，还是只保证以后不再发生?
  A(原话): 以后不再发生就行

## 用户场景

用户在 IM 里跟某个 agent 持续对话。随着来回越来越多，对话会变得很长——长到触及模型一次能「记住」的上限。这是个长对话场景下必然会到的临界点，正常产品行为应该是：用户**无感**地继续聊下去，agent 该总结的自己总结、该记的还记得，回复照常出完。

实际发生的（plato 这条会话）：对话变得很长之后，用户再发一条消息，agent 开始回复、甚至已经吐出了一部分内容和若干次工具调用，然后**整条回复就卡死了**——前端一直显示「正在回复」的转圈，既不继续、也不报错。用户干等了整整两分钟，最后只等来一句笼统的 `[error] relay idle for 120s with no new event`，既没说真实原因（其实是这次回复因为对话太长而处理失败），也让人误以为是网络/服务挂了。

这里其实暴露了两层都坏掉的用户体验：

1. **长对话本不该让回复崩掉**——到了模型记忆上限，系统理应自动腾挪、让 agent 继续答完，这对用户应当完全透明；现在却直接把回复卡死。
2. **就算某次回复真失败了，反馈也不该让人干等两分钟、还给一句假原因**——任何一次 agent 回复失败（不限于这次的长对话场景），用户都应在数秒内看到失败、并看到可读的真实原因。这次的两分钟黑屏，正是第 2 层缺失把第 1 层的崩溃放大成了用户灾难。

修复后要回到的基线：超长对话里 agent 回复正常出完、不失忆；任何回复失败都秒级、带真因地反馈。

## 验收标准

> 用户可观察的回归行为契约。reviewer 逐条走 IM 真实旅程验收。

### Requirement: 超长对话中 agent 仍能正常回复

#### Scenario: 对话长到触及模型记忆上限
- **GIVEN** 用户与某 agent 的对话已经非常长（接近模型一次能处理的上限）
- **WHEN** 用户再发一条消息，agent 开始回复
- **THEN** agent 的回复完整、正常出完，聊天里不出现错误提示，回复不卡在「正在回复」状态

#### Scenario: 长对话之后 agent 不失忆
- **GIVEN** 对话已经非常长并继续往下聊
- **WHEN** 用户追问更早聊过的内容
- **THEN** agent 仍能连贯作答，不表现为忘记了之前的对话

### Requirement: agent 回复失败时用户立即看到真实原因

#### Scenario: 回复失败的即时反馈
- **WHEN** 某次 agent 回复因故无法完成
- **THEN** 用户在数秒内看到该条回复转为失败状态，并附带可读的真实失败原因
- **AND** 用户不需要等约两分钟才收到一句笼统的超时提示

#### Scenario: 失败提示归属正确的 agent
- **WHEN** 失败提示出现
- **THEN** 它显示为对应 agent 发出（带该 agent 的名字/头像），而非匿名的统一兜底文案

## 范围与非目标

- **不做**：恢复/迁移已经卡死的历史会话（forward-fix only，Q3 已确认）。修复后那条会话能否自然继续属于副产物，不列为交付物。
- **不做**：重新设计「对话多长才腾挪 / 保留多少近期内容」的策略与阈值本身。本 unit 只修「腾挪落盘时崩溃」与「失败反馈缺失」，不调腾挪何时发生、力度多大。
- **保留**：IM 侧那条「两分钟无事件即兜底」的最后防线仍保留——它只在「整个 agent 节点真的死掉、什么都发不出来」时兜底，不再是一次回复失败的常规反馈路径。

## 影响范围

- **谁受影响**：所有经 Gateway 跑、对话会变长的 IM agent（plato/hume/luban 等长任务型 agent 首当其冲，因为它们一次回复里会大量调工具、上下文涨得快）。
- **触发条件**：单个 agent 会话上下文累积到触发模型上下文溢出（本例 plato 的 session JSONL 已达 2.0MB / 253 turns，死前最后一串全是 `bash grep` 把大量代码读进上下文）。
- **严重度**：高。命中即该次回复**永久卡死黑屏**，用户须等 120s 兜底；且兜底文案掩盖真因，调试者也被误导（误以为网络/relay 问题）。
- **数据损坏**：无。会话 JSONL 完整，干净停在最后一个成功工具结果（无半截写入、无重复 `compact_boundary`）；崩溃发生在腾挪落盘**之前**，磁盘状态一致，会话可 resume。
- **只在生产暴露**：仅当存储工作在「workspace-aware」模式（生产路径）才命中；测试脚手架走 `data_dir` 旁路，路径解析不要求 `workspace_root`，因此单测全绿、线上必崩。

## 根因分析（RCA）

### 取证链路（症状 → 病根）

1. IM 端 `relay_watchdog`（`src/IM/application/relay_watchdog.py`）把一条卡在 `running` 超过 120s 无新事件的 agent 回复 reap 成 `failed`，写下合成文案「relay idle for 120s with no new event」。这是**症状/安全网**，不是病根。
2. 该回复（message `6002269f…`）事件流：正常推送 deltas/tool_call 到 `14:43:24` 后**彻底静默**（连 heartbeat 也停），直到 `14:45:32` 被 watchdog reap。说明背后的 run 在 14:43:24 后已死。
3. Gateway 日志坐实死因：
   ```
   run_failed | error='cannot resolve session path: the store was constructed with data_dir=None
   (production workspace-aware mode) but the caller did not pass workspace_root — refusing to guess
   the session location', run_id='run_df4ba69f098b3e40', session_id='sess_915bcb60811a17c6'
   ```
   且该 `RuntimeError` 从 `inbound_pipeline._await_terminal_run_async` 逃逸成 unhandled background-task exception。
4. 会话 JSONL（`…/workspace/plato/.nanoassistant/sessions/sess_915bcb60811a17c6.jsonl`）2.0MB、最后写入 14:43:23，**0 条 `compact_boundary` / 0 条 `is_compact_summary`**——腾挪一个字都没落盘就崩了 → 崩点在落盘动作本身。

### 病根（哪行错了）

上下文溢出触发腾挪（`runtime._compact_session`，`reason=OVERFLOW`，由 `runtime.py:651` 溢出恢复分支调起）。`_compact_session` 开头已正确算出 `compaction_workspace_root = config.workspace_root` 并用于 `list_entries`，**却没把它传给落盘动作**：

- `runtime.py:2001` → `CompactionApplier.apply(...)`（`compaction/applier.py:16`，**签名里压根没有 workspace_root 形参**）
- → `manager.append_compaction(...)`（`session/manager.py`，默认 `workspace_root=None`）
- → `_store.append(session_id, …, workspace_root=None)`
- → `JsonlSessionStore._resolve_base(None)`（`session/jsonl_store.py:565`）→ 抛 `SessionNotFoundError`

`append` 不 catch 该异常 → run 失败，error 即上面那句。

### 为什么这种错能进来（防再发着力点）

1. **路径解析有「测试旁路」遮蔽**：`_resolve_base` 只要构造时给了 `data_dir` 就直接返回、忽略 `workspace_root`；生产 `data_dir=None` 才强制要求 `workspace_root`。测试普遍用 `data_dir` 脚手架 → 腾挪落盘缺 `workspace_root` 这条路径在测试里**永远走不到**。这是本仓「本地绿/CI 绿、线上必崩」的同类反复陷阱（workspace-aware 模式漏传 `workspace_root`）。**着力点**：补一条 `data_dir=None`（workspace-aware）下触发腾挪的回归用例。
2. **失败反馈缺失把崩溃放大成灾难**：Gateway `_await_terminal_run_async` 见 run 终态为失败时 `raise RuntimeError(...)`，异常逃逸为后台任务异常，**没有主动给 IM 推终态失败事件**。于是 IM 只能靠 120s watchdog 兜底，用户干等且拿到假原因。**着力点**：run 失败时 Gateway 即时 emit 带真因的终态失败反馈。
3. **同路径潜伏缺陷**（RCA 顺带发现，留待 design 权衡是否一并处理）：
   - `runtime.py:666` `list_turn_messages(session_id)` 同样漏传 `workspace_root`；其内部 catch `SessionNotFoundError` 后返回 `()` → 不崩但会**静默清空 history**（agent 失忆），是同一漏传模式的另一面。
   - 腾挪存在**双写**：`runtime.py:1962-1998` 已用 `writer.enqueue(path,…)` 直接写 `compact_boundary` + summary，`2001` 行 `apply()` 仅为构造返回对象却又 `append_compaction` 写一遍。`apply()` 的持久化副作用是多余且有害的。

## 修复方向

> 高层方向，行级实现与「潜伏缺陷是否一并修」的取舍留给 design / milestone。

1. **修崩溃（agent-core）**：让腾挪的落盘路径稳定携带会话的 `workspace_root`——把 `_compact_session` 已算出的 `compaction_workspace_root` 串到落盘动作；或消除 `apply()` 的冗余持久化副作用、改由已写好的直接路径构造 `CompactionResult`。顺带评估 `list_turn_messages` 漏传的同类修法。
2. **修反馈（gateway relay）**：run 以失败终态结束时，Gateway 主动 emit 一条带真实原因、归属正确 agent 的终态失败反馈给 IM，使失败秒级可见；保留 IM 120s watchdog 仅作「节点真死」最后兜底。
3. **补回归**：新增 `data_dir=None`（workspace-aware）下触发上下文腾挪的用例，堵住「测试旁路遮蔽生产路径」的盲区。
