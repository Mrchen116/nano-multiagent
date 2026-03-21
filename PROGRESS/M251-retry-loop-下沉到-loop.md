# PROGRESS — M251 retry 逻辑下沉到 loop

## R1 — 测试（先红）

- Context: registry.py 中 _run_worker 在 while True 循环里重试 runtime.run()，每次重试都重新调用 runtime.run()，导致 user message 被追加多次到 session history。修复需要把 retry 下沉到 loop.py 中仅包裹 generate()。
- Decision: 先写测试文件 tests/unit/test_loop_retry.py（直接测 AgentLoop retry 逻辑）和 tests/unit/test_runtime_retry_no_duplicate_user_message.py（集成测试通过 runtime）。monkeypatch _loop_sleep 避免实际等待。
- Rationale: TDD red-first 确保测试在实现前失败，验证测试本身有效。
- Evidence:
  - Tests: 5 loop 单测 + 1 runtime 集成测试先红后绿
  - Entry: test_loop_retries_generate_on_retryable_error_and_succeeds，test_runtime_run_retryable_model_error_user_message_appears_once
- Rollback: 回退到 d50da7b（本 milestone 开始前 HEAD）
- Commits: C1=e6ab4f3
- Next: R2 实现 loop.py retry

## R2 — 实现 loop.py retry

- Context: 在 AgentLoop.run() 的 while True 循环内，将 generate() 调用包裹进 retry helper，遇到 retryable ModelError 时在原地重试，不退出 while True 循环，不调用任何 session 写操作。
- Decision: 提取私有方法 `_generate_with_retry()` 实现退避重试逻辑；delays=(0.5,1.0,2.0) 循环，每5次 cooldown 30s，max_retries=20 后抛 non-retryable ModelError。模块级 `_loop_sleep()` 函数可被 monkeypatch。
- Rationale: 只包裹 generate() 确保 session history 写操作（在 runtime.run() 中）不受影响；同一 turn 内 tool 调用链路不受影响。
- Evidence:
  - Tests: 646 passed，包含 6 新 loop 测试 + 1 集成测试
  - Entry: user message 在 fail_count=3 时仍只出现 1 次
- Rollback: 回退到 e6ab4f3（R1 C1）
- Commits: C2=ddde425
- Next: R3 清理 registry.py（合并在同一 commit）

## R3 — 清理 registry.py

- Context: registry.py 的 while True + ModelError retry 循环在 loop 下沉后成为冗余，需移除以防止双重重试。相关测试（test_runs_registry_retries_retryable_model_errors...、test_cancel_stops_retry_loop...）也需同步更新。
- Decision: 将 _run_worker 中的 while True 循环改为单次调用，移除 ModelError retryable 捕获分支，保留 TimeoutError 和通用 Exception 处理。删除无用的 _sleep/_wait_with_cancel/_summarize_retry_error/_truncate_error_message/_sleep_until_retry。更新测试：retryable ModelError 从 runtime.run() 抛出时 registry 标记 failed。
- Rationale: 单一职责——retry 在 loop 层处理，registry 只负责运行状态管理和失败标记。
- Evidence:
  - Tests: 646 passed（全绿）
  - Entry: retryable ModelError 从 runtime 抛出 -> run 标记 FAILED，无 retry 条目
- Rollback: 回退到 e6ab4f3（R1 C1）
- Commits: C2=ddde425（与R2合并）
- Next: DONE
