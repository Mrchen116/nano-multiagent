# M1-fix: progress

## 架构决策（Option C，owner 拍定）：内核无状态，workspace_root 调用方每次带上

lite 模式无 design.md，最终方案记录如下（单一方案，非过程推演）。

**问题**：`JsonlSessionStore` 构造时定死单一 `data_dir`，bootstrap 把它写成进程 cwd 下的
`.nano`，导致所有 session 落入进程 cwd，与 feat-330 design.md 要求的
`{workspace_root}/.nano/sessions/` 不符。

**鸡蛋问题**：`load(session_id)` 时 workspace_root 写在 JSONL 首行，读首行先要知道文件在哪。
feat-330 design.md 本身没解决这个窟窿（「文件位置」段写按 workspace_root 分目录，但
`_resolve_path` 伪代码用扁平 `data_dir`、`load()`/`run()` 只传 session_id）。本 bugfix 补它。

**决策（Option C）**：内核不持有、也不持久化 `session_id → workspace_root` 映射。需要定位
session 文件的请求由调用方每次带上 `workspace_root`——gateway 和 CLI 本来就知道（PA 在
gateway 配置里有每个 agent 的 workspace_root；CLI 是自己的工作目录）。内核每次从入参拿。

为什么不是内存缓存：内存缓存进程重启即空，跨重启 resume 直接坏掉
（`session_bindings.sqlite3` 持久化 binding、feat-330 整个 resume 链路都依赖跨重启按
session_id 定位）。为什么不是持久化索引：owner 评估后选择更彻底的「内核无状态」——
不引入任何内核侧状态文件，把"我属于哪个 workspace"的知识留在本来就掌握它的调用方。

### `data_dir` 回退边界

`JsonlSessionStore` 保留 `data_dir` 作为**可选默认 base**，但这**只是测试脚手架**：

- 生产侧 `bootstrap.py` 永远传 `data_dir=None`，不留任何 cwd 回退。
- `data_dir=None` 的 store（即生产 store）若调用方没传 `workspace_root`，
  `_resolve_base` **显式抛 `SessionNotFoundError`**（带清晰报错信息），绝不静默落到某个
  默认目录。漏传 workspace_root 是调用方 bug，必须大声失败——静默回退正是 bugfix-348
  要修的原 bug，让它无声回来比现在更难查。
- `data_dir` 有值时（测试用 `JsonlSessionStore(data_dir=tmp_path)`）走旧扁平布局，
  现有 `data_dir=` 测试不用大改。

### scanning 操作处理

- `find_session_by_metadata`（agent 工具按 agent_id 找 subagent）：subagent JSONL 在父
  session 的 workspace_root 下，agent 工具运行时父 session 已加载，从 runtime
  (`session_workspace_root`) 取父 workspace_root，作用域化扫描。agent_index 每次按传入
  workspace 重建，不跨 workspace 缓存。
- `list_session_ids`（`GET /v1/sessions` 列表）：探查确认**无产品调用方**——CLI/PA 都只用
  create + get-one + append + stream，不用 list。内核无状态下无法跨 workspace 列举，
  作用域化为「按传入 workspace_root 列举」，HTTP 路由加 `workspace_root` 查询参数。
- `_dispatch_session_shutdown`（kernel 退出时对所有 session 触发 `session_shutdown` 钩子）：
  原实现 `list_sessions()` 扫盘——无状态内核拿不到全集。改为遍历 `runtime` 内存里的活跃
  session（`active_session_ids`）——这也是语义正确的：只对本进程真正跑过的 session 触发
  shutdown，而不是对磁盘上某个 workspace 里躺着的旧 session 触发。

---

### R1 — 调研调用链 + 确认 scanning 操作可作用域化

- Context: 需确认两个产品的内核进程模型、`load`/`get_session` 调用链、scanning 操作
  （list/find_by_metadata/shutdown 广播）能否作用域化。
- Decision: 两产品都是单内核进程多 session（`kernel_app.py` 各调 `create_app` 一次）。
  `load`/`get_session` 的 HTTP 入口只收 `session_id`——印证鸡蛋问题。三个 scanning 操作
  全部可作用域化（见上）；无需停下来回报 design 问题。
- Rationale: 明确修复点 = JsonlSessionStore + SessionManager + SessionService + runtime +
  RunsRegistry + HTTP 路由 + 两端 client；scanning 操作有干净的作用域来源。
- Evidence: 读代码（kernel_app、managed_server、inbound_pipeline、agent/task 工具、app.py
  shutdown 钩子、CLI/PA client）。
- Rollback: N/A
- Commits: plan=ad5cb7d0
- Next: R2

---

### R2 — JsonlSessionStore + SessionManager 改「调用方传 workspace_root」

- Context: store 需放弃单一 `data_dir` 假设，路径按每个 session 的 workspace_root 解析。
- Decision: store 的 `create`/`load`/`append`/`update_config`/`resolve_path`/
  `list_session_ids`/`find_session_by_metadata` 接收 `workspace_root` 入参；
  `_resolve_base` 优先 `data_dir`（测试脚手架）否则 `{workspace_root}/.nano`，两者皆无则
  `SessionNotFoundError`。`SessionManager` 同步透传。
- Rationale: 见顶部决策段。`data_dir` 优先是为了让海量现有 `data_dir=` 测试零改动通过；
  生产 `data_dir=None` 永远走 workspace_root 分支。
- Evidence: 见 R3 合并 Evidence（R2/R3 同批测试）。
- Rollback: C1 commit 60671e07
- Commits: 见 R3
- Next: R3

---

### R3 — runtime / RunsRegistry / HTTP 路由 / 两端 client 透传

- Context: workspace_root 要一路 thread through 到真实入口（HTTP + 工具 + 两端发送方）。
- Decision:
  - `AgentRuntime.run`/`continue_turn`/`compact`/`fork_session`/`get_session` 接收
    `workspace_root`；首次 load 后 `config.workspace_root` 缓存供后续写入；新增
    `active_session_ids` / `session_workspace_root` 访问器。
  - `RunsRegistry`: `RunRecord` 增 `workspace_root`，`submit` 透传给 `runtime.run`。
  - HTTP: `SendMessageRequest`/`AppendMessageRequest` 增字段；fork/compact/interrupt 用
    `SessionWorkspaceBody`；GET 路由加 `workspace_root` 查询参数；`_optional_workspace_root`
    对既有 session 不做 cwd 兜底（缺失即让 store 大声报错）。
  - 工具：agent/task 工具从 runtime 取父 session workspace_root 透传给 subagent 路径；
    `BackgroundSubagentRunner.start` 增 `workspace_root`。
  - 两端：PA `kernel_api_client` + gateway + heartbeat + `InternalDispatchHandler` 带上
    agent 配置里的 workspace_root；`PersistentSessionBindingStore.get()` 去掉冗余失效的
    kernel 探活（存活/workspace 校验上移到 `_binding_matches_workspace_root`）；CLI client
    各方法默认带 `os.getcwd()`。
  - `app.py` shutdown 钩子改用 `runtime.active_session_ids()`。
- Rationale: workspace_root 的来源在调用方——HTTP body/query、工具的 `ctx.cwd`、gateway
  的 agent 配置、CLI 的 cwd。每一处都从它本来就知道的地方取，内核纯透传不存储。
- Evidence:
  - Tests:
    - `pytest tests/unit/test_platform_bootstrap.py` → 14 passed（含跨重启 load、缺
      workspace_root 显式抛错、list 按 workspace 作用域）
    - `pytest tests/unit/test_session_manager.py tests/unit/test_session_service.py
      tests/unit/test_session_service_with_profile.py tests/unit/test_jsonl_store_dag_recovery.py
      tests/unit/agent/session/ tests/unit/test_fork_session.py
      tests/integration/test_session_flow_integration.py tests/integration/background_tasks/`
      → 57 passed, 1 pre-existing failure（`test_append_message_persists_history_once_per_idempotency_key`，
      与本修复无关，round-1 即确认 pre-existing）
    - 全量回归 `pytest tests/unit tests/integration tests/contract`（排除两个 collection-error
      文件 `test_m170_*`）：与基线逐项 diff，**0 个新失败**（基线 156 个 pre-existing 失败，
      多为缺依赖/无关 tools 测试；修复后 154，因装 aiohttp 顺带修了一个环境失败）。
  - Entry: `test_http_workspace_root_threaded_to_session_jsonl_location` —— 真实 HTTP
    create+append+get 全链路，断言 JSONL 落在请求带的 workspace_root 下、不在进程 cwd，
    且缺 workspace_root 时 GET 返回 404（store 大声报错）。
  - 跨重启证据: `test_stateless_store_load_survives_process_restart` —— store A create+写
    turn → 丢弃 A → 全新 store B（零内核状态）→ `load(session_id, workspace_root=...)`
    读回 config+messages，`append` 后再 load 读到两条 turn。
  - Frontend State Matrix / Browser QA / E2E / Visual: N/A（纯后端，无前端、无 e2e 体系）
- Rollback: C1=60671e07, C2=e8a3bb89
- Commits: plan=ad5cb7d0, C1=60671e07, C2=e8a3bb89, C3=(本次)
- Next: 回填 fix.md，合并到 unit/bugfix-348
