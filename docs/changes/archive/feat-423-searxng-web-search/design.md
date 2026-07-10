# feat-423: web_search 支持 SearXNG provider — 技术方案

> 对齐: spec.md v2（含「配置接入说明」修订）

> Unit branch: `unit/feat-423` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/personal_assistant/tools/web_search.py` —— 唯一实现文件。现有结构：两个 provider 纯函数 `_search_duckduckgo` / `_search_brave`（签名统一 `(query, count) -> list[{title,url,snippet}]`）+ 模块级 `_PROVIDERS: dict[str, fn]` 注册表 + `WebSearchTool`（`name="web_search"`，`input_schema` 含 `provider` enum，`run()` 按 `provider` 查表分发）。本 unit 在此加 `_search_searxng` 并注册。
- `src/personal_assistant/product.py:406` —— `WebSearchTool()` **无参实例化**（构造默认 `default_provider="duckduckgo"`）。本 unit **不改它**——auto-default 逻辑落在工具内部。
- `docs/operator-runbook.md` —— operator 配置手册，已记 `IM_JWT_SECRET` 等运行时 env。配置接入说明落这里新增一小节。

### 既有约束

- provider 分发签名统一为 `(query, count)`；新 provider 照此进 `_PROVIDERS` 即可，**不改分发契约**。
- 现状契约（代码 + `tests/unit/personal_assistant/test_web_search_tool.py`）= **provider 失败必须 raise，不返回 `[]`**（provider 失败 ≠ 零结果）。searxng 沿用。
- `personal_assistant` 只 import `agent.sdk`（本 unit 不触及该边界，纯改产品自有工具）。

### 可复用能力

- **provider 模式**（一个纯函数 + 注册进 `_PROVIDERS`）：直接复用，searxng 照此办，不另造抽象类。
- `httpx`：现有 `_search_brave` 已用 `import httpx` + `httpx.get` + `raise_for_status`，searxng 沿用同一依赖与错误传播范式。

### 相关历史

- **refactor-395**（swallowed exception code smell）：把 web_search 两处裸 `except` 拎出来改了。注意其 design.md 当时写的方案是「捕获后 log + 返回空列表」，但**实际 shipped 的代码 + 测试走 fail-loud（raise）**——以代码/测试为准。searxng 延续 fail-loud。
- web_search 最早随 feat-340 引入，无独立 spec。`BRAVE_API_KEY` 至今无任何文档记载——本 unit 顺带给 provider env 配置建一个文档落点。

## 架构总览

改动是「往既有 provider 注册表加一项」，结构不变：

```
WebSearchTool.run(args)
  ├─ 解析 provider：
  │    显式传 → 用它
  │    未传   → _effective_default()：SEARXNG_URL 已设 → "searxng"，否则 self._default_provider("duckduckgo")   ← 新增
  └─ _PROVIDERS[provider](query, count)
        ├─ _search_duckduckgo   (现有)
        ├─ _search_brave        (现有)
        └─ _search_searxng      ← 新增：httpx.get(SEARXNG_URL/search?format=json) → 排序截断 → {title,url,snippet}
```

before：默认恒为 duckduckgo；after：配了 `SEARXNG_URL` 时不带 provider 的调用自动走 searxng，显式 provider 仍优先。

## 关键决策

### 决策 1: auto-default 逻辑放 `run()`，不放构造函数

**`run()` 内按 env 即时推导有效默认 provider；构造参数 `default_provider="duckduckgo"` 保留作静态兜底。**

- **理由**: `SEARXNG_URL` 是运行时状态；放构造时读会被实例化时机固化（product.py 在启动时构造一次）。放 `run()` 每次调用即时反映当前 env，且 product.py 无需改。
- **拒绝**: 「product.py 实例化时读 env 传 `default_provider`」——固化、且要改装配处。
- **风险**: 低。仅当「不传 provider」时分支才变；显式 provider 与未配 `SEARXNG_URL` 时行为与之前完全一致（spec 验收标准「未设 SEARXNG_URL 时默认保持 duckduckgo」钉住）。

### 决策 2: searxng 直接进 `_PROVIDERS`，沿用 `(query, count)` 签名 + fail-loud

**`_search_searxng(query, count)`：`SEARXNG_URL` 未设 → `raise RuntimeError`；`httpx.get(.../search?format=json&pageno=1)` + `resp.raise_for_status()`，错误传播不回退。**

- **理由**: 对齐 hermes 参考实现与现状 fail-loud 契约。结果按 SearXNG `score` 降序排序后截断到 `count`，归一化 `content→snippet`。
- **拒绝**: 「失败回退 duckduckgo」（像 brave 那样）——searxng 是用户明确选定的稳定源，悄悄退回它本想绕开的 ddg 会掩盖问题（spec 决策已定）。
- **风险**: SearXNG 实例未启用 JSON 格式时 `resp.json()` 会抛——属 fail-loud 的合理表现，错误信息需可辨识（指向「不可达 / 响应非 JSON」）。

### 决策 3: 配置说明落 `docs/operator-runbook.md` 新增小节

**新增「web_search 搜索 provider 配置」小节：`SEARXNG_URL` 设置即启用、设后自动成默认、仅搜索语义；顺带补一句 `BRAVE_API_KEY`。**

- **理由**: operator-runbook 是 operator 运行时配置的现成家（已记 `IM_JWT_SECRET`）。聚焦「如何接入本产品」，不含 SearXNG 实例自身 Docker 部署（spec 非目标）。
- **拒绝**: 写进 AGENTS.md——那是开发约定，不是 operator 运行配置；README——本仓 README 非 operator 入口。
- **风险**: 无。

## 接口与数据流

新增函数（签名，非实现）：

```python
def _search_searxng(query: str, count: int) -> list[dict[str, str]]:
    # 读 SEARXNG_URL（未设 → raise RuntimeError）
    # httpx.get(f"{base}/search", params={"q": query, "format": "json", "pageno": 1})
    # resp.raise_for_status()
    # results = resp.json().get("results", [])
    # 按 score 降序 → 取前 count → [{"title","url","snippet"}]（snippet 取 content 字段）
```

注册：`_PROVIDERS["searxng"] = _search_searxng`。

工具内新增有效默认推导（私有，run() 调用）：

```python
def _effective_default(self) -> str:
    # os.environ.get("SEARXNG_URL") 非空 → "searxng"，否则 self._default_provider
```

schema 更新：`provider` enum 加 `"searxng"`；`description` 提及 searxng（needs SEARXNG_URL）。

数据流：与现有 provider 完全一致（`run` → 查表 → 调用 → 统一 `{title,url,snippet}` 截断 → `{ok, query, provider, results}`），searxng 只是表里多一项。

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im: no spec delta
- gateway: no spec delta（web_search 是 PA 内部工具，其 provider 选择不在 gateway 长青契约层——该层记 channel/cron/heartbeat/dispatch/binding 等对外行为；kernel 层的 "provider" 指 LLM provider，与此无关）
- cli: no spec delta

## 风险与回退

- **SEARXNG_URL 自动改默认带来的隐式行为切换**：仅影响「不传 provider」路径；显式 provider 与未配 env 时零变化，spec 已用专门 Scenario 钉住，回归测试覆盖。
- **SearXNG 实例未启用 JSON 格式**：`resp.json()` 抛 → fail-loud 暴露；文档小节提示需在 settings 启用 `json` format。
- **回滚**：单文件单函数 + 一处文档，`git revert` 即可；不涉及数据迁移、不改对外契约。

## Runbook for Reviewer

本 unit 改的是 PA 进程内工具与文档，验收需要 SearXNG 实例 + Gateway。

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| SearXNG（验收用，可本地 Docker） | `docker rm -f searxng` | `docker run -d --name searxng -p 8888:8080 -e SEARXNG_BASE_URL=http://localhost:8888/ searxng/searxng:latest`（需在 settings.yml 的 formats 加 `- json` 后重启） | `curl -s "http://localhost:8888/search?q=test&format=json" \| head -c 100` 返回 JSON |
| Gateway（PA） | `PYTHONPATH=src python -m personal_assistant.main stop` | `SEARXNG_URL=http://localhost:8888 PYTHONPATH=src python -m personal_assistant.main`（带 env 才能验 auto-default） | 启动日志无 error；IM 内对 agent 发起含搜索意图的消息能返回结果 |

> 纯单测路径（正常/空/不可达/未配 URL）不需要起 SearXNG，用 `tests/unit/personal_assistant/test_web_search_tool.py` 的 mock 即可；真实实例仅用于端到端 auto-default 旅程。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-423-M1 | searxng-provider | — | A | `src/personal_assistant/tools/web_search.py`、`docs/operator-runbook.md`、`tests/unit/personal_assistant/test_web_search_tool.py` | `[reviewer]` 覆盖 spec 四组 Requirement 全部 Scenario：显式 searxng 正常返回 / 归一化 / auto-default 生效 / 显式 provider 优先 / 未配默认仍 ddg / 实例不可达报错 / 未配 URL 报错 / 空结果 ok=True；配置说明可在 operator-runbook 查到。`[worker]` `pytest tests/unit/personal_assistant/test_web_search_tool.py` 全绿（新增：searxng 正常返回 / 实例不可达 raise / 未配 URL raise / 空结果 [] / auto-default 推导）；`ruff check` + `ruff format` 干净；schema `provider` enum 含 `searxng`。 |
