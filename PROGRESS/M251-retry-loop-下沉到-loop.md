# PROGRESS — M251 retry 逻辑下沉到 loop

## R1 — 测试（先红）

- Context: registry.py 中 _run_worker 在 while True 循环里重试 runtime.run()，每次重试都重新调用 runtime.run()，导致 user message 被追加多次到 session history。修复需要把 retry 下沉到 loop.py 中仅包裹 generate()。
- Decision: 先写测试文件 tests/unit/test_loop_retry.py（直接测 AgentLoop retry 逻辑）和 tests/unit/test_runtime_retry_no_duplicate_user_message.py（集成测试通过 runtime）。
- Rationale: TDD red-first 确保测试在实现前失败，验证测试本身有效。
- Evidence: TBD
- Rollback: 回退到本 milestone 开始前的 HEAD
- Commits: C1=TBD, C2=TBD, C3=TBD
- Next: R2 实现 loop.py retry

## R2 — 实现 loop.py retry

- Context: 在 AgentLoop.run() 的 while True 循环内，将 generate() 调用包裹进 retry helper，遇到 retryable ModelError 时在原地重试，不退出 while True 循环，不调用任何 session 写操作。
- Decision: 提取私有方法 `_generate_with_retry()` 实现退避重试逻辑；delays=(0.5,1.0,2.0) 循环，每5次 cooldown 30s，max_retries=20 后抛 non-retryable ModelError。
- Rationale: 只包裹 generate() 确保 session history 写操作（在 runtime.run() 中）不受影响；同一 turn 内 tool 调用链路不受影响。
- Evidence: TBD
- Rollback: 回退到 R1 C1
- Commits: C1=（同R1）, C2=TBD, C3=TBD
- Next: R3 清理 registry.py

## R3 — 清理 registry.py

- Context: registry.py 的 while True + ModelError retry 循环在 loop 下沉后成为冗余，需移除以防止双重重试。
- Decision: 将 _run_worker 中的 while True 循环改为单次调用，移除 ModelError retryable 捕获分支，保留 TimeoutError 和通用 Exception 处理。
- Rationale: 单一职责——retry 在 loop 层处理，registry 只负责运行状态管理和失败标记。
- Evidence: TBD
- Rollback: 回退到 R2 C2
- Commits: C1=（同R1）, C2=TBD, C3=TBD
- Next: DONE
