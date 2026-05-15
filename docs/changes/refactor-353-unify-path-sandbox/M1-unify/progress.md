# refactor-353-M1 Progress — unify

> 实施由 orchestrator 亲自写,不派 worker。spec → design → 直接动手 → e2e 实测 → 提 PR。

## R1 — safety.py 拆分语义

- Context: feat-333 演进后 `safety.py:_resolve_path` 仍硬 raise 工作区外路径,跟 auto_mode_gate + dangerously mode 抽象错配。
- 修法:
  1. 新增 `ToolSafety.normalize_path(path, cwd)` — 纯输入清洗(`expanduser` + cwd + `resolve`),不做 boundary check
  2. 新增 `ToolSafety.is_path_in_workspace(resolved)` — 返回 bool,供 hook 用
  3. `resolve_path`(write/edit 用)行为变更:**只做 normalize**,不再 raise。注释明确"workspace boundary 由 auto_mode_gate hook 在 tool 执行前判定"
  4. `resolve_read_path`(read 用)行为不变:仍硬错,因为 read 不走 hook 决策(默认放行)
- Evidence: `test_tool_safety_policy.py` 11 测全绿;`test_tools_builtins.py` 64 测全绿(其中 `test_read_rejects_path_outside_repo` 仍按预期 raise)

## R2 — auto_mode_gate 接入 path 维度

- 新增 `_WRITE_TOOLS_WITH_PATH_INPUT: Mapping[str, str] = {"write": "file_path", "edit": "file_path", "multi_edit": "file_path"}`
- 新增 `_detect_outside_workspace_path(tool_name, tool_input, ctx) -> str | None`:借助 `ToolSafety.normalize_path` + `is_path_in_workspace` 检测工作区外路径
- `on_tool_call` 流程改造:
  - dangerously bypass(原步骤 0)继续在最前面,等于 dangerously + 工作区外 path 自动放行(满足 spec "不进行任何权限管控")
  - 新增步骤 0.5: 检测 outside_workspace_path,作为后续步骤的信号
  - 步骤 2 safe_tools 快速放行:仅当**不在**工作区外时才生效(否则工作区外 write 即使 in safe_tools 也走 classifier)
  - 步骤 5 classifier:user_prompt 顶部注入 "NOTE: target path 'X' is OUTSIDE the agent's workspace ..." 提示,让 LLM 看到路径并做 informed 决策
- Evidence:
  - 新增 11 个单测 `test_path_sandbox_via_hook.py` 全绿(6 个 helper + 4 个 e2e gate branch + 1 个 contract)
  - 既有 64 个 auto_mode_gate 单测全绿
  - 既有 11 个 safety 单测全绿

## R3 — IM e2e 实测三场景

通过 IM HTTP API 直接调,无前端依赖。

### 场景 A: 工作区外 write + auto mode → ask 卡片 + Allow → 文件真写入

- 配置: `~/nanocode/config.yaml` `auto_mode.deny_limit: 1`(无 dangerously)
- 用户消息: `用 write 工具立即在 /tmp/refactor353-test/hello.py 写入: print(...)`
- 观察:
  - Agent 先选 bash(创建目录)→ ask 卡片弹出(`tool_name="bash"`)→ POST allow_once → bash 完成
  - Agent 再选 write(写入文件)→ **ask 卡片再弹出**(`tool_name="write"`,`tool_input.path="/tmp/refactor353-test/hello.py"`,`question="Writing files outside the current working directory and standard config paths requires explicit user confirmation"`)
  - POST allow_once → write 完成 → tool_call.status=completed, output="created (32 bytes)"
  - `cat /tmp/refactor353-test/hello.py` → `print('hello from refactor-353')` ✓

### 场景 B: 工作区外 write + auto mode + Deny → 文件未创建

- 同配置,新会话
- 用户消息: `用 write 工具立即在 /tmp/refactor353-deny/secret.py 写入: ...`
- 观察:
  - write 触发 ask → POST deny → tool_call.status=failed, output="tool blocked by hook"
  - `ls /tmp/refactor353-deny/` → 空 ✓

### 场景 C: 工作区外 write + dangerously mode → 直接通过,无 ask

- 配置改为 `auto_mode.deny_limit: 1` + `dangerously_skip_permissions: true`
- 重启 PA
- 用户消息: `用 write 工具立即在 /tmp/refactor353-danger/bypass.py 写入: ...`
- 观察:
  - 全程 `pr_count=0`(无任何 permission_request)
  - write 工具直接 tool_call.status=completed
  - `cat /tmp/refactor353-danger/bypass.py` → `print('dangerously mode bypass')` ✓
  - **spec 承诺"不进行任何权限管控"真正生效**

## 退出标准达成核对

| 退出标准 | 证据 |
|---|---|
| `[reviewer]` 用户写工作区外路径 → 看到卡片 + Allow 文件真写入 | 场景 A |
| `[reviewer]` Deny 后写入被拒绝、目标路径不变 | 场景 B |
| `[reviewer]` dangerously 模式下工作区外写直接成功,无卡片无错误 | 场景 C |
| `[worker]` 全部相关单测绿 | safety 11 + auto_mode_gate 64 + tools_builtins 64 + permission_broker 18 全绿 |
| `[worker]` 新增 `test_path_sandbox_via_hook.py` 覆盖 4 个关键分支 | 11 个单测全绿(实际 4 个 e2e branch + 6 个 helper + 1 contract) |

全部 ✓。

## Commits 累积 (M1)

- C1 = spec + design (commit b619084b)
- C2 = safety.py 拆分 + auto_mode_gate path 维度接入 + 11 个新单测 + e2e 实测(本 commit)

## 反 anti-pattern / 经验教训

1. **混着两套 gate 的隐性架构错配**:feat-333 引入 auto mode 时只升级了 hook 层,没动 codex 沿用的 tool 入口 safety,导致 dangerously 模式形同虚设。架构演进时要把所有相关 gate 一起搬。
2. **从 raise 到 hook decision 的语义统一**:`raise vs return` 是异常控制流,跟 hook 的 `allow/deny/ask` 不在同一抽象层。把同一类决策(权限)收敛到一个返回形式后,mode-aware 才能真正落地。
3. **path-detection 用 normalize 而不重新写校验逻辑**:`auto_mode_gate._detect_outside_workspace_path` 借助 `ToolSafety.normalize_path` + `is_path_in_workspace`,不复制 path 解析逻辑,保证 hook 和 tool 看到的是同一份 normalized path。
4. **e2e 必须实测多场景**:Allow / Deny / dangerously 三个场景每一个都跑过 IM 真实 API + 文件系统验证。仅靠单测会漏掉 SSE / WS / classifier prompt 链路问题。
