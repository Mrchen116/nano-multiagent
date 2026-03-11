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
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 待补。
  - Entry: 待补。
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 先补红测，锁定 SSE 聚合 + run fallback + relay 回填缺口。
