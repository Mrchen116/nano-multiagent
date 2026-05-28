# bugfix-354: bash 前台短命令输出丢失

## Relations

- Closes: #16

## 原始报告

> bash 每次都返回空字符串，不是被拦截而是实际上看不到文件。
>
> agent 执行 `bash ls /tmp/sandbox-alpha/` 时返回空输出，导致 LLM 得出错误结论（"目录是空的"）。IM 中查看 tool_call result 字段，三次 bash 调用（包括 `ls -la`、`ls -la && find`、`ls -la 2>&1`）全部返回空字符串。目录实际有文件（README.md、notes.txt）。

## 现象 / 复现

**触发条件**：Agent 在 Gateway 模式下（`_wiring is not None`，走 `_run_foreground` 路径）执行短命令（`ls`、`cat`、`echo`、`grep` 等毫秒级完成的命令）。

**现象**：工具状态返回 `completed`，但 `stdout` 字段为空字符串 `""`，agent 得不到任何命令输出，进而产生错误推断。

**复现步骤**：

1. 启动 Gateway（有 wiring，`_run_foreground` 生效）
2. 向 agent 发送消息，让其执行 `bash ls /tmp/<任意有文件的目录>`
3. 观察 IM 中该 tool_call 的 `result` 字段 → 为 `{}`（空），LLM 回复"目录为空"

**注意**：`rm` 等无输出命令同样返回空，但不产生可见问题；`ls` 有输出却为空，暴露了 bug。

## 根因

### 直接原因：`_monitor` 未等 pump 线程写完即触发 `on_complete`

`shell_runner.py` 的 `start()` 方法启动三个线程：

```
Thread A (_monitor): process.wait() → 进程退出后调用 on_complete/on_fail
Thread B (_pump stdout): 持续 read(4096) stdout pipe → output.append(...)
Thread C (_pump stderr): 持续 read(4096) stderr pipe → output.append(...)
```

问题出在 `_monitor`（第 57–89 行）：`process.wait()` 返回后**立即**调用 `on_complete`，没有等 B、C 线程把管道缓冲区里的剩余字节写入 output file。

`_run_foreground`（`bash.py` 第 267 行）在 `completed_event.wait()` 解除阻塞后立即调用 `_read_output_file(output_file)`，此时 B、C 线程极大概率还没完成最后一次 `output.append()`，文件内容为空（只有初始 header 行）。

竞态窗口图：

```
Thread A: process.wait() 返回 → on_complete() → completed_event.set()
Main:                                              ← 立刻被唤醒 → _read_output_file() → ""
Thread B:   read(4096)=b"total 8\n..."  → output.append(...)   ← 太晚
Thread C:   read(4096)=b""  → 退出                              ← 太晚
```

对 `ls /tmp/sandbox-alpha/` 这类几十毫秒完成、输出几百字节的命令，进程退出和 pump 写完几乎同时发生，竞态必然触发。

### 为何现有测试未捕获

`test_shell_runner_completes_with_exit_0`（`test_platform_adapters.py:186`）在 `runner.start()` 后 `time.sleep(0.5)`，再断言文件内容。0.5 秒足以让 pump 线程写完，绕过了竞态窗口。该测试验证的是"pump 最终写完了"，而非"on_complete 触发时输出已就绪"，漏掉了真正的时序约束。

### 为何能进来

`ShellRunner` 的设计把"进程退出"和"输出写完"当作同一事件处理。`subprocess.Popen.wait()` 只保证进程退出，不保证 pipe 缓冲区被读完。这是一个隐含的"进程退出 ≈ 输出就绪"假设，没有在接口或注释中体现，review 时没有触发怀疑。

## 修复

`src/agent/platform/background_tasks/shell_runner.py`:

- `_start_pump` 改为返回 `threading.Thread`,`start()` 保存两个 pump 句柄
- 新增 `_drain_pumps()`,统一在三条 callback 触发分支(正常退出 / `TimeoutExpired` / 通用 `Exception`)前 join pump,timeout 10s
- join 超时不抛错(避免上层永久阻塞),只记 warning,语义退化到修复前
- 模块顶加 `logger` + 常量 `_PUMP_JOIN_TIMEOUT_S = 10.0`,带注释说明取值理由

`tests/unit/agent/background_tasks/test_platform_adapters.py`:

- 新增 `test_shell_runner_output_ready_when_complete_callback_fires`,通过包装 `BashFileOutput.append` 注入 0.3s 延迟把竞态窗口拉到确定级,在 `on_complete` 内无 sleep 直接断言 output file 已含命令输出

Commits(unit branch `unit/bugfix-354-bash-foreground-output-lost`):

- `155e4e9b` test(bugfix-354): add regression for pump race on bash foreground
- `099d6cbc` fix(bugfix-354): join pump threads before signalling completion

## 验证

**修前(C1 单测)**:`test_shell_runner_output_ready_when_complete_callback_fires` 确定性失败,`on_complete` 读到的内容只有 BashFileOutput header(`# Background task b1 — output will appear here\n`),没有命令输出 `hello-from-pump` —— 1:1 复刻 #16 报告中"`ls /tmp/...` 返回空字符串"的现象。

**修后(C2)**:同测试通过;`test_platform_adapters.py` 15/15 全绿,包括既有的 timeout / stop / nonzero-exit 路径;`test_bash_tool.py` 8/8 全绿,无回归。

**Reviewer 旅程**(留待 reviewer 在 Gateway + IM 中验证):
1. 启动 Gateway + IM
2. 让 agent 执行 `bash ls <有文件的目录>`
3. 期望:IM 的 tool_call result 字段返回真实文件列表,不再是空字符串
