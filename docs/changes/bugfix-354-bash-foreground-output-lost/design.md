# bugfix-354: bash 前台短命令输出丢失 — 技术方案

> 对齐: fix.md v1

> Unit branch: `unit/bugfix-354-bash-foreground-output-lost` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

### 涉及范围

| 文件 | 当前职责 | 本 unit 操作 |
|---|---|---|
| `src/agent/platform/background_tasks/shell_runner.py` | 用 `subprocess.Popen` 执行 shell 命令，用两个 pump 线程把 stdout/stderr 流写入 output file，用 monitor 线程监视进程退出 | **主要改动**：让 `_monitor` 在调用 `on_complete`/`on_fail` 前 join pump 线程 |
| `tests/unit/agent/background_tasks/test_platform_adapters.py` | `ShellRunner` 的单元测试（现有 4 个测试都用 `sleep` 规避竞态，未覆盖"callback 触发时输出已就绪"的时序约束） | 新增 1 个回归测试，在 `on_complete` callback 内部（无 sleep）直接断言输出文件已有内容 |

不改动：
- `bash.py`（`_run_foreground` 路径无需改，问题在 shell_runner 层）
- `file_output.py`（`BashFileOutput` 逻辑正确，thread-safe append 没问题）
- `interfaces.py`（`BackgroundBashRunner` 协议定义无需变更）

### 既有约束

- `ShellRunner` 实现 `BackgroundBashRunner` Protocol，接口签名不可破坏
- 改动必须对 background 路径（`_run_background`）保持透明——background 调用者不等 `on_complete`，不受竞态影响，但 join 操作不应引入性能退化
- 测试文件 `test_platform_adapters.py` 中现有测试用 `time.sleep(0.5)` 等待，这些测试应继续通过（不删不改）

### 可复用能力

- `_start_pump` 已经返回的是 `threading.Thread` 启动后的裸线程，只是目前 caller 没有保存引用。**改法**：让 `_start_pump` 返回 `threading.Thread` 对象，`start()` 保存引用，`_monitor` 在 callback 前 join。
- Python `threading.Thread.join(timeout=N)` 原生支持，无需引入新依赖。

### 相关历史

无近期改过 `shell_runner.py` 的 unit。`refactor-353` 改了 `auto_mode_gate.py`，与本 unit 无交集。

---

## 架构总览

### Before（有竞态）

```
subprocess 启动
  ├── Thread B (_pump stdout): read pipe → output.append(...)
  ├── Thread C (_pump stderr): read pipe → output.append(...)
  └── Thread A (_monitor):
        process.wait() 返回
        → on_complete() / on_fail()   ← B、C 还没写完！
              └── completed_event.set()
                    └── 主线程: _read_output_file() → ""（空）
```

### After（join 保证输出就绪）

```
subprocess 启动
  ├── Thread B (_pump stdout): read pipe → output.append(...) → pipe EOF → 退出
  ├── Thread C (_pump stderr): read pipe → output.append(...) → pipe EOF → 退出
  └── Thread A (_monitor):
        process.wait() 返回
        pump_stdout.join(timeout=10)  ← 等 B 写完
        pump_stderr.join(timeout=10)  ← 等 C 写完
        → on_complete() / on_fail()   ← 输出已全部落盘
              └── completed_event.set()
                    └── 主线程: _read_output_file() → "total 8\nREADME.md..."
```

进程退出后 pipe 的 write 端已关闭，pump 的 `stream.read(4096)` 必然很快返回 `b""`，join 的实际等待时间为微秒级。`timeout=10` 是安全网，正常路径不会触达。

---

## 关键决策

### 决策 1：在 `_monitor` 里 join pump 线程，而非改用 `communicate()`

- **选择**：`_start_pump` 改为返回 `threading.Thread`；`_monitor` 在调用 callback 前 `pump_stdout.join(timeout=10); pump_stderr.join(timeout=10)`。
- **理由**：改动最小（约 +8 行），不触动已有的流式写逻辑（`BashFileOutput.append` 支持 256 MiB 输出上限、stderr prefix 等），对 caller 接口零破坏。
- **拒绝 `communicate()`**：`communicate()` 把全部 stdout/stderr 缓存到内存再返回，破坏现有流式写文件架构，且对大输出（上限 256 MiB）有 OOM 风险。
- **拒绝 Event/Barrier 方案**：在语义上等价于 join，但需要额外状态对象，代码复杂度上升，无明显收益。
- **风险**：理论上 pump join 可能因极端情况（pipe 读阻塞）超过 10s 而返回，此时输出文件可能不完整。实际上进程退出后 pipe write 端关闭，read 必定很快 EOF；10s 留量极为充裕。

### 决策 2：join timeout 设为 10 秒

- **选择**：`pump_thread.join(timeout=10.0)`。
- **理由**：进程退出 → pipe EOF → pump `read()` 返回 `b""` → pump 线程退出，这条链路在正常情况下是微秒级。10s 是防止极端情况（OS pipe 缓冲区异常）的硬保底，同时不影响测试速度。
- **拒绝无 timeout**：万一 pump 因 OS 问题卡住，`_monitor` 会永久阻塞，`on_complete` 永不触发，`_run_foreground` 的 120s foreground budget 超时后退化为 `async_launched`，行为退化比崩溃更难调试。
- **拒绝 timeout=0（非阻塞检查）**：等价于不 join，不解决竞态。

### 决策 3：timeout 和 stop 路径也 join pump

- **选择**：`on_fail`（超时 kill / 非零退出 / `stop()` terminate）路径和 `on_complete` 路径对称，都在 callback 前 join pump。
- **理由**：`_run_foreground` 的 fail 路径同样调用 `_read_output_file`（读部分输出展示错误信息），竞态相同。
- **stop 路径特殊处理**：`_stop_task` 调用 `process.terminate()`，进程退出后 `_monitor` 的 `process.wait()` 会返回，随后走正常 join 路径，无需额外处理。

---

## 接口与数据流

### 改动后的 `_start_pump` 签名

```python
# Before
def _start_pump(self, stream, task_id, output, label) -> None:
    ...
    threading.Thread(target=_pump, daemon=True).start()

# After
def _start_pump(self, stream, task_id, output, label) -> threading.Thread:
    ...
    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    return t
```

### 改动后的 `start()` 关键路径（伪代码）

所有触发 callback 的分支（正常退出 / 超时 kill / 通用异常）都必须先 join pump，保持对称：

```python
pump_stdout = self._start_pump(process.stdout, task_id, output, "stdout")
pump_stderr = self._start_pump(process.stderr, task_id, output, "stderr")

def _drain_pumps() -> None:
    """等 pump 把 pipe 余量写完，再让 caller 读 output file。"""
    pump_stdout.join(timeout=10.0)
    pump_stderr.join(timeout=10.0)
    # join 超时不抛错：仍照常触发 callback，避免 caller 永久阻塞；
    # 此时输出可能截断，视为 OS 异常，由实现层记 warning 日志。

def _monitor() -> None:
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
        _drain_pumps()                              # ← timeout 分支也要 join
        on_fail(task_id=..., error=f"timed out ...")
        return
    except Exception as exc:
        _drain_pumps()                              # ← 通用异常分支也要 join
        on_fail(task_id=..., error=str(exc))
        return

    _drain_pumps()                                  # ← 正常退出分支
    if exit_code == 0:
        on_complete(...)
    else:
        on_fail(...)
```

### 回归测试的断言模式（新增）

在 `on_complete` callback 内部（不加 sleep）读 output file，断言已有命令输出：

```python
def on_complete(*, task_id, **_):
    content = path.read_text()
    assert "hello" in content   # 证明 callback 触发时输出已就绪
    completed.append(task_id)
```

---

## 风险与回退

| 风险 | 概率 | 影响 | 应对 |
|---|---|---|---|
| pump join 超过 10s timeout | 极低（需 OS pipe 异常） | 输出文件可能不完整，行为退化为修复前 | **不抛错、仍调用 callback**（避免 caller 永久阻塞），输出截断由调用方按现状处理；worker 实现层须记 warning 日志（含 task_id + label），便于排障；背景任务路径不受影响 |
| 修复引入的 join 在高并发下成为瓶颈 | 极低 | join 等待时间微秒级，实测无影响 | 若出现，可减小 join timeout 或改为非阻塞 try-join + retry |

**回滚**：仅改 `shell_runner.py` 约 8 行，git revert 即可回退，零配置变更，无数据迁移。

---

## Runbook for Reviewer

无常驻服务。本 unit 只改 `ShellRunner`（库代码），由上层 agent 在运行时加载。

reviewer 验收方式：启动 Gateway + IM，向 agent 发送短命令（`ls`、`echo hello`），观察 IM 中 tool_call result 是否有实际输出。

---

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-354-M1 | fix-pump-race | — | A | `src/agent/platform/background_tasks/shell_runner.py`<br>`tests/unit/agent/background_tasks/test_platform_adapters.py`<br>`docs/changes/bugfix-354-bash-foreground-output-lost/fix.md`（回填"修复 / 验证"两节） | `[worker]` `pytest tests/unit/agent/background_tasks/test_platform_adapters.py` 全绿，包含新增回归测试（在 `on_complete` callback 内无 sleep 断言输出就绪）<br>`[worker]` `pytest tests/unit/agent/tools/test_bash_tool.py` 全绿（现有测试不回归）<br>`[worker]` 三条分支（正常退出 / timeout / 通用异常）都 join pump 后再 callback；join 超时不抛错且记 warning 日志<br>`[worker]` 回填 `fix.md` 的"修复"（改了什么 + commit）与"验证"（修前能复现 → 修后不能）章节<br>`[reviewer]` Gateway 模式下 agent 执行 `bash ls <有文件目录>` 返回文件列表，不再返回空字符串 |
