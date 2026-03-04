# M63 REPL命令屏障与在途消息排空一致性

日期：2026-03-04
分支：`milestone/M63`
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M63`

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `112 passed, 44 warnings`

### Plan（一次性拆分）
- Context:
  - 当前 REPL 在 `in-flight` 消息存在时，会对非 `/exit` 命令执行屏障等待；但 timeout 反馈粒度与 `/exit` 收口提示不一致。
  - 本里程碑只允许改 CLI 与指定测试，不改 events/render 深层逻辑。
- Decision:
  - 在 `commands.py` 收敛队列屏障提示与 timeout 判定策略，避免 `/history` 假阳性超时。
  - 在 `repl_runtime.py` 修正 `wait_for_drain` 截止边界竞态，降低“已排空却判定超时”的概率。
- Rationale:
  - 问题核心在命令入口编排与队列排空判定边界，最小修复路径是 CLI 层统一屏障函数 + 队列等待判定微调。
- Evidence:
  - Tests: baseline `112 passed, 44 warnings`。
  - Entry: 已完成 `LOGBOOK/COMMENTING_GUIDE/内核设计蓝图` 阅读并确认作用边界。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：先补红测锁定 false-timeout 与 `/exit` 剩余信息场景。

### R1 /history 与 /exit 的 in-flight 屏障一致性修复
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `TBD`
  - Entry: `TBD`
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
