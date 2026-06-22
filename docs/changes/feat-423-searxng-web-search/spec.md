# feat-423: web_search 支持 SearXNG 自建搜索 provider

## Relations

- Closes: #132
- Related: web_search 现有 provider（duckduckgo / brave）

## 原始需求

用户提供 GitHub issue 链接 `https://github.com/Mrchen116/nano-multiagent/issues/132`，并补充一句「参考hermes agent」。

issue #132 原文关键句（feat(web_search): 支持 SearXNG 自建搜索，提供稳定免费的 agent 搜索方案）：

> 当前 `WebSearchTool` 只支持两个 provider：`duckduckgo`（完全免费、无需 key，但频繁触发 `RatelimitException` / 429，稳定性和结果质量不够生产级）；`brave`（需要 `BRAVE_API_KEY`，2026 年起 Brave 取消免费 tier）。随着 agent 工作流对实时搜索的依赖越来越强，默认的 DuckDuckGo 方案在并发或长时间研究任务中很容易碰壁。我们需要一条**稳定、免费、可自建**的搜索路径。

> 新增 `searxng` provider，接入 SearXNG 自建实例。SearXNG 是隐私优先的开源元搜索引擎，自己没有索引，把同一个查询并行发给 Google/Bing/DuckDuckGo/Brave 等 70+ 上游引擎，聚合去重排序后返回 JSON。只要有一台能跑 Docker 的机器，就能零 API 成本获得接近无限的搜索能力。

> 具体实现：在 `src/personal_assistant/tools/web_search.py` 新增 `_search_searxng`：从环境变量读取 `SEARXNG_URL`（例如 `http://localhost:8888`）；调用 `GET {SEARXNG_URL}/search?q={query}&format=json&pageno=1`；解析 `results` 列表归一化为 `{title, url, snippet}`；保持**仅搜索**语义（不替代 `web_fetch` 做全文提取）；可选在 tool schema 里支持 `categories`、`engines`、`language`、`safesearch` 等参数。

> 验收标准（issue 原文勾选项）：
> - [ ] `web_search` 工具支持 `provider: "searxng"`。
> - [ ] 当 `SEARXNG_URL` 已设置时，可作为默认或显式选择使用。
> - [ ] 返回结果归一化为现有 `{title, url, snippet}` 格式。
> - [ ] 补充单测：正常返回、实例不可达错误、空结果。
> - [ ] README / AGENTS.md 增加 SearXNG Docker 一键部署说明。

> 参考实现：Hermes Agent 的 `plugins/web/searxng/provider.py` 约 100 行，读取 `SEARXNG_URL` → `httpx.get(.../search?format=json)` → 排序截断 → 返回 `{title, url, description}`。

## 澄清记录

- Q1: `SEARXNG_URL` 设置后，searxng 自动成为默认 provider，还是只在显式传 `provider: "searxng"` 时才用？
  A(原话): ok
  Agent 解读: 认可推荐——设置了 `SEARXNG_URL` 就自动当默认（不显式指定 provider 的调用都走 searxng）；调用方显式传别的 provider 时仍尊重其选择。

- Q2: 走 searxng 但失败时（(a) 实例不可达/错误状态，(b) 选了 searxng 但 `SEARXNG_URL` 未设），期望看到什么？
  A(原话): ok
  Agent 解读: 认可推荐——两种都 fail loud（报清晰错误，指明 searxng 不可达 / URL 未配置），不静默回退到 duckduckgo。此方向与现状契约一致：现有代码 + `tests/unit/personal_assistant/test_web_search_tool.py` 已钉「provider 失败 ≠ 零结果，必须 raise 不能吞掉」（refactor-395 触及过 web_search，其 design 当时写的「返回空列表」已被实际实现/测试推翻，以测试为准）。

- Q3: issue 提到的可选参数（`categories` / `engines` / `language` / `safesearch`）本期做不做？
  A(原话): ok
  Agent 解读: 认可推荐——本期不做，只做核心 `provider: "searxng"` + 复用现有 `query` / `count`；可选参数列入非目标。hermes 参考实现本身也只发 `q/format/pageno`。

## 用户场景

某用户的 agent 长时间跑研究任务，频繁调用 `web_search`。默认的 duckduckgo 隔三差五撞 429，结果质量也参差，研究链路时断时续。用户在自己的服务器上用 Docker 起了一个 SearXNG 实例（一条 `docker compose up -d`），把 `SEARXNG_URL` 指过去。

从此他不需要改任何调用代码：agent 发出的每一次不带 provider 的 `web_search`，都自动走 SearXNG —— 由它并行问 Google/Bing/DuckDuckGo 等上游、聚合去重后返回。结果和以前一样是一串 `{title, url, snippet}`，agent 拿去该读哪条读哪条（全文提取仍归 `web_fetch`，SearXNG 只负责「搜」）。稳定、免费、不再被单一引擎限流卡住。

偶尔他想对照一下别的源，仍可以显式传 `provider: "duckduckgo"` / `"brave"`，这时工具尊重他的显式选择，不会因为配了 `SEARXNG_URL` 就强行走 SearXNG。

如果某天 SearXNG 实例挂了（容器没起、端口不通、返回 5xx），他不希望搜索悄悄退回那个他本来就想绕开的 duckduckgo 把问题盖住 —— 他希望工具明确报错「SearXNG 不可达」，好让他去把实例修起来。同样，如果他选了 searxng 却忘了设 `SEARXNG_URL`，也应当得到一句清楚的「URL 未配置」而不是莫名其妙的空结果。

第一次接触这个能力的用户，应当能在 README / AGENTS.md 里找到一段 SearXNG 的 Docker 一键部署 + 启用 JSON 格式 + 设 `SEARXNG_URL` 的说明，照着做就能跑起来。

## 验收标准

### Requirement: 新增 searxng provider 并支持显式选择

#### Scenario: 显式选择 searxng 返回正常结果
- **GIVEN** 一个可用的 SearXNG 实例，`SEARXNG_URL` 已指向它
- **WHEN** 调用 `web_search` 并传 `provider: "searxng"` 和一个有命中的 query
- **THEN** 返回 `ok: true`，`provider: "searxng"`，`results` 为一串 `{title, url, snippet}`，条数不超过 `count`

#### Scenario: 结果归一化为现有格式
- **GIVEN** SearXNG 实例对某 query 返回多条结果
- **WHEN** 通过 searxng 搜索
- **THEN** 每条结果都归一化为 `{title, url, snippet}` 三个字段（与 duckduckgo / brave 输出结构一致），按相关性排序，截断到 `count`

### Requirement: 配置了 SEARXNG_URL 时 searxng 自动成为默认

#### Scenario: 设了 SEARXNG_URL 且不指定 provider
- **GIVEN** `SEARXNG_URL` 已设置
- **WHEN** 调用 `web_search` 只传 `query`、不传 `provider`
- **THEN** 实际走 searxng（返回 `provider: "searxng"`）

#### Scenario: 设了 SEARXNG_URL 但显式指定别的 provider
- **GIVEN** `SEARXNG_URL` 已设置
- **WHEN** 调用 `web_search` 显式传 `provider: "duckduckgo"`
- **THEN** 走 duckduckgo（返回 `provider: "duckduckgo"`），不被 SEARXNG_URL 强制改走 searxng

#### Scenario: 未设 SEARXNG_URL 时默认保持 duckduckgo
- **GIVEN** `SEARXNG_URL` 未设置
- **WHEN** 调用 `web_search` 只传 `query`、不传 `provider`
- **THEN** 默认仍走 duckduckgo（行为与本 unit 之前一致）

### Requirement: searxng 失败时明确报错，不静默回退

#### Scenario: SEARXNG_URL 已设但实例不可达
- **GIVEN** `SEARXNG_URL` 指向一个连不上 / 返回错误状态的地址
- **WHEN** 通过 searxng 搜索
- **THEN** 工具报错（而非返回空结果或悄悄回退 duckduckgo），错误信息可看出是 SearXNG 不可达

#### Scenario: 选了 searxng 但未设 SEARXNG_URL
- **WHEN** 显式传 `provider: "searxng"` 而 `SEARXNG_URL` 未设置
- **THEN** 工具报错，错误信息可看出是 SEARXNG_URL 未配置

#### Scenario: searxng 实例正常但 query 无命中
- **GIVEN** `SEARXNG_URL` 已设且实例可用
- **WHEN** 通过 searxng 搜索一个无任何命中的 query
- **THEN** 返回 `ok: true`，`results` 为空列表（实例工作正常、确实没结果 ≠ 失败）

### Requirement: 提供 SearXNG 部署文档

#### Scenario: 用户查阅部署说明
- **WHEN** 用户在 README / AGENTS.md 中查找如何启用 SearXNG
- **THEN** 能看到一段 Docker 一键部署 + 启用 JSON 格式 + 设置 `SEARXNG_URL` 的可照做说明

## 范围与非目标

- 在范围：
  - `web_search` 新增 `searxng` provider；`SEARXNG_URL` 已设时自动作默认、显式 provider 仍优先。
  - 结果归一化为现有 `{title, url, snippet}`；正常 / 空结果 / 实例不可达 / URL 未配置的单测。
  - README / AGENTS.md 增加 SearXNG Docker 部署说明。
- 非目标：
  - `categories` / `engines` / `language` / `safesearch` 等可选搜索参数（issue 标注「可选」，本期不做，需要时另开 unit）。
  - SearXNG 实例本身的运维 / 监控 / 鉴权。
  - 用 SearXNG 做全文提取（仍归 `web_fetch`，本工具保持「仅搜索」语义）。
  - searxng 失败时回退到其他 provider（明确不做，见验收标准第三组）。
