# bugfix-494: 清理 Feishu SDK cache 协程 warning

## Relations

- Related: feat-464
- Related: refactor-486
- Closes: #218

## 原始报告

Issue：https://github.com/Mrchen116/nano-multiagent/issues/218

> ## 背景
>
> 一次 `pytest -m "not e2e" -n 4` 全量运行虽然 3733 passed、1 skipped，但在 `test_gateway_boundary_outbox.py::test_applied_runtime_and_boundary_survive_gateway_restart` 结束附近出现：
>
> ```text
> RuntimeWarning: coroutine ExpiringCache._start_clear_cron was never awaited
> ```
>
> 协程来自第三方 `lark_oapi/core/cache/expiring_cache.py`。`ExpiringCache.__init__` 会取得当前 event loop，并启动一个长期清理任务。warning 显示在 `session_keys.py` 附近只代表对象回收位置，尚不能据此判定业务代码是根因。
>
> 目标测试单跑，以及与 Feishu worker 测试通过 xdist 并跑，都没有稳定复现。
>
> ## 问题
>
> 该 warning 可能表示 SDK import/实例化时创建的异步任务没有与测试 event-loop 生命周期对齐。当前 CI 不失败，但非确定性的资源回收噪声可能掩盖真正的协程泄漏。
>
> ## 调查方向
>
> - 在 CI 使用的 Python、pytest 与 xdist 配置下尝试稳定复现；
> - 确认触发条件是测试顺序、worker teardown、SDK import 时机还是 event-loop 关闭顺序；
> - 核对新版 Feishu SDK 是否已经修复该生命周期问题；
> - 根据根因选择升级 SDK、隔离 SDK 初始化、显式关闭后台任务或完善测试 teardown；
> - 在根因确认前，不修改业务逻辑，也不全局屏蔽 `RuntimeWarning`。
>
> ## 验收标准
>
> - 得到可说明触发条件的最小复现，或有充分证据确认是已知第三方问题；
> - 相关测试和全量 non-e2e 测试结束时不再留下未 await 协程或存活后台任务；
> - 没有通过全局 warning ignore 隐藏同类资源生命周期错误。
>
> 来源：文档体系重构漂移审查 D-011。

## 对齐记录

本轮不需要新增 owner 问答。Issue、current Gateway 外部通道与服务生命周期契约、`feat-464` 的原始设计和实现、当前 CI 配置以及 Feishu SDK 官方源码已经共同收口问题边界：保留真实 SDK 兼容 seam 和 Feishu worker 进程隔离，只消除本仓测试创建却没有收拢的 SDK cache task；不借机改写飞书产品行为，也不以全局 warning ignore 制造通过。

## 现象 / 复现

仓库在测试收集时导入 `lark_oapi.ws.Client`。`tests/unit/personal_assistant/test_feishu_worker_runtime.py::test_supported_lark_sdk_exposes_reconnect_observer_seam` 随后构造一个真实 `WSClient`，用于确认本仓依赖的 reconnect observer seam，但没有启动 client，也没有收拢构造过程创建的 cache task。该 task 会留在 SDK 取得的 event loop 上；全套测试中的后续 loop teardown 与垃圾回收时机决定 warning 最终显示在哪条无关测试附近。

2026-08-04 在本仓 `.venv` 的 Python 3.12.9、pytest 8.4.2、pytest-asyncio 1.3.0、pytest-xdist 3.8.0 与 `lark-oapi` 1.6.9 下执行当前 CI 的同序命令，并额外打开 RuntimeWarning 与 tracemalloc：

```bash
PYTHONTRACEMALLOC=5 .venv/bin/python -W always::RuntimeWarning -m pytest \
  -m "not e2e" -n 4 --dist worksteal --durations=20 --durations-min=0.5
```

全量运行再次在 `test_gateway_boundary_outbox.py::test_ack_deletes_only_its_durable_boundary` 附近报告 `ExpiringCache._start_clear_cron was never awaited`。这次运行同时有 8 条与本 warning 无因果关系的进程启动/超时失败，因此只能证明 warning 在当前全量 xdist 条件下仍可成立，不能作为当前整套 CI 全绿证据。warning 的归属仍以任务分配、loop 生命周期与 allocation trace 为准，不能按显示的测试名归因给 boundary outbox。

SDK 缺陷本身可用不依赖测试顺序的最小脚本稳定复现：创建 `ExpiringCache` 后关闭其 event loop，再释放对象并执行 `gc.collect()`，必然出现 pending task 和同一条未 await coroutine warning。tracemalloc 把协程分配点定位到 `ExpiringCache.__init__` 的 `loop.create_task(self._start_clear_cron())`。

反向排查本仓调用点后，生产代码只在隔离的 Feishu listener 子进程中构造真实 `WSClient` 并进入其阻塞式 `start()`；测试代码只有上述 seam contract 直接构造真实 `WSClient`。本次观测没有证明线上 listener 在正常运行中泄漏 task，也没有证明 `session_keys.py` 或 boundary outbox 创建了该协程。

目标测试单跑为 `1 passed`，显式组合该测试、6 条 pytest-asyncio 测试和 4 条 boundary outbox 测试并用 `-n 1 --dist worksteal` 运行也为 `11 passed` 且没有这条 RuntimeWarning。这个阴性结果与全量阳性结果共同说明：trigger 是确定的真实 SDK 构造副作用，warning 的出现时机则依赖全套 worker 内的 loop teardown/回收顺序。

### Requirement: SDK seam 测试不遗留异步资源

#### Scenario: 兼容 seam 检查结束

- **WHEN** 贡献者运行 Feishu worker 关联测试或完整 non-e2e 测试
- **THEN** reconnect observer seam 仍被真实验证
- **AND** 测试创建的 `ExpiringCache` 清理协程在所属 event loop 结束前进入终态，不再报告 pending task 或未 await coroutine

#### Scenario: 全量 xdist 改变测试和回收顺序

- **GIVEN** non-e2e 测试由四个 xdist worker 以 worksteal 分配
- **WHEN** SDK seam 测试与其他 asyncio 测试按任意合法顺序结束
- **THEN** 测试套件不依赖垃圾回收碰巧不发生来保持安静，warning 不再漂移到无关测试名下

### Requirement: 真实协程生命周期 warning 不被隐藏

#### Scenario: 后续代码再次遗留未收拢协程

- **WHEN** 本仓或第三方集成产生新的 `RuntimeWarning: coroutine ... was never awaited`
- **THEN** 测试输出仍能暴露该信号
- **AND** 本修复不通过全局 warning ignore、放宽 pytest warning 规则或过滤全部第三方 RuntimeWarning 把它隐藏

### Requirement: Feishu 运行行为保持不变

#### Scenario: Gateway 管理飞书 listener

- **WHEN** Gateway 启动、重连、替换或停止飞书 channel
- **THEN** 既有每 Bot 一个隔离 worker 进程、reconnect 状态上报和 stop/join/terminate 语义保持不变
- **AND** 本修复不改变用户在飞书中的消息收发、路由、权限诊断或连接状态

### 范围与非目标

本期范围：让本仓真实 SDK seam 测试显式拥有并收拢构造时产生的 cache task；保留现有 seam 断言；补充能在测试结束时检查该资源已进入终态的回归；用相关测试与完整 non-e2e xdist 运行确认 warning 消失。

本期不做：不全局屏蔽 RuntimeWarning；不承诺清除 protobuf、JWT 等其他类别的既有 warning；不因为最新 SDK 仍有相同实现就做无效升级；不修改 site-packages、fork Feishu SDK 或重写 SDK 的 event-loop 模型；没有新的线上证据时不扩大为生产 Feishu listener 生命周期重构。

## 根因

### 直接原因

官方 `lark-oapi` 1.6.9 的 `ExpiringCache.__init__` 取得当前 event loop 后立即执行：

```python
self._cron = loop.create_task(self._start_clear_cron())
```

`_start_clear_cron()` 是永久循环。SDK 没有公开 cache/client close API；`ExpiringCache.__del__()` 只调用 `self._cron.cancel()`。event loop 持有 task，task 的 coroutine 又持有 cache 实例；当 loop 关闭并清空回调后，这组对象才可能被回收，而此时单纯 `cancel()` 已经没有机会让 loop 再推进一次，把 task 真正送入 cancelled 终态，所以 Python 报告 pending task 被销毁和 coroutine 从未 await。

本仓 seam contract 构造了完整 `WSClient`，虽然只读取 `_connect`、`on_reconnecting` 与 `on_reconnected`，仍触发上述有副作用的 constructor。测试返回时没有处理 `client._cache._cron`，使资源最终状态交给了全套测试中的 event-loop 与 GC 时序。

官方 PyPI 最新版当前为 1.7.1；其 [`expiring_cache.py`](https://github.com/larksuite/oapi-sdk-python/blob/v1.7.1/lark_oapi/core/cache/expiring_cache.py) 与本仓下限 1.6.9 的实现相同。该文件自 2024 年引入 WebSocket 支持后没有后续修复提交。因此“只把依赖从 1.6.9 升到 1.7.1”不能解决本问题。

### 原始设计意图与必须保住的不变量

`feat-464` 为了解决旧 SDK WebSocket 全局 event loop 无法支持多 Bot 和可靠停止的问题，把每个真实 `WSClient` 放入一个独立 spawn 子进程，由 parent 负责有界 IPC、stop、join，必要时 terminate/kill 并回收整个进程。实现同时依赖 SDK 1.x 的 `_connect` 和 reconnect observer seam 上报连接状态；该 seam 由当前出现泄漏的 contract test 锁定。

修复必须保住：

- 每个飞书 Bot 仍由独立 listener 子进程拥有真实 SDK event loop；
- reconnect observer seam 的不兼容变化仍会让 contract test 失败，不能通过删除真实兼容检查来消除 warning；
- Gateway 对 worker 的 stop/join/terminate、FIFO、status 与 card-action 行为不变；
- Feishu 消息收发、外部 channel 隔离和 IM 状态投影不变；
- 测试显式收拢自己创建的异步资源，而不是让无关业务模块或全局 warning 过滤器兜底。

### 回归引入点

commit `3577ad11277d0b436fe846e097889b5902d3a806`（`feat(feat-464/M1/R2): 隔离 Feishu worker 并统一动态生命周期`）新增 `test_supported_lark_sdk_exposes_reconnect_observer_seam`。该测试首次在 parent 测试进程直接实例化真实 `WSClient`，但没有处理 constructor 创建的 `ExpiringCache` task；当前 warning 可追溯到这个测试资源所有权缺口，不是 Issue 中碰巧显示的 boundary outbox 测试。

### 为什么这种错能进入主线

- 测试目标只是 SDK 私有 seam 是否存在，review 聚焦断言内容，没有审计第三方 constructor 同时创建的后台 task。
- `feat-464` 的生命周期验证关注真实 worker 子进程是否被 parent reaped；没有把 parent 进程中的 SDK compatibility object 纳入同一资源图。
- 聚焦测试和小规模 xdist 组合通常在 warning 可见前退出，原 milestone 证据也只记录“无残留 worker process”，没有强制 event-loop 关闭后再检查 coroutine 终态。
- 第三方 SDK 依靠 `__del__` 取消 task 且没有公开 close，使测试能够表面通过；只有全量测试恰好触发后续 loop teardown/GC 时才暴露资源泄漏，显示位置还会误导到无关测试。

## 修复

## 验证
