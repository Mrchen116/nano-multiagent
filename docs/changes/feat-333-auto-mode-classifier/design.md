# feat-333: Auto 模式默认体验 — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/feat-333-auto-mode-classifier` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

### 涉及范围

| 路径 | 当前职责 | 本 unit 改动 |
|---|---|---|
| `src/agent/platform/tools/safety.py` | 命令策略检查 (`check_command_policy`)：allowlist/denylist + `"review"` 三级判定；路径沙箱 | 扩展：新增 `auto_mode` 配置加载，将 `review` 级命令路由到分类器 |
| `src/agent/platform/hooks/builtins/bash_risk_gate.py` | 对 `review` 级 bash 命令调用 LLM 做 safe/unsafe 二分类 | **重构为** `auto_mode_gate.py`：统一处理所有工具（非仅 bash）的 allow/deny/ask 决策 |
| `src/agent/core/hooks/context.py` | `HookContext`：携带 `call_model()` 能力 | 不改：分类器通过 `ctx.call_model()` 调用 LLM |
| `src/agent/core/tools/registry.py` | `ToolRegistry.execute()`：tool_call intercept 可 block/allow/rewrite | 不改：auto_mode_gate 作为 hook 接入，复用现有 intercept 机制 |
| `src/agent/products/local_coding/profile.py` | Coding CLI 产品配置 | 不改：auto_mode 配置从 config 文件加载，不改 profile 结构 |
| `src/agent/products/personal_assistant/profile.py` | PA 产品配置 | 不改：同上 |
| `src/agent/platform/config/resolver.py` | 配置路径解析（global/workspace 两级） | 扩展：新增 `auto_mode_config_path()` 方法或复用现有路径约定 |
| `src/coding_cli/commands.py` | REPL 循环、用户输入 | 扩展：`ask` 决策时在终端显示权限请求 |
| `src/personal_assistant/gateway/outbound_router.py` | PA 消息出站路由 | 扩展：`ask` 决策时通过 IM 发送权限请求 |

### 既有约束

- **包边界硬规则**：`coding_cli` → `agent`（HTTP only），`personal_assistant` → `agent`（HTTP only），四个包禁止相互 import。
- **hook intercept 四事件**：`INPUT`、`BEFORE_AGENT_START`、`TOOL_CALL`、`TOOL_RESULT`。auto mode 决策必须在 `TOOL_CALL` intercept 中完成。
- **`ToolContext.safety_overrides`**：现有机制用于传递 `bash_allow_unlisted=True` 等 per-call 覆盖。
- **`HookContext.call_model()`**：hook 内可调用 LLM，已有 session_id 强制一致性保证。
- **config 目录约定**：Coding CLI = `~/.nanocode/` + `.nanocode/`；PA = `~/.nanoassistant/` + `.nanoassistant/`。

### 可复用能力

| 能力 | 位置 | 评估 |
|---|---|---|
| `bash_risk_gate` 的 LLM 分类模式 | `platform/hooks/builtins/bash_risk_gate.py` | **改写复用**：提取分类逻辑为通用分类器，扩展到所有工具 |
| `check_command_policy()` 三级判定 | `platform/tools/safety.py` | **直接复用**：作为分类器的快速路径（allowed → allow，denied → deny，review → 分类器） |
| `HookContext.call_model()` | `core/hooks/context.py` | **直接复用**：分类器调用 LLM 的通道 |
| `ToolContext.safety_overrides` | `core/tools/base.py` | **直接复用**：传递 per-call 权限授予 |
| PA `AgentWorkspaceConfig` 的 `tool_allowlist` | `personal_assistant/config/local_store.py` | **参考**：配置加载模式可参考 |

### 相关历史

- `feat-334-tool-result-budget`：工具结果压缩，不影响权限但影响结果返回路径。
- `feat-335-streaming-tool-executor`：流式工具执行器，auto_mode_gate 需要在 executor 的调用链中正确挂载。
- 无近期 unit 改过权限相关区域。

## 架构总览

### Before（现状）

```
用户输入 → AgentLoop → LLM → tool_call
                                  ↓
                          ToolRegistry.execute()
                                  ↓
                      ┌─ bash_risk_gate hook ─┐
                      │  bash 命令?           │
                      │  ├─ allowed → pass    │
                      │  ├─ denied  → block   │
                      │  └─ review  → LLM     │
                      │     ├─ safe → allow   │
                      │     └─ unsafe → block │
                      └───────────────────────┘
                                  ↓
                           tool.run(args, ctx)
```

### After（目标）

```
用户输入 → AgentLoop → LLM → tool_call
                                  ↓
                          ToolRegistry.execute()
                                  ↓
                      ┌─ auto_mode_gate hook ──────────┐
                      │  1. dangerously-skip? → pass    │
                      │  2. safe-tool allowlist? → pass │
                      │  3. bash: check_command_policy  │
                      │     ├─ allowed → pass           │
                      │     ├─ denied  → deny           │
                      │     └─ review  → 分类器         │
                      │  4. 非 bash 工具 → 分类器       │
                      │     分类器:                     │
                      │     ├─ allow → pass             │
                      │     ├─ deny  → block + reason   │
                      │     └─ ask  → 用户交互          │
                      │        ├─ CLI: 终端权限请求     │
                      │        └─ PA: IM 权限请求       │
                      └────────────────────────────────┘
                                  ↓
                           tool.run(args, ctx)
```

核心思路：**用一个统一的 `auto_mode_gate` hook 替换现有的 `bash_risk_gate`**，在 `tool_call` intercept 中实现三段式决策（安全快速路径 → 策略规则 → LLM 分类器），并将 `ask` 决策路由到各产品的用户交互层。

## 关键决策

### 决策 1: 分类器作为 hook 而非 core 层组件

- **选择**: 实现为 `platform/hooks/builtins/auto_mode_gate.py`，注册在 `tool_call` intercept 事件上。
- **理由**: 现有 `bash_risk_gate` 已经证明 hook intercept 是工具权限决策的正确位置。hook 可以访问 `HookContext.call_model()`，可以返回 `block`/`allow_unlisted`，可以跨工具统一处理。将分类器放在 core 层会违反 "core 不依赖 platform" 的分层约束。
- **拒绝**: 在 `ToolRegistry.execute()` 中硬编码权限检查 —— 这会让 core 层依赖 platform 的配置和 LLM 客户端。
- **风险**: hook 的 `timeout_ms` 需要合理设置（LLM 分类可能需要几秒），超时会导致 fail-closed（拒绝执行）。

### 决策 2: 配置存储在产品 config 文件中

- **选择**: `auto_mode` 配置写在各产品现有的 config 文件中（Coding CLI: `~/.nanocode/config.yaml`，PA: `~/.nanoassistant/config.yaml`），支持 workspace 覆盖 global。
- **理由**: 沿用现有配置目录和优先级约定（workspace > global），不引入新的配置路径。spec 明确要求"为了简化代码和其他的东西一致"。
- **拒绝**: 统一放在 `~/.nano/config.yaml` —— 会打破现有两个产品的配置隔离。
- **风险**: 需要给 Coding CLI 产品添加 config.yaml 加载逻辑（目前 Coding CLI 主要通过 CLI args + env vars 配置，没有 YAML 加载）。

### 决策 3: 分类器采用两阶段 LLM 调用

- **选择**: 参考 CC 的两阶段分类：stage 1 快速判定（max_tokens=64），如果 blocked 则 stage 2 深度推理（chain-of-thought）。
- **理由**: 大多数工具调用是安全的，stage 1 可以快速放行，减少延迟。只有被 stage 1 拦截的才需要深度推理，减少误判。
- **拒绝**: 单阶段分类 —— 要么太保守（误拦多），要么太宽松（漏放多）。
- **风险**: 两阶段意味着被拦截的调用延迟更高（~2-4s）。分类器不可用时必须 fail-closed 进入 `ask`。

### 决策 4: safe-tool allowlist 硬编码 + 可配置扩展

- **选择**: 内置 safe-tool allowlist（只读工具如 `read`、`web_fetch`、`web_search`、`task_list`、`task_get` 等自动放行），同时允许配置文件通过 `auto_mode.always_allow_tools` 扩展。
- **理由**: 参考 CC 的 `classifierDecision.ts` 中的 safe-tool allowlist。只读工具不产生副作用，自动放行是安全的。配置扩展满足用户个性化需求。
- **拒绝**: 所有工具都过分类器 —— 浪费 LLM 调用，增加延迟。
- **风险**: 如果 safe-tool allowlist 误包含了有副作用的工具，会绕过安全检查。

### 决策 5: `ask` 交互通过 session event 传递到产品层

- **选择**: 分类器返回 `ask` 时，通过 `HookContext.publish_session_event()` 发布 `permission_request` 事件，由各产品的 session event handler 负责实际的用户交互（CLI 终端提示 / IM 消息）。
- **理由**: hook 本身不能直接做用户交互（hook 在 agent core 的调用链中，不知道产品是 CLI 还是 IM）。session event 是现有的跨层通信机制。
- **拒绝**: hook 内直接调用 `input()` 或发送 IM 消息 —— 违反分层，hook 不应依赖产品层。
- **风险**: 需要各产品实现 session event handler。PA 的 IM 交互需要异步等待用户响应，agent loop 需要暂停。

### 决策 6: `dangerously-skip-permissions` 作为配置字段而非 CLI flag

- **选择**: 在 config.yaml 中配置 `dangerously_skip_permissions: true`，不提供 CLI flag。
- **理由**: spec 覆盖两个产品（Coding CLI 和 PA），PA 没有 CLI 入口。配置文件是两个产品共有的配置方式。
- **拒绝**: `--dangerously-skip-permissions` CLI flag —— PA 无法使用。
- **风险**: 用户需要手动编辑配置文件来启用/禁用，不如 flag 方便。但符合"危险操作应该显式"的安全原则。

## 接口与数据流

### 配置数据结构

```yaml
# config.yaml 中的 auto_mode 段
auto_mode:
  enabled: true                    # 默认 true
  dangerously_skip_permissions: false  # 默认 false
  always_allow_tools: []           # 额外自动放行的工具名
  allow:                           # 自然语言规则，注入分类器 system prompt
    - "reading files and directories"
    - "running tests and linters"
  soft_deny:
    - "deleting files outside the workspace"
  environment:
    - "This is a Python project using pytest"
```

```python
@dataclass(frozen=True)
class AutoModeConfig:
    enabled: bool = True
    dangerously_skip_permissions: bool = False
    always_allow_tools: tuple[str, ...] = ()
    allow: tuple[str, ...] = ()
    soft_deny: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()
```

### 分类器决策类型

```python
@dataclass(frozen=True)
class PermissionDecision:
    behavior: Literal["allow", "deny", "ask"]
    reason: str = ""
    rule_source: str = ""  # "safe_tool" | "command_policy" | "classifier" | "config" | "bypass"
```

### hook → 产品层的 `ask` 通信

```
auto_mode_gate hook
  ↓ 返回 {"ask": True, "permission_request": {...}}
ToolRegistry.execute()
  ↓ 检测到 ask，暂停工具执行
  ↓ publish_session_event("permission_request", {...})
产品层 handler
  ├─ CLI: 终端显示选项，等待用户输入
  └─ PA: 通过 IM 发送权限请求消息，等待用户回复
  ↓ 用户响应 → session_event("permission_response", {decision, rule_update})
ToolRegistry.execute()
  ↓ 根据用户决策继续或中止
```

### 分类器 prompt 结构

```
System: You are a tool permission classifier for a coding agent.
Decide if the following tool call should be allowed, denied, or require user approval.

[Allow Rules]
{auto_mode.allow from config}

[Deny Rules]
{auto_mode.soft_deny from config}

[Environment]
{auto_mode.environment from config}

User: Tool: {tool_name}
Args: {tool_args}
Context: {recent conversation summary}

Respond with JSON: {"decision": "allow"|"deny"|"ask", "reason": "..."}
```

## 风险与回退

### 已知风险

1. **分类器延迟**：每次 `review` 级调用需要 1-4s LLM 推理。对高频工具（如连续读文件）影响显著。
   - **缓解**: safe-tool allowlist 覆盖只读工具；bash 命令先过 `check_command_policy` 快速路径。
2. **分类器不可用**：LLM 服务宕机或超时。
   - **应对**: fail-closed —— 进入 `ask` 路径，让用户手动决策。不静默放行。
3. **`ask` 等待阻塞 agent loop**：PA 场景下用户可能长时间不响应。
   - **缓解**: 设置 `ask` 超时（默认 120s），超时后 deny 并反馈 agent。
4. **配置文件不存在时的默认行为**：两个产品都需要处理无 config 文件的情况。
   - **应对**: 默认 `auto_mode.enabled=true, dangerously_skip_permissions=false`，内置默认 allow/soft_deny 规则。

### 降级路径

- 分类器不可用 → 所有 `review` 级调用进入 `ask`（用户手动审批）
- `dangerously_skip_permissions=true` → 跳过所有权限检查（包括分类器）
- 配置文件损坏 → 使用内置默认规则，日志警告

### 回滚方案

- 删除 config.yaml 中的 `auto_mode` 段 → 回退到默认 auto 模式（内置规则）
- `auto_mode.enabled=false` → 禁用分类器，所有工具直接执行（等同于 `dangerously_skip_permissions`）

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| Coding CLI (agent API) | `kill $(lsof -ti:8000)` | `PYTHONPATH=src python3 -m coding_cli.main --mode managed --base-url http://127.0.0.1:8000` | `curl http://127.0.0.1:8000/v1/health` |
| Personal Assistant | `PYTHONPATH=src python -m personal_assistant.main stop` | `PYTHONPATH=src python -m personal_assistant.main --config /tmp/demo-gateway-config.yaml` | 检查进程存在 + IM 连接状态 |

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-333-M1 | impl | — | A | 全部范围：`auto_mode_gate.py` hook、`AutoModeConfig` 数据结构、config 加载、CLI ask 交互、PA ask 交互 | 两个产品默认 auto 模式可用；`dangerously-skip-permissions` 配置生效；`ask` 决策在 CLI 和 IM 中可响应 |
