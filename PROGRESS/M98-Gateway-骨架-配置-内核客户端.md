# M98 Gateway 骨架 + 配置 + 内核客户端

## 启动记录
- 已阅读：`SPEC.md`、`docs/NodeGateway-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M98，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M98`，branch=`milestone/M98`。
- 测试门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M98/src pytest -q`。
- 基线结果：开始前全量 pytest 失败 1 条，失败点为 `tests/contract/test_multi_product_architecture_acceptance.py::test_architecture_docs_describe_zero_residue_target_state` 读取旧 agent 线程私有路径下的 `多产品架构调整建议.md`，与 M98 scope 无关；M98 在该基线上继续执行，但需确保不新增失败。
- prevention / 注意事项：
  - 严守 NodeGateway-SPEC §15：`personal_assistant` 不得直接 import `agent` 内部模块，所有内核交互通过 HTTP client。
  - 仅实现 M98 所需骨架、配置、client、入口生命周期；不提前落地 M100+ 的 channel / queue / ws / scheduler 实现。
  - worktree 内 `data/dev-tasks.json` 已链接到主仓共享文件，避免状态分叉。

### R1 包骨架与配置加载
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 内核 HTTP 客户端
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R3 进程入口与内核子进程生命周期
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
