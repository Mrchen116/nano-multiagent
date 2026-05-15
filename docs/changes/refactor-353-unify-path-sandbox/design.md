# refactor-353: 统一路径沙箱到 auto_mode_gate 体系 — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/refactor-353-unify-path-sandbox`

## Changelog

(空)

## §现状分析

### 现有架构里有两套并行 gate

**Gate 1 — `auto_mode_gate` hook**(feat-333 引入,`src/agent/platform/hooks/builtins/auto_mode_gate.py`):
- 在 `tool_call` 事件触发,任何 tool 都走它
- 流程:dangerously bypass → session_allowlist 快速放行 → safe_tools 快速放行 → `safety.check_command_policy`(bash 命令分级) → classifier(LLM 判 allow/deny/ask) → ask 卡片
- 返回 `{"block": bool, "reason": str, "allow_unlisted": bool}`,完全是 hook 语义
- 是 mode-aware 的(读 `config.dangerously_skip_permissions`)

**Gate 2 — `safety.resolve_path` 在 tool 入口**(codex-cli 沿用,`src/agent/platform/tools/safety.py:269,289`):
- 仅 write / edit / read 等文件类 tool 用
- `_resolve_path` 在 hook **之后**、tool body 执行时调用 → 路径不在 `allowed_roots` 直接 `raise ToolError("path is outside repo sandbox")`
- **不知道 mode 概念**,无论 dangerously / auto 都硬错
- 调用点:
  - `write.py:35` → `ctx.safety.resolve_path(raw_path, ...)`(allowed_roots = repo_root 单点)
  - `edit.py:47` → 同上
  - `read.py:53` → `ctx.safety.resolve_read_path(raw_path, ...)`(allowed_roots = repo_root + ~/.codex/skills)

### 两套 gate 的语义不对等

| 维度 | Gate 1 (auto_mode_gate) | Gate 2 (safety.resolve_path) |
|---|---|---|
| 返回形 | allow/deny/ask hook decision | raise vs return |
| mode 感知 | 是(dangerously / auto) | 否 |
| 用户可授权 | 是(ask 卡片) | 否 |
| 决策可被 classifier 看到 | 是 | 否(在 hook 之后) |
| 安全保底 | hook 不跑则失效 | 始终生效 |

结果:工作区外的写入永远被 Gate 2 烧成异常,Gate 1 即使想 allow 也没机会(它在 hook 阶段判断的是 `tool_call` event 的 args,看到 path 也无法转译到 write.py:35 的硬错路径)。

### 现有能力可复用

- `auto_mode_gate.handle_ask` 已经接好 PermissionBroker + 卡片 + Allow once / Deny / Allow session 选项 —— 工作区外 path 的 ask 流程可以直接复用
- `auto_mode_gate.is_session_allowed` 已经支持 (session_id, tool_name) 维度的 session allowlist —— path 维度自然也覆盖(同一 session 允许 write 工具,就允许其下所有 write 调用)
- `build_yolo_system_prompt` + `_build_transcript_user_message` 已经把工具调用塞进 transcript —— classifier 看到 `write {"file_path": "/tmp/foo/bar.py", ...}` 不缺信息

### 既有约束

- `safety.py` 还在被很多地方调用,完全删掉 `resolve_path` 会牵涉太多;**保留方法但拆分语义**(normalization vs workspace check)更稳
- `read_allowed_roots` 包含 `~/.codex/skills`(读用),write 不需要这个集合
- 当前 `auto_mode_gate` 只看 `event.get("name")` + `event.get("args")` 决定走哪条路径;没读过 path 字段

## §架构总览

### Before

```
agent → tool_call event
            ├─ auto_mode_gate hook ─→ classify command/tool (path 不参与决策)
            │                          allow/deny/ask
            ↓ (hook allow)
        tool.execute()
            ├─ safety.resolve_path() ─→ 工作区外 → raise ToolError
            └─ ...
```

### After

```
agent → tool_call event
            ├─ auto_mode_gate hook
            │     ├─ pre-check: write/edit tool + path 在工作区外?
            │     │     ├─ dangerously mode → allow,跳过 classifier
            │     │     ├─ auto mode → 注入 "path is outside workspace: X"
            │     │     │             到 classifier user_prompt;classifier 决策
            │     │     └─ (fallthrough) → 现有流程
            │     └─ allow/deny/ask
            ↓ (hook allow)
        tool.execute()
            ├─ safety.resolve_path() ─→ 只做 normalization,**不做** workspace 检查
            └─ ...
        (workspace boundary 已经由 hook 在前置统一决策过)
```

核心改动:**工作区检查整个从 tool 入口移到 hook 层**。safety.resolve_path 只保留 path normalization(`..` traversal、symlink、绝对化)这一安全保底,workspace boundary 判定移交 hook。

### 为什么这样最干净

1. **复用 hook 已经接好的所有能力**:dangerously bypass、session allowlist、broker 卡片、deny_count、classifier 全部不需要新写一遍
2. **单一决策入口**:工作区内 / 外、命令 deny rule、classifier 决策全部都在 hook 层,符合 CC `hasPermissionsToUseTool` 的 single-orchestrator 哲学
3. **mode 真正生效**:dangerously 不再被 Gate 2 偷袭
4. **classifier 拿到上下文**:transcript 里能看到 `write {"file_path":"/tmp/..."}`,LLM 可以基于路径做 informed 决策

## §关键决策

### 决策 1: 工作区检查归 hook,不归 tool

- **选择**: 工作区 boundary 判定整个移入 `auto_mode_gate`。`safety.resolve_path` 只做 normalization(`..` traversal/symlink/absolute),不再检查 `relative_to(repo_root)`。
- **理由**: 单一入口、mode 感知、复用 hook 能力(见 §架构总览)。
- **拒绝**: "在 tool 入口加 mode 感知"(让 safety.resolve_path 读 mode 并决策) —— 需要把 PermissionBroker / AutoModeConfig 都注入 ToolSafety,污染 codex 沿用的纯 fs 抽象;且 ask 流程必须 await broker future,tool 入口是同步的接不进去。
- **拒绝**: "在 safety.resolve_path 里返回 (path, outside_flag) 让 tool 决定" —— 把决策权下放到每个 tool body,等于在多处复制 mode 处理逻辑,反而把单点变多点。
- **风险**: 如果某条 code path 跳过 hook 直接走 tool body(理论上应该不存在),workspace 检查会失守。**缓解**:增加 contract test 验证"所有 file tool 都走 hook"。

### 决策 2: 安全 normalization 保留在 safety 层

- **选择**: `..` traversal、symlink resolve、相对路径转绝对仍在 `safety.resolve_path` 内做;normalization 完成后返回 Path 给 tool 用,不做 workspace 检查。
- **理由**: 这部分是"输入清洗"性质的安全卫生,放 hook 层不合适(hook 不该关心 fs 细节)。CC 也是 `safeResolvePath` 在工具内做 normalization,`isPathAllowed` 在 orchestrator 做边界判定。
- **风险**: 调用方不能再假设"返回的 path 必在 repo_root 下"。所有 callsite 检查;若有原代码依赖这点的,补 audit。

### 决策 3: hook 怎么"看到" path 字段

- **选择**: 在 `auto_mode_gate` 内 hardcode 一个 `_WRITE_TOOLS_WITH_PATH_INPUT = {"write": "file_path", "edit": "file_path", "multi_edit": "file_path"}`,从 `tool_input[字段名]` 取路径。
- **理由**: 显式 + 简单 + 易扩展。
- **拒绝**: "让 tool 自己声明 `path_input_keys`" —— 引入新的 Tool API,工作量超出 unit。
- **风险**: 新增带 path 的 write 类 tool 时要补这个 map,但量极少,工程上 ok。

### 决策 4: dangerously 模式下也跳过 safety.resolve_path 的 normalization 吗

- **选择**: **不跳过**。normalization 永远跑(`..` traversal 永远屏蔽),dangerously 只跳过 workspace boundary 检查。
- **理由**: normalization 是输入清洗,跟权限无关;`..` traversal 即使用户 dangerously,我们仍要规整路径(不然 agent 写 `../../etc/passwd` 走相对路径会出歧义)。CC 同样不跳过 `safeResolvePath`。
- **风险**: 无。

### 决策 5: ask 选项跟 bash 一致吗

- **选择**: 一致。`Allow once` / `Allow session(写工具的所有调用,session 维度)` / `Deny`。复用 `auto_mode_gate._handle_ask` 的现有选项构造。
- **理由**: 用户体验一致。
- **拒绝**: 加 "Allow always(永久 allow 这个路径)" —— Q2 已经定为非目标(需要 additionalDirectories 持久化,独立 unit)。
- **风险**: 用户可能期望"永久 allow",但这次的卡片只给临时 / session 范围,需要 UX 文案说清楚。

## §接口与数据流

### `auto_mode_gate.on_tool_call` 内新增分支(在 dangerously bypass 之后、session allowlist 之前)

```python
# Pseudocode
WRITE_TOOLS_WITH_PATH = {"write": "file_path", "edit": "file_path", "multi_edit": "file_path"}

if tool_name in WRITE_TOOLS_WITH_PATH:
    path_key = WRITE_TOOLS_WITH_PATH[tool_name]
    raw_path = tool_input.get(path_key)
    if isinstance(raw_path, str) and raw_path:
        resolved = safety.normalize_path(raw_path, cwd=ctx.cwd)  # 新方法,只做 normalize
        if not safety.is_path_in_workspace(resolved):
            # 路径在工作区外
            if config.dangerously_skip_permissions:
                # 危险旁路:直接放行(走 normal path-in-workspace 分支也行,但显式放行表达更清晰)
                return None  # 让后续流程不再因为 path 触发额外 check
            # auto 模式:升级到 classifier,带 path 提示
            extra_hint = f"NOTE: target path '{resolved}' is OUTSIDE the workspace ({safety.repo_root})."
            # classifier 拿到带提示的 transcript,决策 allow/deny/ask
            decision = classify_action_with_extra_hint(extra_hint, ...)
            if decision == ask: → broker ask → 卡片 → Allow/Deny
            if decision == allow: pass through, write 真执行
            if decision == deny: block
```

### `safety.ToolSafety` API 变更

```python
class ToolSafety:
    # 新增
    def normalize_path(self, path: str, *, cwd: Path) -> Path:
        """Pure normalization: expanduser + cwd + resolve.  No boundary check."""

    def is_path_in_workspace(self, resolved: Path) -> bool:
        """Whether resolved path lies under repo_root."""

    def is_path_in_read_allowed_roots(self, resolved: Path) -> bool:
        """Whether resolved path lies under repo_root or trusted read roots."""

    # 行为变更
    def resolve_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path for WRITE tools.

        After refactor-353: only normalization happens here. Workspace boundary
        is enforced by auto_mode_gate hook before tool execution. Caller MUST
        ensure the tool_call event has been gated by hooks.
        """
        return self.normalize_path(path, cwd=cwd)

    # 不变
    def resolve_read_path(self, path: str, *, cwd: Path, tool_name: str) -> Path:
        """Resolve a path for READ tools — keeps boundary check on read_allowed_roots."""
        # 原行为保留:read 不走 hook 决策(默认放行),所以 boundary check 留这
```

### auto_mode_gate 入口/出口契约

- 入口不变:`(event, ctx) -> intercept_dict`
- 出口新增:对 write 类 tool,如果工作区外 path 通过 hook 决策(dangerously / classifier allow / 用户 Allow),返回正常 allow 结果(不变);如果被 deny / ask 拒绝,返回 `{"block": True, "reason": ...}`(已有形)。

### 数据流(工作区外 write 的完整路径)

```
1. agent.tool_use(write, file_path="/tmp/foo/x.py")
2. loop.py dispatch tool_call event → auto_mode_gate.on_tool_call(...)
3. auto_mode_gate:
   3a. dangerously? 是 → return None (pass through)
   3b. session_allowlist 命中? 是 → return None
   3c. tool_name="write" + path="/tmp/foo/x.py":
       3c-1. normalize → /tmp/foo/x.py
       3c-2. is_in_workspace? 否
       3c-3. dangerously? 否 (已在 3a 处理)
       3c-4. 走 classifier,user_prompt 附加 "OUTSIDE workspace" hint
       3c-5. classifier → ask (rm-rf 同款逻辑)
       3c-6. _handle_ask → broker.register_request → emit permission_request SSE
   3d. PA 收 SSE → 转 IM → 卡片
   3e. 用户点 Allow once → IM POST → PA POST kernel → broker.resolve(future)
   3f. hook 收 PermissionResponse(allow_once) → reset deny_count → return None
4. tool.execute()
   4a. safety.resolve_path("/tmp/foo/x.py") → normalize 返回 Path("/tmp/foo/x.py")
       (不再 raise,因为 workspace check 已在 hook 完成)
   4b. write file
   4c. success
```

## §风险与回退

### 风险 1: 跳过 hook 的代码路径

如果有任何 code path 跳过 hook 直接调 tool.execute(),工作区检查彻底失守。

**缓解**:
- 增加一个 contract test `tests/contract/test_file_tools_go_through_hooks.py`,验证所有文件 tool 在 ToolRegistry 注册时都触发 tool_call event
- 现有 ToolRegistry.execute 已经派发 tool_call event(见 `tools/registry.py` 的 intercept 流程),不存在跳过路径;但用 contract test 锁死防回归

### 风险 2: classifier 错误放行工作区外破坏性写

LLM 概率性给 allow,工作区外路径写入直接发生,无 ask。

**缓解**:
- "工作区外" 这一信号被注入 classifier user_prompt,LLM 更倾向触发 ask
- 现有 deny_limit:1 配置(workspace config)继续生效 —— 即使 classifier 第一次 allow,下次同 tool deny 一次就触发 ask
- 用户始终可以通过 `auto_mode.confirm_tools = ["write", "edit"]` 强制每次必 ask(已存在能力,文档说明)

### 风险 3: 现有单测大量改动

`test_tool_safety_policy.py` 等单测当前断言 `raises ToolError("path is outside...")`,改完后变成 hook decision。

**缓解**:
- 把这些测试整体迁移到 `test_auto_mode_gate.py`,新加 `test_write_outside_workspace_*` 系列
- 老 `safety.py` 路径检查的测试只保留 "normalization 正确" 的(`..` traversal 等)
- read path 不受影响,read 测试不动

### 风险 4: dangerously 模式漏放行 path normalization 异常

如果 dangerously + 路径含恶意 traversal,我们 normalize 后仍会得到一个 resolved path,可能落在意外位置。

**缓解**:决策 4 已明确 normalization 永远跑;dangerously 只跳过 boundary check,不跳过 normalize。

### 回退方案

如果上线后发现 hook 层判断 path boundary 出严重 bug,回退路径:
1. revert 本 PR
2. safety.py 路径检查回到 raise ToolError(老 codex 行为)
3. dangerously 仍失效 —— 但这就是 PR 修复前的状态,可接受作短期权宜

## §Runbook for Reviewer

涉及常驻服务:Kernel(uvicorn @ 8000)+ PA Gateway + IM(uvicorn @ 8011)。

```bash
# 重启 PA(Kernel 由 PA 拉起):
PYTHONPATH=src python -m personal_assistant.main restart

# 健康检查:
curl -sf http://127.0.0.1:8000/v1/health
curl -sI http://127.0.0.1:8011/ | head -1

# IM 入口(浏览器):
open http://127.0.0.1:8011/
# 登录: nano / nano1234

# 测试 agent(direct chat):default-agent
# Agent workspace_root: /private/tmp/demo-agent-workspace (见 ~/.nano-assistant/config.yaml)
# Workspace 外测试目标: /tmp/refactor353-test/
```

## §Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-353-M1 | unify | — | A | `src/agent/platform/tools/safety.py`, `src/agent/platform/hooks/builtins/auto_mode_gate.py`, `src/agent/platform/tools/builtins/write.py / edit.py / multi_edit.py`(callsite 改动)、相关单测迁移 | `[reviewer]` 用户在 IM 让 agent 写工作区外路径 → 看到 permission card → 点 Allow 后文件真写入;点 Deny 后写入被拒绝、路径不变 `[reviewer]` dangerously 模式下工作区外写直接成功,无卡片无错误 `[worker]` 全部相关单测(`test_tool_safety_policy.py` / `test_auto_mode_gate.py` / `test_product_profiles.py`)绿;新增 `test_path_sandbox_via_hook.py` 覆盖 4 个关键分支(workspace 内、workspace 外+dangerously、workspace 外+classifier-allow、workspace 外+ask) |
