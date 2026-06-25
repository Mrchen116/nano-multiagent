# bugfix-437: 超长对话压缩落盘漏传 workspace_root 卡死黑屏 — 技术方案

> 对齐: incident.md v1

> Unit branch: `unit/bugfix-437` (will be created by orchestrator)

## Changelog

<!-- design 阶段保持空 -->

## 现状分析

### 涉及范围

- `src/agent/core/agent/loop.py` —— `_maybe_compact`(threshold 预压缩,每轮迭代开头先于 LLM 调用)调 `list_entries(session_id)` **漏传 `workspace_root`**。loop 层**结构性地拿不到** `workspace_root`(`AgentState` 无该字段,全文无 `workspace_root`)。本 unit 要让它拿到并传下去。← plato 最可能命中的崩点(它不直接落盘,崩在读取,解释了 JSONL 一条 `compact_boundary` 都没有)。
- `src/agent/core/agent/state.py` —— `AgentState` 定义,需新增 `workspace_root` 字段把根穿进 loop。
- `src/agent/core/agent/runtime.py` —— `_compact_session`(overflow 恢复 @659 / manual @889)已算出 `compaction_workspace_root`,却没传给 `2001` 行的 `apply()`;`666` 行 `list_turn_messages(session_id)` 漏传(吞异常 → 静默清空 history → agent 失忆);`1962-1998` 直接 enqueue 写 `compact_boundary`+summary,与 `apply()` 构成**双写**。
- `src/agent/core/agent/compaction/applier.py` —— `CompactionApplier.apply` 无 `workspace_root` 形参 → 内部 `append_compaction` 用默认 `None` → 抛。
- `src/agent/core/session/manager.py` —— `append_compaction` / `list_entries` / `list_turn_messages` 已支持 `workspace_root` 形参(默认 None),无需改签名,只需调用方传值。
- `src/personal_assistant/main.py` —— `_build_relay_lifecycle_callback` 的 `failed` 分支(@3165)只发 `send_delivery_receipt`(relay_task 级),不像 `completed` 分支(@3114)同时发 `node.report`(message 级带 `message_id`)。本 unit 要它补发 message 级 failed report。
- 只读不改:`src/agent/core/session/jsonl_store.py`(stateless 契约是正确设计,不动)、`src/IM/ws/gateway_handler.py`(`node.report` 已支持 `delivery_status="failed"` 翻消息)、`src/IM/application/relay_watchdog.py`(120s 兜底保留)。

### 既有约束

- **store 有意 stateless**(feat-330 / bugfix-348):每方法必须由调用方带 `workspace_root`,生产 `data_dir=None` 模式下拒绝猜测、缺了即抛 `SessionNotFoundError`。本 unit **遵守**该契约(把根补齐到调用点),不弱化它退回「猜测默认路径」。
- 分层:`personal_assistant` 只 import `agent.sdk`,不碰 `agent.core`/`platform` 内部 —— gateway 侧改动只在 PA 自己的 relay callback 内。
- 失败反馈走既有 `node.report` / `node.delivery_receipt` 上行协议,不新增协议帧。

### 可复用能力

- **失败反馈**:`completed` 分支已有「`node.report`(message 级,带 `message_id`)+ `delivery_receipt`」双发模式 —— `failed` 分支**镜像它**,不另造。
- **IM 落盘**:`node.report` 的 `delivery_status="failed"` 翻消息路径已存在(`gateway_handler.py:1184/2298`)—— 直接复用,IM 不改。
- **workspace_root 取值**:`_execute_loop` 已持有 session 的 `workspace_root`(以 `current_working_directory_override=session_workspace_root` 传入);`_compact_session` 已算出 `compaction_workspace_root` —— 都是现成的,只是没穿到底。

### 相关历史

- feat-330 / bugfix-348 确立 store stateless「每调用必带 workspace_root,拒绝猜测」。本 unit 是该契约在压缩子系统的**漏执行**修补,不是推翻它。
- feat-436(最近 kernel 改动)涉及 per-model context_window 压缩判定阈值 —— 只动「何时触发压缩」,不动「压缩怎么落盘」,与本 unit 无冲突。
- bugfix-426-M4(#140)同类症状家族:relay 在 message 级未被正确 finalize → 120s relay-idle 黑屏。本 unit 的 B 面是同一「占位气泡未在 message 级翻态」病根的另一触发路径。

## 架构总览

两个独立 bug 面,落在两个包;IM 不改(已支持)。

```mermaid
graph TB
  subgraph agentcore["agent.core (A 面: 压缩落盘漏传 workspace_root)"]
    loop["loop._maybe_compact<br/>threshold 压缩"]
    rt["runtime._compact_session<br/>overflow / manual 压缩"]
    state["AgentState<br/>(+ workspace_root)"]
    mgr["session.manager<br/>list_entries / append_compaction / list_turn_messages"]
    store["jsonl_store (stateless)<br/>每调用必带 workspace_root ← 不改"]
    state -.传根.-> loop
    loop -->|list_entries(ws)| mgr
    rt -->|append_compaction(ws)| mgr
    mgr --> store
  end
  subgraph pa["personal_assistant (B 面: 失败反馈只到 relay-task 级)"]
    runturn["inbound_pipeline._run_turn<br/>except → emit phase=failed"]
    cb["main relay_lifecycle_callback<br/>failed 分支 (+ node.report message 级)"]
    runturn --> cb
  end
  subgraph im["IM (不改)"]
    rep["gateway_handler._handle_report<br/>已支持 status=failed 翻消息"]
    wd["relay_watchdog<br/>120s 兜底 ← 保留"]
  end
  cb -->|node.report status=failed + message_id| rep
```

before/after 一句话:**A 面** —— 压缩各调用点把会话的 `workspace_root` 穿到底(loop 经 `AgentState`、runtime 经已算出的 `compaction_workspace_root`),并把压缩落盘收敛为单一带根的写入路径(消除双写);**B 面** —— run 失败时 gateway 在 message 级补发 `node.report(status=failed)` 翻占位气泡,120s watchdog 退回为「节点真死」最后兜底。

## 关键决策

### 决策 1: 系统性贯穿 workspace_root,而非逐点打补丁

**把会话的 `workspace_root` 穿透压缩全部调用点**:loop 经 `AgentState` 新增字段拿到根 → `_maybe_compact` 传给 `list_entries`;runtime 把已算出的 `compaction_workspace_root` 传给 `apply()` 与 `list_turn_messages`。

- **理由**:现状是 stateless store 契约的「漏执行」散落在 3+ 个调用点(threshold / overflow / manual / reload),逐点 hack 下一个调用点还会再忘 —— 正是「测试旁路遮蔽生产」的复发模式。根因是 loop 层结构性缺 `workspace_root`,补到 `AgentState` 从源头堵住。
- **拒绝**:① 让 store 在缺根时回退猜测默认路径 —— 直接违反 feat-330/bugfix-348 的 stateless 设计,把「大声失败」改成「静默走错路径」,更危险。② 只修 plato 命中的 threshold 一处 —— overflow/manual 路径仍是雷。
- **风险**:`AgentState` 是 `@dataclass`,加字段需核对所有构造点;workspace-aware e2e 才暴露,单测须显式构造 `data_dir=None` 场景。

### 决策 2: 压缩落盘收敛为单一带根写入路径(消除双写 + 修失忆)

**`_compact_session` 的压缩落盘只走一条带 `workspace_root` 的写入路径,删除冗余的第二次写**;`list_turn_messages` 重载补传 `workspace_root`。

- **理由**:`runtime.py:1962-1998` 直接 enqueue 与 `2001` 行 `apply()→append_compaction` 写的是同一对 `compact_boundary`+summary —— 双写既冗余又是崩点。收敛为单一路径(经 `append_compaction(workspace_root=…)`)后,既消双写又自然带根;`list_turn_messages` 漏传会静默清空 history(违反「压缩后不失忆」),一并补根。
- **拒绝**:保留双写、只给两条都补根 —— 仍留冗余写入与未来 drift 面。
- **风险**:收敛写入路径时须保证 `compact_boundary` 仍在 summary turn **之前**落盘(`jsonl_store.load` 靠它界定保留窗口);改动须有「压缩后重放重建一致」的测试守。

### 决策 3: 失败在 message 级即时反馈,watchdog 退为最后兜底

**gateway `failed` 分支镜像 `completed`,补发 `node.report(status="failed", message_id, error)` 翻占位气泡**;保留既有 `delivery_receipt` 与 IM 120s watchdog。

- **理由**:`_run_turn` 已 emit `phase=failed` 带真因,缺的只是 callback 里那条 message 级 report —— 占位气泡靠它翻态。补上后任何 run 失败都秒级、带真因可见。watchdog 仍保留,只在「整个节点真死、什么都发不出」时兜底(它本就是为此设计)。
- **拒绝**:① 缩短 watchdog 120s 窗口 —— 治标,且会误杀静默长命令/等权限等合法长窗口(gateway spec 已有这些 Scenario)。② 在 IM 侧改 —— IM 已支持 failed report,无需动。
- **风险**:失败时 `message_id` 须仍在 `message.metadata`(completed 分支同源读取,已验证可得);需测「run 失败 → 气泡秒级翻 failed 带真因」。

### 决策 4: 单 milestone

**单 M1 端到端修两面 + 补回归。** 详见 Milestones 段理由。

## 接口与数据流

不新增对外 API / 协议帧。核心是把已有数据(`workspace_root`)穿到底 + 复用已有上行帧(`node.report`)。

### 主流程:超长对话触发压缩(before vs after)

```mermaid
sequenceDiagram
  participant U as 用户(IM)
  participant GW as Gateway
  participant LP as loop/runtime(agent.core)
  participant ST as session store
  Note over LP: 对话增长,迭代开头触发 threshold 压缩
  rect rgb(255,235,235)
    Note over LP,ST: BEFORE(bug)
    LP->>ST: list_entries(session_id)  # 漏 workspace_root
    ST-->>LP: ❌ SessionNotFoundError
    Note over LP: run 失败,事件流静默
    Note over GW: failed 只发 delivery_receipt(relay-task 级)
    Note over U: 占位气泡卡 running → 120s 后 watchdog 兜底「relay idle」
  end
  rect rgb(235,245,235)
    Note over LP,ST: AFTER(fix)
    LP->>ST: list_entries(session_id, workspace_root)  # 带根
    ST-->>LP: entries
    LP->>ST: append_compaction(workspace_root)  # 单一带根写入
    Note over LP: 压缩透明,run 继续出完
    U-->>U: 回复正常完成(无错误气泡)
  end
```

### 失败路径(after):run 真失败时

```mermaid
sequenceDiagram
  participant RT as _run_turn
  participant CB as relay_lifecycle_callback
  participant IM as IM _handle_report
  participant U as 用户
  RT->>RT: 捕获异常 → emit phase=failed(error=真因)
  CB->>IM: node.report(status=failed, message_id, error)  # 新增 message 级
  CB->>IM: delivery_receipt(failed)  # 既有,保留
  IM-->>U: 占位气泡秒级翻 failed,显示真因 + 正确 agent 归属
```

## 契约层增量 (delta-spec)

- kernel:  `specs/kernel/spec.md` —— 强化「上下文压缩在长会话中保持可恢复」:增加消费者视角 Scenario「持续增长的会话触发压缩 → run 透明继续完成,不因会话存储定位失败而报错」。
- gateway: `specs/gateway/spec.md` —— 新增 Requirement/Scenario「run 真失败 → message 级即时上报失败带真因,不等 idle 看门狗」。
- im:      no spec delta(`node.report` failed 翻消息已是现有契约)。
- cli:     no spec delta(不涉及)。

## 风险与回退

- **AgentState 加字段的波及面**:它是 loop 单轮状态的载体,构造点需逐个核对(grep `AgentState(`)。回退:字段给默认值,缺省不破坏现有构造,但默认值不能是「猜测路径」——缺根仍应大声失败。
- **压缩写入路径收敛的正确性**:`compact_boundary` 与 summary 的先后顺序是 `load()` 重建的关键。风险点是收敛时打乱顺序导致历史窗口错位。守护:加「压缩后由事件重放重建,历史一致」的测试。
- **测试盲区复发**:本 bug 的根源是测试用 `data_dir` 脚手架照不到生产 workspace-aware 路径。回退无意义 —— 关键是**补一条 `data_dir=None` 下触发压缩的回归用例**,否则修了也防不住再发。
- **回滚**:本 unit 改动均为「补传已有参数 / 补发已有帧」,无数据结构变更,可整体 revert 回到当前行为(即回到本 bug),无迁移负担。

## Runbook for Reviewer

本 unit 改 agent 内核(被 Gateway 进程内持有)+ Gateway relay callback。reviewer 需经真栈 IM ↔ Gateway 验「超长对话压缩不崩 + 失败秒级反馈」。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM (uvicorn) | `stop_pidfile .im.pid`(或 kill 对应 PID) | `IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" > .im.log 2>&1 & echo $! > .im.pid` | `curl -s http://127.0.0.1:$IM_PORT/` 返回前端入口 |
| Gateway | `stop_pidfile .gateway.pid`(`--foreground` 起的) | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 `[connected]` |

> 推荐直接用 `./scripts/e2e-up.sh` 一键起 IM+Gateway(自动分配端口/隔离 config/auto-bind),`./scripts/e2e-down.sh` 干净停。worktree 内务必走 ephemeral 端口,勿占主仓 8011。

**Review 驱动方式**: 端到端真栈。本 unit **改了客户端面可观察行为**(IM 聊天气泡:超长对话回复正常出完、失败秒级翻态带真因),须真驱动:在 Web IM 与某 agent 持续对话直到触发压缩、并构造一次 run 失败,走查聊天气泡的两个 Requirement。压缩触发可观察上下文增长成本高,reviewer 可借「构造接近上限的会话」或核对压缩落盘事件辅助判定,但最终结论以 IM 气泡可观察结果为准。

## Milestones

单 M1。两面(agent-core 压缩 / gateway 失败反馈)虽在不同包、文件零交集,理论可并行,但体量都不大(合计预计 < 400 行、< 10 文件,单 worker 窗口内可完成),且同属一个事故 —— 一个 worker 端到端修两面 + 走完整旅程验证(超长对话不崩 ↔ 失败秒级反馈本就互补)更连贯。不满足「工作量超窗口 / 必须分阶段验证」任一硬触发,按默认不拆。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-437-M1 | fix | — | A | `src/agent/core/agent/{loop.py,runtime.py,state.py}`、`src/agent/core/agent/compaction/applier.py`、`src/agent/core/session/manager.py`(若需)、`src/personal_assistant/main.py`、`src/personal_assistant/gateway/inbound_pipeline.py`(若需)、相关测试 | `[reviewer]` 超长对话中 agent 回复完整正常出完、不卡 running、无错误气泡(Req-超长对话仍能正常回复 / Scenario-触及记忆上限)<br>`[reviewer]` 长对话后 agent 不失忆,能连贯回答更早内容(同 Req / Scenario-长对话后不失忆)<br>`[reviewer]` 任意 run 失败时用户数秒内见失败态 + 真实原因,归属正确 agent,不等约两分钟笼统超时(Req-失败即时反馈 / 两个 Scenario)<br>`[worker]` 新增 `data_dir=None`(workspace-aware)下触发 threshold + overflow 压缩的回归用例,断言压缩落盘成功且会话可由事件重放重建、历史不被清空<br>`[worker]` 压缩落盘单一路径(无双写),`compact_boundary` 仍先于 summary turn<br>`[worker]` 全测试树 `pytest -m "not e2e"`(含 im_service)不回归;`ruff check` + `ruff format` 绿 |
