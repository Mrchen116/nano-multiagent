# Skill体系设计细化

## 1. 设计目标
- 自动技能（pi 风格）：在 system prompt 注入 `<available_skills>`，模型按需用 `read` 读取 SKILL.md。
- 显式技能（openclaw 风格）：支持 `/skill:name`，输入改写后走常规推理。

## 2. 自动技能（system prompt）
- `read` 是内置基础工具，默认始终可用。
- 只要存在可见 skills，就在 system prompt 追加 skills 段。
- system prompt 插入原文（参考 `pi-mono`）：
```text
The following skills provide specialized instructions for specific tasks.
Use the read tool to load a skill's file when the task matches its description.
When a skill file references a relative path, resolve it against the skill directory (parent of SKILL.md / dirname of the path) and use that absolute path in tool commands.
```
- skills 段格式：
```xml
<available_skills>
  <skill>
    <name>...</name>
    <description>...</description>
    <location>/abs/path/to/SKILL.md</location>
  </skill>
</available_skills>
```
- 同时写明指令：任务匹配时，必须先用 `read(location)` 读取 SKILL.md，再执行。

## 3. 显式技能（/skill）
- 识别 `/skill:<name> [args...]`。
- 改写为：
  - `Use the "<name>" skill for this request.`
  - 有参数时再加 `User input:\n<args>`
- 改写后进入普通推理流程；不直接展开 SKILL.md 原文。

## 4. 核心模块
- `skills/registry.py`：加载/缓存 `name, description, location, base_dir`。
- `skills/workspace.py`：按工作区和配置筛选可见 skills。
- `skills/formatter.py`：生成 `<available_skills>` 文本。
- `agent/prompting.py`：拼装 skills 段到 system prompt。
- `agent/skill_commands.py`：处理 `/skill` 输入改写。

## 5. 与 task 的关系
- `task` 工具支持 `load_skills` 参数。
- `task` 启动 subagent 时，可显式传入 `load_skills` 作为该次任务的技能注入集合。
- 主 agent 的自动 skills 机制与 `task.load_skills` 可叠加：
  - 自动机制负责“可见技能与自主选择”；
  - `load_skills` 负责“本次子任务强制/定向注入”。

## 6. 验收
- 有可见 skills 时，system prompt 必须包含 `<available_skills>`。
- 模型可通过 `read` 成功读取 `location` 指向的 SKILL.md。
- `/skill:name` 会被改写为 `Use the "name" skill for this request.`。
- `task(load_skills=[...])` 能让 subagent 按指定技能执行。
