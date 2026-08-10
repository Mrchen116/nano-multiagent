# feat-530 M1 tasks

## Test strategy

- 保护的回归风险与可观察 seam: Adapter 归一化 occurrence、Dispatcher 固定 receipt、Gateway model/readable 双投影、group/replay bytes、PA stable timezone 与 Kernel default-on footer policy；分别从 `InboundMessage`、Kernel input parts/provider request、chat-history JSONL、prompt 与 `list_features()` 观察。
- 已有保护与处置: 扩展现有 Web/Feishu parser、Dispatcher、group sender/image、chat-history、prompt、SDK contract 测试；这些测试继续保护原行为，只在同一 seam 增加新断言。新的纯逻辑 owner（冻结 context、exact readable store、PA runtime policy）各自新建最低层测试，不复制现有失败原因。
- 落层/目录/marker: 纯逻辑与 Gateway seam 位于 `tests/unit/`；跨 PA runtime/Kernel prompt 位于 `tests/integration/`；SDK discovery 位于 `tests/contract/`；真实进程/浏览器/LLM 作为一次性验收证据，不加入永久套件。自动化 marker 均为无。
- 文件归属: 扩展既有 owner 文件；新建 `test_human_message_context.py`、`test_readable_input_projection.py`、`test_gateway_readable_projection.py`、`test_pa_time_prompt_policy.py`，理由是它们分别拥有此前不存在的稳定行为边界。
- 可选依赖 importorskip: 无；新增永久测试不依赖可选外部服务。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): worktree Web IM 浏览器旅程、真实 Feishu direct/group/catch-up、Gateway restart 与 provider/transcript/chat-history 对照，结论与 locator 记录到 `progress.md` / `evidence/`，不提交 secret、运行数据库或原始日志。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Web/Feishu 入站解析与 relay | `test_web_relay_adapter_attachments.py`、`test_feishu_client.py`、`test_feishu_history_client.py`、`test_feishu_group_history_catchup.py` | keep + 扩展 | 同一生产 parser seam 增加 source time 断言，原 relay/附件/catch-up 风险仍保留 | focused adapter tests |
| Dispatcher 接受与排队 | `test_inbound_dispatcher.py` | keep + 扩展 | receipt 必须在现有同步 acceptance seam 观察 | focused dispatcher tests |
| group sender、buffer 与附件 parts | `test_gateway_pipeline_sender_prefix.py`、`test_group_context_store.py`、既有 image tests | keep + 扩展 | 同一 Coordinator projection seam 验证 header 顺序、mixed old/new 与 raw metadata | focused Gateway tests |
| 用户可读 chat history | `test_chat_history_hook.py` | keep + 扩展 | 现有持久化 owner 增加 exact provenance/no-match 行为 | focused hook tests |
| PA/Core prompt 与 SDK feature 目录 | `test_personal_assistant_prompt_integration.py`、`test_kernel_list_capability_queries.py`、`test_sdk_kernel_wiring.py` | keep + 扩展 | 从现有 prompt/SDK canonical seam 固定 default-on 与 PA explicit-false | focused integration/contract tests |
| active steer admission | `test_session_run_coordinator_admission.py` | keep + 扩展 | 只验证共用 parts builder 的 envelope，不改变或新增生命周期契约 | focused coordinator tests |

## Roadpoints

- [x] C1: Add failing tests for normalized occurrence/receipt times and immutable PA timezone context.
- [x] C1: Add failing tests for sealed model envelope, group sender ordering, multimodal input, and mixed legacy/new buffer rows.
- [x] C1: Add failing tests for exact readable history projection and rollback.
- [x] C1: Add failing tests for `include_session_created_datetime`, PA runtime/preview policy, and SDK discovery.
- [x] C2: Implement the smallest adapter, Gateway, hook, and Kernel changes that make the tests pass.
- [ ] C3: Run focused and risk-expanded validation; record real Web IM/Feishu evidence.
- [ ] C4: Complete verifier, product reviewer, and code-review gates; correct delta specs and archive the unit.
