# bugfix-418-M1 — Progress

## 根因坐实（前置）

- `runtime.run` 入口 `runtime.py:286`：`self._session_locks.setdefault(session_id, asyncio.Lock())` 后 `async with lock`。该 Lock 在主 agent turn 首次跑时绑定到 RunsRegistry 专用循环。
- 旧前台路径 `agent.py:_run_subagent_turn_sync`（:611）在私有 ThreadPoolExecutor 工作线程里 `asyncio.run(runtime.run(...))` 起**瞬时新循环 L2**，L2 上 `async with` 那个绑定专用循环的 Lock → `<asyncio.locks.Event/Lock ...> is bound to a different event loop`。共享 httpx AsyncClient（绑专用循环，feat-335）同样跨循环 await。
- 缺陷二（故障隔离）：瞬时循环 L2 运行+close 污染共享单例，主循环 heartbeat/relay 下次操作即抛、协程静默死掉，进程在但失联。

## R1 — 前台 subagent 改走专用循环 + 删死代码 + 结构性单测

- Context:
- Decision:
- Rationale:
- Evidence:
- Rollback:
- Commits:

## R2 — 真 LLM e2e 回归守卫

- Context:
- Decision:
- Rationale:
- Evidence:
- Rollback:
- Commits:
