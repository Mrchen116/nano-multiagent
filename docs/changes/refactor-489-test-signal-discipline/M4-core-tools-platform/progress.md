# refactor-489-M4 — Progress

## 启动记录

- Baseline: `unit/refactor-489@8d6cfb3e8`；M4 slice `658 passed, 1 warning`。
- Baseline command: 用 zsh array 选取 `tests/unit/platform` 与排除 M2/M3/M5--M8/M13 语义归属后的 root `tests/unit/test_*.py`，执行 `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q`。
- 调试说明: 首轮命令误用 zsh 特殊参数名 `path`，循环赋值污染 `PATH`，造成 6 个 `bash` 子进程假失败；改用普通变量后同一测试集全绿，确认不是仓库基线缺陷。
- Scope clarification: orchestrator 确认 `tests/unit/test_curator.py` 归 M3、`tests/unit/test_text_runner.py` 归 M8，M4 不修改；跨 slice 替代保护只能引用当前基线已存在且可运行的测试，不能依赖尚未合入结果。

## Promotion Candidates

None.
