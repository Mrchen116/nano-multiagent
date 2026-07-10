# feat-447-M3 — Progress

## R1 — feishu_client 错误分类与重试

- Context: M1 的 send_message 对所有 API 错误统一抛 ValueError，无法区分 rate limit / auth / server 错误，也无法自动重试瞬态故障。
- Decision: 定义 FeishuAPIError（基类）和 FeishuAuthError（子类），send_message 根据 response.code 分类处理：429 指数退避重试最多 3 次、401/403 抛 FeishuAuthError、5xx 重试一次、其他抛 FeishuAPIError。
- Rationale: 飞书 API 有明确的错误码体系，分类处理能减少瞬态故障的影响，auth 错误需要上层特殊处理（通知用户重新授权）。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_client.py` — 17 passed（含 7 个新增错误分类测试）
  - Entry: N/A（纯内部逻辑，不涉及用户入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（单测覆盖完整分类逻辑，mock time.sleep 验证退避）
  - Visual/Interaction: N/A
- Rollback: `git revert 97f16eeb`（C2 实现提交）
- Commits: C1=edb6e4a0, C2=97f16eeb, C3=<本次>

## R2 — feishu_adapter 错误通知

- Context: adapter.send() 直接透传 feishu_client 的异常，没有日志上下文，运维无法从日志定位是哪个 bot / 哪个 chat 出错。
- Decision: send() 方法 catch FeishuAuthError 和 FeishuAPIError，记录结构化日志（extra 含 error_code, chat_id, agent_id, adapter），然后 re-raise。
- Rationale: adapter 是运维可观测性的关键节点，结构化日志能让日志聚合系统按 error_code 聚合告警。adapter 不吞异常——上层（OutboundRouter / InboundPipeline）负责通知用户。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_adapter.py` — 14 passed（含 2 个新增错误通知测试）
  - Entry: N/A（纯内部逻辑）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert 97f16eeb`（与 R1 同一个 C2 提交）
- Commits: C1=edb6e4a0, C2=97f16eeb, C3=<本次>

## R3 — 单元测试

- Context: 需要验证错误分类、重试逻辑、adapter 异常处理的正确性。
- Decision: 在现有测试文件中扩展（TESTING_GUIDE §2 先定位再新建），新增 9 个测试函数覆盖所有新增行为。使用 `@patch("time.sleep")` mock 时间推进验证退避逻辑。
- Rationale: 复用现有 test helper（`_make_started_client`, `_mock_response`），不新建测试文件。
- Evidence:
  - Tests: `pytest tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py` — 30 passed; 全量 feishu 测试 — 45 passed
  - Entry: N/A（后端单元测试，不涉及真实入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（纯 mock 单测，不需要 e2e）
  - Visual/Interaction: N/A
- Rollback: `git revert edb6e4a0`（C1 红测提交）
- Commits: C1=edb6e4a0, C2=97f16eeb, C3=<本次>
