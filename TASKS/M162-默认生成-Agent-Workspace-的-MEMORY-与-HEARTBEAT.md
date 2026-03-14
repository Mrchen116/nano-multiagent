# M162 Task — 默认生成 Agent Workspace 的 MEMORY.md 与 HEARTBEAT.md

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M162`
- 已确认 branch：`milestone/M162`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读：
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `src/personal_assistant/scheduler/heartbeat_scheduler.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - 参考模板：`TASKS/M160-修复群聊创建参与者选择器显示与可操作性.md`
  - 参考模板：`PROGRESS/M160-修复群聊创建参与者选择器显示与可操作性.md`

## 目标
保证每个 Agent workspace 在创建或首次初始化时默认存在 `<agent_workspace>/MEMORY.md` 与 `<agent_workspace>/HEARTBEAT.md`，并且对已有 workspace 的补齐行为保持幂等，不破坏已有内容。

## 明确问题
1. 当前默认 workspace 创建只保证目录存在，没有默认落盘 `MEMORY.md` 与 `HEARTBEAT.md`。
2. IM Agent 创建真实链路中的 `_IMConfigSyncClient.sync_agent()` 只 `mkdir`，不会补默认文件。
3. 本地配置初始化入口 `load_local_config()` 对已有 workspace 也没有缺失文件补齐机制。
4. 现有测试没有锁定“自动创建两个默认文件且不覆盖已有内容”的回归门禁。

## Scope
- 找到 Agent workspace 的真实创建/初始化入口，并补齐默认文件生成。
- 为默认/显式 workspace 都提供安全、幂等的默认文件补齐。
- 增加聚焦单元测试，覆盖创建、补齐与不覆盖已有内容。
- 更新 `TASKS/M162-*.md` 与 `PROGRESS/M162-*.md`，记录 Roadpoints、验证命令、提交点与结论。

## 非目标
- 不修改 `data/dev-tasks.json`。
- 不改变 heartbeat 调度语义或新增 heartbeat 默认动作。
- 不在本 milestone 内扩展新的端到端浏览器链路；真实链路复验在合入 main 后执行。

## Roadpoints

### R1. 锁定 workspace 默认文件生成入口与测试门禁
- Status: TODO
- Acceptance:
  - 能明确指出创建/初始化 Agent workspace 的实际入口。
  - 测试先覆盖 `MEMORY.md` / `HEARTBEAT.md` 默认生成与幂等行为。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_local_store.py -k "workspace"`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_main.py -k "im_config_sync_client"`
- DoD:
  - 回归门禁能在无实现时暴露缺口，在实现后稳定通过。

### R2. 在默认创建与初始化入口补齐 MEMORY/HEARTBEAT 默认文件
- Status: TODO
- Acceptance:
  - 新建 Agent workspace 时默认存在 `MEMORY.md` 与 `HEARTBEAT.md`。
  - 已有 workspace 缺失这两个文件时可安全补齐。
  - 已有文件内容不被覆盖。
- Tests Plan:
  - 沿用 R1 聚焦单测，验证补齐与幂等。
- DoD:
  - 真实创建路径与初始化入口都调用统一的幂等补齐逻辑。

### R3. 聚焦验证、记录与收口
- Status: TODO
- Acceptance:
  - 跑完聚焦验证命令并将结果写入 PROGRESS。
  - 完成小步提交并记录 commit hash。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_local_store.py`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_main.py -k "im_config_sync_client or workspace"`
- DoD:
  - 分支可提交，结论可用于合并前评审。

## 当前结果
- 已定位两个关键入口：`load_local_config()` 的 workspace 初始化路径，以及 `_IMConfigSyncClient.sync_agent()` 的 Agent 创建/同步路径。
- 下一步按 TDD 先补测试，再在这两个入口接入统一的默认文件补齐逻辑。

## 回滚点
- 若需要回滚本 milestone，优先撤回：
  - `src/personal_assistant/config/local_store.py`
  - `src/personal_assistant/main.py`
  - `tests/unit/personal_assistant/test_local_store.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `TASKS/M162-默认生成-Agent-Workspace-的-MEMORY-与-HEARTBEAT.md`
  - `PROGRESS/M162-默认生成-Agent-Workspace-的-MEMORY-与-HEARTBEAT.md`

## 验证命令
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_local_store.py`
- `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M162/tests/unit/personal_assistant/test_main.py -k "im_config_sync_client or workspace"`

## 提交计划
- C1: 任务/进度落盘，锁定入口、Roadpoints 与验证计划
- C2: 测试与实现，补齐 workspace 默认文件生成
- C3: 若验证阶段出现收尾问题，再补最小修复提交
