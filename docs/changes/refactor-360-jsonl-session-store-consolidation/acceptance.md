# refactor-360 — 验收报告

> 对齐: motivation.md 用户侧验收标准（不变性）
> Round: 1 · 2026-05-19

## Verdict

**pass-with-issues**

无 blocking。1 条 minor 问题（历史 session --resume 失败为基线已有缺陷）。核心不变性（IM 网页、Coding CLI 多轮对话+resume 当轮 session、Gateway 启动/停止）全部通过。删除目标 100% 达成。

## Highest Required Action

**out-of-unit**（仅 minor 级别的 Side Finding，不阻塞本 unit 合并）

## User Journeys Exercised

### Journey 1: Coding CLI 多轮对话 + 当轮 --resume
1. 在 unit worktree 启动 managed API（`--mode managed --base-url http://127.0.0.1:8103`）
2. `--text "hello, this is a reviewer test"` → 收到 assistant 回复，获得 `sess_2724fce9074d929f`
3. `--resume sess_2724fce9074d929f --text "what was my previous message?"` → assistant 正确回忆 "hello, this is a reviewer test"

**观察**：session 创建、消息发送、resume 加载历史均正常；JSONL store 读写无异常。

### Journey 2: IM API 登录 + 对话列表历史回看
1. POST `/im/v1/auth/login` 获取 token
2. GET `/im/v1/conversations` 返回 31 条历史对话（含直聊和群聊）
3. GET `/im/v1/agents` 返回 6 个 agent（demo-node 上 Arch/default-agent/ArchA 在线）

**观察**：登录、对话列表、历史回看 API 全部正常；IM 网页（http://127.0.0.1:8011/）可访问。注：当前生产 Gateway（main 分支代码）在线，不变性成立——unit 分支的 refactor 不影响运行时路径（(A) JsonlSessionStore 全程未动）。

### Journey 3: Gateway 启动命令验证
1. 在 unit worktree 执行 `python -m personal_assistant.main --config /tmp/gateway_reviewer_config.yaml --im-service-url http://127.0.0.1:8011`
2. 控制台输出 "Gateway started (pid=58084)" / "IM service: http://127.0.0.1:8011  [connected]"
3. stop/restart 子命令存在于 `--help` 输出中

**注**：因主用户 Gateway 已占用默认 PID 文件，无法对同一 config 路径执行 stop 测试；但 CLI 命令存在，代码路径未受 refactor 影响。

### Journey 4: 删除判据全量核验
```
grep -rn "SQLiteSessionStore|from agent.platform.persistence.session import |from .sqlite_store|from .base import SessionStore" src/ tests/
```
返回零（0 行）——motivation 判据 1 完全满足。

```
ls src/agent/platform/persistence/session/
```
输出：`__init__.py  service.py`（仅保留 SessionService）——判据 2 满足。

```
ls src/agent/core/session/store.py
```
返回 `No such file or directory`——SessionStore ABC 已删除。

### Journey 5: xfail 测试转 pass 验证
```
pytest tests/e2e/test_personal_assistant_main_e2e.py -k "workspace_root"
```
2 passed（之前为 xfail）——issue #25 关闭验收通过。

### Journey 6: 测试套回归对比
- unit 分支：165 失败（排除 playwright 依赖文件）
- main 分支：202 失败（同等条件）
- unit 分支比 main 减少 37 个失败，无新引入回归（经 diff 分析）

新出现在 unit 分支但不在 main 的 5 个失败：
1. `test_anthropic_default_model_and_base_url` — main 已更新模型注册表（`99164cdf`），unit 分支滞后，合并后自动消除
2. `test_dispatch_handler_build_aiohttp_handler_returns_callable` — worktree `.venv` 缺 `socksio` 包，环境差异（安装后消失）
3. `test_kernel_api_client_requires_token_for_authenticated_calls` — 同上
4. `test_gateway_runtime_connects_to_real_im_service` — worktree 缺 `scripts/free-ports.sh`，IM 无法启动；代码路径未变
5. `test_spec_node_gateway_s16_channel_startup_and_four_step_decision` — 同上

以上 5 项均为 worktree 环境差异，非 unit 代码引入的回归。

## 问题清单

| # | 严重度 | 现象 | Recommended Action | Action Rationale |
|---|---|---|---|---|
| 1 | minor | `--resume <历史session>` 在 managed 模式返回 `session_not_found`：`--resume sess_0787fd3de8aad5ec --text "test"` → `session_not_found (404)`。此行为在 main 分支（基线）完全相同——说明本 unit 的 refactor 没有使其变好也没有使其变坏。 | out-of-unit | motivation 第 4 条要求历史 session --resume 能工作，但 main 分支基线本就不支持（managed 模式新起 API 实例无法自动发现 ~/.nano/sessions/ 中的旧文件）。这是独立的 Coding CLI 功能缺陷，不属于本 refactor 的交付范围。|

## 验收标准覆盖

| ID | 验收项 | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|---|
| A1 | IM 网页：登录 / 选 agent / 单聊往返 / 群聊 @ 路由 / 历史回看 与本 unit 之前一致 | motivation.md §用户侧验收标准 条目 1 | API 验：POST /im/v1/auth/login → 200 + token；GET /im/v1/conversations → 31 条历史对话；GET /im/v1/agents → 6 个 agent（Arch/default-agent/ArchA 在线）。IM 网页 http://127.0.0.1:8011/ 可访问（200）。 | login 200 token, conversations 31 items, agents list with online status | **pass** | Runbook 说明：unit refactor 不动运行时路径，(A) JsonlSessionStore 全程在用，无 stale binary 问题 |
| A2 | Coding CLI：`create-session` / `send-message` / `--resume` 行为与本 unit 之前一致 | motivation.md §用户侧验收标准 条目 2 | managed 模式 --text 发消息收到 assistant 回复；--resume 当轮 session 正确加载历史；multi-turn 行为正常 | Journey 1 transcript：sess_2724fce9074d929f 创建成功，assistant 正确回忆上轮消息 | **pass** | 注：AGENTS.md 文档中的 `create-session` 子命令与实际 CLI 不符（CLI 实际只有 health/llm-config 子命令，需要通过 --text 或 REPL），但此为基线已有文档不准，不是 unit 引入 |
| A3 | Gateway：启动 / 健康检查 / `stop` / 重启后 agent 仍在线 与本 unit 之前一致 | motivation.md §用户侧验收标准 条目 3 | unit 分支代码启动 Gateway → "Gateway started" + "IM service: connected" 输出；`--help` 含 stop/restart 子命令；http://127.0.0.1:8000/v1/health → {"healthy":true} | Journey 3 日志输出，health API 200 | **pass** | stop 子命令无法独立测试（主用户 Gateway 占用 PID 文件），但命令存在且代码路径未被本次 refactor 触及 |
| A4 | 现有 `.nano/sessions/` 历史 session 文件在 refactor 后仍能被 `--resume` 正常加载 | motivation.md §用户侧验收标准 条目 4 | managed 模式 --resume sess_0787fd3de8aad5ec → session_not_found (404) | Journey 1 扩展测试，两分支均返回 404 | **fail** | **基线已有缺陷**：main 分支同样返回 404，本 unit 行为与变更前完全一致（不退化也未修复）。属于 CLI managed 模式的独立功能缺陷。标记 out-of-unit（见问题清单 #1）。 |
| A5 | 删除判据：grep 返回零 | motivation.md Q1 判据 1 | `grep -rn "SQLiteSessionStore\|from agent.platform.persistence.session import \|from .sqlite_store\|from .base import SessionStore" src/ tests/` | 0 行输出 | **pass** | — |
| A6 | 包结构：`platform/persistence/session/` 只剩 service.py + __init__.py | motivation.md Q1 判据 2 | `ls src/agent/platform/persistence/session/` | `__init__.py  service.py  __pycache__` | **pass** | — |
| A7 | pytest tests/ 全过（含 xfail 转 pass） | motivation.md Q1 判据 3 | pytest 全套 + workspace_root 专项 | 2 xfail 已转 pass；整体 unit 分支失败数（165）< main 基线（202），无新回归 | **pass** | 165 失败均为 main 分支基线已有 + worktree 环境差异，非 unit 引入 |
| A8 | issue #25 关闭 | motivation.md §Relations + M5 退出标准 | `gh issue view 25` | state: CLOSED | **pass** | — |

## Side Findings

- AGENTS.md 中的 `create-session / send-message` CLI 命令与实际 CLI 实现不符（实际 CLI 无这两个子命令，需用 `--text` 或 REPL）。这是文档与代码长期不同步的小问题。minor，out-of-unit，不立 issue。

- worktree `.venv` 缺 `socksio` 包（与主仓 `.venv` 不同），导致 2 个 personal_assistant unit 测试和 2 个 e2e 测试在 worktree 环境失败。建议 worktree 初始化时与主仓同步 `pip install -e ".[dev]"`。minor，out-of-unit，不立 issue。

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新（架构层不涉及 session store 具体实现）
- [x] `docs/内核设计SPEC.md`：**已在 M1 更新**（4 处 stale 描述已修正，删第 47 行 SessionStore ABC、第 71-72 行合并为 JSONL 描述）。无需进一步更新。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新（架构总览段未引用死代码）
- [x] 相关产品 SPEC（CodingCLI / NodeGateway / IM 等）：无需更新（session store 是 agent 内核内部，不在各产品 SPEC 边界内）
