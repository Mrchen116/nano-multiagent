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
- Method：新增回归单测；既有 worker 测试按风险组运行；Ruff 与 format check 覆盖两个修改文件。
- Result：新增 owner-death 测试通过；既有正常 stop/隔离/背压/drain/drop/card/crash/SDK 日志测试逐项通过；静态检查通过。
- Locator：`src/personal_assistant/channels/feishu/worker.py` 与 `tests/unit/personal_assistant/test_feishu_worker_runtime.py`。
- Limit：实施前与首次整文件回归期间，宿主同时运行其他并行 pytest/vitest 且 load average 一度超过 70，现行 5 秒 child-ready 基线在 `origin/main` 与 unit worktree 均出现超时；失败用例在负载下降后不改代码逐项通过。交付前仍需取得整文件与本地 CI 单次全绿证据。

## Commits

- 待提交。
