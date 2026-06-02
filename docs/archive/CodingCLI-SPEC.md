# Coding CLI SPEC — src/coding_cli/

> **版本** v1.0 | **日期** 2026-03-10
> 本文档是 `src/coding_cli/` 的设计权威文件，从属于顶层 `SPEC.md`。

---

## 1. 定位

`coding_cli` 是面向开发者的本地编码助手终端应用。

**做什么**：在终端内与 Agent 交互式对话，辅助读代码、写代码、执行命令、调试问题。

**不做什么**：不实现 Agent Loop，不直接调用 LLM，不管理会话持久化，不做 IM 接入。

**边界**：通过 `import agent.sdk` 进程内调用内核，禁止 import `agent.core` / `agent.platform` 内部模块。

**体验准则**：`coding_cli` 的前端交互与整体产品体验应优先对标成熟商业 Coding Agent CLI（如 Claude Code、Codex CLI）的一致性、简洁性与低心智负担；后续任何交互、信息架构、默认行为设计，都应先满足这一原则，偏离时必须有明确理由。

---

## 2. 运行模式

**refactor-387 起**：内核为进程内库（`agent.sdk`），无独立 HTTP API 进程。`--mode managed/remote`、`--base-url` 已移除。直接执行 `coding_cli` 即启动异步 REPL，进程内持有内核。

```
coding_cli ──import agent.sdk──→ Kernel（进程内）
```

- 无需启动/监控子进程
- 支持 LLM 覆盖参数（`--llm-provider`、`--llm-model`、`--llm-base-url`、`--llm-api-key`）

### 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `NANO_MULTIAGENT_API_BASE_URL` | API 服务地址 | `http://127.0.0.1:8000` |
| `NANO_MULTIAGENT_API_TIMEOUT_SECONDS` | 请求超时（秒） | `30.0` |
| `NANO_MULTIAGENT_TRACE_CONSOLE` | 设为 `1` 启用 ConsoleTracer，慢请求 waterfall 输出到 **stderr** | 未设置（关闭） |
| `NANO_MULTIAGENT_TRACE_CONSOLE_THRESHOLD_MS` | 自定义 ConsoleTracer 阈值（毫秒），覆盖 `100.0` | 未设置 |

Coding CLI 不引入 token 鉴权环境变量；新增配置应优先使用显式 CLI 参数或产品配置文件，以保持接口面简洁。

---

## 3. 双输出模式

### 交互式 REPL

面向人类的持续对话界面。支持实时事件流、上下文预算显示、斜杠命令、输入编辑与历史回溯。

### 单命令（Single Command）

面向脚本 / CI 的机器可读接口。stdout 输出唯一 JSON 对象，stderr 输出进程事件。

可用单命令：`health`、`create-session`、`send-message`、`llm-config`

错误输出格式：

```json
{ "error": "...", "layer": "input|network|runtime", "suggestion": "..." }
```

---

## 4. REPL 交互

### 会话生命周期

1. 启动时不自动创建 session
2. 用户首次输入时，调用 `POST /v1/sessions { workspace_root }` 创建 session，`workspace_root` 为当前工作目录
3. session 持续复用，直到用户执行 `/new` 创建新 session 或 `/use <id>` 切换
4. 退出时清理队列，managed 模式关闭 agent 进程

### 消息收发流程

```
用户输入
  │
  ├─ 斜杠命令？ → repl_commands 路由处理 → 显示结果
  │
  └─ 普通消息 →
       POST /v1/sessions/{id}/messages:async → run_id
       GET /v1/sessions/{id}/events (SSE 轮询)
       ├─ tool_start / tool_exec_* → 实时预览
       ├─ text_delta → 累积文本
       └─ run completed → 渲染最终响应 + usage + budget
```

### 异步事件消费

- 提交消息后获得 `run_id`，通过 SSE 轮询事件
- 事件按 `event_id` 去重，按 `run_id` 过滤
- 实时显示工具调用进度和文本生成增量
- 若异步不可用，退化为同步等待

### 斜杠命令

| 命令 | 功能 |
|---|---|
| `/help` | 显示帮助 |
| `/new` | 创建新 session |
| `/use <id>` | 切换活跃 session |
| `/session` | 显示当前 session ID |
| `/tools` | 列出当前 session 可用工具 |
| `/compact` | 手动触发上下文压缩 |
| `/history [n]` | 显示最近 n 条消息（默认 20） |
| `/exit` | 退出 REPL |

- 输入 `/` 时弹出命令下拉菜单，`↑/↓` 选择，`Enter` 填充
- 斜杠命令不计入消息历史

### 输入引擎

| 功能 | 按键 |
|---|---|
| 光标移动 | `←` `→` |
| 插入 / 删除 | 可打印字符 / `Backspace` |
| 历史回溯 | `↑`（上一条）`↓`（下一条） |
| 命令菜单 | `/` 触发，`↑/↓` 选择，`Enter` 填充 |
| 提交 | `Enter` |
| 退出 | `Ctrl-D`（EOF） |

- 非 TTY 环境退化为 `input()` 模式
- 输入历史按 session 隔离
- 进入历史浏览时保存当前草稿，返回时恢复

### 上下文预算显示

每轮对话后显示：

```
Context budget: 12500/128000 (9.8%)
```

阈值提示：
- ≥70%：`monitor context and consider /compact`
- ≥85%：`consider /compact soon`
- ≥95%：`run /compact now`

预算查询失败不阻塞主流程（fail-open）。

---

## 5. 错误处理

三层分类：

| 层 | 场景 | 示例 |
|---|---|---|
| `input` | 参数校验、无效 session | 缺少必填参数 |
| `network` | 连接失败、超时、鉴权 | 401 未授权、连接拒绝 |
| `runtime` | Agent 执行错误 | 工具执行失败、stop_reason 异常 |

每个错误携带 `layer` + `suggestion`（可执行的修复建议）。

---

## 6. 模块结构

```text
src/coding_cli/
├── main.py              # 进程入口
├── commands.py          # REPL / 单命令编排（CLI module boundary）
├── input/
│   ├── repl_input.py    # 终端输入引擎（行编辑、历史、命令菜单）（`repl_input.py`）
│   └── repl_commands.py # 斜杠命令路由与参数校验（`repl_commands.py`）
├── events/
│   ├── repl_events.py   # 异步事件消费与实时预览
│   └── event_pipeline.py # 事件归一化与去重
├── render/
│   ├── repl_render.py   # Turn 摘要渲染
│   ├── context_budget.py # 预算显示与阈值提示
│   ├── error_presenter.py # 错误分层与建议
│   └── turn_usage.py    # Token 用量格式化
└── runtime/
    └── repl_runtime.py  # 后台队列（异步消息派发）
```

> **refactor-387**: `client.py`（HTTP ServerClient）、`managed_server.py`（进程管理）、
> `kernel_app.py`、`session_stream.py` 已于 M4 删除。

### 模块职责边界

- `commands.py` 只做编排，不做输入解析、渲染、事件处理；stdout 输出 single final JSON object on stdout
- `input/` 不知道 agent，只处理终端交互
- `events/` 只消费内核事件流，不做 UI 渲染决策
- `render/` 只格式化输出，不做业务逻辑

---

## 7. 与 agent 内核的接口

**refactor-387 起**：内核 HTTP API 已删除。coding_cli 通过 `agent.sdk` 进程内直调：

| 操作 | SDK 调用 | 用途 |
|---|---|---|
| 创建 session | `await kernel.create_session(workspace_root=...)` | 启动 session |
| 提交消息 | `kernel.submit(session_id=..., parts=...)` | 异步发送消息 |
| 消费事件流 | `async for ev in kernel.stream(session_id)` | REPL 实时事件 |
| 列工具 | `kernel.list_session_tools(session_id=...)` | `/tools` 命令 |
| 压缩 | `await kernel.compact(session_id=...)` | `/compact` 命令 |
| 打断 | `kernel.interrupt(session_id=...)` | Ctrl-C |
| LLM config | `kernel.get_llm_config()` / `kernel.reconfigure_llm(...)` | `llm-config` 子命令 |

### Workspace 绑定

创建 session 时传入 `workspace_root`（默认为 CLI 启动时的 `cwd`）。此后该 session 内所有工具执行（read / write / edit / bash）的工作目录绑定到此 workspace。

---

## 8. 产品配置

coding_cli 使用 `local_coding` 产品 profile：

| 配置项 | 值 |
|---|---|
| product_id | `local_coding` |
| config_namespace | `nanocode` |
| 全局配置目录 | `~/.nanocode/` |
| 工作区配置目录 | `<workspace>/.nanocode/` |
| 默认工具 | `read` `write` `edit` `bash` `task` |
| 默认 hook | `bash_risk_gate` `default_status` `realtime_stream` `usage_metrics` |
| Session 存储 | `~/.nanocode/sessions.sqlite3` |
| System prompt | Expert coding assistant（带工具说明和 skill 发现） |

用户可在 `~/.nanocode/tools/`、`~/.nanocode/hooks/`、`~/.nanocode/skills/` 追加全局扩展。
工作区可在 `<workspace>/.nanocode/tools/` 等目录追加项目级扩展。

---

## 9. 硬约束

1. 禁止直接 import `agent.core` / `agent.platform` 内部模块；只允许 import `agent.sdk`
2. 单命令模式 stdout 只输出一个 JSON 对象，REPL 增强不得影响单命令输出格式
3. 错误必须携带 `layer` 和 `suggestion`，分层一致
4. 预算显示、事件流等增强功能 fail-open，不阻塞主对话流程
5. 输入历史按 session 隔离，命令执行不污染历史
6. 退出时调用 `kernel.close()` 释放后台线程
7. 非 TTY 环境必须可用（退化为 `input()` + 同步模式）
8. 禁止继续扩张环境变量接口面；新增配置必须优先走显式 CLI 参数或产品配置文件
9. 默认交互路径必须保持无参数启动；URL、端口等内部连接参数不得成为日常使用的必填项

---

## 10. 验收标准

1. 直接执行 `coding_cli`（无参数）即可启动 Managed 模式、自动拉起 agent、完成对话、退出时清理进程
2. `--mode remote --base-url <url>` 能连接远端 agent 并正常对话
3. 单命令 `send-message` 输出合法 JSON
4. REPL 中 `/new`、`/use`、`/tools`、`/compact`、`/history` 均正常工作
5. 斜杠命令下拉菜单 `↑/↓` 选择和 `Enter` 填充正常
6. 输入历史 `↑/↓` 回溯正常，session 间隔离
7. 实时事件流显示工具调用进度和文本增量
8. 上下文预算在每轮后正确显示，`/compact` 后刷新
9. 网络异常、鉴权失败等错误输出包含 layer + suggestion
10. 非 TTY 环境（如管道输入）不崩溃，退化为基础模式
