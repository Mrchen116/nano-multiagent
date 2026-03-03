# PROGRESS (Milestone: M33)

- Title: 独立IM服务骨架与SQLite持久化
- Goal: 在 `src/IM` 创建独立 FastAPI IM 服务，落地 SQLite 持久化（用户/会话/消息）并提供 conversations/messages 基础增查接口。
- Exit Criteria:
  - 新增独立服务入口 `src/IM/app.py`，可单独启动。
  - SQLite 持久化落地并具备初始化机制。
  - 提供 conversations/messages 基础增查接口并通过 unit+integration。
  - 不改动 `src/nano_multiagent/*`。
  - 测试全绿（`PYTHONPATH=src pytest -q tests/im_service`）。
- Test command: `PYTHONPATH=src pytest -q tests/im_service`
- Branch: `milestone/M33`

### Baseline
- Context:
  - execution_mode=`parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M33`，branch=`milestone/M33`。
  - 已按技能要求在 worktree 建立 `data -> /Users/czj/Repos/nano-multiagent/data` 共享链接，确保 `data/dev-tasks.json` 与 `data/locks` 同源。
  - prevention_rules：保持 IM 服务独立边界，只做“人和人聊天”后端，不改 `src/nano_multiagent/**`。
- Decision:
  - Roadpoint 划分为三段：`R33.1` 数据层初始化、`R33.2` users/conversations 接口、`R33.3` messages 接口与入口收口。
- Rationale:
  - 先固化持久层再上 API，可减少路由层返工并让 Red/Green 边界更清晰。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（baseline：失败，目录不存在）。
  - Entry: 当前仓库尚无 `src/IM` 与 `tests/im_service` 实现。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - 完成 Plan 文档提交后进入 `R33.1` Red。

### R33.1 SQLite 持久化骨架与初始化机制
- Context:
  - Red 阶段新增 `tests/im_service/unit/test_db_init.py` 与 `test_repositories.py`，先红错误为 `ModuleNotFoundError: IM`。
  - 需要在不依赖 `src/nano_multiagent/**` 的前提下提供用户/会话/消息最小持久化能力。
- Decision:
  - 新建独立包 `src/IM`，落地 `models`、`infra/db`、`repositories` 三层最小实现。
  - SQLite schema 采用幂等 `CREATE TABLE IF NOT EXISTS`，并启用 foreign keys。
  - 会话创建要求 participant 非空且必须是已存在用户；消息创建要求会话存在、发送者存在且为会话成员。
- Rationale:
  - 先把约束收敛到仓储层，可确保后续 API 层只做输入映射，避免逻辑分散。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（`4 passed`）
  - Entry: `connect + initialize_schema` 可重复执行，用户/会话/消息增查与顺序断言通过。
- Rollback:
  - `bbef20b`（R33.1 C1，仅红测）
- Commits: C1=`bbef20b`, C2=`9795d47`, C3=`<pending-current-commit>`
- Next:
  - 进入 `R33.2` Red：补 users/conversations API 集成红测。

### R33.2 Users/Conversations 基础 REST 接口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R33.3 Messages 接口与独立服务入口收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
