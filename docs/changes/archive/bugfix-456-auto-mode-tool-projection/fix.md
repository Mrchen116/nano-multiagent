# bugfix-456: Auto mode tool projection for dynamic tools

## Relations

- Related: feat-333-auto-mode-classifier

## 原始报告

> logs/session/2026-07-08_19-51-39_066_sess_be95cd418012b9d4/2026-07-08_20-07-18_735-req-anthropic_messages.json 这有问题吧，为啥skill_manage工具调用，这里请求权限也是bash rm -rf cold-joke-on-insult？

> 没有 classifier projection是什么意思

> 你再看看claude code源码，他是怎么设计的，所有工具都有映射？那mcp工具怎么办

> dynamic/MCP 类工具要有通用 projection，claude code的通用是啥

> 我们原本的设计是咋样，CC的这个很合理

> 那现在设计下，我们应该怎么最合理

> 别搞legacy fallback。

## 澄清记录

- Q1: auto mode 工具投影要继续用 `auto_mode_gate` 中央映射表，还是改成 CC 风格的工具协议？
  A(原话): 我们原本的设计是咋样，CC的这个很合理
  Agent 解读: 用户认可 Claude Code 的工具自带 projection / MCP wrapper 通用 projection 方向；本 bugfix 不应继续依赖中央 `TOOL_PROJECTIONS`。

- Q2: 迁移时是否保留 legacy fallback，未知工具继续按中央表或空投影兼容？
  A(原话): 别搞legacy fallback。
  Agent 解读: 本 bugfix 必须硬切到工具协议或注册期 wrapper；不得保留 `TOOL_PROJECTIONS` 作为 fallback，也不得让未知非 safe 工具空投影静默放行。

## 现象 / 复现

用户在 IM 中触发 `skill_manage create` 创建 skill 时，auto mode 权限请求显示的阻断理由却来自上一条历史动作 `bash rm -rf cold-joke-on-insult`。

取证路径：

- LLM proxy 请求文件 `logs/session/2026-07-08_19-51-39_066_sess_be95cd418012b9d4/2026-07-08_20-07-18_735-req-anthropic_messages.json` 是 auto mode classifier 请求。
- 对应会话历史中，上一条真实危险动作是 `bash rm -rf cold-joke-on-insult`，被拒绝。
- 后续真实当前动作是 `skill_manage create`，但 classifier prompt 没有 `skill_manage` 当前动作投影，导致 classifier 只基于历史 `bash rm -rf` 给出 deny。
- 用户可见结果是：当前工具调用是 `skill_manage`，权限卡/请求理由却像是在审批 `bash rm -rf`。

最小复现场景：

1. 在同一会话历史中先出现一个被 auto mode 判断为危险的 `bash rm -rf ...` 工具调用。
2. 随后触发一个非 safe、但当前没有 classifier projection 的工具，例如 `skill_manage create`。
3. auto mode classifier 请求中当前 action 为空或不可见。
4. 权限判断沿用历史危险动作语义，给当前工具返回错误阻断理由。

## 根因

### 直接根因

`auto_mode_gate` 使用中央 `TOOL_PROJECTIONS` 表生成 classifier-visible action。当前只覆盖 `bash` / `read` / `write` / `edit`：

```python
TOOL_PROJECTIONS = {
    "bash": ...,
    "read": ...,
    "write": ...,
    "edit": ...,
}
```

未知工具没有 projection 时返回空字符串。`skill_manage` 这种新增的有副作用工具没有进入中央表，因此当前动作没有被投影给 classifier。

旧行为还会在当前 action 无投影时继续调用 classifier。classifier prompt 只剩历史 transcript 中的 `bash rm -rf ...`，于是把历史危险动作的判断错误应用到当前 `skill_manage`。

### 原始设计意图追溯

该能力来自 `feat-333-auto-mode-classifier`。它的设计目标是复刻 Claude Code auto mode：safe 工具快速放行；工具自身可先做 `check_permissions`；需要上下文判断的非 safe 工具进入 LLM classifier；classifier 只看用户消息和 assistant tool_use 投影，不看 assistant 文本，避免 prompt injection。

`feat-333` 的 `design.md` 在“工具输入投影”中写过两个互相冲突的方向：

- 正确方向：每个非 safe 工具实现 `to_auto_classifier_input()`，复刻 CC 的 `toAutoClassifierInput` 契约。
- 落地方向：也允许在 `auto_mode_gate` 中集中实现 `TOOL_PROJECTIONS`，未知工具返回空、对 classifier 不可见。

M1 实施最终固化了中央表，导致新增工具、dynamic 工具、未来 MCP 工具都依赖人工记得补表。这个实现偏离了 CC 的实际架构，也偏离了“每个工具实现 projection”的更合理设计意图。

### Claude Code 对照结论

Claude Code 不是靠一个中央映射表覆盖所有工具。它把每个运行时工具建模为 `Tool`，由工具对象提供 `toAutoClassifierInput(input)`；MCP 工具也会被 wrapper 成 Tool：

- 普通工具：安全相关工具 override `toAutoClassifierInput`。
- safe allowlist：只读、搜索、任务/计划/内部协调等工具不进 classifier。
- MCP 工具：wrapper 统一提供通用 projection，格式为 `key=value key=value`；无参数时返回 MCP 原始 tool name。
- 权限规则支持 `mcp__server__tool`、`mcp__server`、`mcp__server__*` 粒度。

因此，dynamic/MCP 类工具不能因为没有专门映射就变成空动作。

### 为什么这种错能进来

- `feat-333` 的文档把“工具自带 projection”和“中央映射表”都写成可选落地方向，没有把“非 safe 工具必须可投影当前动作”设为不可变约束。
- 测试只覆盖了中央表中已知工具和 unknown 返回空，没有覆盖“历史危险动作 + 当前无 projection 非 safe 工具”的误归因场景。
- 新增 `skill_manage` 等 self-evolution 工具时，没有注册期 invariant 要求每个非 safe 工具具备 classifier projection。

## 修复

本 bugfix 的目标修复是硬切到工具协议，不保留 legacy fallback：

1. 删除 `auto_mode_gate` 中央 `TOOL_PROJECTIONS` 机制。
2. 在工具协议上引入 `to_auto_classifier_input(tool_input)`，作为 classifier action 的唯一来源。
3. 内置工具逐个声明 projection：
   - `bash`: command
   - `read`: file path
   - `write`: file path + content 摘要
   - `edit`: file path + new_string 摘要
   - `skill_view`: skill name/location 等只读目标
   - `skill_manage`: action/name/scope/file_path/content-or-patch 摘要
4. safe allowlist 只表示“根本不需要 classifier”；不允许把“没有 projection”当 safe。
5. dynamic / MCP / user tool 在注册期必须满足 projection 协议。没有专用 projection 的动态工具由注册期 wrapper 补通用结构化 projection：

   ```json
   {
     "tool": "<tool_name>",
     "input": { "...": "..." }
   }
   ```

6. `auto_mode_gate` 行为：
   - safe allowlist 命中：直接 allow，不进 classifier。
   - 非 safe 工具：从 tool 实例调用 `to_auto_classifier_input()`。
   - projection 返回 `""` 只允许表示工具明确声明“无安全相关动作”。
   - 找不到 tool 或 tool 缺 projection：ask / fail-closed；不得静默 allow，不得继续用空当前 action 调 classifier。
7. 不保留 `TOOL_PROJECTIONS` fallback，不保留 unknown-tool 空投影兼容路径。

### 实施结果

- `auto_mode_gate` 已删除中央 `TOOL_PROJECTIONS` / `project_tool_input`，classifier prompt 的工具动作只从 tool 实例 `to_auto_classifier_input()` 读取。
- `ToolRegistry.register()` 会为缺少专用 projection 的已注册 native / dynamic / user tool 包装通用结构化 projection：`{"tool": "<tool_name>", "input": {...}}`。
- 非 safe 工具在进入 classifier 前必须能解析到 tool 实例和非空 projection；找不到 tool、缺 projection、projection 抛错或返回空时直接 fail-closed，不调用 classifier 处理空 current action。
- safe allowlist 已收紧为当前约定集合：`read`、`web_search`、`skill_view`、`task_stop`、`agent`、`send_message`、`memory`。
- `web_fetch` 未加入 safe allowlist，继续保留 `WebFetchTool.check_permissions` 的预批准 host / hostname rule / ask fallback 语义，并补充 URL/prompt projection。
- `skill_manage list` 由工具级 `check_permissions` 本地 allow；`create` / `edit` / `patch` / `write_file` / `remove_file` 等变更 action 带 action/name/scope/content 等 projection 进入 classifier。
- `cron list` / `cron runs` 本地 allow；`add` / `update` / `remove` / `run` 由工具级 projection 后进入 classifier。

### Auto classifier bypass policy

本 bugfix 同时收紧“哪些工具不用 auto classifier 审核”的定义，避免修完 projection 后所有工具都频繁进 LLM classifier。

参考 Claude Code 的分层：

- safe allowlist 只放只读、搜索/资源枚举、任务元数据、plan/UI、内部协调类工具。
- `write` / `edit` 不在 safe allowlist；它们由工具自己的权限逻辑处理低风险路径，必要时才进入 classifier。
- MCP resource list/read 是 safe；普通 MCP tool 不是 safe，而是 wrapper 成 Tool 后走权限系统。

本项目采用两层 bypass：

#### 1. 无条件 safe allowlist

这些工具默认不进 classifier，因为它们不改变用户文件、外部系统、网络状态或长期自动化状态：

| 工具 | 决策 | 理由 |
|---|---|---|
| `read` | safe allowlist | 只读文件；对齐 CC `Read`。 |
| `web_search` | safe allowlist | 只读搜索公开网页结果；对齐 CC 搜索类工具不进 classifier。 |
| `skill_view` | safe allowlist | 只读取可见 skill 内容，并记录调用审计；不修改 skill。 |
| `task_stop` | safe allowlist | 停止/清理 agent 内部后台任务；不执行用户文件写入或外部发送。 |
| `agent` | safe allowlist | 内部子 agent 编排；子 agent 的具体工具调用仍各自走权限检查。 |
| `send_message` | safe allowlist | 按 CC `SendMessage` 对齐为内部协作/消息路由工具；发送动作不再经过 auto classifier。 |
| `memory` | safe allowlist | 仅写入 agent 自身记忆区，不修改用户代码/系统状态；若后续扩大到外部同步或共享发布，必须移出 safe allowlist。 |

未来如果出现 `task_list` / `task_get` / `task_update` / `task_output` 等纯任务元数据工具，可按 CC 放入 safe allowlist；但当前未注册的工具名不应预先出现在 allowlist 里。

#### 2. 工具级 fast path，不进入 safe allowlist

这些工具本身不是无条件 safe，但某些 action / 参数组合可以由 `check_permissions` 本地放行；本地无法明确安全时进入 classifier：

| 工具 | 本地可放行示例 | 需要 classifier / ask 的示例 |
|---|---|---|
| `bash` | 明确只读命令、测试、构建、项目内常规开发命令 | `rm -rf`、`sudo`、启动外部监听服务、远端 push、下载并执行代码 |
| `write` / `edit` | 当前仅对敏感系统路径本地 `ask`；普通写入不本地 allow | 项目内普通写入仍进入 classifier；敏感路径走 bypass-immune ask |
| `web_fetch` | 预批准 host 或文档读取类 URL | 未知 host、可能泄露 token 的 URL、下载执行链路 |
| `skill_manage` | `list` 等只读 action | `create` / `edit` / `patch` / `write_file` / `remove_file` |
| `cron` | `list` / `runs` 等查询 action | `add` / `update` / `remove` / `run`，因为它改变长期自动化或触发后台执行 |

#### 3. Dynamic / MCP / user tools

动态工具默认不进入 safe allowlist。注册期 wrapper 必须提供通用 projection；是否 bypass classifier 只能来自：

- 用户显式 allow rule；
- 工具自身 `check_permissions` 明确返回 allow；
- 该工具被明确归类为只读/资源枚举，并经过代码审查后加入 safe allowlist。

未知动态工具不得因为“没有 projection”跳过 classifier，也不得默认 safe。

## 验证

修复必须覆盖以下验证：

- 单测：所有内置注册工具都具备 `to_auto_classifier_input`，safe allowlist 工具除外也必须显式可解释。
- 单测：`project_tool_input` / `TOOL_PROJECTIONS` 不再存在于 `auto_mode_gate`。
- 回归测试：历史中有 `bash rm -rf cold-joke-on-insult`，当前调用 `skill_manage create` 时，classifier prompt 的 current action 必须包含 `skill_manage` 及其 action/name/scope 信息。
- 回归测试：当前工具缺 projection 且非 safe 时，gate 走 ask/fail-closed，不调用 classifier 处理空 action。
- 回归测试：dynamic wrapper 工具未自定义 projection 时，classifier action 使用结构化通用 projection，包含 tool name 和原始 input。
- 单测：safe allowlist 只包含本文列出的当前已注册 safe 工具；`web_fetch`、`skill_manage`、`cron` 不应无条件 safe。
- 单测：`skill_manage list`、`cron list/runs` 等 action 级低风险路径可由工具级 `check_permissions` 放行，不需要 LLM classifier。
- 真实验收：在 IM 中触发 `skill_manage create`，权限卡/请求理由必须围绕当前 skill 管理动作，不得出现上一条 `bash rm -rf` 的理由串台。

### 验证结果

- 红测：`/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py` -> 20 failed / 127 passed（实现前）。
- 窄测：同一组相关测试 -> 147 passed。
- Contract / integration 补充：`/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_tool_gate_coverage.py tests/integration/test_hooks_runtime_tools_integration.py` -> 4 passed。
- Lint：`/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check ...`（本次修改文件）-> All checks passed。
- 修复后失败回归：`/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_no_hardcoded_workspace_dirname.py tests/unit/test_path_sandbox_via_hook.py` -> 7 passed。
- 广测：`/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` -> 3322 passed / 2 skipped / 22 deselected。
