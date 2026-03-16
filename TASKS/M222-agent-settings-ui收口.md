# M222 - Agent 设置/新增页面产品收口

已在编码前阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`。

- Milestone: M222 / 梳理并修复新增 Agent 页面关键产品问题
- Branch: `milestone/M222`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M222`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
- Prevention Rules:
  1. 不能只修 workspace 一条文案，必须整体收口 create/detail 页的主次、状态反馈、控件密度与内部术语泄漏。
  2. workspace 表达必须区分“当前运行位置”与“保存中的设置”，避免把只读状态和可编辑设置混在一起。
  3. allowlist / node / status 区块要降低噪音，避免 advanced/internal 概念直接压到产品主路径。
  4. 页面级回归必须覆盖 create/detail/list mobile 的关键语义与布局层级。
  5. 若基线测试失败，先区分环境问题与代码问题；本 milestone 不越界改无关模块。

## R1 页面信息架构与 workspace 语义收口
- Status: DONE
- Acceptance:
  - create/detail 页的页头、主体表单、侧栏状态、底部操作区层级清晰，不再互相抢信息。
  - workspace 明确区分“当前运行中的位置”和“下次保存后采用的设置”，不再出现“当前/设置”语义混淆。
  - 操作反馈聚焦在保存/创建结果，不再把状态、说明、CTA 分散到多个区域造成穿模。
  - 文案不再泄漏 internal / advanced 等内部术语到默认产品路径。
- Tests Plan:
  - unit: 不单独新增；该路点以页面行为与文案层级为主。
  - contract: 不新增；现有 API 字段足够表达语义。
  - integration: 使用 React Testing Library 覆盖 create/detail 页关键文案、结构与可达 CTA。
  - e2e: 不做；本 milestone 入口风险主要在前端页面编排，已有页面级测试即可锁定回归。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写清页面分区、workspace 语义与回滚点。

## R2 allowlist / node / status 视觉交互收口与列表回归
- Status: DONE
- Acceptance:
  - allowlist 区域默认只呈现产品可选项，不把高噪音标签和大段解释堆在主路径。
  - node/status 区域从“信息堆叠”收口为可扫读的状态摘要，避免和主表单竞争注意力。
  - agents list mobile 与 detail/create 页保持一致的 workspace 语义与入口命名。
  - 回归覆盖 mobile list、detail/create 的页面级关键语义，避免后续再把内部术语或误导文案带回去。
- Tests Plan:
  - unit: 不新增；重点在页面组合层。
  - contract: 复用现有 API 集成测试，不新增协议层变更。
  - integration: 扩展 `agent-create/agent-detail/agents-list-mobile` 断言 allowlist、status、workspace 文案与入口一致。
  - e2e: 不新增；当前 exit criteria 聚焦页面级前端回归。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-mobile.test.tsx`
  - `tests/im_service/integration/test_agent_create_flow.py`
  - `tests/im_service/integration/test_agent_config_api.py`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写清 allowlist/status 收口点、回归证据与最终稳定提交。
