# 反向追根因(Root Cause Tracing)

## 这是什么

bug 经常**显现在调用栈很深的地方**(在错误目录 `git init`、文件写到错误位置、用错路径打开了数据库)。你的本能是"在报错的地方修",但那是治症状。

> **核心:沿调用链反向往上追,直到找到最初的触发点,在源头修。**

## 什么时候用

- 错误发生在执行的深处,不是入口;
- stack trace 显示一条很长的调用链;
- 不清楚非法数据最初从哪来;
- 要找出是哪个测试 / 哪段代码触发了问题。

## 追踪流程

**1. 观察症状**
```
Error: git init failed in ~/project/packages/core   # 不该在源码目录建 .git
```

**2. 找直接原因**——什么代码直接导致它?
```python
subprocess.run(["git", "init"], cwd=project_dir)
```

**3. 问:谁调了这个?** 一层层往上列调用链
```
WorktreeManager.create_session_worktree(project_dir, session_id)
  ← Session.initialize_workspace()
  ← Session.create()
  ← 测试在 Project.create() 处调起
```

**4. 继续往上——传进来的值是什么?**
- `project_dir = ""`(空串!)
- 空串作为 `cwd` 会落到 `os.getcwd()`
- 那正是源码目录!

**5. 找到最初触发点——空串哪来的?**
```python
ctx = setup_core_test()          # 返回 {"tmp_dir": ""}
Project.create("name", ctx.tmp_dir)   # 在 fixture 初始化之前就被访问了!
```

**根因**:顶层变量在 fixture 就绪前被访问,拿到空值。**修法**:把 `tmp_dir` 改成"未就绪就 raise"的属性,而不是在 `git init` 那行加判断。

## 手动追不动时:加诊断打印栈

```python
import traceback, os
def git_init(directory: str):
    print(f"DEBUG git init: dir={directory!r} cwd={os.getcwd()!r}", file=sys.stderr)
    traceback.print_stack(file=sys.stderr)   # 打完整调用栈
    subprocess.run(["git", "init"], cwd=directory)
```

要点:
- **在危险操作之前**打,不是等它失败之后;
- 测试里用 `stderr`(logger 可能被吞);
- 带上下文:目录、cwd、相关环境变量、时间戳;
- `traceback` 给出完整调用链。

跑并抓取:
```bash
pytest 2>&1 | grep 'DEBUG git init'
```
分析栈:找测试文件名、找触发那一行的行号、找模式(同一个测试?同一个参数?)。

## 找"是哪个测试污染了环境"

某个东西在跑测试时冒出来、但不知道是哪个测试干的 → **二分**:把测试集对半分别跑,缩小到第一个污染者。`pytest -p no:randomly tests/a tests/b ...` 逐批跑,定位首个出问题的文件。

## 关键原则

```
找到直接原因
  └─ 能再往上追一层吗?
       ├─ 能 → 往上追 → 这是源头吗? ──否──┐(继续往上)
       │                          └─是→ 在源头修 → 各层补校验 → bug 变得不可能
       └─ 不能 → ⛔ 绝不只修症状处
```

**绝不只在报错出现的地方修。** 追回最初触发点。找到源头后,通常顺手做一遍 `defense-in-depth`(多层加校验),让同类 bug 结构上不可能再发生。
