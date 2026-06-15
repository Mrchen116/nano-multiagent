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
