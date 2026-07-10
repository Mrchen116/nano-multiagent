# feat-425: 工具自带展示(含 emoji)——修复 web_search / web_fetch 渲染,展示真正随工具走

## Relations

- Related: refactor-406(决策 12:presentation travels with the Tool object)、feat-409(IM tool-call display,presenter passthrough)
- Closes: #131

## 原始需求

> ### Summary
>
> `web_search` and `web_fetch` currently render poorly in the IM chat panel. More importantly, the current presenter/emoji architecture deviates from the intent of **refactor-406 决策 12** ("presentation travels with the Tool object"), making it hard for first-party tools and impossible for user-defined tools to own their visual rendering.
>
> ### Current behavior
>
> #### `web_search`
> - Has **no presenter** at all (`src/personal_assistant/tools/web_search.py`).
> - Falls back to `_DefaultPresenter` in `src/agent/platform/tools/presentation.py`.
> - Collapsed row shows truncated JSON args: `🔧 web_search {"query":"...","count":3}`
> - Expanded card has no bespoke renderer → falls back to raw `<pre>` output string.
> - No emoji mapping in `tool-presentation.ts` → generic 🔧.
>
> #### `web_fetch`
> - Has a presenter, but the **collapsed row does not show the URL** — it shows `status=200 (title)`, which is machine-facing.
> - Tool returns `text`, presenter/frontend read `content`, and tool does not return `title`/`final_url` → **expanded `WebCard` likely shows URL + status with an empty body**.
> - Presenter class is defined centrally, not in `web_fetch.py`.
>
> ### Architecture problems
> 1. **Presenters for built-in tools are centralized** — All `_XxxPresenter` classes live in `src/agent/platform/tools/presentation.py`. Each built-in tool only imports and attaches the instance. This is only slightly better than the old global string-keyed registry, and it forces first-party tool changes to touch a central kernel file.
> 2. **User-defined tools cannot define emoji** — `ToolPresentationEvent` only carries `visible`/`label`/`summary`/`detail`. Emoji is resolved by a hard-coded frontend table in `src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts`. Any `.nano/tools/*.py`, MCP tool, or new product tool gets the generic 🔧.
> 3. **No presenter sharing actually happens** — The design says presenters "can be shared", but every built-in tool has its own 1:1 presenter class. The central file is not buying any reuse.
>
> ### Desired behavior
>
> #### For the two web tools
>
> | Tool | Collapsed row | Expanded card |
> |---|---|---|
> | `web_search` | `🔍 <query>` | Search-result card: title / URL / snippet list |
> | `web_fetch` | `🌐 <url>` | Web card: URL + status + extracted text |
>
> This mirrors the bash convention: collapsed row shows the human-facing primary argument (`description`/`command` for bash, `query` for search, `url` for fetch).
>
> #### For the architecture
> 1. Each tool file owns its own presenter class (especially product tools like `web_search`).
> 2. Emoji should be part of `ToolPresentationEvent` so the tool/presenter owns it, not a frontend name→emoji table.
> 3. `src/agent/platform/tools/presentation.py` should keep only: `ToolPresentationEvent`、`ToolPresenter` Protocol、`resolve_presenter_for_tool`、shared helpers (`_truncate`, `_enforce_cap`, etc.).
>
> ### Affected files
> - `src/personal_assistant/tools/web_search.py`
> - `src/agent/platform/tools/builtins/web_fetch.py`
> - `src/agent/platform/tools/presentation.py`
> - `src/IM/frontend/src/features/chat/v2/components/tool-presentation.ts`
> - `src/IM/frontend/src/features/chat/v2/components/tool-detail-renderers.tsx`
> - `src/agent/core/tools/presentation.py`
>
> ### Related design docs
> - `docs/changes/refactor-406-sdk-curated-surface/design.md` — 决策 12
> - `docs/changes/feat-409-im-tool-call-display/design.md` — presenter passthrough

## 澄清记录

- Q1: web_search 展开卡里 URL 是否可点击跳转?
  A(原话): 你从产品经理的角度思考,我信你
  Agent 决策: **不可点,做纯文本展示**(与 web_fetch 现状 `WebCard` 的 URL 一致,`tool-detail-renderers.tsx:236` 是纯文本 div)。
  理由:① 一致性——当前聊天面板所有工具卡的 URL 都是纯文本,单独给 web 工具开可点链接会割裂;② web_search 的结果 URL 来自上游搜索(不可信内容),从聊天面板直接点开未经确认的外链有安全面(target、来源校验、点击确认),那是独立一块,不该塞进本期"修渲染"。把"结果可点击跳转"列为非目标(后续单独立)。本期保证 URL 完整可读、可手动复制。

- Q2(Agent 自答,grounding 后定): web_fetch 抓取失败(网络错误 / URL 非法 / 4xx-5xx)时用户该看到什么?
  Agent 决策:折叠行仍显 `🌐 <url>`(主参数,与成功态同构),展开卡显**可读的错误信息或状态**,绝不出现空正文 / `status=None` 这类机器串。具体:网络错误/非法 URL → 展开显错误文案;4xx/5xx → 展开显 URL + 状态码 + 已抓到的正文(若有)。
  理由:对齐 feat-409 failalign 既定约定(失败态 summary = 干净主参数,error 进 detail 渲染一次,✕ 图标表达失败)。这是当前 `_WebFetchPresenter` 在工具实际返回 `error`/`text` 时会暴露的破绽(presenter 读 `result.error`,但 web_fetch 的失败在 `output["error"]` 里),必须一并修。

- Q3(Agent 自答): "presenter 类下沉到各工具文件"是否要全部 9 个内置工具都搬?
  Agent 决策:**spec 不约束 presenter 类的物理存放位置**——那是实现结构,非用户可观察,归 design.md 拍板。本 spec 的验收只盯用户能观察到的结果:两个 web 工具渲染正确、emoji 随工具走、自定义工具能拥有自己的 emoji。是否把全部 presenter 搬进各 builtin 文件,由 design 决定(issue 架构诉求 #1/#3 作为实现约束交接给 design-author)。
  理由:§4 硬约束——实现层标准不进 spec 验收(否则 reviewer 会滑进翻源码模式,整轮验收作废)。

- Q4(Agent 自答): emoji 进 `ToolPresentationEvent` 后,对用户的可观察增量是什么?
  Agent 决策:用户可观察的是——**自定义工具(`.nano/tools/*.py`)/ MCP 工具 / 新产品工具若声明了 emoji,IM 折叠行就显该 emoji**,不再一律 🔧;未声明 emoji 的工具仍回退通用 🔧(无回归);既有内置工具的 emoji 与渲染保持不变。
  理由:这是 issue 架构诉求 #2 唯一的用户可观察出口,写成验收 Scenario;而"emoji 字段加在事件还是别处""前端表怎么改"是实现,归 design。

## 用户场景

**谁**:在 IM 聊天面板里看 agent 工具调用记录的用户(产品自带 web 工具的使用者),以及给 agent 写自定义工具 / 接 MCP 工具的进阶用户。

**现状痛点(用户在产品上真实看到的):**

agent 在群聊里帮我查资料,调了 `web_search`。聊天面板里那一行折叠的工具记录,显示的是 `🔧 web_search {"query":"...","count":3}`——一个通用扳手图标加一截裸 JSON。我得在脑子里把 JSON 解出来才知道它搜了什么。点开想看结果,展开区是一坨原始字符串,不是我期望的"一条条结果"。

接着 agent 调 `web_fetch` 抓了个网页。折叠行写着 `status=200 (某标题)`——这是给机器看的,我根本不知道它抓的是哪个网址。点开展开卡,只有一行 URL 和状态码,**正文是空的**——它明明抓到了内容,却什么都没显示出来。

对比之下,同一个面板里 `bash` 的折叠行显示的是我让它干嘛(命令/描述),`read` 显示读了哪个文件——一眼就懂。两个 web 工具偏偏是异类。

我还自己给 agent 写过一个 `.nano/tools/` 下的小工具。它在面板里永远是通用扳手 🔧,我没办法让它显示一个能一眼认出来的图标——哪怕我很想给它配个专属 emoji。

**变更后我期望看到的:**

- `web_search` 折叠行直接显示 `🔍 我搜的那句话`;点开是一张搜索结果卡,一条条列出标题、网址、摘要。搜不到东西时明确告诉我"没有结果",而不是空白。搜索本身出错(比如服务不可用)时,这一行标红、点开能看到出错原因。
- `web_fetch` 折叠行显示 `🌐 它抓的那个网址`;点开能看到网址、状态码,以及**抓到的正文内容**。抓取失败时,折叠行仍显示网址、点开看到可读的错误说明,不会再出现空正文或 `status=None` 这种机器串。
- 我给 agent 写的自定义工具,只要我给它配了 emoji,面板折叠行就显示我配的那个图标;没配的工具继续显示通用扳手(和现在一样,不退化)。
- 其它既有工具(bash / read / edit / write / agent / memory / 等)的图标和展示跟现在完全一样,不受影响。

## 验收标准

### Requirement: web_search 折叠行显示人话主参数

#### Scenario: 正常搜索
- **WHEN** agent 调用 `web_search` 搜索某个查询词且搜索成功
- **THEN** 聊天面板该工具调用的折叠行显示 `🔍` 图标 + 查询词文本(如 `🔍 nano multiagent 架构`)
- **AND** 不再出现裸 JSON args 或通用 🔧 图标

#### Scenario: 搜索失败(服务不可用 / provider 报错)
- **WHEN** `web_search` 因 provider 不可用或报错而失败
- **THEN** 折叠行仍显示 `🔍` + 查询词(主参数,不拼接错误文本)
- **AND** 该行呈失败态(✕ / 标红),展开后能看到出错原因

### Requirement: web_search 展开卡按结果条目渲染

#### Scenario: 有搜索结果
- **GIVEN** 一次成功的 `web_search` 返回了若干条结果
- **WHEN** 用户点开该工具调用
- **THEN** 展开区按条目列出每条结果的标题、网址、摘要,而不是一坨原始字符串
- **AND** 网址以完整可读的纯文本展示(可手动复制)

#### Scenario: 无搜索结果(空态)
- **WHEN** `web_search` 成功执行但查询无任何命中
- **THEN** 展开区显示明确的"无结果"空态文案,而不是空白或原始字符串

### Requirement: web_fetch 折叠行显示抓取的网址

#### Scenario: 正常抓取
- **WHEN** agent 调用 `web_fetch` 抓取某 URL 且抓取成功
- **THEN** 折叠行显示 `🌐` 图标 + 该 URL(如 `🌐 https://example.com/doc`)
- **AND** 不再显示 `status=200 (title)` 这类机器视角文案

#### Scenario: 抓取失败(网络错误 / 非法 URL / 4xx-5xx)
- **WHEN** `web_fetch` 因网络错误、URL 非法或服务端返回 4xx/5xx 而未取到正常内容
- **THEN** 折叠行仍显示 `🌐` + 该 URL
- **AND** 展开区显示可读的错误说明或状态码,绝不出现空正文或 `status=None` 这类机器串

### Requirement: web_fetch 展开卡显示抓到的正文

#### Scenario: 抓取成功有正文
- **GIVEN** 一次成功的 `web_fetch` 抓到了网页正文
- **WHEN** 用户点开该工具调用
- **THEN** 展开区显示网址、状态码,以及抓取到的正文文本(正文非空)

### Requirement: 工具自带 emoji,自定义工具可拥有专属图标

#### Scenario: 自定义 / MCP 工具声明了 emoji
- **GIVEN** 用户为一个 `.nano/tools/` 自定义工具(或 MCP / 新产品工具)配置了专属 emoji
- **WHEN** agent 调用该工具,记录出现在聊天面板
- **THEN** 折叠行显示该工具自带的 emoji,而非通用 🔧

#### Scenario: 工具未声明 emoji(回退,不退化)
- **WHEN** agent 调用一个未声明 emoji 的工具(自定义 / MCP)
- **THEN** 折叠行回退显示通用 🔧 图标(与当前行为一致)

#### Scenario: 既有内置工具不受影响(回归保护)
- **WHEN** agent 调用 bash / read / edit / write / agent / memory / skill_manage / task_stop 任一既有内置工具
- **THEN** 其折叠行图标与展开卡渲染与本次变更前完全一致

## 范围与非目标

- 在范围:
  - `web_search` 获得自己的展示(折叠行 `🔍 <query>` + 搜索结果卡:标题/网址/摘要列表 + 无结果空态 + 失败态)。
  - `web_fetch` 折叠行改为 `🌐 <url>`;修复展开卡正文为空 / 字段错配 / 失败态机器串的缺陷。
  - emoji 成为工具自带的展示要素:工具/presenter 拥有自己的 emoji,自定义/MCP 工具可声明专属图标,未声明者回退 🔧。
  - 既有内置工具的图标与渲染零回归。
- 非目标:
  - **搜索结果 / 网址的可点击跳转**(点开外链有独立的安全面:来源校验、点击确认、新标签策略;本期只保证 URL 可读可复制,跳转后续单独立单)。
  - 重排其它内置工具(read/bash/edit/...)的折叠文案或展开卡内容(仅在实现上可能涉及 presenter 类位置调整,但用户可观察行为不变,属 design 决策)。
  - 改动 web_search / web_fetch 的搜索 provider、抓取逻辑、权限模型、SSRF 校验等非展示层行为。
  - 给所有工具补 emoji 或重新设计 emoji 体系——本期只打通"工具能自带 emoji"的通路 + 让两个 web 工具用上,不做全量 emoji 重定。
