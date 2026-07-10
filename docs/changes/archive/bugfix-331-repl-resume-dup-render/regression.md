# Regression Verification: Bugfix-331

## 修复范围

本次最终落地的修复包含 4 个点：

1. TTY 已完成输出改成 append-only，避免后一轮覆盖前一轮
2. `--resume` 启动时把历史稳定地渲染成一个 block
3. async turn 在 `assistant/tool/assistant` 交错时按真实事件顺序渲染
4. `turn_end` 之后 replay 的工具事件被截断，不再污染最终 summary

---

## 自动化验证

执行命令：

```bash
uv run pytest \
  tests/unit/test_cli_main.py \
  tests/unit/test_repl_summary.py \
  tests/e2e/test_cli_text_streaming_and_injection_e2e.py \
  -q
```

结果：

```text
109 passed
```

### 本次新增/更新的关键约束

- `emit_persistent_text()` 不允许清除已完成 block
- `resume` 历史仍然只发出一个稳定 block
- `assistant/tool/assistant` 回合必须生成 `ordered_updates`
- `turn_end` 后 replay 的 `tool_start/tool_end` 必须被忽略
- ordered rendering 已经输出工具行时，summary 末尾不能再重复打印同一工具结果

---

## 真实测试

## 真实测试 1：真实 managed 后端 + 真实模型 + TTY 渲染路径

方法：

- 启动新的 managed 端口
- 通过真实 `ServerClient` 发送消息
- 走与 TTY 一致的 `_send_message_from_repl(..., out=TTY-like stream)` 路径
- 对最终 `print_repl_turn_summary()` 输出做顺序检查

本次真实结果满足：

1. `Assistant: Let's first check ...`
2. `Tool: bash output=...`
3. `Assistant: Now let's read ...`
4. `Tool: read output=...`
5. `Assistant: I've read the README ...`
6. `State: completed | stop=stop`

且同时满足：

- 没有 `Tool: bash start`
- 没有 `Tool: read start`
- 没有重复 `Tool: read output`

## 真实测试 2：真实 CLI 进程 + 真 PTY

执行命令（示例端口）：

```bash
PYTHONPATH=src ./.venv/bin/python3 -m coding_cli.main \
  --mode managed \
  --base-url http://127.0.0.1:54237 \
  --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

输入：

```text
Look at the readme.
```

真实 PTY 输出确认：

- 先出现 assistant 第一段说明
- 再出现 `Tool: bash output=...`
- 再出现 assistant 第二段说明
- 再出现 `Tool: read output=...`
- 最后出现 assistant 总结
- `State:` 之前不再有 replay 的工具尾巴

这条验证是最终验收标准。

---

## 修复后不再出现的错误表现

以下现象在真实测试中已消失：

- 第二轮 assistant 覆盖第一轮 assistant
- `assistant/tool/assistant` 被压扁成 “整段 assistant + 工具摘要”
- `turn_end` 之后再次出现 `Tool: ... start/output`
- 同一 `Tool: read output=...` 在同一回合中重复打印

---

## Verdict

Bugfix-331 当前结论：

- 代码路径已修复
- 自动化测试通过
- 真实 managed + 真实模型 + 真实 PTY 验收通过

该 bugfix 可关闭。
