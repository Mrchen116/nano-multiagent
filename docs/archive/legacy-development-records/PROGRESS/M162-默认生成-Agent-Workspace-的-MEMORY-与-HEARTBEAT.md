# M162 Progress — 默认生成 Agent Workspace 的 MEMORY.md 与 HEARTBEAT.md

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M162`
- 已确认 branch：`milestone/M162`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读文件：
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `src/personal_assistant/scheduler/heartbeat_scheduler.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`

## 初始根因判断
- `_IMConfigSyncClient.sync_agent()` 在 Agent 创建/同步真实链路里只会 `mkdir` workspace 根目录，不会默认创建 `MEMORY.md` 与 `HEARTBEAT.md`。
- `load_local_config()` 在本地初始化入口里只保证默认 workspace 目录存在；对于已存在但缺文件的 workspace 也没有补齐逻辑。
- `HEARTBEAT.md` 目前允许不存在，scheduler 会静默跳过，因此“默认必须存在”的产品保证尚未落地。
- 缺少针对“默认生成两个文件且不覆盖已有内容”的单测，导致该退化没有被门禁捕获。

## 执行策略
1. 先补 `TASKS/M162` 与 `PROGRESS/M162`，锁定入口、Roadpoints 与验证命令。
2. 再以 TDD 方式补单测，覆盖新建 workspace 与已有 workspace 缺失文件的补齐行为，以及幂等不覆盖已有内容。
3. 最后在统一的 workspace 初始化逻辑接入 `load_local_config()` 与 `_IMConfigSyncClient.sync_agent()`，跑聚焦验证并完成提交收口。

## 进度

### R1 锁定 workspace 默认文件生成入口与测试门禁
- Context:
  - 需要先确认真正负责 Agent workspace 创建/初始化的入口，避免只修表层调用点。
- Decision:
  - 将 `load_local_config()` 视为本地初始化/补齐入口。
  - 将 `_IMConfigSyncClient.sync_agent()` 视为新建 Agent 的真实创建/同步入口。
  - 以 `test_local_store.py` 与 `test_main.py` 承接聚焦回归门禁。
- Rationale:
  - 这两条路径分别覆盖“已有 workspace 初始化”和“真实 Agent 创建链路”，合在一起可满足 milestone 出口标准。
- Evidence:
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
- Status: DONE

### R2 在默认创建与初始化入口补齐 MEMORY/HEARTBEAT 默认文件
- Context:
  - 仅创建目录还不能满足产品要求；需要统一且幂等的默认文件补齐逻辑，并接入初始化入口与真实创建链路。
- Decision:
  - 在 `src/personal_assistant/config/local_store.py` 新增 `ensure_workspace_defaults()`，集中负责创建目录并补齐 `MEMORY.md` 与 `HEARTBEAT.md`。
  - 让 `_parse_agents()` 在默认/显式 workspace 上都调用该 helper，覆盖本地初始化与已有缺失 workspace 补齐。
  - 让 `_IMConfigSyncClient.sync_agent()` 在注册 live agent 前也调用该 helper，覆盖真实 Agent 创建/同步链路。
- Rationale:
  - 统一入口可避免多个调用点各自散落 `mkdir`/写文件逻辑，减少未来漂移；`exists()` 门控可保证已存在文件不被覆盖。
- Evidence:
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
- Status: DONE

### R3 聚焦验证、记录与收口
- Tests:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_local_store.py`
    - 结果：`11 passed`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_main.py -k "im_config_sync_client or workspace"`
    - 结果：`2 passed, 25 deselected`
- Verification notes:
  - `test_local_store.py` 已锁定：默认 workspace 会生成 `MEMORY.md` 与 `HEARTBEAT.md`、显式 workspace 缺文件时会补齐、已有文件不会被覆盖。
  - `test_main.py` 已锁定：IM Agent 创建/同步链路会补齐两个默认文件，且不会覆写已有内容。
  - `HEARTBEAT.md` 默认模板只提供安全占位说明，不引入默认 schedule，因此不会改变现有 scheduler 触发语义。
- Commits:
  - C1=`ed00037` `docs(M162): outline workspace default file backfill plan`
  - C2=`<pending>`
- Status: DONE

## 回滚点
- 若需回滚本 milestone，只需撤回：
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `TASKS/M162-默认生成-Agent-Workspace-的-MEMORY-与-HEARTBEAT.md`
  - `PROGRESS/M162-默认生成-Agent-Workspace-的-MEMORY-与-HEARTBEAT.md`

## 当前结论
- 缺口已完成修复：现在不论是本地配置初始化，还是 IM Agent 创建/同步链路，workspace 都会默认具备 `MEMORY.md` 与 `HEARTBEAT.md`。
- 补齐逻辑是幂等的：缺文件时自动创建，已有文件保持原样，不会破坏已有长期记忆与 heartbeat 定义。
- 聚焦验证已通过，本 milestone 已具备合并前评审条件；合入 `main` 后仍需按要求纳入 Agent 创建真实链路复验。
