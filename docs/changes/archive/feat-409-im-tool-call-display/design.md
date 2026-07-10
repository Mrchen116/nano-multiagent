# feat-409: IM 工具调用展示体验重做 — 技术方案

> 对齐: spec.md v1
>
> Unit branch: `unit/feat-409-im-tool-call-display` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

改动横跨内核 → Gateway → IM relay → 前端四跳:

| 层 | 文件 | 当前职责 |
|---|---|---|
| 内核 presenter | `src/agent/platform/tools/presentation.py` | presenter 类定义(`_BashPresenter` 等)+ `resolve_presenter_for_tool` + `_enforce_cap`(256KB 尾截断) |
| 内核工具 | `src/agent/platform/tools/builtins/{agent,memory,skill_manage,task_stop,web_fetch}.py` | 工具类挂 `presenter` 属性(决策 12 随工具走) |
| 内核工具(死代码) | `src/agent/platform/tools/builtins/task.py` | 未在 `__init__.py` 注册,携 `_TaskPresenter` 从不触发 |
| 实时流 hook | `src/agent/platform/hooks/builtins/realtime_stream.py` | `on_tool_result` 产 tool_end 事件,**已带 `presentation.detail`** |
| Gateway | `src/personal_assistant/main.py:3501-3538`(tool_end) | 把内核事件转 `node.streaming_delta`;**只取 `pres["summary"]`,detail 丢弃** |
| IM 领域 | `src/IM/domain/models.py:184` `ToolCall` | id/name/status/duration_ms/input/output(str),**无 detail** |
| IM relay 解析 | `src/IM/ws/gateway_handler.py` `_parse_tool_call` | streaming_delta dict → ToolCall |
| IM 序列化 | `src/IM/api/ws/event_types.py:38` `tool_call_to_dict` | ToolCall → WS payload(省略未设字段) |
| IM 持久化 | `src/IM/infra/repositories.py` `_encode/_decode_tool_calls` | tool_calls 存 `messages.tool_calls_json` |
| 前端类型 | `src/IM/frontend/src/features/chat/v2/chat-types.ts:31` `ToolCall` | input/output(string),**无 detail** |
| 前端渲染 | `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.tsx` | input/output 裸 `<pre>`,不分工具类型 |
| 前端 reducer | `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts` | `upsertToolCall` 按 id 合并 |

**detail 断点链**:presenter 产出完整 detail → realtime_stream 带上 → **Gateway `main.py:3510-3512` 只读 summary 丢 detail** → 后面 IM 三跳的数据结构里压根没有 detail 字段 → 前端无从渲染。修复要把 detail 一路打通到前端,且 IM 的 ToolCall 结构/序列化/持久化/前端类型都要加 detail。

### 既有约束

- **模块边界**:产品(Gateway / IM)只能 import `agent.sdk`;presenter 类型 `ToolPresenter` / `ToolPresentationEvent` 已由 `agent.sdk` 暴露。本 unit 内核改动落在 `agent.platform.tools`,产品侧不直接 import。
- **presenter 随工具走(refactor-406 决策 12)**:补 presenter = 给工具类挂 `presenter = _XXX_PRESENTER` 属性,**不是**改全局注册表(已无注册表)。`resolve_presenter_for_tool` 读 `getattr(tool, "presenter", None)`。
- **256KB 硬上限**:`_enforce_cap` 对 `stdout/stderr/diff/content` 字段尾截断并置 `truncated:True`。新 presenter 的大字段要走同一 cap;前端"源头已截断"提示读 `detail.truncated`。
- **WS / 持久化体量**:detail 透传后单条 tool_call payload 体量上升(最坏接近 256KB)。需确认 IM WS 帧大小与 `tool_calls_json` 列无更小的隐藏上限。
- **分层文档**:内核 presenter 行为经 `agent.sdk` 被消费者观察 → 有 kernel delta-spec;IM 展示是前端行为,IM 契约层按"用户可观察行为"判断是否产 delta。

### 可复用能力

- **`_enforce_cap` / `_truncate` / `_stringify`**(presentation.py):直接复用,新 presenter 的大字段套 `_enforce_cap`。
- **`_TaskPresenter`**(presentation.py:373):**改用**——它的 detail 结构(description/status/summary/artifacts)与 agent 工具 result 不匹配(agent 是 content/agent_id/output_file),需按 agent 真实 schema 重写为 `_AgentPresenter`,而非原样迁移。
- **realtime_stream 的 detail 透传**:**不用改**——它已正确带 detail,断点在下游 Gateway。
- **前端 `upsertToolCall` 合并逻辑**:复用,只需让 detail 字段参与合并。
- **tool-calls-panel 折叠/展开骨架**:复用顶部总开关 + 逐行结构,只替换每行的详情渲染。

### 相关历史

- **refactor-406**(刚合入,#94):presenter 从全局注册表改为随工具对象走;`products` 装配层解散为消费者工厂;内核三层。本 unit 全部按此新架构落地。
- **feat-337 M5**(遗留,#83 并入本 unit):task→agent 改名未收尾——遗留 task.py 死代码、agent 工具无 presenter、kernel spec 工具清单仍写 task。本 unit 一并清理。

## 架构总览

数据沿单向链路从内核流到前端,本 unit 在**每一跳都补齐 detail 的承载**,不新增跳数、不改交互结构:

```
[内核] tool.presenter.format_end → ToolPresentationEvent{summary, detail}
   │   (补 agent/memory/skill_manage/task_stop presenter;删 task.py)
   ▼
[realtime_stream] tool_end 事件携 presentation.detail   ← 无需改
   ▼
[Gateway main.py tool_end] ★断点:现仅取 summary
   │   → 改为透传 presentation(summary + detail)进 streaming_delta.tool_call
   ▼
[IM relay] ToolCall(+detail) → _parse_tool_call → tool_call_to_dict → 持久化
   │   (domain/parse/serialize/persist 四处加 detail 字段)
   ▼
[前端] ToolCall(+detail) → 折叠态通用渲染 output(presenter 的 summary);展开态按 name 分发精渲染 + 未知工具通用卡片 + 长输出限高滚动
```

**before**:detail 在 Gateway 丢弃,前端只有 `output:string`,裸 `<pre>` 渲染 → `exit=0 elapsed=152ms`。
**after**:summary(人话)+ detail 全程透传;折叠态通用渲染 summary,展开态按 name 精渲染 detail(未知工具走通用卡片)。

## 关键决策

### 决策 1:Gateway 透传整个 `presentation.detail`,不在 Gateway 做裁剪

tool_end 把 `pres["detail"]`(已被内核 `_enforce_cap` 控制在 256KB 内)整体放进 `streaming_delta.tool_call.detail`,Gateway 不二次截断、不重组结构。

- 理由:内核 presenter 是 detail 结构的唯一权威,Gateway 只做透传管道;在 Gateway 裁剪会让"展示什么"逻辑散落两处。256KB 上限已由内核 `_enforce_cap` 兜底,Gateway 无需再设阈值。
- 拒绝备选:Gateway 按工具类型裁剪 detail——违反"presenter 是展示权威",且 Gateway 不应懂工具语义。
- 风险:单条 payload 最坏接近 256KB。见决策 6。

### 决策 2:IM `ToolCall` 增 `detail: dict | None` 字段,贯穿 parse/serialize/persist

`domain/models.py` ToolCall 加 `detail`;`_parse_tool_call` 从 streaming_delta 读 detail;`tool_call_to_dict` 序列化 detail(沿用"省略未设字段");`_encode/_decode_tool_calls` 持久化 detail 进 `tool_calls_json`。`summary` **不**单独加字段——presenter 的 `summary` 已经过 Gateway 落进 IM 的 `output`(`main.py:3511-3512`),折叠态直接用它(见决策 4);本 unit 只需新增 `detail` 这一结构化字段。

- 理由:detail 是结构化 dict,一处贯通即可;summary 已有 `output` 承载,不必在传输层再立一份冗余字段。
- 拒绝备选:同时加 `summary` 独立字段——与现有 `output` 信息重复。
- 风险:`tool_calls_json` 历史行无 detail → 前端渲染必须容忍 `detail` 缺失(老消息回退到 `output` 串)。

### 决策 3:内核补 4 个 presenter,删 task.py;按各工具真实 result schema 定 detail

给 `AgentTool` / `MemoryTool` / `SkillManageTool` / `TaskStopTool` 挂 `presenter` 属性。detail schema 按 grounding 的真实 result/args(见 §接口与数据流)。`_TaskPresenter` 重写为 `_AgentPresenter`(agent 的 result 是 `content/agent_id/output_file`,非 task 的 `summary/artifacts`),删除 `task.py` 与 `_TaskPresenter`。

- 理由:agent 工具的展示是本 unit 最关键诉求(完整派发 prompt),且 #83 要求收尾 task→agent;两件事在同一文件区,合并做。
- **agent presenter 必须把完整 `prompt`(args,不截断)放进 detail 且排在结果前**——这是用户判断派发准确性的关键(spec Scenario)。prompt 不进 `_enforce_cap` 的截断字段集(它截 stdout/stderr/diff/content);派发 prompt 体量恒小(数千字以内),保持完整。
- 拒绝备选:只补 agent、其余三个留默认——spec 明确要求 memory/skill_manage/task_stop 有专属呈现。

### 决策 4:折叠态人话摘要由工具自己的 presenter 产出(`summary`),前端通用渲染

折叠态每行文案 = 内核 presenter 的 `summary` 字段——它本就随 `tool_start`/`tool_end` 产出,且 Gateway 已把 `pres["summary"]` 落进 IM 的 `output`(`main.py:3511-3512`)。前端**只做通用渲染**:显示 summary 文本 + `status==failed` 标红,**不按工具名写折叠态派生分支**。要让 bash 折叠态显示 description,改的是 **bash presenter 的 `summary`**(format_end 由 `exit=N elapsed=Xms` 改为 `args.description`,空则降命令首段),落在 M1 内核侧。其余工具的 summary 同理在 presenter 内产人话(agent→description、web_fetch→`status=200 (title)`、memory/skill→message…)。

- 理由:展示"by 工具"是内核既定原则(决策 12 presentation 随工具走)。把折叠文案放前端按 name 派生,等于**每加一个工具就要改 IM 代码**;用户 DIY / MCP 工具无法改 IM,折叠态必然退化。放 presenter:工具自带 summary 即生效,前端零改动也不报错。
- **DIY 工具(`.nano/tools` 用户工具类)同样受益**:loader 原样注册用户工具对象、不剥属性(`loader.py:_is_tool` 只校验 name/description/input_schema/run),用户在自己工具类上写了 `presenter`(summary + detail),`resolve_presenter_for_tool` 经 `getattr(tool, "presenter", None)` 照样认 —— summary 入 `output`、detail 透传,端到端生效,**无须改 IM 一行**。只有完全没写 presenter 的工具才落默认 presenter(截断参数)。
- 拒绝备选:前端按 name 派生折叠文案(本决策初稿)——违反 by-工具原则,DIY/MCP 失配,新增工具强耦合 IM。
- 关于展开态:结构化 `detail` 同样是 presenter(工具)产出的数据;前端对已知内置工具做**精渲染**(diff 着色、prompt 在前等 *视觉* 修饰),对不认识的 name(自带 presenter 的 DIY / MCP)用**通用结构化卡片**忠实按 key 渲染其 detail(而非裸 JSON)——DIY 工具的 detail 内容照样完整呈现,差别仅在拿不到 bespoke 视觉修饰。
- 代价:emoji 前缀是纯视觉,留前端按 name 映射 + 默认图标兜底(DIY 工具拿通用图标,不阻塞)。

### 决策 5:前端长输出两级展开——默认截断 + "展开全部"限高滚动

每行展开态:大字段(stdout/diff/content)先按前端阈值(如 50 行 / 4KB)截断显示 + "点击展开全部";点开后渲染完整 detail 字段,容器 `max-height` + `overflow:auto` 内部滚动 + "收起"。`detail.truncated===true` 时在末尾标注"输出过长,已在源头截断"。

- 理由:spec 明确要求展开全部不撑爆聊天流;前端阈值与内核 256KB cap 是两级独立关卡(前端管视觉、内核管体量)。
- 拒绝备选:一次性渲染完整 detail——长输出撑乱消息列表滚动位置(spec 反例)。

### 决策 6:detail 体量风险用内核既有 256KB cap 兜底,不为本 unit 新增上限

不为本 unit 新增传输层上限。复核 IM WS 帧 / `tool_calls_json` 列无更小隐藏限制(M1 grounding 项)。agent 的 `prompt` 不纳入 `_enforce_cap`——派发 prompt 体量恒小(数千字以内),不构成体量风险,无需截断。

- 理由:已有 256KB cap(截 stdout/stderr/diff/content)是唯一体量权威,新增上限会与之冲突。stdout/diff 这类才会爆量;prompt/记忆/skill 内容这类小字段不进截断集,保持完整。
- 风险:若 WS/列有更小上限 → M1 暴露后在内核 cap 处下调,而非各跳零散截断。

## 接口与数据流

### 新增 presenter 的 detail schema(按真实 result/args)

```python
# _AgentPresenter (name="agent")  args: description, prompt, subagent_type, background
detail = {
    "description": str,        # args.description
    "prompt": str,             # args.prompt —— 完整不截断,排在结果前(spec)
    "subagent_type": str,      # args.subagent_type | agent_type
    "status": str,             # completed | failed | async_launched | message_queued
    "agent_id": str,           # output.agent_id
    "content": str,            # output.content(前台完成时的结果文本)
    "output_file": str,        # output.output_file(后台/续传时)
    "error": str | None,       # output.error(失败时)
}

# _MemoryPresenter (name="memory")  args: action, target, content
detail = {"action": str, "target": str, "content": str, "message": str, "success": bool}

# _SkillManagePresenter (name="skill_manage")  args: action, name, content
detail = {"action": str, "name": str, "message": str, "path": str, "success": bool}

# _TaskStopPresenter (name="task_stop")  args: task_id
detail = {"task_id": str, "status": str}   # status: killed | <record.status>
```

失败路径统一沿用既有约定:`error` → `summary="failed: …"` + `detail={"error":{"message":…}}`。

### 主流程时序(一次 bash 调用从内核到前端)

```mermaid
sequenceDiagram
    participant K as 内核 tool.presenter
    participant H as realtime_stream
    participant G as Gateway main.py
    participant I as IM relay
    participant F as 前端 panel
    K->>H: ToolPresentationEvent{summary, detail}
    H->>G: tool_end{presentation:{summary, detail}}
    Note over G: ★改:读 pres.detail 一并透传
    G->>I: streaming_delta.tool_call{..., detail}
    Note over I: ★改:ToolCall.detail 贯穿 parse/serialize/persist
    I->>F: tool_call_completed{tool_call:{name, detail, ...}}
    Note over F: ★改:按 name 分发渲染 + 长输出限高滚动
    F-->>F: 折叠态派生人话摘要;展开态分工具卡片
```

## 契约层增量 (delta-spec)

- kernel: `docs/changes/feat-409-im-tool-call-display/specs/kernel/spec.md`(presenter 覆盖工具集扩到 agent/memory/skill_manage/task_stop;task 工具退役,工具清单订正——经 `agent.sdk` 消费者可观察 detail 更全)
- im: `docs/changes/feat-409-im-tool-call-display/specs/im/spec.md`(工具调用展示行为:折叠态人话摘要 + 失败标红 + 分工具展开 + 长输出可控——用户可观察)
- gateway: no spec delta(仅透传管道扩展,无新增对外行为契约)
- cli: no spec delta(本 unit 不动 CLI 渲染层;内核 presenter 改动 CLI 进程内共享但不在本期渲染)

## 风险与回退

- **历史消息无 detail**:前端渲染必须容忍 `detail` 缺失,回退到 `output` 串显示。非阻塞,老消息不报错即可。
- **payload 体量**:最坏接近 256KB/调用。若 WS/持久化有更小上限(M1 暴露),在内核 cap 处统一下调。
- **回退**:前端分工具渲染组件可整体降级回裸 `<pre>(output)`;detail 透传是增量字段,关掉前端渲染分支即回到现状,不破坏数据链。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid` | `IM_JWT_SECRET=<secret> PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port $IM_PORT > .im.log 2>&1 & echo $! > .im.pid` | `curl -s localhost:$IM_PORT/` 200 |
| Gateway | `stop_pidfile .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config "$WT_CFG" --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | `.gateway.log` 出现 bound + relay connected |
| Vite(前端) | `stop_pidfile .vite.pid` | `cd src/IM/frontend && npm run dev -- --port $VITE_PORT --strictPort > .vite.log 2>&1 & echo $! > .vite.pid` | 浏览器开 `localhost:$VITE_PORT` 登录测试账号 |

> 推荐直接 `./scripts/e2e-up.sh` 一键起 IM+Gateway(自动分配端口/隔离 config/auto-bind),前端单独起 Vite 指向其 `$IM_URL`。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 内核 presenter 补齐/改人话 + task 收尾 + 透传链打通 | — | A | 补 agent/memory/skill_manage/task_stop presenter(`_AgentPresenter` 重写自 `_TaskPresenter`,含完整 prompt);**bash 等内置 presenter 的 `summary` 改人话**(bash→description 降级命令首段、agent→description、web_fetch→`status=200 (title)`…);删 task.py + `_TaskPresenter`;Gateway tool_end 透传 detail;IM ToolCall.detail 贯穿 parse/serialize/persist;web_fetch detail 放宽;kernel/im delta-spec;复核 WS/持久化体量上限 | [worker] presenter 单测覆盖各 status 路径 + detail schema + summary 人话(bash summary=description、空降级);agent detail 含完整未截断 prompt 单测;task.py/`_TaskPresenter` 删除后 contract+全测试树绿;Gateway tool_end 单测断言 detail 透传;IM 序列化/持久化往返单测含 detail。[reviewer] e2e:在 IM 触发 bash/edit/agent 调用,Gateway→IM 链路 summary(人话)+ detail 到达前端(可在 WS/DB 观测) |
| M2 | 前端分工具渲染 + 长输出可控展开 | M1 | A | chat-types ToolCall 加 detail;折叠态直接渲染 `output`(presenter 产的 summary)+ `status==failed` 标红 + 真实工具名 + emoji 按 name 兜底映射(**不按 name 派生折叠文案**);展开态按 name 精渲染内置工具(bash/edit/write/web_fetch/agent/memory/skill_manage/task_stop)+ 未知/DIY 工具回退通用结构化卡片;长输出默认截断 + 展开全部限高滚动 + 收起 + 源头截断标注;历史无 detail 降级 | [worker] vitest 覆盖各工具展开渲染分支 + 未知工具通用卡片回退 + 折叠态用 output 渲染 + 失败标红 + 长输出截断/展开/收起 + detail 缺失降级;`npm run build` 绿。[reviewer] 走 spec 全 14 Scenario:折叠态扫信息量/失败标红/真实名、展开态分工具、agent 完整 prompt 在结果前、长输出展开不撑乱滚动、执行中不退化 |

> 拆 2 个 milestone 的举证:M1 是数据链(内核+Gateway+IM relay,Python 测试栈),M2 是渲染(前端 React/vitest 栈),两者技术栈与验收手段不同;M2 强依赖 M1 的 detail 到达(无 detail 无从渲染),串行依赖明确,不可并行。各自退出标准独立可验。
