# feat-423-M1: searxng-provider — Tasks

> 对齐: ../design.md v2

## 目标

`web_search` 工具新增 `searxng` provider：`SEARXNG_URL` 已设时自动成默认、显式 provider 仍优先、fail-loud 不回退；结果归一化为 `{title, url, snippet}`。operator-runbook 新增「web_search 搜索 provider 配置」小节。

## 退出标准

- [x] `pytest tests/unit/personal_assistant/test_web_search_tool.py` 全绿（11 passed, 1 skipped），新增覆盖：searxng 正常返回 / 实例不可达 raise / 未配 SEARXNG_URL raise / 空结果返回 [] / auto-default 推导 / 显式 provider 优先 / 未配默认仍 ddg
- [x] `ruff check` + `ruff format` 干净
- [x] schema `provider` enum 含 `searxng`，description 提及它
- [x] operator-runbook 新增 provider 配置小节（第 10 节：SEARXNG_URL 启用即默认、仅搜索语义、补 BRAVE_API_KEY）

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - 显式 `provider: "searxng"` + mock httpx 正常返回 → results 归一化 + 按 score 降序截断
  - `SEARXNG_URL` 已设、不传 provider → 走 searxng（auto-default）
  - `SEARXNG_URL` 已设、显式传 duckduckgo → 走 duckduckgo（显式优先）
  - `SEARXNG_URL` 未设、不传 provider → 仍走 duckduckgo（默认不变）
  - searxng 实例不可达（httpx raise）→ tool raise，不回退、不返回 []
  - 显式 searxng 但 `SEARXNG_URL` 未设 → tool raise RuntimeError
  - searxng 返回空 results → ok=True, results=[]
- 已有测试在：`tests/unit/personal_assistant/test_web_search_tool.py`（扩展），沿用现有 patch.dict(_PROVIDERS) + mock httpx 风格
- 落层/目录/marker：tests/unit/，marker：无
- 可选依赖 importorskip：无（httpx 是现有依赖，searxng 测试全 mock httpx.get）
- 本 milestone 产生的一次性验收证据：无（纯单测路径已覆盖；真实 SearXNG 实例 auto-default 端到端归 reviewer）

前端：N/A（纯后端工具）

## Roadpoints

### R1 — 新增 _search_searxng + auto-default + schema + 文档 — DONE

- 步骤:
  - C1: 扩展 test_web_search_tool.py，加 searxng 七个场景测试（Red）
  - C2: 实现 `_search_searxng`、注册进 `_PROVIDERS`、`_effective_default()`、run() 用它、schema enum/description 更新（Green）
  - C2: operator-runbook 新增 provider 配置小节
  - C3: 补 tasks/progress
- 验证: pytest 该文件全绿 + ruff check/format 干净
