# M115 Gateway 默认 workspace 与内部 kernel 配置收口

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M115/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/src/personal_assistant/config/local_store.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/src/personal_assistant/main.py`、相关 unit/e2e 测试、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/README.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M115/docs/operator-runbook.md`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M115，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M115`，branch=`milestone/M115`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/unit/personal_assistant tests/e2e/test_personal_assistant_main_e2e.py tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- 基线结果：`45 passed`。
- prevention / 注意事项：
  - `workspace_root` 缺省必须落到 `~/nano-assistant/workspace/<agent_id>/`，仅显式配置时覆盖。
  - `kernel.base_url` 视为内部实现细节，用户最小配置不应暴露为必填项。
  - 真实入口验证不能退化为只测 loader happy path。
  - 只做最小必要改动，不做无关重构。

### R1 默认 workspace_root 解析与创建
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 kernel.base_url 内部化与文档示例收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
