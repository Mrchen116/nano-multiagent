# bugfix-417-M2 — Progress

> 实施说明：R1（进程组隔离 + killpg）与 R2（非阻塞 drain）是同一文件
> `bash_runner.py` 上三处**协同**改动——killpg 杀掉持写端的孤儿后，非阻塞 drain
> 才能立即见 EOF；非阻塞 drain 又是「即便仍有孤儿持写端」的最终兜底。拆成两次
> 独立提交会让中间态不自洽（只 killpg 不改 drain，正常路径仍阻塞读 EOF；只改
> drain 不 killpg，孤儿仍残留）。故两个 roadpoint 在一次 C1→C2 内一并落地，
> 下面合并记录。

## R1+R2 — 进程组隔离 + killpg 杀整组 + 非阻塞 drain

- Context: bugfix-417 C 层根因（incident #110 / design 决策 6）。现状
  `bash_runner.run_stream`：① `Popen` 无 `start_new_session`，子 bash 不独立成组；
  ② 超时/KeyboardInterrupt 用 `process.kill()` 只 SIGKILL 直接子 bash，`npm run build`
  的 node/vite/tsc 孙进程被孤儿化、继续持 stdout 写端；③ 收尾 `process.stdout.read()`
  阻塞读，孤儿持写端则永等不到 EOF → 承载 tool.run() 的执行线程挂死（事故链中
  A 层 session 锁的最初持有者卡住的直接原因）。

- Decision: 单文件三处改动：
  1. `Popen(..., start_new_session=True)` —— 子 bash 成进程组/会话 leader（pgid==pid），
     派生孙进程同属该组。
  2. 抽 `_kill_process_group(process)`：`os.killpg(pgid, SIGTERM)` 宽限
     `_PROCESS_GROUP_TERM_GRACE=2.0s`（轮询进程退出）后升级 `SIGKILL`，杀整棵进程树；
     超时（循环内）与 KeyboardInterrupt 两处原 `process.kill()` 均替换为它。幂等容错：
     进程已退/组不存在时 `getpgid` 抛 `ProcessLookupError` 静默跳过。
  3. 抽 `_drain_nonblocking(stream)`：把 fd 切非阻塞，循环 `os.read`，EOF 即收尾、
     EAGAIN 用 selector 等下一次可读、总时限 `_DRAIN_TIMEOUT=2.0s` 兜底，替换阻塞
     `process.stdout.read()`，保证执行线程必然解封。

- Rationale: 直击三处根因，最小改动。SIGTERM 先于 SIGKILL 给子进程 flush/善后窗口
  （决策 6 风险条要求）；宽限期 2s « 任何工具 timeout，不影响超时及时性。
  非阻塞 drain 在正常路径（进程已退、写端已关）下同样读尽残余 + 见 EOF，行为与原
  阻塞读等价；仅在孤儿持写端的异常路径下用超时兜底解封——不改回显/截断语义。
  selector 实时回显主循环完全不动（保住 feat-414/bugfix-354 前台流式输出）。

- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/builtins/test_bash_runner.py` 12 passed
    （含新增 3：独立进程组 / 超时杀孙进程 / 孤儿持写端 drain 不挂死）。红测态总耗时
    14s（drain 挂死复现 8s），修复后 2.23s（drain 立即返回）。
  - Entry: 经 **真实 `BashTool.run`**（非 mock 入口）跑 `sleep 30 & wait`（派生孙进程的
    npm-build 类命令）+ timeout=1：1.06s 内以 `ToolError: Command timed out after 1
    seconds` 失败（修复前会挂 30s 等孙进程退出），孙进程 `alive_after_timeout=False`
    被整组回收无孤儿残留。即 Req D（派生子进程命令超时干净收尾、会话可继续）的入口投影。
  - Frontend State Matrix: N/A（纯后端工具执行层）
  - Browser QA: N/A
  - E2E/Regression: bash 回归门禁 `integration/test_tools_bash_integration.py`（流式落盘 +
    SIGTERM 信号细节）+ `contract/test_tools_bash_contract.py` + `unit/agent/tools/test_bash_tool.py`
    + `unit/agent/platform/tools/test_safety.py` + `unit/test_tools_builtins.py` 共 **39 passed**
    —— 回显/信号/截断语义不破。
  - Visual/Interaction: N/A
- Rollback: `git revert 73b47250`（C2 实现）回退到合作式 `process.kill()` + 阻塞 drain
  现状；测试 `git revert 490dcbf2`。本 milestone 单文件，独立可回退（design 风险表）。
- Commits: C1=490dcbf2, C2=73b47250, C3=<本提交>
- Next: 本 milestone 已完成，走 §6 集成到 unit/bugfix-417。
