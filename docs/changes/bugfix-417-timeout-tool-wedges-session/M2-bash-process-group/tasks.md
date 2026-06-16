# bugfix-417-M2: bash-process-group — Tasks

> 对齐: ../design.md（决策 6，C 层）

## 目标

bash 工具超时/中断时连同**派生子进程树**一起回收，执行线程不再因孤儿持写端的阻塞 drain 而挂死。外部可观察：跑 `npm run build` / `bash -c 'sleep 200 & wait'` 这类会派生子进程的命令到 `timeout` 时，在 timeout 附近以 timeout 终态失败、无孤儿进程残留、执行线程及时返回（不无限等待）。

## 退出标准

- [x] `Popen(..., start_new_session=True)` 起独立进程组
- [x] 超时 / KeyboardInterrupt 时 `os.killpg(os.getpgid(pid), SIGTERM)` 宽限后 `SIGKILL` 杀整组（不再只 `process.kill()` 杀直接子）
- [x] 收尾 drain 改带超时/非阻塞读，孤儿持写端时执行线程必然解封、不挂死
- [x] 超时后无孤儿子进程残留的回归测试全绿
- [x] feat-414/bugfix-354 前台流式回显语义不破（selector 实时 chunk 事件保留）

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  1. 派生子进程的命令超时 → 整个进程组被杀、子进程不残留
  2. 派生子进程持 stdout 写端的命令超时 → 执行线程在合理时间内返回（drain 不挂死）
  3. 进程组隔离（子 bash 在独立 session/进程组里）
  4. 既有流式回显 / 正常退出 / 失败退出 / 信号细节语义不变（回归）
- 已有测试在：`tests/unit/agent/platform/tools/builtins/test_bash_runner.py`（扩展，加进程组/孤儿回收 case）；信号/回显回归已在 `tests/integration/test_tools_bash_integration.py`（不改，跑通即回归）
- 落层/目录/marker：tests/unit/（真起子进程，无 mock 入口，无 e2e marker）
- 可选依赖 importorskip：无（POSIX 内置 os/signal）
- 本 milestone 产生的一次性验收证据：手动跑 `bash -c 'sleep 200 & wait'` timeout 后 `ps` 验证无残留（记 progress，不进套件）

前端：N/A（纯后端工具执行层）

## Roadpoints

| ID | 描述 | 状态 |
|---|---|---|
| R1 | 进程组隔离（`start_new_session=True`）+ 超时/中断 killpg 杀整组（SIGTERM 宽限 → SIGKILL） | DONE |
| R2 | 收尾 drain 改非阻塞/带超时读，杜绝孤儿持写端致执行线程挂死 | DONE |
