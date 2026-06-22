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
