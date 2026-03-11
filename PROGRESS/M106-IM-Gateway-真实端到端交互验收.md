# M106 — IM↔Gateway 真实端到端交互验收

## 0. 前置说明
- 本里程碑开工前已阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/NodeGateway-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。
- 工作目录限定在：`/Users/czj/Repos/nano-multiagent/.worktrees/M106`。
- 按要求先执行真实基线，再开始补测试与实现。

## 1. 基线与最终验收
- 基线命令：
  - `PYTHONPATH=src pytest -q tests/im_service/integration/test_gateway_websocket_api.py tests/unit/personal_assistant/test_gateway_pipeline.py`
- 基线结果：8 passed。
- 最终验收命令：
  - `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py`
  - `python scripts/acceptance/run_m106_acceptance.py`
- 最终验收结果：
  - `tests/acceptance/test_im_gateway_real_acceptance.py`：2 passed。
  - `scripts/acceptance/run_m106_acceptance.py` 输出结构化检查项并再次跑出 2 passed。
- 最终结构化证据（来自实际脚本输出与 acceptance 断言）：
  - `device bind start+confirm`
  - `gateway websocket register+heartbeat`
  - `relay.message -> gateway inbound pipeline -> outbound reply`
  - `node.delivery_receipt sent/completed`
  - `node.report capture`
  - `product-gap assertion: SSE still lacks relay receipt progress events`

## 2. 当前发现
- IM 侧已具备：`GatewayHandler`、`RelayService`、`/im/ws/gateway`、消息中继与回执 ack。
- Gateway 侧已具备：`InboundPipeline`、`SessionRunQueue`、`OutboundRouter`、`KernelApiClient`、配置加载与最小启动骨架，以及可被 acceptance harness 直接复用的真实进程边界能力。
- M106 已补齐的资产：
  1. `tests/acceptance/test_im_gateway_real_acceptance.py` 固化了 bind start/confirm、node.register、node.heartbeat、relay.message、Gateway pipeline reply、node.delivery_receipt(sent/completed)、node.report 的真实链路证据。
  2. `scripts/acceptance/run_m106_acceptance.py` 提供了单入口复验脚本，并输出机器可读的检查项摘要。
  3. `PROGRESS/M106-产品交互批判记录.md` 把当前可工作主链路与仍未产品化的状态映射缺口分离记录。
- 仍然成立的真实产品缺口：
  1. conversation SSE 目前仍只暴露 `message.sent` / `message.delivered`，尚未把 `node.delivery_receipt` 和 `node.report` 映射为用户可见的 `relay.*` 进度事件。
  2. 节点离线状态会实时回到 `/im/v1/nodes`，但消息流里没有同步解释“节点已断开/刚完成一次执行”的上下文提示。

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
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py` → `2 passed in 0.43s`
  - Entry: 验收测试覆盖 bind start/confirm、node.register、node.heartbeat、relay.message、Gateway pipeline reply、node.delivery_receipt(sent/completed)、node.report。
  - Entry: `python scripts/acceptance/run_m106_acceptance.py` 输出结构化检查项并再次跑出 `2 passed in 0.37s`。
- Rollback:
  - 可回退到 `199dc082b49e3a37acd112e63284635f0977365d` 前的稳定点；该 Roadpoint 主要新增测试资产与脚本，无侵入式运行时代码改动。
- Commits: C1=199dc082b49e3a37acd112e63284635f0977365d
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
  - Tests: `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py` → `2 passed in 0.43s`
  - Entry: 批判记录明确指出 SSE 仍缺少 `relay.sent/relay.completed` 等用户可见状态事件，`message.delivered` 语义与真实处理进度存在错位。
  - Entry: `python scripts/acceptance/run_m106_acceptance.py` 的结构化输出已把上述产品缺口作为最终验收检查项之一固化。
- Rollback:
  - 若需重写批判结论，可保留 acceptance 资产不动，仅回退文档提交 `199dc082b49e3a37acd112e63284635f0977365d` 之后的文档变更。
- Commits: C1=199dc082b49e3a37acd112e63284635f0977365d
- Next:
  - 运行全量相关测试、整理最终证据、提交 milestone/M106 分支。

## 4. 当前结论
1. M106 所需真实链路已经被 acceptance harness 固化，可重复验证“绑定 -> 连接 -> 消息往返 -> 回执 -> 上报”。
2. 当前系统的主要不足不在协议存在与否，而在产品状态映射：receipt/report 没有进入 conversation SSE，用户无法看到真实执行阶段。
3. `/im/v1/nodes` 在 websocket 关闭后迅速回到 `offline`，说明节点状态聚合是实时的，但消息流缺少配套的状态解释。
4. 本里程碑未触碰 data/dev-tasks.json，符合要求。
