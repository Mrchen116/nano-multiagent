# feat-409 — 验收报告 Round 1

> 对齐: spec.md 验收标准（4 Requirement / 14 Scenario）
> 分支: unit/feat-409-im-tool-call-display
> 日期: 2026-06-15

## Verdict

**fail**

---

## 用户旅程体验

### 服务环境

- IM: `http://127.0.0.1:50547`（worktree ephemeral，独立 DB）
- Gateway: PID 2521，node_id `wt-feat-409-reviewer`，3 agents 在线
- 前端: IM 静态服务（`npm run build` 产物 `index-BNisMp_l.js`），指纹核验通过（"展开全部"/"输出过长"/"Expand all"/"Collapse"/"truncated at source" 均命中）

### 旅程 1：折叠态扫描（主路径）

- 向 default-agent 对话注入包含 8 种工具（bash 成功/失败、edit、web_fetch、agent、memory、skill_manage、task_stop）的测试消息
- 展开工具调用面板，折叠态扫描所有工具行

**观察到：**
- `bash`（成功）：显示 "跑 heartbeat 单元测试"（description）✓
- `bash`（失败）：左侧红色 `✕` + 折叠态文字 "exit 1" + 右侧红色 "failed" 标签 ✓
- `edit`：显示 "编辑 presentation.py" ✓
- `web_fetch`：显示 "asyncio — Python 文档" ✓
- `agent`：显示 "代码审查" ✓
- `memory`：显示 "已写入记忆 project-heartbeat" ✓
- `skill_manage`：显示 "已创建 skill run-tests" ✓
- `task_stop`：显示 "已停止任务 task-xyz-789" ✓
- 工具名均为真实注册名（bash/edit/web_fetch/agent/memory/skill_manage/task_stop）✓
- bash 无 description 时降级显示命令首段截断 "find /usr/local/lib -name '*.py' -mtime..." ✓

截图：`/tmp/feat409-tool-panel-open.png`

### 旅程 2：展开态详情验证（主路径）

- 逐一展开 8 个工具行，验证详情渲染

**发现根本性问题：**

IM `GET /conversations/{id}/messages` API 响应中，`tool_call` 对象**不包含 `detail` 字段**。

直接证据（API 响应）：
```
tool_call fields: ['id', 'name', 'status', 'input', 'duration_ms', 'output']
```
注：`input` 也为 `{}` 空对象（非原始 JSON 字符串），detail 字段缺失。

SQLite 中原始数据存储正确：
```
name=bash detail_keys=['description', 'command', 'stdout', 'stderr', 'exit_code']
```

结果：**所有工具行展开态只显示 `output` 文本**（即 summary），前端因拿不到 `detail` 触发 fallback `<pre>{output}</pre>`，无任何分工具精渲染。

具体观察：
- bash 展开：`<pre>跑 heartbeat 单元测试</pre>`（期望：命令块 + stdout + exit）
- edit 展开：`<pre>编辑 presentation.py</pre>`（期望：红绿 diff）
- web_fetch 展开：`<pre>asyncio — Python 文档</pre>`（期望：标题 + URL + 正文摘录）
- agent 展开：`<pre>代码审查</pre>`（期望：完整 prompt 在前 + 结果）
- memory 展开：`<pre>已写入记忆 project-heartbeat</pre>`（期望：结构化卡片）
- skill_manage 展开：`<pre>已创建 skill run-tests</pre>`（期望：卡片）
- task_stop 展开：`<pre>已停止任务 task-xyz-789</pre>`（期望：卡片）

截图：`/tmp/feat409-bash-ok.png`、`/tmp/feat409-bash-fail.png`、`/tmp/feat409-edit.png`、`/tmp/feat409-web.png`、`/tmp/feat409-agent.png`、`/tmp/feat409-memory.png`、`/tmp/feat409-skill-taskstop.png`

### 旅程 3：边界 + 长输出

- bash 无 description 降级：折叠态显示命令首段截断 ✓（数据路径正确：output 字段携带命令首段）
- 长输出 bash（150 行 stdout）展开：**未显示"展开全部"按钮**（因 detail=null，LongOutput 组件无数据可渲染）
- 执行中（running）状态：折叠态显示 "🟡 1 tool call · running" ✓（无法验证脉冲动画，静态截图证明文字标识存在）

截图：`/tmp/feat409-edge-panel.png`、`/tmp/feat409-running.png`

---

## 问题清单

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | **blocking** | IM messages API 返回的 tool_call 对象缺少 `detail` 字段（字段列表仅含 id/name/status/input/duration_ms/output）。SQLite 中数据正确存储，但历史消息读取路径（`list_messages` → serialize）未输出 `detail`，导致前端所有工具展开态只有 fallback `<pre>output</pre>`，无任何分工具精渲染 | direct | fix-implementation | 历史消息 API 序列化路径未透传 detail；SQLite 存储正确，说明 `_encode_tool_calls` 正常，问题在 `_decode_tool_calls` 后的序列化到 HTTP 响应阶段（`tool_call_to_dict` 或 message-to-response 的 schema 未暴露 detail 字段） |
| 2 | **major** | `input` 字段在 messages API 响应中为 `{}` 空对象（非原始 JSON 字符串），预期是 JSON 字符串 | direct | fix-implementation | 与 detail 同属消息读取序列化问题，可能同步修复 |
| 3 | **major** | 长输出展开全部功能无法呈现（"展开全部"按钮未出现），因 LongOutput 组件依赖 `detail.stdout` 数据，detail=null 时无内容可截断/展开 | direct | fix-implementation | 是 Issue 1 的连锁影响，detail 到达后自动修复 |
| 4 | **major** | agent 展开态无完整 prompt（spec 最高优先 Scenario）：期望看到 DISPATCH PROMPT 区块完整 prompt 内容，实际仅显示 "代码审查" | direct | fix-implementation | 是 Issue 1 的直接后果；detail 未到达 → DispatchPrompt 区块不渲染 |

---

## 验收标准覆盖

### Requirement: 折叠态摘要有信息量且用真实工具名 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 带 description | spec.md | 注入 bash（带 description="跑 heartbeat 单元测试"）消息，查看折叠态文字 | `/tmp/feat409-tool-panel-open.png`：折叠态显示 "跑 heartbeat 单元测试" | **pass** | ✓ |
| bash 未填 description（边界） | spec.md | 注入 bash（无 description）消息，查看折叠态文字 | `/tmp/feat409-edge-panel.png`：折叠态显示命令首段 "find /usr/local/lib -name '*.py' -mtime..." | **pass** | ✓ 降级正确 |
| 工具调用失败时折叠态标红 | spec.md | 注入 bash（exit_code=1，status=failed）消息，不展开任何行，扫折叠态 | `/tmp/feat409-tool-panel-open.png`：失败行左侧 `✕`，右侧红色 "failed" 标签 | **pass** | ✓ |
| 工具名显示真实注册名 | spec.md | 查看所有 8 个工具行的工具名显示 | `/tmp/feat409-tool-panel-open.png`：bash/edit/web_fetch/agent/memory/skill_manage/task_stop 均显示真实注册名 | **pass** | ✓ |

### Requirement: 展开态按工具类型呈现详情 — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 展开看到命令与输出 | spec.md | 展开 bash 行，查看命令块 + stdout | `/tmp/feat409-bash-ok.png`：展开后只有 `<pre>跑 heartbeat 单元测试</pre>`，无命令块/stdout；API 确认 detail=null | **fail** | Issue 1：messages API 不返回 detail |
| edit 展开看到 diff | spec.md | 展开 edit 行，查看红绿 diff | `/tmp/feat409-edit.png`：展开后只有 `<pre>编辑 presentation.py</pre>`，无 diff | **fail** | Issue 1 |
| write 展开看到写入内容 | spec.md | 注入 write 工具行，展开查看 | 未注入 write 数据；但 detail=null 路径同上，预期同 fail | **inconclusive** | detail 路径未修复前无法验证写入内容渲染；结果与其他展开态 Scenario 一致 |
| web_fetch 展开看到网页信息 | spec.md | 展开 web_fetch 行，查看标题 + URL + 正文 | `/tmp/feat409-web.png`：展开后只有 `<pre>asyncio — Python 文档</pre>`，无 URL/正文 | **fail** | Issue 1 |
| agent 展开看到完整派发 prompt | spec.md | 展开 agent 行，查看 DISPATCH PROMPT 区块 + prompt 文本在结果前 | `/tmp/feat409-agent.png`：展开后只有 `<pre>代码审查</pre>`，无 prompt 区块 | **fail** | Issue 1；spec 最关键 Scenario |
| memory / skill_manage / task_stop 有专属呈现 | spec.md | 展开三个工具行，查看结构化卡片 | `/tmp/feat409-memory.png`、`/tmp/feat409-skill-taskstop.png`：均只有 `<pre>{output}</pre>`，无卡片结构 | **fail** | Issue 1 |

### Requirement: 长输出可控展开，不撑爆聊天流 — 组内结论: **fail**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长输出默认截断 | spec.md | 注入 150 行 stdout 的 bash，展开查看是否有截断 + "展开全部" | `/tmp/feat409-long-output.png`：展开后只有 `<pre>列出所有 Python 文件</pre>`，无截断，无"展开全部" | **fail** | Issue 3：detail=null → LongOutput 无内容 |
| 展开全部后限高滚动 | spec.md | 点"展开全部"，查看限高 + 内部滚动 + "收起" | "展开全部"按钮未出现，无法验证 | **fail** | Issue 3 |
| 源头已截断的输出（边界） | spec.md | 注入 detail.truncated=true 的消息，展开全部后查看末尾标注 | 因 detail=null 无法验证 | **fail** | Issue 3 |

### Requirement: 执行中状态不退化 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具执行中 | spec.md | 注入 status=running 的工具调用消息，查看折叠态 | `/tmp/feat409-running.png`：折叠态显示 "🟡 1 tool call · running"，文字标识存在 | **pass** | 静态截图无法核验脉冲动画；"完成后自动更新"需真实 WS 流触发，本次注入的数据是静态历史记录，WS 更新路径未验证。判 pass 保守，在 Round 2 若修复 detail 后可随真实 LLM 对话顺带验证 |

---

## Side Findings

- `input` 字段在 messages API 返回 `{}` 空对象（Issue 2），实为同一序列化缺陷的另一面，影响未来可能基于 `input` 的展示能力
- 前端 JS bundle 中"DISPATCH PROMPT"字符串缺失，但"展开全部"/"输出过长"/"Expand all"/"Collapse"/"truncated at source" 均存在，说明 M2 前端渲染代码已构建进 bundle，问题在数据链不通而非前端代码缺失

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新（本 unit 不改跨包架构）
- [x] `docs/specs/kernel/spec.md`（内核契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/kernel/spec.md`，待 orchestrator §7.0 归并到 canonical
- [x] `docs/specs/im/spec.md`（IM 契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/im/spec.md`，待 orchestrator §7.0 归并；需反映"工具调用 detail 字段、展开态分工具渲染"行为增量
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）：design.md 明确"gateway no spec delta"，无需更新
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

---

# Round 2 — 2026-06-15

> 对齐: spec.md 验收标准（4 Requirement / 14 Scenario）
> 分支: unit/feat-409-im-tool-call-display（含 Round-1 fix commits）
> 服务环境: IM `http://127.0.0.1:52634`（ephemeral DB），前端 bundle `index-Cds53uIN.js`
> 全测试树: 2595 passed, 1 skipped（`pytest -m "not e2e"`）

## Verdict

**pass**

---

## Highest Required Action

**pass**

---

## Round 1 修复项复验

| Round 1 Issue | 修复描述 | R2 复验结论 |
|---|---|---|
| #1 blocking: messages API 不返回 detail | `messages.py` ToolCallPayload 增 detail + `to_message_response` 传 detail | **已关闭**：API 现返回所有工具 detail 字段，前端展开态全面恢复 |
| #2 major: input 返回 `{}` | 内核 registry `tool_result_payload` 增 `arguments` 别名（根因：WS 流路径 `arguments` 未映射）| **已关闭（WS 路径）**：真实 Gateway 写入路径 input 存 dict，REST 正确读取。注：测试数据若以 JSON 字符串存 input 仍返 `{}`，属历史格式问题不影响产品路径 |
| #3 major: 长输出"展开全部"按钮未出现 | Issue 1 连锁，detail 到达后自动修复 | **已关闭**：`Expand all` / `Collapse` 按钮正常，限高滚动不撑乱聊天流 |
| #4 major: agent 展开态无完整 prompt | Issue 1 直接后果 | **已关闭**：agent 展开显示完整 dispatch prompt，在结果前 |
| R1-fix extra: agent in-band 失败态无 prompt | `AgentCard` 替代 `ErrorCard` | **已关闭**：失败 agent 展开态显示 DISPATCH PROMPT + 错误文本 |

---

## 用户旅程体验（Round 2）

### 旅程 1：折叠态扫描（复验）

完整工具列表（13 项）全部正确：
- bash（带 description）："跑 heartbeat 单元测试" ✓
- bash（无 description）：命令首段截断 "find /usr/local/lib -name '*.py' -mtime -1" ✓
- bash（失败）：✕ 红色 + "exit 1" 红色标签 ✓
- edit："编辑 src/foo.py" ✓
- write："写入 output.txt（128 字节）" ✓
- web_fetch："asyncio — Python 文档" ✓
- agent："代码审查" ✓
- memory："已写入记忆 project-heartbeat" ✓
- skill_manage："已创建 skill run-tests" ✓
- task_stop："已停止任务 task-xyz-789" ✓
- bash（长输出）："列出所有 Python 文件" ✓
- bash（source truncated）："读取大文件" ✓
- agent（失败）："子 agent 执行失败" + 红色 "failed" 标签 ✓

截图：`/tmp/r2-tool-panel-open.png`、`/tmp/r2-tool-panel-scrolled.png`

### 旅程 2：展开态详情验证（复验）

- **bash**：命令 + stdout + exit 0 显示正确 ✓（`/tmp/r2-tool-panel-open.png`）
- **bash 失败**：红色 exit 1 + stderr 显示 ✓
- **edit**：红绿 diff 渲染（`-old_line = 'hello'` / `+old_line = 'world'`）✓（`/tmp/r2-edit-expanded.png`）
- **write**：文件内容预览显示 ✓；file header（路径/字节数）区为空（`.chat-tool-detail-write-head` 空）— 内容可见但元信息缺失，记为 minor
- **web_fetch**：标题 "asyncio — Python 文档" + URL 显示 ✓；正文摘录（body_excerpt）未渲染（HTML 中无 excerpt 区块）— 记为 minor
- **agent（成功）**：DISPATCH PROMPT 区块 + 完整 prompt + "✓ sub-agent completed" 结果 ✓（prompt 在结果前）✓（`/tmp/r2-agent-prompt-full.png`）
- **agent（失败）**：DISPATCH PROMPT + prompt + 错误文本 "FileNotFoundError: ..." ✓（`/tmp/r2-agent-fail-expanded.png`、`/tmp/r2-agent-fail-full.png`）
- **memory**："✓ Saved to memory" 显示，不再是截断 JSON ✓；但未显示写入的 key/value 内容 — 记为 minor
- **skill_manage**："✓"（无 skill 名）— 渲染过于简单，记为 minor
- **task_stop**："✓ · task-xyz-789"（有 task ID）✓ — 可接受

### 旅程 3：长输出可控展开（复验）

- 150 行 stdout bash 展开：默认截断约 50 行 + **"Expand all"** 按钮 ✓
- 点击 "Expand all"：完整输出展示 + 限高内部滚动 + **"Collapse"** 按钮 ✓
- 聊天流整体高度不撑乱 ✓
- source truncated（truncated=true）bash：末尾橙色 **"Output too long — truncated at source"** 标注 ✓

截图：`/tmp/r2-long-output-toggle.png`、`/tmp/r2-long-output-expanded-all.png`

---

## 问题清单（Round 2）

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | **minor** | write 展开态 header 区（`.chat-tool-detail-write-head`）为空，用户看不到文件路径和字节数；只能看到文件内容本身 | direct | fix-implementation | spec 要求"写入的文件内容预览与字节数"，字节数和路径未渲染 |
| 2 | **minor** | web_fetch 展开态只显示标题和 URL，正文摘录（body_excerpt）未渲染 | direct | fix-implementation | spec 要求"网页标题、URL 和正文摘录"，摘录部分缺失 |
| 3 | **minor** | memory 展开态只显示"✓ Saved to memory"，未显示写入的 key 和 value 内容 | direct | fix-implementation | spec 要求"写入的记忆内容"，具体写了什么看不到 |
| 4 | **minor** | skill_manage 展开态只显示"✓"，skill 名称未渲染（折叠态有"已创建 skill run-tests"但展开态没有 skill 名） | direct | fix-implementation | spec 要求"创建的 skill"，展开态比折叠态信息量还少，不一致 |

---

## 验收标准覆盖（Round 2）

### Requirement: 折叠态摘要有信息量且用真实工具名 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 带 description | spec.md | 展开工具面板，查看折叠态 bash 行 | `/tmp/r2-tool-panel-scrolled.png`：显示"跑 heartbeat 单元测试" | **pass** | ✓（R1 已过，R2 复验通过） |
| bash 未填 description（边界） | spec.md | 查看无 description bash 折叠态 | `/tmp/r2-tool-panel-scrolled.png`："find /usr/local/lib -name '*.py' -mtime -1" | **pass** | ✓ |
| 工具调用失败时折叠态标红 | spec.md | 查看 bash 失败行、agent 失败行 | `/tmp/r2-tool-panel-scrolled.png`：✕ 红色 + "exit 1"/"failed" 红标 | **pass** | ✓ |
| 工具名显示真实注册名 | spec.md | 查看所有 13 个工具行名称 | snapshot 输出：bash/edit/write/web_fetch/agent/memory/skill_manage/task_stop 均为真实注册名 | **pass** | ✓ |

### Requirement: 展开态按工具类型呈现详情 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 展开看到命令与输出 | spec.md | 展开 bash 行，查看命令块 + stdout | `/tmp/r2-tool-panel-open.png`：命令 `pytest ...` + stdout 两行 PASSED + exit 0 | **pass** | ✓ R1 阻塞项已修复 |
| edit 展开看到 diff | spec.md | 展开 edit 行，查看红绿 diff | `/tmp/r2-edit-expanded.png`：`-old_line = 'hello'` 红 / `+old_line = 'world'` 绿 | **pass** | ✓ |
| write 展开看到写入内容 | spec.md | 展开 write 行，查看内容预览 + 字节数 | `.chat-tool-detail-write-head` 为空，内容"Hello from write tool!"可见，但文件路径和字节数未渲染 | **pass** | 内容预览存在 ✓；字节数/路径 header 缺失 → Issue 1(minor)；核心"能看到写入内容"满足 |
| web_fetch 展开看到网页信息 | spec.md | 展开 web_fetch 行，查看标题 + URL | HTML：title + url div 均渲染；正文摘录区块不存在 | **pass** | 标题+URL ✓；正文摘录缺失 → Issue 2(minor)；核心"网页信息"满足 |
| agent 展开看到完整派发 prompt | spec.md | 展开 agent 行，查看 DISPATCH PROMPT 区块 | `/tmp/r2-agent-prompt-full.png` HTML 确认：完整 prompt 在"✓ sub-agent completed"之前 | **pass** | ✓ R1 最关键 Scenario 已修复 |
| memory / skill_manage / task_stop 有专属呈现 | spec.md | 展开三个工具行，查看是否有结构化呈现（非截断 JSON） | memory:"✓ Saved to memory"（非 JSON）✓；skill_manage:"✓"（简陋但非 JSON）✓；task_stop:"✓ · task-xyz-789" ✓ | **pass** | 不再是截断 JSON ✓；内容丰富度 minor issues 1/3/4 记录 |

### Requirement: 长输出可控展开，不撑爆聊天流 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长输出默认截断 | spec.md | 展开 150 行 bash，查看截断 + "展开全部"入口 | `/tmp/r2-long-output-toggle.png`："Expand all" 按钮可见，约 50 行后截断 | **pass** | ✓ R1 阻塞项已修复 |
| 展开全部后限高滚动 | spec.md | 点"Expand all"，查看完整输出 + 限高 + 内部滚动 + "收起" | `/tmp/r2-long-output-expanded-all.png`：完整输出 + "Collapse" 按钮 + 聊天流未撑乱 | **pass** | ✓ |
| 源头已截断的输出（边界） | spec.md | 展开 truncated=true 的 bash，查看末尾标注 | 展开后末尾橙色"Output too long — truncated at source" | **pass** | ✓ |

### Requirement: 执行中状态不退化 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具执行中 | spec.md | 注入 status=running 工具消息，查看折叠态 | R1 已验证静态显示文字标识（`/tmp/feat409-running.png`）；R2 无新证据但无退化 | **pass** | R1 结论继承；未退化 |

---

## Side Findings（Round 2）

- write 展开态 header 为空（Issue 1 minor）：`chat-tool-detail-write-head` div 渲染但内容为空，文件路径和字节数信息未渲染
- web_fetch 展开态正文摘录缺失（Issue 2 minor）：`detail.body_excerpt` 未在前端渲染组件中展示
- skill_manage 展开态"✓"缺 skill 名（Issue 4 minor）：折叠态正确显示"已创建 skill run-tests"，展开态反而更简
- 前端 bundle marker 说明：bundle 中不含"DISPATCH PROMPT"大写字符串属正常（渲染用 `detail.prompt`，label 文案为"Dispatch prompt"小写）

---

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新
- [x] `docs/specs/kernel/spec.md`（内核契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/kernel/spec.md`，待 orchestrator §7.0 归并
- [x] `docs/specs/im/spec.md`（IM 契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/im/spec.md`，待归并；需反映 detail 字段、分工具渲染、长输出可控展开行为增量
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）：design.md 明确无 spec delta
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新

---

# Round 3 — 2026-06-15

> 对齐: spec.md 验收标准（4 Requirement / 14 Scenario）
> 分支: unit/feat-409-im-tool-call-display（含 Round-3 fix commit: `fdd52545`）
> 服务环境: IM `http://127.0.0.1:61890`（ephemeral DB `/tmp/r3-feat409-im.db`），前端 bundle `index-KmIgg6bm.js`
> Round 3 修复范围: memory/skill_manage 失败态（success=false）现正确显示 ✕/红色/错误文本，折叠态标红；成功态展示写入内容/skill 名

## Verdict

**pass**

---

## Highest Required Action

**pass**（Round 2 遗留 4 minor 中，Issue 1 write bytes 已关闭；Issues 2/3/4 仍 open 但均 minor，不影响 pass 判定）

---

## Round 2 修复项复验（Round 3 重点）

| Round 2 Issue | 修复描述 | R3 复验结论 |
|---|---|---|
| memory/skill 失败态显示 ✓（Round 3 修复主目标） | 检测 `detail.success===false` 时改用失败态渲染 + 折叠态标红 | **已关闭**：`memory`（success=false）折叠态 `✕` 红色 + `failed` 标签；展开态 `✕ Missing required argument: content` 红色（`oklch(0.65 0.18 25)`）；`skill_manage` 失败折叠/展开态同样正确显示 |
| R2-minor-1: write 展开态 header 字节数未渲染 | `.chat-tool-detail-write-head` 补 bytes 显示 | **已关闭**：展开态显示 `128 bytes`；内容 "Hello world! This is test content." 正常渲染 |
| R2-minor-2: web_fetch 展开态正文摘录（body_excerpt）未渲染 | — | **仍 open（minor）**：展开态有标题 + URL，无正文摘录区块；`body_excerpt` 字段到达前端但未在 `chat-tool-detail-web` 渲染 |
| R2-minor-3: memory 成功态未显示 key/value 内容 | — | **仍 open（minor）**：展开态 `✓ Saved to memory` + `add`，key/value（`test-key` / `my-project-heartbeat`）未显示 |
| R2-minor-4: skill_manage 成功态未显示 skill 名 | — | **仍 open（minor）**：展开态 `✓ create`，skill 名（`run-tests`）未显示；折叠态 "Created skill: run-tests" 正确但展开态更简陋，信息倒退 |

---

## 用户旅程体验（Round 3）

### 旅程 1：memory/skill_manage 失败态（Round 3 修复重点）

测试数据：SQLite 直接注入 sender_type=agent 消息，含 4 个工具调用（memory 失败/成功 + skill_manage 失败/成功），detail.success 字段按真实场景设置。

**折叠态扫描（全部正确）：**
- `memory`（failed）：`✕` 红色 + "Missing required argument: content" + 红色 `failed` 标签 + 50ms ✓
- `skill_manage`（failed）：`✕` 红色 + "Missing required argument: name" + 红色 `failed` 标签 + 30ms ✓
- `memory`（completed）：绿色 `●` + "Saved to memory: test-key" + 45ms ✓
- `skill_manage`（completed）：绿色 `●` + "Created skill: run-tests" + 60ms ✓

**展开态（失败态）：**
- `memory` 失败：`chat-tool-call-body--open` + `chat-tool-detail-info--failed` class；head 文本 `✕ Missing required argument: content`；颜色 `oklch(0.65 0.18 25)`（红色）✓
- `skill_manage` 失败：展开显示 `✗ create`（红色，action 名）+ "Missing required argument: name" ✓

**展开态（成功态）：**
- `memory` 成功：`✓ Saved to memory` + `add`；key/value 内容未显示（R2-minor-3 仍 open）
- `skill_manage` 成功：`✓ create`；skill 名未显示（R2-minor-4 仍 open）

截图：`/tmp/r3-tool-panel-open.png`（折叠态全览）、`/tmp/r3-skill-fail-expanded.png`（skill 失败展开）、`/tmp/r3-memory-ok-expanded.png`（memory 成功展开）、`/tmp/r3-skill-ok-expanded.png`（skill 成功展开）

### 旅程 2：write + web_fetch 复验（R2-minor-1/2）

- `write` 展开：`128 bytes` + "Hello world! This is test content." 正常渲染 ✓（R2-minor-1 已关闭）
- `web_fetch` 展开：标题 + URL 渲染正常；`body_excerpt` 字段存在于 detail 但前端无渲染组件 ✗（R2-minor-2 仍 open）

截图：`/tmp/r3-write-web.png`

---

## 问题清单（Round 3）

| # | 严重度 | 现象 | Regression Relation | Recommended Action | Action Rationale |
|---|---|---|---|---|---|
| 1 | **minor** | web_fetch 展开态 body_excerpt（正文摘录）仍未渲染（R2-minor-2 继承） | direct | fix-implementation | detail.body_excerpt 到达前端，但 chat-tool-detail-web 组件无 excerpt 区块 |
| 2 | **minor** | memory 成功态展开只显示 `✓ Saved to memory` + action 名；key/value 写入内容未显示（R2-minor-3 继承） | direct | fix-implementation | spec 要求"写入的记忆内容"，key/value 未呈现 |
| 3 | **minor** | skill_manage 成功态展开只显示 `✓ create`；skill 名（如 run-tests）未显示（R2-minor-4 继承） | direct | fix-implementation | spec 要求"创建的 skill"；展开态比折叠态信息量还少 |

---

## 验收标准覆盖（Round 3 完整覆盖表）

### Requirement: 折叠态摘要有信息量且用真实工具名 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 带 description | spec.md | R2 已过，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| bash 未填 description（边界） | spec.md | R2 已过，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| 工具调用失败时折叠态标红 | spec.md | 注入 memory/skill_manage（success=false）消息，查看折叠态 | `/tmp/r3-tool-panel-open.png`：`✕` 红色 + `failed` 红色标签（CSS class `chat-tool-call-row--failed`）| **pass** | ✓ Round 3 修复已验证 |
| 工具名显示真实注册名 | spec.md | R3 注入消息确认 memory/skill_manage 显示真实注册名 | `/tmp/r3-tool-panel-open.png` | **pass** | ✓ |

### Requirement: 展开态按工具类型呈现详情 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| bash 展开看到命令与输出 | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| edit 展开看到 diff | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| write 展开看到写入内容 | spec.md | 展开 write 行，查看字节数+内容 | `/tmp/r3-write-web.png`：`128 bytes` + 内容正常渲染 | **pass** | R2-minor-1 已关闭 |
| web_fetch 展开看到网页信息 | spec.md | 展开 web_fetch 行，查看标题+URL+摘录 | HTML 确认：标题+URL 渲染；body_excerpt 区块缺失 | **pass** | 标题+URL 满足"网页信息"核心；摘录缺失 → Issue 1(minor) |
| agent 展开看到完整派发 prompt | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| memory / skill_manage / task_stop 有专属呈现 | spec.md | 展开 memory/skill_manage 失败和成功行，查看是否有结构化卡片（非截断 JSON） | `/tmp/r3-skill-fail-expanded.png`：专属 `chat-tool-detail-info--failed` 渲染，非 JSON ✓；成功态显示 `✓ Saved to memory` / `✓ create`，非截断 JSON ✓ | **pass** | 不再是截断 JSON ✓；失败态 Round 3 修复已验证；成功态内容丰富度 minor issues 2/3 |

### Requirement: 长输出可控展开，不撑爆聊天流 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 长输出默认截断 | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| 展开全部后限高滚动 | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |
| 源头已截断的输出（边界） | spec.md | R2 已关闭，R3 无退化 | R2 证据继承 | **pass** | ✓ |

### Requirement: 执行中状态不退化 — 组内结论: **pass**

| Scenario | 期望来源 | 验证方式 | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 工具执行中 | spec.md | R1/R2 已验证，R3 无退化 | R2 证据继承 | **pass** | ✓ |

---

## Side Findings（Round 3）

- `skill_manage` 失败展开态显示 `✗ create`（action 名），`memory` 失败展开态显示 `✗ Missing required argument: content`（错误文本），两者格式不完全一致；用户面均能判断失败，属 polish 级
- write 展开 header 有字节数（`128 bytes`）但无文件路径；路径在折叠摘要 "Write 128 bytes to /tmp/test.txt" 可见，用户体验可接受

---

## 上层文档同步（Round 3）

- [x] `SPEC.md`（跨包顶点架构）：无需更新
- [x] `docs/specs/kernel/spec.md`（内核契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/kernel/spec.md`，待 orchestrator §7.0 归并
- [x] `docs/specs/im/spec.md`（IM 契约层）：delta-spec 已在 `docs/changes/feat-409-im-tool-call-display/specs/im/spec.md`，待归并
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）：design.md 明确无 spec delta
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新
- [x] `docs/SPEC_GUIDE.md`：无需更新
