# bugfix-402-M1: transcript-integrity — Tasks

> 对齐: ../design.md v1

## 目标

保证 JSONL session 中每个 assistant tool_call 在再次发送给模型前都有对应结果；
中断/取消/关闭时写入取消终态；普通 load 不写文件；并发 prepare 幂等。

## 退出标准

- [ ] 只读 `load()` 不写文件（无副作用）
- [ ] `prepare_transcript_for_run()` 在 per-session 路径锁内完成 flush/replay/check/append/flush
- [ ] recovery entry 带确定性 idempotency key，重复 prepare 只产生一个逻辑结果
- [ ] runtime run 前调用 prepare，`build_chat_messages` 只接受合法消息序列
- [ ] 中断/取消/shutdown 写 `tool_call_recovery` 终态 entry（reason = interrupted/cancelled/shutdown）
- [ ] Anthropic/OpenAI mapper 均收到合法顺序 transcript（multi-call、partial-result、post-compaction 都覆盖）
- [ ] 所有指定测试文件全绿

## 测试策略

被测行为：
1. prepare_transcript_for_run: 检测未闭合 tool_call，写确定性 recovery entry；幂等；锁保护
2. load: 普通只读，不写文件
3. runtime._run: run 前 prepare 调用，build_chat_messages 只见合法 transcript
4. interrupt/cancel/shutdown: 写 tool_call_recovery 终态
5. mapper 层：含 recovery entry 的 transcript 能通过 Anthropic/OpenAI 映射而不报错

已有测试在：
- `tests/unit/test_session_manager.py`（扩展，加 prepare + recovery 单元测试）
- `tests/unit/test_session_persistence_fidelity.py`（扩展，加 orphaned tool_call -> recovery）
- `tests/unit/test_agent_prompting.py`（扩展，加含 synthetic tool result 的 build_chat_messages 测试）
- `tests/integration/test_session_store_persistence_integration.py`（扩展，加 prepare 跨进程幂等）

新建：
- `tests/unit/test_session_service.py`（已有，扩展 prepare_transcript_for_run 路径）

落层：tests/unit/ 和 tests/integration/，无 e2e marker

可选依赖 importorskip：无

一次性验收证据：无

前端 UI：N/A

## Roadpoints

### R1 — tool_call_recovery entry schema + JsonlSessionStore.prepare_transcript_for_run

- 状态: TODO
- 步骤:
  1. C1: 在 test_session_manager.py 新增 TestPrepareTranscript 测试类（红）：
     - 未闭合 tool_call → prepare 写 recovery entry，再次 load 时 build_chat_messages 合法
     - 多个 tool_call 部分已有结果 → 只补缺失
     - 幂等：prepare 两次不产生重复 recovery entry
     - 只读 load 不写文件
  2. C2: 在 jsonl_store.py 新增 `prepare_transcript_for_run(session_id, ...)` 方法：
     - 取文件锁（threading.Lock per path，session 级）
     - flush writer
     - 读取 raw lines，build pending tool_call map，检查哪些没有 result/recovery
     - 批量 append recovery entries（确定性 id = `tool-call-recovery:<tool_call_id>`）
     - flush writer
     - 释放锁
  3. C3: 更新 tasks.md + progress.md
- 验证: pytest tests/unit/test_session_manager.py -xvs 全绿

### R2 — SessionService/SessionManager 暴露 prepare_transcript_for_run

- 状态: TODO
- 步骤:
  1. C1: 在 test_session_service.py 新增测试（红）：service.prepare_transcript_for_run() 透传 + 幂等
  2. C2: SessionManager + SessionService 增加 prepare_transcript_for_run 方法，委托 store
  3. C3: 更新 docs
- 验证: pytest tests/unit/test_session_service.py -xvs

### R3 — runtime._run 调用 prepare_transcript_for_run（run 前准备）

- 状态: TODO
- 步骤:
  1. C1: 在 test_session_persistence_fidelity.py 新增 TestOrphanedToolCallRecovery：
     - session JSONL 中含悬空 tool_call，run 前 prepare 修复后 build_chat_messages 合法
  2. C2: 修改 runtime.py `_run_impl` 在 load/cache hit 后、构建 user_msg 前调用 prepare
  3. C3: 更新 docs
- 验证: pytest tests/unit/test_session_persistence_fidelity.py tests/unit/test_agent_prompting.py -xvs

### R4 — 中断/取消/shutdown 写 tool_call_recovery 终态

- 状态: TODO
- 步骤:
  1. C1: 在 test_session_manager.py 增加 TestInterruptCancelRecovery：
     - interrupt/cancel/shutdown 调用 recovery writer，load 后 build_chat_messages 合法
  2. C2: 在 runtime.py 的中断/取消/shutdown 路径调用 store append recovery entry
  3. C3: 更新 docs
- 验证: pytest tests/unit/test_session_manager.py -xvs

### R5 — 集成：prepare + load 全流程 + mapper 合法性

- 状态: TODO
- 步骤:
  1. C1: 扩展 test_session_store_persistence_integration.py：含悬空 tool_call 的 session，两次
     prepare 后再 load，transcript 合法（仅一套 recovery entry）
  2. C2: 如有 mapper contract 测试，加含 recovery 的消息序列覆盖
  3. C3: 更新 docs + progress.md
- 验证: pytest tests/unit/ tests/integration/ -x -q 全绿
