# CLI 真实测试指南

## 目的

这份文档说明这次 Bugfix-331 是怎么做“真实 CLI 测试”的，重点回答两个问题：

- 怎么在**真实 PTY / 真实终端控制序列**下复现问题
- 为什么不能只信 `termwright` 或纯 `StringIO` 单测

本次关注的问题：

1. `--resume` 启动 REPL 时，历史恢复是否符合真实用户感知
2. agent 调用工具后，assistant 文本是否在终端里出现重复渲染

---

## 为什么需要“真实测试”

这个问题不是单纯的业务逻辑 bug，而是 **TTY 渲染 + ANSI 控制序列 + 事件重放** 叠加出来的。

只看下面两类测试都不够：

- 纯单元测试：只能证明字符串拼接逻辑，不代表真实终端会怎么显示
- `termwright` 屏幕测试：能看到最终屏幕，但它本身也可能对滚屏、光标移动、清屏序列存在兼容性偏差

这类问题最终必须看：

- 真实 shell
- 真实 PTY
- 真实 CLI 进程输出的原始控制序列

---

## 测试分层

建议把 CLI 测试分成 3 层，可信度从低到高：

### 1. 纯函数 / 假客户端测试

例如：

- `tests/e2e/test_cli_text_streaming_and_injection_e2e.py`
- `tests/unit/test_cli_main.py`
- `tests/unit/test_repl_live.py`

用途：

- 验证 `consume_async_run_events` 的事件消费逻辑
- 验证 `merge_text_delta`、dedupe、summary render 等纯逻辑

局限：

- 没有真实 PTY
- 没有真实 ANSI 清屏 / 上移 / 光标恢复
- 看不到“屏幕上为什么重复”

### 2. `termwright` 屏幕自动化

例如：

- `tests/e2e/termwright_repl_resume_test.sh`

用途：

- 快速回归
- 观察“最终屏幕文本”

局限：

- `termwright` 不是系统终端本身
- 对控制序列的解释可能和真实终端不完全一致
- 测试脚本本身也可能写错断言

本次就发现一个具体问题：现有脚本把 `say hi` 命中了 `hi`，于是把“assistant 回复存在”误判成 `PASS`。这类脚本可以辅助，但不能作为最终结论。

### 3. 真实 PTY 测试

这是这次问题的主判据。

工具：

- `pexpect`

用途：

- 启动真实 shell
- 分配真实 PTY
- 保留 ANSI 控制序列
- 抓取 CLI 原始输出

这层最接近用户实际看到的行为。

---

## 环境要求

建议在仓库根目录执行：

```bash
cd /Users/czj/Repos/nano-multiagent
```

优先使用仓库自己的 Python：

```bash
./.venv/bin/python3
```

不要默认用外层 shell 的 `python3`。我这次就遇到过一个误差：`pexpect` 起的子 shell 没继承你平时交互 shell 的完整环境，结果直接报：

```text
ModuleNotFoundError: No module named 'httpx'
```

所以真实测试时建议显式写全：

```bash
PYTHONPATH=src ./.venv/bin/python3 -m coding_cli.main ...
```

---

## 真实测试方法一：复现 `--resume` 历史恢复

### 目标

验证的不是“有没有任何输出”，而是：

- CLI 是否真的打印了历史
- 打印的是不是完整、合理、用户可理解的历史

### 命令

下面这个脚本会：

1. 用真实 `zsh` 启动 CLI
2. 给它一个已有 session
3. 等待 prompt 出现
4. 抓取从启动到 prompt 的全部 PTY 输出

```bash
python3 - <<'PY'
import pexpect, time

cmd = (
    'cd /Users/czj/Repos/nano-multiagent && '
    'PYTHONPATH=src ./.venv/bin/python3 -m coding_cli.main '
    '--model volcanoArk:doubao-seed-2-0-code-preview-260215 '
    '--resume sess_f9036fd8ddb982f7'
)

child = pexpect.spawn(
    '/bin/zsh',
    ['-lc', cmd],
    encoding='utf-8',
    timeout=120,
    dimensions=(40, 140),
)

transcript = []
start = time.time()
while time.time() - start < 30:
    idx = child.expect(
        [r'\[sess_f9036fd8ddb982f7\]> ', pexpect.TIMEOUT, pexpect.EOF],
        timeout=2,
    )
    transcript.append(child.before)
    if idx == 0:
        transcript.append(child.after)
        break
    if idx == 2:
        transcript.append('<EOF>')
        break

print('---TRANSCRIPT START---')
print(''.join(transcript))
print('---TRANSCRIPT END---')

if child.isalive():
    child.close(force=True)
PY
```

### 本次实际抓到的结果

```text
> hi
Assistant:
Let's start by exploring the repository contents to understand what we're working with.
Assistant:
Let's check the README.md file to understand what this repository is about:
Assistant:
Now let's check the source code structure in src/:
Assistant:
Let's check test_dup.py, which is a file in the repository root that was last modified today:
[sess_f9036fd8ddb982f7]>
```

### 结论

这个结果说明：

- 不是“完全没打印历史”
- 但也不是“完整恢复历史”
- 当前更像是只恢复了最近一部分 message，而且格式也不完整

所以 `resume` 问题不能只写成“完全无历史”，真实说法应该是：

`resume` 历史恢复行为与用户感知不一致，且恢复内容不完整。

---

## 真实测试方法二：复现“工具后重复渲染”

### 为什么要分两步

这个问题要区分两种情况：

1. 不调工具时，是否已经有文本重复
2. 调工具后，重复是否明显恶化

用户这次补充的信息很重要：

> 一般好像是 agent 有调用工具之后才遇到不停重复文字

所以测试要明确覆盖“会调工具”的 prompt。

### 命令

下面这个脚本会：

1. 启动真实 CLI
2. 发 `hihi`
3. 等第一轮结束
4. 再发 `说中文`
5. 抓两轮之间的原始 PTY 输出

```bash
python3 - <<'PY'
import pexpect, time

cmd = (
    'cd /Users/czj/Repos/nano-multiagent && '
    'PYTHONPATH=src ./.venv/bin/python3 -m coding_cli.main '
    '--model volcanoArk:doubao-seed-2-0-code-preview-260215'
)

child = pexpect.spawn(
    '/bin/zsh',
    ['-lc', cmd],
    encoding='utf-8',
    timeout=180,
    dimensions=(45, 160),
)

child.expect('nano> ', timeout=60)
child.sendline('hihi')
child.expect(r'Started new session (sess_[a-f0-9]+)\.', timeout=60)
session_id = child.match.group(1)

end = time.time() + 20
buf1 = ''
while time.time() < end:
    try:
        buf1 += child.read_nonblocking(size=4096, timeout=1)
    except pexpect.TIMEOUT:
        pass
    except pexpect.EOF:
        break

child.sendline('说中文')
end = time.time() + 35
buf2 = ''
while time.time() < end:
    try:
        buf2 += child.read_nonblocking(size=4096, timeout=1)
    except pexpect.TIMEOUT:
        pass
    except pexpect.EOF:
        break

print('SESSION', session_id)
print('---AFTER HIHI---')
print(buf1)
print('---END AFTER HIHI---')
print('---AFTER 中文---')
print(buf2)
print('---END AFTER 中文---')

if child.isalive():
    child.close(force=True)
PY
```

### 本次实际抓到的结果

第一轮，不调工具时已经有重复：

```text
> Hi there! 😊 How can I help you with your project today?
> Hi there! 😊 How can I help you with your project today?
```

第二轮，进入工具流程后明显恶化：

```text
> 好的，没问题！让我先看看你这个项目的结构，了解一下我们在做什么。
> 好的，没问题！让我先看看你这个项目的结构，了解一下我们在做什么。
▸ Tool: bash
...
> 好的，没问题！让我先看看你这个项目的结构，了解一下我们在做什么。好的，没问题！让我先看看 README 了解一下这个项目。
✓ Tool: bash (elapsed=14ms)
...
▸ Tool: read
▸ Tool: read
...
```

### 结论

真实行为不是“只有工具时才重复”，而是：

- 纯文本回复时已经可能重复一次
- 一旦 agent 调工具，重复和重绘残留会显著放大

这和用户体感是一致的，因为真正让人觉得“停不下来”的，一般就是工具阶段。

---

## 为什么 `termwright` 不能当最终证据

`termwright` 仍然有价值，但只能当辅助证据。

原因有两类：

### 1. 工具自身可能有终端仿真偏差

比如：

- 对 `\x1b[A`、`\x1b[2K`、`\x1b[J` 的解释和系统终端不完全一致
- 对滚屏和光标恢复的行为不一致

### 2. 测试脚本本身可能误判

这次就有现成例子：

- `tests/e2e/termwright_repl_resume_test.sh`
- 用 `grep -q "[Hh]i\|[Hh]ello"` 判断“assistant reply 存在”

这会把用户输入 `say hi` 误判成 assistant 的 `hi`。

所以结论应该是：

- `termwright` 适合做快速回归
- 真实 PTY 才适合做问题定性和验收

---

## 推荐测试流程

建议以后按这个顺序做：

1. 先跑纯逻辑单测，确认事件消费和 dedupe 没写错
2. 再跑 `termwright` 做快速回归，观察最终屏幕
3. 最后用 `pexpect` 跑真实 PTY，抓原始输出定性

如果问题涉及下面任一项，必须做第 3 步：

- ANSI 清屏
- 多行重绘
- 光标上移
- rich live render
- “用户说屏幕看起来不对”

---

## 编写真实 CLI 测试时的注意事项

### 1. 显式指定解释器

用：

```bash
PYTHONPATH=src ./.venv/bin/python3 -m coding_cli.main ...
```

不要偷懒写成：

```bash
PYTHONPATH=src python3 -m coding_cli.main ...
```

因为 `pexpect` 子 shell 的环境可能和你当前交互 shell 不同。

### 2. 显式指定 shell

建议直接指定：

```python
pexpect.spawn('/bin/zsh', ['-lc', cmd], ...)
```

这样更接近用户实际执行环境。

### 3. 固定终端尺寸

建议给 `dimensions=(rows, cols)`，否则换行位置会漂移，复现结果不稳定。

### 4. 保留原始控制序列

不要一开始就把 ANSI 全部清洗掉。先保留原始输出，必要时再做二次分析。

### 5. 断言不要写得太“聪明”

避免这种模糊断言：

```bash
grep -q "hi"
```

应该尽量断言：

- 明确的 `Assistant:` 块
- 明确的工具行
- 明确的 session prompt
- 或直接比较抓到的原始 transcript 片段

---

## 建议的后续沉淀

后续可以把这份手工流程再固化成一个仓库脚本，例如：

- `scripts/repro_cli_resume_realpty.py`
- `scripts/repro_cli_dup_render_realpty.py`

目标不是替代人工判断，而是：

- 稳定生成真实 PTY transcript
- 让 review / 回归时能直接复跑

---

## 结论

这次 CLI 问题的有效复现，最终依赖的是 `pexpect + 真实 shell + 真实 PTY`，不是 `termwright`，也不是纯单测。

对这类终端渲染问题，仓库里以后应该默认采用这个判断标准：

- 逻辑正确性看单测
- 快速回归看 `termwright`
- 最终定性和验收看真实 PTY
