# M106 — IM↔Gateway 真实端到端交互验收

## 0. 前置说明
- 本里程碑开工前已阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/NodeGateway-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 工作目录限定在：`/Users/czj/Repos/nano-multiagent/.worktrees/M106`。
- 按要求先执行真实基线，再开始补测试与实现。

## 1. 基线
- 基线命令：
  - `PYTHONPATH=src pytest -q tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant/test_gateway_pipeline.py`
- 基线结果：8 passed。
- 基线补充：用真实 HTTP 进程 + IM TestClient WebSocket 跑通了一次原型化链路，确认当前仓库已经具备“IM relay.message 下推 + Gateway pipeline 回发 + delivery_receipt 回执”的核心碎片，但还缺少规范化的真实端到端测试资产、Gateway 上游连接实现、以及从商业产品视角的交互审视文档。

## 2. 当前发现
- IM 侧已有：`GatewayHandler`、`RelayService`、`/im/ws/gateway`、消息中继与回执 ack。
- Gateway 侧已有：`InboundPipeline`、`SessionRunQueue`、`OutboundRouter`、`KernelApiClient`、配置加载与最小启动骨架。
- 关键缺口：
  1. `src/personal_assistant/` 还没有 `ws/im_connection.py`、`channels/web_relay_adapter.py`、`reporter/upstream_reporter.py`，真实 IM↔Gateway 长连接尚未在 Gateway 侧落地。
  2. 现有 IM SSE 只反映消息持久化事件，没有把 Gateway 的 receipt/report 映射成更贴近商业 IM 的过程状态流。
  3. 缺少 M106 专属 TASKS/PROGRESS、验收脚本、交互审视记录。

## 3. Roadpoint 记录

### R1 真实验收资产
- Context:
  - M103 已完成，但仓库内缺少 M106 专属的“真实 IM HTTP + Gateway WS + Gateway pipeline”验收资产。
  - 范围限定在 M106，不扩展到 M104 全系统总验收，也不新增尚未要求的正式生产组件。
- Decision:
  - 新增 `tests/acceptance/test_im_gateway_real_acceptance.py`，用真实 IM app/TestClient `/im/ws/gateway` WebSocket + 现有 `InboundPipeline` 组合出 acceptance harness。
  - 新增 `scripts/acceptance/run_m106_acceptance.py` 作为单入口验收脚本。
- Rationale:
  - 当前仓库已有 IM websocket handler 与 Gateway pipeline 核心能力；M106 更需要把这些碎片串成“可复跑、可证据化”的真实链路，而不是继续扩写基础设施。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py`
  - Entry: 验收测试覆盖 bind start/confirm、node.register、node.heartbeat、relay.message、Gateway pipeline reply、node.delivery_receipt(sent/completed)、node.report。
  - Entry: `python scripts/acceptance/run_m106_acceptance.py` 可作为人工/CI 复验脚本。
- Rollback:
  - 可回退到本里程碑计划提交前的稳定点；该 Roadpoint 主要新增测试资产与脚本，无侵入式运行时代码改动。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 结合真实链路结果输出产品交互批判记录，并在 TASKS/PROGRESS 固化问题清单。

### R2 产品交互批判
- Context:
  - LOGBOOK 已要求持续做“真实端到端联调 + 商业产品视角批判”，覆盖绑定、会话建立、消息发送、回执、异常反馈、状态提示。
  - 当前仓库协议层能力基本存在，但用户可见状态链路仍不完整。
- Decision:
  - 新增 `PROGRESS/M106-产品交互批判记录.md`，明确真实链路已具备的能力、产品层缺口、问题清单与后续改进建议。
- Rationale:
  - 将“技术链路可跑”与“产品体验是否成熟”显式分离，避免把协议完成误判为产品已完成。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py`
  - Entry: 批判记录明确指出 SSE 仍缺少 `relay.sent/relay.completed` 等用户可见状态事件，`message.delivered` 语义与真实处理进度存在错位。
- Rollback:
  - 若需重写批判结论，可保留 acceptance 资产不动，仅回退文档提交。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 运行全量相关测试、整理最终证据、提交 milestone/M106 分支。

## 4. 当前结论
1. M106 所需真实链路已经被 acceptance harness 固化，可重复验证“绑定 -> 连接 -> 消息往返 -> 回执 -> 上报”。
2. 当前系统的主要不足不在协议存在与否，而在产品状态映射：receipt/report 没有进入 conversation SSE，用户无法看到真实执行阶段。
3. `/im/v1/nodes` 在 websocket 关闭后迅速回到 `offline`，说明节点状态聚合是实时的，但消息流缺少配套的状态解释。
4. 本里程碑未触碰 data/dev-tasks.json，符合要求。
