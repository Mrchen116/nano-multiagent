# M223 Agent 设置页/新增页视觉穿模与布局收口

## 启动记录
- Milestone: M223 / 修复 Agent 设置页/新增页视觉穿模与布局收口
- Execution: parallel；使用 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M223`；分支 `milestone/M223`
- Scope:
  - Allowed: `src/IM/frontend/**`, `tests/**`, `TASKS/**`, `PROGRESS/**`
  - Forbidden: `src/IM/api/**`, `docs/**`, `ACCEPTANCE/**`, `data/dev-tasks.json`
- Test Gate:
  - `pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile && pnpm --dir src/IM/frontend build`
- Baseline:
  - 环境内缺少 `pnpm` 可执行文件，改用 `npx pnpm` 跑同一门禁。
  - 当前基线已有 1 条失败：`agent-detail-page.test.tsx` 对旧聊天说明文案的断言与页面实际文案不一致；属于前端测试/文案漂移，纳入本 Milestone 一并收口。
- Notes from LOGBOOK:
  - 做产品 UI 收口时，不能只验证功能 happy path，还要持续批判真实页面的信息架构与状态提示是否像产品而不是内部工具。
  - 若真实入口与预期不符，先排查环境；本次已确认是缺少 `pnpm` 命令，不是前端代码异常。
- Commenting Guide Commitment:
  - 后续新增/修改 public 代码会遵守 docstring 与注释规范；注释只写意图、约束与边界，不复述实现。

### R1 创建页/详情页信息架构与 allowlist 收口
- Context: 用户截图暴露出 Agent 新增页与详情页的主表单、侧栏、底栏同时抢焦点；allowlist selector 同时堆叠 chips、帮助文案、卡片与高级选项，视觉噪音过高。
- Decision: 将创建页与详情页都重排为 Identity / Behavior / Access & model 主区块，并把运行时/直聊信息收口到轻量右栏；allowlist selector 改为计数 badge + 轻量 chips + Common choices / Saved advanced selections / Show advanced options 三层结构。
- Rationale: 先按用户实际截图问题做信息架构减法，比继续往同一页面堆侧信息更能直接消除穿模、拥挤和“后台控制台感”。
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- agent-create agent-detail`
  - Entry: `AgentCreatePage` 与 `AgentDetailPage` 页面级测试均验证新分区标题、allowlist 计数、创建/保存主链路与直聊 CTA 仍可用。
- Rollback: `0e58787`
- Commits: C1=`0e58787`, C2=`ff6c71f`, C3=`f49160b`
- Next: 进入 R2，清理 Agents 列表桌面表格与移动端摘要密度。

### R2 Agents 列表页密度与桌面布局收口
- Context: Agents 列表桌面端仍是高密度表格，描述、工作区、节点和更新时间挤在表格列中，产品观感偏运维后台。
- Decision: 删除桌面 table，统一改成摘要卡片；桌面卡片分成 Workspace / Routing 两个摘要区块，移动端沿用更紧凑卡片但保留稳定直聊、工作区与节点信息。
- Rationale: 列表页核心目标是快速扫读和进入详情，不是做高密度数据表；卡片化更适合当前字段类型与产品语境。
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- agents-list-mobile`；全量门禁 `npx pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile && npx pnpm --dir src/IM/frontend build`
  - Entry: `AgentsListPage` 测试确认移动端无 table，桌面端改为 Active agents 摘要卡片并保留 Workspace / Routing 摘要和详情入口。
- Rollback: `fce24d7`
- Commits: C1=`fce24d7`, C2=`ff6c71f`, C3=`f49160b`
- Next: 提交文档，随后整体 rebase / merge / 更新 dev-tasks。
