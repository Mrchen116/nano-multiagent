# Design Review: bugfix-446-gateway-im-resilience

**结论**: Approved

**Reviewer**: design-reviewer (极致分析模式)
**日期**: 2026-06-29

---

## 核实台账

逐条核过的承重原子。结论附证据，不是打勾。

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| 现状: `run_forever` 单一 `except Exception` | 读 `im_connection.py:337` | ✅ 生产代码确实 `except Exception as exc`，漏 `CancelledError`/`KeyboardInterrupt` 等 `BaseException` |
| 现状: `_mark_disconnected` 在 807，`set_exception` 无保护 | 读 `im_connection.py:807-821` | ✅ `ack_future.set_exception(...)` 无 `suppress(InvalidStateError)`，但 check(`done()`)与 set 间无 await，经典 TOCTOU 在单 loop 下实际不成立——design 也这么判断 |
| 现状: eager `connect_once()` 裸调用 | 读 `main.py:1580` | ✅ `await self._im_connection_manager.connect_once()` 在 `_ready_event.set()` 之后、无 try/except |
| 现状: `_post_im_connect` 只 catch `GatewayStartupError` | 读 `main.py:1582-1587` | ✅ `except GatewayStartupError as exc: ... raise`，其他异常（`OSError`/HTTP 错误）逃逸 |
| 现状: `im_task` 无 done callback、无 watchdog | 读 `main.py:1588-1591` | ✅ `create_task(run_forever())` 后无人监督，死即永远死 |
| 现状: `_scheduler.tick()` 裸 await | 读 `main.py:1237` | ✅ `summary = await self._scheduler.tick()` 无 try/except，而相邻 cron tick(1258-1260)已有 |
| 现状: `_await_background_task` 行为 | 读 `main.py:4601-4607` | ✅ 5s 内完成则 await 重抛异常，超时则 cancel+suppress——finally 内调用它确实可能让清理流程炸穿 |
| 现状: `on_connected` 非致命包装 | 读 `im_connection.py:278-282` | ✅ `try: await self._on_connected() except Exception: self._events.append(...)`，错只记事件不致命 |
| 现状: `ensure_node_binding` 抛 `GatewayStartupError` | 读 `main.py:847-874` | ✅ bind 端点不可达时 `raise GatewayStartupError`，当前在 `_post_im_connect` 中致命 |
| 现状: local-autonomy 不变量 | 读 `im_connection.py` 类 docstring 区域 + `main.py:1578` `_ready_event.set()` 在 connect 前 | ✅ 就绪与 IM 解耦，连接故障不打断本地执行——design 正确保住 |
| 现状: 契约层 drift | 读 `docs/specs/gateway/spec.md:277-294` | ✅ canonical 已声明「断线后自动重连」，但 Scenario 只有 socket 断开路径，不覆盖休眠/断网/IM 重启——design 要补的三个场景确实是 gap |
| 决策 1: 两层防御 | 拍死?自洽? | ✅ 内层自愈为主(退避保留)+外层 watchdog 安全网，拒绝项合理(只内层→将来新路径漏出仍僵尸；只外层→丢退避) |
| 决策 2: CancelledError 分流 | 自洽?与决策 1 一致? | ✅ cancel 先 `_mark_disconnected` 清理再 re-raise，Exception 退避重试，其余漏给 watchdog——与决策 1 外层兜底衔接 |
| 决策 3: node-binding 移入 `on_connected` | 数据流闭合? | ✅ `ensure_node_binding` 幂等(已绑定 return None)，失败分支全为瞬态条件(节点未就绪/bind 端点不可达)；并入 `on_connected` 非致命包装后，binding 在每次连上时自愈重试。`_ready_event` 在 connect 前 set，就绪与 IM 解耦 |
| 决策 3: 心跳启动时序 | 移除 eager connect 后 feat-393 约束 | ✅ 代码顺序 `im_task = create_task(...)` 后 `await heartbeat_runner.start()` 不变；`start()` 只 `create_task(_run_loop)` 不 await 连接；im_task 会先于心跳 tick 获得调度，实际效果等价 |
| 决策 4: tick 兜底 | 有据? | ✅ 对齐相邻 cron tick 已有模式(1258-1260)，`tick()` 失败不应拖垮整个调度循环 |
| 决策 5: 测试策略 | 覆盖? | ✅ 单测用既有 doubles + e2e 真栈 kill/restart IM 覆盖四场景，登记 `e2e-critical-paths.md` |
| 决策 6: `set_exception` 防御 | 零成本?有据? | ✅ 单 loop 无 await 间隔，TOCTOU 实际不成立；`suppress(InvalidStateError)` 零成本防御，标最低优先级 |
| spec: 休眠唤醒 Scenario | incident.md 有→delta-spec 有? | ✅ incident:71-74 + delta-spec MODIFIED 第三 Scenario |
| spec: 网络中断恢复 Scenario | 同上 | ✅ incident:76-79 + delta-spec MODIFIED 第四 Scenario |
| spec: IM 重启 Scenario | 同上 | ✅ incident:81-84 + delta-spec MODIFIED 第五 Scenario |
| spec: 启动顺序不敏感 | 同上 | ✅ incident:87-90 + delta-spec ADDED「启动顺序不敏感」 |
| spec: 连接故障永不致僵尸 | 同上 | ✅ incident:94-97 + delta-spec ADDED「连接维护故障永不致不可恢复」 |
| delta-spec MODIFIED 用法 | 锚 canonical?保留原 Scenario? | ✅ 改既有「断线后自动重连」，精确锚定标题；原三个 Scenario(补发帧/指数退避/主路径可用)完整保留，新增三个 Scenario |
| delta-spec ADDED Scenario THEN | 用户可观察? | ✅ 全部写「节点自动恢复 online」「Gateway 不崩溃」等消费者可观察结果，无内部函数名 |
| M1: 垂直切片? | 单 M?横切? | ✅ 单 M1，改动跨两文件但逻辑高度耦合(watchdog 包住 hardened loop)，不可真并行，垂直切片 |

---

## 架构进攻

四角度逐个走，每条发现带具体长远代价。

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | 决策 3: `ensure_node_binding` 移入 `on_connected` | ✅ 走完无存活发现。`ensure_node_binding` 在 `personal_assistant` 内(bootstrap client)，移入同包的 `on_connected` 回调，依赖方向正确(`personal_assistant` → `agent.sdk`)，无反向依赖 |
| 该不该存在 | 决策 1: watchdog 间接层 | ✅ 走完无存活发现。删除测试：删掉 watchdog → im_task 死无人重启 → 僵尸。watchdog 不是假想接缝，是 issue 根因 6(结构性缺口)的直接修复 |
| 深还是浅 | 两层防御(内层 hardened loop + 外层 watchdog) | ✅ 走完无存活发现。内层消化 99% 瞬态故障并保留退避节奏，外层只处理"内层因未预料原因退出"的罕见情况——职责分层清晰，不是浅封装 |
| 治本还是补丁 | 整体方案：堵 6 条逃逸路径 + watchdog 兜底 | ✅ 走完无存活发现。修复直接堵住每条已知逃逸路径(治本)加结构性兜底(防未知路径)，不是在共享设施上叠特例；eager connect 移除 + binding 移入 on_connected 是正面重构而非绕路 |

---

## Issues

无。

---

## Recommendations

- watchdog 重建的独立退避实现细节(退避上限、连续失败计数阈值)在 design 中只提了方向、没给参数建议。worker 可直接复用 `IMConnectionConfig`(initial=1s/max=60s)，建议 design 补一句"复用同一退避参数"避免 worker 另造一套。
