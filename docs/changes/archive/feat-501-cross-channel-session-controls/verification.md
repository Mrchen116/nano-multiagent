# feat-501 verification

> 独立 verifier 核验；2026-08-05。

## Verdict

通过。实现与 `spec.md`、`design.md` 的关键用户契约一致，可以进入交付收尾。

## 已核验的实现契约

- 内部 IM 与外部 channel 共用 `/new`、`/compact`、`/compact <focus>` 解析和群聊显式指向门控；稳定 operation identity 防止同一 relay/provider 事件重复切换或重复压缩。
- `/new` 在发布新 binding 前 quiesce 旧 run 的可见输出；发布失败恢复旧输出，成功后抑制旧 stream、final reply 与 external mirror。
- 外部控制结果与 `PendingExternalControlDelivery` 同次持久化；当前请求、cached external channel ready 后的 Gateway 启动，以及 IM reconnect 都会 drain。失败的外部 `/new` 同样写入可恢复 outcome/intent。
- 手动 `Kernel.compact` 将 focus 透传给 strict summary；空摘要、summary 错误或持久化失败均不改变可恢复上下文；同一 idempotency key 在 Kernel 重启后返回首次结果。
- `/compact` 是 per-session FIFO barrier：运行中的 Agent 不被打断，命令在已有 work 后执行，其后到达的普通输入不会被 steer 到压缩之前；外部 shadow 同步前已占住该 FIFO 位；`/new` 将旧 generation 的排队压缩持久标为 `superseded`，重放不影响新会话。
- compaction boundary 与 summary/reinjection 通过同目录 atomic replacement batch 一次可见。实际 `os.replace` 失败回归确认 JSONL 字节不变；成功后 transcript tail 才推进，后续公开 append 在重启后仍从摘要继续。
- `design.md` 的 external control materialization 描述已与真实接口一致：`ExternalControlDeliveryMaterializer.prepare_agent_output(run_id="control:" + operation_id, output_kind="final")`。

## 实际验证证据

```text
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/agent/test_kernel_manual_compact.py \
  tests/unit/agent/session/test_jsonl_transcript.py \
  tests/unit/test_loop_compact.py \
  tests/integration/test_conversation_compaction_integration.py \
  tests/contract/test_compaction_contract.py \
  tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py \
  tests/unit/personal_assistant/test_external_control_delivery.py \
  tests/unit/personal_assistant/test_session_run_coordinator_admission.py \
  tests/unit/personal_assistant/test_run_visibility_lease.py \
  tests/unit/personal_assistant/test_gateway_stop_command.py \
  tests/unit/personal_assistant/test_gateway_web_relay_adapter.py \
  tests/unit/personal_assistant/test_gateway_relay_lifecycle.py \
  tests/unit/personal_assistant/test_connection_ready_shadow_recovery.py

127 passed, 2 third-party deprecation warnings
```

```text
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check [all changed Python production files]
All checks passed!

git diff --check
passed
```

## 验收边界

本次验证覆盖可复现的 unit、integration、contract 和 Gateway 生命周期 seam，不替代真实飞书账号、provider 回调与内部 IM 部署环境中的端到端验收。特别是 provider 已接收发送后进程退出的 at-least-once 重投，以及飞书群真实 mention 的呈现，应在具备有效飞书凭据和 IM 服务的环境中按 `design.md` 验收计划执行。

## Rebase revalidation

`unit/feat-501` 已在 `9c50b8a5f` 上重放；唯一的冲突收束是把 `run_reset_discard`、quiesce 和 suppress 分支适配为重构后 observer 的 `_PreparedEvent` typed contract。独立 verifier 复核了 relay lifecycle、visibility lease、coordinator admission/terminal、task tracker、shadow sync 和 Gateway lifecycle 相邻回归：`101 passed`；受影响 Python 文件 Ruff 与 `git diff --check` 均通过。该复核对应行为提交 `13ba17f42`，未发现需要实现修复的问题。
