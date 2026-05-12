# 技能与斜杠命令 —— nano-multiagent vs Claude Code

> 对比维度：技能系统架构、斜杠命令、bundled skills、技能发现、技能执行

---

## 1. 技能系统架构

### Claude Code —— 三层技能

#### 1.1 Bundled Skills（代码内嵌）

```ts
// src/skills/bundledSkills.ts
registerBundledSkill({
  name: 'schedule',
  description: 'Schedule remote agents',
  getPromptForCommand: async (args, ctx) => [...],
  allowedTools: ['Task', 'Read'],
  model: 'sonnet',
})
```

内嵌技能列表（`src/skills/bundled/`）：
- `batch.ts` —— 批处理
- `claudeApi.ts` —— Claude API 调用
- `cronManage.ts` —— Cron 管理
- `debug.ts` —— 调试
- `keybindings.ts` —— 快捷键
- `loop.ts` —— 循环
- `remember.ts` —— 记住
- `scheduleRemoteAgents.ts` —— 调度远程 agent
- `simplify.ts` —— 简化
- `skillify.ts` —— 创建技能
- `stuck.ts` —— 卡住时求助
- `updateConfig.ts` —— 更新配置
- `verify.ts` —— 验证

**特性**：
- 编译进 CLI 二进制文件
- 支持内嵌参考文件（`files` 字段）
- 首次调用时惰性提取到临时目录
- 支持 `allowedTools` 限制工具范围
- 支持专用 `model`

#### 1.2 文件系统 Skills

```ts
// src/skills/loadSkillsDir.ts
```

从 `~/.claude/skills/` 和项目目录加载 SKILL.md 文件。

#### 1.3 MCP Skills

```ts
// src/skills/mcpSkills.ts
// src/skills/mcpSkillBuilders.ts
```

从 MCP 服务器动态构建技能。

### nano-multiagent —— 单层技能

```python
# src/agent/core/skills/registry.py
SkillRegistry(search_roots: Sequence[Path])
  └── _discover_skills() → 扫描 SKILL.md 文件
```

- 仅从文件系统扫描 `SKILL.md`
- 无 bundled skills 概念
- 无 MCP skills

```python
# src/agent/core/skills/formatter.py
format_available_skills_section(skills) → 渲染为系统提示文本
```

技能在系统提示中渲染为文本列表。

**缺陷**：
1. 无 bundled skills，所有技能必须放在文件系统
2. 无 MCP 技能发现
3. 技能功能较简单（只是文本注入）

---

## 2. 斜杠命令系统

### Claude Code —— Skills 即 Commands

```ts
// src/commands.ts
Command = {
  type: 'prompt' | 'immediate'
  name: string
  description: string
  aliases?: string[]
  allowedTools?: string[]
  model?: string
  getPromptForCommand: (args, ctx) => Promise<ContentBlockParam[]>
  // ...
}
```

斜杠命令 = 技能：
- `/schedule` → `schedule` skill
- `/simplify` → `simplify` skill
- `/verify` → `verify` skill

命令处理：
```
用户输入 "/schedule every 5m /foo"
  └── handlePromptSubmit()
        └── 解析斜杠命令
              └── command.getPromptForCommand(args, ctx)
                    └── 构建特殊提示 → 调用 query()
```

**特性**：
- 斜杠命令可以改变模型、工具列表、上下文
- `immediate` 类型命令直接执行，不走 API
- 命令可以带参数
- 支持别名

### nano-multiagent —— Skill Commands

```python
# src/agent/core/agent/skill_commands.py
rewrite_skill_command(user_text) → 改写 skill 命令
```

- 简单的文本替换机制
- 无 `Command` 类型系统
- 无 `allowedTools` 切换
- 无 `model` 切换

```python
# src/coding_cli/commands.py
```

CLI 命令存在，但不是斜杠命令系统。

**缺陷**：
1. 斜杠命令只是文本别名，无法改变模型或工具
2. 无 immediate 命令（本地执行）
3. 无命令参数解析

---

## 3. 技能发现

### Claude Code

```ts
// 启动时并行加载
setup() + getCommands() + getAgentDefinitionsWithOverrides()
```

- bundled skills：模块初始化时注册
- 文件系统 skills：启动时扫描
- MCP skills：连接 MCP 服务器后动态发现

### nano-multiagent

```python
# AgentRuntime._resolve_session_available_skills()
resolve_available_skills(
    workspace_root=session.workspace_root,
    include_names=session.skills,
    config_resolver=self._config_resolver,
)
```

- 按 session 配置的技能名称过滤
- 从 `config_resolver` 解析的搜索根目录扫描
- 无 MCP 发现

---

## 4. 技能上下文

### Claude Code

```ts
BundledSkillDefinition = {
  context?: 'inline' | 'fork'
  agent?: string
  hooks?: HooksSettings
}
```

- `inline`：在当前上下文中执行
- `fork`：在隔离上下文中执行
- 可以指定使用的 agent
- 可以配置 hooks

### nano-multiagent

- 无 `context` 概念
- 无 `agent` 绑定
- 技能只是文本片段

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Bundled Skills | 20+ 内嵌技能 | 无 | 🔴 高 |
| 文件系统 Skills | 有 | 有 | 🟢 低 |
| MCP Skills | 有 | 无 | 🟡 中 |
| 斜杠命令 | 完整命令系统 | 文本替换 | 🔴 高 |
| 命令改变模型 | 有 | 无 | 🟡 中 |
| 命令改变工具 | 有 | 无 | 🟡 中 |
| Immediate 命令 | 有 | 无 | 🟡 中 |
| 技能上下文 | inline/fork | 无 | 🟡 中 |
| 技能内嵌文件 | 有 | 无 | 🟢 低 |
| 技能别名 | 有 | 无 | 🟢 低 |
