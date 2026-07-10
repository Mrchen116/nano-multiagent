# Bugfix 339: REPL SSE Streaming 渲染缺陷

## 现象

在 feat-338（Kernel Message SSE）集成到 Coding CLI REPL 后，交互式终端输出出现 5 个关联缺陷：

1. **批量输出而非流式**：所有事件在运行结束后一次性输出，用户看不到实时进度。
2. **中间 assistant 消息丢失**：多 turn agent loop 中，只有最后一个 LLM turn 的文本被显示，中间的思考/分析文本全部丢失。
3. **文字与工具行分组堆叠**：assistant text 被集中到一块，tool 标记被集中到另一块，不反映真实的时序穿插关系。
4. **Rich Live 光标跟踪损坏**：当 assistant text 长度从几行增长到超过终端高度时，Rich 的 in-place cursor tracking 失效，导致部分行失去 `> ` 前缀或内容重复。
5. **尾部空行污染**：每个 `assistant_message` 事件的内容末尾换行符被拆分为空字符串，打印出孤立的 `> ` 行。

## 复现步骤

在 TTY 终端执行：

```bash
PYTHONPATH=src python3 -m coding_cli.main --mode managed
# 输入一个会触发多 turn + 多工具的消息
> 看看agent loop代码
```

观察输出：
- 所有内容在运行结束后一次性出现
- 中间文本如"先看看项目结构""让我查看完整目录"等消失
- 工具标记全部集中在底部，不与文字穿插
- 出现大量只有 `> ` 的空行

## 根因分析（RCA）

### 根本原因 1：事件收集后再渲染

`_send_message_via_sse` 的 TTY 分支：

```python
with renderer:
    events = reader.drain_run(...)          # ← 先全部收集
    for event in events:                     # ← 运行结束后再遍历
        ...
```

`drain_run` 是阻塞式的：它持续 poll SSE 事件队列直到看到 terminal `run_status`。原始代码在 `with renderer` 上下文内调用 `drain_run`、拿到完整列表后才遍历渲染。这意味着整个运行期间终端只显示一个 static spinner，运行结束后才一次性更新所有内容。

### 根本原因 2：`on_text_delta` 的 merge 语义不适合完整消息

原始 TTY 分支对每个 `assistant_message` 调用 `renderer.on_text_delta(content)`。该方法的实现是：

```python
merged = merge_text_delta(self._assistant_text, delta)
self._assistant_text = merged
```

`merge_text_delta` 会把新内容拼接到旧内容后面。对于多个独立的 `assistant_message`（每个代表一个完整 LLM turn），这会把 turn 1、turn 2、turn N 的文本全部拼接成一段超长文本，完全丢失了 turn 边界。

### 根本原因 3：Rich Live 的架构限制

`rich.live.Live` 维护一个单一的 renderable 对象，它在终端底部原地更新。这个设计对于"一个固定高度的状态面板"很好，但对于"不断增长的多行文本 + 穿插的工具标记"完全不合适：

- 当文本行数超过终端高度时，Rich 的光标跟踪算法（基于 ANSI escape 序列控制光标位置）会失效，导致内容错位、前缀丢失。
- 工具标记被固定在 live area 的底部，所有文字在上方滚动，两者无法按真实时序穿插。

### 根本原因 4：未处理尾部换行

```python
for line in content.split("\n"):
    print(f"> {line}", file=out)
```

当 `content = "让我查看目录。\n"` 时，`split("\n")` 得到 `["让我查看目录。", ""]`。空字符串被打印为 `> `，形成无意义的空行。

## 影响范围

- **产品**：Coding CLI REPL（TTY 模式）
- **用户影响**：中 — 多 turn 场景下无法看到 agent 的中间思考过程，输出顺序混乱，空行浪费屏幕空间
- **回滚**：可回滚到旧版批量渲染，但会重新引入所有缺陷

## 修复方向

放弃 Rich Live，改用 ANSI 光标控制（`\r\033[K` 擦除行）的纯顺序打印方案：

1. `drain_run` 新增 `on_event` 回调参数，事件到达即触发渲染。
2. `tool_start` 在同一行打印 `▸ Tool: name`（无换行）。
3. `tool_end` 用 `\r\033[K` 擦除后打印 `✓ Tool: name (elapsed=Xms)`。
4. `assistant_message` 直接逐行打印 `> content`。
5. 尾部空字符串通过 `while lines and lines[-1] == "": lines.pop()` 过滤。
