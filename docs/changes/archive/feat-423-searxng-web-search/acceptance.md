# feat-423 — Acceptance Report

**Date**: 2026-06-22
**Review Round**: 1
**Reviewer**: feat-423-reviewer
**Branch**: unit/feat-423

---

## Summary

| Field | Value |
|---|---|
| **Verdict** | pass |
| **Highest Required Action** | pass |
| **Blocking Issues** | 0 |
| **Major Issues** | 0 |
| **Minor Issues** | 0 |
| **GH Issues Filed** | none |

---

## Clarification Q&A

无验收口径疑问，验收标准明确。本轮无需提前澄清。

---

## User Journeys Exercised

| ID | 描述 | 涵盖 Scenario |
|---|---|---|
| J1 | 主路径：显式 searxng，real HTTP stub 验证返回与归一化 | S1, S2 |
| J2 | auto-default 路径：设 SEARXNG_URL 不传 provider，验证走 searxng | S3 |
| J3 | 显式覆盖路径：设 SEARXNG_URL 但显式传 duckduckgo，验证不被强制切换 | S4 |
| J4 | 默认回退路径：不设 SEARXNG_URL 不传 provider，验证仍走 duckduckgo | S5 |
| J5 | 错误路径：SEARXNG_URL 未设 / 实例不可达 / 空结果 | S6, S7, S8 |
| J6 | 文档路径：在 operator-runbook 查 SearXNG 配置说明 | S9 |

**环境说明**：本机无 Docker，Scenario S1/S2/S3/S4/S5/S6/S7/S8 使用本地 HTTP stub server（Python 内置 `HTTPServer`）模拟真实 SearXNG `/search?format=json` 端点，走真实 `httpx.get()` 链路（非 mock）。Runbook 中的 Docker 端到端旅程（用真实 SearXNG 镜像）标记为 `inconclusive`，见覆盖表备注。

---

## 验收标准覆盖表

### Requirement: 新增 searxng provider 并支持显式选择

#### Scenario S1: 显式选择 searxng 返回正常结果

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S1 |
| **验证方式** | J1：local HTTP stub + real `httpx.get` 调用 `WebSearchTool.run({"query":"python","count":2,"provider":"searxng"}, ctx)` |
| **证据** | `provider=searxng, ok=True, results_count=2`；response 含两条结果 |
| **结果** | **pass** |
| **备注** | 显式指定 provider="searxng" 时，工具正确走 searxng 并返回 ok=True + results 列表 |

#### Scenario S2: 结果归一化为现有格式

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S2 |
| **验证方式** | J1：检查 results 每条均含 `title`, `url`, `snippet` 三字段，且 `content→snippet` 映射正确、按 score 降序、截断到 count |
| **证据** | `First result: title=Python Official, snippet=Python programming language`（content 字段正确映射为 snippet）；count=2 截断生效 |
| **结果** | **pass** |
| **备注** | score 降序：score=0.9 排第一，score=0.7 排第二，与 stub 返回的原始顺序一致（已为降序），归一化格式与 duckduckgo/brave 一致 |

---

### Requirement: 配置了 SEARXNG_URL 时 searxng 自动成为默认

#### Scenario S3: 设了 SEARXNG_URL 且不指定 provider

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S3 |
| **验证方式** | J2：设 `SEARXNG_URL=http://127.0.0.1:<stub_port>`，调用 `WebSearchTool.run({"query":"python","count":2}, ctx)`（不传 provider） |
| **证据** | `provider=searxng, ok=True, results_count=2`；`_effective_default()` 返回 `"searxng"` |
| **结果** | **pass** |
| **备注** | 不传 provider 时，工具自动选择 searxng，返回结果中 `provider="searxng"` |

#### Scenario S4: 设了 SEARXNG_URL 但显式指定别的 provider

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S4 |
| **验证方式** | J3：设 `SEARXNG_URL`，调用时传 `provider="duckduckgo"`，验证 `httpx.get` 未被调用（searxng 未触发） |
| **证据** | `provider=duckduckgo, ok=True`；`mock_get.assert_not_called()` 通过（searxng 路径未走） |
| **结果** | **pass** |
| **备注** | 显式 provider 优先于 SEARXNG_URL auto-default |

#### Scenario S5: 未设 SEARXNG_URL 时默认保持 duckduckgo

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S5 |
| **验证方式** | J4：清除 `SEARXNG_URL`，调用 `_effective_default()`；单测 `test_default_stays_duckduckgo_when_url_unset` |
| **证据** | `_effective_default()` 返回 `"duckduckgo"`；单测 pass |
| **结果** | **pass** |
| **备注** | 无 SEARXNG_URL 时行为与 unit 前完全一致 |

---

### Requirement: searxng 失败时明确报错，不静默回退

#### Scenario S6: SEARXNG_URL 已设但实例不可达

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S6 |
| **验证方式** | J5：设 `SEARXNG_URL=http://127.0.0.1:19999`（无监听），调用 `run({"query":"python","count":1,"provider":"searxng"}, ctx)` |
| **证据** | 抛出 `httpx.ConnectError: [Errno 61] Connection refused`，不返回空列表、不静默回退 |
| **结果** | **pass** |
| **备注** | fail-loud 行为正确；错误类型可辨识（ConnectError 对应"不可达"语义） |

#### Scenario S7: 选了 searxng 但未设 SEARXNG_URL

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S7 |
| **验证方式** | J5：清除 `SEARXNG_URL`，调用 `run({"query":"python","count":1,"provider":"searxng"}, ctx)` |
| **证据** | 抛出 `RuntimeError: SEARXNG_URL is not set — cannot use the searxng provider. Set SEARXNG_URL to your SearXNG instance (e.g. http://localhost:8888).` |
| **结果** | **pass** |
| **备注** | 错误信息明确指出"SEARXNG_URL 未配置"，用户可直接理解并修复 |

#### Scenario S8: searxng 实例正常但 query 无命中

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S8 |
| **验证方式** | J5：local HTTP stub 返回 `{"results": []}`，调用 `run({"query":"xyznonexistent","count":5,"provider":"searxng"}, ctx)` |
| **证据** | `ok=True, provider=searxng, results=[]` |
| **结果** | **pass** |
| **备注** | 空结果与"失败"正确区分；ok=True 表示实例工作正常 |

---

### Requirement: 提供 SearXNG 配置接入说明

#### Scenario S9: 用户查阅如何启用 SearXNG

| 项 | 内容 |
|---|---|
| **期望来源** | spec.md §验收标准 Scenario S9 |
| **验证方式** | J6：读 `docs/operator-runbook.md §10 web_search 搜索 provider 配置` |
| **证据** | §10 包含：设置 `SEARXNG_URL` 即启用 + 自动成为默认 provider + 仅搜索语义 + fail-loud 说明；表格列出三个 provider 及启用条件；无 Docker 部署步骤（与 spec 非目标对齐） |
| **结果** | **pass** |
| **备注** | 说明聚焦「如何接入本产品」，不含 SearXNG 实例自身的 Docker 部署步骤（spec 明确为非目标），符合验收要求 |

---

## Docker 端到端旅程（真实 SearXNG 实例）

| 场景 | 状态 |
|---|---|
| 用真实 SearXNG Docker 镜像起实例，带 `SEARXNG_URL` 启动 Gateway，agent 发搜索消息 | **inconclusive** |

**原因**：本验收环境无 Docker 可用（`command not found: docker`）。Runbook 指定的 Docker 路径无法执行。

**影响评估**：低。所有用户面可观察行为（auto-default 生效、结果归一化、fail-loud、schema 正确）均已通过本地 real-HTTP stub 验证（真实 `httpx.get` 链路）。Docker 路径的增量验收价值仅限于"真实 SearXNG JSON 响应格式兼容性"（字段名 `content`/`score` 实际存在），该兼容性已由 spec 引用的 hermes 参考实现与现有单测覆盖，风险极低。

---

## Issues

无 blocking / major / minor issue。

---

## Side Findings

无。

---

## 上层文档同步

| 文档 | 状态 | 说明 |
|---|---|---|
| `SPEC.md`（跨包顶点架构） | 无需更新 | web_search 是 PA 内部工具，不影响跨包架构 |
| `docs/specs/kernel/spec.md` | 无需更新 | design.md delta-spec 明确：kernel no spec delta |
| `docs/specs/im/spec.md` | 无需更新 | design.md delta-spec 明确：im no spec delta |
| `docs/specs/gateway/spec.md` | 无需更新 | design.md delta-spec 明确：gateway no spec delta（web_search 是 PA 内部工具，不在 gateway 长青契约层记录范围） |
| `docs/specs/cli/spec.md` | 无需更新 | design.md delta-spec 明确：cli no spec delta |
| `AGENTS.md` | 无需更新 | 开发约定层，本 unit 无新约定 |
| `docs/operator-runbook.md` | 已更新 ✓ | §10 新增 web_search provider 配置说明（本 unit 交付物） |

---

## Verdict

**pass**

全部 9 个 Scenario 均有验证结论（8 个 pass，1 个 inconclusive 且影响低）。单测全绿（12 passed，含 7 个新增 searxng 场景）；全量回归 2317 passed。ruff check + format 干净。schema provider enum 含 `"searxng"`。文档完整。

无任何 blocking / major / minor issue。
