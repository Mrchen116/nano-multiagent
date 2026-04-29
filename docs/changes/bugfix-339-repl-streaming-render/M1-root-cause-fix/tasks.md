# M1: 根因修复

## 目标

修复 Coding CLI REPL TTY 渲染路径的 5 个关联缺陷，确保 SSE 事件流在终端上按真实时序、无丢失、无空行污染地呈现。

## Roadpoint

### RP1: 实时事件回调（解决批量输出）

- [x] `SessionStreamReader.drain_run()` 新增 `on_event` 参数
- [x] `_send_message_via_sse` TTY 分支传入回调，事件到达即渲染
- [x] non-TTY 分支同步改为回调模式

### RP2: 放弃 Rich Live，改用 ANSI 顺序打印（解决分组/光标损坏/消息丢失）

- [x] TTY 路径移除 `ReplLiveRenderer`
- [x] 实现 `\r\033[K` 行擦除逻辑
- [x] `tool_start` 无换行打印，`tool_end` 覆盖同一行
- [x] `assistant_message` 直接逐行输出
- [x] 验证多 turn 场景下中间消息不丢失、文字与工具穿插

### RP3: 过滤尾部空行（解决空行污染）

- [x] `assistant_message` 打印前 `pop` 尾部空字符串
- [x] 保留中间空行（段落分隔）
- [x] 单元测试覆盖

## 验收标准

1. 运行多 turn + 多工具查询时，终端逐行实时更新（非批量）。
2. 每个 LLM turn 的文本都可见，中间消息不丢失。
3. 文字与工具标记按事件到达顺序穿插呈现。
4. 无孤立的 `> ` 空行。
5. 所有现有单元测试通过。
