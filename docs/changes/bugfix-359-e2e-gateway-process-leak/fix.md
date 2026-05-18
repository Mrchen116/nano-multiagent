# bugfix-359: e2e 测试泄漏 Gateway/kernel 进程

## Relations

- Related: #23

## 原始报告

> 以及为啥每次agent写完代码，pytest都会留下一堆僵尸进程？这是pytest的问题吗

调查现场(2026-05-19 07:36 排查 stuck chat 时发现):

```
$ ps aux | grep personal_assistant.main | grep -v grep
czj  67791 ... personal_assistant.main --config /private/var/folders/.../pytest-of-czj/pytest-65/test_main_default_command_retu0/node-config.yaml --foreground
czj  67811 ... personal_assistant.main --config /private/var/folders/.../pytest-of-czj/pytest-65/test_main_stop_command_reports0/node-config.yaml --foreground
... (共 12 个,6 对 Gateway + kernel,最早活了 12+ 小时)
```

每对都是:`personal_assistant.main --foreground`(Gateway 后台子进程)+ 对应的 `uvicorn personal_assistant.kernel_app`,配置路径全部命中 `pytest-of-czj/pytest-NN/test_main_*` 目录。

伴随 GitHub issue #23 已立。

## 澄清记录

- Q1: 「成功修复」长什么样,以哪种验证为准?
  A(原话): ok
  Agent 解读: 采纳推荐 —— 跑完 `tests/e2e/test_personal_assistant_main_e2e.py`(含异常路径:Ctrl-C 中断 / 超时打断 / assert 失败)后,机器上不留任何 cmdline 含 `pytest-of-<user>/pytest-NN/` 的 `personal_assistant.main` 或 `kernel_app` 进程。

- Q2: 修复范围只到「e2e 测试不漏」还是顺手扩到「手工跑 `personal_assistant.main` 异常崩溃也不留 kernel 子进程」?
  A(原话): 对
  Agent 解读: 采纳推荐 —— 只到 e2e 不漏。运行时进程生命周期健壮性(用户手工 `kill -9` 父进程的兜底)留给单独 issue。本 unit 改动可能顺带让运行时受益(若 `os.setsid` 落到了 `personal_assistant.main`),但不作为本 unit 的验收目标。

- Q3: conftest 兜底强杀时打印告警还是静默清理?
  A(原话): ok
  Agent 解读: 采纳推荐 —— 打印告警。每个被强杀的进程输出 `WARN: pytest finalizer killed leaked process: pid=<pid> cmdline=<...>`。预期修完后 0 告警,有告警就是真问题(测试本身回收失败)。

## 现象 / 复现

跑 `tests/e2e/test_personal_assistant_main_e2e.py` 后(尤其在测试因超时 / assert 失败 / Ctrl-C 中断时),机器上残留成对的 `personal_assistant.main --foreground` + `uvicorn personal_assistant.kernel_app` 进程,cmdline 命中 `pytest-of-<user>/pytest-NN/test_main_*/node-config.yaml`。

这些僵尸:

- 持续占随机端口(`--host 127.0.0.1 --port <N>`),下次跑测可能抢同 port 失败
- 用 `monkeypatch.setenv("HOME", tmp_path)` 起的,但配置文件路径已被 pytest tmpdir 清理 → 进程内部还在 reload 配置时会写错地方
- 同 user 下还会去连真实的 IM 服务(`http://127.0.0.1:8011`),和真 Gateway 抢注册同名 agent,扰乱真实运行环境

复现路径:`pytest tests/e2e/test_personal_assistant_main_e2e.py::test_main_default_command_returns_after_background_start`,人工 Ctrl-C 打断,或把 `_wait_for_health` 的 URL 改成不可达让它 timeout,跑完 `ps aux | grep personal_assistant.main` 仍能看到泄漏进程。

## 根因

三层都有问题,详见 GitHub issue #23,概括:

1. **PID 通过 stdout 解析**:`tests/e2e/test_personal_assistant_main_e2e.py` 模式是
   ```python
   completed = subprocess.run(_main_command(config_path), timeout=20)
   pid = _parse_started_pid(completed.stdout)
   try: _wait_for_health(...)
   finally: _terminate_background_pid(pid)
   ```
   一旦 `subprocess.run` 超时或前置失败,已经 daemonize 的 Gateway 子进程没人记得 PID,finally 也没 fallback。

2. **`personal_assistant.main` 后台模式没用进程组**:父进程 re-exec 一个 `--foreground` 子进程后退出。子进程又 `Popen` 了 `uvicorn kernel_app`,没 `os.setsid()`,SIGTERM 只杀 Gateway 父,kernel 子进程不跟着死(僵尸列表里每个测试 dir 都同时留 Gateway + kernel,即证)。

3. **e2e 套没有 session-scoped finalizer 兜底**:conftest 没有在 session teardown 时按 `pytest-of-<user>/pytest-NN/` cmdline 兜底强杀残留进程的机制。前两层任何一层漏,这里也接不住。

## 修复

<!-- 实施后补 -->

## 验证

<!-- 实施后补 -->
