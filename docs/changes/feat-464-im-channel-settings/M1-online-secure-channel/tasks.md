# feat-464-M1: 在线安全接入与热连接 — Tasks

> 对齐: ../design.md v10

## 目标

从真实 Agent detail → 通道入口完成飞书新增、编辑与在线热连接：IM 安全保存期望配置和密钥 envelope，Gateway 不重启即可调和为稳定 `feishu:<agent_id>` runtime，页面区分 pending/connecting/connected/failed 且不泄漏 secret 或内部 revision。

## 退出标准

- [ ] M1-E1：未配置时展示通用外部通道空态和“添加通道”，不展示 Web IM。
- [ ] M1-E2：已有飞书时 provider picker 显示“已添加”并禁止第二实例。
- [ ] M1-E3：飞书向导只给简短准备说明、指定开放平台链接和 App ID/Secret 必填校验。
- [ ] M1-E4：在线保存后无需改配置文件或重启，先显示 pending/connecting，再显示 connected 或具体 failed；编辑不回显 secret，keep/replace 显式且 replace 才要求新 secret。
- [ ] M1-E5：真实入口的 connected 卡片显示最近状态时间与“当前配置已应用”，不展示 revision/版本号。
- [ ] M1-E6：独立 connection 并发旧 revision 仅一个成功，desired+manifest 原子；envelope 固定向量、credential revision、AAD 篡改、key mismatch、跨 owner、响应/日志无 secret 受测；same-owner bind 幂等，online/offline cross-owner bind 409 且数据/cache/API 隔离不变。
- [ ] M1-E7：runtime 始终使用 `feishu:<agent_id>`；UI 新建和 legacy seam 都可持久化 owner/bot identity、启用 `feishu-doc`；App ID replacement 清 metadata，新 owner 重绑，旧 generation patch 双端拒绝；card action correlation/timeout/crash/first-wins 受测。
- [ ] M1-E8：Feishu worker 可真实 stop/join；同节点两个 listener 隔离；替换凭据切断旧收发；小容量 IPC queue backpressure、status coalescing、priority error、stop drain/drop、incarnation/sequence 逆序和 A→B cutover 受测；四个 M1 原型锚点有 durable 浏览器证据，前端 build 与最窄测试通过。

## 测试策略

- 被测行为（来自退出标准）：M1-E1..M1-E8 全部；HTTP create/list/patch 是后端真实入口，Gateway reconcile 是跨模块入口，Agent detail → 通道是真浏览器入口。
- 已有测试在：`tests/im_service/integration/test_agent_config_api.py`、`tests/im_service/integration/test_account_binding_api.py`、`tests/unit/personal_assistant/test_gateway_channel_and_session.py`、`tests/unit/test_feishu_adapter_permission_approval.py`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`（扩展关联既有行为）；无合适 channel control 测试，新建 `tests/unit/IM/test_agent_channels.py`、`tests/unit/IM/test_channel_credentials.py`、`tests/unit/personal_assistant/test_channel_manager.py`、`tests/unit/personal_assistant/test_feishu_worker_runtime.py`、`tests/integration/test_channel_reconcile.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`，理由：当前产品尚无 external channel control/domain/runtime/UI。
- 落层/目录/marker：纯 store/envelope/runtime 状态在 `tests/unit/`，marker 无；HTTP/WS/manager 接线在 `tests/integration/`，marker 无；真实浏览器为本 milestone durable 临时验收证据，不新增永久 e2e 文件。
- 可选依赖 importorskip：无；项目已安装 cryptography、lark-oapi 与前端 Playwright。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器脚本只在 CLI session 中执行；截图、console/network 报告落 `M1-online-secure-channel/evidence/`，不提交临时脚本。

### 用户路径分类

- `critical-path`：空态 → 添加飞书 → 必填校验 → 在线保存 → pending/connecting → connected/failed → 编辑 keep/replace；用前端交互回归 + 真实浏览器验收。
- `visual-only`：原型卡片层级、状态 pill、桌面密度；用 1440px 截图与 Prototype Comparison。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | provider picker 与新增向导 |
| loading | 通道 query loading 占位 |
| empty | 通用空态、无 Web IM |
| error | 保存 failed 的具体错误；list error 完整态归 M3 |
| disabled | 已添加 provider 选项不可点击 |
| submitting | 保存按钮 disabled + pending/connecting 卡片 |
| permission denied | N/A，权限诊断归 M3 |
| long content | App ID 脱敏单行；M1 无长文本诊断 |
| missing/nullable data | observed 为空投影 pending |
| mobile viewport | N/A，完整移动端验收归 M3 |
| desktop viewport | 1440px 四个 M1 must-match 锚点 |
| dark mode（如项目支持） | N/A，当前产品/原型仅 light |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| secret/envelope 与 owner/revision 原子性 | unit + HTTP integration | 是 |
| 在线热连接/替换旧路径 | manager/WS integration + 真 Gateway | 是 + durable live evidence |
| provider 唯一性和 keep/replace | frontend interaction + HTTP integration + 浏览器 | 是 |
| connected 信息层级 | 1440px 截图 + 文本/无 revision 断言 | 交互断言是，截图否 |
| IPC stop/backpressure/status 顺序/card action | unit/integration | 是 |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `#channels-empty` | must-match：Agent detail → 通道，desktop + empty；M1-E1/E2 | 1440px 真入口截图 + 空态交互报告 | worker |
| `#add-feishu` | must-match：desktop + 已添加 provider 禁选 + required error + 显式 secret keep/replace；M1-E2/E3/E4 | 新增/编辑 modal 截图与交互报告 | worker |
| `#channel-connecting` | must-match：在线新增/编辑保存后的 connecting；M1-E4 | 保存后即时 screenshot + network/console 记录 | worker |
| `#channel-connected` | must-match：desktop connected；“当前配置已应用”+最近状态时间，无内部 revision；M1-E5 | 最终态 screenshot + DOM 文案报告 | worker |
| provider icon、阴影和过渡时长 | may-adapt | 采用现有 IM token/卡片密度，记录偏离 | worker |
| 未来 provider tile、Web IM | out-of-scope，真实产品不得展示 | DOM/截图确认不存在 | worker |

## Roadpoints

### R1 — IM 安全控制面与 HTTP 入口

- 状态: DOING
- 步骤: channel schema + 独立 `ChannelControlStore` + envelope v1 + REST/service；node key 与 bind owner guard；覆盖 M1-E6。
- 验证: `pytest -q tests/unit/IM/test_agent_channels.py tests/unit/IM/test_channel_credentials.py tests/im_service/integration/test_account_binding_api.py`。

### R2 — Gateway 动态 runtime 与 Feishu worker

- 状态: TODO
- 步骤: 并发安全 registry、`ChannelManager`、activation/metadata generation、可终止进程与双向 card action IPC；覆盖 M1-E7/E8 runtime 部分。
- 验证: `pytest -q tests/unit/personal_assistant/test_channel_manager.py tests/unit/personal_assistant/test_feishu_worker_runtime.py tests/unit/test_feishu_adapter_permission_approval.py`。

### R3 — WS 在线 reconcile/status 闭环

- 状态: TODO
- 步骤: node.register 公钥、完整 reconcile/status/metadata frames、Gateway IM client dispatch 与 composition root 在线热应用。
- 验证: `pytest -q tests/integration/test_channel_reconcile.py tests/im_service/unit/test_gateway_handler.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`。

### R4 — Agent 通道页与 provider registry

- 状态: TODO
- 步骤: 通用 channels panel、飞书 provider registry/表单/API；覆盖空态、唯一性、required、keep/replace、connecting/connected/failed。
- 验证: `npm test -- agent-channels-panel.test.tsx im-agent-config-api.test.ts agent-detail-page.test.tsx && npm run build`。

### R5 — 真栈/真浏览器证据与总门禁

- 状态: TODO
- 步骤: 按 reviewer runbook 起隔离真栈，走 M1 用户路径，落四锚点 durable evidence，核对 console/network/secret/worker 清理；完成 M1-E1..E8 对账。
- 验证: 最窄后端/前端、`pytest -m "not e2e"`、`ruff check src tests`、浏览器报告与服务 PID 清理。
