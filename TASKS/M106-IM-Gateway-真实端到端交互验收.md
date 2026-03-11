# M106 — IM↔Gateway 真实端到端交互验收

## 前置阅读
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/SPEC.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/docs/NodeGateway-SPEC.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/docs/内核设计SPEC.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/ROADMAP.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`

## TDD 计划
- [x] 先跑当前基线，确认 IM WebSocket + Gateway pipeline 现状
- [x] 增加真实进程边界下的 IM↔Gateway e2e/acceptance 测试资产
- [x] 复用现有 IM WebSocket + Gateway pipeline 组件，形成真实验收 harness（不扩展到 M104）
- [x] 让验收脚本覆盖注册 / 连接 / 消息往返 / 状态回执主链路
- [x] 输出商业产品视角交互审视与问题清单
- [ ] 更新 PROGRESS 与 board 状态，完成后合并回 main

## Roadpoints

### R1 真实验收资产
- Acceptance:
  - 用真实 IM HTTP API + `/im/ws/gateway` WebSocket 跑通 register/connect/message/receipt 主链路。
  - 验收测试同时覆盖 bind start/confirm、relay.message、Gateway pipeline reply、delivery_receipt sent/completed、node.report。
  - 产出可复跑的 acceptance 脚本，便于后续人工/CI 复验。
- Tests Plan:
  - unit: 不新增；已有 gateway pipeline 单测已覆盖局部路由语义，本 Roadpoint 聚焦真实链路。
  - contract: 不新增；协议字段已有 gateway protocol contract 测试，避免与 acceptance 重复。
  - integration: 复用既有 IM/gateway integration 作为基线。
  - e2e: 新增 acceptance 测试作为主验证入口。
- Expected Tests:
  - `tests/acceptance/test_im_gateway_real_acceptance.py::test_im_gateway_acceptance_covers_bind_connect_roundtrip_and_receipts`
  - `tests/acceptance/test_im_gateway_real_acceptance.py::test_im_gateway_acceptance_exposes_failure_feedback_gap_in_sse`
  - `python scripts/acceptance/run_m106_acceptance.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/acceptance/test_im_gateway_real_acceptance.py` 全绿。
  - 验收脚本可直接运行并输出检查项。
  - PROGRESS 记录证据与边界。
- 状态: DONE

### R2 产品交互批判
- Acceptance:
  - 记录绑定、会话建立、消息发送、回执、失败反馈、状态提示六个视角的成熟产品批判。
  - 明确当前主链路可工作的证据和仍未产品化的缺口。
  - 输出问题清单与后续改进建议，但不跨到 M104 全量验收。
- Tests Plan:
  - unit: 不适用；此 Roadpoint 为验收结论与产品批判文档。
  - contract: 不适用；不新增接口契约。
  - integration: 依赖 R1 真实链路证据。
  - e2e: 以 R1 acceptance 结果作为输入证据。
- Expected Tests:
  - 依赖 `tests/acceptance/test_im_gateway_real_acceptance.py`
- DoD:
  - 形成独立产品批判记录。
  - TASKS/PROGRESS 写明问题清单、跟进建议与不做范围。
- 状态: DONE

## 产出清单
- `tests/acceptance/test_im_gateway_real_acceptance.py`
- `scripts/acceptance/run_m106_acceptance.py`
- `PROGRESS/M106-产品交互批判记录.md`
- `PROGRESS/M106-IM-Gateway-真实端到端交互验收.md`
