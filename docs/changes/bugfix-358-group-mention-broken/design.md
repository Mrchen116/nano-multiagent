# bugfix-358: 群聊 @-mention 处理 — 技术方案

> 对齐: incident.md v1
> Unit branch: `unit/bugfix-358` (will be created by orchestrator)

## Changelog

- 2026-05-18 (post-impl): 决策 5 修订 — picker handle 列改为**常态显示**。原"仅重名时显示"实测 UX 不佳：用户选中候选后无法对所选目标的 agent_id 做二次回看，wire 层信息从视觉上完全消失。常态显示信息密度可接受（agent_id 列字号小、颜色淡），重名场景下 handle 自然成为区分依据无须额外切换逻辑。

## 现状分析

### 涉及范围

- `src/IM/application/relay_service.py`
  - `_resolve_all_participants:500` — 当前对 agent 项填 `{"id": user_id, "display_name": ..., "type": "agent"}`，把 synth user UUID 当 agent wire ID 暴露。直接根因。
  - `_resolve_mention_to_agent_ids:300` — 双支查表（agent_id 精确 + display_name fallback + 保留原值兜底），display_name fallback 是同源根因。
  - `_resolve_sender_info:474` — 对 agent 发送者也以 `id=user_id` 暴露，与上同源。
- `src/agent/products/personal_assistant/prompts.py:62` — 硬编码"prefer stable IDs (`user_id` / `agent_id`) when mentioning participants"。把 user_id 和 agent_id 当成可互换"稳定 ID"，是 RCA 设计层根因的措辞证据。
- `src/agent/products/personal_assistant/hooks/communication_context.py` — `_build_communication_context_block` 在 M247 已铺好 actor-first 分支；`message_format` 文案要扩展并改为教 agent 输出 inline 标签。
- `src/IM/frontend/src/features/chat/v2/components/mention-picker.tsx` — 候选 `MentionCandidate { agent_id, display_name, initials, status }` 已带 wire ID；handle 列常态显示供用户回看 agent_id（见 Changelog 2026-05-18 决策 5 修订）。
- `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`
  - `handleMentionSelect:135` 当前写入 `@${c.display_name}` —— 必须改为写入 `<mention type="..." target_id="..."/>` 标签。
  - `MENTION_HIGHLIGHT_RE:47 + buildMirrorNodes:49` 当前只用正则 `<mark>` 高亮 — 要扩展成识别 inline 标签并渲染成 chip mask。
  - `MessageBubble.MarkdownContent:371` — 渲染历史消息时也要把 inline `<mention/>` 替换成 chip 节点。
- `src/personal_assistant/gateway/inbound_pipeline.py:790 _normalize_group_participants` — **不动**。M247 已支持 `agent_id`/`user_id` 优先 fallback `id`。IM 端补字段后端到端自动正确。

### 既有约束

- 四个顶层包不互相 import；IM ↔ Gateway 走 HTTP/WS；改 prompt/hook 在 `src/agent/products/personal_assistant/`。
- `agent_profiles.agent_id` 是 PK（不可改）；`users.username` UNIQUE；`agent_profiles.display_name` 和 `users.display_name` **均无 UNIQUE 约束**——Q6 "放开唯一性" 在 DB / repository / API 三层已经是开放状态，零额外工作。
- relay payload 是 IM↔Gateway 的 wire 契约；本 unit 只补 IM 出参字段，不改 Gateway 解析逻辑（M247 已支持新字段）。
- 消息 `content` 是纯字符串；IM messages 表只有 `content TEXT`，无 mentions 旁路字段。本 unit **不动 DB schema**。

### 可复用能力

- ✅ Gateway `_normalize_group_participants`：actor-first 解析已就位，IM 补字段后即用。
- ✅ `communication_context._build_communication_context_block` 的 actor-first 分支：复用，仅重写 `message_format` 文案。
- ✅ `_resolve_participant_agent_ids`：返回纯 agent_id 列表，作为合法 wire ID 集合复用。
- ❌ 前端 chip 渲染没有现成实现（当前仅 `<mark>` 高亮）；新增 inline `<mention/>` 解析 + chip 组件，落地 composer mirror 和 MessageBubble 两处。

### 相关历史

- **M247 (feat-247)** 已经把 participants 升级为结构化、actor-first schema；Gateway hook 已认 `agent_id`/`user_id`；遗漏是 IM `_resolve_all_participants` 没跟上 + 前端 picker / chip 未消费 wire ID。**本 unit 是 M247 的收尾 + 前端缺口补齐 + display_name fallback 删除**。
- **issue #21**：IM↔Gateway agent 表对账（孤儿来源根因）；本 unit Refs，不阻塞。
- 旁注：`src/IM/infra/repositories.py:1271` 有一处 fallback `Actor(type="agent", id=fallback_display_name, ...)` 把 display_name 当 id 用，与本 unit 同源。worker 实施时若顺手碰到再判断是否捎带修。

## 架构总览

修复后的核心形态：**mention 走单一 inline 标签格式 `<mention type="..." target_id="..."/>`，agent 输出端和 user picker 端都直接产出该标签；IM 是哑存储 + 单一字典供应方，不做任何文本改写**。

```
                Producer 端 (一致格式产出)
  ┌──────────────────────────────────┬─────────────────────────────────┐
  │  Frontend picker / composer       │  Agent reply                    │
  │  选中候选 → 写入 inline tag       │  prompt 教 LLM 输出 inline tag  │
  │  <mention type="agent"            │  <mention type="agent"          │
  │     target_id="ArchA"/>            │     target_id="ArchA"/>         │
  └──────────────────────────────────┴─────────────────────────────────┘
                              │                       │
                              ▼                       ▼
                       POST /messages          (Gateway outbound)
                              │                       │
                              └───────────┬───────────┘
                                          ▼
                              ┌───────────────────────┐
                              │  IM (dumb storage)    │
                              │  - content 原样持久化  │
                              │  - 不改写 / 不验证     │
                              │  - 不查字典塞文本      │
                              └───────────────────────┘
                                          │
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
                  GET /messages      relay payload     WS push
                  (content 原样)    (content 原样)   (content 原样)
                                          │
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
                  Frontend chip    Gateway mention     Mention parser
                  渲染:扫标签 →    解析:扫 content →   只认标签,不再扫 @
                  按 participants  对照 participants
                  查当前 display   决定 mentioned_agent_ids
                  _name 渲染       (Gateway 已就绪)

  字典供应:
    relay payload.participants[] = [
      {type:"agent", agent_id:"ArchA", display_name:"Q"},
      {type:"user",  user_id:"503...",  display_name:"Test User"}
    ]
    前端 conversation.participants 同形态
    (改名只动 display_name 字段,target_id 永远稳定)
```

不变性（架构层硬约束）:

1. **direction-agnostic**：agent / user / picker / composer 任一端写出的 mention 文本承载格式**逐字一致**，都是 `<mention type="..." target_id="..."/>`。
2. **wire 与 display 分层**：`target_id` 是 wire（agent_id / user_id PK），`display_name` 是字典查值（动态、可重名、可改）。
3. **display_name 只在渲染时查表**：不烧进 content、不烧进 mention 标签属性。Q4"改名后所有指向 chip 自动按新名渲染"由此自然成立。
4. **IM 不重写 content**：消息 content 是不可变字节，IM 角色仅为存储 + 字典供应。

## 关键决策

### 决策 1: mention 文本承载 = inline XML 标签

**选择**: 消息 `content` 里直接嵌 `<mention type="agent"|"user" target_id="X"/>` 自闭合标签。不引入旁路 `mentions[]` JSON 列、不引入 markdown link 形式、不引入 placeholder + offset/length 结构。

**理由**:
- 消息 content 是单一权威载体；mention 结构信息与文本同生命周期，schema 演化代价 = 0。
- agent / user / picker 三个 producer 写同一种文本，"direction-agnostic"在源头就成立，无须 IM 改写步骤。
- 旧消息 content 里没标签 → 渲染端找不到标签 = 字面渲染，零兼容代码（Q5 "不计过往"自然落地）。

**拒绝**:
- IM 入站改写 `@<wire_id>` → 标签：引入"改写延迟 / 参与者验证时机"边角；agent 路径还要单独走改写函数；user 输入端和 agent 输入端要分两条 normalize 路径——伪一致。
- `mentions_json` 旁路列：DB schema 升级；所有 reader 适配；与 Q5 "不回填"冲突会迫使前端维护两套渲染路径。
- markdown link `[@display](id://...)`：与消息体 markdown 解析互相干扰；display_name 烧进 token 文本违反 Q4。

**风险**:
- LLM 输出 XML 标签的格式可靠性：Sonnet 类模型对 XML 输出可靠；prompt 给两个示例（agent / user 各一）即可，详见决策 3。
- 标签字符串在 composer textarea 直接可见，会让用户看到"裸 XML"——通过 composer mirror layer 覆盖式渲染解决（见决策 4）。

### 决策 2: 标签 schema = `<mention type="agent"|"user" target_id="X"/>`

**选择**: 自闭合标签，两个属性：`type ∈ {"agent","user"}` 和 `target_id`（agent_id 或 user_id 字面）。

**理由**:
- `target_id` 是 wire，必备。
- `type` 显式标注，让解析端不需要双表查询确认 target 是 agent 还是 user；同时为后续演进（如 mention 群、mention 频道）预留属性位。
- 自闭合，无 body——避免"body 是 display_name 快照"诱惑（违反 Q4）。
- 不冗余 display_name 进属性——同上理由。

**拒绝**:
- 分形标签 `<mention-agent/>` / `<mention-user/>`：写正则、改 type 域、加新 actor 类型都得改标签名而非属性，线性扩展能力差。
- `<at id="X"/>`：更短但语义不足；XML 标签命名应见名知意。

**风险**: 无显著。

### 决策 3: agent prompt 维持现有 `[Communication Context]` 块结构

**选择**: 沿用 `_build_communication_context_block` 当前输出形态。改两处：

1. `message_format` 那行教 agent 输出 inline 标签（带 agent / user 各一例）；不再教 `@<id>` 形式。
2. 删 `prompts.py:62` "prefer stable IDs (`user_id` / `agent_id`)"硬编码——由 hook 单一来源说明 @ 规则，避免双源口径漂移。

具体文案落到 worker 实施；本 design 锁定的是**口径**：

- 教 inline 标签作为唯一 mention 输出形式
- `target_id` 严格取自 `group_participants` 中对应条目的 `agent_id` / `user_id`
- 给一个 agent → agent 示例 + 一个 agent → user 示例

**理由**: M247 actor-first 块已能输出 `name (type, agent_id|user_id: X)`，agent 已有完整字典；本 unit 不重设计现有信息架构，只切换输出语法。

**拒绝**: 重设计 prompt 块整体格式——已有结构能用，重做即风险。

**风险**: LLM 偶发产出格式偏差（缺斜杠 / 属性名错位 / 引号 missing）。**Q10 已断**：扫不出合法标签的 mention 不进路由、不报错、字面渲染，不破坏消息持久化。

### 决策 4: 前端 mention 双轨渲染（composer + 历史消息）

**选择**: 两处统一通过同一个 `<mention/>` 解析函数（建议命名 `parseMentions(content)` → `Array<{type:'text'|'mention', ...}>`）驱动渲染：

- **Composer mirror layer**: 现有的 `chat-composer-highlight-mirror` 镜像 div 接管 inline 标签 → 渲染成 chip 视觉块覆盖在 textarea 上层（textarea 内的字面 XML 字符串保持原样，由 mirror 视觉遮盖）。光标移动 / 退格按字符工作（不做"原子单元"删除）—— 简单优先。用户退格删进标签中间会破坏 chip，IM 端会因标签不完整无法识别为 mention，回归到普通文本字面，自然降级；用户可手动重新选 picker。
- **MessageBubble**: `MarkdownContent` 在渲染段落前先解析 inline 标签，把命中区段替换为 `<MentionChip target_id="X" type="..."/>` React 节点，节点内部从 `conversation.participants` 字典查当前 display_name 渲染。
- **不存在的 target_id**: 渲染为灰色字面 `@<unknown>`（或保留原 `<mention/>` 不替换）；用户视觉上是失效引用。worker 阶段定具体降级样式。

### 决策 5: picker 选中后写入标签 + handle 列常态显示

**选择**:

- `handleMentionSelect` 改为 `setDraft(before + '<mention type="agent" target_id="ArchA"/> ')`（实际类型 / target_id 取自 candidate）。
- mention-picker.tsx 行内 handle 列**每条候选都显示**：右侧固定列显示 `@<agent_id>`（去掉 `agent[_-]` 前缀后），字号小、颜色淡。

**理由**: 选中前后用户都能看到所选 agent 的 wire ID（agent_id），是 wire / display 两层架构在 UI 层的对应——左 display_name 是给"读"，右 agent_id 是给"对"。重名时 handle 自动成为区分依据，无须额外切换逻辑。

**拒绝**:
- 仅重名时显示 handle：表面"常态干净"，实测代价是用户每次选中后丧失对 wire ID 的回看；重名是发生时刻无预警的，UI 不能等到那一刻才开始展示。
- 拼接 display 文案 `"助手 · ArchA"`：把两个独立字段混成字符串，后续搜索 / 过滤逻辑得拆回去。

### 决策 6: IM 删除 `_resolve_mention_to_agent_ids` 的 display_name fallback

**选择**: mention 解析改为只扫 content 里的 `<mention type="agent" target_id="X"/>` 标签提取 target_id；不再 split text 找 `@<...>`、不再按 display_name 查表。

**理由**: 同源根因。Q4 决定整条链路改造，display_name fallback 这一支没存在意义。

**拒绝**: 保留 fallback 用作"agent 输出错格式时的兜底"——这是把缺陷写进协议，违反 Q1 精神。Q10 已断不存在的 mention 不进路由是正确降级。

### 决策 7: relay payload `participants[]` schema 修正

**选择**: `_resolve_all_participants` 返回项分两形态：

```python
# agent 项
{"type": "agent", "agent_id": "<agent_id>", "display_name": "<name>"}

# user 项
{"type": "user", "user_id": "<user_id>", "display_name": "<name>"}
```

不再有 `id: <synth_user_uuid>` 字段。`_resolve_sender_info` 同步修正——agent 发送者给 `agent_id` 而非 user_id。

**理由**: 这是直接根因修复，且与 Gateway `_normalize_group_participants` (M247) 期望的 actor-first 字段完全对齐——IM 改完字段后 Gateway 解析自动跑对路径。

**拒绝**: 引入新字段（如 `wire_id`）当通用别名——会与既有 `agent_id` / `user_id` 含义重复，污染契约。

## 接口与数据流

### IM relay payload `message.content` 形态

```
"<mention type=\"agent\" target_id=\"ArchA\"/> 要不我们从认识论聊起？\n<mention type=\"user\" target_id=\"503349f1...\"/> 你看怎么样？"
```

content 是单一权威字段。Gateway 不再 split text、不再处理 `@<...>` token。

### IM relay payload `participants[]`

```json
[
  {"type": "agent", "agent_id": "Arch",  "display_name": "架构"},
  {"type": "agent", "agent_id": "ArchA", "display_name": "Q"},
  {"type": "user",  "user_id":  "503349f1...", "display_name": "Test User"}
]
```

Gateway `_normalize_group_participants` 已支持此 schema。

### IM relay payload `metadata.mentioned_agent_ids`

由 IM 在 `enqueue_message_relay` 中按"扫 `<mention type="agent" .../>` 标签并交集 participants 中 agent 集合"得出。**不再扫 `@<...>` 文本**。

```python
# 新 _resolve_mention_to_agent_ids（重写后）
def _resolve_mentioned_agent_ids(self, *, content: str, participant_agent_ids: list[str]) -> list[str]:
    """扫 content 内 <mention type="agent" target_id="X"/> 标签提取 target_id,
    过滤为 participants 中存在的 agent_id 集合。"""
    # 正则:<mention\s+...target_id="([^"]+)"[^/]*/>，type=agent 才采纳
    # 返回去重 + 排序后的 agent_id 列表
```

agent prompt 教会的 mention 形式与本扫描器对齐。

### Frontend `parseMentions(content)`

返回 `Array<TextSegment | MentionSegment>`：

```ts
type Segment =
  | { kind: "text"; text: string }
  | { kind: "mention"; type: "agent" | "user"; target_id: string };
```

供 composer mirror 和 MessageBubble 共用。MentionSegment 渲染时由调用方从 `conversation.participants` 查 display_name。

### Agent system prompt `[Communication Context]` 块（新口径）

沿用现有键值行结构。`message_format` 行替换为类似（具体措辞由 worker 落实，design 锁口径）:

```
- mention_format: 引用群内某人时，在你的回复中直接写
  <mention type="agent" target_id="<id>"/> 或
  <mention type="user"  target_id="<id>"/>。
  <id> 严格取自上方 group_participants 对应条目的 agent_id / user_id。
  例：<mention type="agent" target_id="ArchA"/> 你说呢？
      <mention type="user"  target_id="503349f1..."/> 我同意。
```

不出现 `@<id>` 形式的教程；老的 `prompts.py:62` 行删除。

## 风险与回退

| 风险 | 后果 | 应对 |
|---|---|---|
| LLM 输出 `<mention/>` 标签格式偏差（属性名 / 引号 / 自闭合斜杠） | 该条消息 mention 失效（字面渲染）；目标对象不被触发 | Q10 已断的降级路径；prompt 给 2 个示例显著降低偏差概率；不需架构兜底 |
| 用户在 composer 里手动编辑标签字符（退格删进中间） | 标签结构破坏 → 字面渲染 + 不进路由 | 接受：自然降级；用户可重新走 picker。不做"原子单元"删除来增加复杂度 |
| 前端 chip 渲染在某个未覆盖路径上漏掉解析 | 用户看到字面 `<mention .../>` 字符串而非 chip | worker 单测覆盖 composer / MessageBubble 两路；reviewer 旅程验证两路渲染 |
| Gateway / agent prompt 改完上线但 IM relay payload 没改，导致 agent 看到的 participants 字典仍带 synth UUID | agent 输出标签时 target_id 写错 | 单 milestone 一次性交付（见 §Milestones），不分阶段上线避免此风险 |
| 老 conversation 里残留消息 content 含 `@<UUID>` 字面 | 字面渲染，无 chip | Q5 已断不回填；用户视觉降级可接受 |

**回退**: 单 unit 分支 `unit/bugfix-358` 整体撤回即可（git revert merge commit）。无 DB schema 改动，无数据迁移，回退无遗留。

## Runbook for Reviewer

reviewer 走旅程前按下表无脑重启清单内服务（避免 stale-binary）：

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM 服务 | `pkill -f "uvicorn IM.app"` | `IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011 &` | `curl -fsS http://127.0.0.1:8011/im/v1/auth/me -H "Authorization: Bearer <token>"` 或浏览器开 `http://127.0.0.1:8011/` |
| Gateway | `PYTHONPATH=src python -m personal_assistant.main stop` | `PYTHONPATH=src python -m personal_assistant.main` | `tail -n 50 ~/.nano-assistant/gateway.log` 看到 `agents synchronized` 即可 |
| 前端构建产物 | — | `cd src/IM/frontend && npm run build` | 重启 IM 后浏览器硬刷一次 (`Cmd+Shift+R`)，确保 dist 是新版 |

> 三者顺序：先停 Gateway → 停 IM → 重 build 前端 → 起 IM → 起 Gateway。

## Milestones

单 M1。本 unit 是 wire 协议双端 + agent prompt + 前端渲染**一条完整链路**，任一处单独上线没有用户可观察价值且会破坏一致性（参见 §风险与回退）。垂直切片整体交付。

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| bugfix-358-M1 | impl | — | A | `src/IM/application/relay_service.py`<br>`src/agent/products/personal_assistant/prompts.py`<br>`src/agent/products/personal_assistant/hooks/communication_context.py`<br>`src/IM/frontend/src/features/chat/v2/components/mention-picker.tsx`<br>`src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`<br>对应单测 + 集成测试 | `[reviewer]` 群聊中 user 通过 picker 选中一个 agent 发送 mention 后，该 agent 收到该消息并触发响应；前端把该 mention 渲染成 chip，显示目标 agent 的当前 display_name<br>`[reviewer]` 群聊中一个 agent 在自己回复里 @ 另一个 agent，被 @ 的 agent 收到并响应；该 mention 在前端渲染为 chip，显示当前 display_name，不出现 UUID / agent_id 等内部字符作为字面文本<br>`[reviewer]` user 把某 agent 的 display_name 改名后，本次修复生效之后产生的新消息中针对该 agent 的 chip 自动按新 display_name 渲染<br>`[reviewer]` 系统允许多个 agent 使用相同 display_name；群里出现重名时，picker 让用户能区分并独立选中其中任一；被选中的 agent 被 @ 后，只有它响应<br>`[reviewer]` 当 IM 中存在残留 / 离线节点上的孤儿 agent，user 或 agent 在群里发出针对该名字的 mention 后，目标 agent 仍正确被触发<br>`[reviewer]` agent→user mention（agent 在群里 @ 当前 user）渲染成对应 display_name chip，被 @ 的用户收到通知<br>`[worker]` `pytest -xvs tests/unit/im/test_relay_service.py` 全绿；新增测试覆盖：agent 项 payload 含 `agent_id` 且不含 synth user UUID；mention 解析只认 `<mention/>` 标签；display_name fallback 分支已删除<br>`[worker]` `pytest -xvs tests/integration/test_group_mention_routing.py`（新增）覆盖 agent→agent / user→agent / agent→user 三向 mention 路由 + 同名 agent 消歧路由<br>`[worker]` `cd src/IM/frontend && npm run test` 全绿；新增测试覆盖：`handleMentionSelect` 写入 `<mention/>` 标签；composer mirror + MessageBubble 共用 `parseMentions` 解析；chip 按 `conversation.participants` 查当前 display_name；picker handle 列常态显示<br>`[worker]` `cd src/IM/frontend && npm run build` 通过<br>`[worker]` `pytest -m "not e2e"` 全绿 |

