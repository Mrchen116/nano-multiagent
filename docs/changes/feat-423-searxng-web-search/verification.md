# Verification Report: feat-423

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 |
| Correctness | 9/9 scenarios covered |
| Coherence | Followed |

No critical issues. 1 suggestion to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks: 4/4 complete

`docs/changes/feat-423-searxng-web-search/M1-searxng-provider/tasks.md` 所有退出标准已勾 `[x]`：

- `pytest tests/unit/personal_assistant/test_web_search_tool.py` 全绿 — 实际运行 12 passed（ddgs 已安装，integration 测试由 skip 变 pass；tasks.md 记录 11 passed 1 skipped 是 worker 运行时 ddgs 未安装，不影响正确性）
- `ruff check` + `ruff format` — 验证：`src/personal_assistant/tools/web_search.py` 全绿
- schema `provider` enum 含 `searxng`，description 提及它
- `docs/operator-runbook.md` 第 10 节已新增 provider 配置说明

### Spec requirement 覆盖

spec 四组 Requirement 全部有实现：

| Requirement | 实现位置 |
|---|---|
| 新增 searxng provider 并支持显式选择 | `web_search.py:83-138`（`_search_searxng` + 注册进 `_PROVIDERS`） |
| 配置了 SEARXNG_URL 时 searxng 自动成为默认 | `web_search.py:181-191`（`_effective_default()`） |
| searxng 失败时明确报错，不静默回退 | `web_search.py:108-112, 120`（RuntimeError + raise_for_status） |
| 提供 SearXNG 配置接入说明 | `docs/operator-runbook.md:309-333` |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 显式选择 searxng 返回正常结果 | `web_search.py:83-131`（`_search_searxng` + `_PROVIDERS["searxng"]`） | `test_searxng_normalizes_and_sorts_by_score`（line 165） | covered |
| 结果归一化为 `{title, url, snippet}`，按 score 排序截断 | `web_search.py:122-131`（score 降序、`content→snippet`、`[:count]`） | `test_searxng_normalizes_and_sorts_by_score`（line 165） | covered |
| 设了 SEARXNG_URL 且不指定 provider → 走 searxng | `web_search.py:181-191`（`_effective_default` 即时读 env）+ `web_search.py:211` | `test_auto_default_searxng_when_url_set`（line 233） | covered |
| 设了 SEARXNG_URL 但显式指定别的 provider → 尊重显式选择 | `web_search.py:211`（`args.get("provider", self._effective_default())`） | `test_explicit_provider_overrides_auto_default`（line 245） | covered |
| 未设 SEARXNG_URL 时默认保持 duckduckgo | `web_search.py:189-191`（`_effective_default` 返回 `self._default_provider`） | `test_default_stays_duckduckgo_when_url_unset`（line 261） | covered |
| SEARXNG_URL 已设但实例不可达 → 报错，不回退 | `web_search.py:114-120`（`httpx.get` + `raise_for_status`，不捕获） | `test_searxng_unreachable_raises`（line 193） | covered |
| 选了 searxng 但未设 SEARXNG_URL → 报错，指明 URL 未配置 | `web_search.py:107-112`（`RuntimeError("SEARXNG_URL is not set…")`） | `test_searxng_unset_url_raises`（line 210） | covered |
| searxng 正常但 query 无命中 → `ok=True, results=[]` | `web_search.py:122`（`resp.json().get("results", [])` → 空时截断也空） | `test_searxng_empty_results_ok`（line 220） | covered |
| 用户查阅如何启用 SearXNG → 可在文档位置找到配置说明 | `docs/operator-runbook.md:309-333` | 无自动测试（文档，符合 TESTING_GUIDE 不测文档内容原则） | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：auto-default 逻辑放 `run()`（而非构造函数），即时读 env | 是 | `web_search.py:181-191`（`_effective_default()` 每次 `run()` 调用时读 `os.environ.get`），`product.py:406`（`WebSearchTool()` 无参实例化，未改） |
| 决策 2：`_search_searxng` 直接进 `_PROVIDERS`，`(query, count)` 签名，fail-loud 不回退 | 是 | `web_search.py:83-131`（无捕获 + `raise_for_status()`，不回退 ddg）；`web_search.py:134-138`（注册 `_PROVIDERS["searxng"]`） |
| 决策 3：配置说明落 `docs/operator-runbook.md` 新增小节 | 是 | `docs/operator-runbook.md:309-333`（第 10 节，聚焦接入说明，不含 Docker 部署步骤） |
| 架构边界：`personal_assistant` 只 import `agent.sdk`，不 import 内部 | 是 | `web_search.py:13`（`from agent.sdk import ToolContext`）；contract 测试 126/126 通过 |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

- **`WebSearchTool` class docstring 未提及 searxng**：`web_search.py:142`，docstring 仍写 "Search the web using DuckDuckGo (free) or Brave (API key)"，忽略了新增的 searxng。三个 provider 都在 `description` 字段里描述（第 149-153 行），保持一致性建议 class docstring 同步更新为类似 "Search the web using DuckDuckGo, Brave, or a self-hosted SearXNG instance."。**不影响功能，提 PR 后修也可**。

---

All checks passed. Ready for PR.
