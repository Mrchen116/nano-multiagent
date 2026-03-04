# M52 - 交互与脚本双通道契约固化（TTY/non-TTY）

日期：2026-03-04  
分支：`milestone/M52`  
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M52`

## Milestone 启动记录
- Context:
  - 目标是固化 TTY 与非交互脚本输出边界，避免 REPL 终端控制序列污染非 TTY 输出。
  - 仅允许修改 CLI 与指定测试文件；不触碰内核与非 CLI 目录。
- Decision:
  - 采用单一 Roadpoint：先补红测锁定双通道边界，再最小实现输出策略分流。
  - 门禁以用户指定命令为准，且补充 managed CLI 实跑片段作为入口证据。
- Rationale:
  - 基线已全绿，必须通过新增失败测试证明本里程碑新增能力，而不是“只复跑已有测试”。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `106 passed`
  - Entry: 已完成 LOGBOOK / 蓝图 / COMMENTING_GUIDE 启动阅读。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits:
  - plan: `TBD`
- Next:
  - 执行 R1：先红测，再实现输出策略分流与门禁回归。

### R1 双通道输出策略分离与契约护栏
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
