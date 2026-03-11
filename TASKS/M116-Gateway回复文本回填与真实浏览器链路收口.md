# M116 Gateway 回复文本回填与真实浏览器链路收口

## 目标
修复 Gateway 在真实浏览器链路下没有把 kernel SSE / run 输出中的 agent 回复文本正确聚合并回填到 IM/UI 的缺口，确保 UI 能看到非空 agent 气泡与 completed 状态。

## Exit Criteria
1. Gateway 可从 kernel session SSE `text_delta` 聚合 assistant 文本。
2. 当 `stream_session_events` 不可用或未返回有效文本时，Gateway 会正确回退到 `get_run().output_text`。
3. relay/IM 链路会把聚合后的非空回复文本回填到会话事件与送达回执。
4. 真实浏览器聊天可见非空 agent 气泡与 `completed` 状态。
5. 派发包指定的 gateway/IM/integration/e2e 测试全绿。

## Roadpoints

### R1 Gateway 回复文本聚合与 IM/UI 回填收口
- **Acceptance**:
  1. `InboundPipeline` 在 run 快照缺少 `output_text` 时，可从 session SSE 的 `text_delta` 仅按当前 `run_id` 聚合 assistant 文本。
  2. SSE 缺失、不可用或未提供有效文本时，仍以 `get_run().output_text` 作为最终回退，不影响既有 direct/local channel 行为。
  3. web relay 链路会把聚合后的回复文本同时用于 outbound message、running report summary 与 completed delivery detail。
  4. runtime 仅在 IM 连接已建立时发送 relay lifecycle 回执；不引入第二条内容回放路径。
  5. 真实入口测试继续证明 UI 侧能看到非空 agent 气泡与 `completed`。
- **Tests Plan**:
  - unit: 需要；覆盖 SSE 文本聚合、去重、run fallback、relay lifecycle callback 接线。
  - contract: 不单独新增；当前 kernel client / IM payload 契约已有测试覆盖，本次只补真实缺口的行为回归。
  - integration: 需要；覆盖 browserless IM ↔ gateway roundtrip 中回复文本与 relay 状态回填。
  - e2e: 需要；保留真实 acceptance / real-process roundtrip 证明真实入口仍满足“非空 agent 气泡 + completed”。
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/unit/personal_assistant/test_kernel_api_client.py`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `tests/acceptance/test_im_gateway_real_acceptance.py`
  - `tests/e2e/test_m112_real_process_roundtrip_e2e.py`
- **DoD**: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_m103_gateway_im_integration.py tests/im_service/integration/test_m103_im_gateway_e2e.py tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_kernel_api_client.py -q 2>&1 | tail -120` 全绿 + 形成可追溯的 C1/C2/C3 提交 + PROGRESS 记录决策/证据/哈希。
- **Status**: TODO
