# feat-515-M1: 创建时选择并固定 Agent workspace root — Tasks

> 对齐: ../design.md v1

## 目标

用户能在 Agent 创建页选择节点默认目录或目标节点上的自定义绝对路径；Gateway 在节点本地完成
路径解析、确认、唯一性、初始化和 provenance 持久化，IM 只转发结构化结果并原样镜像 root。

## 退出标准

- [ ] 创建页在 Identity 与 Behavior 之间提供默认/自定义 Workspace 卡，桌面与 390px 窄屏符合原型。
- [ ] 默认与自定义创建分别返回正确 canonical root 和 default/custom provenance；已有 Agent 详情保持只读且无新增来源标签。
- [ ] 缺失/不可用 parent、非目录 target、已有目录未确认、同节点已占用均无创建副作用，并返回可呈现的稳定错误码。
- [ ] 已有目录确认重试成功且不覆盖现有文件；不同节点的同字符串路径不共享 ownership 索引。
- [ ] IM 全链路把 Gateway root 当 opaque mirror，register/migration/legacy 行为兼容，节点侧负责新建前 preview root 解析。
- [ ] 相关 Python/frontend 测试、production build、ruff、diff check、docs check 与隔离单/双 Gateway 真栈和浏览器验收通过。

## 测试策略

- 保护的回归风险与可观察 seam: Gateway 创建 handler 的文件系统/本地 config 结果；`agent.created` 帧和 HTTP 状态/JSON；SQLite profile/register 镜像；真实 `/im/v1/nodes/:id/agents`；创建页提交 payload、错误分支、确认重试和视觉状态。
- 已有保护与处置: 扩展 `tests/unit/personal_assistant/test_agent_config_sync_ownership.py`、`test_gateway_im_connection_behavior.py`、`tests/im_service/{unit,integration,contract}/` 现有 ownership/create owner；API adapter 扩展 `im-agent-config-api.test.ts`，Workspace 独立交互因既有 `agent-create.test.tsx` 已超 400 行而落到 `agent-create-workspace.test.tsx`。同一风险分别落在 Gateway 文件系统边界、跨进程协议/HTTP 边界和浏览器交互边界，不复制内部调用断言。
- 落层/目录/marker: `tests/unit/`（纯 Gateway creation authority）、`tests/im_service/unit|integration|contract/`（IM persistence/protocol/HTTP）、`src/IM/frontend` Vitest（交互/API adapter）、`tests/e2e/` 或 reviewer runbook（真进程/真浏览器），marker: 真进程/浏览器证据为 `e2e` 或临时验收。
- 文件归属: 扩展上述现有语义 owner；仅在没有合适 owner 时新增按行为命名的测试文件。
- 可选依赖 importorskip: Playwright 真浏览器验收走现有环境，不新增 Python 可选依赖。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: unit evidence 下 desktop/390px 截图、HTTP 请求/响应摘要、单/双 Gateway 旅程报告；runtime config/log/DB 保持 gitignored。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Gateway 动态创建和 local config ownership | `tests/unit/personal_assistant/test_agent_config_sync_ownership.py` | rewrite-merge | 扩为创建 authority 的公开 handler 结果与磁盘副作用，避免私有调用断言 | targeted pytest |
| WS create/preview 协议 | `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、`test_gateway_control_frame_correlation.py` | rewrite-merge | 旧 preview root 由 IM 派生的前提退役，改测节点解析和 structured outcome | targeted pytest |
| IM HTTP 创建与镜像 | `tests/im_service/contract/test_agent_create_contract.py`、`integration/test_agent_create_flow.py` | rewrite-merge | 扩展 code/status/provenance/成功后持久化，保留真实 HTTP+WS seam | targeted pytest |
| register workspace seed | `tests/im_service/unit/test_gateway_handler.py`、`integration/test_gateway_im_registration.py` | rewrite-merge | 增加 provenance seed、空值补齐、legacy root fallback，保留既有 first-seen 风险 | targeted pytest |
| 创建页草稿与提交 | `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`、`agent-create-workspace.test.tsx` | rewrite-merge | 保留原文件的离开保护/节点能力；新建 204 行的 Workspace 语义 owner，避免继续扩展既有超长文件 | targeted Vitest |
| 前端错误 envelope | `src/IM/frontend/src/features/settings/agents/im-agent-config-api.test.ts` | rewrite-merge | 让稳定 `code`/`agent_id` 进入 UI 分支 | targeted Vitest |

### 用户路径分类

`critical-path`: 创建 Agent 的默认、自定义、已有目录确认、路径冲突与父目录失败；落库交互/协议回归并完成真栈浏览器验收。`visual-only`: Workspace 卡桌面/390px 布局；截图对照原型。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 默认模式默认选中，自定义字段隐藏，提交 `workspace_root:null` |
| loading | 复用页面/节点现有 loading；提交中按钮 disabled |
| empty | 自定义空路径在字段处报错 |
| error | parent/target/assigned code 映射到 Workspace 卡 |
| disabled | 节点离线或提交中沿用创建按钮 disabled |
| submitting | 两次确认提交都保持草稿并展示 saving |
| permission denied | N/A；节点 owner/online 门禁沿用既有页级错误 |
| long content | 长自定义路径在卡内不撑宽布局 |
| missing/nullable data | legacy provenance 仅影响详情 API，不给创建表单新增状态 |
| mobile viewport | 390px 模式卡单列与卡片层级 |
| desktop viewport | 两种模式并排且卡位于 Identity/Behavior 之间 |
| dark mode（如项目支持） | N/A；产品当前不提供 dark mode |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 默认/custom payload 与成功 provenance | HTTP/WS integration + frontend interaction + browser | 是 |
| 已有目录零副作用与确认重试 | Gateway unit + HTTP integration + browser | 是 |
| canonical 同节点 ownership / 不同节点隔离 | Gateway unit + 双 Gateway 真栈 | 是（最低层）+ 当次证据 |
| opaque mirror / provenance migration/register/RPC | repository/HTTP/WS tests | 是 |
| desktop/390px 卡片层级与视觉 | 真浏览器截图对照 | 否（当次 durable evidence） |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| Workspace 卡位置 | must-match: 位于 Identity 与 Behavior 之间 | desktop 创建页截图 | worker |
| 默认/自定义模式 | must-match: 二选一且默认选中 | desktop + 390px 截图和交互 | worker |
| 自定义路径字段 | must-match: 明示目标节点、parent 必须存在、字段错误 | custom/parent-error 截图 | worker |
| 已有目录提醒 | must-match: 醒目提示、确认框、再次提交 | existing-directory 截图/录屏 | worker |
| 颜色、间距、控件 | may-adapt: 使用现有 Agent tokens/层级 | desktop/390px 人工对照 | worker |

## Roadpoints

### R1 — Gateway 本地 workspace creation boundary

- 状态: DONE
- 步骤: 先补红测；实现 default/custom provenance、canonical ownership、parent/target/confirmation/initialization outcome、本地 YAML/register 持久化和节点侧 preview root 解析。
- 验证: Gateway focused pytest；文件系统副作用断言；preview/provider seam。

### R2 — WS/HTTP structured outcome 与 opaque IM mirror

- 状态: DONE
- 步骤: 先补红测；扩展 create 帧 outcome、HTTP code 映射、profile provenance schema/repository/migration/register，统一 opaque accessor 并迁移相关 RPC/read seam。
- 验证: IM unit/integration/contract focused pytest；失败不建 profile；root 字符串原样往返。

### R3 — Workspace 创建 UI 与 i18n

- 状态: DONE
- 步骤: 先写交互红测/状态清单；实现卡片、默认/custom payload、字段错误、已有目录确认重试、preview payload、响应式样式和中英 i18n。
- 验证: frontend targeted Vitest、production build；确认 existing Agent detail 未新增 default/custom 标签。

### R4 — 回归矩阵与质量门禁

- 状态: DONE
- 步骤: 汇总/补齐 Gateway/IM/frontend 退出标准覆盖，处理受影响既有测试，运行针对性与风险扩展门禁。
- 验证: focused/full-enough pytest、frontend test/build、ruff、diff check、docs check。

### R5 — 隔离真栈与浏览器原型对照

- 状态: DOING
- 步骤: 通过 runbook 启动隔离 IM/Gateway/Vite 和第二 Gateway，走全部创建旅程；desktop/390px 截图落 unit evidence；检查 console/network；停止并验证资源释放。
- 验证: 单/双 Gateway HTTP/API/DB/文件系统证据、浏览器截图和 Prototype Comparison。
