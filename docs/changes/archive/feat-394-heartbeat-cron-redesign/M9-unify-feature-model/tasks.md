# feat-394-M9: unify-feature-model — Tasks

## 目标

把 heartbeat/cron 并入 FEATURE_REGISTRY，与 memory/skill 完全同模型。
铲除 ad-hoc 平行机制（ctx.vars 门控 / cron_json / heartbeat_enabled/cron_enabled 字段）。
让前端进 Features 列表复选、勾后展开配置面板、工具 pill 按 default_on 渲染有效态。

## 退出标准（[worker] 轨）

- FEATURE_REGISTRY 含 cron_scheduling(requires_tool=cron)/heartbeat(requires_tool=None)，
  prompt 段经 ctx.flags 门控单测通过
- resolve_effective_tool_allowlist 纯白名单（无 cron-append），单测通过
- cron/heartbeat enable 经 features dict 持久化+同步、cron_json 退役、老 profile backward compat 测试
- capabilities.tools 带 default_on + IM 透传 + 前端有效态渲染测试
- promptPreview 携 features 使 cron/heartbeat 段反映的前端测试
- prompt 段文案与 openclaw 逐字一致不变单测
- coding_cli 不广告 cron/heartbeat 特性、无 cron 工具/无 pa.heartbeat·pa.cron 段隔离断言
- pytest -m "not e2e" 全绿（含 im_service）+ contract + tsc -b + vitest 绿

## 测试策略

后端：单元测试（feature_registry / prompt_sections 门控 / resolve_effective_tool_allowlist /
local_store / inbound_pipeline / upstream_reporter / main.py sync）
前端：vitest 单元测试（Features 列表渲染 / promptPreview 段变化 / 工具 pill default_on）
     + tsc -b 类型检查

## UI 状态矩阵

| 状态 | 处理方式 |
|---|---|
| heartbeat 特性未勾 | 配置面板隐藏 |
| heartbeat 特性已勾 | cadence every + active hours 面板展开 |
| cron 特性未勾 | cron 配置面板隐藏，cron 工具不在 pill 区 |
| cron 特性已勾 | Scheduled tasks 列表面板展开，cron 工具即时出现在 pill 区 |
| 默认工具（read/write 等）空白名单时 | pill 显示选中（default_on=true），可取消选中 |
| 默认工具被取消 | 保存后不下发，重进仍显未选 |
| mobile viewport | N/A（配置页桌面优先） |

## 用户路径分类

- Features 列表 + 勾选联动：normal-ui
- 工具 pill 默认可禁：normal-ui
- Preview 段随 features 变化：normal-ui

---

## Roadpoints

### R1 — FEATURE_REGISTRY 加 cron_scheduling/heartbeat + 红测 [TODO]

后端红测：FEATURE_REGISTRY 中 cron_scheduling.requires_tool == "cron"、
heartbeat.requires_tool is None、两者 default_on=False、layer="product"。
范围：feature_registry.py + 单测文件。

### R2 — prompt_sections 门控改 ctx.flags + 删 runtime/kernel vars 注入 [TODO]

- prompt_sections.py：_heartbeat_enabled/_cron_enabled 改读 ctx.flags.get("heartbeat"/"cron_scheduling")
- runtime.py：删 "heartbeat_enabled"/"cron_enabled" 注入 vars
- kernel.py：删 assemble_prompt_preview 的 heartbeat_enabled/cron_enabled 参数
- main.py：删 PromptPreviewProvider 的 heartbeat/cron 参数转发
- 相关测试同步
范围：prompt_sections.py / runtime.py / kernel.py / main.py + 测试

### R3 — AgentWorkspaceConfig 改 features 派生 + cron_json/heartbeat_json 退役 [TODO]

- local_store.py：AgentWorkspaceConfig 删 cron_enabled/heartbeat_enabled 字段，
  加 @property 读 features（features.get("cron_scheduling") / features.get("heartbeat")）
- local_store.py：_parse_agents 退役 cron_json 解析（只认 features）
- main.py：config sync 退役 heartbeat_json/cron_json，改写 features dict
- heartbeat_scheduler.py：读 agent.cron_enabled/heartbeat_enabled 经 property 不变
- 约 30 处测试构造点更新
范围：local_store.py / main.py / heartbeat_scheduler.py + 测试

### R4 — inbound_pipeline 删 cron-append + metadata 注入 agent_features [TODO]

- inbound_pipeline.py：resolve_effective_tool_allowlist 删 cron_enabled 参数和 append 逻辑
- inbound_pipeline.py：_build_session_metadata 删 cron_enabled 注入
- 相关测试
范围：inbound_pipeline.py + 测试

### R5 — IM 后端 + upstream_reporter default_on [TODO]

- config_service.py：AgentProfile 退役 cron_json，features dict 承载 cron_scheduling/heartbeat enable
- models.py/domain：AgentProfile.cron_json 退役
- routes/agents.py：capabilities.tools 带 default_on；features endpoint 含新两条
- upstream_reporter.py：_build_tool_names 带 {name, description, default_on}
- 相关测试（config contract / agent config API）
范围：IM/ + upstream_reporter.py + 测试

### R6 — 前端重构：Features 列表 + 勾后展开 + 工具 pill 有效态 [TODO]

- agent-detail-page.tsx / agent-create-page.tsx：
  heartbeat/cron 进 Features 复选列表（与 memory/skill 并列）
  勾选后展开各自配置面板（heartbeat→cadence+activeHours；cron→Scheduled tasks）
  移除 CronCard/HeartbeatCard 独立 enable 开关（只保留配置内容部分）
- allowlist-selector.tsx / pill-selector.tsx：
  工具 pill 据 default_on 渲染有效态（空白名单时默认工具显示选中、可禁）
- i18n：zh.json/en.json 加 feature.heartbeat.label/help / feature.cron_scheduling.label/help
- 类型：CronConfig 退役（enable 字段移入 features）
- vitest 测试
范围：src/IM/frontend/src/features/settings/agents/ + i18n + 类型 + 测试

### R7 — 全树测试门禁 + 文档 [TODO]

- pytest -m "not e2e" 全绿（含 im_service、contract）
- tsc -b + vitest 绿
- ruff check + ruff format --check 绿
- progress.md 收口
范围：全树
