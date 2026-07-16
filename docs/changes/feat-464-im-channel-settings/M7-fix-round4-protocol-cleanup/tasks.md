# M7: Round 4 protocol correlation and security cleanup — Tasks

> 对齐: ../design.md v14

## 目标

闭合 Round 4 verifier 确认的 status wire-send/coalescing race、断线 incarnation 淘汰和 register/heartbeat 错误归属，并确保 removal receipt 自动收敛为空态时清除旧请求错误与等待提示。

> Scope decision（2026-07-16）：用户明确不要求旧 `config.yaml` 或历史 backup 的后向兼容、自动迁移与清理；原 M7 item 4 已移出范围。安全保证只覆盖 IM 通道页新建/更新后不向 `config.yaml` 写入 App Secret。

## 退出标准

- [ ] `channel.status` 在 wire send 开始前进入明确 in-flight owner；并发 coalesce 不会删除该 frame，correlated result 只释放同 request。
- [ ] 同 channel 新 runtime incarnation 在断线后淘汰旧 sent/unacked status；新 socket 只发送 current incarnation，旧 result/ACK 为 no-op，非 status FIFO 不受影响。
- [ ] `node.register` 与 heartbeat 拥有独立 correlation/error owner；register ack 前业务 FIFO 不发送，register/heartbeat error 不弹业务队首、不误伤 waiter。
- [ ] removal retry 响应丢失或临时失败后，polling/自动 reconcile 令 receipt 消失并进入空态时，旧 request error 与 waiting notice 同步清除。
- [ ] deterministic asyncio/two-socket、真实 startup/bootstrap、永久 Vitest 与 targeted production browser evidence 完成；一次性 full backend/frontend/build/Ruff/test-size/secret/diff/process gate 全绿。

## 测试策略

- 被测行为（来自退出标准）：wire-send yield 期间 status owner 稳定；断线后 current incarnation 独占重放；register/heartbeat 错误与业务 FIFO 隔离；removal resource 自动消失时清理旧反馈。
- 已有测试在：`tests/unit/personal_assistant/test_channel_status_protocol.py`、`tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`、`src/IM/frontend/src/features/settings/agents/agent-channels-panel.test.tsx`（扩展）；新建 `tests/unit/personal_assistant/test_gateway_status_frame_ownership.py` 与 `tests/unit/personal_assistant/test_gateway_control_frame_correlation.py`，理由：现有 status/connection behavior 文件已超过或接近 400 行软上限，M7 的 wire-owner/two-socket 与 control-owner 行为需要独立且长期可读的最低层回归。
- 落层/目录/marker：`tests/unit/` 与前端 Vitest，marker：无；targeted production browser 只作 durable evidence，不落一次性 e2e 脚本。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离高位 IM/Gateway、production frontend 和 Playwright session；截图与 sanitized 报告保存在 `M7-fix-round4-protocol-cleanup/evidence/`，临时配置、数据库、日志、PID、symlink 和浏览器 profile 收尾删除。

用户路径分类：
- critical-path：Gateway register/control 与业务上行 FIFO，永久 deterministic asyncio/two-socket regression。
- bug-regression：status replacement 与 removal 自动收敛残影均落永久回归。
- normal-ui：removal temporary error/waiting → polling empty，Vitest + production browser。
- visual-only：空态无旧 alert/notice，截图对照 `#channel-deleting/#channels-empty`。

UI 状态矩阵：
| 状态 | 覆盖计划 |
|---|---|
| default | removal card 保持既有 pending/failed 展示 |
| loading | 复跑既有 channels loading 行为 |
| empty | receipt 自动消失后只显示通用空态 |
| error | retry 临时错误先可见，resource 消失后清除 |
| disabled | N/A，本轮不改启停 |
| submitting | retry pending 保持按钮 disabled |
| permission denied | N/A，本轮不改权限诊断 |
| long content | 临时错误仍按现有布局换行 |
| missing/nullable data | polling 返回空数组触发反馈 owner 清理 |
| mobile viewport | N/A，Round 4 已覆盖；本轮聚焦 desktop targeted browser |
| desktop viewport | production browser 1440×1000 覆盖 failed retry → auto empty |
| dark mode（如项目支持） | 项目无独立 dark-mode contract，N/A |

测试与验收映射：
| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| send/coalesce race 删除正在发送的 status | await-send-yield asyncio regression | 是 |
| 旧 sent/unacked incarnation 在新 socket 重放 | deterministic two-socket regression | 是 |
| register/heartbeat error 错弹业务队首 | control correlation + waiter/FIFO regression | 是 |
| retry response 丢失后空态残留 alert/notice | Vitest + production browser截图 | 是（截图为交付证据） |

Prototype / Reference Contract：
| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `prototype.html#channel-deleting` | must-match：失败可重试且等待状态只随 removal receipt 存在 | production failed retry → automatic receipt disappearance | worker |
| `prototype.html#channels-empty` | must-match：收敛后为空态且无旧 alert/notice | 1440×1000 durable screenshot + console/network report | worker |

## Roadpoints

### R1 — Status wire owner 与 coalescing race

- 步骤：把 pending、in-flight、sent/unacked、superseded owner 显式建模；wire send 开始前原子转移 owner，result 按 request correlation 释放。
- 验证：await-send-yield 时新 status 不删除 in-flight；result 只释放同 request，后继不被错位阻塞。
- 状态：DONE。pending queue 与 wire business owner 分离，owner 在 `websocket.send` 前建立并以 `sending/awaiting_result` phase 明确生命周期；correlated result 只消费 owner request。

### R2 — 断线 incarnation supersede 与 control correlation

- 步骤：断线后新 incarnation 退休同 channel 旧 sent/unacked status；register/heartbeat 建立独立 ACK/error 边界，并以 register ack 开启业务 flush。
- 验证：two-socket 只发 current；旧 result no-op；owner mismatch/heartbeat error 对 report/status/message/waiter 零误伤。
- 状态：DONE。新 socket 的 register ack 成为业务 flush 边界；register/heartbeat 进入 control lane 并占有显式 wire owner，错误只终止对应 control frame。断线重排 status 时，pending 中已有同 channel 新 incarnation 即淘汰旧 sent/unacked status，业务 FIFO 和 waiter 保持不变。

### R3 — Removal 自动成功清理旧反馈

- 步骤：把 retry error/waiting notice 与具体 removal resource 关联；polling/stream 更新令 resource 消失时清理对应 state。
- 验证：retry response lost/temporary error 后 query 自动变空，页面仅空态且无 alert/notice；永久 Vitest。
- 状态：DONE。retry 临时错误记录其 removal resource owner；query polling/stream 令该 receipt 消失时 effect 同步清除对应 error 与 offline waiting notice，空态不再残留旧反馈。

### R4 — Targeted browser 与一次性全量门禁

- 步骤：隔离 production runtime 只复验 R4 用户路径，保存 durable screenshot/report；随后一次性运行 full backend/frontend/build/Ruff/test-size/secret/diff/process gates并清理资源。
- 验证：真实浏览器从 removal temporary error/waiting 收敛为空态，无 console render error/failed channel request；所有聚合门禁全绿。
- 状态：TODO。
