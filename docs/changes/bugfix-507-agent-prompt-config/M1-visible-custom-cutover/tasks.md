# bugfix-507-M1: visible custom prompt cutover — Tasks

> 对齐: ../design.md（2026-08-06 Gate 2 approved）

## 目标

Owner 升级后能在 Custom Instructions 中看到此前隐藏但实际生效的角色文本，并以稳定提示词预览核对下一轮会采用的公开配置；IM/PA 公开配置不再存在可生效或复活的 `system_prompt` 路径。

## 退出标准

- [ ] IM SQLite 与 Gateway YAML 都按 legacy-first 合并表把旧 `system_prompt` 幂等迁入 `custom_prompt`，新存储和公开 API 不再包含 legacy 字段。
- [ ] 首次 `node.register` 可用 `agent_custom_prompts` 为 IM first-seen profile 提供 canonical seed，已有 profile（含显式空值）不被覆盖。
- [ ] PA runtime、session metadata、live snapshot 与 preview 只使用 `custom_prompt`；Kernel 内部 generic override 保持可用。
- [ ] conversations 不再复制 `config_system_prompt` 正文，既有聊天在配置更新后继续使用历史并于下一轮采用新稳定配置。
- [ ] Agent 设置页与创建页称其为 stable system prompt preview，继续明确排除 group/memory runtime 段，并通过真实浏览器验收。
- [ ] 隔离 IM↔Gateway 真进程路径证明旧 YAML → 空 IM → 可见 custom → preview/下一轮一致 → 改配置后既有聊天继续。

## 测试策略

- 保护的回归风险与可观察 seam: SQLite/YAML 迁移后的列与序列化结果；IM HTTP Agent profile shape；真实 `node.register` seed 与 notification-only `config.sync`；Gateway live payload/PromptSlots/LLM system prompt；浏览器 Custom Instructions 与 stable preview。
- 已有保护与处置: 扩展 IM repository/contract/API、Gateway reporter/config-sync/session、PA prompt integration、frontend Agent settings 与 config-continuity E2E；同一失败原因只在最低层断言合并逻辑，高层只验证跨边界接线和用户旅程。
- 落层/目录/marker: `tests/unit/`、`tests/im_service/{unit,contract,integration}/`、`tests/integration/`，marker 无；真进程路径在 `tests/e2e/critical_paths/`，marker `e2e`；真实浏览器为一次性验收证据。
- 文件归属: 迁移组合新增语义 owner `tests/im_service/unit/test_agent_prompt_config_migration.py` 与 `tests/unit/personal_assistant/config/test_agent_prompt_config_migration.py`（既有对应文件已超过 400 行或没有迁移 owner）；其余扩展既有语义 owner。
- 可选依赖 importorskip: E2E 依赖沿用既有 suite/fixture；不新增可选依赖导入。
- 本 milestone 产生的一次性验收证据（收尾不进测试套件）: `M1-visible-custom-cutover/evidence/` 中桌面/移动截图及 browser QA 记录；服务日志、PID、数据库仍留 worktree runtime，不提交。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| IM profile/API 仍暴露 legacy 字段 | `tests/im_service/contract/test_agent_config_contract.py`、`tests/im_service/integration/test_agent_config_api.py` | rewrite-merge | 公开 shape 与更新路径仍需保护，改为只断言 custom | focused pytest |
| 首见 profile seed 与重注册 precedence | `tests/im_service/integration/test_gateway_im_registration.py`、`tests/im_service/unit/test_repositories_agent_profile.py` | rewrite-merge | 沿用真实 WS/register 与 repository seam，加入 custom seed/显式空不覆盖 | focused pytest |
| Gateway YAML/mirror/live/runtime 投影 | `tests/unit/personal_assistant/test_gateway_im_config_sync.py`、`test_gateway_upstream_reporter.py`、`test_gateway_session_binder.py`、`test_inbound_pipeline_session_metadata.py` | rewrite-merge | 删除对公开 `system_prompt` 的旧假设，以 canonical custom 和无 legacy key 替代 | focused pytest |
| PA prompt 公开字段来源 | `tests/integration/test_personal_assistant_prompt_integration.py` | rewrite-merge | 保留同源装配风险，断言 duck-typed legacy 值也不能注入 | focused pytest |
| 既有聊天配置更新连续 | `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py` | rewrite-merge | 同一真进程风险 owner 中加入旧 YAML 首次注册、preview 与 LLM stable prompt 证据 | e2e pytest |
| UI 保存/预览与 API shape | `src/IM/frontend/src/features/settings/agents/{im-agent-config-api,agent-create,agent-edit,agent-detail-page,agent-prompt-preview}.test.*` | rewrite-merge | 行为仍在，更新字段与 stable-preview 文案断言，不固化无关布局 | vitest |
| Kernel generic override | `tests/contract/test_sdk_kernel_wiring.py` | keep | 内部控制面仍是合法独立能力 | focused contract pytest |

### 前端验收计划

- 用户路径分类: `bug-regression`（隐藏人设与 preview 不一致），必须有 API/组件 regression，并完成真实浏览器验收。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 已迁移 custom 显示在 textarea，stable preview 展示同一文本 |
| loading | 保留既有 preview loading regression |
| empty | custom 为空时 preview 无额外 profile 人设 |
| error | 保留既有 preview error regression |
| disabled | N/A；本次不改变控件 enable 条件 |
| submitting | 保留既有保存 pending/dirty 行为 |
| permission denied | N/A；owner-scoped 403/404 行为不变 |
| long content | 浏览器检查 textarea 与 preview 的长文本可滚动/换行 |
| missing/nullable data | `custom_prompt: null` 归一化为空输入 |
| mobile viewport | 390×844 打开配置、展开 preview 并截图 |
| desktop viewport | 1440×1000 编辑/保存、展开 preview 并截图 |
| dark mode（如项目支持） | N/A；Agent 设置页无独立 dark-mode contract |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| legacy 文本仍隐藏或重复注入 | migration unit + IM API/真进程 E2E | 是 |
| preview 与下一轮稳定配置分叉 | PA integration + 真进程 recording LLM + 浏览器 | 是（回归）+ 当次证据 |
| stable/runtime exclusion 文案错误 | i18n/component regression + 桌面/移动浏览器截图 | 是（语义）+ 当次证据 |
| 空 custom 仍有 profile 人设 | PA integration + 浏览器 empty 状态 | 是 + 当次证据 |

Prototype / Reference Contract: N/A；design 未提供 prototype 或 reference screenshot。

## Roadpoints

### R1 — IM canonical profile、schema 与 register seed

- 状态: DONE
- 步骤: 先写 migration 合并表/API shape/register precedence 红测；再移除 AgentProfile/API/SQLite/conversation legacy 字段并接入 `agent_custom_prompts` first-seen seed。
- 验证: IM repository/contract/integration focused pytest；fresh DB 与 old DB schema inspection。

### R2 — Gateway YAML、sync 与 runtime prompt 单源

- 状态: DONE
- 步骤: 先写旧 YAML/旧 mirror/registration payload/runtime prompt 红测；再让 `AgentWorkspaceConfig` 只保留 canonical custom，移除 live/session legacy projection，更新 E2E fixture 数据。
- 验证: PA unit/integration/contract focused pytest，断言序列化和 wire payload 无 legacy key，Kernel override 回归通过。

### R3 — Frontend public shape 与 stable preview 文案

- 状态: IN PROGRESS
- 步骤: 先更新 regression 断言为无 legacy profile 字段和 stable preview；再收敛 TS types/payload 与中英文文案。
- 验证: focused vitest + frontend build；UI 状态矩阵 ready for browser。

### R4 — 隔离真栈、浏览器与最终门禁

- 状态: TODO
- 步骤: 扩展现有 config-continuity critical path，跑旧 YAML→空 IM seed→preview→下一轮/更新后历史连续；启动隔离 Vite 做桌面/移动浏览器验收并保存证据。
- 验证: e2e critical path、浏览器 console/network 检查、focused/full risk gates、`git diff --check` 与 Ruff。
