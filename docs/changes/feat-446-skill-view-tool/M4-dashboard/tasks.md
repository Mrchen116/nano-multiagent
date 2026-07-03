# feat-446-M4: dashboard — Tasks

> 对齐: `../design.md` v1

## 目标

在现有 Agent detail shell 中新增 Skills 使用统计页，并通过 IM HTTP API → Gateway WS RPC 从对应 agent workspace 的真实 `.usage.json` 读取数据；同时让 chat v2 工具调用面板对 `skill_view` 提供可审计的专属折叠/展开/失败展示。

## 退出标准

- [ ] Skill 列表视图显示真实 `use_count`、状态、最近 30 天趋势，并支持 archived 过滤视图。
- [ ] Agent 维度视图显示最近 30 天 skill 使用热力图。
- [ ] 健康度视图显示 F3/F4 创建总数、仍 active 数、`use_count > 0` 数的漏斗数字。
- [ ] 无 skill 数据显示空态；gateway 离线/超时显示离线提示，不伪装为空数据。
- [ ] `skill_view` 工具行折叠态显示 `查看 skill：<name>`。
- [ ] `skill_view` 工具行展开态显示 name、location、content 预览/展开全文。
- [ ] `skill_view` 失败态标红并展示错误原因。
- [ ] `cd src/IM/frontend && npm run test` 全绿。
- [ ] IM API 返回真实 `.usage.json` 数据。

## 测试策略

- 被测行为（来自退出标准）：
  - IM API 经 Gateway WS RPC 返回真实 `.usage.json`，缺失文件返回空列表，gateway 离线返回 503。
  - Gateway RPC 聚合 `trend_buckets`、`heatmap_data`、自进化健康度所需字段，并保留 archived 数据。
  - Agent detail 的 Skills 页展示列表、archived 过滤、热力图、健康度漏斗、空态和离线态。
  - chat v2 `skill_view` 工具行展示折叠摘要、展开详情和失败原因。
- 已有测试在：
  - 扩展 `tests/im_service/unit/test_gateway_handler.py`、`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、`tests/im_service/integration/test_agent_config_api.py`，沿用 heartbeat/cron WS RPC 测试模式。
  - 扩展 `src/IM/frontend/src/features/settings/agents/im-agent-config-api.test.ts`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`。
  - 扩展 `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx`。
- 落层/目录/marker：
  - 后端 HTTP/WS RPC：`tests/im_service/unit`、`tests/im_service/integration`、`tests/unit/personal_assistant`，marker 无。
  - 前端组件/API：Vitest colocated tests，marker 无。
  - 真实浏览器验收：一次性 Playwright/Vite 脚本证据写入 `progress.md`，不提交为永久测试。
- 可选依赖 importorskip：无；浏览器验收使用本地前端已有 Playwright 依赖或临时脚本，证据不进测试套件。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`/tmp/feat446-m4-browser-qa/*` 截图、console/network 记录、真服务 API curl 输出摘要。

### 前端实现计划

用户路径分类：

- 使用统计面板：`normal-ui`，需 Vitest regression + 真实浏览器临时验收。
- `skill_view` 工具卡：`normal-ui`，需组件 regression + 真实浏览器临时验收。
- IM API 数据通道：后端真实入口，需要 HTTP/WebSocket integration regression。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | Skills 页 list/agent/health 三视图显示真实 mock 数据；浏览器截图覆盖。 |
| loading | Query loading 文案/骨架由 Agent detail query 或 Skills usage query 覆盖。 |
| empty | API 返回空 skills 时显示“暂无 skill 使用数据”空态。 |
| error | API 503/请求失败显示离线/失败提示和重试入口。 |
| disabled | Archived 过滤无匹配时显示过滤空态；按钮状态不改变布局。 |
| submitting | N/A，本页无提交操作。 |
| permission denied | N/A，沿用路由鉴权；本 milestone 不新增权限态。 |
| long content | `skill_view` content 长文本预览 + 展开全文组件测试覆盖。 |
| missing/nullable data | `last_used_at`、`created_at`、`session_refs` 缺失时使用可理解占位，不崩溃。 |
| mobile viewport | Playwright 截图覆盖 Agent detail Skills 页和 tool card。 |
| desktop viewport | Playwright 截图覆盖 Agent detail Skills 页和 tool card。 |
| dark mode（如项目支持） | N/A，当前 IM 前端无独立暗色模式入口。 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| IM 误读本地 workspace 而非 Gateway workspace | HTTP/WS integration 断言 frame 类型、真实 `.usage.json` 由 gateway 读取 | 是 |
| archived 数据被过滤丢失 | 后端 aggregation + 前端 archived filter regression | 是 |
| dashboard 状态错把离线当空态 | API 503 + 前端离线态 regression | 是 |
| `skill_view` 失败态只显示通用 JSON | ToolCallsPanel regression + browser screenshot | 是/截图 |
| dashboard 真实页面布局溢出 | Vite + Playwright desktop/mobile 截图，console/network 检查 | 否，证据写 progress |

## Roadpoints

### R1 — usage API and gateway RPC

- 状态: DONE
- 步骤:
  - 增加 IM route response model 与 `/im/v1/agents/{agent_id}/skills/usage`。
  - 扩展 `GatewayHandler` request/waiter/response handling。
  - 扩展 PA `IMConnectionManager` 下行 request handler，读取 `<workspace>/.nanoassistant/skills/.usage.json` 并聚合 30 天趋势。
  - 增加后端 unit/integration tests，证明返回真实 `.usage.json`。
- 验证:
  - `PYTHONPATH=src pytest -q tests/im_service/unit/test_gateway_handler.py::test_request_node_skills_usage_returns_none_when_node_offline tests/im_service/unit/test_gateway_handler.py::test_handle_skills_usage_resolves_waiter_with_usage_payload tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_handles_skills_usage_request tests/im_service/integration/test_agent_config_api.py::test_get_skills_usage_calls_rpc_not_direct_file_read tests/im_service/integration/test_agent_config_api.py::test_get_skills_usage_reports_offline_when_rpc_times_out` -> 5 passed.
  - `PYTHONPATH=src pytest tests/im_service/unit/test_gateway_handler.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/integration/test_agent_config_api.py -q` -> 81 passed.
  - `python -m compileall -q src/IM/ws/gateway_handler.py src/personal_assistant/ws/im_connection.py src/IM/api/routes/agents.py` -> passed.

### R2 — Agent detail Skills dashboard

- 状态: TODO
- 步骤:
  - 在 `im-agent-config-api.ts` 增加 usage API client 和类型。
  - 在 Agent detail shell 加 `Config / Skills` 分段导航，配置页原内容保持原样。
  - 新增 Skills panel，覆盖 list/agent/health 三视图、archived 过滤、空态、离线态。
  - 扩展前端 API 和 Agent detail tests。
- 验证:
  - `cd src/IM/frontend && npm run test -- --run src/features/settings/agents/im-agent-config-api.test.ts src/features/settings/agents/agent-detail-page.test.tsx`
  - `cd src/IM/frontend && npm run test`

### R3 — skill_view tool card and browser QA

- 状态: TODO
- 步骤:
  - 扩展 tool presenter helpers/detail renderer，给 `skill_view` 专属 emoji、折叠摘要和详情卡。
  - 扩展 `ToolCallsPanel` regression 覆盖成功、长内容、失败态。
  - 启动隔离 IM/Gateway/Vite 或稳定真入口数据，完成真实浏览器 desktop/mobile 验收、console/network 检查和截图。
  - 回填 `progress.md` 每条退出标准证据。
- 验证:
  - `cd src/IM/frontend && npm run test -- --run src/features/chat/v2/components/tool-calls-panel.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - 真入口浏览器验收截图与 console/network 结论记录到 `progress.md`
