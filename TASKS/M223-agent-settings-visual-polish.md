# M223 Agent 设置页/新增页视觉穿模与布局收口

- Milestone: M223
- Title: 修复 Agent 设置页/新增页视觉穿模与布局收口
- Goal: 直接收口 Agent 新增页、详情页、列表页的密度爆炸、卡片拥挤、说明堆叠、侧栏失衡与穿模风险，让页面更接近产品设置页而不是内部控制台。
- Prevention Rules:
  - 直接面向截图暴露的穿模和丑陋问题做视觉收口。
  - 减少噪音和堆叠，压缩重复表达。
  - 不把内部控制台感继续带进产品界面。
- Test Gate:
  - `pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile && pnpm --dir src/IM/frontend build`
  - 本地基线因环境缺少 `pnpm` 可执行文件，执行时使用 `npx pnpm` 等价跑同一门禁。

## R1 创建页/详情页信息架构与 allowlist 收口
- Status: TODO
- Acceptance:
  - 创建页与详情页出现明确的主区块分组，基础信息、行为配置、访问范围、运行状态主次清晰。
  - allowlist 选择器不再同时堆叠重复帮助文案、重卡片和冗长 chips，已选状态可快速扫读。
  - 侧栏/底栏职责收口，状态区与主表单不再相互挤压，常见桌面宽度下按钮区与状态区清晰可读。
  - 不改 API 语义，只调整前端文案、结构和视觉层次。
- Tests Plan:
  - unit: 不单独新增纯函数单测；本 Roadpoint 以页面渲染结构为主，收益低。
  - contract: 不新增；接口字段契约未变化。
  - integration: 选择 `agent-create.test.tsx`、`agent-detail-page.test.tsx`、`agent-edit.test.tsx`，验证创建/详情真实页面在新结构下仍可完成主流程与保存流程。
  - e2e: 不新增浏览器 e2e；本 milestone 先用现有 React Testing Library 入口覆盖页面级结构与交互。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - 入口：`npx pnpm --dir src/IM/frontend test -- agent-create agent-detail`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - `PROGRESS/M223-agent-settings-visual-polish.md` 记录决策、证据、回滚点与提交哈希。

## R2 Agents 列表页密度与桌面布局收口
- Status: TODO
- Acceptance:
  - 列表页在桌面宽度下不再使用信息密度过高的大表格，主信息、次信息和 CTA 分区清楚。
  - 移动端卡片去掉多余噪音，保留默认模型、工作区、节点、更新时间等关键摘要。
  - 空态、加载态、错误态仍保留明确操作入口。
  - 常见桌面宽度下无明显拥挤、折行穿模和说明文案堆叠。
- Tests Plan:
  - unit: 不新增；核心变化是页面布局结构而非独立逻辑。
  - contract: 不新增；列表接口契约不变。
  - integration: 在 `agents-list-mobile.test.tsx` 同时覆盖移动端与桌面端渲染，验证不再出现桌面 table，且关键摘要仍可见。
  - e2e: 不新增浏览器 e2e；列表页用现有 router + fetch mock 入口足够验证。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agents-list-mobile.test.tsx`
  - 入口：`npx pnpm --dir src/IM/frontend test -- agents-list-mobile`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - `PROGRESS/M223-agent-settings-visual-polish.md` 记录决策、证据、回滚点与提交哈希。
