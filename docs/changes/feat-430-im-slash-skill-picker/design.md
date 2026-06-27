# feat-430: IM slash skill picker — 技术方案

> 对齐: spec.md v2（含 Q11/Q12 范围扩展）

> Unit branch: `unit/feat-430` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

| 路径 | 当前职责 | 本 unit 怎么动 |
|---|---|---|
| `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx` | composer，`@` mention 在此触发（正则 `/@([^@\s]*)$/`），`/` 无任何处理 | **加 `/` 检测 + slash picker 接入**，主战场 |
| `src/IM/frontend/src/features/chat/v2/components/mention-picker.tsx` | 候选面板：前缀过滤、键盘上下/Enter、选中插入 | **照搬为 slash-picker**（新建同构组件，不复用同一文件以免耦合 mention 语义） |
| `src/IM/frontend/.../chat-workspace-page.tsx` | 聊天工作区，只调 `GET /im/v1/agents`（不含 skills），派生 `mentionCandidates` / `groupMembers` | **加每会话 agent 的 skills 数据获取** |
| `src/IM/frontend/.../settings/agents/im-agent-config-api.ts` | `getAgentCapabilities`（`{name,description,default_on}`）/ `getAgentConfig`（白名单 `string[]`） | capabilities 类型 **加 `location` 字段** |
| `src/agent/core/skills/registry.py` | `SkillMetadata` 含 `name/description/location/base_dir` | 只读，location 取此处 |
| `src/agent/sdk/dto.py` | `SkillInfo(name, description)` | **加 `location` 字段** |
| `src/personal_assistant/reporter/upstream_reporter.py` | `_skills_from_kernel()` 把 `SkillInfo` 映射成 `{name,description}`，丢 location | **透传 location** |
| `src/IM/api/routes/agents.py` | capabilities API 的 `AllowlistOptionResponse` | **加 location 字段** |
| `src/personal_assistant/gateway/inbound_pipeline.py` | `_should_process`（群聊 MENTION 投递策略）、`_build_message_parts`（群聊加 `[sender] ` 前缀） | **`_should_process` 放行裸 `/stop`**（不做 wire-mention strip）；`_build_message_parts` 的 sender 前缀**保持不变** |
| `src/agent/core/agent/skill_commands.py` | `rewrite_skill_command`，行首正则 `^\s*/skill:` | **改正则**：认可选前导 `[..]` 段（不编码 sender 格式） |
| `src/agent/core/agent/runtime.py` | `:451` 对 `user_text` 跑 rewrite；`:580` 多 part 分支把 `effective_user_text` 重取末 part（绕过 rewrite） | **对命令所在 part（`effective_user_text`/末 part）跑 rewrite**，使多 part 群聊路径不漏（design-review #2） |

### 既有约束

- 产品包（`personal_assistant` / `IM`）只能 import `agent.sdk`，不能 import `agent.core` 内部——location 字段必须先经 `SkillInfo`(sdk dto) 暴露，gateway 才能取。
- `/stop` 中断走 `kernel.interrupt()` → `RunController.abort(user_initiated=True)`，本 unit **不动中断机制本身**，只修"命令是否被识别/投递"。
- `/skill:name` 重写在 kernel `runtime.py:451`（`rewrite_skill_command`）；本 unit **扩其正则容忍并保留群聊 `[sender] ` 前缀**，重写后的目标语义不变。

### 可复用能力

- **mention picker 整套机制**（`mention-picker.tsx` + `message-pane.tsx` 的触发/键盘/插入）= slash picker 的现成骨架。决定**照搬新建**，不复用同一组件：mention 选中走 wire XML（`<mention/>`）+ 旁路 `draftMentions`，slash 选中只是补纯文本，语义不同，强行共用会互相污染。
- **capabilities API** 已存在且已返回 `{name,description}`，只需扩 `location` 一个字段，不新建 API。
- **`/stop` 单聊链路** 已完整可用，单聊侧零后端改动。

### 相关历史

- `feat-439`（多回合 turn 气泡）、近期 IM 前端 mention picker 相关 unit 改过 `message-pane.tsx` 同一区域——本 unit 在其旁新增 `/` 分支，注意不破坏 `@` 既有逻辑。
- 群聊投递策略（MENTION）、sender 前缀是既有群聊机制，非本 unit 引入；本 unit 只为 `/stop`、`/skill` 命令开特例通道。

### 契约层 grounding

- **gateway（发现 drift）**: canonical `Requirement: 群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent`（`docs/specs/gateway/spec.md:71`）已把"控制命令"列为群聊触发条件之一，但代码 `_should_process` 实际**丢弃**群聊裸 `/stop`——契约与代码 **drift**。本 unit 负责让代码符合既有契约（裸 `/stop` 触发中断），并补 picker wire mention 形式 `/stop` 的识别。
- **kernel/im**: 现有契约未声明 skill `location` 经 `list_skills` / capabilities API 暴露，本 unit 为**新增**字段。`/skill:name` 改写既有契约（kernel:356）成立，本 unit 扩其覆盖到带 `[sender]` 前缀的群聊消息。

## 架构总览

本 unit 是"一个前端新组件 + 三段后端缺口修复 + 一个字段全链路透传"的组合。难点在**数据从哪来、命令到哪生效**两条链路跨了前端→IM→gateway→kernel 四层，故下面用一张结构图标改动点 + 一张时序图走一遍核心操作。

```mermaid
graph TD
  subgraph FE["IM 前端"]
    MP["message-pane.tsx<br/>加 / 检测"]
    SP["slash-picker.tsx<br/>(照搬 mention-picker)"]
    HOOK["skills 数据获取<br/>(chat-workspace-page)"]
    MP --> SP
    HOOK --> SP
  end
  subgraph IM["IM 中心服务"]
    CAP["capabilities API<br/>+location 字段"]
    RELAY["消息 relay"]
  end
  subgraph GW["personal_assistant gateway"]
    INB["inbound_pipeline.py<br/>_should_process 放行裸 /stop"]
    RPT["upstream_reporter<br/>透传 location"]
  end
  subgraph K["agent 内核 (agent.sdk)"]
    DTO["SkillInfo +location"]
    REW["rewrite_skill_command 正则<br/>+ runtime 对命令 part 重写"]
    INT["kernel.interrupt (不改)"]
  end
  HOOK -.拉 skills+location.-> CAP
  CAP -.读.-> RPT
  RPT -.读.-> DTO
  MP ==发送命令文本==> RELAY ==> INB
  INB --> REW
  INB --> INT
```

**before**：前端 composer 不认 `/`；skills 的 location 在 `SkillInfo` 处被丢；群聊裸 `/stop` 被 MENTION 投递策略丢弃、`/skill` 因多 part 选取 + sender 前缀不被重写。
**after**：前端敲 `/` 弹 picker（数据 = config 白名单 ∩ 带 location 的 capabilities）；群聊裸 `/stop` 放行生效、`/skill` 对命令所在 part 重写后生效。

## 关键决策

### 决策 1: slash picker 照搬 mention picker，新建独立组件

**新建 `slash-picker.tsx`，复用 mention picker 的交互机制但不共用同一组件**。

- **理由**: 触发/键盘导航/前缀过滤/选中插入逻辑可直接照搬；但 mention 选中产出 wire XML + 旁路 `draftMentions`，slash 选中只补纯文本，数据通路不同。
- **拒绝**: 复用同一组件加 mode 分支——两套选中语义糅在一起，后续任一改动互相牵连。
- **风险**: 两组件有重复代码；可接受，交互稳定后再抽公共 hook。
- **UI 约束**: picker 锚定 composer 上方、高度受限（max-height ≤ 视口一半）+ 内部滚动，候选多时不得穿出视口顶部（原型实测：composer 不贴底时长候选列表会穿屏顶，故依赖 composer 处于聊天窗底部的既有布局）。

### 决策 2: 已启用 skills = config 白名单 ∩ capabilities（取 description/location）

**前端同时拉 `getAgentConfig`（拿已启用白名单 `skills: string[]`）+ `getAgentCapabilities`（拿 description/location），按 name 取交集**。capabilities 的 skill 项**没有 `default_on`**，不能用它判"已启用"。

- **理由**: Q1 要的是"该 agent 已开启的 skills"，真实启用判据是 config 白名单 `agent.skills`（现状分析已核 `inbound_pipeline.py:777`）；capabilities 的 `list_skills(ws)` 返 workspace **全部**发现的 skill，必须与白名单取交集才等价于 Q1。capabilities 仅用于补 description（白名单只有名字）与 location。
- **拒绝**: 只用 capabilities 过滤 `default_on`——skill 项无此字段（`_skills_from_kernel` 只投 `{name,description}`，`default_on` 是 tools 专属、skill 恒 False），照此实现 picker **永远空**（design-review #1）。也不要给 skill 补 default_on（越到工具语义之外）。
- **空白名单语义**: `agent.skills` 为空时与运行时对齐——运行时 `session.skills` 未设即全部可用，故 picker 也显示该 agent 全部发现的 skill。
- **风险**: 群聊要对每个成员 agent 各拉一次（config + capabilities）；成员数量级小，可并发拉取 + 缓存，可接受。

### 决策 3: location 全链路只读透传

**`SkillMetadata.location` → `SkillInfo.location`(sdk) → `_skills_from_kernel` 透传 → capabilities API `AllowlistOptionResponse.location` → 前端 `AgentAllowlistOption.location`，五层各加一个只读字段**。

- **理由**: location 是同名 skill 唯一性的判据，必须端到端可见。只读、可空（`str | None`），不破坏既有结构。
- **拒绝**: 前端按 name 区分——会把不同路径的同名 skill 错误合并（违反 Q7）。
- **风险**: 跨 sdk/kernel/gateway/im 四包改动；但都是加可空字段，无行为变更，低风险。

### 决策 4: 群聊裸 `/stop` 绕过 MENTION 投递策略（纯文本，不做 wire-mention 识别）

**群聊 /stop = 裸纯文本 `/stop `（与决策 6 命令补文本一致）；改 `inbound_pipeline.py` 的 `_should_process`，让裸 `/stop` 优先于群聊 MENTION 策略送达群内 agent**。

- **理由**: Q6 明确群聊 /stop 是"普通文本广播、各 agent 幂等响应"；picker 补的就是纯 `/stop `，不补 `@agent` 形式。裸 `/stop` 经放行后，既有 `_is_stop_command` 对裸 `/stop` 本就匹配，无需 wire-mention strip。中断机制（`kernel.interrupt`）不动。
- **拒绝**: 让 `_is_stop_command` 识别 picker 补入的 `@agent:{id}` wire 形式（原决策 4①）——picker 根本不补这种形式，该识别**无消费者**（design-review #3）。
- **风险**: 绕过 MENTION 策略要严格限定只对 `/stop` 开口子，不影响普通消息投递；幂等由既有 `interrupt`（无 active run 即 no-op）保证。

### 决策 5: 群聊 `/skill:name` — 对命令所在 part 重写 + 正则认通用前缀（sender 前缀保留）

**`[sender] ` 前缀保持不变；两步：① 让 rewrite 作用于命令所在的那个 part（多 part 分支后的 `effective_user_text`/末 part），而非整段 join 的行首；② 正则放宽为认"可选前导 `[..]` 段"、不编码 sender 具体格式**：`^\s*(?:\[[^\]]*\]\s*)?/skill:…`。群聊 `[Alice] /skill:doc args` → `[Alice] Use the "doc" skill...`。

- **理由**: design-review #2 已核实——群里有人先发言时消息是多 part，`runtime.py:580` 多 part 分支把 `effective_user_text` 重取末 part、**绕过** `runtime.py:451` 的 rewrite，且整段 join 后 `/skill:` 落非首行。只改正则不改 part 选取会 false-fix（单条消息测试过、群里有 buffered 上下文就静默失效）。命令总在末 part（当前消息），故对末 part rewrite 即可命中。正则认通用 `[..]` 前缀而非 `[{sender}] ` 精确格式，弱化对产品格式的依赖。
- **拒绝**: 只放宽正则、不改 part 选取（多 part 路径仍 miss，design-review #2）；gateway 剥 sender 前缀（丢发送者，用户否决）。
- **技术债（design-review #4，登记排期不在本 unit 解）**: 即便正则只认通用 `[..]` 前缀，core 仍假设"命令前可能有产品前缀"。根因是产品把 sender 元数据塞进文本、逼 core 解析；纯架构应让 sender 结构化、core 只见纯正文——但那要重构整条群聊 sender 传递管线（gateway `_format_sender_text` + core 渲染），远超本 unit。**立为独立 refactor unit**（见风险与回退段末），本 unit 不在 core 正则里假装解决。

### 决策 6: 选中 skill 补 `/skill:name `，命令与 skill 一视同仁前缀过滤

**选中 skill → 输入框补 `/skill:name `（尾随空格，光标在末尾）；输入 `/pre` 时命令和 skill 都按前缀过滤**（spec Q9/Q10）。

- **理由**: 与既有 kernel `rewrite_skill_command` 的 `/skill:name` 格式对齐；前缀统一过滤符合主流 picker 直觉。
- **拒绝**: 补 `/name`（与内核重写格式不一致）；命令始终显示（敲 `/pr` 还挂着 `/stop` 干扰）。
- **触发与过滤（两种前缀形态）**: 触发正则识别 ① 裸 `/<prefix>`（过滤命令+skills）② `/skill:<prefix>`（已在 skill 命名空间，只过滤 skills）。关键：用户删改已补入的 `/skill:doc`→`/skill:d` 时，picker 须把 `d` 当 skill 前缀重新弹出过滤，支持纠错——若只认裸 `/<prefix>`，`/skill:d` 会被当查询串 `skill:d` 匹配落空（原型实测缺陷）。正则形如 `^/(skill:)?([^\s/]*)$`，捕获组 1 标识是否 skill 模式、组 2 为前缀。

## 接口与数据流

### capabilities API 字段增量

`GET /im/v1/agents/{id}/capabilities` 响应中每个 skill option：

```
AllowlistOptionResponse {
  name: str
  description: str
  default_on: bool       # 既有：tools 专属；skill 项恒 False，不作启用判据（启用看 config 白名单）
  location: str | None   # 新增：SKILL.md 绝对路径，用于同名去重 + 来源标注
}
```

对应链路各层同步加 `location: str | None`：`SkillInfo`(sdk) → reporter payload → API response → 前端 `AgentAllowlistOption`。
启用判据另走 `getAgentConfig` 的白名单 `skills: string[]`，前端按 name 与上面交集（决策 2）。

### 前端数据组装

- **单聊**: 取当前会话 agent 的 `config.skills`（已启用白名单）∩ `capabilities.skills`（取 description/location）→ picker 候选 + 固定 `/stop`。白名单为空时显示该 agent 全部发现的 skill（与运行时一致）。**不要用 `default_on` 判已启用**（skill 项无此字段，恒 False）。
- **群聊**: 对每个成员 agent 各取 白名单 ∩ capabilities，跨成员取并集；**按 `location` 去重合并**（同 location 合一行，记录 `fromAgents: string[]`；不同 location 同名分行）→ picker 每行标注来源 agent。

### 核心操作时序（单聊敲 `/` 选 skill 发送）

```mermaid
sequenceDiagram
  participant U as 用户
  participant MP as message-pane
  participant SP as slash-picker
  participant CAP as capabilities API
  participant GW as gateway inbound
  participant K as kernel

  U->>MP: 在空输入框/开头敲 "/"
  MP->>SP: 检测命中，打开 picker
  SP->>CAP: (会话进入时已拉/缓存) skills+location
  SP-->>U: 显示 /stop + 已启用 skills(带描述)
  U->>SP: ArrowDown 选 pr-review, Enter
  SP->>MP: 输入框补 "/skill:pr-review "
  U->>MP: 续写内容, Enter 发送
  MP->>GW: 普通文本消息 "/skill:pr-review ..."
  GW->>K: submit (单聊无 sender 前缀)
  K->>K: rewrite_skill_command 命中 → 执行 skill
```

### slash picker 交互规范（worker 实现 checklist）

一次梳理完整，worker 照此实现，避免逐点补漏：

- **触发**: 仅当 `/` 在输入框开头（前面无非空字符）才触发；输入框中间出现 `/` 不触发。`/skill:<prefix>` 形态进入 skill-only 过滤（支持编辑已补入文本纠错）。
- **候选与过滤**: 命令（`/stop`）+ skills，统一按前缀过滤；`/skill:` 前缀下只过滤 skills。无匹配显示空态文案，不阻塞继续输入。
- **description 展示**: skill 描述来自 SKILL.md frontmatter `description`（缺省回退正文首段，见 `agent/core/skills/registry.py`），真实值常是写给模型的**整段长触发描述**；picker 里**单行截断**（`text-overflow: ellipsis`）展示，不撑高列表。
- **键盘**: `↑`/`↓` 循环移动高亮，**高亮项始终滚动进视野**（`scrollIntoView({block:'nearest'})`）；`Enter` 与 `Tab` 都确认选中；`Esc` 关闭面板并保留已输入的 `/` 文本。
- **鼠标**: hover 高亮**只切 class、不重建列表 DOM**（重建会打断点击——本次原型实测的"点不中"根因）；点击用 `mousedown` + `preventDefault`（防输入框失焦、不依赖 `click`）确认；**点击面板与输入框之外关闭面板**。
- **选中落地**: 命令补 `/name `、skill 补 `/skill:name `（尾随空格），**光标置于末尾**，输入框保持焦点。
- **布局**: 面板锚定 composer 上方，`max-height ≤ 视口一半` + 内部滚动，候选多时不穿出视口顶部（依赖 composer 处于聊天窗底部）。
- **焦点/可访问性**: 真实实现给面板/项加 `role=listbox`/`option` 与 `aria-activedescendant`，键盘操作时输入框不失焦。

## 前端原型

- 原型文件: [prototype.html](prototype.html)
- 覆盖范围: 单聊/群聊敲 `/` 弹面板、键盘上下导航 + Enter 选中、前缀过滤、空态、群聊同名 skill 按 location 分行 + 来源标注、选中后补 `/skill:name ` 到输入框。

## 契约层增量 (delta-spec)

- kernel: [specs/kernel/spec.md](specs/kernel/spec.md) — `SkillInfo` 经 `agent.sdk` 暴露 `location`；`/skill:name` 在带 `[sender] ` 前缀的**多 part 群聊消息**上仍被识别重写（发送者标注保留）
- im: [specs/im/spec.md](specs/im/spec.md) — capabilities API 返回 skill `location`
- gateway: [specs/gateway/spec.md](specs/gateway/spec.md) — 群聊裸 `/stop` 不受 @ 策略限制送达（纯文本，无 wire-mention 识别）
- cli: no spec delta

## 风险与回退

- **绕过群聊 MENTION 投递策略的开口子**：必须严格限定只对 `/stop` 命令文本生效，逻辑写错会让普通消息也无视 @ 策略乱投递。回退：该改动独立可还原，回滚后群聊 `/stop` 退回"需 @ 才生效"的现状，单聊不受影响。
- **location 字段跨四包**：worker 须按依赖顺序改（先 sdk dto，再 kernel/gateway/im，最后前端），否则中间层取不到字段。低风险（加可空字段）。
- **群聊每成员各拉 capabilities**：成员多时请求数增加；用并发 + 会话内缓存兜底，不在每次敲 `/` 时重复拉。
- **降级**：若 location 透传未就绪，前端 picker 仍可按 name 显示（同名暂合并），群聊来源标注降级——但这违反 Q7，不作为交付态，仅作 worker 分步落地的中间态。
- **群聊 /skill 多 part 路径（design-review #2）**：命令在末 part，须对 `effective_user_text`/末 part 重写，否则群里有人先发言就静默失效。worker 单测必须覆盖「buffered 上下文 + 末 part `/skill`」路径，不能只测单条 `/skill`。
- **登记的独立 refactor unit（design-review #4，不在本 unit 解）**：群聊 sender 元数据当前以 `[sender] ` 文本前缀塞进消息正文，逼 `agent.core` 解析产品格式。本 unit 用"正则只认通用 `[..]` 前缀"控制耦合面，但根因未除。应另立 refactor unit：让 sender 作结构化属性传入内核、core 只见纯正文、prompt 渲染层统一拼 sender 前缀。**Refs: 待开 issue（见对话）**。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| IM | `stop_pidfile .im.pid` | `IM_JWT_SECRET=... PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port $IM_PORT > .im.log 2>&1 & echo $! > .im.pid` | `curl -s 127.0.0.1:$IM_PORT/` |
| Gateway | `stop_pidfile .gateway.pid` | `PYTHONPATH=src python -m personal_assistant.main --config $WT_CFG --im-service-url http://127.0.0.1:$IM_PORT --foreground --auto-bind > .gateway.log 2>&1 & echo $! > .gateway.pid` | 见 `.gateway.log` 绑定成功 |
| Vite (IM 前端) | `stop_pidfile .vite.pid` | `cd src/IM/frontend && npm run dev -- --port $VITE_PORT --strictPort` | 打开 `http://127.0.0.1:$VITE_PORT/` |

推荐用 `./scripts/e2e-up.sh` 一键起 IM+Gateway，再单独起 Vite。

**Review 驱动方式**: 端到端真栈。本 unit **改了客户端面**（IM 前端 composer 新增 slash picker），必须**真驱动客户端面**——在浏览器里实际敲 `/`、走键盘选中、单聊/群聊各发一次 `/stop` 和 `/skill:name` 看后端真生效。关键界面：单聊 composer、群聊 composer（含同名 skill 来源标注）、空态。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-430-M1 | slash-picker | — | A | 前端 `message-pane.tsx` / 新建 `slash-picker.tsx` / `chat-workspace-page.tsx` / `im-agent-config-api.ts`；后端 location 透传 `sdk/dto.py` / kernel `list_skills` / `upstream_reporter.py` / `IM/api/routes/agents.py`；群聊命令缺口 `inbound_pipeline.py`（`_should_process` 放行裸 `/stop`）/ `skill_commands.py`（`/skill` 正则认通用前缀）/ `runtime.py`（对命令所在 part 重写） | 见下两轨 |

退出标准（单 M1，两轨）：

- `[reviewer]` 单聊敲 `/` 弹面板含 `/stop`+该 agent **已启用**（config 白名单 ∩ capabilities）skills，**不含未启用的**（覆盖 Scenario:单聊里敲 `/`；防 design-review #1 的空/全量）
- `[reviewer]` 群聊敲 `/` 弹面板含 `/stop`+成员已启用 skills 并集，同 location 合并、异 location 分行且标注来源（覆盖 Scenario:群聊里敲 `/` / 同路径合并 / 不同路径分开）
- `[reviewer]` 键盘（↑↓/Enter/Tab/Esc）+鼠标（点击/hover/点面板外关闭）导航选中、高亮项滚动可见、选中后输入框保持焦点（覆盖 Scenario:方向键选择 / 高亮滚动可见 / 鼠标点击 / Esc 或点外关闭）
- `[reviewer]` 选中 skill 补 `/skill:name `（覆盖 Scenario:选中 skill 后补）
- `[reviewer]` 前缀过滤 + 空态（覆盖 Scenario:输入 `/pr` / 输入 `/xyz`）；输入框中间 `/` 不触发（覆盖 Scenario:中间出现 `/`）
- `[reviewer]` 单聊发 `/skill:name ...` skill 真执行（覆盖 Scenario:选中 skill 后继续输入并发送）
- `[reviewer]` **群聊里有其他成员先发言（buffered 上下文）后再发 `/skill:name`，该 skill 仍真执行**（覆盖 design-review #2 多 part 路径，防 false-fix）
- `[reviewer]` 群聊发 `/stop`（含裸 `/stop` 不受"仅 @ 才响应"影响、对未运行 agent 幂等）正在运行的 agent 停止（覆盖 Scenario:群聊里发送 `/stop` / 裸 `/stop` 不受设置影响 / 幂等）
- `[worker]` 前端 `npm run test`（slash-picker 相关）+ `npm run build` 全绿；含「白名单 ∩ capabilities」交集与空白名单语义的单测
- `[worker]` 后端 `pytest -m "not e2e"` 相关单测全绿：location 透传四层；`_should_process` 放行裸 `/stop`；`rewrite_skill_command` 正则认通用前缀 + **`runtime.py` 对命令所在 part 重写**，且单测覆盖「buffered 多 part + 末 part `/skill`」路径
- `[worker]` location 字段四层透传：sdk/kernel/gateway/im 单测验证字段端到端非空
