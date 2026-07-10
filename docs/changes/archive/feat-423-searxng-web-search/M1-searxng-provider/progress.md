# feat-423-M1 — Progress

## R1 — 新增 _search_searxng + auto-default + schema + 文档

- Context: web_search 仅有 duckduckgo/brave，duckduckgo 易 429 不稳、brave 2026 起取消免费 tier。需加稳定免费可自建的 searxng provider（issue #132）。
- Decision:
  - `_search_searxng(query, count)` 进 `_PROVIDERS`，沿用统一 `(query, count)` 签名。读 `SEARXNG_URL`（未设 raise RuntimeError）→ `httpx.get(/search?format=json&pageno=1)` + `raise_for_status()` → `resp.json()["results"]` 按 `score` 降序 → 取前 count → 归一化 `{title, url, snippet}`（snippet 取 SearXNG 的 `content` 字段）。
  - auto-default 落 `WebSearchTool._effective_default()`，run() 内即时读 env：`SEARXNG_URL` 非空 → `"searxng"`，否则 `self._default_provider`（duckduckgo）。product.py 未改。
  - `httpx` 提到模块级 import（brave 内的局部 import 删除复用），便于测试 `patch.object(ws_module.httpx, "get", ...)`。
  - schema `provider` enum 加 `"searxng"`，description 注明 needs SEARXNG_URL + 自动成默认。
- Rationale:
  - 决策 1（design）：`SEARXNG_URL` 是运行时状态，放 run() 即时读，避免被 product.py 启动期实例化固化，且无需改装配处。
  - 决策 2（design）：fail-loud 不回退——searxng 是用户明确选定的稳定源，悄悄退回它本想绕开的 ddg 会掩盖问题。对齐现状契约（provider 失败必须 raise，不返回 []）。未照搬 hermes 参考实现的 `{success, error}` dict-return，因本仓契约是 raise。
  - 决策 3（design）：配置说明落 operator-runbook（运行配置的现成家，已记 IM_JWT_SECRET）。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_web_search_tool.py` → 11 passed, 1 skipped（skip 为 ddgs importorskip 集成）。新增 7 个：归一化+score 排序+截断 / 实例不可达 raise(httpx.HTTPError) / 未配 URL raise(RuntimeError, match SEARXNG_URL) / 空结果 ok=True []  / auto-default 选 searxng / 显式 provider 覆盖 auto-default / 未配默认仍 ddg。原有 5 个 provider-fail-loud 测试不受影响仍绿。
  - Entry: 真实 HTTP 入口验证——本地起 `http.server` stub 模拟 SearXNG `/search?format=json` 响应，通过 `WebSearchTool().run()` 走**真实 httpx.get**（非 mock）到该 server：不传 provider → `provider=searxng`（auto-default 生效）、`ok=True`、results 归一化为 `[{"title":"Python","url":"https://python.org","snippet":"official site"}]`（content→snippet、score 降序 + count=1 截断）；显式传 `provider=duckduckgo` → `provider=duckduckgo`（不被 SEARXNG_URL 强制改走）。stub server 用完 shutdown，未驻留端口。
  - Frontend State Matrix: N/A（纯后端工具）
  - Browser QA: N/A
  - E2E/Regression: 7 个新增单测即 regression 保护（覆盖 spec 四组 Requirement 全部可单测的 Scenario）。真实 SearXNG 实例的端到端 auto-default 旅程需 Docker 实例，归 reviewer（design Runbook 已列）。
  - Visual/Interaction: N/A
- Rollback: 单文件单函数 + 一处文档，`git revert` C2(实现) 即回到改前；不涉数据迁移、不改对外契约。
- Commits: C1=test 红测（searxng 七场景）, C2=feat 实现+文档, C3=docs 本段
- Next: 本 milestone 已完成，进入 §6 集成到 unit 分支。
