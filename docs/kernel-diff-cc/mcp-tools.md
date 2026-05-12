# MCP 与工具生态 —— nano-multiagent vs Claude Code

> 对比维度：MCP 服务器集成、工具权限、工具发现、工具搜索、sandbox

---

## 1. MCP 服务器集成

### Claude Code —— 完整 MCP 支持

**文件**：`src/tools/MCPTool/`, `src/tasks/MonitorMcpTask/`, `src/cli/handlers/mcp.ts`

**MCP 功能**：

```bash
claude mcp add <name> <command>    # 添加 MCP 服务器
claude mcp remove <name>          # 移除
claude mcp list                   # 列出
claude mcp get <name>            # 详情
claude mcp serve                  # 作为 MCP 服务器运行
```

**配置层级**：
- 用户级：`~/.claude/settings.json`
- 项目级：`.claude/settings.json`
- 本地级：`.claude/settings.local.json`

**MCP 工具集成**：
- `MCPTool`：将 MCP 服务器的工具暴露给模型
- `ReadMcpResourceTool`：读取 MCP 资源
- `McpAuthTool`：MCP 认证
- `mcpSkills.ts`：从 MCP 服务器动态构建技能

**运行时行为**：
- `MonitorMcpTask`：监控 MCP 服务器健康状态
- MCP 工具动态注册到工具列表
- MCP 工具和普通工具统一调度

### nano-multiagent —— 完全缺失

- 无 MCP 相关代码
- 无 `mcp` 命令
- 无 MCP 配置
- 无 MCP 工具加载

**缺陷**：
1. 无法接入外部工具服务器（如文件系统、数据库、浏览器等）
2. 工具生态封闭，只有内置工具
3. 无法利用社区 MCP 服务器生态

---

## 2. 工具权限系统

### Claude Code —— 完整权限体系

**权限模式**：

```ts
// src/hooks/toolPermission/PermissionContext.ts
type PermissionMode = 'suggestive' | 'auto-edit' | 'auto-everything'
```

- **suggestive**：所有工具需要用户确认
- **auto-edit**：Read/Edit/Write 自动批准，其他需要确认
- **auto-everything**：所有工具自动批准

**权限上下文**：

```ts
ToolPermissionContext = {
  mode: PermissionMode
  allowedTools: string[]
  dangerousCommands: string[]
  // ...
}
```

**运行时检查**：

```ts
// REPL.tsx
const toolPermissionContext = useAppState(s => s.toolPermissionContext)
// query.ts
canUseTool: CanUseToolFn  // 工具权限检查函数
```

**权限 UI**：
- `PermissionRequest` 组件：覆盖层显示权限请求
- `SandboxPermissionRequest`：沙箱权限请求
- 用户可以通过快捷键批准/拒绝

### nano-multiagent —— 无权限系统

- 无 `PermissionMode` 概念
- 无 `canUseTool` 检查
- 工具一旦注册就全部可用
- 有 `bash_risk_gate.py` hook 做简单的 bash 风险检测，但不是系统级权限

```python
# src/agent/platform/hooks/builtins/bash_risk_gate.py
```

**缺陷**：
1. 无法区分自动批准和手动确认
2. 无工具级别权限控制
3. 无危险命令检测和拦截
4. 用户无法感知工具调用正在被请求

---

## 3. 工具发现

### Claude Code —— Deferred Tool Discovery

```ts
// src/utils/toolSearch.ts
```

- 工具搜索 beta：只包含已发现的 deferred tools
- 大项目时避免工具列表过长
- `ToolSearchTool`：模型可以搜索可用工具

### nano-multiagent —— 全量注册

- 所有可用工具一次性注册到 `tool_registry`
- 无 deferred 发现机制
- 无工具搜索

**缺陷**：工具多时上下文膨胀，影响模型选择和性能。

---

## 4. Sandbox 检测

### Claude Code

- 沙箱环境检测
- 沙箱权限请求 UI
- 受限环境下的功能降级

### nano-multiagent

- 无沙箱检测
- 无沙箱权限请求

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| MCP 服务器 | 完整集成 | 完全缺失 | 🔴 高 |
| MCP 工具 | MCPTool, ReadMcpResourceTool | 无 | 🔴 高 |
| MCP 配置 | 三级配置 | 无 | 🔴 高 |
| MCP 监控 | MonitorMcpTask | 无 | 🟡 中 |
| 权限模式 | suggestive/auto-edit/auto-everything | 无 | 🔴 高 |
| 权限上下文 | ToolPermissionContext | 无 | 🔴 高 |
| 权限 UI | PermissionRequest 覆盖层 | 无 | 🔴 高 |
| 工具发现 | Deferred discovery | 全量注册 | 🟡 中 |
| 工具搜索 | ToolSearchTool | 无 | 🟢 低 |
| Sandbox | 检测 + 权限请求 | 无 | 🟡 中 |
| 危险命令拦截 | 有 | bash_risk_gate hook | 🟡 中 |
