# refactor-521-M1: typed ingress cutover — Tasks

> 对齐: ../design.md v1

## 目标

把 WebRelay、Feishu 与 recovery producer 一次规范化为 `InboundMessage.ingress`，Gateway 内部只携带 `RoutedInbound(message, shadow)`，并在不改变 Web IM、外部 channel、shadow、静默和重放行为的前提下删除 hidden runtime metadata 与 derived fallback。

## 退出标准

- [x] callback 只交付 `InboundMessage(ingress=InboundIngress(...))`；producer/absence matrix 与非法组合被长期测试保护。
- [x] Gateway 后续只传 `RoutedInbound(message, shadow)`；shadow empty/pending/anchored 三态与非法 ref-without-saga 被保护。
- [x] native relay 与 external shadow 分型投影到 run delivery target，且 typed facts/saga 各只有一个 authority。
- [x] 删除 `InboundEnvelope`、`RuntimeProtocolFacts`、top-level event identity、旧 shadow ref saga/relay 字段、私有 metadata key 与 fallback derive。
- [x] 四处 ingress `web_relay` 业务代理改读 typed facts；outbound/managed identity 残留逐项核为合法。
- [x] typed containers 不进入 reply/session/DB/public metadata。
- [x] 聚焦 Gateway/Feishu/shadow/delivery、contract、non-E2E、Ruff check/format-check 全绿；隔离真栈 Web IM 与专用 Feishu 入口验收完成。

## 测试策略

- 保护的回归风险与可观察 seam: adapter callback 交付完整 typed ingress；pipeline 对 native Web/external shadow/Feishu 的门控和 shadow 结果；run delivery 对 provisional/empty/external target 的行为；回复/SQLite/public metadata 无 typed carrier 泄漏；真 Gateway/IM 与真 Feishu 仍只产生既有可见结果。
- 已有保护与处置: 扩展/改写 WebRelay、Feishu、pipeline、shadow sync、relay lifecycle、runtime delivery 与 persistence 现有文件；不按 milestone 新建平行 unit 文件。新增 contract 文件仅在现有 unit 文件不能承担 cross-module carrier invariants 时使用。
- 落层/目录/marker: `tests/unit/personal_assistant/`（producer/state/projection 最低暴露层）、`tests/contract/`（唯一 authority/deletion 边界）、`tests/e2e/critical_paths/` 与隔离真栈（真实进程/外部入口，marker: e2e）。
- 可选依赖 importorskip: 无新增。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 隔离 Web IM/Feishu 运行日志只保留本机定位信息；可审查摘要写 progress，不提交 secret/runtime DB。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| WebRelay callback/dedup/attachment | `test_gateway_web_relay_adapter.py`、`test_web_relay_adapter_attachments.py` | rewrite-merge | 删除 return-only wrapper 断言，保留 callback、typed facts、dedup 与 attachment 行为 | 聚焦 pytest |
| Feishu provider identity | `test_gateway_im_relay.py`、Feishu adapter 相关测试 | rewrite-merge | top-level event identity 改为 ingress producer contract，provider frame 行为不变 | 聚焦 pytest |
| shadow durable identity/recovery | `test_gateway_shadow_sync.py`、`test_inbound_shadow_identity_guard.py` | rewrite-merge | 将 hidden protocol setup 改为 `InboundIngress`/`RoutedInbound`，保留真实 durable saga/IM HTTP outcome | 聚焦 pytest |
| pipeline group/control/session behavior | `test_inbound_pipeline_session.py` 及 coordinator admission/terminal tests | rewrite-merge | request carrier 改型但场景结果不变；合并旧 metadata-derived assertions | 聚焦 pytest |
| relay lifecycle/run delivery | `test_gateway_relay_lifecycle.py`、`test_runtime_delivery_stream.py`、`tests/helpers/runtime_delivery.py` | rewrite-merge | 以分型 target/visibility/terminal outcome 替换 `RuntimeProtocolFacts` setup | 聚焦 pytest |
| private metadata strip | `test_persistent_session_binding_store.py::test_bind_strips_existing_private_runtime_protocol_metadata` | delete | 私有 key 与 attachment helper退役后风险不再存在；由 typed carrier 不落 metadata contract 替代 | contract + persistence tests |
| Web direct/group/replay 真入口 | 现有 critical paths 与 reviewer runbook | keep | 真进程行为风险不同于 unit projection | isolated e2e |

前端 UI：N/A；本 milestone 不改 Web 前端或视觉 reference。

## Roadpoints

### R1 — 建立 typed carrier 与 producer matrix

- 状态: DONE
- 步骤: 先写 carrier validation/WebRelay/Feishu producer 红测；在 channels 层新增不可变 carrier，迁移 adapter callback，删除 return-only envelope。
- 验证: producer/absence/invalid-combination 聚焦 tests 红转绿，adapter dedup/attachment suites 通过。

### R2 — 切换 RoutedInbound 与 shadow/session owners

- 状态: DONE
- 步骤: 先写 shadow 三态、pipeline native/external 分型与 recovery 红测；迁移 pipeline、request/lifecycle carrier、session/coordinator/shadow persistence consumers。
- 验证: pipeline/shadow/control/coordinator/persistence 聚焦 suites 红转绿；typed facts/saga 不回写 metadata。

### R3 — 投影 runtime delivery 并删除 legacy authority

- 状态: DONE
- 步骤: 先写 IMRelayTarget/ExternalShadowTarget 与 visibility/empty terminal 红测；迁移 lifecycle/context/observer/background，删除 runtime protocol helpers和失效测试，完成 residual 分类。
- 验证: delivery/contract/全量 non-E2E/Ruff 全绿；隔离 Web IM direct/group/replay 与专用 Feishu/shadow 真入口通过并清理资源。
