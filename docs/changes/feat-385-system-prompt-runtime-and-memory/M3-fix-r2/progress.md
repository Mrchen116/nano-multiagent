# feat-385-M3 (M3-fix-r2) Progress

## 澄清记录

- 读完上下文确认 P1/B1 范围,无需额外澄清。
- 基线: 1 个与本 milestone 无关的测试已预先失败 (test_run_cli_repl_dedupes_replayed...)。

---

### R1 — P1 C1: preview 内联占位符失败测试

- Context: M2 把 volatile 段末尾堆叠为说明块,用户验收否决。需要改为就地内联占位符。
- Decision: 在 test_prompt_preview_endpoint.py 追加 3 个失败测试,断言 volatile 段就地出现内联占位符、无末尾堆叠块、stable 段字节一致性。同时将旧 test_prompt_preview_excludes_volatile_sections 更新为新的正确行为描述。
- Rationale: 测试先行确认当前行为与期望行为的差距;旧测试名不再准确(volatile 段现在应出现而非被排除)。
- Evidence:
  - Tests: pytest tests/unit/personal_assistant/test_prompt_preview_endpoint.py — 3 新测试 FAILED (Red),符合预期
  - Entry: N/A (C1 阶段)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 14ce28c8
- Commits: C1=14ce28c8

---

### R2 — P1 C2+C3: 实现就地内联 + 删末尾堆叠 + spec.md 修正

- Context: global_routes.py 的 prompt_preview 函数之前把 volatile 段过滤掉,在末尾堆叠说明块。需要改为:对每个 volatile 段用 dataclasses.replace 生成 placeholder 版本(always-enabled,render 返回中文"运行时注入"描述),和 stable 段一起传给 assemble_system_prompt。
- Decision:
  1. 实现 `_make_volatile_placeholder_section()` 内部函数,把 volatile 段替换为内联占位符段。
  2. 删除 M2 的 `volatile_placeholders` / `volatile_note` / 末尾 append 逻辑。
  3. 已知 volatile 段名称可读化映射 (core.memory_block → "agent 的 MEMORY.md 内容", core.user_profile_block → "USER.md 用户画像", pa.communication_context → "当前会话通信上下文")。
  4. 更新 contract 测试 `test_prompt_preview_runtime_parity.py`:改为断言 preview 以 runtime stable-only 输出为前缀,且含内联占位符,无 "---" 分隔符。
  5. 更新 spec.md Req-4 措辞:明确"就地内联"而非"底部堆叠"。
- Rationale: `dataclasses.replace` 复用段的 order/位置,无需额外逻辑;段渲染本身的 `assemble_system_prompt` 保证正确位置;内联占位符与 datetime 占位符风格一致(设计方案的正确范式)。
- Evidence:
  - Tests: pytest tests/unit/test_prompt_preview_endpoint.py (15/15 passed) + tests/contract/test_prompt_preview_runtime_parity.py (1/1 passed)
  - Entry: HTTP GET /v1/prompt-preview 端点返回正确结构,volatile 段内联,无末尾块
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 905c5829 (实现), 508f8a18 (文档)
- Commits: C2=905c5829, C3=508f8a18

---

### R3 — B1 C1: stream_session workspace_root 透传失败测试

- Context: Gateway SSE 消费链路 stream_session 漏传 workspace_root query param。多 agent 场景下内核无法定位 session JSONL,返回 session_not_found 404。
- Decision: 在 3 个测试文件各追加失败测试:
  1. test_kernel_api_client.py: async transport mock 断言请求 URL 含 workspace_root query param。
  2. test_background_session_events_r6.py: 断言 BackgroundSessionEventSubscriber(workspace_root=X) 把 workspace_root 透传给 stream_session。
  3. test_inbound_pipeline_sse.py: 端到端测试断言 pipeline handle_inbound 时 stream_session 收到 agent workspace_root。
- Rationale: 三层测试覆盖三处需要修改的代码点,确保每层改动都有独立验证。
- Evidence:
  - Tests: 4 个新测试 FAILED (Red),符合预期
  - Entry: N/A (C1 阶段)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert 8f74c957
- Commits: C1=8f74c957

---

### R4 — B1 C2+C3: 实现 3 文件 5 处改动

- Context: 需要在三个文件里加 workspace_root 参数并透传。
- Decision:
  1. `kernel_api_client.py::stream_session`: 加 `workspace_root: str | None = None` 参数,非 None 时构造 `params` dict 并传给 httpx client.stream()。
  2. `inbound_pipeline.py::_await_terminal_run_async`: 加 `workspace_root` 参数,透传给 stream_session。其调用处加 `workspace_root=agent_workspace_root`。
  3. `inbound_pipeline.py::_ensure_background_subscriber`: 加 `workspace_root` 参数,透传给 BackgroundSessionEventSubscriber。其调用处加 `workspace_root=agent_workspace_root`。
  4. `background_session_events.py::BackgroundSessionEventSubscriber.__init__`: 加 `workspace_root` 参数存为 `self._workspace_root`。`_run_loop` 中 stream_session 调用加 `workspace_root=self._workspace_root`。
  5. 更新所有 fake/stub stream_session 签名(接受 workspace_root 参数)以兼容改动。
- Rationale: 改法与同文件其他参数(get_session、submit_message 等)的 workspace_root 处理模式完全一致;只有非 None 时才放入 params dict,避免发送不必要的参数。
- Evidence:
  - Tests: pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e" — 2202 passed, 22 skipped, 3 xfailed (基线那个原本失败的测试也得到修复)
  - Entry: stream_session 的 HTTP 请求 URL 含 workspace_root query param (asyncio transport mock 断言)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: test_inbound_pipeline_stream_session_receives_workspace_root 覆盖端到端透传路径
  - Visual/Interaction: N/A
- Rollback: git revert a7a3d0b2
- Commits: C2+C3=a7a3d0b2
- Next: 本 milestone M3-fix-r2 全部 roadpoint DONE,准备合并到 unit/feat-385。
