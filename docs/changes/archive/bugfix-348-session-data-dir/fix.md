# bugfix-348: session JSONL 未按 workspace_root 存储

## Relations

- Related: feat-330

## 原始报告

> 等下，commit了？那现在个人助手的聊天记录放在哪里？哪里的jsonl，我没看到

> 比如，我在 http://127.0.0.1:8011/chat/50e80bda7ac145219d46a4a4f6e2ed27 和"架构"Agent的沟通存在哪里

> 实现了就不用改这两个文档了。但是落进了仓库目录里的 .nano/ 和需求不一致吧

> 在main分支的worktree上开个bugfix吧，其实就是一个很小的改动，对吧？

> 照 design 改版

## 澄清记录

- Q1: 修复目标是"小修版"（让 session 落到产品固定 home，session 仍平铺在一个目录），还是"照 design 改版"（按 feat-330 design.md 的 `{workspace_root}/.nano/sessions/` 分目录存）？
  A: 照 design 改版 —— 按 design.md 的 `{workspace_root}/.nano/sessions/{session_id}.jsonl` 存。
- Q2: 影响范围只算个人助手，还是 Coding CLI 也算、修复一并覆盖？
  A: 一并覆盖。两个产品都受同一根因影响，修复同时覆盖个人助手和 Coding CLI。
- Q3: 已经落在旧位置（启动进程 cwd 的 `.nano/sessions/`）的 session 文件要不要迁移到新位置？
  A: 不迁移。修复只改"今后新建/写入的落点"，旧文件留在原地（feat-330 已定调"开发态不兼容旧数据"；IM 侧 SQLite 仍有完整聊天副本，丢的只是内核侧 resume 上下文）。

## 现象 / 复现

feat-330 给 agent 内核引入了 JSONL 会话存储，design.md 要求会话落在
`{workspace_root}/.nano/sessions/{session_id}.jsonl` —— 即每个会话的 JSONL 跟着它自己的
workspace 走。实际落地的行为不是这样：

- 会话 JSONL 落在**启动内核进程时的当前工作目录（cwd）下的 `.nano/sessions/`**，与
  会话自己的 `workspace_root` 无关。
- 复现（100% 必现）：在仓库目录下启动个人助手 Gateway → 和某个 agent（如"架构"）对话
  → 该会话的内核 JSONL 出现在 `<仓库目录>/.nano/sessions/sess_xxx.jsonl`（git 未跟踪的
  脏文件），而不是该 agent 的 workspace `~/nano-assistant/workspace/架构/.nano/sessions/` 下。
  Coding CLI 同理：会话落在"启动 CLI 时的 cwd"，而非 design 要求的 workspace 下。

后果：

1. 所有 agent、两个产品的会话平铺进同一个 cwd 相关目录，**无 workspace 隔离**。
2. 换个目录启动内核 → 之前的会话"找不到"（resume 不到，因为还在旧 cwd 的 `.nano/` 里）。
3. 污染代码仓库 —— 会话文件以未跟踪状态堆在仓库目录里。

不涉及数据损坏：写入的 JSONL 内容本身正确，只是落点错；IM 侧 SQLite 仍有完整聊天副本，
前端 `/chat` 页面读的是 IM 存储而非内核 JSONL。

## 根因

- 直接原因：`src/agent/platform/bootstrap.py` 构造内核 session store 时，把存储根目录写死成
  「内核进程 cwd」下的 `.nano/` —— 用的是 bootstrap 的 `repo_root` 入参，和会话的
  `workspace_root` 完全无关。`src/agent/platform/persistence/session/service.py` 的
  `_resolve_data_dir()` 同样只返回 cwd 相对的 `.nano/`：它的 docstring 甚至声明了"优先级 2：
  按 Profile 的 global_config_home 解析"，但代码体里根本没实现这一分支 —— 实现连自己
  docstring 声明的意图都没写完。
- 为什么这种错能进来：feat-330 design.md 写的是按 `workspace_root` 分目录存，但 session store
  的存储根目录是**进程启动时一次性定死的单一目录**，而 `workspace_root` 是**每个会话各自不同**
  的。存储层的接口形态（构造时定死一个根目录）和 design 意图（按每个会话的 workspace 解析路径）
  从一开始就不对齐。feat-330 落地时没人拿 design 的存储路径做对照验证；PR review 也没卡住 ——
  因为 feat-330 的验收标准里没有把"会话存储位置"列成可验项（当时被当成实现细节），这条偏差
  就直接溜过了。

## 修复

方案：**内核无状态，`workspace_root` 由调用方每次请求带上**（Option C，owner 拍定）。
内核不持有、也不持久化 `session_id → workspace_root` 映射——需要定位 session 文件的
请求由调用方带上 `workspace_root`（gateway 从每个 agent 的配置取，CLI 取自己的工作目录）。
覆盖个人助手 + Coding CLI 两个产品。

### 内核侧

- **`src/agent/core/session/jsonl_store.py`** — `JsonlSessionStore` 改为无状态：
  `create` / `load` / `append` / `update_config` / `resolve_path` / `list_session_ids` /
  `find_session_by_metadata` 接收调用方传入的 `workspace_root`，路径解析为
  `{workspace_root}/.nano/sessions/{session_id}.jsonl`。`data_dir` 降为「可选默认 base」，
  **仅供测试脚手架**；`_resolve_base` 优先 `data_dir`，否则 `{workspace_root}/.nano`，
  两者皆无则**显式抛 `SessionNotFoundError`**——绝不静默回退 cwd（静默回退正是本 bug）。
- **`src/agent/platform/bootstrap.py`** — `JsonlSessionStore(data_dir=None)`，杜绝生产
  cwd 回退（改前是 `data_dir=resolved_root / ".nano"`，`resolved_root` 是进程 cwd，
  即根因）。
- **`src/agent/core/session/manager.py`** — `SessionManager` 各方法透传 `workspace_root`。
- **`src/agent/core/agent/runtime.py`** — `run` / `continue_turn` / `compact` /
  `fork_session` / `get_session` 接收 `workspace_root`；首次 load 后 `config.workspace_root`
  缓存供后续写入；新增 `active_session_ids` / `session_workspace_root` 访问器。
- **`src/agent/core/runs/registry.py`** — `RunRecord` 增 `workspace_root` 字段，`submit`
  透传给 `runtime.run`。
- **`src/agent/platform/persistence/session/service.py`** — `SessionService` 透传
  `workspace_root`；并修根因第二处：`_resolve_data_dir` 整个删掉（其 docstring 宣称的
  "优先级 2：profile global_config_home" 从未实现，正是【根因】段所指），`_resolve_store`
  改为 `NANO_MULTIAGENT_DATA_DIR` 环境变量存在时用它（明确 opt-in），否则返回
  `JsonlSessionStore(data_dir=None)`（无状态）——**去掉静默的 `Path(".nano")` cwd 回退**。
  注：`_resolve_store` 仅在 `create_app()` 无 profile 且无显式 store 时可达（测试/SDK
  glue）；生产两产品的 `kernel_app.py` 都传 profile，store 由 `bootstrap_product` 注入，
  此 fallback 对生产不可达——但 cwd 相对 fallback 留着会误导，故一并修掉。
- **`src/agent/platform/http_api/app.py`** — kernel 退出时的 `session_shutdown` 钩子广播
  改为遍历 `runtime.active_session_ids()`（无状态内核无全局注册表；且只对本进程跑过的
  session 触发也是语义正确的）。

### HTTP 层

- **`src/agent/platform/http_api/routes/session.py`** — `SendMessageRequest` /
  `AppendMessageRequest` 增 `workspace_root` 字段；fork/compact/interrupt 用新增的
  `SessionWorkspaceBody`；GET 路由（get_session / list / tools / messages / context-budget /
  stream）增 `workspace_root` 查询参数。`_optional_workspace_root` 对既有 session 不做 cwd
  兜底——缺失即让 store 大声报错。

### 工具层

- **`agent.py` / `task.py`** — subagent JSONL 在父 session 的 workspace_root 下，从
  runtime 取父 workspace_root 透传给 subagent 路径；`BackgroundSubagentRunner.start`
  （`interfaces.py` / `runtime_runner.py` / `wiring.py`）增 `workspace_root`。

### 两端发送方

- **PA** — `kernel_api_client` 的 `submit_message` / `append_message` / `interrupt_session` /
  `get_session` 增 `workspace_root`；`inbound_pipeline` / `heartbeat_scheduler` 从 agent
  配置取 workspace_root 带上；`InternalDispatchHandler` 注入 `agent_id → workspace_root`
  映射；`PersistentSessionBindingStore.get()` 去掉冗余且失效的 kernel 探活——存活/workspace
  校验上移到 `_binding_matches_workspace_root`（那里知道 agent 的 workspace_root）。
- **Coding CLI** — `client` 的 `submit_message` / `stream_session` / `list_session_tools` /
  `compact_session` / `get_context_budget` / `get_session_messages` 默认带 `os.getcwd()`
  （CLI 进程单一工作目录，与 `create_session` 既有默认一致）。

### 其他

- `.gitignore` 补 `.nano/`：测试以 cwd 作 workspace_root 时会在仓库内生成，不提交。

### Commits

- `ad5cb7d0` — plan: 改采 Option C，tasks.md 架构决策段收口为单一方案
- `60671e07` — C1: 失败测试（跨重启 load、缺 workspace_root 显式抛错、HTTP 全链路透传）
  + 各测试替身签名更新
- `e8a3bb89` — C2: 实现（内核无状态 + 全链路 workspace_root 透传 + 两端 client）
- `0f915d9b` — C3: progress.md 重写为 Option C + fix.md 回填
- `a48182af` — C1（R4）: 改对两个把旧 bug 当期望值的 stale 测试
  （`test_app_factory_with_profile` / `test_session_service_with_profile`）
- `47cf290b` — C2（R4）: 修根因第二处 `_resolve_store` —— 去掉静默 cwd 回退
- `4191f5f2` — C2（R4）: 修 `_resolve_store` 改无状态后连带破的 4 个 bare-`create_app` 测试
- C3（本 commit）— progress.md 补 R4 段 + 全量 diff 结果 + fix.md 回填

> 注 1：本 unit 早期一版（已合入的 `d555c887`）走的是「内核内存缓存 workspace_root」方案，
> 该方案进程重启后 load 不到上一进程写的 session，破坏跨重启 resume。后续按 owner 决策
> 撤掉内存缓存，改为内核无状态。
>
> 注 2：R4 是 orchestrator §3.3 核对退回补齐——R3 漏了把旧 bug 当期望的 stale 测试、
> 漏修根因第二处 `_resolve_data_dir`、且当时只跑核心子集误报「0 回归」。R4 三项全部补齐，
> 并自己跑了与 main 同口径的全量 diff（结果见「验证 / 回归」段）。

## 验证

### 修前能复现

```bash
# 在仓库目录下启动个人助手
PYTHONPATH=src python -m uvicorn personal_assistant.kernel_app:app --port 18070

# 创建 session（workspace_root 指向某 agent 工作区）
curl -s -X POST http://127.0.0.1:18070/v1/sessions \
  -H "Authorization: Bearer test-token" -H "Content-Type: application/json" \
  -d '{"workspace_root": "/tmp/agent-workspace-test"}'

# 修前：JSONL 落在仓库目录下的 .nano/sessions/，不在 /tmp/agent-workspace-test/.nano/sessions/
ls .nano/sessions/                            # 可见 sess_xxx.jsonl（污染仓库）
ls /tmp/agent-workspace-test/.nano/sessions/  # 不存在
```

### 修后不能复现 + 跨重启 resume 正常

新增/改写测试全部通过（`pytest tests/unit/test_platform_bootstrap.py
tests/integration/test_session_flow_integration.py` 等）：

- `test_session_jsonl_falls_in_workspace_root_not_process_cwd` —— 直接断言 JSONL 落在
  `{workspace_root}/.nano/sessions/{session_id}.jsonl`，且**不在**进程 cwd。
- `test_workspace_aware_store_multiple_workspaces_isolated` —— 两个不同 workspace 的
  session 各自落在自己目录，互不串。
- `test_stateless_store_load_survives_process_restart` —— **跨进程重启**：store A
  create + 写 turn → 丢弃 A → 全新 store B（零内核状态）→ `load(session_id,
  workspace_root=...)` 读回 config + messages，`append` 后再 load 读到两条 turn。
  证明无状态内核靠调用方传入的 workspace_root 即可跨重启 resume（修复了早期内存缓存
  方案的回归）。
- `test_stateless_store_raises_without_workspace_root_and_without_data_dir` —— 缺
  workspace_root 且无 data_dir 时显式抛 `SessionNotFoundError`，不静默回退 cwd。
- `test_http_workspace_root_threaded_to_session_jsonl_location` —— 真实 HTTP
  create + append + get 全链路：JSONL 落在请求带的 workspace_root 下、不在进程 cwd；
  缺 workspace_root 的 GET 返回 404（store 大声报错而非静默命中错位置）。

### 回归（全量 diff，与 main 同口径）

> R3 当时只跑核心子集就下了「0 回归」结论，是错的——orchestrator 全量 diff 抓到 1 个真
> 新失败（stale 测试）。R4 改为**自己跑与 main 完全同口径的全量 diff**。

命令：`pytest -m "not e2e" --continue-on-collection-errors -q --tb=no`，抓 `FAILED`/`ERROR`
行排序，与 `origin/main` 同命令结果逐项 diff。

| | FAILED+ERROR 行 | failed | passed |
|---|---|---|---|
| `origin/main` | 207 | 206 | 1296 |
| 本 unit（R4 全部提交后） | 207 | 206 | **1303** |

- **新失败 0、意外修复 0**——FAILED+ERROR 集与 main **完全一致**。
- `passed` +7 = 本 unit 新增/改写的测试（跨重启 load、HTTP workspace_root 透传、无状态
  store 断言、两个 stale 测试改对等）。
- 过程中 R3 merge 后曾 diff 出 2 个新失败：① stale 测试 `test_app_factory_with_profile`
  （R4 已改对）；② `test_safety_background` —— 排查确认 pre-existing flaky（零处引用
  session 代码，隔离重跑全 pass，是 background-process 计时竞态在全量并发下偶发），
  最终全量 diff 未再出现。

核心 session 测试集（`test_platform_bootstrap` / `test_session_manager` /
`test_session_service*` / `test_app_factory_with_profile` / `test_jsonl_store_dag_recovery` /
`agent/session/` / `test_fork_session` / `test_session_flow_integration` / `background_tasks/`）
单独跑：全绿（除 `test_append_message_persists_history_once_per_idempotency_key` 与
`test_create_app_with_profile_uses_resolver_skill_roots_over_legacy_codex` 两个 pre-existing
failure——均在 main 基线里就失败，与本修复无关）。

## R5: 评审反馈 — dirname 走 `profile.workspace_config_dirname`

R1-R4 修对了 session JSONL 的**位置**（落到 `workspace_root` 下），但把 dirname
`.nano` 当作不变常量硬编码——绕过了仓内已有的 `profile.workspace_config_dirname`
抽象（PA: `.nanoassistant` / LC: `.nanocode`）。后果是 merge 后同一 PA workspace 下
session 落 `.nano/sessions/`、memory / skill / hook 落 `.nanoassistant/`，**比修前更乱**。

评审作者本人在 feat-385 design 阶段提出（PR #9 上的 self-review，倾向选项 1：本 PR 顺手收）。
feat-385 design.md "决策 10" 已把"per-workspace 资源必须走 `profile.workspace_config_dirname`、
禁硬编码 `.nano` / `.nanoassistant` / `.nanocode`"立为架构原则，并把 PR #9 列为 session
JSONL 部分的落地点。本轮按这一原则收口：

- `src/agent/core/session/jsonl_store.py`：`JsonlSessionStore.__init__` 新增
  `workspace_config_dirname: str = ".nano"` 参数；`_resolve_base` 把硬编码的 `".nano"`
  改为 `self._workspace_config_dirname`。默认值 `.nano` 仅供裸构造的测试脚手架使用，
  生产链路由 bootstrap 显式覆盖。
- `src/agent/platform/bootstrap.py`：构造 store 时传
  `workspace_config_dirname=profile.workspace_config_dirname or ".nano"`，让 PA / LC
  session JSONL 与 memory / skill / hook 共住同一 per-workspace 子目录。
- 同步改 `tests/unit/test_app_factory_with_profile.py` 端到端断言走
  `profile.workspace_config_dirname`，不再写死 `.nano/sessions/`。

### 顺手解的事

merge `origin/main` 进 bugfix-348 时，feat-383 / bugfix-384 在 RunsRegistry / KernelApiClient
等链路上加了 `origin` 参数，与本 unit 加的 `workspace_root` 参数并存。解 13 个冲突
（含一个 modify/delete：`tests/unit/personal_assistant/test_gateway_pipeline.py` 在 main 上
被 refactor-372 拆成 5 个文件，HEAD 上只加了 `**_kwargs` 兼容——保留 main 的拆分，把
`**_kwargs` 迁到 `_pipeline_helpers.py`）。

merge 后全量回归（`pytest -m "not e2e"`）：**2407 passed / 0 failed**，
含本轮新走 dirname 抽象后所有 session / runtime / contract / IM 路径。
