# M134 Web IM Agent 配置真实链路收口

## Milestone 概述
- Goal: 将 `/settings/agents` 列表与详情从前端 mock-settings-api 切到真实 IM Agent 配置 API，并验证配置修改只影响新会话。
- Test Command: `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build`
- Scope: 仅限 `/Users/czj/Repos/nano-multiagent/.worktrees/M134`；不修改 `data/dev-tasks.json`，不创建新 worktree。

## R1 设置页真实 API 读链路
- Status: TODO
- Acceptance:
  - `/settings/agents` 列表通过真实 `GET /im/v1/agents` 读取，不再依赖 `mock-settings-api`。
  - `/settings/agents/:agentId` 详情通过真实 `GET /im/v1/agents/{id}/config` 读取。
  - 前端保留必要的 loading/error 状态，且适配真实接口字段。
  - 后端 contract/integration 测试覆盖 Agent 列表与详情返回字段。
- Tests Plan:
  - unit: 前端 API client 与页面绑定测试，验证真实接口调用与渲染。
  - contract: 后端 contract 测试校验 `/im/v1/agents`、`/im/v1/agents/{id}/config` 结构。
  - integration: 前后端集成测试验证真实读取链路。
  - e2e: 本 Roadpoint 先不做；留到 R3 统一用真实浏览器验证。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agents-list-page*.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page*.test.tsx`
  - `tests/im_service/contract/test_agent_config_contract.py`
  - `tests/im_service/integration/test_agent_config_api.py`
- DoD:
  - 相关红测先失败，再以最小实现转绿。
  - `PYTHONPATH=src pytest -q tests/im_service && cd src/IM/frontend && npm run test && npm run build` 全绿。
  - 完成 C1/C2/C3，并在 PROGRESS 记录证据、提交哈希、回滚点。

## R2 设置页真实 API 写链路与新会话生效约束
- Status: DONE
- Acceptance:
  - `/settings/agents/:agentId` 保存走真实 `PATCH /im/v1/agents/{id}/config`，携带 `profile_version` 乐观锁。
  - 成功保存后页面显示最新 `profile_version` 与保存反馈。
  - 自动化验证“配置变更仅影响新会话，旧会话不漂移”。
  - 冲突场景保持真实 409 语义，不被前端吞掉。
- Tests Plan:
  - unit: 前端保存交互、请求 payload、保存后页面状态。
  - contract: 后端 PATCH 成功/409 响应结构。
  - integration: 后端现有新旧会话版本快照测试继续覆盖 system prompt 更新语义；必要时补前端 API 层测试。
  - e2e: 本 Roadpoint 先不做；留到 R3 统一验证真实入口。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `tests/im_service/contract/test_agent_config_contract.py`
  - `tests/im_service/integration/test_agent_config_api.py`
- DoD:
  - 红测体现真实 PATCH 缺口后再实现。
  - 全量门禁命令全绿。
  - 完成 C1/C2/C3，并在 PROGRESS 记录真实配置约束证据。

## R3 真实入口浏览器验证与记录收口
- Status: DONE
- Acceptance:
  - 通过真实浏览器验证 `/settings/agents` 可读、Agent 详情可写。
  - 记录真实 system prompt 修改后新会话生效、旧会话不漂移的入口证据。
  - TASKS/PROGRESS 补齐最终状态、证据与剩余风险。
- Tests Plan:
  - unit: 不新增，复用前序测试。
  - contract: 不新增，复用前序测试。
  - integration: 复用 IM service API tests 作为自动化主证据。
  - e2e: 使用浏览器真实入口（Playwright 或等价方式）验证 settings 页面读写。
- Expected Tests:
  - 浏览器真实入口操作记录
  - `PYTHONPATH=src pytest -q tests/im_service`
  - `cd src/IM/frontend && npm run test && npm run build`
- DoD:
  - 浏览器真实入口证据可回传（本轮已通过 Playwright CLI 直接验证 IM host `/settings/agents` 读写）。
  - 全量门禁命令全绿。
  - 完成 C1/C2/C3，并在 PROGRESS 记录入口证据、回滚点、下一步。
