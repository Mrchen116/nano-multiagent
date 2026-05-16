# bugfix-355 — 回归验证

> 对齐: incident.md v1
> Review round: 1
> Date: 2026-05-16

## Verdict

**fail**

---

## 环境信息

- Branch: `unit/bugfix-355-read-workspace-outside-rejected`
- Gateway 启动命令: `PYTHONPATH=src python -m personal_assistant.main --config ~/.nano-assistant/config.yaml`
- Kernel API: `http://127.0.0.1:8000`
- IM: `http://127.0.0.1:8011`
- 服务接管: Gateway + IM 均重启; unit 分支新建文件 (`dangerous_paths.py`, `webfetch_preapproved.py`, `hostname_rules.py`) 已确认存在; `resolve_read_path` 已从 safety.py 删除

---

## User Journeys Exercised

| 旅程 | 路径 | 对应 Milestone |
|---|---|---|
| J1-auto-read-outside | 在 auto mode 下让 agent 读 `/tmp/sandbox-alpha/README.md`（工作区外）| M1 |
| J2-dangerous-write-bashrc | 在 dangerously 模式下让 agent 写 `~/.bashrc.test.bak` | M2 |
| J3-dangerous-write-git | 在 dangerously 模式下让 agent 写 `.git/test_config` | M2 |
| J4-normal-write | 在 dangerously 模式下让 agent 写 `/tmp/test_normal.txt`（期望直接放行）| M2 |
| J5-webfetch-preapproved | 在 auto mode 下让 agent web_fetch `https://docs.python.org/3/tutorial/` | M3 |
| J6-webfetch-unknown | 在 auto mode 下让 agent web_fetch `https://evil.example.com` | M3 |

---

## 复现验证 (M1)

**修复前行为（incident 描述）**: 用户让 agent 读 `/tmp/sandbox-alpha/README.md`，返回 `path is outside repo sandbox | 0 lines`。

**修复后验证**:

创建测试文件:
```
/tmp/sandbox-alpha/README.md: "Hello from sandbox-alpha! This is a test file for bugfix-355 verification."
```

Session `sess_6579afe909c70897`, Run `run_c2bbe526c7d74594`，发送消息 "请读 /tmp/sandbox-alpha/README.md 并返回文件内容"。

**观察到的结果**:

```
[user] 请读 /tmp/sandbox-alpha/README.md 并返回文件内容
[assistant] 让我读取这个文件。
[tool] 1→Hello from sandbox-alpha! This is a test file for bugfix-355 verification.
[assistant] 文件已成功读取，内容为：Hello from sandbox-alpha! This is a test file for bugfix-355 verification.
```

**结论**: R1 修复验证通过。Read 工具不再产生 `path is outside repo sandbox` 错误，agent 成功读取工作区外文件并返回内容。

---

## 回归测试

### M2: W1 危险目录写保护（bypass-immune safety_check）

**根本问题发现**: `tool_registry` 从未被注入到 HookContext metadata 中。

根据 design.md Anchor C，`auto_mode_gate.on_tool_call` 应通过 `metadata.get("tool_registry")` 拿到 tool 实例，再调用 `tool.check_permissions`。但在实际运行时：

```python
# auto_mode_gate.py:670
tool_registry = metadata.get("tool_registry")    # → None（从未被注入）
tool_instance = tool_registry.get(tool_name) if tool_registry is not None else None  # → None
check_fn = getattr(tool_instance, "check_permissions", None)  # → None
tool_result = check_fn(tool_input, None) if check_fn is not None else None  # → None
```

platform assembler（`src/agent/platform/http_api/app.py`）构建 HookRegistry 时没有把 `tool_registry` 注入进 hook 的 metadata 传递链。`build_hook_registry()` 与 `HookContext` 建立的地方（`loop.py:290`）都没有把 `app.state.tool_registry` 透传到 hook 调用的 metadata 字典中。

**旅程 J2 结果** (Session `sess_b3d4096f6da52e3b`, Run `run_9a2ce74d0904bfc7`):

```
[user] 请在 ~/.bashrc.test.bak 写入 test content: bugfix355
[tool] File created successfully at: /Users/czj/.bashrc.test.bak
[assistant] 已成功创建文件并写入内容！
```

`~/.bashrc.test.bak` 被直接写入，没有弹卡片。（注意：`.bashrc.test.bak` basename 不完全匹配 `.bashrc`，所以 `check_dangerous_path` 本身就返回 False，但 tool_registry 未注入使这条路径根本不可达）

**旅程 J3 结果** (Run `run_ae5de5e0d44fa218`):

```
[user] 请在当前目录的 .git/test_config 写入 content: test-git-write
[tool] File created successfully at: .git/test_config
[assistant] 已成功创建 .git/test_config 文件并写入内容！
```

`.git/test_config` 被直接写入真实 `.git` 目录，没有弹卡片。`check_dangerous_path('.git/test_config')` 在直接调用时返回 `True`，但 tool_registry 注入缺失导致 check_permissions 从未被调用。

**孤立测试验证** (check_permissions 函数本身):

```python
WriteTool().check_permissions({'path': '.git/test_config'}, mock_ctx)
# → PermissionDecision(behavior='ask', decision_reason={'type': 'safety_check', 'matched_path': '.git/test_config'})
WriteTool().check_permissions({'path': '~/.bashrc'}, mock_ctx)
# → PermissionDecision(behavior='ask', decision_reason={'type': 'safety_check'})
```

函数逻辑本身正确，但端到端链路断开。

**额外发现 - `.bashrc.test.bak` 命名问题**:

`check_dangerous_path('~/.bashrc.test.bak')` 返回 `False`（不命中），因为 basename `.bashrc.test.bak` 不完全等于 DANGEROUS_FILES 中的 `.bashrc`。设计 runbook 把 `~/.bashrc.test.bak` 列为"应该弹卡片"的测试路径，但当前实现的 exact-basename-match 规则无法覆盖 `.bashrc*` 前缀文件。这是一个独立的实现问题（与 tool_registry 注入无关）。

**M2 结论**: **fail（blocking）** — W1 端到端未生效。写入危险路径（`.git/config`, `~/.bashrc` 等）不弹卡片，dangerously mode bypass-immune 机制形同虚设。

### M3: WebFetch hostname rule 引擎

**旅程 J5 结果** (Session `sess_d295a27090e07a92`, Run `run_6a38e80bf374f311`):

- 消息: "请用 web_fetch 获取 https://docs.python.org/3/tutorial/ 的内容"
- 状态: completed，agent 返回了 Python 教程目录内容
- **问题**: 内容成功返回，但无法确认是否通过 preapproved 路径直接 allow，还是通过 classifier 判断后 allow（因 tool_registry 未注入，check_permissions 未被调用）

**旅程 J6 结果** (Run `run_93ba57d8bc48bec2`):

- 消息: "请用 web_fetch 获取 https://evil.example.com 的内容"
- 状态: completed，agent 输出: "抱歉，我无法获取该 URL 的内容，因为它指向一个可能存在风险的外部域名"
- **问题**: agent 未调用 web_fetch 工具，而是 LLM 凭 system prompt 中的安全指引拒绝了该请求。期望行为应为：gate 弹卡片要求用户确认，而不是 LLM 自行拒绝（用户无法看到卡片并选择 Allow 强制执行）

**孤立测试验证** (check_permissions 函数本身):

```python
WebFetchTool(config=AutoModeConfig()).check_permissions({'url': 'https://docs.python.org/3/'}, ctx)
# → PermissionDecision(behavior='allow', reason='preapproved host: docs.python.org')

WebFetchTool(config=AutoModeConfig()).check_permissions({'url': 'https://evil.example.com'}, ctx)
# → PermissionDecision(behavior='ask', reason='permission not granted yet for evil.example.com')

WebFetchTool(config=AutoModeConfig(web_fetch=WebFetchConfig(allow_hosts=('example.org',)))).check_permissions({'url': 'https://example.org/x'}, ctx)
# → PermissionDecision(behavior='allow', reason='hostname rule: allow example.org')
```

函数逻辑（preapproved → allow，unknown → ask，allow_hosts/deny_hosts/ask_hosts 规则）本身正确，但端到端链路断开（同 M2 问题）。

**M3 结论**: **fail（blocking）** — WebFetch check_permissions 端到端未生效，preapproved host 走的是 classifier 路径而非直接 allow，unknown host 的弹卡片行为被 LLM self-reasoning 覆盖，用户无法通过卡片强制允许访问。

---

## 验收标准覆盖

| ID | 验收项（incident.md）| 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|---|
| AC1 | 用户在 `auto` mode 下让 agent 读工作区外文件（如 `/tmp/foo/bar.md`），agent 能拿到内容并返回给用户；不再收到 `path is outside repo sandbox` 报错 | incident.md 验收标准第1条 | 真实 API session，发送 "请读 /tmp/sandbox-alpha/README.md" | Session sess_6579afe909c70897, 工具返回文件内容 | **pass** | R1 修复生效 |
| AC2 | 用户在 `dangerously-skip-permissions` mode 下读工作区外任意文件，直接放行无任何弹卡片；读 `.git/.bashrc/~/.ssh/id_rsa` 等也直接放行 | incident.md 验收标准第2条 | 真实旅程（dangerously 模式 read） | 未单独测试（工作区外 read 已在 AC1 验证，Read 工具无危险目录保护符合 CC 设计） | **pass** | R1 同时覆盖；Read 在 SAFE_TOOL_ALLOWLIST，bypass 下直接放行，符合 CC 设计 |
| AC3 | 用户在 `dangerously-skip-permissions` mode 下让 agent 改 `~/.bashrc` / `.git/config` / `~/.zshrc` 等危险路径，**仍然弹卡片让用户确认**（不再沉默写入） | incident.md 验收标准第3条 | 真实 API session，dangerously 模式写 `.git/test_config` | Run run_ae5de5e0d44fa218：文件被直接写入，没有弹卡片 | **fail** | tool_registry 注入缺失，WriteTool.check_permissions 未被调用，危险路径写入静默发生 |
| AC4 | 用户在 `dangerously-skip-permissions` mode 下改工作区内任意文件、改 `/tmp/foo/bar.txt` 等普通工作区外路径，跟之前一样直接放行（W1 不能误伤正常路径）| incident.md 验收标准第4条 | 真实旅程（dangerously 模式写普通路径）| 未直接测试；鉴于 tool_registry 未注入，check_permissions 从未被调用，所有写操作都直接放行（反而"符合"此条，但系统性失控）| inconclusive | AC3 fail 状态下此条实质上是"所有写操作都放行"，反映的是系统失控而非正确实现 |
| AC5 | 用户在 `auto` mode 下让 agent 调 WebFetch 抓未审核域名，行为按 CC 复刻的 hostname rule 引擎（preapproved → allow；否则按用户规则匹配 / 弹卡片 / classifier）；跟之前"直接 allow"行为有可观察的差别 | incident.md 验收标准第5条 | 真实 API session，web_fetch evil.example.com | Run run_93ba57d8bc48bec2：LLM 自行拒绝调用 tool，没有弹卡片让用户选择 | **fail** | tool_registry 注入缺失，WebFetchTool.check_permissions 未被调用；evil.example.com 被 LLM self-reasoning 拒绝，不是权限门控卡片 |
| AC6 | 用户在 `auto` mode 下让 agent 派子 agent（`agent` 工具），行为跟修复前一致，直接 allow | incident.md 验收标准第6条 | 代码审查（agent 仍在 SAFE_TOOL_ALLOWLIST） | SAFE_TOOL_ALLOWLIST 保留 `agent`（从 auto_mode_gate 源码确认）| **pass** | 代码确认，无需旅程验证 |
| AC7 | 用户在 `auto` mode 下让 agent 写工作区外路径，classifier 的决策跟修复前可重现一致或更准（本仓不再加塞 OUTSIDE NOTE） | incident.md 验收标准第7条 | 代码审查：搜索 `OUTSIDE NOTE` 相关代码 | `grep "OUTSIDE\|NOTE.*target\|_detect_outside"` 在 auto_mode_gate.py 无命中（W2 删除已生效）| **pass** | W2 修复已生效，OUTSIDE NOTE 从 classifier prompt 移除 |
| AC8 | refactor-353 spec.md Q1 / design.md 决策 2 段末有 corrigendum 注释，Changelog 有索引行 | design.md M1 退出标准 | 直接读文档文件 | refactor-353 spec.md:L32 和 design.md:L110 均有 `Corrigendum (2026-05-16, bugfix-355)` 注释；Changelog 也各有一行 | **pass** | R2 文档修正已生效 |

---

## 问题清单

### Issue #1 — tool_registry 注入缺失，导致 check_permissions 端到端失效

**Severity**: blocking

**现象**: WriteTool / EditTool / WebFetchTool 的 `check_permissions` 方法已正确实现，但 `auto_mode_gate.on_tool_call` 无法拿到 tool 实例，因此从未调用这些方法。所有写操作（含 `.git/config`, `~/.bashrc` 等）在 dangerously 模式下静默写入；WebFetch 的 preapproved/ask 逻辑也完全旁路。

**期望**: `auto_mode_gate.py:670` `metadata.get("tool_registry")` 应返回当前 session 的 ToolRegistry 实例。

**实际**: 永远返回 `None`；tool_instance = None；check_fn = None；tool_result = None；safety_locked = False。

**影响**: M2 W1（bypass-immune safety_check）完全失守；M3 S1（WebFetch hostname rule）完全失守。

**定位**: design.md Anchor C 明确要求 "在 platform 装配处把 registry 透传给 hook"，但 `src/agent/platform/http_api/app.py` 的 HookContext 构建链（`loop.py:286-299` 及 AgentRuntime 初始化）均未注入 `tool_registry` 到 metadata。

**Recommended Action**: fix-implementation

**Action Rationale**: 实现遗漏，design.md Anchor C 已明确定义注入点，只是 worker 实施时没有把 `app.state.tool_registry` 透传到 HookContext metadata。

---

### Issue #2 — `.bashrc.test.bak` 类命名文件不受保护（exact-match vs prefix-match）

**Severity**: major

**现象**: `check_dangerous_path('~/.bashrc.test.bak')` 返回 `False`，因为 DANGEROUS_FILES 使用 exact basename matching，而 `.bashrc.test.bak` ≠ `.bashrc`。Runbook for Reviewer 把 `~/.bashrc.test.bak` 列为"应弹卡片"的测试路径，说明此类命名是预期被保护的场景。

**期望**: `.bashrc.test.bak`, `.bashrc.bak`, `.bashrc_backup` 等 `.bashrc` 变体，按 CC 的实际用户感知，也应视为危险文件触发 ask。

**实际**: 只有完全匹配 `.bashrc` 的文件才触发保护。

**注意**: 此 issue 与 Issue #1 独立——即使 #1 修复，`.bashrc.test.bak` 仍不会被保护。

**Recommended Action**: fix-implementation

**Action Rationale**: DANGEROUS_FILES 匹配规则过窄（exact match），应改为 "basename 以危险文件名开头" 或 "basename 去掉扩展名后匹配" 的前缀规则，以覆盖备份/临时命名变体。

---

### Issue #3 — dangerously 模式配置路径 Runbook 文档有误

**Severity**: minor

**现象**: design.md Runbook for Reviewer 说 "workspace config 改 `auto_mode.dangerously_skip_permissions: true`" 并指向 `~/.nano-assistant/config.yaml`，但 `auto_mode_gate` 实际从 `<workspace>/.nanocode/config.yaml`（`global_config_dir=None`，`workspace_config_dir=repo_root / ".nanocode"`）读取 auto_mode 配置，而不是 `~/.nano-assistant/config.yaml`。reviewer 按照 runbook 操作无法实际切换到 dangerously 模式。

**Recommended Action**: fix-implementation（文档修正）

**Action Rationale**: Runbook 配置路径与代码实际读取路径不一致，属于 design.md 中 runbook 段的文档错误，无需 revise-design。

---

## 自动化测试增量

| 单测文件 | 覆盖内容 |
|---|---|
| `tests/unit/agent/platform/tools/test_dangerous_paths.py` | 44 tests: DANGEROUS_FILES/DIRECTORIES 常量, `check_dangerous_path` 各路径规则（44 passed）|
| `tests/unit/agent/platform/tools/test_tool_check_permissions.py` | 23 tests: Tool 协议 + WriteTool/EditTool check_permissions（23 passed）|
| `tests/unit/agent/platform/tools/builtins/test_webfetch_preapproved.py` | 25 tests: PREAPPROVED_HOSTS, `is_preapproved_host`（25 passed）|
| `tests/unit/agent/platform/permissions/test_hostname_rules.py` | HostnameRuleEngine deny/ask/allow 优先级（已集成）|
| `tests/unit/agent/platform/test_auto_mode_web_fetch_config.py` | 16 tests: AutoModeConfig.web_fetch 字段解析（16 passed）|
| `tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py` | 21 tests: WebFetchTool check_permissions 4 分支（21 passed）|

**注意**: 单测全部通过，但**单测未能覆盖 tool_registry 注入链路**（Issue #1）。单测直接实例化 tool 并调用 check_permissions，跳过了 auto_mode_gate → HookContext → metadata 的传递路径，因此注入缺失未被任何单测检出。

---

## 上层文档同步

- [x] `SPEC.md`（架构总览）：**无需更新** — 本 unit 不改变整体架构，权限子系统改动在 platform 内部
- [x] `docs/内核设计SPEC.md`：**需要检查** — 新增 `check_permissions` 接口、`PermissionDecision.passthrough` 行为、tool_registry 注入约定；待 Issue #1 修复后更新内核设计文档
- [x] `AGENTS.md` / `CLAUDE.md`：**无需更新** — 开发者约定未变
- [x] 相关产品 SPEC（`docs/NodeGateway-SPEC.md`、`docs/CodingCLI-SPEC.md`）：**无需更新** — 本 unit 只影响权限 gate 层，不改产品 SPEC

---

## Side Findings

- `~/.nanoassistant/` 目录（ProductProfile `global_config_home`）与 `~/.nano-assistant/`（AGENTS.md 文档约定）拼写不一致（一个有连字符，一个没有）。这是文档 vs 代码的不一致，不影响本 unit 功能。[minor, out-of-unit]
- 当前 `auto_mode_gate` fallback 的 `global_config_dir=None` 意味着全局 auto_mode 配置（如 `~/.nanoassistant/config.yaml` 中的 `dangerously_skip_permissions`）对 personal_assistant kernel 无效，只有 workspace `.nanocode/config.yaml` 生效。这可能不是设计意图，但不在本 unit 范围。[minor, out-of-unit]

---

## 结论

| Gap | 修复状态 |
|---|---|
| R1: Read 工作区外硬错 | ✅ 已修复并验证 |
| R2: refactor-353 文档 corrigendum | ✅ 已修复并验证 |
| W1: bypass-immune 危险目录写保护 | ❌ 端到端未生效（tool_registry 注入缺失）|
| W2: OUTSIDE NOTE 移除 | ✅ 已修复并验证 |
| S1: WebFetch hostname rule 引擎 | ❌ 端到端未生效（tool_registry 注入缺失）|
| S2: web_search 从 SAFE_TOOL_ALLOWLIST 移除 | ✅ 代码确认已移除 |

**Highest Required Action**: fix-implementation

**needs_re_review**: true
