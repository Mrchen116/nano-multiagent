# M116 Gateway 回复文本回填与真实浏览器链路收口

## 启动记录
- 已阅读：`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M116/src/personal_assistant/gateway/inbound_pipeline.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M104/src/personal_assistant/gateway/inbound_pipeline.py`、相关 gateway/IM/unit/integration/acceptance/e2e 测试与 `main.py`/`kernel_api_client.py`。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M116，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M116`，branch=`milestone/M116`。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_m103_gateway_im_integration.py tests/im_service/integration/test_m103_im_gateway_e2e.py tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_kernel_api_client.py -q 2>&1 | tail -120`
- 基线结果：`31 passed, 14 warnings`。
- prevention / 注意事项：
  - 只固化这次最终验收发现的真实缺口，不扩散为无关重构。
  - 成功标准必须回到真实入口：UI 可见非空 agent 气泡 + `completed`。
  - 优先保证单一主链路：执行期聚合文本，终态只负责收口状态，不新增终态后二次内容回放分支。
  - 流式与最终摘要必须补缺不重放，避免文本重复或串 run。

### R1 Gateway 回复文本聚合与 IM/UI 回填收口
- Context: 最新 main 的 `InboundPipeline` 只读 `get_run().output_text`，缺少对 kernel session SSE `text_delta` 的聚合；同时 runtime 未把 relay 生命周期自动回填到 IM，导致真实浏览器链路里 agent 气泡可能为空、completed 只剩状态收口而没有文本。范围仅限 gateway/IM/UI 直接相关接线，不改 ROADMAP 与 dev-tasks 运行态文件。
- Decision: 迁移旧 M104 已验证的最小主链路：在 `InboundPipeline` 内按当前 `run_id` 轮询 `stream_session_events()` 聚合 `text_delta`，终态用 `output_text > streamed_text > error` 顺序取最终 reply；在 `build_runtime()` 中注入 relay lifecycle callback，把 accepted/running/completed/failed 映射为 IM 的 receipt/report 帧，并补齐 `UpstreamReporter.send_report()` 所需的 `conversation_id/message_id` 字段。
- Rationale: 文本聚合必须发生在执行期主链路，才能同时驱动 outbound reply、running summary 与 completed detail；若只在终态补拉或在 UI/IM 层额外兜底，会重新引入双路径回放与重复文本风险。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M116 && python -m pytest tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_m103_gateway_im_integration.py tests/im_service/integration/test_m103_im_gateway_e2e.py tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_kernel_api_client.py -q 2>&1 | tail -120` → `34 passed, 14 warnings`。
  - Entry: `tests/acceptance/test_im_gateway_real_acceptance.py` 继续断言 `relay.completed.detail == "assistant:hello from web im"`、`message.delivered.progress_state == "completed"`；`tests/e2e/test_m112_real_process_roundtrip_e2e.py` 保持真实进程 roundtrip 全绿。
- Rollback: 29f906f
- Commits: C1=29f906f, C2=7971767, C3=3285b93（补记提交：77064c2）
- Next: 全部 Roadpoint 已完成，等待主 agent 验收/后续集成。
