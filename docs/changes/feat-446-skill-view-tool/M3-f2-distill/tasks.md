# feat-446-M3: f2-distill — Tasks

> 对齐: ../design.md v1

## 目标

交付 F2 从历史会话蒸馏 skill 的最小端到端入口：Gateway 启动安装 PA 内置 `conversation-skill-distiller`，IM conversation 列表暴露通用 `run_state` 与可审计 JSONL 路径，前端支持会话多选、执行 agent / 写入范围确认、跳转执行 agent 新对话并预填普通聊天消息，用户发送后仍由现有 Gateway/agent/tool 展示链路完成。

## 退出标准

- [x] 干净 HOME 或移走 `~/.nanoassistant/skills/conversation-skill-distiller` 后启动 Gateway，会自动生成 `~/.nanoassistant/skills/conversation-skill-distiller/SKILL.md`，且不覆盖已存在的用户本地同名 skill。
- [x] 默认 IM conversation 列表不显示运行态标签。
- [x] 用户进入"生成 skill"多选模式后，checkbox 出现，`run_state=idle` 的 conversation 可选，`run_state=running` 的 conversation 禁选并显示"运行中"。
- [x] 用户选择一个或多个可选 conversation 后，点击"蒸馏为 skill"会先按来源 agent 集合确定执行 agent：来源全属同一 agent 时自动使用该 agent，来源跨多个 agent 时弹窗要求用户选择一个执行 agent。
- [x] 确认执行 agent 可发现 `conversation-skill-distiller`，不可见时提示去配置页启用，不预填无法加载的 `/skill:`。
- [x] 可见时同一弹窗选择 agent 级或 PA 产品级写入范围，再跳转到执行 agent 的新对话。
- [x] 现有输入框预填 `/skill:conversation-skill-distiller`、`source_jsonl_paths`、`execution_agent_id`、`target_scope` 和默认意图 prompt。
- [x] 用户编辑后按普通聊天消息发送，Gateway 不解析 `source_jsonl_paths`、不注入 transcript。
- [x] agent 在蒸馏 skill 指导下读取 JSONL path，任一 source 不可读或证据不足时不创建 skill。
- [x] agent 通过 `skill_manage(create, scope=<target_scope>)` 写入对应 skill root，并通过现有工具调用展示/普通回复告知结果。
- [x] 本期不新增 SKILL.md 草稿预览卡片或确认写入/取消按钮。
- [x] 蒸馏 skill 使用标准目录型包内资源并纳入 package data；若 generic built-in skill bootstrap 未合并则实现同一通用 helper，不能写 feishu/distill 专用逻辑。
- [x] IM 前端相关测试全绿。
- [x] `skill_manage(create)` 在 `target_scope=agent` 时写入执行 agent 的 skill root，在 `target_scope=pa` 时写入 PA skill root。
- [x] 历史蒸馏创建的 skill 按用户主动创建处理，不进入自动 Curator。

## 测试策略

- 被测行为（来自退出标准）：PA 内置 skill 自举安装/不覆盖；conversation `run_state` 与 `source_jsonl_path` 响应；前端默认不显示运行态、多选模式 idle/running 交互、单 agent 自动执行 agent、跨 agent 选择执行 agent、skill 不可见拦截、scope 选择、跳转新对话预填、普通发送不特殊解析；蒸馏 SKILL.md 对不可读/证据不足/create scope 的指令约束；`skill_manage(create, scope=agent|pa)` 复用 M1 行为回归。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_launch.py`（扩展 Gateway 启动自举），`tests/im_service/unit/test_repositories_user_conversation.py` / `tests/im_service/unit/test_message_runtime_state.py`（扩展 conversation 派生字段），`src/IM/frontend/src/features/chat/v2/components/conversation-sidebar.test.tsx` 与 `chat-workspace.integration.test.tsx`（扩展前端交互），`tests/unit/test_skill_manage_tool.py`（已有 scope 行为，必要时补回归）。新建 `tests/unit/personal_assistant/test_builtin_skills_bootstrap.py`，理由：当前没有 PA 包内 builtin skill bootstrap 的独立行为测试。
- 落层/目录/marker：后端 `tests/unit/` 与 `tests/im_service/unit/`，marker：无；前端 Vitest component/integration，无 pytest marker；真实浏览器验收作为一次性证据，不进测试套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`ACCEPTANCE/feat-446-M3/` 下的浏览器截图/日志；临时运行的 IM/Vite/Gateway 进程由 pidfile 清理。

用户路径分类：critical-path（F2 conversation 选择 → 新对话预填 → 普通发送），需要前端交互 regression + 真实浏览器验收。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 默认 conversation 列表无运行态标签；右键菜单入口可见 |
| loading | 复用现有 conversation 加载态，本 milestone 不改；回归跑 chat v2 现有测试 |
| empty | 无选中 conversation 时蒸馏按钮 disabled |
| error | 执行 agent 不可见 `conversation-skill-distiller` 时弹窗内错误提示，不跳转 |
| disabled | `run_state=running` conversation 禁选且显示"运行中"；无选择时按钮 disabled |
| submitting | 跳转新对话预填后使用现有 composer 发送路径，复用现有 submitting 行为 |
| permission denied | N/A，本入口不新增权限门控 |
| long content | 长标题/多 JSONL path 在侧栏与 composer 中不撑破布局，浏览器验收覆盖 |
| missing/nullable data | 缺 `run_state` 按 `idle` 兼容；缺 `source_jsonl_path` 不进入可用蒸馏选择 |
| mobile viewport | 浏览器验收覆盖移动宽度，验证侧栏/弹窗/预填不重叠 |
| desktop viewport | 浏览器验收覆盖桌面宽度，验证右键、多选、弹窗、预填 |
| dark mode（如项目支持） | N/A，当前 chat v2 无独立 dark mode 入口 |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| Gateway 未安装内置 distiller 或覆盖用户文件 | PA unit test + 真实 Gateway 启动 HOME 隔离验证 | 是 + 临时证据 |
| conversation `run_state` / JSONL 路径响应缺失 | IM repository/API unit test | 是 |
| 多选模式误选 running conversation | sidebar component test + 浏览器验收 | 是 |
| 跨 agent 执行 agent / scope 选择错误 | workspace integration test + 浏览器验收 | 是 |
| skill 不可见仍预填 `/skill:` | workspace integration test | 是 |
| 预填内容字段缺失或发送被特殊处理 | workspace integration test + 浏览器验收 | 是 |

## Roadpoints

### R1 — built-in distiller and scope contract

- 状态: DONE
- 步骤: 补 PA 内置 skill bootstrap 测试与 distiller SKILL.md；确认/补 package data；回归 `skill_manage(create, scope=agent|pa)`。
- 验证: `PYTHONPATH=src pytest tests/unit/personal_assistant/test_builtin_skills_bootstrap.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/test_skill_manage_tool.py -x`

### R2 — conversation distill metadata

- 状态: DONE
- 步骤: 为 IM conversation 响应派生 `run_state` 与 `source_jsonl_path`；保持默认列表不展示运行态由前端控制。
- 验证: `PYTHONPATH=src pytest tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_message_runtime_state.py tests/im_service/integration/test_users_conversations_api.py -x`

### R3 — frontend selection and prefill flow

- 状态: DONE
- 步骤: 在 chat v2 conversation 侧栏接入右键"生成 skill"多选、running 禁选、执行 agent/scope 弹窗、skill 可见性检查、跳转执行 agent 新对话并预填 composer。
- 验证: `cd src/IM/frontend && npm run test -- --run src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/chat-workspace.integration.test.tsx`

### R4 — real entry QA and final gates

- 状态: DONE
- 步骤: 起 IM/Vite/Gateway 真入口验收干净 HOME 自举和 F2 浏览器路径；补 progress 证据；跑后端/前端最终门禁。
- 验证: `PYTHONPATH=src pytest tests/unit/personal_assistant/test_builtin_skills_bootstrap.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/test_skill_manage_tool.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_message_runtime_state.py -x`；`cd src/IM/frontend && npm run test -- --run src/features/chat/v2`；浏览器截图/console/network 记录。
