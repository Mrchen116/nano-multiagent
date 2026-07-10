# feat-421-M1 — Progress

## R1 — 起栈底座：conftest fixture + IM 黑盒客户端 + e2e-up.sh 鲁棒化

- Context: 仓库无任何「真起 Gateway 子进程 + 黑盒经 IM 接口」的 e2e（现有 4 条真 LLM e2e 全是进程内拼装 `AgentRuntime`/组件，绕开进程编排/中继/事件循环——#117 类崩裂无人拦）。也无现成测试用 IM HTTP/WS 客户端。本 roadpoint 建这两层底座 + 复用 `e2e-up.sh`/`e2e-down.sh` 当起栈引擎（design 决策 1、2）。
- Decision:
  - 起栈不在 Python 重写：session 级 fixture subprocess 调 `scripts/e2e-up.sh --wt <pytest tmp>` 起真 IM + 真 Gateway，解析它写出的 `.e2e-ports.env`（`export K=V` 行）拿 `IM_URL`/`IM_PORT`/`NODE_ID`，session 结束调 `e2e-down.sh`（design 决策 1）。
  - IM 黑盒客户端 `_im_client.py`：`IMClient`（auth/会话/消息/建 agent/权限）+ `IMUserWebSocket`（resume 握手 + `wait_for_event` 有界轮询 + `assert_no_event` 否定式窗口）+ `restart_gateway`（kill `.gateway.pid` → 同 config 重起 foreground → 等就绪标志）。`websockets` 用 `pytest.importorskip` 可选化（design 决策 2 风险项）。
  - 门控三道：env 开关（`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1`）+ `GET :4000/health` 探活（沿用既有范式，不另造）+ `~/.nano-assistant/config.yaml` 存在性，任一不满足干净 skip 带清晰提示。
- Rationale: 起栈编排（端口隔离 / config 副本 / auto-bind / 就绪探测）已在脚本调通，重写等于造轮子且易踩 bugfix-380 那类「env 名写错卡 30 分钟」坑（design 决策 1 拒绝项）。客户端集中后单条测试只写「旅程脚本 + 鲁棒断言」（design 决策 2）。门控沿用既有 marker/env 避免与现有范式割裂（design 决策 3）。
- Evidence:
  - **范围外共享脚本改动（必需，非可选）**：design 决策 1 要求 fixture 传 `--wt <pytest tmp>` 隔离，但现状 `e2e-up.sh` 硬编码 `cd "$WT_ROOT"` + `PYTHONPATH=src`，要求 `$WT_ROOT` 本身含 `src/`。对 pytest tmp（非 git checkout、无 `src/`）实测 `ModuleNotFoundError: No module named 'IM'`，IM 根本起不来。做了最小鲁棒化：`REPO_ROOT` 从脚本自身 `$0` 反推（`SCRIPT_DIR=$(cd dirname $0)`、`REPO_ROOT=$SCRIPT_DIR/..`）、IM/Gateway 启动用绝对 `PYTHONPATH="$SRC_DIR"`、`free-ports.sh` 用 `$SCRIPT_DIR`。对既有 worktree 用法**行为等价**（REPO_ROOT 仍解析到 repo、PYTHONPATH 绝对化等价、`bash -n` 语法 OK）。orchestrator 已审并接受。
  - 真起栈验证：`bash scripts/e2e-up.sh --wt <tmp>` → `e2e stack ready`，IM 端口 + Gateway pid 就绪，`.e2e-ports.env` 正确写出（`IM_URL=http://127.0.0.1:<port>` / `NODE_ID=wt-<name>-<pid>`）。
  - IM 客户端经真栈验证：`register_or_login("nano")` 拿 token + user_id；`wait_for_online_node()` 返回在线 node_id；`list_agents()` 返回 `['default-agent','Arch','ArchA']`。
  - Entry: 客户端只走 IM 公开 HTTP/WS 契约（不 import 任何产品代码），等价于真实前端所触达的那一面。已核实 WS 事件帧 `{op:"event",event_type,event_id,conversation_id,data}` 与 `message.completed` 的 `data.content`=最终全文（IM `api/ws/event_types.py:build_message_completed_payload`）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 见 R2（底座由奠基 2 条真跑覆盖）。
  - Visual/Interaction: N/A
- Rollback: 纯新增文件 + `e2e-up.sh` 单点鲁棒化；`git revert` 即整体撤回，零产品影响。
- Commits: C2=feat（底座 + e2e-up.sh 鲁棒化，与 R2 同一 commit）
- Next: R2 奠基 2 条

## R2 — 奠基 2 条 + 一条命令 runner

- Context: design Milestones 表 M1 行要求两条奠基路径——「工具调用后回复」（agent 最常用旅程，覆盖工具调用主循环）与「进程重启后会话续接」（只有真起进程才暴露的接缝）——经真 Gateway 进程跑通。
- Decision:
  - `test_tool_call_then_reply_carries_sentinel`：注入随机哨兵到 `wt_dir` 下一个文件 → 发「用 bash/read 读该文件并回复 token」→ 等 WS `message.completed` 且 `data.content` 含哨兵 + 非空 + 不含 `Traceback`。
  - `test_context_survives_gateway_restart`：发「记住暗号 <哨兵>」等一条确认回复 → `restart_gateway(wt_dir, im_port)` 真 SIGTERM 杀旧 Gateway pid + 复用**同一份** `.gateway-config.yaml`（同 node_id / workspace_root）重起 foreground + 等节点重上线 → 发「复述暗号」断言回复仍含哨兵。
  - `scripts/e2e-critical.sh`：设 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + 绝对 `PYTHONPATH` → `python -m pytest tests/e2e/critical_paths "$@"`（extra args 透传，支持 `-m "not slow"` / `-k`）。
- Rationale: 哨兵 token 是真 LLM 不确定输出里唯一稳的锚（design 决策 4）；续接路径复用同 config 保证 node_id/workspace/会话历史不变（这是「续接」语义的前提），不重新生成 config。
- Evidence:
  - **真端到端证据（live-critical）**：
    - 工具调用路径：注入哨兵 `SENT05252B66` → agent 真调工具读文件 → IM 上 WS `message.completed.content` == `'SENT05252B66'`（与注入哨兵逐字相等）。
    - 续接路径：记住 `MEMO<rand>` → 重启 Gateway 进程 → 复述回复仍含该哨兵（断言通过）。
  - Tests: `scripts/e2e-critical.sh` 两轮真跑均 **2 passed**（19.81s / 21.79s），真 IM + 真 Gateway 子进程 + 真 LLM `:4000`（非 stub/进程内）。
  - Entry: 测试经 `IMClient` 走 IM 公开 HTTP/WS，断言只看用户在 IM 上可观察信号（`message.completed` 事件 + content）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 这套 e2e 即永久回归套件，门控关时不烧 token——`pytest tests/e2e/critical_paths`（env 未设）→ `2 skipped`（不崩）；`pytest tests/e2e/critical_paths -m "not e2e"` → `2 deselected`（baseline 不收集，靠父 conftest 自动打 e2e marker）。teardown 后 `ps` 扫 pytest-tmp 进程 → 无泄漏。
  - Visual/Interaction: N/A
- Rollback: 纯新增测试 + 脚本；`git revert` 撤回。
- Commits: C2=feat（与 R1 同一 commit）
- Next: R3 catalog

## R3 — 关键路径 catalog 骨架

- Context: spec「单一权威的关键路径清单 catalog 可对账」要求一处登记「用户旅程 ↔ 守护测试 ↔ 归属子系统 ↔ 引入 unit」+ 显式登记暂无 e2e 兜底的缺口（design 决策 6）。
- Decision: 单文档 `docs/e2e-critical-paths.md`：v1 必保活段（11 条四列表，M1 落地的 #1/#10 挂真实测试函数路径，其余 9 条标 `TODO(feat-421-M2)`）+ 已知缺口 backlog 段 + 登记纪律一句（新增关键特性须登记一行 + 配 e2e）。归属列引 `docs/specs/<包>/spec.md`。
- Rationale: 它是跨包「测试↔路径↔归属」索引（非某包对外契约），故不进 `docs/specs/`，放 `docs/` 顶层更像一等公民、好翻到（design 决策 6）。AGENTS.md 关键文档索引挂链留到 M2（与四列填全同时落，避免半成品文档先上索引）。
- Evidence:
  - 11 条 v1 路径全列（工具调用回复 / bash 前台超时 / bash 后台通知 / subagent / /stop / cron[slow] / heartbeat[slow] / 群聊双向定向@ / 权限审批 / 进程重启续接 / 经 IM 建 agent）。
  - backlog 段含「前端 UI smoke（Playwright，稳定后端、无真 LLM）独立 unit」+ 断线重连 / 压缩恢复 / 附件透传 / provider 切换 / 节点上下线看板 5 项，诚实登记「暂无 e2e 兜底」。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 文档，N/A。
  - Visual/Interaction: N/A
- Rollback: 纯新增文档。
- Commits: C3=docs
- Next: milestone 完成（M2 接 9 条 + 四列填全 + AGENTS.md 挂链）

<!-- 每个 roadpoint 完成后追加。 -->
