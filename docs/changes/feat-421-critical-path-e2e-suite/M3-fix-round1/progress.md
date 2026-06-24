# feat-421-M3 — Progress（fix-round1）

> reviewer 反馈循环小修快车道：拆文件+消重+correctness+cleanup 7 项（heartbeat marker 第 8 项挂起）。
> 省略 §0.4 三提交（单 commit 自包含 fix 列表）、不复制独立 roadpoint —— 理由：每条 fix 单点、
> 集中一次 commit 可整体 revert，符合 §FL ② 减流程仪式判据。

## 关键决策与证据

### 拆 `_im_client.py`（fix#1）

- Context: `_im_client.py` 552 行 > 400 软上限，contract `test_new_test_files_under_400_lines` 实测红。
- Decision: 按行为聚类拆 4 文件，全 ≤400：
  - `_im_polling.py`(68)：共享 `poll_until(probe, predicate, *, timeout, interval, desc)` + `assert_absent_within(...)`（消重核心）。
  - `_im_ws.py`(165)：`mention_tag` + `EventFrame` + `IMUserWebSocket` + WS 窗口常量 + websockets importorskip。
  - `_im_gateway.py`(120)：`restart_gateway` + `_terminate_process_group`（进程生死）。
  - `_im_client.py`(369)：`IMClient`（HTTP/agent-ops）。re-export `restart_gateway`/`IMUserWebSocket`/`mention_tag`/`DEFAULT_EVENT_TIMEOUT` 保历史 import 兼容（测试文件无需改 import 行）。
- 消重：散在 `test_group_chat._wait_listed`/`_wait_agent_message`/`_agent_messages`、`test_create_agent._wait_for_agent_listed`、`test_cron` 内联轮询、`test_stop`/`test_permission` 否定窗口——全部同构「轮询直到 predicate / 窗口内 predicate 缺席」，统一到 `poll_until`/`assert_absent_within`。`IMClient` 新增 `wait_for_agent_listed` / `agent_messages` 供测试复用。
- Evidence: contract 400 行测试 `2 passed`；全套 e2e 13 passed（消重后轮询行为不变）。

### killpg 误杀 pytest 进程组（fix#6，systematic-debugging）

- Context: fix#6 要 `restart_gateway` 杀进程组（避免 relay/heartbeat worker 成孤儿）。首版无脑 `killpg(getpgid(pid))`。
- 现象: 重启续接 e2e **exit 144（128+SIGTERM）、零输出**——pytest 进程自己被 SIGTERM 杀。
- 根因（systematic-debugging）: e2e-up.sh 起的 Gateway **没 setsid**，继承 pytest 的进程组；对它 `killpg(getpgid(pid))` = 杀**整个 pytest 进程组**（含 pytest 自己）。
- 修复: `_terminate_process_group` 只在 `os.getpgid(pid) == pid`（独立进程组组长，即 `start_new_session` 起的）时 killpg；非组长退回单 pid kill（Gateway 作为 supervisor 收 SIGTERM 自行向 worker 传播，不留孤儿）。restart 重起时用 `start_new_session=True` 让新 Gateway 成独立组长。
- Evidence: 修复后重启续接 `1 passed in 15.25s`（不再 exit 144）。

### subagent 失败隔离（fix#3）

- Context: catalog #4 声称守护「子 agent 失败被隔离不拖垮常驻进程」（#117 核心一半），但 M2 只有「产出回带」测试，隔离 scenario 实际没测（verifier W2 + reviewer 点）。
- Decision: 新测试两阶段：① 派注定失败的前台子 agent（要求它跑 `bash -c 'exit 7'` 且「必须成功」→ 子 agent 任务失败），断言父 agent 仍产出 message.completed（进程没崩/没卡死）；② 同对话再发普通哨兵消息，断言正常收到含哨兵回复——**隔离的确定性锚 = Gateway 进程存活后后续消息仍正常处理**（不锁子 agent 失败时父 agent 措辞）。
- Evidence（live）: `test_failed_subagent_isolated_from_main_process PASSED in 33.52s`（真 IM+真 Gateway+真 LLM）。

### 其余

- fix#5 `_drain_one` 补捕 `ConnectionClosedOK/ConnectionClosedError/ConnectionClosed`：Gateway 重启 / IM 断连时 `ws.recv` 抛 ConnectionClosed，优雅返回 None（视作「这一刻无新帧」），让有界轮询窗自然走完，不冒泡成测试 ERROR（重启测试首当其冲）。
- fix#7 conftest teardown 检查 `e2e-down.sh` returncode：非零打 `[WARN]` + stderr tail（不 raise，session finalizer 兜底），别静默吞掉「进程没杀干净」。
- fix#8 cron「等 feature 同步」no-op：`update_agent_config` 返回后 agent 早在 `list_agents`（配置改动非新建），循环首次迭代即命中、从未真等 config 热重载 → 删掉伪等待 + 注释说明 config sync 异步无就绪信号、靠 cron 推送 180s 宽窗兜底。
- fix#4 M2 tasks.md 退出标准 4 条勾 [x]（实现 M2 已完成、文档漏勾；heartbeat 状态如实注明）。

### heartbeat skip→xfail(strict)（fix#2，用户拍板 B）

- 决定: 用户拍板 B——本 unit 守「只做测试、不改产品代码」。heartbeat 不修产品前缀，标 `@pytest.mark.xfail(strict=True, #126)`（TESTING_GUIDE §7：已知产品回归用 xfail(strict)+issue 号，不用 skip）。
- 门控顺序: 门控在 `e2e_stack` fixture 的 `_gate_or_skip()`（无 proxy/config → `pytest.skip`）。fixture setup 阶段 raise Skip **先于** xfail 判定 → env off 时 SKIPPED（不进 xfail），符合「skip 先于 xfail」要求。
- 验证（真跑双态确认）:
  - env off: `1 skipped`（门控 fixture skip）。
  - env on: `1 xfailed in 184.09s`——真跑旅程到 K2.6 对 openclaw 心跳前缀回 HEARTBEAT_OK → 断言失败 → XFAILED（strict 下 EXIT=0，不报错）。
- 活复现资产: #126 修复后（产品前缀移 system role，PoC 见 #126），K2.6 冒泡 → XPASS → strict 转 fail 自动提醒去 xfail。不改产品 `_build_heartbeat_message` / `_OPENCLAW_HEARTBEAT_PROMPT`。

## 退出标准达成

- contract 400 行 `2 passed`；全套 e2e-critical `12 passed, 1 xfailed`（heartbeat 真跑 XFAIL）；全树 ruff clean + format ok；全树 collect 2735；0 进程泄漏 + 0 workspace 残留。
- heartbeat marker 已落 xfail(strict, #126)（用户拍板 B，本 unit 不改产品代码）。

## Commits

- 10ebf5a3：fix#1/3/4/5/6/7/8 + killpg 护栏（systematic-debugging 后修正，单 commit）
- e23b982c：fix#2 heartbeat skip→xfail(strict, #126)
- + M3 tasks/progress 文档 commit

## Next

8 项 fix 全部完成，heartbeat xfail 落地。待合并 milestone/feat-421-M3 → unit/feat-421。
