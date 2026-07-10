# feat-425-M1: tool-presenter-emoji — Tasks

## 目标

让"工具展示随工具走"覆盖 emoji 这一要素,并修复 web_search / web_fetch 在 IM 聊天面板的渲染:
emoji 进 `ToolPresentationEvent` 全链路透传 + 落库;9 个内置 presenter 类下沉到各自工具文件;
web_fetch 补展示正文字段;web_search 获得自己的 presenter + 结果卡。

## 退出标准

- `pytest -m "not e2e"`(含 im_service)全绿
- `pytest tests/contract/` 全绿(依赖方向不破:product 包仍只 import `agent.sdk`)
- `ruff check src/ tests/` + `ruff format --check src/ tests/` 干净
- 前端 `npm run test`(vitest)全绿 + `npm run build` 绿
- 7 个内置工具(read/write/edit/bash/agent/memory/skill_manage/task_stop)presenter 下沉后行为**零变更**
  (golden + test_presentation.py + 全测试树兜),emoji 是唯一新增;只有 web_fetch / web_search 是有意行为变化

## 测试策略

跨包展示链路改动,逐层单测 + golden 契约兜回归:

1. **core**:`ToolPresentationEvent.emoji` 字段 + `_presentation_dict` 序列化单测(realtime_stream)。
2. **决策 3 下沉零回归**:`test_presentation_golden.py` 给 `_evt_tuple` 加 emoji 维度(内置工具一律
   预期 `emoji=""`,web_fetch 预期 `🌐`);`test_presentation.py` 9 个 presenter 各 status 路径。
   golden 的预期更新**只来自两个有意决策**(emoji 维度 + web_fetch 改读 content/final_url),其它工具
   summary/detail 措辞一字不改。
3. **决策 4**:web_fetch.run() 返回 content/final_url 单测 + serialize_result 仍只吐 text 回归;
   presenter 折叠 url / 读 content / 失败判 `output["ok"] is False` 单测。
4. **决策 5**:web_search presenter + detail schema + 空/双失败通道单测。
5. **决策 1/2 透传链**:gateway relay 转发 emoji 单测;IM ToolCall emoji parse/serialize/persist
   往返单测(复用 feat-409 detail 的同一测试文件)。
6. **前端**:vitest 覆盖 emoji 事件优先 / 名表兜底 / 历史行降级、WebSearchCard(有结果/空态/失败)、
   WebCard 去 title 改正文非空;`npm run build` 类型验证。

## UI 状态矩阵

| 工具 | 折叠态 | 展开态 |
|---|---|---|
| web_search 成功 | `🔍 <query>` | 结果卡:逐条 标题/网址(纯文本)/摘要 |
| web_search 空结果 | `🔍 <query>` | "无结果"空态文案 |
| web_search 失败 | `🔍 <query>` + 标红 | ErrorCard 显出错原因 |
| web_fetch 成功 | `🌐 <url>` | URL + 状态码 + 正文(非空) |
| web_fetch 失败 | `🌐 <url>` + 标红 | 可读错误说明/状态码,无空正文/`status=None` |
| 自定义工具(声明 emoji) | 该 emoji + 名 + summary | 按 detail 渲染(BESPOKE 或 GenericCard) |
| 自定义工具(未声明) | 🔧 + 名 + summary | 同上 |
| 既有内置工具 | 与变更前完全一致(emoji 名表兜底) | 与变更前完全一致 |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | C1 红测:emoji 全链路 + web_fetch/web_search presenter + 字段修复(含 golden emoji 维度更新) | DONE |
| R2 | C2 实现:core emoji 字段 + realtime 序列化 + 9 presenter 下沉 + web_fetch 决策4 + web_search 决策5 + gateway relay + IM 落库五层 + 前端事件优先/WebSearchCard/WebCard | DONE |
| R3 | C3 文档:delta-spec(kernel emoji + im web_search/web_fetch 折叠/展开)+ design changelog | DONE |
