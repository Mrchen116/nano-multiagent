# feat-385 — 验收报告

> 对齐: spec.md v1 — System Prompt Runtime 切段式 + Memory 闭环修复

## Round 1 — 2026-05-29

### Verdict

**fail**

### Highest Required Action

fix-implementation

### Issues Count

- Blocking: 0
- Major: 2
- Minor: 0

---

## 用户旅程体验

### 旅程 1 (Req-1 Scenario 1 + Req-3 Scenario 1/2): memory 跨 session 感知 + 工具调用验证

**环境**: Worktree 全栈（IM port 60520, Kernel API port 60521, Gateway PID 90133），使用 `scripts/e2e-up.sh` 启动。

**步骤**:
1. 在 `default-agent` workspace 的 `.nanoassistant/memory/MEMORY.md` 中预写三条已知用户偏好：`user_preference_no_emoji`、24 小时制、Python `.venv/` 习惯。
2. 调用 Kernel API `POST /v1/prompt-preview` 验证 `## Available Tools` 不出现。
3. 直接通过 Python API 模拟 `_ensure_memory_snapshot` + `resolve_effective_prompt` 验证 runtime system prompt 内容。

**观察**:
- `## Available Tools` 段在 preview 和 runtime 均不出现 ✓
- `user_preference_no_emoji`、24 小时制、`.venv/` 均出现在 runtime system prompt ✓
- `pa.memory_intro` 已删除，不再误导 model 走错路径 ✓
- `core.memory_block` (order=950) 和 `core.user_profile_block` (order=960) 均在 CORE_SECTIONS 中正确注册 ✓

### 旅程 2 (Req-1 Scenario 2): 新 agent 空 memory 行为

**步骤**: 创建临时新目录模拟全新 agent（`.nanoassistant/memory/` 不存在），调用完整段式装配。

**观察**:
- `MemoryStore.format_for_prompt("memory")` 在 memory_root 不存在时返回非 None 的空 banner 字符串 `'══...MEMORY (your personal notes) [0% — 0/2,200 chars]══...'`
- `core.memory_block` 的 `enabled_when` 判 `ctx.memory_block is not None`，空 banner 为 truthy，导致段激活
- 结果：新 agent system prompt 末尾出现两个空 banner（MEMORY + USER PROFILE），对 LLM 是噪音 ✗
- Spec Scenario 2 THEN："不出现'memory 为空'之类的显式提示扰动对话" — 违反

### 旅程 3 (Req-1 Scenario 3): 关闭 Memory Curation 后不再 memory 感知

**步骤**: 模拟 PA Gateway 格式（`agent_features: {"memory_curation": False}`），验证 `resolve_flags_from_metadata` 返回 False，进而跳过 memory 读取和段渲染。

**观察**:
- 当 `agent_features["memory_curation"] = False` 时，flags 正确返回 False ✓
- memory_block / user_profile_block 均为 None，不注入 system prompt ✓
- 注意：从 Kernel API 直接创建 session（无 `agent_features`，只有 `self_evolution`）的 session 永远使用默认值 True，这是预期行为（PA Gateway 负责注入 `agent_features`）

### 旅程 4 (Req-2 Scenario 1): coding agent 既有行为不退化

**步骤**: 用 `local_coding` product 的 CORE_SECTIONS + LC_SECTIONS 渲染 system prompt。

**观察**:
- `actions_care`（风险动作确认）：✓ ("reversibility", "blast radius" 出现)
- `tone_style`（`file_path:line_number` 格式）：✓
- `tool_rules`（工具使用优先）：✓
- `## Available Tools`：不出现 ✓

### 旅程 5 (Req-2 Scenario 2): PA agent 群聊/单聊既有协议不退化

**步骤**: 用 PA product 的所有 sections 渲染群聊上下文 system prompt。

**观察**:
- `NO_REPLY` 协议：✓
- `send_message` 路由边界：✓
- Platform Policy：✓
- `web_fetch` 不可信内容警告：✓
- `pa.memory_intro` 已删除（不再误导 model 读 workspace root 的 MEMORY.md）：✓

### 旅程 6 (Req-4 Scenario): preview 与 runtime 一致性

**步骤**: 调用 `POST /v1/prompt-preview`，与直接调用段式装配的 runtime 产物对比。

**观察**:
- Stable 段（前 100 字节）一致：✓
- 时间占位符 `<运行时注入：当前时间>`：✓ 出现
- cwd 占位符 `<运行时注入：workspace 路径>`：✓ 出现
- `core.memory_block` / `core.user_profile_block` 在 preview 中**完全不出现**：无占位符、无 "memory 段未在预览中显示" 的说明 ✗
- Spec Req-4 THEN："volatile 段(memory_block / 时间)在预览中以可识别的占位符呈现，且预览底部明确说明该差异" — 仅时间/cwd 有占位符，memory 段静默缺失，无任何说明

---

# Round 2 — 2026-05-29

## Verdict

**pass**

## Highest Required Action

pass

## Issues Count

- Blocking: 0
- Major: 0
- Minor: 0

---

## Round 2 复验摘要

M2-fix-r1 合入了 4 个 roadpoint 修复：

- **I1 修复**(R1): `MemoryStore.format_for_prompt` 空内容/不存在时返回 `None`，段通过 `enabled_when` 自动失活
- **I2 修复**(R2): `/v1/prompt-preview` 端点对 volatile 段（cache_safe=False）以 `[<name> — runtime fills]` 占位符渲染，末尾追加 `---` 分隔的 volatile 差异说明块
- **W1 接通**(R3): `AgentLoop` 新增 `on_compaction` callback，`_maybe_compact` 成功后回调 `_invalidate_memory_snapshot`
- **W2 清理**(R4): 彻删老常量 `LOCAL_CODING_SYSTEM_PROMPT`/`CODING_SYSTEM_PROMPT`/`_DEFAULT_TOOL_SPECS`，同步退役测试引用

本轮走用户旅程复验如下。

---

## 复验用户旅程

### 旅程 1: Issue 1 复验 — 新 agent 无 memory 时空 banner 消除（Req-1 Scenario 2）

**步骤**:
1. 用 `tempfile.TemporaryDirectory()` 模拟全新 agent，`memory_root` 目录不存在
2. 构造 `MemoryStore(memory_root=<不存在目录>)`，调用 `format_for_prompt('memory')` 和 `format_for_prompt('user')`
3. 用返回值装配完整 `PromptContext` + `assemble_system_prompt(CORE_SECTIONS, ctx)`
4. 追加：`memory_root` 存在但为空目录同样验证

**观察**:
- `memory_root` 不存在时：`mem_block is None: True`，`user_block is None: True` ✓
- `memory_root` 存在但为空目录时：同样返回 `None` ✓
- 完整 system prompt 中无 `0% —` 空 banner 字符 ✓
- System prompt 长度 4443（合理，无冗余段）✓

```
PASS: Both blocks are None for new agent - no empty banners
PASS: Req-1 Scenario 2 — new agent empty memory produces no banners
```

---

### 旅程 2: Issue 2 复验 — preview volatile 段占位符 + 说明（Req-4 Scenario）

**步骤**:
1. 启动全栈（e2e-up.sh，IM=55987, API=55988）
2. 用 nano/nano1234 登录 IM，拿 token
3. `POST $API_URL/v1/prompt-preview`，`agent_id=default-agent`，`memory_curation=True`
4. 检查 preview prompt 末尾内容

**观察**:
- `<运行时注入：当前时间>` 出现 ✓
- `<运行时注入：workspace 路径>` 出现 ✓
- `---` 分隔线出现在 preview 末尾 ✓
- `以上预览不包含 volatile 段(memory_block / user_profile_block / 时间等)，runtime 装配时实填:` 出现 ✓
- `[core.memory_block — runtime fills]` 出现 ✓
- `[core.user_profile_block — runtime fills]` 出现 ✓
- `[pa.communication_context — runtime fills]` 出现 ✓（PA 产品的另一个 volatile 段）
- `## Available Tools` 不出现 ✓

```
Last 300 chars of preview:
'...Current date and time: <运行时注入：当前时间>\nCurrent working directory: <运行时注入：workspace 路径>\n\n---\n以上预览不包含 volatile 段(memory_block / user_profile_block / 时间等)，runtime 装配时实填:\n[core.memory_block — runtime fills]\n[core.user_profile_block — runtime fills]\n[pa.communication_context — runtime fills]'
```

Spec Req-4 THEN 要求：`volatile 段(memory_block / 时间)在预览中以可识别的占位符呈现，且预览底部明确说明该差异` — **完全满足** ✓

---

### 旅程 3: 回归验证 — 其余 Round 1 pass 项不退化

**Req-1 Scenario 1**（既有 memory 跨 session 感知）:

```
mem_block contains emoji pref: True
mem_block contains .venv: True  
user_block contains 24-hour: True
System prompt length: 5101
System prompt contains emoji pref: True
System prompt contains .venv: True
System prompt contains 24: True
PASS: Req-1 Scenario 1 — existing memory injected into new session
```

**Req-1 Scenario 3**（关闭 Memory Curation 后不再感知）:

```
memory_curation flag: False
Unique marker NOT in rendered: True
MEMORY banner NOT in rendered: True
PASS: Req-1 Scenario 3 — memory_curation OFF suppresses memory content
```

**Req-2 Scenario 1**（coding agent 不退化）:

```
PASS: actions_care (reversibility)
PASS: tone_style (file_path:line_number)
PASS: no ## Available Tools
```

**Req-2 Scenario 2**（PA agent 协议不退化）:

```
PASS: NO_REPLY protocol
PASS: send_message routing
PASS: no pa.memory_intro
PASS: no ## Available Tools
```

**Req-3 Scenario 1**（工具仍通过 API 通道注册，prompt 无 `## Available Tools`）:

```
Tools count: 11
Names: ['read', 'write', 'edit', 'bash', 'agent', 'task_stop', 'web_fetch', 'send_message', 'web_search', 'skill_manage', 'memory']
```

---

## 全套测试

```
2193 passed, 22 skipped, 3 xfailed
1 failed: test_dispatch_handler_build_aiohttp_handler_returns_callable
  (aiohttp 依赖未安装，与 feat-385 无关，git blame 显示该测试预存在于更早的 milestone)
```

---

## 验收标准覆盖（Round 2 更新）

### Requirement: Agent 跨 session 持续感知既有 memory — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 既有 memory 在新 session 启动时被 agent 感知 | spec.md Req-1 | 旅程 3: 预写 memory 条目，新 session 装配 system prompt，确认内容出现 | emoji pref / .venv / 24-hour 均出现在 rendered prompt (len=5101) | **pass** | 继承 Round 1 pass |
| 新 agent 没有任何 memory 时不报错也不显眼 | spec.md Req-1 | 旅程 1: memory_root 不存在 / 目录为空两种场景，format_for_prompt 返回 None，完整 system prompt 无空 banner | mem_block=None, user_block=None; 无 0% banner; len=4443 | **pass** | Round 1 fail → Round 2 fix 关闭 |
| 关闭 Memory Curation 后 agent 不再表现 memory 感知 | spec.md Req-1 | 旅程 3: memory_curation=False, 检查唯一 marker 不出现在 rendered prompt | Unique marker not in rendered, MEMORY banner not in rendered | **pass** | 继承 Round 1 pass |

### Requirement: Runtime 行为相对当前不退化 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| coding agent 既有任务流不退化 | spec.md Req-2 | 旅程 3: LC product 装配，检查 actions_care/tone_style 关键词 + 无 ## Available Tools | reversibility ✓, file_path:line_number ✓, ## Available Tools 不出现 ✓ | **pass** | 继承 Round 1 pass |
| PA agent 群聊/单聊既有协议不退化 | spec.md Req-2 | 旅程 3: PA product 装配，检查 NO_REPLY / send_message / pa.memory_intro 删除 | NO_REPLY ✓, send_message ✓, pa.memory_intro 已删 ✓ | **pass** | 继承 Round 1 pass |

### Requirement: System prompt 不再列举工具，工具调用走 API 原生通道 — 组内结论: **pass (Scenario 3 not-applicable)**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| prompt preview 不含 `## Available Tools` 段 | spec.md Req-3 | 旅程 2: POST /v1/prompt-preview 检查响应内容 | ## Available Tools 不出现 ✓ | **pass** | 继承 Round 1 pass |
| 所有当前工具仍可被 agent 正常调用 | spec.md Req-3 | 旅程 3: GET /v1/tools 确认 11 个工具全部注册 | 11 个工具全在列 (read/write/edit/bash/agent/task_stop/web_fetch/send_message/web_search/skill_manage/memory) | **pass** | 继承 Round 1 pass |
| 某 provider 不透传 tools 通道时错误直接暴露 | spec.md Req-3 | 不可验证（无现成不支持 tools 的 provider） | N/A | **not-applicable** | 继承 Round 1 not-applicable |

### Requirement: prompt-preview 与 runtime 完全一致 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 预览反映 agent 真实接收的系统提示词 | spec.md Req-4 | 旅程 2: POST /v1/prompt-preview，检查 datetime/cwd 占位符 + memory_block 占位符 + volatile 说明块 | 时间/cwd 占位符 ✓；[core.memory_block — runtime fills] ✓；[core.user_profile_block — runtime fills] ✓；底部差异说明 ✓ | **pass** | Round 1 fail → Round 2 fix 关闭 |

---

## Side Findings

- 全套测试中 1 个预存在失败 `test_dispatch_handler_build_aiohttp_handler_returns_callable`，根因是 `aiohttp` 依赖未安装，与 feat-385 完全无关，git blame 显示该测试来自更早的 milestone
- `pa.communication_context` 段（PA 产品的 volatile 段）也正确出现在 preview 的 volatile 占位符列表中，表明修复具有通用性，不止覆盖 memory_block/user_profile_block

---

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新
- [x] `docs/内核设计SPEC.md`：无需更新（低优先级，implementation detail）
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] 相关产品 SPEC（NodeGateway / CodingCLI 等）：无需更新

---

## Issues

### Issue 1: 新 agent 无 memory 时 system prompt 出现空 banner（major）

**Severity**: major

**现象**: 新创建 agent 或 memory_root 目录不存在时，`MemoryStore.format_for_prompt()` 返回非 None 的空标题字符串 `'══...MEMORY (your personal notes) [0% — 0/2,200 chars]══...\n══...USER PROFILE (who the user is) [0% — 0/1,375 chars]══...'`。由于 `core.memory_block` 和 `core.user_profile_block` 段的 `enabled_when` 只检查字段是否为 None，空 banner 为 truthy 导致这两段被激活，注入到 system prompt 末尾。用户对话时 LLM 收到两个语义为空的 memory 标题，是不必要的 token 消耗和行为扰动。

**证据**:
```
══════════════════════════════════════════════
MEMORY (your personal notes) [0% — 0/2,200 chars]
══════════════════════════════════════════════


══════════════════════════════════════════════
USER PROFILE (who the user is) [0% — 0/1,375 chars]
══════════════════════════════════════════════
```

**Recommended Action**: fix-implementation

**Action Rationale**: `MemoryStore.format_for_prompt` 在 memory_root 不存在或文件为空时应返回 `None`（而非空标题字符串），或者 `core.memory_block` / `core.user_profile_block` 段的 `enabled_when` 应检查内容长度而非 None。

---

### Issue 2: prompt-preview 中 memory_block/user_profile_block 段静默缺失，无占位符和说明（major）

**Severity**: major

**现象**: 调用 `POST /v1/prompt-preview` 时，`core.memory_block` 和 `core.user_profile_block` 两个 volatile 段完全不出现在预览内容中——既无占位符、preview 末尾也无任何关于"memory 段在真实对话中存在但预览未显示"的说明文字。用户在 IM 配置页查看"系统提示词预览"时，无法感知到实际 runtime 提示词中还有一大段 memory 内容会注入，导致预览信息失真。

**证据**: 完整 preview 内容末尾：
```
Current date and time: <运行时注入：当前时间>
Current working directory: <运行时注入：workspace 路径>
```
（无 memory 段占位符，无任何 volatile 段未显示的说明）

Spec Req-4 Scenario THEN 原文：
> 预览内容与 agent 在真实对话中接收的系统提示词在所有 stable 段上字节一致；volatile 段(memory_block / 时间)在预览中以可识别的占位符呈现，且预览底部明确说明该差异

**Recommended Action**: fix-implementation

**Action Rationale**: 需要在 preview 末尾添加两行占位符（例如 `<运行时注入：MEMORY 内容>` / `<运行时注入：USER PROFILE 内容>`）以及说明文字（例如 "memory 段在真实对话中动态注入，此处以占位符表示"）。

---

## 验收标准覆盖

### Requirement: Agent 跨 session 持续感知既有 memory — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 既有 memory 在新 session 启动时被 agent 感知 | spec.md Req-1 | 旅程 1: 预写 MEMORY.md 三条偏好，Python 端到端调用 _ensure_memory_snapshot + resolve_effective_prompt，检查 runtime system prompt 包含偏好内容 | user_preference_no_emoji、24小时制、.venv/ 均出现在渲染 prompt 中 (len=7923) | **pass** | |
| 新 agent 没有任何 memory 时不报错也不显眼 | spec.md Req-1 | 旅程 2: 临时新目录（无 memory 文件），完整段式装配，检查 system prompt 不含显式空 banner | system prompt 末尾出现两个 [0% — 0/2,200 chars] 空 banner；见 Issue 1 | **fail** | `MemoryStore.format_for_prompt` 在 memory_root 不存在时返回非 None 空 banner，`enabled_when` 判 None 导致段被激活 |
| 关闭 Memory Curation 后 agent 不再表现 memory 感知 | spec.md Req-1 | 旅程 3: `agent_features: {"memory_curation": False}` 模拟 Gateway 格式，验证 flags 正确返回 False + system prompt 不含 memory 内容 | memory_block=None，rendered 不含偏好内容，len=7029 | **pass** | 注：从 Kernel API 直接创建 session (无 agent_features) 永远用默认值 True，这是预期行为 |

### Requirement: Runtime 行为相对当前不退化 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| coding agent 既有任务流不退化 | spec.md Req-2 | 旅程 4: LC product 完整段式装配，检查 actions_care / tone_style / tool_rules 关键内容 + 无 ## Available Tools | "reversibility"、"file_path:line_number"、"dedicated tool" 均出现，## Available Tools 不出现 | **pass** | |
| PA agent 群聊/单聊既有协议不退化 | spec.md Req-2 | 旅程 5: PA product 群聊上下文装配，检查 NO_REPLY / send_message / Platform Policy / web_fetch 内容 | 所有关键协议词均出现，pa.memory_intro 已删 | **pass** | |

### Requirement: System prompt 不再列举工具，工具调用走 API 原生通道 — 组内结论: **pass (Scenario 3 not-applicable)**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| prompt preview 不含 ## Available Tools 段 | spec.md Req-3 | 旅程 1/6: POST /v1/prompt-preview 检查响应内容 | `'## Available Tools' in prompt` 为 False；section_count=16 | **pass** | |
| 所有当前工具仍可被 agent 正常调用 | spec.md Req-3 | GET /v1/tools 获取工具列表，确认 11 个工具均存在（read/write/edit/bash/agent/task_stop/web_fetch/send_message/web_search/skill_manage/memory） | 11 个工具全部在列，通过 API tools=[] 通道传递 | **pass** | 无真实 LLM 可驱动完整对话调用验证，以工具注册为辅助证据 |
| 某 provider 不透传 tools 通道时错误直接暴露 | spec.md Req-3 | 验证 system prompt 中不含 ## Available Tools 兜底文字 | ## Available Tools 在 preview 和 runtime 均不出现，无任何工具文字兜底 | **not-applicable** | 此 Scenario 是保证机制（不做 fallback），非用户可观察行为，无法通过真实 provider 旅程验证（无现成不支持 tools 的 provider） |

### Requirement: prompt-preview 与 runtime 完全一致 — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 预览反映 agent 真实接收的系统提示词 | spec.md Req-4 | 旅程 6: 对比 POST /v1/prompt-preview 与直接段式装配 runtime 产物；检查 stable 段一致性 + volatile 段占位符 + 底部说明 | Stable 段前 100 字节一致 ✓；时间/cwd 有占位符 ✓；memory_block/user_profile_block 完全不出现且无说明 ✗ | **fail** | 见 Issue 2 |

---

## Side Findings

- MemoryTool per-session 隔离验证通过：agent A 和 agent B 的 `_resolve_memory_root` 返回不同路径，`_fixed_memory_root` 为 None（bootstrap 不再传固定路径）
- `local_store.py` seed 位置已正确改到 `.nanoassistant/memory/`；workspace root 只有 HEARTBEAT.md，不再有错误位置的 MEMORY.md
- `tests/contract/test_no_hardcoded_workspace_dirname.py` 通过
- 测试套件全绿：2186 passed, 22 skipped, 3 xfailed
- contract test `test_prompt_preview_runtime_parity` 通过（仅验证 stable 段，未验证 volatile 段占位符，因此未发现 Issue 2）
- workspace root 下的空 MEMORY.md/USER.md 是早期我手动 cat 测试时误判；实际工作目录内 MEMORY.md 只在 `.nanoassistant/memory/` 下

---

## 上层文档同步

- [x] `SPEC.md`（架构总览）：无需更新（runtime 切段式是内部实现变化，SPEC 的模块职责描述不变）
- [x] `docs/内核设计SPEC.md`（agent 内核）：可能需要补充 `_ensure_memory_snapshot` 和 `MemorySnapshot` 的描述，但属于 implementation detail，不是外部接口变更，低优先级
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] 相关产品 SPEC（NodeGateway / CodingCLI 等）：无需更新（memory 闭环修复对外行为描述已在 spec.md 体现）

---

## User Journeys Exercised

1. **旅程 1**: 既有 memory 跨 session 感知（Req-1 S1 + Req-3 S1/2） — 预写 memory → 段式装配 → runtime prompt 包含 memory 内容，no Available Tools
2. **旅程 2**: 新 agent 空 memory 场景（Req-1 S2） — 新目录 → 段式装配 → 发现空 banner 注入
3. **旅程 3**: 关闭 memory_curation（Req-1 S3） — agent_features 格式 → flags 正确 → memory 不注入
4. **旅程 4**: coding agent 行为不退化（Req-2 S1） — LC product 完整装配 → 关键内容检查
5. **旅程 5**: PA agent 群聊/单聊协议不退化（Req-2 S2） — PA product 群聊上下文 → 协议内容检查
6. **旅程 6**: preview 与 runtime 一致性（Req-4 S1） — POST /v1/prompt-preview + 直接装配对比
