# bugfix-471-M1: session continuity — Tasks

> 对齐: ../design.md

## 目标

在不更换 Kernel session 或 transcript 的前提下，让既有直聊、群聊与外部渠道会话在下一新 run 原子采用最新完整运行配置，并继续理解此前历史。

## 退出标准

- [x] 同一绑定在 model、prompt、skills、tools、features 变化后保留 session id 与 transcript，下一 run 使用完整最终配置。
- [x] active run 与其 steer 保持原配置；排队新 run 在 admission 时只采用 catalog 最新配置。
- [x] Gateway 重启后从 binding applied state 与 transcript 恢复正确 baseline；错误时不提交 run。
- [x] heartbeat 复用会话、cron 新建会话均采用完整 runtime，且不进入聊天边界语义。
- [x] `pytest -m "not e2e"` 与相关 contract 测试全绿；完成真实 Gateway/Web IM 入口验证。

## 测试策略

- 被测行为（来自退出标准）：完整 runtime 的 canonical identity、持久 replacement/幂等/恢复/写失败与 turn 串行；Gateway admission 先 reconfigure 再 submit、legacy/schema baseline、失败不 submit、active steer 冻结；heartbeat/cron 的完整 runtime 装配。
- 已有测试在：`tests/unit/agent/session/test_conversation_session.py`、`tests/unit/agent/session/test_jsonl_transcript.py`、`tests/unit/personal_assistant/test_session_run_coordinator_admission.py`、`tests/unit/personal_assistant/test_gateway_session_binder.py`、`tests/unit/personal_assistant/test_persistent_session_binding_store.py`、`tests/unit/personal_assistant/test_heartbeat_session_binding.py`、`tests/unit/personal_assistant/test_cron_admission_linearization.py`（扩展）；`tests/integration/test_session_run_coordinator_real_kernel.py`（扩展）。
- 落层/目录/marker：`tests/unit/` 与 `tests/integration/`，marker：无；真栈验证作为 `tests/e2e/` 已有关键路径的手工执行证据。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree 隔离 IM + Gateway 的配置更新、重启、直聊/群聊/Feishu 路径日志与 LLM proxy 请求对账。

## Roadpoints

### R1 — Kernel runtime replacement

- 状态：DONE
- 步骤：定义 SDK runtime DTO/identity；把完整 raw runtime 写入 creation/config_update transcript；在 ConversationSession turn gate 内实现 durable replacement 与 inspection；让 submit 只接受 session runtime model。
- 验证：扩展 Kernel/session 单元与集成测试，覆盖 identity、幂等、并发、恢复、写失败和能力替换。

### R2 — Gateway admission continuity

- 状态：DONE
- 步骤：用统一 runtime projection 创建/重配；binding SQLite 持久 applied identity；配置发布不再删除绑定；在 SessionRunCoordinator admission 内按 latest snapshot inspect/reconfigure/持久 applied state 后 submit。
- 验证：扩展 binder/store/coordinator 测试，覆盖 ordering、active steer、连续保存、legacy/schema baseline、inspection/reconfigure 失败与 restart。

### R3 — Background parity and live verification

- 状态：DONE
- 步骤：使 heartbeat 复用会话与 cron 新建会话采用完整 runtime，补回归与真栈验证；`gateway/kernel_client.py` 是 scheduler 进入 in-process Kernel 的必要 adapter seam，`product.py` 是 system_prompt 进入完整 runtime 的唯一 projection seam，均按 orchestrator 确认纳入本 roadpoint，不修改 `design.md`。
- 验证：相关 scheduler 测试、`pytest -m "not e2e"`、真 Gateway restart 的 direct/group/Feishu 请求对账。
- 证据：Web IM direct/group/restart 与 LLM 请求对账已完成；显式 `{}` features 有 Gateway admission 回归和隔离真栈的用户可见回复、restart、transcript 持久化证据（`evidence/live-empty-features-runtime.json`）。真实 Feishu 测试群在 M1 分支 Gateway 的单一 app 连接上完成配置边界与 restart：同一 `kernel_session_id` 在 phase one、phase two 与 restart 后保持不变，用户可见回复依次为 `ACK-FEISHU-4A7D`、`CONFIRMED-FEISHU-4A7D`、`RESTARTED-FEISHU-4A7D`；proxy 请求对账确认 model、system prompt、tools 与历史均正确，详见 `evidence/live-feishu.json`。
