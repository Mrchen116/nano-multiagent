# bugfix-496-M1: parent-liveness 实施记录

## 范围与决策

- 产品改动只落在 `FeishuWorkerRuntime` child bootstrap；Gateway、ChannelManager、配置、协议、IM 与前端 interface 均未改变。
- child 在 listener target 前启动 daemon watcher，等待 multiprocessing parent sentinel；owner 消失后以进程级退出释放 WebSocket 与 IPC。正常 `stop()` 路径不变。
- 与 design 一致，无设计偏差。

## 测试策略

- 保护的回归风险与可观察 seam：真实 spawn owner 无法 cleanup 便退出后，已记录的 listener PID + process birth 必须在 3 秒内消失。
- 已有保护与处置：扩展 `tests/unit/personal_assistant/test_feishu_worker_runtime.py`；既有多 Bot、正常 stop/join、背压、drain/drop、card RPC、worker crash 与 SDK 日志测试全部保留，不建立平行测试文件。
- 落层：`tests/unit/personal_assistant/`，无 marker；这是能够真实跨过 spawn/bootstrap 进程边界的最低现有测试面。
- 一次性验收证据：真实 IM/Gateway/Feishu 与通道页旅程由 M1-E1～E4 的独立 product reviewer 执行，不提交临时 config、凭据、PID、日志或数据库。

## 实施证据

### Red

- Claim：现行 listener 会脱离异常死亡的 owner 继续存活。
- Baseline：`e79b5d1a12204c077188f3646f741c8648d66cc9`，unit worktree，无产品代码修改。
- Method：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_feishu_worker_runtime.py::test_listener_exits_when_its_owner_dies_without_cleanup`。
- Result：fail；owner `os._exit(23)` 后，原 listener PID + birth 超过 3 秒仍存在。随后定向 `SIGKILL` 只用于清场，不计成功。
- Locator：`test_listener_exits_when_its_owner_dies_without_cleanup`。
- Limit：fake target 只替代外部飞书 SDK；真实 WebSocket、重启、消息与页面状态由 reviewer 旅程覆盖。

### Green

- Claim：owner-death 回归与既有 worker 行为同时成立。
- Method：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_feishu_worker_runtime.py`；Ruff 与 format check 覆盖两个修改文件。
- Result：整文件单次 `8 passed`；owner-death 探针用独立 subprocess 隔离异常 owner 的 resource tracker，startup 通过独立 IPC outcome 与 45 秒建桩预算和 owner 死后的 3 秒契约分离；parent-alive idle 明确观察同一 worker birth 后正常 stop。pytest 进程没有 semaphore leak warning，静态检查通过。
- Locator：`src/personal_assistant/channels/feishu/worker.py` 与 `tests/unit/personal_assistant/test_feishu_worker_runtime.py`。
- Limit：fake target 只替代外部飞书 SDK；真实 WebSocket、重启、消息与页面状态由独立 product reviewer 报告持有。

## Commits

- `067d1763b` — parent-sentinel worker 实现、owner-death 回归与本记录初稿。
- `d0331f25b` — 回填首轮实现证据。
- `d14f0db00` — 关闭 verifier R1-C1/R1-W1 与 code review C1/C2 的测试确定性、idle 反例和 tracker 隔离。
