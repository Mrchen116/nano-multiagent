# M108 — REPL 粘贴与退出语义修复

## Plan Notes
- 遵守 `LOGBOOK.md` 中与 CLI 边界、REPL run_id/event_id、命令屏障二次复检相关规则。
- 遵守 `COMMENTING_GUIDE.md`：public API/docstring 写契约，注释只写意图/约束。
- 当前测试门禁命令：`PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
- 基线说明：派发包中的默认 `tests/coding_cli` 路径在本仓不存在，已记录为 baseline 偏差；后续统一使用 focused test 命令。

### R1 输入聚合：多行粘贴应作为一次用户输入提交
- Context: managed/async REPL 的 raw 输入把粘贴中的换行直接当提交键，导致一段多行文本被拆成多条请求；同时不能破坏普通 Enter 提交与 slash 菜单语义。
- Decision: 在 `repl_input.read_interactive_line` 增加 pasted-newline token 识别；真实终端读键时把连续换行批次折叠成单个 paste token，再由输入层一次性写入 chars，后续用额外 Enter 结束该逻辑输入。
- Rationale: 只在输入层识别 paste，保持 `commands.py` 编排边界稳定；普通编辑/历史/命令菜单仍复用既有状态机，不把粘贴语义扩散到 HTTP/渲染层。
- Evidence:
  - Tests: `PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
  - Entry: scripted REPL 粘贴 `first\nsecond` 时，仅产生一次 async send，assistant/history 都保留换行文本。
- Rollback: `5ce6fb2`（R1 红测提交）
- Commits: C1=`5ce6fb2`, C2=`1c96feb`, C3=
- Next: 写 `/exit` 清队红测，确保退出先止收止派再关闭 managed 子进程

### R2 退出语义：/exit 立即止收止派并清队
- Context: `/exit` 旧语义会把“是否退出”绑定到 backlog 自然排空，导致退出卡住；而直接 close 整个队列又会误伤当前 FIFO 头部尚未开始但应视作 active candidate 的收尾，造成单条消息输出丢失。
- Decision: 退出路径改为只在 `/exit` 上调用 `run_queue.close(..., discard_pending=True)`，并在 `ReplRunQueue.close` 中区分“当前 active”与“FIFO 头部 active candidate”：若 worker 尚未抢到第一项但退出已发生，则保留队首、仅丢弃其后的 queued backlog；非 `/exit` barrier 仍保持原有 wait-for-drain 语义。
- Rationale: 这样既满足 SPEC 的“退出时清理队列、managed 模式关闭子进程”，又保住当前正在收尾或已经获得执行权的 run，不把 `/exit` 扩散成普通命令/历史回放的全局语义改变。
- Evidence:
  - Tests: `PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q` => `113 passed`
  - Entry: `/new -> first -> second -> /exit` 时，仅保留 first 的收尾输出，second 不再继续派发；managed 模式仍触发 stop。
- Rollback: `2b17b52`（R2 红测提交）
- Commits: C1=`2b17b52`, C2=待补, C3=待补
- Next: 更新 dev-tasks/merge 回 main，并清理 `.worktrees/M108`
