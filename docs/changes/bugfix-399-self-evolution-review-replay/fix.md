# bugfix-399: self-evolution review 通知重复刷屏(无对应 LLM 交互)

## Relations

- Related: feat-349-self-evolving-skills-memory   # 引入后台 self-evolution review fork + 通知的 unit
- Related: refactor-387                            # 引入本回归的 unit(gateway 进程内化时丢失 anchor 语义)

## 原始报告

> http://127.0.0.1:58232/chat/7d5c7bbe3ae946b1ba8370574e6fbe7b 在9:43后，输出了5个·
> background self-evolution review: self-evolution updated。但是llm proxy侧，我看不到有
> 相关llm交互。帮我研究定位为啥会不停输出updated

## 现象 / 复现

个人助手聊天窗口里,在某一时刻之后连续弹出 5 条系统通知
`· background self-evolution review: self-evolution updated`,看起来像后台自我进化在不停
触发。但 LLM proxy 侧在同一时间段没有任何对应的模型调用记录——通知在刷,模型却没动。

复现路径:与某个 agent 持续对话若干轮(期间后台 self-evolution 至少真实触发过一次),之后
每发一条新消息,就会再被推送一遍历史上那条"updated"通知;消息发得越多 / 历史里攒的 review
事件越多,刷出来的条数越多。期间 LLM proxy 无新增交互。

附带可观察症状:通知文案恒为泛化的 `self-evolution`,从不显示具体是 `skills` 还是 `memory`。

## 根因

单一根因:**网关主事件循环以 `after_sequence=0` 订阅进程内事件流,导致每轮对话都重放整个
session 历史,把过去真正发生过的 `self_evolution_review` 旧事件当成新事件再次转发。**

链路:

1. 后台 hook(`self_improvement`)在累计若干轮后 fork 一次自我学习子会话(这一次才真正调
   LLM),完成后调 `publish_session_event("self_evolution_review", …)`,事件进入进程内
   `EventStreamHub`。该 hub 带 2000 条上限的历史缓冲,进程存活期间事件一直留存。
2. `personal_assistant/gateway/inbound_pipeline.py` 的每轮主循环把 `anchor_sequence`
   硬编码为 `0`(注释误以为"in-process 不需要 replay"),传给 `kernel.stream(after_sequence=0)`。
   `after_sequence=0` 不是"不重放"而是"重放全部历史"——于是每轮都把该 session 历史里所有
   `self_evolution_review` 事件重新吐一遍。
3. 主循环的 `_on_other_event` 对 `self_evolution_review` 无任何按序号去重,逐条调用回调
   发 IM 系统消息。重放出来的是旧事件,**没有新 fork**,所以 LLM proxy 看不到交互。

两处放大 / 次生缺陷:

- 主循环与持久后台订阅者(`background_session_events.py`)两条路径都会转发
  `self_evolution_review`,同一事件存在被两路各发一次的窗口。
- `personal_assistant/main.py` 的通知回调从 `event["data"]` 读 `reviewed_skills` /
  `reviewed_memory`,但 SSE 事件是**扁平 dict**(这两个字段在顶层、不在 `data` 下),永远读
  不到 → subject 恒退化为 `self-evolution`,这是"从不显示 skills/memory"的原因。

**原始设计意图 / 必须保住的不变量**(来自 feat-349):`self_evolution_review` 通知的语义是
"后台自进化**真正发生**了一次,已更新 skills/memory"。修复要消除的是**重放/重复**,而不是
通知本身——每发生一次真实 fork,用户仍应**恰好收到一次**通知,且能区分 skills / memory。
不能为了消掉刷屏把通知整条砍掉。

**为什么这种错能进来(回归引入点,非原始设计遗漏)**:feat-349 的事件投递设计本身**正确**,
不是设计遗漏。回归是 **refactor-387/M3**(commit `8840e42f`,2026-05-29,gateway 进程内化)
引入的。重构**前**(HTTP/SSE 时代)这段锚点逻辑是对的:

```python
# anchor_sequence is captured before the run starts; use it as Last-Event-ID
raw_anchor = run_payload.get("anchor_sequence")
anchor_sequence = int(raw_anchor) if isinstance(raw_anchor, int) else None
```

即:run 携带一个"开始前捕获的 anchor",订阅只取本 run 之后的事件,历史不会被重放。重构把内核
从 HTTP API 改成进程内库时,删掉了 HTTP 的 `run_payload`、改用 `kernel.submit()` 返回的
`run_record`,却**没有把 anchor 语义一起迁移**,而是写死成 `0`,并配了误导性注释
"in-process mode: no SSE replay needed"——判断恰好反了:进程内 `EventStreamHub` 同样保留
历史,`after_sequence=0` 等于"重放全部历史"。

根本教训:**重构丢失了一个隐式契约**。anchor 当年藏在 HTTP `run_payload` 里,是个未被显式
建模的约定,从没成为 run 的一等属性,所以换传输层时最容易蒸发。本次修复把它提升为
`RunRecord.start_sequence`(run 自带起始序号),正是把这条隐式契约显式化,以后再换底层传输
也不会再丢——这也是选"run 携带起点"而非"消费方事后去重"的根因所在。

## 修复

架构性修复(让每次 run 自带"我从事件流的哪一页开始",而非靠消费方事后去重):

- `agent/core/runs/registry.py`:`RunRecord` 新增 `start_sequence` 字段;`RunsRegistry.submit`
  在发布本 run 首个 QUEUED 事件**之前**快照 `event_hub.current_sequence()` 写入该字段。这是
  "本 run 从哪开始"的唯一权威。`EventHubLike` 协议补 `current_sequence()`。
- `personal_assistant/gateway/inbound_pipeline.py`:主循环锚定 `run_record.start_sequence`
  (不再用 `0`),只消费本 run 及之后的事件,历史不再被重放。
- `personal_assistant/gateway/inbound_pipeline.py`:删除主循环 `_on_other_event` 中对
  `self_evolution_review` 的转发分支,session 级事件收归持久后台订阅者**独家**处理,同一事件
  不再被两路各发一次。
- `personal_assistant/main.py`:通知回调改为直接读扁平字段 `event["reviewed_skills"]` /
  `event["reviewed_memory"]`,subject 恢复正确显示 skills / memory / skills + memory。

commit:`58867a21`(分支 `bugfix-self-evolution-review-replay`)。

## 验证

- 修前:多轮对话后每发新消息即重复推送历史 review 通知(LLM proxy 无对应交互),且文案恒为
  `self-evolution`。
- 修后:主循环只收本 run 事件,历史不再重放;`self_evolution_review` 仅由持久后台订阅者在
  **真实 fork 完成后**转发一次;不变量保住——真发生一次学习,用户恰好收到一次通知,subject
  正确区分 skills / memory。
- 回归测试:`tests/unit/test_runs_registry.py`、`tests/unit/agent/runs/`、
  `tests/unit/personal_assistant/`、`tests/contract/`、`tests/unit/test_self_improvement_hook.py`、
  `tests/unit/personal_assistant/test_background_session_events.py` 全绿(合计 436 passed,
  1 skipped)。`ruff check` + `ruff format --check` 通过。
