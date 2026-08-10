# bugfix-361: IM running 占位消息超时回收 watchdog

## Relations

- Closes: #22
- Related: 后续可另开 unit 做 Gateway try/finally 兜底 + 前端 placeholder 超时 UX(本 unit 不含)

## 原始报告

> ## 现象
>
> 会话 `bd4b7e7f9d49471db63bdf28898bf4a1` 在 2026-05-18 12:37 用户断网瞬间被卡住。表现：UI 一直显示 agent「正在回复」，用户无法继续输入。
>
> 排查后发现：数据库里 agent 的最后一条消息 `ad2d42584b09458682099a4cdb80eda0` 处于 `delivery_status='running'`、`content=''` 的状态，永远不会被翻成 `failed` 或 `completed`。
>
> 进一步用 `SELECT id, sender_type, delivery_status, created_at FROM messages WHERE delivery_status='running'` 扫了一下，**最近 4 天里累计 10 条**这种孤儿 running 消息（5-14 起），说明不是网断专属，凡是 relay 过程中 Gateway 端 LLM 调用 / WS 链路异常未走到 `relay.completed` 或 `relay.failed`，IM 这条 placeholder 就会永久留在 `running`。
>
> ## 根因
>
> `src/IM/infra/repositories.py:1238`：
>
> ```python
> delivery_status = (
>     "running" if event_type == "relay.processing"
>     else "failed" if event_type == "relay.failed"
>     else "completed"
> )
> ```
>
> `running` 只能靠后续 `relay.completed` / `relay.failed` 事件翻转。但 Gateway 侧任何丢链路、进程崩溃、网络断、LLM 超时挂死的场景都不会再发这两个事件，IM 也没有 watchdog 去检查长时间 `running` 的消息。
>
> ## 修复方向
>
> 1. **IM 侧 watchdog**：起一个后台任务，扫描 `delivery_status='running'` 且 `now - created_at > N`（建议 5 min）的消息，强制翻成 `failed`，并 push `relay.failed` 给前端。
> 2. **Gateway 侧**：处理 LLM 调用的 try/finally 必须保证至少发一条 `relay.completed` 或 `relay.failed`；进程退出钩子里也兜一遍未结束的 turn。
> 3. **前端**：即便后端没回收，UI 也应在 placeholder 上挂超时（e.g. 90s 没增量就允许用户取消或重发）。
>
> ## 已做的临时修复
>
> ```sql
> UPDATE messages SET delivery_status='running' WHERE delivery_status='running';
> ```
>
> 10 条历史 stuck 全部清理，会话可继续。
>
> ## 复现路径
>
> 1. 在群聊里 @ 一个 agent
> 2. agent 流式回复中途断网（或 kill Gateway）
> 3. 网恢复后 UI 永久卡在「正在回复」

## 澄清记录

- Q1: 范围 — 做单层 IM watchdog 兜底,还是三层(IM + Gateway + 前端)全做?
  A(原话): ok
  Agent 解读: 用户同意只做 ① IM watchdog,按 bugfix lite 处理;Gateway 与前端的防御作为后续单独 unit,不在本 unit 范围内。

## 现象 / 复现

参见【原始报告】。可观察到的卡死症状:placeholder 消息在 DB 中 `delivery_status='running'` 且 `content=''` 永久不翻转,前端 UI 持续显示 agent「正在回复」,用户无法在该会话继续发送消息。

复现路径(issue 给出):

1. 群聊 @ 一个 agent
2. agent 流式回复中途断网(或 kill Gateway 进程)
3. 网络恢复后 UI 永久卡在「正在回复」

历史数据佐证:最近 4 天累计 10 条孤儿 `running` 消息,横跨多种异常路径(网断、进程异常、LLM 超时),非单一触发条件。

## 根因

直接原因:`src/IM/infra/repositories.py:1238` 将 `delivery_status` 的流转完全绑死在 `relay.processing → relay.completed/failed` 事件链上,而 IM 端没有任何兜底机制检查长时间 `running` 的消息。Gateway 侧任何未走到 `relay.completed` / `relay.failed` 的异常路径(WS 断、进程崩溃、LLM 挂死)都会让 placeholder 永久卡在 `running`。

深层原因:relay 状态机的设计假设了 Gateway 一定会回发终态事件,把"消息能否被回收"这件事完全外包给了上游(Gateway)。这是一个**缺少最后一道防线**的设计——IM 作为消息持久化方,本应对自己持久化的状态有自洽的回收能力,不应假设上游永远可靠。review 阶段没意识到这条隐式依赖,测试也没覆盖"上游永远不回终态"的场景。

## 修复

新增 IM 侧 watchdog,作为 placeholder 状态回收的最后一道防线,不再假设 Gateway 永远会回发终态事件。

实施要点:

- `src/IM/application/relay_watchdog.py`(新增):
  - `scan_and_fail_stuck_running_messages(connection, event_repository, timeout_seconds=300)` 扫描 `messages.delivery_status='running'` 且 `created_at < now - timeout` 的行,对每条:
    1. 读取该 message 最新的 `relay.processing` 事件 payload(若存在),把 `relay_task_id` / `agent_id` / `node_id` / `run_id` 透传过来——保证前端 synthetic-message 映射逻辑(`_synthetic_message_id_from_event_payload`)产出的 id 不变,placeholder 直接原地翻状态,而不是新增一条 bubble。
    2. 通过 `EventRepository.append_event` 落一条 `relay.failed` 事件(`progress_state='failed'`、`semantic='relay_watchdog_timeout'`、`detail='relay timed out after Ns ...'`),由现有 `notify` 钩子推到 WS 客户端。
    3. 通过 `EventRepository.update_message_delivery_status` 把 `messages.delivery_status` 翻成 `failed`。
    4. 单条失败被吞掉(`logger.exception` + `continue`),不让一行脏数据卡死整轮扫描。
  - `run_relay_watchdog(...)` 后台循环,每 `interval_seconds` 跑一次扫描;复刻 `run_offline_guard` 的写法,由 FastAPI lifespan 持有 task 句柄,shutdown 时 `cancel`。
- `src/IM/app.py` lifespan 段:`asyncio.create_task(run_relay_watchdog(...))`,并通过环境变量调节:
  - `IM_RELAY_WATCHDOG_INTERVAL_SECONDS`(默认 30s)— 扫描频率。
  - `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS`(默认 300s = 5 min,对齐 issue 建议值)— 判定 stuck 的窗口。
- `tests/im_service/unit/test_relay_watchdog.py`(新增 4 个用例):
  - stale running → 翻 failed + 发 `relay.failed`
  - fresh running(未到窗口) → 不动
  - 已经 `completed` / `failed` 终态 → 不动(幂等)
  - prior `relay.processing` payload 继承 → 同步 synthetic id 字段

注释只解释"为什么"(IM 不能信任 Gateway 是终态事件的真值源),不复述代码 do-what(遵循 COMMENTING_GUIDE)。

## 验证

**单元测试**(都过):

```
PYTHONPATH=src pytest tests/im_service/unit/test_relay_watchdog.py -xvs
→ 4 passed
```

**整 IM 套件无新增回归**:

- worktree 上 `tests/im_service/` 全跑(忽略 `test_agent_config_api`):201 passed / 20 failed
- 同等条件下 main 上跑:197 passed / 20 failed
- 多出来的 4 个 pass 正是新加的 watchdog 用例;20 个失败在 main 上同样存在(`test_agent_config_api`、`test_relay_service` group/picker 用例、`test_ws_event_types` token usage 等),与本 unit 改动无关。

**lifespan 装配自检**:

```
PYTHONPATH=src python -c "from IM.app import create_app; create_app()"
→ ok
```

确认新增的 `run_relay_watchdog` task 创建路径不破坏 app 构建。

**修前 / 修后行为对照**:

| 场景 | 修前(原 #22) | 修后 |
|---|---|---|
| 群聊 @ agent,流式回复中断网 | placeholder 永久 `running`,UI 卡「正在回复」 | 5 分钟后 watchdog 把消息翻 `failed`,推 `relay.failed`,UI 显示失败状态,用户可继续发 |
| 历史已 stuck 的 running 消息(IM 启动时已存在) | 永不回收 | IM 启动后第一轮扫描(~30s 内)即回收 |
| 正常 running(LLM 还在回复中) | — | 不到 timeout 窗口,不动;一旦 Gateway 发 `relay.completed` 照常翻 `completed`,watchdog 不与正常路径冲突 |

后续仍可另开 unit 做 Gateway 侧 try/finally 兜底 + 前端 placeholder 超时 UX(三层防御的另外两层),但 IM watchdog 本身已经让症状彻底消失。
