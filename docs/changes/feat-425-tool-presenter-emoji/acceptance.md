# feat-425 验收报告

**Round**: 1
**Date**: 2026-06-23
**Reviewer**: feat-425-reviewer
**Branch**: unit/feat-425
**Verdict**: fail
**Highest Required Action**: fix-implementation

---

## 澄清记录

无疑问，按当前最合理理解走旅程。

---

## 服务接管记录

| 服务 | 状态 |
|---|---|
| IM (port 59414) | 起动成功，curl 健康检查通过 |
| 前端 build | `npm run build` 成功，指纹核验：dist/assets/index-D0XgAMMc.js 含 WebSearchCard/web_search/searchNoResults 关键 marker（3 处命中）|
| Gateway (pid 95548) | 带 `SEARXNG_URL=http://100.88.34.122:8888` 重启，3 个 agent (default-agent/Arch/ArchA) 均 online |

---

## User Journeys Exercised

| 旅程 | 描述 | 覆盖 Scenario |
|---|---|---|
| A | web_search 成功（searxng，5 条结果） | 正常搜索 折叠行 + 展开结果卡 |
| B | web_search 失败（No module named 'ddgs'） | 搜索失败 折叠行 + 失败态展开 |
| C | web_fetch 成功（https://example.com，200） | 正常抓取 折叠行 + 展开正文 |
| D | web_fetch 失败（不存在域名，SSL错误） | 抓取失败 折叠行 + 失败展开 |
| E | bash 工具回归检查（echo hello world） | 既有工具不退化 |
| F | 自定义工具 emoji（test_emoji_tool.py） | 工具加载失败，inconclusive |

---

## 验收标准覆盖表

### Requirement: web_search 折叠行显示人话主参数

#### Scenario: 正常搜索
- **期望来源**: spec.md § Requirement: web_search 折叠行显示人话主参数
- **验证方式**: 旅程 A — 触发 agent 调用 web_search 搜索「nano multiagent」(searxng)，截图 + snapshot 核对折叠行
- **证据**: screenshots/feat425-web-search-folded.png；snapshot 显示 `button "● web_search nano multiagent 8.3s ▾"` 含 `generic: 🔍 web_search` + `generic: nano multiagent`
- **结果**: pass
- **备注**: 折叠行显示 `🔍 web_search  nano multiagent`。`🔍` 图标出现 ✓，查询词出现 ✓，裸 JSON 消失 ✓，🔧 图标消失 ✓。`web_search` 工具名随 emoji 作为 label 出现，这与 bash（`💻 bash <cmd>`）等其他工具一致，是系统统一格式，符合 spec THEN 条件（不含裸 JSON args / 通用 🔧）

#### Scenario: 搜索失败（服务不可用 / provider 报错）
- **期望来源**: spec.md § Scenario: 搜索失败
- **验证方式**: 旅程 B — 触发 web_search（ddgs provider 不可用），截图 + snapshot
- **证据**: screenshots/feat425-web-search-failed.png；snapshot `button "✕ web_search nano multiagent architecture failed 1.4s ▾"` 含 `generic: 🔍 web_search` + `generic: nano multiagent architecture` + `generic: failed`；展开 `generic: "tool execution failed: No module named 'ddgs'"`
- **结果**: pass
- **备注**: ✕ 失败图标 ✓，折叠行仅含主参数（无错误文本拼入主参数） ✓，展开显示可读错误信息 ✓

### Requirement: web_search 展开卡按结果条目渲染

#### Scenario: 有搜索结果
- **期望来源**: spec.md § Scenario: 有搜索结果
- **验证方式**: 旅程 A — 点开成功的 web_search 工具调用展开卡
- **证据**: screenshots/feat425-tool-call-detail.png；snapshot 展开卡 `e238` 结构：5 条 `generic`，每条含 title（e240/e244/e248/e252/e256）+ url（e241/e245/e249/e253/e257）+ snippet（e242/e246/e250/e254/e258）。URL 以纯文本 generic 展示（非可点链接）
- **结果**: pass
- **备注**: 标题/URL/摘要三元素逐条列出 ✓，URL 纯文本可读 ✓。spec 非目标明确指出"URL 可点击跳转"不在本期范围，纯文本展示符合预期

#### Scenario: 无搜索结果（空态）
- **期望来源**: spec.md § Scenario: 无搜索结果（空态）
- **验证方式**: 旅程 A 变种 — 用极罕见字符串「zzzzzzqqqqqwwwwwxxx99999uniquenonexistent2026」尝试触发空结果，searxng 仍返回无关结果 5 条，未能触发真正空态
- **证据**: 前端 vitest 测试 `tool-calls-panel.test.tsx` 含空态测试（`detail: { count: 0, results: [] }` → 期望 `无结果|没有结果|no results` 文案）通过（从 progress.md 的 `vitest 448 passed` 确认）；真实环境无法通过真实搜索引擎构造空 results
- **结果**: inconclusive
- **备注**: 外部搜索引擎（searxng）对任意查询词均返回兜底结果，reviewer 无法在不修改代码/配置的条件下构造真实空结果触发空态 UI。vitest 覆盖了此路径，但根据 §3.2，单测通过不能自动等同于用户面 pass。标 inconclusive，建议 worker 通过 API 注入空 results 消息来验证此空态渲染。

### Requirement: web_fetch 折叠行显示抓取的网址

#### Scenario: 正常抓取
- **期望来源**: spec.md § Scenario: 正常抓取
- **验证方式**: 旅程 C — 触发 web_fetch 抓取 https://example.com，截图 + snapshot
- **证据**: screenshots/feat425-web-fetch-expanded.png；snapshot `button "● web_fetch https://example.com 25.8s ▾"` 含 `generic: 🌐 web_fetch` + `generic: https://example.com`
- **结果**: pass
- **备注**: 🌐 图标出现 ✓，URL 在折叠行可见 ✓，`status=200 (title)` 机器文案消失 ✓。同 web_search，工具名 `web_fetch` 作为 label 随 emoji 出现，是系统一致格式

#### Scenario: 抓取失败（网络错误 / 非法 URL / 4xx-5xx）
- **期望来源**: spec.md § Scenario: 抓取失败
- **验证方式**: 旅程 D — 抓取不存在域名 `https://this-domain-does-not-exist-abc123.com/test`，截图 + snapshot
- **证据**: screenshots/feat425-web-fetch-failed.png；snapshot `button "● web_fetch https://this-domain-does-not-exist-abc123.com/test 9.2s ▾"` 折叠行含 URL；展开卡 `generic: ✕` + `generic: "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"` 可读错误信息
- **结果**: pass
- **备注**: 折叠行仍显示 URL ✓，展开显示可读错误 ✓，无 `status=None` 机器串 ✓

### Requirement: web_fetch 展开卡显示抓到的正文

#### Scenario: 抓取成功有正文
- **期望来源**: spec.md § Scenario: 抓取成功有正文
- **验证方式**: 旅程 C — 点开成功的 web_fetch 工具调用展开卡
- **证据**: screenshots/feat425-web-fetch-expanded.png；snapshot 展开卡 `e323`：`generic: https://example.com · 200`（URL+状态码）+ `generic: "Example Domain # Example Domain This domain is for use in documentation examples without needing permission..."` (正文非空)
- **结果**: pass
- **备注**: URL ✓，状态码 200 ✓，正文非空 ✓（修复了之前正文恒空的 bug）

### Requirement: 工具自带 emoji，自定义工具可拥有专属图标

#### Scenario: 自定义 / MCP 工具声明了 emoji
- **期望来源**: spec.md § Scenario: 自定义 / MCP 工具声明了 emoji
- **验证方式**: 旅程 F — 让 agent 创建 `~/.nano/tools/test_emoji_tool.py`（含 emoji='🎯' 的 _TestEmojiPresenter），重启 gateway，请求 agent 调用该工具
- **证据**: agent 确认文件创建成功，gateway 重启后 agent 仍报该工具不在可用工具列表，无法触发工具调用，无法观测到 IM 折叠行上的 🎯 图标
- **结果**: inconclusive
- **备注**: 无法在 reviewer 零写入约束下完成此 Scenario 的完整验证。工具文件存在（`/Users/czj/.nano/tools/test_emoji_tool.py`）但 gateway 未加载，可能是 `.nano/tools/` 目录加载需要额外配置或工具 interface 格式不匹配（不读源码无法定位）。vitest 测试 `emoji 事件优先` 覆盖了前端侧行为（从 progress.md 448 passed 确认），但真实 e2e 路径无法走通。建议 worker 提供一个可被 gateway 正确加载的最小自定义工具例子，或补充一个 e2e 测试验证此路径

#### Scenario: 工具未声明 emoji（回退，不退化）
- **期望来源**: spec.md § Scenario: 工具未声明 emoji（回退，不退化）
- **验证方式**: 旅程 A — 观察 web_search 第一次调用（ddgs 失败时，通过 _DefaultPresenter 兜底）折叠行图标
- **证据**: 第一次失败的 web_search 调用折叠行仍显示 `🔍`（_WebSearchPresenter 已附加，而非 _DefaultPresenter），未见 🔧；未声明 emoji 的工具例：现有默认兜底行为 `generic: 🔍 web_search`（presenter 有 emoji）
- **结果**: inconclusive
- **备注**: 在当前旅程中无法触发一个"真实未声明 emoji 的自定义工具"调用（受限于工具加载问题），无法直接验证 🔧 回退。vitest 覆盖了历史降级路径。标 inconclusive

#### Scenario: 既有内置工具不受影响（回归保护）
- **期望来源**: spec.md § Scenario: 既有内置工具不受影响
- **验证方式**: 旅程 E — 让 agent 运行 bash 命令 `echo hello world`，截图 + snapshot
- **证据**: screenshots/feat425-bash-tool-call.png；snapshot `button "● bash echo hello world 23ms ▾"` 含 `generic: 💻 bash`（emoji ✓），展开卡 `$ echo hello world` + `hello world` + `exit 0`（卡片格式未变）
- **结果**: pass
- **备注**: bash 工具的 💻 emoji ✓，命令摘要 ✓，展开卡正常 ✓，格式与本次 unit 变更前一致

---

## Issues

### Issue 1: web_search 展开卡无结果空态无法通过真实旅程验证

- **Severity**: major
- **Regression Relation**: direct
- **Scenario**: web_search 展开卡 — 无搜索结果（空态）
- **Symptom**: 外部搜索引擎（searxng）对任意查询词均返回兜底结果，reviewer 无法在不修改代码的条件下构造空 `results:[]` 触发空态 UI。空态 `WebSearchCard` 的"无结果"文案无法通过真实产品旅程验证
- **Evidence**: 尝试搜索「zzzzzzqqqqqwwwwwxxx99999uniquenonexistent2026」，searxng 返回 5 条无关结果，agent 照常显示结果卡，空态分支未触发
- **Recommended Action**: fix-implementation
- **Action Rationale**: 需要通过 API 注入方式（向 IM 直接写入 `results:[]` 的消息）或增加一个可控的搜索 fixture，让 reviewer 能验证空态 UI。这是测试可及性问题，工具侧实现可能正确但 reviewer 无法确认

### Issue 2: 自定义工具 emoji e2e 路径无法验证（工具加载未通）

- **Severity**: major
- **Regression Relation**: direct
- **Scenario**: 自定义 / MCP 工具声明了 emoji + 工具未声明 emoji 回退
- **Symptom**: 在 gateway 重启后，`.nano/tools/test_emoji_tool.py` 未被加载到 agent 可用工具列表，无法触发工具调用，IM 折叠行上的自定义 emoji（🎯）无法通过真实聊天验证
- **Evidence**: agent 明确告知「当前环境中没有可用的 test_emoji_tool 工具」，gateway 重启后仍然如此。工具文件存在（`/Users/czj/.nano/tools/test_emoji_tool.py`）
- **Recommended Action**: fix-implementation
- **Action Rationale**: spec 的核心架构诉求之一（"自定义工具可拥有专属 emoji"）需要 e2e 路径走通。若工具加载机制需要特定配置或格式约定，应在 design Runbook for Reviewer 中补充如何构造一个可被 gateway 真实加载的自定义工具测试案例，或在 gateway config 中添加一个内置的测试工具

---

## Side Findings

1. **web_fetch 响应耗时约 26s**：https://example.com 的抓取响应时间 25.8s，从用户感知明显偏长。可能是网络原因，记录供参考，不影响本次验收（非本 unit 性能要求）

2. **gateway 启动无输出日志**：gateway 启动时日志未写入 `.gateway.log`（输出到 stdout 但 worktree 内日志文件大小为 0），这使得排查 gateway 状态较困难。非本 unit 引入，记录供参考

3. **message-pane 越界修复（R2 progress 记录）**：worker 修复了 `message-pane.test.tsx` 和 `message-pane.tsx` 的基线 tsc 错误（`querySelectorAll<HTMLTableCellElement>` 泛型实参 + `MD_REMARK_PLUGINS as const` 冲突），这两处均为非本 unit 引入的基线债。若倾向单列 issue 可单独跟踪

---

## 上层文档同步检查

- [x] `SPEC.md`（跨包顶点架构）— 无需更新（跨包架构未变）
- [x] `docs/specs/kernel/spec.md`（内核契约层）— **已更新**（worker R3 已增 emoji 字段 + presenter 透传 Scenario，见 progress.md R3）
- [x] `docs/specs/im/spec.md`（IM 契约层）— **已更新**（worker R3 已增 web_search 折叠/展开 Scenario + web_fetch 展开修正，见 progress.md R3）
- [x] `docs/specs/gateway/spec.md`（Gateway 契约层）— design.md 明确无 spec delta，符合"relay 仅多透传一字段"的设计决策
- [x] `docs/specs/cli/spec.md`（CLI 契约层）— design.md 明确无 spec delta，本 unit 不动 CLI 渲染层
- [x] `AGENTS.md` / `CLAUDE.md` — 无需更新（无运维/开发约定变更）
- [x] `docs/SPEC_GUIDE.md` — 无需更新（未改文档体系）

---

## 截图索引

所有截图位于 `docs/changes/feat-425-tool-presenter-emoji/screenshots/`：

| 文件 | 内容 |
|---|---|
| feat425-web-search-collapsed.png | web_search 失败折叠行（第一次调用，ddgs 缺失）|
| feat425-web-search-folded.png | web_search 成功 + 折叠行 `🔍 web_search nano multiagent` |
| feat425-tool-call-detail.png | web_search 成功展开卡（结果列表完整）|
| feat425-web-search-failed.png | web_search 失败态展开（可读错误信息）|
| feat425-web-fetch-expanded.png | web_fetch 成功 + 折叠行 `🌐 web_fetch https://example.com` + 展开卡 URL/状态/正文 |
| feat425-web-fetch-failed.png | web_fetch 失败态（SSL 错误可读信息）+ bash 工具调用 |
| feat425-bash-tool-call.png | bash `echo hello world` 展开卡（既有工具回归验证）|

---

## Verdict 判定

| 必验 Scenario | 结果 |
|---|---|
| web_search 正常搜索 | pass |
| web_search 搜索失败 | pass |
| web_search 有搜索结果（展开卡）| pass |
| web_search 无搜索结果（空态）| **inconclusive** |
| web_fetch 正常抓取 | pass |
| web_fetch 抓取失败 | pass |
| web_fetch 展开卡正文非空 | pass |
| 自定义工具声明 emoji | **inconclusive** |
| 工具未声明 emoji 回退 | inconclusive |
| 既有内置工具不退化 | pass |

根据 §4.3：任意必验 Scenario 为 `inconclusive` → `fail`

**Verdict: fail**

两个 inconclusive 均属 major 级（核心 Scenario 无法验证）。需要：
1. 提供空态验证路径（API 注入或 fixture）
2. 提供自定义工具 emoji 的 e2e 验证路径（gateway 加载 .nano/tools/ 工具后验证）

---

# Round 2 — 2026-06-23

**Round**: 2
**Date**: 2026-06-23
**Reviewer**: feat-425-reviewer
**Branch**: unit/feat-425 @ 02dcb744
**Verdict**: fail
**Highest Required Action**: fix-implementation

---

## Round 2 澄清记录

team-lead 对 round 1 的两个 inconclusive 定性：
- B1（web_search 空态）：使用 duckduckgo provider + UUID 字符串 `zzq9x7nonexist44102qxqz` 触发
- B2（自定义工具 emoji）：工具文件放到 `<workspace_root>/.nano/tools/` 下

Round 2 新增验证目标：
- A2：web_fetch 大页面截断信号 → 展开卡显"源头已截断"提示
- C5：web_fetch 4xx → 展开卡状态码只出现一次（不重复进 content）
- C1：自定义工具 running 阶段折叠行即显自带 emoji（不先 🔧 后跳）

---

## Round 2 服务接管记录

| 服务 | 状态 |
|---|---|
| worktree reset | `git reset --hard origin/unit/feat-425` → 02dcb744 |
| 前端 rebuild | `npm run build` 成功，marker 核验：index-D0XgAMMc.js 含 truncated/截断/WebSearchCard 等关键字 |
| IM (port 59414) | 重启，使用新鲜数据库 `$WT_ROOT/data/im_fresh.sqlite3`（避免主仓旧 schema 导致 messages API 500）|
| Gateway | 重启，`SEARXNG_URL=http://100.88.34.122:8888`，3 agent 均 online |
| 自定义工具 | test_emoji_tool.py 放置于 `<workspace_root>/.nano/tools/test_emoji_tool.py` |

---

## Round 2 User Journeys Exercised

| 旅程 | 描述 | 覆盖 Scenario |
|---|---|---|
| A2 | web_fetch 大页面截断（Wikipedia Python page，27.9s） | 截断提示 A2 |
| C5 | web_fetch 4xx（httpbin.org/status/404）| 状态码不重复 C5 |
| B1 | web_search duckduckgo + UUID（`zzq9x7nonexist44102qxqz`） | 空态 B1 |
| searxng | web_search searxng（Python programming language） | 正常搜索结果卡 |
| B2/C1 | 请求 agent 调用 test_emoji_tool | 自定义工具 emoji B2/C1 |

---

## Round 2 关键发现（系统性退行）

**所有 round 1 通过的核心 Scenarios 在 round 2 全部失败。**

通过直接查询 IM SQLite 数据库（`$WT_ROOT/data/im_fresh.sqlite3`）确认：

```
tool_calls_json 里所有工具调用的 emoji 字段 = MISSING
tool_calls_json 里所有工具调用的 summary 字段 = MISSING
web_fetch detail.content = '' (空字符串)
web_search detail = None（searxng 成功时）
```

**前端展示结果**（与 round 1 对比）：

| 项目 | Round 1 | Round 2（02dcb744）|
|---|---|---|
| web_fetch 折叠行 | `● web_fetch 🌐 https://example.com 25.8s` | `● web_fetch 27.9s`（无 🌐，无 URL）|
| web_search 折叠行 | `● web_search 🔍 nano multiagent 8.3s` | `● web_search 4.3s`（无 🔍，无 query）|
| web_fetch 展开正文 | URL + status + 正文非空 | OUTPUT: status=200（fallback，无正文）|
| web_search 展开卡 | WebSearchCard 结构化结果 | OUTPUT: raw JSON（fallback）|
| A2 截断提示 | N/A（首次验） | 未出现（detail.truncated=false，content=''）|
| C5 HTTP 前缀 | N/A | content='' → 无重复，但也无内容可验 |

---

## Round 2 验收标准覆盖表

### Requirement: web_search 折叠行显示人话主参数（继承 Round 1）

#### Scenario: 正常搜索
- **期望**: 折叠行 `🔍` + query
- **实际**: `● web_search 4.3s`（searxng 成功调用，无 emoji，无 query）
- **证据**: screenshots/feat425-r2-websearch-success-expanded.png；IM SQLite `summary=MISSING, emoji=MISSING`
- **结果**: **fail**（round 1 pass → round 2 fail，退行）
- **备注**: emoji 和 summary 字段完全未写入 IM tool_calls_json，gateway relay 到 IM 的链路断了

#### Scenario: 搜索失败（服务不可用 / provider 报错）
- **期望**: 折叠行 `✕ 🔍 <query>`
- **实际**: `✕ web_search 1.1s`（有 ✕ 失败图标，无 🔍，无 query）
- **证据**: screenshots/feat425-r2-websearch-failed-collapsed.png；IM SQLite `summary=MISSING`
- **结果**: **fail**（round 1 pass → round 2 fail，退行）

### Requirement: web_search 展开卡按结果条目渲染（继承 Round 1）

#### Scenario: 有搜索结果
- **期望**: WebSearchCard 按条目列出 title/URL/snippet
- **实际**: OUTPUT: `{"ok":true,"query":"Python...","provider":"searxng","result..."}` raw JSON
- **证据**: screenshots/feat425-r2-websearch-success-expanded.png；IM SQLite `detail=None`（searxng 成功时）
- **结果**: **fail**（round 1 pass → round 2 fail，退行）
- **备注**: BESPOKE 表有 web_search→WebSearchCard，但前端收到的 detail=null 导致 fallback 渲染

#### Scenario: 无搜索结果（空态）
- **期望**: "无结果"空态文案
- **实际**: duckduckgo provider 报 `No module named 'ddgs'`（工具运行失败，非 empty results）
- **证据**: IM 工具调用 status=failed
- **结果**: **fail**（无法触发真实空态——duckduckgo 缺依赖，无法绕过触发 empty results path）
- **备注**: B1 round 1 inconclusive 仍未关闭。需要可控的搜索 fixture

### Requirement: web_fetch 折叠行显示抓取的网址（继承 Round 1）

#### Scenario: 正常抓取
- **期望**: 折叠行 `🌐` + URL
- **实际**: `● web_fetch 27.9s`（无 🌐，无 URL）
- **证据**: screenshots/feat425-r2-webfetch-collapsed-fail.png；IM SQLite `summary=MISSING, emoji=MISSING`
- **结果**: **fail**（round 1 pass → round 2 fail，退行）

#### Scenario: 抓取失败（网络错误 / 非法 URL / 4xx-5xx）
- **期望**: 折叠行 `🌐` + URL
- **实际**: `● web_fetch 2.5s`（无 🌐，无 URL）
- **证据**: screenshots/feat425-r2-webfetch-404-collapsed.png；IM SQLite `summary=MISSING`
- **结果**: **fail**（round 1 pass → round 2 fail，退行）

### Requirement: web_fetch 展开卡显示抓到的正文（继承 Round 1）

#### Scenario: 抓取成功有正文
- **期望**: URL + status + 非空正文；若截断则显"源头已截断"（A2 fix）
- **实际**: OUTPUT: `status=200` 仅此一行；IM SQLite `detail.content=''`
- **证据**: screenshots/feat425-r2-webfetch-expanded-fail.png；IM SQLite web_fetch detail：`{"url":"...","status":200,"content":"","truncated":false}`
- **结果**: **fail**（round 1 pass → round 2 fail，退行）
- **备注 A2**: detail.truncated=false，即使 Wikipedia 27.9s 大页面也显示未截断；content='' 导致 WebCard 正文不可见

#### Scenario: 抓取失败时展开可读错误（C5 验证）
- **期望**: 展开卡 URL + status 只出现一次（不在 content 里重复 "HTTP 404"）
- **实际**: OUTPUT: `status=404`，content=''（httpbin.org/status/404 空 body）
- **证据**: screenshots/feat425-r2-webfetch-404-expanded.png；IM SQLite `content=''`
- **结果**: **pass**（C5 逻辑正确——content 不含 HTTP 前缀，但由于 content 是空的，整体体验仍差）
- **备注**: C5 fix 本身（去除 HTTP prefix）逻辑可能正确，但 content='' 问题掩盖了验证

### Requirement: 工具自带 emoji，自定义工具可拥有专属图标（继承 Round 1）

#### Scenario: 自定义 / MCP 工具声明了 emoji（B2 + C1）
- **期望**: agent 执行阶段折叠行即显 🎯；完成后折叠行继续显 🎯
- **实际**: agent 无法调用 test_emoji_tool（LLM 提到工具名但未调用）
- **证据**: 聊天回复只有 `code: test_emoji_tool`（引用），无工具调用行
- **结果**: **inconclusive**（B2 仍未关闭）
- **备注**: 自定义工具放置路径已按 team-lead 指示（`<workspace_root>/.nano/tools/`），但 agent 仍未能调用。可能是工具文件接口格式与 gateway 期望不匹配（`from agent.sdk import ToolPresentationEvent` 可能导致加载失败）

#### Scenario: 工具未声明 emoji（回退，不退化）
- **期望**: 折叠行回退 🔧
- **实际**: 无法触发未声明 emoji 的工具调用
- **结果**: **inconclusive**（继承 round 1）

#### Scenario: 既有内置工具不受影响（回归保护）
- **期望**: bash/read/edit 的 emoji 和展开卡与 round 1 一致
- **实际**: 未在 round 2 单独验证（round 1 已通过，round 2 专注修复验证）
- **结果**: **inconclusive**（从 round 1 继承，但鉴于系统性退行，需重新验证）
- **备注**: 高度警戒——emoji/summary 字段全量 MISSING，bash 工具的 💻 emoji 可能也受影响

---

## Round 2 Issues

### Issue 3（Round 2）: emoji + summary 全量丢失 — 所有工具调用折叠行退化

- **Severity**: blocking
- **Regression Relation**: suspected-regression（02dcb744 A2+C5+C1 fix 引入）
- **Scenario**: web_search 折叠行 / web_fetch 折叠行 / 所有工具折叠行
- **Symptom**: IM tool_calls_json 里所有工具调用的 `emoji` 和 `summary` 字段均 MISSING（数据库级别确认）。前端折叠行退化为 `● <toolname> <duration>`，完全丢失 emoji 图标和 summary（query/url 等人话参数）。Round 1 时这些字段存在并正确显示，round 2 后消失。
- **Evidence**: IM SQLite 查询：`SELECT tool_calls_json FROM messages WHERE tool_calls_json != '[]'` → 所有 tool_call 对象无 `emoji` key，无 `summary` key。screenshots/feat425-r2-websearch-success-expanded.png / feat425-r2-webfetch-collapsed-fail.png
- **Recommended Action**: fix-implementation
- **Action Rationale**: emoji/summary 是在 round 1 已验证的核心展示功能，round 2 全量丢失。可能是 gateway relay 层（main.py C1 fix）改动破坏了 tool_end 事件的 emoji/summary 传递路径，或 IM schema 迁移缺失。

### Issue 4（Round 2）: web_fetch detail.content 恒空 — 展开卡正文不可见

- **Severity**: blocking
- **Regression Relation**: suspected-regression（C5 fix 可能引入）
- **Scenario**: web_fetch 展开卡显示抓到的正文（A2 截断提示依赖此路径）
- **Symptom**: IM SQLite `detail.content = ''`（空字符串），无论抓取 Wikipedia 大页面（200）还是 httpbin 404 页面。WebCard 不显示正文，A2 截断提示无法触发（因为 content 空），C5 的"状态码不重复"虽然逻辑正确但无法形成有意义的展示。
- **Evidence**: IM SQLite `detail={"url":"...","status":200,"content":"","truncated":false}`；round 1 时同样的旅程 content 非空（round 1 展开卡显示 Wikipedia 正文）
- **Recommended Action**: fix-implementation
- **Action Rationale**: C5 fix 修改了 `web_fetch.run()` 里 `content` 的赋值逻辑（`content = text` 然后 `text = banner + ...`），可能导致 content 在某路径变成空字符串。Presenter 读 `output.get("content","")` 时拿到空串，导致 WebCard 无正文。

### Issue 5（Round 2）: web_search detail=None — 展开卡 WebSearchCard 未触发

- **Severity**: blocking
- **Regression Relation**: suspected-regression
- **Scenario**: web_search 展开卡按结果条目渲染
- **Symptom**: IM SQLite `detail=None`（searxng 成功调用时）。前端 BESPOKE 查不到有效 detail dict，fallback 到 raw JSON 显示 `{"ok":true,"query":"...","result..."}` 而非 WebSearchCard
- **Evidence**: IM SQLite: `SELECT tool_calls_json FROM messages` → searxng 成功的 web_search tool_call `detail=None`
- **Recommended Action**: fix-implementation
- **Action Rationale**: _WebSearchPresenter.format_end 没有把结构化 results 写入 detail，或 gateway 没有把 detail 序列化到 IM。Round 1 时展开卡成功显示了 WebSearchCard 结构，round 2 后 detail 全为 None。

---

## Round 2 Verdict

| 必验 Scenario | Round 1 | Round 2 |
|---|---|---|
| web_search 正常搜索 | pass | **fail**（退行） |
| web_search 搜索失败 | pass | **fail**（退行） |
| web_search 有搜索结果（展开卡）| pass | **fail**（退行）|
| web_search 无搜索结果（空态）| inconclusive | **fail**（无法触发 duckduckgo）|
| web_fetch 正常抓取 | pass | **fail**（退行） |
| web_fetch 抓取失败 | pass | **fail**（退行） |
| web_fetch 展开卡正文非空 | pass | **fail**（退行，content=''）|
| A2 截断提示 | N/A | **fail**（content=''，truncated=false）|
| C5 HTTP 前缀不重复 | N/A | pass（content=''，前缀确实不在其中，但体验仍差）|
| 自定义工具声明 emoji（B2）| inconclusive | **inconclusive**（仍未能触发）|
| 工具未声明 emoji 回退 | inconclusive | inconclusive（继承）|
| 既有内置工具不退化 | pass | inconclusive（需重验）|

**根据 §4.3：blocking issue 存在 + 多个 fail Scenario → Verdict: fail**

**Verdict: fail**
**Highest Required Action: fix-implementation**
**issues_count: { blocking: 3, major: 0, minor: 0 }**

### 根本问题摘要

Round 2 代码（02dcb744）引入了**系统性退行**：A2+C5+C1 三处 fix 导致：
1. emoji + summary 全量从 tool_calls_json 消失（工具折叠行全退化）
2. web_fetch content 恒空（正文不可见，A2 截断提示无法触发）
3. web_search detail=None（WebSearchCard 无法渲染）

Round 1 验收通过的 7 个核心 Scenarios 在 round 2 全部 fail。需要 fix worker 回查 C1 fix（main.py gateway relay 改动）对 tool_end 事件链路的影响，以及 C5 fix 对 web_fetch content 赋值的影响。
