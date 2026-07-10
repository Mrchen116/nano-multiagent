# bugfix-418 — 回归验证

> 对齐: incident.md

> Round: 1 — 2026-06-22

## Verdict

**pass**

## Highest Required Action

**pass**（无 blocking/major issue）

## 澄清记录

reviewer 在走旅程前无疑问，口径明确：三条用户可观察验收项均来自 incident.md §现象与复现 + design.md §Milestones M1 `[reviewer]` 轨。

## 环境 / 服务接管

- worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-418`
- 用 `scripts/e2e-up.sh`（带 `IM_FRONTEND_DIST_DIR` 指向主仓 dist，本 unit 无前端改动）一键起 IM + Gateway
- IM port: 60200，Gateway pid: 93167
- 前端产物指纹核验：`assets/index-B-n4TkuT.js`（与主仓 dist 一致，前端无改动）

## 复现验证（incident「现象与复现」期望 → 修后验证）

### 验收项1：前台 subagent 工具卡返回子 agent 结果（非 event-loop 报错）

**步骤**：
1. 起 IM + Gateway（`scripts/e2e-up.sh`）
2. 向 `default-agent` 发消息，令其调用 `agent` 工具派一个前台 subagent（`description="Tell me a short joke"`, `subagent_type="default"`）
3. 查 `GET /im/v1/conversations/{id}/messages` 中 agent 的回复

**期望**：工具卡 status=completed，content 含子 agent 结果

**实际**：
```
tool: agent  status=completed
detail.status: completed
detail.content: "Why don't scientists trust atoms? Because they make up everything."
detail.error: ""（无报错）
```
父 agent 回复："The subagent completed successfully. Here's the joke it returned: ..."

**结论**：pass — 子 agent 正常跑完并返回结果，不含 "bound to a different event loop"

---

### 验收项2：前台 subagent 在 budget 内完成时，父 agent 只收到 inline 工具结果，不额外收到 task-notification

**步骤**：同上旅程，查 conversation 消息总数和消息类型

**期望**：conversation 中只有用户消息 + agent 回复（2 条），无额外 task-notification 消息

**实际**：
```
total messages: 2
  [0] sender_type=user
  [1] sender_type=agent  tool=agent  status=completed
```

无任何 task-notification 类消息。

**结论**：pass — bugfix-417 不变量保住，in-budget 完成路径不走 BackgroundTaskRegistry → 物理上不可能触发通知

---

### 验收项3：一次失败的 subagent 调用后，Gateway 仍在线，heartbeat 不超时

**步骤（正常成功路径后持续存活验证）**：
- 两次 subagent 调用（含 invalid subagent_type fallback 场景）后，查 `GET /im/v1/nodes`

**实际（2026-06-21T19:34:26Z）**：
```
node_id=wt-unit-bugfix-418-93056
  status=online
  last_heartbeat_at=2026-06-21T19:34:11Z  （15 秒前刚心跳）
  last_error=None
```

**步骤（失败隔离 e2e 断言）**：
运行 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 pytest tests/e2e/test_subagent_foreground_e2e.py -v`

```
tests/e2e/test_subagent_foreground_e2e.py::test_foreground_subagent_completes_via_dedicated_loop PASSED
tests/e2e/test_subagent_foreground_e2e.py::test_failing_foreground_subagent_does_not_kill_dedicated_loop PASSED

2 passed in 2.28s
```

第二条用例注入 `_FailingRuntime`（`raise RuntimeError("subagent turn exploded")`），断言 `status=failed`，随后同一专用循环上健康 subagent 仍跑通（`get_event_loop().is_running()` = True）。

**结论**：pass — Gateway 持续在线；失败隔离由 Task 隔离机制保证，专用循环不被单次失败终止

## 回归测试

### 自动化测试结果

```
pytest tests/ -m "not e2e"
2711 passed, 2 skipped, 6 deselected, 15 warnings in 120.90s
```

（较 main 多 +1 条新结构性单测：`test_create_subagent_session_routes_through_dedicated_loop`）

### 验收标准覆盖表

| 验收项（来自 incident.md + design.md M1 [reviewer] 轨） | 验证方式 | 证据 | 结果 |
|---|---|---|---|
| 前台 subagent 工具卡返回子 agent 结果（非 event-loop 报错） | IM API 真实调用：向 default-agent 发消息让其派前台 subagent | tool.status=completed, detail.content="Why don't scientists trust atoms?…", detail.error="" | **pass** |
| 前台 subagent budget 内完成时，父 agent 不额外收到 task-notification | 查 conversation messages 总数和内容 | 2 条消息（用户+agent），无 task-notification | **pass** |
| 一次 subagent 调用失败后 Gateway 仍在线（GET /im/v1/nodes → online，heartbeat 不超时） | (1) 多次调用后查 /im/v1/nodes；(2) e2e 失败注入测试 | status=online, last_hb 持续更新, last_error=None；e2e `test_failing_foreground_subagent_does_not_kill_dedicated_loop` PASSED | **pass** |

## 自动化测试增量

| 测试文件 | 覆盖场景 |
|---|---|
| `tests/e2e/test_subagent_foreground_e2e.py::test_foreground_subagent_completes_via_dedicated_loop` | 前台 subagent 经专用循环跑通、返回 pong（真 LLM） |
| `tests/e2e/test_subagent_foreground_e2e.py::test_failing_foreground_subagent_does_not_kill_dedicated_loop` | 失败注入：subagent 抛错被收敛为 status=failed，专用循环仍 is_running（真 RunsRegistry） |
| `tests/unit/agent/background_tasks/test_runtime_runner_foreground.py` | `submit_foreground` 接口单测（含 loop-bound 原语场景） |
| `tests/unit/agent/tools/test_agent_tool.py::test_foreground_in_budget_does_not_register_subagent` | 结构性钉死决策2：in-budget 完成路径不调用 BackgroundTaskRegistry.register_subagent |
| `tests/unit/agent/tools/test_agent_tool.py::test_create_subagent_session_routes_through_dedicated_loop` | create_session 经 submit_foreground 提交（不再裸 asyncio.run） |

## Issues

无 blocking/major issue。

## Side Findings

- `tests/e2e/test_agent_runtime_e2e.py` 已 stale（`create_llm_client` 签名变更 + `RetryingLLMClient` 不再支持 `with` 上下文管理器），与本 bug 无关，worker 已立 issue #121。本次旅程未触碰该文件。

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：**无需更新** — 本 unit 修内核工具执行路径，不涉及跨包接口/架构变更
- [x] `docs/specs/kernel/spec.md`（长青行为契约层）：**需要更新** — canonical spec 对齐行仍为 `bugfix-417`，delta-spec（`docs/changes/bugfix-418-subagent-event-loop/specs/kernel/spec.md`）已存在，orchestrator 收尾归并时需将 delta-spec MODIFIED + ADDED Requirements 合并进 canonical，并更新对齐行为 `bugfix-418`
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新** — 本 unit 无架构/运维约定变更
- [x] `docs/SPEC_GUIDE.md`（文档规范）：**无需更新** — 本 unit 未改文档体系
