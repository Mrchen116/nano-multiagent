# feat-440-M1: semantic-reject-feedback — Tasks

> 对齐: ../design.md v1

## 目标

LLM 收到的工具拒绝结果从恒为通用字面量 `tool blocked by hook` 改为按「主会话用户拒 / 主会话用户拒+理由 / 策略自动拒 / subagent 被拒」四类区分的语义化文本（措辞照搬 CC，私有名词处本地化）；IM 权限卡按钮区上方常驻一个选填的拒绝理由输入框，用户拒绝时把理由透传进回传文本。

## 退出标准

- [x] `build_reject_message` 四类映射单测全绿（含非白名单 synthetic→SUBAGENT）— R1/R2
- [x] CC 文本主体逐字一致 + `newText` 本地化 + 自动拒无规则尾句（单测断言）— R1
- [x] reject_messages.py docstring 显式标注「不实现 SUBAGENT 带理由变体为有意省略」— R1
- [x] tool_executor 四类拒绝均经 build_reject_message 构造 ToolResult.error（含提取 details["reason"]）— R2
- [x] IM reason 透传单测（messages 端点 + gateway_handler push）绿 — R3
- [x] 前端 permission-card 常驻选填理由框、deny 带 reason、允许类忽略，组件测试 + 真实浏览器验收绿 — R4

## 测试策略

- 被测行为（来自退出标准）：
  1. build_reject_message 四类信号→文本映射（纯逻辑）
  2. 常量文本与 CC 逐字一致 + newText 本地化 + 自动拒无规则尾句
  3. StreamingToolExecutor：非白名单 synthetic / catch ToolError 两路径产出语义化 error，且提取 details["reason"]
  4. IM 端点 + gateway_handler 透传 reason
  5. 前端理由框存在、deny POST 带 reason、允许类不读 reason
- 已有测试在：
  - reject_messages：无 → 新建 `tests/unit/test_reject_messages.py`，理由：纯逻辑 helper 无现有归属文件
  - tool_executor：扩展 `tests/unit/test_streaming_tool_executor.py`
  - IM 端点：扩展 `tests/unit/IM/test_permission_streaming.py`（已有 REST endpoint 测试类）
  - gateway_handler：扩展 `tests/im_service/unit/test_gateway_handler.py`
  - 前端：扩展 `src/IM/frontend/.../permission-card.test.tsx`
- 落层/目录/marker：tests/unit/ + tests/im_service/unit/（无 e2e marker，纯逻辑/接线/HTTP TestClient）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：浏览器验收截图（progress.md 记路径，不进套件）

### 前端部分（permission-card.tsx）

用户路径分类：`normal-ui`（权限卡新增常驻理由输入框；核心 deny 流程经 messageId/decision POST 已有 regression，新增 reason 字段补组件测试 + 真实浏览器临时验收）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | 待决卡含空理由框 — 组件测试 + 截图 |
| loading | N/A（卡片无独立 loading 态） |
| empty | 理由框空 → deny 不带 reason — 组件测试 |
| error | POST 失败显示 alert（既有，不回归破坏）— 既有测试 |
| disabled | submitting 时按钮 + 理由框禁用 — 组件测试 |
| submitting | 点决策后禁用（既有）— 既有测试 |
| permission denied | 本卡即权限决策入口，N/A |
| long content | 理由框长文本 — 截图（受控 textarea 自然换行） |
| missing/nullable data | reason 选填，留空走默认文本 — 组件测试 |
| mobile viewport | 待决卡 375px — 截图 |
| desktop viewport | 待决卡 1440px — 截图 |
| dark mode | 项目为 dark mono 体系，default 即 dark — 截图 |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| deny 带理由 POST body 含 reason | 组件测试断言 fetch body | 是 |
| 允许类忽略理由框 | 组件测试断言 allow POST 无 reason | 是 |
| 理由框常驻渲染 + 留空可决策 | 组件测试 + 浏览器截图 | 是（组件） |
| 理由框视觉/响应式 | 浏览器截图 1440/375 | 否 |

## Roadpoints

### R1 — [DONE] reject_messages.py（常量 + build_reject_message 选择器）

- 步骤: 新建 `src/agent/core/agent/reject_messages.py`，照搬 CC 四常量（new_string→newText 本地化）+ auto_reject_message(reason) + build_reject_message 四类选择器 + docstring 标注死路径省略。
- 验证: `tests/unit/test_reject_messages.py` 穷举四类映射 + CC 逐字 + newText + 无规则尾句。

### R2 — [DONE] tool_executor.py 接线

- 步骤: catch ToolError 分支提 details["reason"]；非白名单 synthetic + catch 两分支均调 build_reject_message(is_subagent=self._tool_execution_allowlist is not None) 得 error 文本。
- 验证: 扩展 `tests/unit/test_streaming_tool_executor.py`：非白名单→SUBAGENT、user_deny+reason→WITH_REASON、自动拒→auto_reject。

### R3 — [DONE] IM reason 两端透传

- 步骤: messages.py SubmitPermissionDecisionRequest 加选填 reason 透传 push_permission_response；gateway_handler.push_permission_response 加 reason 参数写进 frame payload。
- 验证: 扩展 test_permission_streaming.py（endpoint 透传 reason）+ test_gateway_handler.py（push 写入 frame）。

### R4 — [DONE] 前端权限卡理由输入框

- 步骤: permission-card.tsx 加常驻受控理由 input；handleChoice POST body 带 reason（trim 后非空才带）；允许类决策不影响放行。
- 验证: 组件测试（deny 带 reason / allow 无 reason / 留空可决策）+ 真实浏览器验收（1440/375 截图，console/network 检查）。
