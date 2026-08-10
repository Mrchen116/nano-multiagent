# Incident: REPL resume 显示异常 + TTY 渲染错序/重复

## 摘要

Bugfix-331 最终确认有两类用户可见问题：

1. `--resume` 进入 REPL 后，历史展示与用户感知不一致
2. TTY 下 assistant/tool 混合回合的终端渲染不稳定，表现为：
   - 下一轮覆盖上一轮
   - 同一轮里工具行顺序错乱
   - `turn_end` 之后 replay 的工具事件被重复打印

本次问题的判据最终不是单测，也不是 `termwright`，而是 **真实 shell + 真实 PTY + 真实模型调用**。

---

## 用户可见现象

### 现象 1：`--resume` 后历史展示不稳定

早期实现里，resume 时要么不打印历史，要么只打印一部分，要么格式与真实会话链路不一致。

用户感知是：

- session 明明还在
- 模型上下文里也已经加载了历史
- 但终端里看到的恢复内容缺失或不完整

### 现象 2：第二轮可能覆盖第一轮

真实会话中，第一轮 assistant 已经输出完成；到第二轮完成时，终端又把上一轮 assistant block 擦掉，只留下第二轮内容。

这不是 `jsonl` 顺序错，而是 **终端把“已完成 turn”错误地当成“可重绘 live block”**。

### 现象 3：同一轮里 assistant/tool 顺序错了

真实 `jsonl` 可能是：

1. `assistant`: `Let's check the README...`
2. `tool`: `read`
3. `assistant`: `Okay, I've checked the README!...`

但终端里却会变成：

1. 整段 assistant 总结
2. `Tool: read ...`

也就是把真实的 `assistant -> tool -> assistant` 压成了 “最终 assistant 全文 + 工具摘要”。

### 现象 4：回合末尾工具行重复

修到顺序后，又进一步发现：某些真实 run 在 `turn_end` 和 `run_status=completed` 之后，还会 replay 一遍 `tool_start/tool_end`。

如果客户端不截断这段尾部 replay，终端就会变成：

- 正文里按顺序已经打印过一遍工具结果
- `State:` 之前又再补打一遍工具行

---

## 最终根因

### 根因 1：已完成 turn 和 live block 共用了同一套“可擦除”状态

代码位于：

- `src/coding_cli/input/repl_input.py`
- `src/coding_cli/commands.py`

旧逻辑的 `emit_external_text()` 会在新输出前，根据 `_LAST_EXTERNAL_TEXT_LINES` 回退并清除上一块多行文本。

这本来只适合：

- 同一轮里的 live preview 更新

但旧实现把下面这些也走了同一路径：

- turn summary
- resume 历史
- 错误块
- queue / injected 提示

结果就是：

- 第二轮完成时会擦掉第一轮完成输出

### 根因 2：summary renderer 丢掉了真实事件顺序

代码位于：

- `src/coding_cli/render/repl_render.py`
- `src/coding_cli/render/repl_summary.py`

旧逻辑是：

1. 先打印最终 assistant 文本
2. 再打印 `_repl_view.tool_updates`

这会把真实的：

- `assistant -> tool -> assistant`

渲染成：

- `assistant(合并后的全文) -> tool`

顺序天然错误。

### 根因 3：真实事件流在 `turn_end` 之后 replay 工具事件

代码位于：

- `src/coding_cli/events/repl_events.py`

真实 managed server + 真实模型调用下，事件流可观察到：

1. `text_delta`
2. `tool_start/tool_end`
3. `text_delta`
4. `turn_end`
5. `run_status=completed`
6. **再次出现 `tool_start/tool_end` replay**

如果客户端继续把第 6 步收进 summary，就会在回合末尾重复打印工具行。

这一步是通过真实事件抓取得出的，不是推测。

---

## 修复方案

### 修复 1：把已完成输出改成 append-only

新增：

- `repl_input.emit_persistent_text()`

策略：

- live 可重绘块仍然可以替换上一块
- 已完成 turn、resume 历史、错误块、退出块改成 append-only
- append-only 输出后清空 `_LAST_EXTERNAL_TEXT_LINES`

效果：

- 第二轮不会再擦掉第一轮

### 修复 2：保留按真实事件顺序生成的 `ordered_updates`

在 async 事件聚合阶段新增：

- `_repl_view.ordered_updates`

它保留的是按真实事件顺序整理出的块，例如：

1. `assistant`
2. `tool`
3. `assistant`
4. `tool`
5. `assistant`

渲染时优先按这个顺序输出，而不是只看最终 assistant 文本。

### 修复 3：只在真的存在交错回合时启用 ordered path

不是所有回合都需要 ordered rendering。

本次策略是：

- 只有在出现 `assistant/tool/assistant` 交错时，才启用 ordered path
- 普通单段 assistant 回合仍走原来的紧凑 summary 路径

这样避免把其他成熟路径一起扰动。

### 修复 4：在 `turn_end` 后截断 replay 的非状态事件

新增逻辑：

- 遇到当前 run 的 `turn_end` 后
- 后续只允许 `run_status`
- 丢弃 replay 的 `tool_start/tool_end/...`

效果：

- 回合末尾不再二次打印工具行

---

## 最终结果

修复后，真实 TTY 下的目标顺序变成：

1. `Assistant: Let's check ...`
2. `Tool: bash output=...`
3. `Assistant: Now let's read ...`
4. `Tool: read output=...`
5. `Assistant: I've read the README ...`
6. `State: completed | stop=stop`

并满足：

- 第二轮不覆盖第一轮
- `resume` 历史按稳定 block 恢复
- `turn_end` 后无 replay 工具行
- 同一工具结果不重复打印

---

## 经验教训

这次最重要的教训有三条：

1. `jsonl` 顺序正确，不代表用户终端看到的顺序正确
2. `termwright` 只能做辅助回归，不能替代真实 PTY 验收
3. 终端渲染问题必须把“live block”和“已完成历史块”分开建模，不能共用擦除状态
