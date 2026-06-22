# feat-421-M1: harness-and-foundation — Tasks

> 对齐: ../design.md（§现状分析、§关键决策 1-6、§接口与数据流、Milestones 表 M1 行）、../spec.md

## 目标

外部可观察变化（本 unit 的「用户」= 跑这套 e2e 的开发者）：

1. 一条命令 `scripts/e2e-critical.sh` 起**真 IM + 真 Gateway 进程 + 真 LLM**，黑盒经 IM 对外 HTTP/WS 接口跑通「工具调用后回复」「进程重启后会话续接」2 条关键路径，每条给 pass/fail。
2. 平时不跑：默认 `pytest` / `pytest -m "not e2e"` 不触发（靠门控 skip + 父 conftest 自动 e2e marker），不烧 token。
3. 缺本地 LLM proxy（`:4000/health`）或缺 `~/.nano-assistant/config.yaml` 时干净 skip 而非崩。
4. 一份关键路径 catalog 骨架（`docs/e2e-critical-paths.md`）：11 条 v1 路径全列、未实现标 TODO、含 backlog 段 + 登记纪律。

## 退出标准

- [x] `scripts/e2e-critical.sh` 起真 IM+真 Gateway+真 LLM 并跑通 2 条奠基路径（真端到端绿，非 stub/进程内）。
- [x] 门控缺 proxy/config 时干净 skip 而非崩。
- [x] catalog 列出全部 11 条 v1 路径（其余暂 TODO）+ backlog 段含「前端 UI smoke 独立 unit」。
- [x] 起栈 fixture 传 `--wt <pytest tmp>` 隔离，不污染主仓；teardown 必走 `e2e-down.sh`，无进程泄漏。
- [x] IM 黑盒客户端 `websockets` 依赖用 `pytest.importorskip` 可选化（缺则 skip 不崩）。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（这套 e2e **本身就是测试交付物**，不是「给某段产品逻辑配测试」）：
  - 工具调用后回复：发需 agent 调工具才能答的消息（哨兵 token 注入文件）→ IM 上收到含哨兵的 assistant 回复。
  - 进程重启后会话续接：建上下文（记住哨兵）→ 重启 Gateway 进程（同 config / node_id / workspace）→ 再发消息，回复仍含重启前的哨兵。
- 测试落层/目录/marker：`tests/e2e/critical_paths/`；自动继承 `@pytest.mark.e2e`（父 `tests/e2e/conftest.py` 的 `pytest_collection_modifyitems` 按路径打标）；额外注册 `slow` marker 供 M2 的 cron/heartbeat 用。
- 门控：沿用既有 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + `GET :4000/health` 双门控（不另造），外加 `~/.nano-assistant/config.yaml` 存在性探测，三道任一不满足干净 skip。
- 可选依赖 importorskip：`websockets`（WS 客户端）→ 缺则整组 e2e skip。
- 鲁棒断言（design 决策 4）：只锚「注入的随机哨兵 token + 协议级 `message.completed` 事件」，不锁 LLM 措辞；哨兵每条用例独立随机。
- 一次性验收证据 vs 永久回归：这套 e2e 是**永久回归套件**（入 `tests/`），平时门控关、按需一条命令全跑。临时验收证据（手跑 stdout、哨兵命中片段）记 progress.md，不进 `tests/`。

前端用户路径分类：N/A（design 决策 7：本 unit 走 API 级，前端 UI smoke 另立独立 unit，已登记 catalog backlog）。
UI 状态矩阵：N/A（无新 UI）。

## Roadpoints

### R1 — 起栈底座：conftest fixture + IM 黑盒客户端 + e2e-up.sh 鲁棒化 [DONE]

- 步骤:
  1. 核实 IM 真实对外接口（auth / conversations / messages / WS resume 协议 / nodes / agents / permission）+ e2e-up.sh/down.sh 起停范式。
  2. 实现 `tests/e2e/critical_paths/_im_client.py`（httpx + websockets，`importorskip` 可选化）：auth、会话、消息（含 mention 标签）、WS resume 握手 + 有界轮询事件等待 + 否定式断言、权限审批、建 agent、重启 Gateway。
  3. 实现 `tests/e2e/critical_paths/conftest.py`：session 级起栈 fixture（subprocess 调 `e2e-up.sh --wt <pytest tmp>`，source `.e2e-ports.env`，teardown `e2e-down.sh`）+ 三道门控 skip + 失败时 dump 日志。
  4. 鲁棒化 `scripts/e2e-up.sh`：REPO_ROOT 从脚本自身 `$0` 反推、PYTHONPATH 用绝对 `$SRC_DIR`、free-ports 用 `$SCRIPT_DIR`（范围外但必需，见 progress Evidence）。
- 验证: `e2e-up.sh --wt <tmp>` 真起栈成功（IM + Gateway 就绪），IM 客户端经真栈完成 auth / 拿在线 node / 列 agents。

### R2 — 奠基 2 条 + 一条命令 runner [DONE]

- 步骤:
  1. 实现 `test_tool_call_reply_critical_path.py`（哨兵注入文件 → agent 调工具读取 → 断言 WS `message.completed.content` 含哨兵）。
  2. 实现 `test_restart_session_continuity_critical_path.py`（记住哨兵 → `restart_gateway()` 重启 → 复述断言回复仍含哨兵）。
  3. 实现 `scripts/e2e-critical.sh`（设 env + `pytest tests/e2e/critical_paths`，extra args 转发）。
- 验证: `scripts/e2e-critical.sh` 真端到端 2 passed；teardown 后无进程泄漏；门控关时 2 skipped / `-m "not e2e"` 2 deselected。

### R3 — 关键路径 catalog 骨架 [DONE]

- 步骤:
  1. 实现 `docs/e2e-critical-paths.md`：11 条 v1 路径四列表（M1 落地 2 条挂真实测试函数，其余 9 条标 `TODO(feat-421-M2)`）+ 已知缺口 backlog 段 + 登记纪律一句。
- 验证: 11 条全列；backlog 含「前端 UI smoke 独立 unit」+ 断线重连/压缩恢复/附件透传/provider 切换/节点看板 5 项。
