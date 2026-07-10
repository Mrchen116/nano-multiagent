# M1-fix-pump-race — progress

## R1 — 写回归测试(C1 红)

- **Context**: design.md 决策"在 `on_complete` 内无 sleep 断言输出就绪",直接用 `echo hello` 在本机调度下竞态不可靠(测试假绿)。
- **Decision**: 包装 `BashFileOutput`,在 `append` 内 `time.sleep(0.3)`,把"process exit → pump 完成 append"的窗口从微秒级拉到 0.3s,断言确定性失败。
- **Rationale**: 测试必须能可靠暴露 bug 才有回归价值;包装 output 是唯一不动 shell_runner 即可放大窗口的方式,且语义上模拟了"pump 写文件慢"的真实场景(大输出 / 慢磁盘)。
- **Evidence**: C1 单跑 → `AssertionError: output not drained before callback: '# Background task b1 — output will appear here\n'`(只有 header,没有 `hello-from-pump`),1:1 复刻 #16 报告现象。
- **Rollback**: 单测增量,revert 该文件 hunk 即可。
- **Commits**: `155e4e9b test(bugfix-354): add regression for pump race on bash foreground`

## R2-R3 — 修 shell_runner(C2 绿)

- **Context**: design.md 决策 1/2/3:`_start_pump` 返回 Thread,`_monitor` 三分支统一 join,timeout 10s。
- **Decision**:
  - `_start_pump` 返回 `threading.Thread`,`start()` 保存 `pump_stdout` / `pump_stderr`
  - 新增 `_drain_pumps()` 闭包,统一封装"join 两个 pump + 超时记 warning"
  - 在三条 callback 路径前调用:正常 `exit_code` 分支、`TimeoutExpired` 分支(kill + wait 之后)、通用 `Exception` 分支
  - 顶层加 `_PUMP_JOIN_TIMEOUT_S = 10.0` 常量,带注释说明取值理由(进程退出后 pipe 关闭 → read EOF → 微秒级返回,10s 是 OS 异常硬保底)
  - join 超时不抛、只 `logger.warning`,避免上层永久阻塞,语义退化回修前
- **Rationale**: 决策 1 拒绝 `communicate()`(破坏流式 + 256 MiB OOM 风险) / Event(等价更复杂);决策 3 三分支对称——`_run_foreground` 的 fail 路径同样读 output file,必须一并 join。
- **Evidence**:
  - C1 测试转绿
  - `pytest tests/unit/agent/background_tasks/test_platform_adapters.py` → 15 passed
  - `pytest tests/unit/agent/tools/test_bash_tool.py` → 8 passed
- **Rollback**: `git revert 099d6cbc` 即回退,文件级 diff 仅 ~35 行。
- **Commits**: `099d6cbc fix(bugfix-354): join pump threads before signalling completion`

## R4 — 回填文档 + 收尾

- **Context**: design.md M1 退出标准要求 worker 回填 `fix.md` 的"修复"与"验证"两段。
- **Decision**: 直接写入实际修改文件、commit 列表、修前/修后证据、留给 reviewer 的旅程脚本。
- **Evidence**: `docs/changes/bugfix-354-bash-foreground-output-lost/fix.md` 两段已填实。
- **Commits**: 见 C3 提交。

## Next

- worktree 合回 unit 集成分支,删除 milestone 分支与 worktree
- 由 orchestrator 派 reviewer 走 Gateway + IM 真实旅程验收
