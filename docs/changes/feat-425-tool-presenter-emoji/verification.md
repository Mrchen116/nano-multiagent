# Verification Report: feat-425

> Round 1 · 2026-06-22 · branch `unit/feat-425` · HEAD `f4cdd7f2`

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 tasks DONE；10/10 spec requirement 有实现 |
| Correctness | 10/10 覆盖（含 3 个关键 scenario 的测试正向验证） |
| Coherence | Followed — 5 条 design 决策全部遵守；架构边界自洽 |

All checks passed. Ready for PR.

---

## Completeness

### Task 完成情况

`docs/changes/feat-425-tool-presenter-emoji/M1-tool-presenter-emoji/tasks.md` 中 3 个 Roadpoint：

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测 | DONE (`b76d7e21`) |
| R2 | C2 实现 | DONE (`5749f698`) |
| R3 | C3 文档 delta-spec + design changelog | DONE (`85e15069`) |

**Tasks: 3/3 complete。**

### Spec 覆盖情况（10 条 requirement）

全部 10 条 spec requirement 有实现：

1. web_search 折叠行 `🔍 <query>`（正常搜索） — `web_search.py:51-52`
2. web_search 搜索失败态折叠仍显查询词 — `web_search.py:70-77`（emoji=🔍，summary=query）
3. web_search 展开卡结果列表 — `tool-detail-renderers.tsx:258`（`WebSearchCard`）
4. web_search 无结果空态 — `tool-detail-renderers.tsx:264`（空态文案）
5. web_fetch 折叠行 `🌐 <url>`（正常抓取） — `web_fetch.py:200-204`（`format_start` emoji=🌐）
6. web_fetch 抓取失败折叠仍显 URL — `web_fetch.py:214-228`（双失败通道均判）
7. web_fetch 展开卡正文非空 — `web_fetch.py:480-488`（`run()` 返回 `content`）+ `tool-detail-renderers.tsx:235`（WebCard 读 content）
8. 工具自带 emoji 自定义工具显专属图标 — `tool-presentation.ts:43-45`（`toolEmojiFor`：event-first）
9. 工具未声明 emoji 回退 🔧（无退化） — `tool-presentation.ts:45`（`toolEmoji(call.name)` 兜底）
10. 既有内置工具图标与渲染零变更 — 9 个 presenter 下沉到各 builtin 文件，行为原样搬迁（golden 测试验证）

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| web_search `🔍 <query>` 折叠行（正常搜索） | `web_search.py:38-53`（`_WebSearchPresenter.format_start`） | `test_web_search_presenter.py:38`（`test_start_shows_query_with_search_emoji`） | covered |
| web_search 搜索失败态（服务不可用/provider 报错） | `web_search.py:69-77`（双失败通道；emoji=🔍，summary=query，detail.error） | `test_web_search_presenter.py:91`（`test_end_failed_unknown_provider`）`test_web_search_presenter.py:108`（`test_end_failed_searxng_raise`） | covered |
| web_search 展开卡结果列表 | `tool-detail-renderers.tsx:258`（`WebSearchCard`，逐条标题/URL/摘要） | `tool-calls-panel.test.tsx:293`（`renders web_search as a card listing result entries`） | covered |
| web_search 无结果空态 | `tool-detail-renderers.tsx:264`（`rawResults.length === 0` → 空态文案） | `tool-calls-panel.test.tsx:319`（`renders web_search empty state`） | covered |
| web_search 展开卡展示 provider error | `web_search.py:69-77`（`detail.error`） → 前端 `BESPOKE.web_search` → `ErrorCard` | `tool-calls-panel.test.tsx:333`（`routes a web_search failure to the error card`） | covered |
| web_fetch `🌐 <url>` 折叠行（正常抓取） | `web_fetch.py:199-204`（`format_start`，emoji=🌐，summary=url） | `test_presentation.py:238`（`test_start_shows_url_with_globe_emoji`） | covered |
| web_fetch 抓取失败折叠仍显 URL（双失败通道） | `web_fetch.py:214-228`（out-of-band `result.error` + in-band `output["ok"] is False`） | `test_presentation.py:270`（`test_end_failed_out_of_band`），`test_presentation.py:283`（`test_end_failed_in_band_ok_false`） | covered |
| web_fetch 展开卡正文非空（修复恒空 bug） | `web_fetch.py:480-488`（`run()` 返回 `content` 剥 banner）；`test_web_fetch_run.py:32`；`tool-detail-renderers.tsx:235`（`WebCard` 读 `content`） | `test_web_fetch_run.py:32`（`test_run_returns_content_without_banner`），`tool-calls-panel.test.tsx:274`（`renders web_fetch as a card with url + status + non-empty content`） | covered |
| 工具自带 emoji，自定义工具显专属图标 | `tool-presentation.ts:43-45`（`toolEmojiFor(call)`: `call.emoji || toolEmoji(call.name)`） | `tool-calls-panel.test.tsx:88`（`prefers the tool-carried emoji over the name table`） | covered |
| 工具未声明 emoji 回退 🔧（不退化） | `tool-presentation.ts:45`（名表兜底）；`ToolPresentationEvent.emoji` 默认 `""` | `tool-calls-panel.test.tsx:77`（`falls back to a generic emoji for unknown tools`），`test.tsx:100`（历史行降级） | covered |
| 既有内置工具图标与渲染零变更（回归保护） | 9 个 presenter 下沉（`builtins/*.py`），行为搬迁不改；golden 断言 `(visible,label,summary,emoji,detail)` 五元组 | `test_presentation_golden.py`（全 9 工具 start/end golden）；`test_presentation.py`（各 status 路径） | covered |

---

## Coherence

### design 关键决策遵守检查

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: emoji 进 `ToolPresentationEvent`，复用 feat-409 透传链 | 是 | `core/tools/presentation.py:20`（`emoji: str = ""`）；`realtime_stream.py:199-201`（`_presentation_dict` 序列化 emoji）；gateway `main.py:3586-3606`（relay 转发）；前端 `tool-presentation.ts:43`（`toolEmojiFor`） |
| 决策 2: emoji 落库（IM ToolCall + gateway relay + 前端） | 是 | `domain/models.py:209`（`emoji: str | None = None`）；`repositories.py:2810-2882`（persist/decode）；`event_types.py:65`（WS payload）；`messages.py:94`（REST ToolCallPayload）；`chat-types.ts:83`（`emoji?`） |
| 决策 3: 全部 presenter 类下沉到各 builtins 文件 | 是 | 9 个 `_XxxPresenter` 各在 `builtins/{read,write,edit,bash,web_fetch,agent,memory,skill_manage,task_stop}.py`；`presentation.py` 缩到 251 行，只留 Protocol/Event/resolver/default/helper |
| 决策 4: web_fetch 字段修复（`content`/`final_url` + 失败判 `ok is False`） | 是 | `web_fetch.py:480-488`（run() 返回 content/final_url）；`web_fetch.py:214-228`（presenter 双失败判断）；折叠 summary=url、emoji=🌐 |
| 决策 5: web_search presenter + `WebSearchCard`（`web_search.py` 自持） | 是 | `web_search.py:33-100`（`_WebSearchPresenter`，import 自 `agent.sdk`）；`tool-detail-renderers.tsx:258`（`WebSearchCard`）；BESPOKE 注册 `web_search:470` |

### 架构自洽性（§4.3）

- **依赖方向**：`web_search.py` import 来源 `from agent.sdk import ToolContext, ToolPresentationEvent`（`web_search.py:13`），contract test 通过（126 passed），无边界违反。
- **平行机制**：emoji 全程复用 feat-409 已建立的 detail 透传链，没有另造平行管道；`_SNIPPET_CAP` 是 product 层本地截断（`_enforce_cap` 属于 platform 内部，product 包无法调用，设计合理）。
- **跨机边界**：无跨进程边界假设；all changes stay within gateway relay → IM store → frontend chain。

### 代码模式一致性（§4.2 表层）

- 注释风格（Google docstring + "为什么/约束"内联注释）：遵循 COMMENTING_GUIDE.md 约定，新增的类/方法均有 docstring（`_WebSearchPresenter`、`_WebFetchPresenter`、`_WebFetchTool.run` 均有完整说明）。
- commit message 格式：`test(feat-425/M1): C1 红测…` / `feat(feat-425/M1): C2 实现…` / `docs(feat-425/M1): C3…` 完全匹配 `AGENTS.md` 规范。
- TODO/FIXME 格式：无遗留 TODO/FIXME 引入。
- message-pane 越界修复（`querySelectorAll<HTMLTableCellElement>` 泛型实参 + 去 `as const`）：属基线 TS 类型修复，非本 unit 引入；已在 design.md Changelog 和 progress.md 中说明，供 lead 知晓。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

无。

---

All checks passed. Ready for PR.
