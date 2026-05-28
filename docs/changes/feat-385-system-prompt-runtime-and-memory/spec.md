# feat-385: System Prompt Runtime 切段式 + Memory 闭环修复

## Relations

- Depends on: bugfix-348 (PR #9) — bugfix-348 已建好 "workspace_root 调用方 per-request 透传" 基础链路 + 修了 session JSONL 隔离 bug;本 unit 在它建好的 hook_metadata 透传链路上加 `workspace_config_dirname` key + 修 MemoryTool 同类隔离 bug。**实施期等 bugfix-348 合并后启动**,避免改同一片代码 conflict
- Related: feat-379-system-prompt-sections(段式框架的引入者;本 unit 是它的完成与延伸)
- Related: feat-349-self-evolving-skills-memory(MemoryTool 引入者;本 unit 修复其 design.md L24 漏接的注入闭环)
- Related: feat-383-prompt-preview-fidelity(基于段式框架做预览保真;本 unit 完成后预览与 runtime 真正一致)

## 原始需求

> 1. 379是重构，他没做完，我们新unit要做完。2. 做完之后把## Available Tools删掉 3. 对齐CC的一些我想要的，这个我们还要进一步聊。

补充背景（本对话推导，非用户原话）：

- feat-379 引入段式 system prompt 框架（`core/agent/prompt_sections/`，CORE_SECTIONS + 产品 sections），但 runtime（`loop.py:155 build_system_prompt`）仍走老 f-string 模板（`LOCAL_CODING_SYSTEM_PROMPT` / `PERSONAL_ASSISTANT_SYSTEM_PROMPT`）；段式产物目前**仅供** `/v1/prompt-preview` 端点（IM 配置页预览）消费，不进入模型真实对话。bootstrap.py:160 自承"legacy string-based prompt path"。
- `## Available Tools` 段（`core.runtime_tools`）把 ToolSpec 名字+描述渲染进 system prompt，与 Anthropic API `tools=[]` 原生通道重复（schema 在 API 通道、文字描述在 prompt 通道），token 浪费、易漂移、掩盖 provider 兼容 bug。
- memory 闭环断了：MemoryTool（feat-349 引入，复刻 hermes）写入路径活，但 MemoryStore.format_for_prompt 在 session 启动从未被调用，`PromptContext.memory_block` 永远为 None，`core.memory_block` 段（feat-379 已就位）永远未激活——agent 写得进 memory 但读不到自己写的内容。本 unit 第 3 项补这条注入链路。

> 备注：原始需求第 3 项"对齐 CC 一些段"经澄清后整体推迟（见 Q3/Q4），本 unit 第 3 项已收窄为"修 memory 闭环"，CC 内容补搬留给后续 unit。

## 澄清记录

- Q1: 三件事(完成 feat-379 重构 + 删 `## Available Tools` + 对齐 CC 通用段)合并为一个 `feat-385` unit,还是拆?
  A(原话): 不是refactor，是 feature。一个完整的feature做这是三个事情
  Agent 解读: 一个 feat unit 完成三件事;首文档用 `spec.md` 模板。

- Q2: CC 的 `loadMemoryPrompt`(#9 段)对齐方向?给出三选项:A1 修复 hermes 范式(MemoryTool 写 + 自动注入 system prompt 读)、A2 切到 CC 范式(索引文件 + per-topic 文件 + 通用文件工具读写)、A3 本期不动 memory 体系另立 unit。
  A(原话): 效果上要方向 A1(修复 hermes 范式)，注入system prompt消费，MemoryTool写入。实现上要按本仓的CC的按feature接入system prompt段的逻辑写代码。
  Agent 解读: memory 这块本期含在范围内。效果走 hermes 闭环(MemoryTool 已存在,补"session 启动渲染 → 注入 system prompt"那一头)。实现路径走 feat-379 段式 + feature-gate:用 `PromptContext.memory_block` + 已存在的 `core.memory_block` 段(order=950, cache_safe=False),由 `memory_curation` feature 开关控制。PA prompt 里"用 read 工具读 `<workspace>/MEMORY.md`"那段属于残留机制 3,要清除(避免与 MemoryTool 操作的不同文件造成误导)。

- Q3: 第 3 项"对齐 CC 通用段"的范围 — 提议搬 7 段(Intro 部分 / Doing tasks / Output efficiency / Session guidance 裁剪 / Environment 补齐 / Language section 化 / SUMMARIZE_TOOL_RESULTS),其余排除;另外问 M4 已搬 4 段当时的删减是否要本期补回。
  A(原话): 我决定不搬了，379搬了多少就多少，后面再做
  Agent 解读: CC 内容补搬整体推迟,M4 已搬的 4 段删减也不补回。本 unit 不再含任何 CC 内容对齐工作 — feat-379 既有内容(`core.system / actions_care / tool_rules / tone_style` 当前版本)原样保留。

- Q4: memory 闭环修复(hermes A1)是否随 Q3 一起推迟?给两选项:A 仅做 runtime 切段式 + 删 `## Available Tools`;B 上述 + memory 闭环修复。
  A(原话): B
  Agent 解读: 本 unit 最终范围 = (1) runtime 切段式收尾(`loop.py` 走段式装配,老 f-string 模板退役);(2) 删 `core.runtime_tools` 段(`## Available Tools`),工具走 API `tools=[]` 原生通道;(3) memory 闭环修复(MemoryStore 在 session 启动渲染 + 注入 `PromptContext.memory_block`,清 PA prompt 残留)。CC 内容补搬全部排除,留给后续 unit。

  Unit 目录已重命名为 `feat-385-system-prompt-runtime-and-memory`,标题同步改为 "System Prompt Runtime 切段式 + Memory 闭环修复"。

- Q5: memory 闭环修复后,产品覆盖范围 / USER.md 是否一起注入 / 默认开关 — 这些怎么定?
  A(原话): 这个之前引入hermes agent的自进化的时候对过了吧
  Agent 解读: 撤回 Q5,沿用 feat-349 已对齐结论:(1) 两产品都开 — feat-349 spec Q1 原话"两个产品都做";(2) MEMORY.md(agent 笔记)+ USER.md(用户画像)都注入,每个 agent 完全隔离自己的两份 — feat-349 Q3;(3) 默认开启,memory_curation feature 开关可关(整体关 / 分别关 skill 自进化 / memory 记录)— feat-349 Q5。本 unit 不重新决议产品覆盖问题,只补"闭环断了的注入那一头"。

- Q6: 删 `## Available Tools` 段时,若某 provider tool calling 因此炸了,本 unit 要不要在 system prompt 留 fallback 兜底?
  A(原话): 不兜底
  Agent 解读: 直接删,不在 system prompt 留 fallback。若某 provider 适配层没把 API `tools=[]` 通道传给模型,该 provider 适配层独立修,本 unit 不掩盖。reviewer 验收时要走"所有现有工具调用稳定"回归旅程,真踩雷直接暴露。

- Q7: design 阶段调研发现 — 现状 `bootstrap_product` 是 per-process(PA Gateway 起一个 kernel 进程对应一次 bootstrap),`bootstrap.py:143` 把 bootstrap-time `memory_root` 作为 `_fixed_memory_root` 注入 MemoryTool,`MemoryTool._resolve_memory_root` 第一行短路了 per-session 解析。结果:所有 agent 实际共用同一份 MEMORY.md / USER.md(基于进程 cwd / env),**与 feat-349 spec Q3 "每个 agent 完全隔离自己的 memory" 的产品契约矛盾**。本 unit 是否顺手修这个 bug?给三选项:G1 本 unit 扩范围,顺手修(让 MemoryTool 走 ctx.session_metadata 派生 per-session memory_root,runtime 在 hook_metadata 加 workspace_root key);G2 本 unit 只保证读路径正确(读写不一致,memory 形同虚设,不可取);G3 推迟,先开 bugfix 单独修,完成后再做本 unit。
  A(原话): 本 units 扩大一刀。没关系啊，这个有你的任务多一点没关系，后面我们做 精确的 milestone 分割就好了。
  Agent 解读: 选 G1。本 unit 范围扩到含 MemoryTool 隔离修复:(1) `bootstrap.py:143` MemoryTool 构造不再传 `memory_root`(传 None);(2) `MemoryTool._resolve_memory_root` 不再短路 _fixed,强制走 ctx.session_metadata;(3) runtime `_run_locked` 在 hook_metadata 中加 `workspace_root` key(目前只有 `cwd`);(4) memory_root 派生路径统一为 `<workspace>/.nanoassistant/memory/`(对齐 `WORKSPACE_CONFIG_DIRNAME` 与 PA local_store 注释);(5) 本 unit freeze 流程从同一来源派生 memory_root,读写一致。milestone 拆分由 design 阶段定。


## 用户场景

本 unit 含三件事,镜头分两类:**memory 闭环修复**是用户能直接感知的新能力(憧憬式);**runtime 切段式 + 删 `## Available Tools`** 是结构清理,用户不应感受到任何 regression(回归基线镜头)。

### 场景一:agent 跨 session 记住事(memory 闭环新能力)

小张和他的 PA agent 聊了一周,期间陆续说过:
- "我用的是 macOS,本机 venv 永远在 .venv/"
- "我不爱用 emoji,直接来"
- "我做日程时间偏好 24 小时制"

每次说完,agent 顺手在后台用 `memory` 工具把这些事实分别写进 MEMORY.md(自己的笔记)和 USER.md(用户画像)。

到了第二周,小张重新打开 PA 和它聊。他没再说一遍偏好,但 agent 直接表现得**像它记得**:
- 给日程建议时默认 24 小时制
- 回复不带 emoji
- 让小张装包时直接说"在 .venv 里 pip install ..."

小张不需要主动喊"看下 MEMORY.md",这件事在每个 session 启动时自动发生 — agent 的系统提示词里已经带着前期沉淀的两块 memory。

同样的能力在 coding agent 上:跨 session 记住"本仓 Python 入口要 `PYTHONPATH=src`"、"测试默认跑 `not e2e` 节省时间"等长期事实。

用户能关:在 IM agent 配置里取消 `Memory Curation` 开关后,agent 不再自动写 memory,系统提示词里也不再注入既有 memory — 整个能力回到关闭态。

### 场景二:agent 整体行为不退化(runtime 切段式回归基线)

老王平时用 coding agent 干活 — 改 bug、写代码、review diff。本 unit 上线后,老王不应该感受到任何质量退化 — agent 风格、tool 使用习惯、风险动作是否先确认、引用代码用 `file_path:line_number` 格式等行为**保持原样**(且因为 M4 已搬的 `actions_care` / `tone_style` / `system` 等 CC-adapted 段第一次真正作用于 runtime,部分行为可能微正向变化,但绝不退化)。

同样,小张的 PA agent 在群聊和单聊的所有现有约束 — 群聊 `NO_REPLY` 协议、`send_message` 路由边界、IM 简洁语气、平台 Policy 等 — 全部保留生效。

reviewer 验收时走真实旅程:coding 让 agent 改个 bug;PA 在群聊和单聊各跑一轮;两边都看是否一切如常。

### 场景三:删 `## Available Tools` 后工具调用照旧(provider 兼容观察面)

小张在 PA agent 上点开"系统提示词预览"展开看,**注意到原来那段 `## Available Tools\n- read: ...\n- write: ...` 列表不见了**。

但 agent 实际工作时,该用 `read` 还是用 `read`、该用 `send_message` 还是用 `send_message`、该用 `memory` 还是用 `memory` — **所有工具一切正常**。因为工具描述本就该走 LLM API 的 `tools` 通道(本仓 LLM 代理已支持),系统提示词里那段重复列表删掉,既省 token 又消除"prompt 描述漂移于 schema"的风险。

如果哪天小张换了一个不透传 `tools` 通道的 provider,agent 的工具调用会直接炸 — 这是 **provider 适配层该修的事**,本 unit 不在 system prompt 兜底掩盖。

## 验收标准

### Requirement: Agent 跨 session 持续感知既有 memory

#### Scenario: 既有 memory 在新 session 启动时被 agent 感知
- **GIVEN** 某 agent 在过去 session 已经向 MEMORY.md / USER.md 写入若干条目
- **WHEN** 用户开启新 session 和该 agent 对话,涉及既有 memory 覆盖的话题
- **THEN** agent 的回复体现出对既有 memory 的感知(例如不再询问已记录的用户偏好、直接按既有事实回答)

#### Scenario: 新 agent 没有任何 memory 时不报错也不显眼
- **GIVEN** 新创建的 agent,MEMORY.md / USER.md 还从未被写过
- **WHEN** 用户开启 session 和该 agent 对话
- **THEN** agent 正常对话,不出现"memory 为空"之类的显式提示扰动对话

#### Scenario: 关闭 Memory Curation 后 agent 不再表现 memory 感知
- **GIVEN** 某 agent 之前有 memory 条目,用户在 IM 配置中关闭 Memory Curation 开关
- **WHEN** 用户开启新 session 对话(涉及既有 memory 覆盖的话题)
- **THEN** agent 不再表现出"记得"既有事实,需要用户重新说一遍

### Requirement: Runtime 行为相对当前不退化

#### Scenario: coding agent 既有任务流不退化
- **GIVEN** coding agent 配置不变
- **WHEN** 用户走真实 coding 旅程(让 agent 改 bug / 编辑文件 / 跑测试 / 引用代码位置)
- **THEN** agent 工具使用 / 文件引用格式 / 风险动作确认行为与本 unit 上线前一致或更靠谱,无可观察 regression

#### Scenario: PA agent 群聊 / 单聊既有协议不退化
- **GIVEN** PA agent 已加入若干群聊和单聊,配置不变
- **WHEN** 用户在群聊中触发 `NO_REPLY` 场景、在单聊中触发 `send_message` 跨会话路由场景
- **THEN** 既有协议(群聊 `NO_REPLY`、`send_message` 路由边界、IM 简洁语气、平台 Policy、`web_fetch` 不可信外部内容等)全部保留生效

### Requirement: System prompt 不再列举工具,工具调用走 API 原生通道

#### Scenario: prompt preview 不含 `## Available Tools` 段
- **WHEN** 用户在 IM 打开任意 agent 的"系统提示词预览"并展开
- **THEN** 预览内容中不出现 `## Available Tools` 段及其下方的工具名 / 描述列表

#### Scenario: 所有当前工具仍可被 agent 正常调用
- **GIVEN** 某 agent 拥有 `read / write / edit / bash / agent / memory / skill_manage / send_message` 等全部默认工具
- **WHEN** 用户在真实对话中分别让 agent 触发每种工具的使用
- **THEN** 所有工具均能被正常调用、参数正确、结果返回正常,无"工具未知 / 不存在 / 参数缺失"等错误

#### Scenario: 某 provider 不透传 tools 通道时错误直接暴露而非被兜底掩盖
- **GIVEN** 假设某 LLM provider 适配层未把 API `tools` 通道传给模型
- **WHEN** agent 试图调用任何工具
- **THEN** 错误立即暴露(模型说"我没有这个工具"或 tool calling 直接失败),本 unit **不**通过 system prompt 文本兜底掩盖

### Requirement: prompt-preview 与 runtime 完全一致

#### Scenario: 预览反映 agent 真实接收的系统提示词
- **GIVEN** agent 配置稳定(工具列表、特性开关、custom prompt 等)
- **WHEN** 用户在 IM 打开"系统提示词预览"
- **THEN** 预览内容与 agent 在真实对话中接收的系统提示词在所有 stable 段上字节一致;volatile 段(memory_block / 时间)在预览中以可识别的占位符呈现,且预览底部明确说明该差异

## 范围与非目标

- **在范围**:
  - **runtime 切段式装配**:`loop.py` / `runtime.py` 改用段式装配(`assemble_system_prompt` 路径),老 `LOCAL_CODING_SYSTEM_PROMPT` / `PERSONAL_ASSISTANT_SYSTEM_PROMPT` f-string 模板 + `prompting.build_system_prompt` 旧路径退役
  - **删 `core.runtime_tools` 段**(对应渲染产物 `## Available Tools`),工具描述完全由 LLM API `tools=[]` 通道送达
  - **memory 闭环修复**:session 启动时构造 `MemoryStore` + `load_from_disk`,装配点调 `format_for_prompt` 灌进 `PromptContext.memory_block`,激活既有 `core.memory_block` 段;同样处理 USER.md;清 PA prompt 中"用 `read` 工具读 `<workspace>/MEMORY.md`"残留(与 MemoryTool 操作的 `<memory_root>/MEMORY.md` 不通,留着误导)
  - **MemoryTool 隔离修复**(Q7 G1):修 `bootstrap.py:143` + `MemoryTool._resolve_memory_root` + runtime 的 hook_metadata,让 memory_root 真正 per-session(per-agent)派生,符合 feat-349 spec Q3 产品契约;读(本 unit 新增的 freeze 流程)与写(MemoryTool)走同一 memory_root
  - 两个产品(coding + PA)同步享用上述改动(沿用 feat-349 已对齐方案,不重新决议)
  - prompt-preview 端点保持工作,与 runtime 装配产物一致(volatile 段以占位符呈现)

- **非目标**:
  - **不补搬** CC 任何额外段(Intro / Doing tasks / Output efficiency / Session guidance / Environment 补齐 / Language section 化 / SUMMARIZE_TOOL_RESULTS 等)— 全部留给后续 unit
  - **不补回** M4 当时砍掉的 `core.actions_care` / `core.tool_rules` / `core.tone_style` 删减内容
  - 不引入 "core 通用框架 + product 段差异化补例" 这种分层结构(feat-379 的同层共享设计沿用)
  - 不改 memory 体系底层结构(继续 § -分隔单文件,不切 CC 的"索引文件 + per-topic 文件 + frontmatter"形态)
  - 不改 MemoryTool 接口(继续 `add / replace / remove`,不补 `read` action)
  - 不动 skill 自进化机制 / FEATURE_REGISTRY 的开关结构 / IM 前端 agent 配置页 UI(沿用 feat-379 M9 已建成果)
  - 不引入新 LLM provider,也不修复任何 provider 适配层 bug(本 unit 只暴露问题,不掩盖、不修复)
  - 不补 verifier 流程治理(feat-379 因为缺它出事是另一回事,不在本 unit 范围)
