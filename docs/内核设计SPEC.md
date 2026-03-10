# 内核设计 SPEC — src/agent/

> **版本** v1.0 | **日期** 2026-03-10
> 本文档是 `src/agent/` 内核包的设计权威文件，从属于顶层 `SPEC.md`。

---

## 1. 定位

`src/agent/` 是整个系统唯一的 Agent 执行内核。对外只暴露 HTTP API，不暴露 Python import。

**做什么**：单 Agent 运行时 + 工具执行 + 技能发现 + 事件扩展 + 会话持久化 + 上下文压缩 + 多 LLM Provider 适配。

**不做什么**：不知道什么是 coding / assistant；不做 IM 接入、Channel 路由、heartbeat 调度；不做 CLI 交互。

消费方通过 HTTP 使用内核：`coding_cli` 和 `personal_assistant` 同机直连，IM 不直接调用内核。

---

## 2. 三层架构

```text
src/agent/
├── core/        # 执行内核（纯逻辑，无 IO）
├── platform/    # 集成层（接外部环境）
└── products/    # 产品 profile（装配方案）
```

依赖方向：`platform → products + core`（禁止反向）。`core` 不依赖 `platform` / `products`。

### Core — 怎么运行

| 模块 | 职责 |
|---|---|
| `core/types.py` | `Message`、`ToolSpec`、`ToolCall`、`ToolResult`、`TurnResult` |
| `core/events.py` | 运行时事件与 Hook 事件契约 |
| `core/errors.py` | 类型化异常：`ModelError`、`ToolError`、`PolicyViolation` |
| `core/ids.py` | session / turn / message / tool-call ID 生成 |
| `core/agent/runtime.py` | 上层统一 API：`run`、`continue_turn`、`get_session` |
| `core/agent/loop.py` | 核心状态机：构建上下文 → 调 LLM → 工具执行 → 追加结果 → 继续 |
| `core/agent/state.py` | 会话与轮次内存状态 |
| `core/agent/policies.py` | 最大轮次、最大工具调用、token 预算策略 |
| `core/agent/prompting.py` | System prompt 与工具说明拼装（含 skills 段） |
| `core/agent/skill_commands.py` | `/skill:name` 输入改写 |
| `core/agent/compaction/` | 上下文压缩子系统（见 §5） |
| `core/session/manager.py` | 创建 / 加载 / 切换 / 归档会话 |
| `core/session/entries.py` | 会话事件定义（含 `CompactionEntry`） |
| `core/session/store.py` | `SessionStore` 持久化抽象接口 |
| `core/tools/base.py` | `Tool` 接口：`name` + `schema` + `run(args, ctx)` |
| `core/tools/registry.py` | 注册 / 分发 / 执行工具，参数校验 |
| `core/hooks/types.py` | `HookEvent`、`HookHandler`、`HookResult` |
| `core/hooks/context.py` | `HookContext`：只读会话上下文 + 日志 + 受控动作 |
| `core/hooks/registry.py` | Hook handler 注册表 |
| `core/hooks/runner.py` | 事件分发：优先级排序、超时、异常隔离、结果合并 |
| `core/skills/registry.py` | 加载 / 缓存技能元数据 |
| `core/skills/formatter.py` | 生成 `<available_skills>` prompt 片段 |
| `core/llm/interfaces.py` | `LLMClient`：`generate(context, tools, stream)` |
| `core/llm/factory.py` | 按配置选择 provider 客户端 |
| `core/llm/model_registry.py` | Provider / model 元数据与能力描述 |
| `core/observability/` | 结构化日志（session/turn/tool-call 关联 ID）+ 可选 tracing |

**规则**：core 不做文件 IO、DB 操作、Shell 执行、网络请求。这些全部委托给 platform 或 tool 实现。

### Platform — 怎么接环境

| 模块 | 职责 |
|---|---|
| `platform/http_api/` | HTTP routes、SSE、Bearer auth、deps、错误映射 |
| `platform/llm/providers/openai_compat/` | OpenAI 兼容协议实现 |
| `platform/llm/providers/anthropic/` | Anthropic 协议实现 |
| `platform/persistence/session/sqlite_store.py` | 生产默认 session store |
| `platform/persistence/session/jsonl_store.py` | 调试与回放友好 store |
| `platform/tools/loader.py` | 从产品配置目录扫描加载自定义工具 |
| `platform/tools/safety.py` | 路径沙箱、命令白黑名单、超时、输出截断 |
| `platform/tools/builtins/` | 5 个内置工具实现：`read` `write` `edit` `bash` `task` |
| `platform/hooks/loader.py` | 双源目录扫描加载 hook 模块 |
| `platform/config/` | 配置目录解析与 product namespace 映射 |
| `platform/bootstrap.py` | 产品装配接线：Profile → ResolvedProductConfig |
| `platform/sdk/client.py` | 供应用使用的 HTTP client |

### Products — 产品长什么样

| 模块 | 职责 |
|---|---|
| `products/base.py` | `ProductProfile` + `ResolvedProductConfig` 契约定义 |
| `products/local_coding/` | Coding 产品 |
| `products/personal_assistant/` | Assistant 产品 |

每个产品目录结构：

```text
products/<product>/
├── profile.py      # ProductProfile 声明
├── prompts.py      # 默认 system prompt
├── toolsets.py     # 从内核内置 + 产品专属工具中筛选默认启用集
├── tools/          # 产品专属工具实现
├── hooks/          # 产品专属 hook 实现
├── skills/         # 产品专属内置 skill
└── defaults.py     # 其他默认配置
```

`toolsets.py` 的作用是筛选：产品可能定义了多个专属工具，但部分是未来态尚未就绪，通过 toolsets 控制当前实际启用哪些。Hook 同理。

---

## 3. Runtime API

HTTP 层以下的统一入口，供 `platform/http_api` 调用：

```python
class AgentRuntime:
    def run(self, session_id: str, parts: list[dict], *, stream: bool = True): ...
    def continue_turn(self, session_id: str, *, stream: bool = True): ...
    def get_session(self, session_id: str): ...
```

- `parts` 仅支持 `text` 和 `image` 两种输入
- 音频 / 文件等非原生输入由外部先落盘，内核只接收路径文本
- 输入处理链路：`hooks.input`（可 transform / handled）→ `skill_commands` 改写 → `hooks.before_agent_start` → Agent Loop
- Provider 切换纯配置（`provider` + `model`），不改 runtime / tool / session 代码

---

## 4. Agent Loop 状态机

```
用户输入
  │
  ▼
hooks.input (intercept: continue / transform / handled)
  │
  ▼
skill_commands 改写（/skill:name → "Use the ... skill"）
  │
  ▼
hooks.before_agent_start (intercept: append_message / override_system_prompt)
  │
  ▼
┌─────────────────── Turn Loop ───────────────────┐
│  compaction preflight check                      │
│  │                                               │
│  ▼                                               │
│  构建上下文 → 调用 LLM (generate)                │
│  │                                               │
│  ├─ 纯文本响应 → 追加 assistant message → 结束   │
│  │                                               │
│  └─ tool_call →                                  │
│       hooks.tool_call (intercept: block?)         │
│       ToolRegistry.execute(name, args, ctx)       │
│       hooks.tool_result (intercept: rewrite?)     │
│       追加 tool result → 继续下一轮               │
│                                                   │
│  compaction post-turn check                      │
└──────────────────────────────────────────────────┘
  │
  ▼
hooks.agent_end (observe)
```

**Turn**：一次 LLM request-response 往返。
**Run**：从用户消息到 agent 完成的完整执行（可能跨多个 turn）。
**Session**：持久化会话，含历史、压缩点、事件日志。

---

## 5. Compaction（上下文压缩）

| 模块 | 职责 |
|---|---|
| `compaction/policy.py` | 触发判定：`threshold`（接近上限）vs `overflow`（已溢出） |
| `compaction/planner.py` | 切点规划：按完整 turn 切分，禁止拆开 tool_call 与 tool_result |
| `compaction/summarizer.py` | 通过 `LLMClient` 生成结构化摘要（目标 / 约束 / 进展 / 决策 / 下一步） |
| `compaction/applier.py` | 写入 `CompactionEntry`，重建上下文：`system + summary + kept_recent` |
| `compaction/types.py` | `CompactionReason`、`CompactionSettings`、`CompactionResult` |

- 运行时在 LLM 调用前做 preflight check，调用后做 post-turn check
- 落盘为 `CompactionEntry`，保留 `first_kept_event_id` 保证可重建与可审计
- overflow 后可恢复重试

---

## 6. 工具系统

### 接口

```python
class Tool:
    name: str
    schema: dict          # JSON Schema
    def run(args, ctx) -> ToolResult: ...
```

所有执行必须经 `ToolRegistry`。工具应无状态、可单测。工具执行时的 `cwd` / `repo_root` 绑定到当前 session 的 `workspace_root`（见 §9）。

### 5 个内置工具

| 工具 | 功能 | 关键约束 |
|---|---|---|
| `read` | 读文件 / 图片 | 截断：2000 行或 50KB；图片自动缩放 |
| `write` | 创建 / 覆盖文件 | 自动创建父目录 |
| `edit` | 精确文本替换 | 先精确后 fuzzy；多处匹配则失败 |
| `bash` | Shell 命令执行 | 尾部截断；超时 / 中断转明确错误 |
| `task` | 本地临时 subagent | blocking / non_blocking；仅本节点；需超时与幂等键 |

- `task` 无独立 HTTP 接口，外部入口始终是 `sessions/messages`
- `task` 的 `session_id` 参数（用于 continuation）与 `X-Session-Id` 不是同一概念

### 工具来源与加载

工具实现分布在两个地方：

| 实现位置 | 说明 |
|---|---|
| `platform/tools/builtins/` | 内核内置工具：`read` `write` `edit` `bash` `task` |
| `products/<product>/tools/` | 产品专属工具（如 assistant 的 IM 消息工具等） |

`products/<product>/toolsets.py` 负责**筛选**：从内核内置 + 产品专属工具中声明哪些默认启用、哪些可选。产品专属工具可能有未来态尚未实现的，通过此筛选层控制实际启用集合。

最终可用工具集按四层合并，优先级从低到高：

| 层 | 来源 | 说明 |
|---|---|---|
| 1. 内核内置 | `platform/tools/builtins/` | `read` `write` `edit` `bash` `task` |
| 2. 产品默认 | `products/<product>/tools/` + `toolsets.py` 筛选 | 产品专属工具，经筛选后启用 |
| 3. 用户全局 | `<global_config_home>/tools/` | 如 `~/.nanocode/tools/`，用户自行追加 |
| 4. 工作区 | `<workspace>/<workspace_config_dirname>/tools/` | 如 `<repo>/.nanocode/tools/`，项目级定制 |

- 同名工具高优先级覆盖低优先级
- 运行期不提供注册 / 卸载 API，变更需重启生效

> 详细参数与返回值契约见 `内核设计细化/工具设计细化.md`

---

## 7. Hook 系统

### 编程模型

每个 hook 文件导出 `setup(hooks: HookAPI)`。运行期无注册 / 卸载 API。

```python
class HookAPI:
    def on(self, event: str, handler, *, priority: int = 100, timeout_ms: int = 1500): ...
```

### Hook 来源与加载

Hook 实现分布在两个地方：

| 实现位置 | 说明 |
|---|---|
| `platform/hooks/builtins/` | 内核内置 hook（框架级默认行为） |
| `products/<product>/hooks/` | 产品专属 hook（如 assistant 的 NO_REPLY、heartbeat 提醒等） |

`products/<product>/` 的 profile 声明哪些 hook 模块默认启用。

最终加载按四层合并，执行顺序按 priority 排序：

| 层 | 来源 | 说明 |
|---|---|---|
| 1. 内核内置 | `platform/hooks/builtins/` | 框架级默认 |
| 2. 产品默认 | `products/<product>/hooks/` + profile 筛选 | 产品专属 hook |
| 3. 用户全局 | `<global_config_home>/hooks/` | 如 `~/.nanocode/hooks/`，用户自行追加 |
| 4. 工作区 | `<workspace>/<workspace_config_dirname>/hooks/` | 如 `<repo>/.nanocode/hooks/`，项目级定制 |

- 变更需重启生效
- 同优先级下后加载的 hook 后执行，便于本地覆盖内置行为
- 若需精确控制执行顺序，使用 `hooks.on(..., priority=...)` 参数

### 19 个事件

| 事件 | 阶段 | 类型 |
|---|---|---|
| `session_start` `session_compact` `session_shutdown` | 会话 | observe |
| `input` | 输入 | **intercept**：`continue` / `transform` / `handled` |
| `before_agent_start` | Loop 前 | **intercept**：`append_message` / `override_system_prompt` |
| `agent_start` `agent_end` | 运行 | observe |
| `turn_start` `turn_end` | 轮次 | observe |
| `message_start` `message_update` `message_end` | 消息流 | observe |
| `tool_call` | 工具执行前 | **intercept**：`block` + `reason` |
| `tool_execution_start` `tool_execution_update` `tool_execution_end` | 工具执行中 | observe |
| `tool_result` | 工具结果回写前 | **intercept**：重写 `content` / `details` / `is_error` |
| `run_error` `run_timeout` `run_abort` | 异常 | observe |

### 关键规则

- 默认 fail-open：单个 hook 异常 / 超时不中断主流程
- observe 事件不得改写核心状态；仅 intercept 事件允许改变行为
- 闭包共享状态必须按 `session_id` 隔离，不得替代会话持久化
- `input.handled` 和 `tool_call.block` 短路后续 handler

> 详细契约见 `内核设计细化/Hook体系设计细化.md`

---

## 8. Skill 系统

### 自动技能

当存在可见 skills 时，`prompting.py` 在 system prompt 追加：

```xml
<available_skills>
  <skill><name>...</name><description>...</description><location>/abs/path/SKILL.md</location></skill>
</available_skills>
```

模型按需用 `read` 工具读取 SKILL.md，不直接注入全文。

### 显式技能

`/skill:name [args]` → 改写为 `Use the "<name>" skill for this request.`（有参数时追加 `User input:` 段），然后走常规推理。

### Skill 来源与搜索

Skill 定义（SKILL.md）分布在多个位置：

| 实现位置 | 说明 |
|---|---|
| `products/<product>/skills/` | 产品专属内置 skill |

搜索按四层合并，优先级从高到低：

| 层 | 来源 | 说明 |
|---|---|---|
| 1. 工作区 | `<workspace>/<workspace_config_dirname>/skills/` | 如 `<repo>/.nanocode/skills/` |
| 2. 用户全局 | `<global_config_home>/skills/` | 如 `~/.nanocode/skills/` |
| 3. 产品默认 | `products/<product>/skills/` | 产品出厂内置 skill |
| 4. 兼容根 | `ProductProfile.compat_skill_roots` | 如 `~/.codex/skills/`，最低优先级 |

搜索结果合并去重后注入 `<available_skills>`。

### 与 task 的关系

`task` 工具支持 `load_skills` 参数，为子任务定向注入技能。自动机制（模型自主选择）与 `load_skills`（强制注入）可叠加。

> 详细契约见 `内核设计细化/Skill体系设计细化.md`

---

## 9. Session 与持久化

| 模块 | 职责 |
|---|---|
| `SessionManager` | 创建 / 加载 / 切换 / 归档会话 |
| `SessionStore`（接口） | 保存事件、加载会话、追加轮次 |
| `SQLiteSessionStore` | 生产默认（可靠、可查询） |
| `JSONLSessionStore` | 调试与回放友好 |
| `entries.py` | 会话事件定义（含 `CompactionEntry`） |
| `serializers.py` | 版本化序列化，支持迁移 |

- Event-sourced：每次状态变更产生事件并持久化
- Session 可由事件重放重建
- 运行时不能直接写 SQL，只通过 `SessionStore` 接口
- `sessions.sqlite3` 固定放在产品全局配置目录下

### Workspace 绑定

创建 session 时必须传入 `workspace_root`（工作区根目录）。该路径绑定到 session 生命周期：

- 后续该 session 内所有工具执行的 `cwd` / `repo_root` 均为此 `workspace_root`
- 工具加载的工作区层（§6 第 4 层）从 `<workspace_root>/<workspace_config_dirname>/tools/` 扫描
- Hook 加载的工作区层（§7 第 4 层）从 `<workspace_root>/<workspace_config_dirname>/hooks/` 扫描
- Skill 搜索的工作区层（§8 第 3 层）从 `<workspace_root>/<workspace_config_dirname>/skills/` 扫描
- Safety 沙箱以 `workspace_root` 为边界

---

## 10. LLM 抽象

```python
class LLMClient:
    def generate(self, context, tools, *, stream=False) -> LLMResult | Iterator[LLMEvent]: ...
```

| 模块 | 层 | 职责 |
|---|---|---|
| `core/llm/interfaces.py` | Core | 运行时唯一依赖的抽象接口 |
| `core/llm/factory.py` | Core | 按配置选择 provider |
| `core/llm/model_registry.py` | Core | Provider / model 元数据 |
| `platform/llm/providers/openai_compat/` | Platform | OpenAI 兼容协议 |
| `platform/llm/providers/anthropic/` | Platform | Anthropic 协议 |

- `agent` 只依赖 `core/llm/interfaces`，不能直接依赖 `platform/llm/providers/*`
- 请求必须携带 `X-Session-Id`，subagent 与主 agent 保持相同值
- Provider 切换纯配置，新 provider 必须通过 `LLMClient` 契约测试

---

## 11. ProductProfile

```python
@dataclass
class ProductProfile:
    product_id: str                            # 如 "local_coding"
    display_name: str
    config_namespace: str
    default_system_prompt: str | None
    default_tool_ids: list[str] | None
    optional_tool_ids: list[str]
    default_hook_modules: list[str] | None
    skill_search_policy: str | None
    session_store_policy: str | None
    memory_layout: dict
    heartbeat_layout: dict
    safety_defaults: dict
    capabilities: dict
    global_config_home: Path | None            # 如 ~/.nanocode/
    workspace_config_dirname: str | None       # 如 .nanocode
    session_db_filename: str                   # 默认 sessions.sqlite3
    compat_skill_roots: list[Path]
```

Bootstrap 启动时将 Profile 解析为 `ResolvedProductConfig`（含已装配的 `ToolRegistry`、`HookRegistry`、`SessionStore`），runtime 和 http_api 消费解析结果，无需产品条件分支。

---

## 12. HTTP API

统一约定：`Authorization: Bearer <token>`、`X-Request-Id` 追踪、`Idempotency-Key` 幂等。

错误格式：`{ "error": { "code": "...", "message": "...", "retryable": false, "trace_id": "..." } }`

### 全局

| Method | Path | 用途 |
|---|---|---|
| GET | `/v1/health` | 健康检查：`{ healthy, version, node_id }` |
| GET | `/v1/capabilities` | 当前节点支持的模型与工具 |
| GET | `/v1/openapi.json` | OpenAPI schema |

### 会话与消息

| Method | Path | 用途 |
|---|---|---|
| POST | `/v1/sessions` | 创建会话 `{ workspace_root, title?, metadata? }` |
| GET | `/v1/sessions` | 会话列表 |
| GET | `/v1/sessions/{id}` | 会话详情 |
| PATCH | `/v1/sessions/{id}` | 更新标题 / 归档状态 |
| POST | `/v1/sessions/{id}/messages` | 发送消息，同步等待 `{ parts: [text|image], model?, stream? }` |
| POST | `/v1/sessions/{id}/messages:async` | 异步提交，返回 `{ run_id }` |
| GET | `/v1/sessions/{id}/messages` | 分页读取消息 |
| POST | `/v1/sessions/{id}/abort` | 中断当前运行 |
| POST | `/v1/sessions/{id}/compact` | 手动触发压缩 |

### 运行与事件流

| Method | Path | 用途 |
|---|---|---|
| GET | `/v1/events` | 全局 SSE 事件流 |
| GET | `/v1/sessions/{id}/events` | 会话 SSE 事件流 |
| GET | `/v1/runs/{run_id}` | 异步运行状态 |
| POST | `/v1/runs/{run_id}/cancel` | 取消异步运行 |

### 工具与 Hook

| Method | Path | 用途 |
|---|---|---|
| GET | `/v1/tools` | 可用工具列表与 schema |
| GET | `/v1/hooks/events` | Hook 事件清单、类型、返回值契约 |
| GET | `/v1/hooks` | 已加载 Hook（名称、路径、来源、订阅事件、priority） |

工具和 Hook 不提供 HTTP 写操作。管理通过文件系统 + 重启生效。

---

## 13. 依赖方向

```
platform/http_api → core/agent, core/session, core/tools, core/hooks, core/llm
core/agent        → core/hooks, core/llm, core/tools, core/session, core/events
core/agent/compaction → core/llm, core/session
core/agent/prompting  → core/skills, core/tools
platform/llm/providers → core/llm/interfaces
platform/bootstrap     → products, core
platform/tools         → core/tools
platform/hooks         → core/hooks
products               → core（仅引用类型）
core/*                 → 仅依赖 core/ 内部
```

**铁律**：`core` 禁止 import `platform` 或 `products`。若破坏此方向，provider 和存储细节反向污染运行时。

---

## 14. 硬约束

1. `core/agent/runtime` 不得 import 具体 provider 实现类
2. 所有工具执行必须经 `ToolRegistry`
3. 内置 5 工具默认启用工作区安全约束
4. 每次状态变更必须产生事件并通过 `SessionStore` 持久化
5. Compaction 必须落盘为 `CompactionEntry`，保留 `first_kept_event_id`
6. `task` 仅本节点执行，需超时与幂等键；其 `session_id`（continuation）与 `X-Session-Id` 无关
7. 所有 LLM 请求必须带 `X-Session-Id`，subagent 与主 agent 相同值
8. Provider 切换纯配置，新 provider 必须通过 `LLMClient` 契约测试
9. Skills 自动发现走 `<available_skills>` prompt，禁止注入 SKILL.md 全文
10. `/skill:name` 改写为自然语言指令后走常规推理，不展开原文
11. Hook 执行支持优先级、超时、异常隔离；单个 hook 异常不中断主流程
12. 仅 intercept 事件允许改变行为；observe 事件不得改写核心状态
13. Tool / Hook / Skill 从四层来源合并加载（内核内置 → 产品默认 → 用户全局 → 工作区），运行期无注册 / 卸载 API
14. 创建 session 必须传入 `workspace_root`，后续工具执行 cwd 绑定到该 workspace

---

## 15. 验收标准

1. 相同 prompt + 相同 session snapshot 可稳定重放
2. 切换 provider 只改配置，不改 runtime / tool / session 代码
3. 5 个内置工具能通过模型 tool-call 正常触发
4. 进程重启后可恢复会话
5. 从日志 / 事件可完整追踪一轮执行链路
6. 长会话自动压缩不中断主流程，overflow 后可恢复重试
7. `task` blocking 与 non_blocking 均可工作
8. Skills 非空时 system prompt 含 `<available_skills>`，模型可 `read` SKILL.md
9. Hook observe / intercept / fail-open 均按契约生效
10. 自定义工具放入配置目录后重启可被 `GET /v1/tools` 发现
