# feat-440-M2: fix-round1（post-acceptance fix）— Tasks

> 对齐: ../design.md v1（Changelog 2026-06-27 M2 行）

## 目标

M1 合入后 code review + reviewer 现场发现一个 CONFIRMED correctness bug（F1）+ 一批防御/覆盖缺口。本 milestone 按根因治本修以下 7 项，使 design §选择表 Row 3（bare user_deny → 简洁 REJECT_MESSAGE）真实路径成立，并补齐被绕过的测试盲点。

## 退出标准

- [ ] F1：gate `response.reason or ""`（去掉 "user denied" 占位），bare-deny 经真 gate 产出 REJECT_MESSAGE；补 gate 层测试
- [ ] F2：`auto_reject_message` 空 reason guard，不产语法损坏 `Reason: . `；补单测
- [ ] F3：IM 后端纯空白 reason 归一化为未提供；补单测
- [ ] F4：前端仅 deny 决策带 reason，allow 类不带（含失败后残留不被 allow 误带）；POST body 断言
- [ ] F5：subagent 内白名单工具被 gate 拒 → SUBAGENT_REJECT 集成测试
- [ ] F6：`is_subagent` 与 `tool_execution_allowlist` 解耦为显式 fork 信号 + 测试
- [ ] 全测试树 `-m "not e2e"` + 前端 vitest 全绿

## 测试策略

- 被测行为：
  - F1：`_handle_ask` user deny + 空 response.reason → payload["reason"] == ""（非 "user denied"）
  - F2：`auto_reject_message("")` 不含 `Reason: . `，仍含 guidance；`build_reject_message(approval=None, reason="", is_subagent=False)` 走 guard
  - F3：endpoint 收到纯空白 reason → 透传给 push_permission_response 的 reason 为 None
  - F4：前端 deny 决策 POST body 含 reason、allow 决策 POST body 不含 reason；失败 deny 后 allow 不带 reason
  - F5：StreamingToolExecutor(is_fork_sidechain=True, allowlist=("edit",))，edit 在白名单但被 hook block 拒 → SUBAGENT_REJECT
  - F6：显式 fork 信号驱动 is_subagent；allowlist 仅管执行裁决
- 已有测试在：扩展 `tests/unit/test_auto_mode_gate_hook.py`(F1)、`tests/unit/test_reject_messages.py`(F2)、`tests/unit/IM/test_permission_streaming.py`(F3)、`tests/unit/test_streaming_tool_executor.py`(F5/F6)、`src/IM/frontend/.../permission-card.test.tsx`(F4)
- 落层/目录/marker：tests/unit + im_service/前端 vitest，marker 无（非 e2e）
- 可选依赖 importorskip：无
- 一次性验收证据：无（全部落库回归）

### 前端（F4）

用户路径分类：bug-regression（修 allow 误带 reason / 失败残留）

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | deny 带 reason、allow 不带（组件测试断言 POST body） |
| submitting | 既有 disabled 覆盖，不回归 |
| error | deny 失败后再 allow 不带 reason（组件测试） |
| 其余 | N/A（本 fix 不改视觉，沿用 M1 已验收布局） |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| allow 误带 reason / 失败残留 | permission-card.test.tsx POST body 断言 | 是 |

## Roadpoints

- R1（F1）: gate `response.reason or ""` + gate 层 bare-deny 测试 — TODO
- R2（F2）: `auto_reject_message` 空 reason guard + 测试 — TODO
- R3（F6）: 显式 fork 信号解耦 + 测试 — TODO
- R4（F5）: subagent 白名单内工具被 gate 拒集成测试 — TODO
- R5（F3）: IM 后端空白 reason 归一化 + 测试 — TODO
- R6（F4）: 前端仅 deny 带 reason + POST body 断言 + 浏览器验收 — TODO
