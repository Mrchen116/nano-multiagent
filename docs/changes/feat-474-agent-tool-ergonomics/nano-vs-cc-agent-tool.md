# nano `agent` vs Claude Code `Agent` 对比

> 调研笔记，供 feat-474 澄清 / design 用。  
> 参考：本仓 `AgentTool`、feat-337、CC 源码；**实机目录以本节「CC 实机日志」为准，不必再翻 LLM_PROXY session。**

## 1. 工具拆分

| 能力 | nano | Claude Code |
|------|------|-------------|
| 派生子 agent | `agent` | `Agent` |
| 运行中插话 / 续跑 | 仍用 `agent(agent_id=...)` | 独立 `SendMessage({to, message})` |
| 停止后台任务 | `task_stop` | `TaskStop` |

两边主路径能力对称；nano 把「派发 + 插话 + 续跑」合进一个工具，CC 把续跑 / 插话拆到 `SendMessage`。

## 2. 入参（schema）

### nano 现状（改造前）

**必填：** `description` / `prompt` / `load_skills`（可 `[]`）  
**可选：** `subagent_type` / `category`（新建互斥必选其一）/ `run_in_background` / `agent_id` / `timeout_seconds`

### CC 实机 schema（2026-07-23，cc 2.1.218）

**必填：** `description` / `prompt`  
**可选：** `subagent_type` / `model` / `run_in_background` / `name` / `team_name` / `mode` / `isolation`  
**没有：** `timeout_seconds` / `load_skills` / `category` / `agent_id`

工具描述写明：不传 `subagent_type` → **general-purpose**；续跑走 **SendMessage**。类型列表不塞进 tool description，而在 conversation 的 system 附件 / reminder 里（见下节）。

### 入参对照小结

| 能力 | nano 现状 | CC 实机 | feat-474 倾向 |
|------|-----------|---------|---------------|
| 必填 | + `load_skills` | 仅 description+prompt | 删 `load_skills` |
| 选类型 | category **或** subagent_type 必选 | 可选，默认 general-purpose | 删 category；真类型目录 |
| 续跑 | `agent_id` | `SendMessage` | 保持 `agent_id`（已对齐语义） |
| 前台超时 | `timeout_seconds` 可调 | 系统 ~120s，schema 无 | 删参数，保留系统默认 |
| 模型 / 隔离 / 团队 | 无 | model / isolation / name… | 本期不做 |

## 3. CC 实机：主 agent 能调哪些 `subagent_type`

**证据（一次采全，后面不用再挖日志）：**

- Session: `LLM_PROXY/logs/session/2026-07-23_11-04-57_383_bd955747-630e-4946-9e5f-0adca705c23a/`
- 用户问：「你的agent工具，可以用哪些subagent_type」
- 请求样例：`…_11-04-57_405-req-anthropic_messages.json`（同内容亦见于更新的 `…_11-06-56_761-req-…`）
- `cc_version=2.1.218.2d7`，`cc_entrypoint=cli`，cwd=`LLM_PROXY`

系统附件原文列出的 **Available agent types**：

| `subagent_type` | 何时用（摘要） | Tools（日志原文） |
|-----------------|----------------|-------------------|
| **claude** | FleetView 兜底；没打名时的默认之一 | `*` |
| **claude-code-guide** | 问 Claude Code / SDK / API / Slack Tag 怎么用 | Bash, Read, WebFetch, WebSearch |
| **Explore** | 只读广搜；要结论不要文件倾倒；可指定 thoroughness | 除 Agent, Artifact, ExitPlanMode, Edit, Write, NotebookEdit |
| **general-purpose** | 通用调研 / 多步任务；不自信一次搜到就派它 | `*` |
| **Plan** | 只读架构规划；步骤 + critical files | 同 Explore（只读） |
| **statusline-setup** | 配 Claude Code status line | Read, Edit |

**未出现：** `verification`（源码里有，但要 feature + GrowthBook）。

**与源码 `builtInAgents.ts` 的差：** 实机多了 **`claude`**（产品/FleetView 向）；其余与「general-purpose + statusline-setup + guide + Explore/Plan」一致。

**类型真正改变什么（源码 + 实机一致）：**

- 工具 allow / deny（只读 vs 全开 vs 窄工具）
- 专用 system prompt
- 默认 model（如 Explore→haiku、guide→haiku）
- 其他：如 `omitClaudeMd`、`permissionMode`、`background` 默认等

**不是**只改个展示标签。

### 3.1 实机派发四类型：系统提示词差异（同一实验）

**证据：** 主 agent 在 `…_11-14-17_230` 并行派发 `claude` / `Explore` / `general-purpose` / `Plan`（均 `run_in_background:false`、`isolation:worktree`、`model:haiku`）。  
子 agent 请求：`…_11-14-28_{331,396,354,376}-req-anthropic_messages.json`。  
全文已落盘：`cc-subagent-system-prompts/{claude,Explore,general-purpose,Plan}.system.md`（以后对照用这个目录，不必再挖 session）。

| 类型 | 角色提示（头几句） | Edit/Write | 其它观察 |
|------|-------------------|------------|----------|
| **claude** | 「This session is a **background job**…」+ `result:` / `needs input:` / `failed:` 状态约定 | ✅ 有 | 与 general-purpose **不是同一套 prompt**；像 FleetView/作业线程协议 |
| **general-purpose** | 「You are an **agent for Claude Code**… concise report…」+ 搜代码 strengths/guidelines | ✅ 有 | 经典通用子 agent；禁止无必要新建文件 / 主动写 README |
| **Explore** | 「You are a **file search specialist**…」+ **READ-ONLY MODE** 大段禁改 | ❌ 无 | 强调快、并行搜；用 Bash 的 find/grep + Read；结果直接当消息回，不写报告文件 |
| **Plan** | 「You are a **software architect and planning specialist**…」+ **READ-ONLY** | ❌ 无 | 流程：理解需求 → 探索 → 设计 → 明细计划；末尾要 Critical Files 列表（源码定义；本实验任务只是打招呼） |

共性（四份请求都有）：

- 顶层还有短句 `You are Claude Code…`
- 工具列表里 **都没有 `Agent`**（这次派发不能再套一层 Agent）
- Explore/Plan 仍有 Bash / Read / Web* / Skill / Task* / SendMessage / Cron* 等，但靠 **去掉 Edit/Write/NotebookEdit + READ-ONLY 文案** 约束
- 各自 `isolation:worktree` → 独立 worktree cwd（日志里路径不同）
- 并行时 user 侧有 `Other agents active… SendMessage({to: name})` reminder

结论（对 feat-474）：要对齐 CC，类型差 = **专用 system prompt + 工具子集**；`claude` 与 `general-purpose` 在实机上是两套 prompt，不要当成同义词。

## 4. nano 现状：`subagent_type` 几乎只是标签

- `_resolve_agent_name`：`subagent_type or category` → 写入 metadata `agent_type`
- **没有**按类型换工具集 / 换 system prompt 的内置目录
- 传 `explore` / `general-purpose` / 任意字符串，执行能力基本一样

## 5. 来源分层

| 层 | 来源 | 内容 |
|----|------|------|
| 传参形态（旧） | oh-my-opencode `delegate_task` | `load_skills`、`category`↔`subagent_type` |
| 后台生命周期 | Claude Code（feat-337） | agent_id、output_file、notification、120s 转后台 |
| 类型语义（本期要对齐） | Claude Code 内置 AgentDefinition + 上节实机目录 | 类型 → 工具 + prompt（+ 可选 model） |

## 6. 双向通信

| 方向 | nano | CC |
|------|------|-----|
| 主 → 子（运行中插话） | ✅ `agent(agent_id, prompt)` | ✅ `SendMessage` |
| 子 → 主（边跑边推） | ❌ | ✅ 仅 Agent Teams |
| 完成回主 | ✅ `<task-notification>` | ✅ |
| 中途看进度 | 主 `read` `output_file` | 同 |

## 7. 已对齐（feat-337）

后台、`output_file`、`task_stop`、~120s 转后台、`<task-notification>`、运行中插话排队。

## 8. 一句话

生命周期与主→子插话已跟 CC 普通 subagent 对齐；入参仍偏 oh-my-opencode；**`subagent_type` 尚未成为真类型**。feat-474：瘦 schema + 落地真类型目录（候选见 spec 澄清）。
