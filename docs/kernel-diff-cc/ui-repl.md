# UI/REPL 架构 —— nano-multiagent vs Claude Code

> 对比维度：REPL 架构、终端渲染、快捷键、并发控制、输入处理

---

## 1. REPL 架构

### Claude Code —— React/Ink 全屏终端 UI

**文件**：`src/screens/REPL.tsx`（5009 行）

**技术栈**：
- React + Ink（React for terminals）
- 全屏终端渲染
- 虚拟滚动
- 组件化 UI

**架构**：

```tsx
<KeybindingSetup>
  <AnimatedTerminalTitle />
  <GlobalKeybindingHandlers />
  <CommandKeybindingHandlers />
  <ScrollKeybindingHandler />
  <CancelRequestHandler />
  <MCPConnectionManager>
    <FullscreenLayout
      overlay={<PermissionRequest />}
      scrollable={<>
        <Messages />
        <UserTextMessage />
        {toolJSX}
        <SpinnerWithVerb />
      </>}
      bottom={<>
        <SandboxPermissionRequest />
        <PromptDialog />
        <ElicitationDialog />
        <CostThresholdDialog />
        <FeedbackSurvey />
        <PromptInput onSubmit={onSubmit} ... />
      </>}
    />
  </MCPConnectionManager>
</KeybindingSetup>
```

**状态管理**：
- 全局 AppState（Zustand store）
- 本地 React state（50+ 个 useState/useRef）
- 关键 Ref：queryGuard, messagesRef, abortController

**两种模式**：
1. **Prompt 模式**：主交互界面
2. **Transcript 模式**：只读浏览历史，支持搜索

### nano-multiagent —— 简单终端输出

**文件**：`src/coding_cli/render/`

```
repl_render.py      # 基本渲染
repl_live.py        # Live 显示
repl_tool_lines.py  # 工具行渲染
turn_usage.py       # Usage 显示
context_budget.py   # 上下文预算
error_presenter.py  # 错误展示
repl_summary.py     # 摘要
```

**技术栈**：
- Rich（Python 终端渲染库）
- 非全屏，传统终端输出
- 无 React 组件模型

**架构**：

```python
# src/coding_cli/runtime/repl_runtime.py
class ReplRuntime:
    # 简单的输入输出循环
    # 无组件化架构
```

**与 CC 的差异**：

| 特性 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| UI 框架 | React + Ink | Rich |
| 渲染模式 | 全屏 | 滚动输出 |
| 组件化 | 是 | 否 |
| 虚拟滚动 | 有 | 无 |
| 消息搜索 | Transcript 模式 | 无 |
| 动画 | 终端标题动画、Spinner | 基本 Spinner |
| 覆盖层 | PermissionRequest 等 | 无 |

**缺陷**：
1. 无全屏 UI，大对话时难以浏览
2. 无消息搜索
3. 无覆盖层对话框
4. 无动画效果

---

## 2. 快捷键系统

### Claude Code —— 完整快捷键

**文件**：`src/keybindings/`

```ts
// 全局快捷键
Ctrl+C        // 取消请求
Ctrl+D        // 退出
Ctrl+L        // 清屏
v             // 切换 Transcript 模式
/             // 斜杠命令补全
@             // 文件提及
#             // 上下文选择
```

**组件**：
- `GlobalKeybindingHandlers`
- `CommandKeybindingHandlers`
- `ScrollKeybindingHandler`
- `CancelRequestHandler`

### nano-multiagent —— 基本无快捷键

- 无专门的快捷键系统
- 基本依赖标准终端输入
- 有 `repl_commands.py` 处理一些命令，但不是快捷键

**缺陷**：无快捷键严重影响交互效率。

---

## 3. 输入处理

### Claude Code

**PromptInput 组件**：
- 斜杠命令自动补全
- @ 提及文件/目录
- 多行输入支持
- 粘贴检测
- 图片粘贴

**输入预处理**：
```ts
// src/utils/handlePromptSubmit.ts
handlePromptSubmit()
  ├── 斜杠命令 → 路由到 Command handler
  ├── 普通文本 → 构建 UserMessage → onQuery()
  └── 图片附件 → 构建 Image content block
```

### nano-multiagent

**基本输入**：

```python
# src/coding_cli/input/repl_input.py
# 标准 input() 或 asyncio 读取
```

- 无自动补全
- 无 @ 提及
- 无多行输入
- 无粘贴检测

---

## 4. 消息渲染

### Claude Code

**Messages 组件**：
- 不同消息类型的不同渲染
- Assistant message：Markdown 渲染
- Tool use：折叠/展开
- Tool result：格式化输出
- Image：终端图片显示
- Streaming text：打字机效果

### nano-multiagent

**基本渲染**：
- 文本直接输出
- 工具调用通过 `repl_tool_lines.py` 简单渲染
- 无 Markdown 渲染
- 无折叠/展开

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| UI 框架 | React + Ink | Rich | 🟡 中 |
| 全屏渲染 | 有 | 无 | 🟡 中 |
| 组件化 | 是 | 否 | 🟡 中 |
| 消息搜索 | Transcript 模式 | 无 | 🟡 中 |
| 快捷键系统 | 完整 | 无 | 🔴 高 |
| 斜杠补全 | 有 | 无 | 🟡 中 |
| @ 提及 | 有 | 无 | 🔴 高 |
| 多行输入 | 有 | 无 | 🟡 中 |
| 图片粘贴 | 有 | 无 | 🟡 中 |
| Markdown 渲染 | 有 | 无 | 🟡 中 |
| 工具折叠 | 有 | 无 | 🟢 低 |
| 动画效果 | 有 | 无 | 🟢 低 |
| 覆盖层对话框 | 多种 | 无 | 🟡 中 |
