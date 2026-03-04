# PROGRESS (Milestone: M37)

- Title: Playwright 抽检与视觉交互打磨（第一轮）
- Goal: 用 Playwright 对 IM 前端 desktop/mobile 的 chat/settings 关键流程做真实浏览器抽检，修复视觉与交互偏差并形成第一轮验收记录。
- Exit Criteria:
  - chat 与 settings 关键路径有 Playwright 实测与截图证据。
  - 明显视觉/响应式/交互问题已修复并回归验证。
  - 第一轮验收记录完整。
  - `cd src/IM/frontend && npm run test && npm run build` 全绿。
- Test command: `cd src/IM/frontend && npm run test && npm run build`
- Branch: `milestone/M37`

### Baseline
- Context:
  - use_worktree=true，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M37`。
  - 已读取并应用：`tdd-execution-worker`、`playwright`、`COMMENTING_GUIDE.md`、`LOGBOOK.md`、`IM前端蓝图.md`、`IM服务蓝图.md`、`Agent 助手（基于 SDK 的上层应用）蓝图.md`。
  - 首次跑门禁报错 `vitest: command not found`，已通过 `npm install` 补齐前端依赖。
- Decision:
  - 按三段执行：R37.1 真机抽检取证 -> R37.2 缺陷修复与回归 -> R37.3 验收收口与主干集成。
- Rationale:
  - 本里程碑核心是“真实可用性 + 视觉一致性”，先用真浏览器抓问题再做最小修复，能降低盲改风险。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build` 基线全绿（10 files / 13 tests passed + build success）。
  - Entry: `npx` 可用，Playwright CLI 前置满足。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R37.1：执行 desktop+mobile chat/settings 抽检并沉淀问题清单与截图证据。

### R37.1 Chat/Settings 桌面+手机 Playwright 抽检与证据采集
- Context:
  - 抽检范围覆盖 chat/settings，并同时覆盖 desktop（1280 宽）与 mobile（390x844）。
  - 要求在真实浏览器执行点击、输入、保存，非静态截图。
- Decision:
  - 采用 Playwright CLI（`open/snapshot/click/fill/screenshot`）逐路由抽检，并统一输出到 `src/IM/frontend/output/playwright/`。
  - 先做“修复前”取证，形成问题清单，再进入 R37.2。
- Rationale:
  - 先把偏差事实化（截图+操作路径），可避免后续修复目标漂移。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`（基线全绿）。
  - Entry:
    - Chat desktop：`M37-chat-desktop-list.png`、`M37-chat-desktop-after-send.png`
    - Chat mobile：`M37-chat-mobile-list.png`、`M37-chat-mobile-after-send.png`
    - Settings desktop：`M37-settings-desktop-agents-list.png`、`M37-settings-desktop-agent-detail-saved.png`、`M37-settings-desktop-nodes-saved.png`、`M37-settings-desktop-policies-saved.png`、`M37-settings-desktop-account.png`
    - Settings mobile：`M37-settings-mobile-agents-list.png`
    - 发现缺陷：
      - chat 详情页消息区域默认顶部对齐，未满足“消息流默认贴底”。
      - `/settings/agents` mobile 仍使用桌面表格，出现横向溢出（右侧空白带）。
- Rollback:
  - `0412c9a`（计划提交）
- Commits: C1=`N/A`, C2=`N/A`, C3=`N/A`
- Next:
  - R37.2：先写失败测试锁定两处缺陷，再做最小修复与回归取证。

### R37.2 视觉/响应式/交互缺陷修复（第一轮）
- Context:
  - R37.1 已定位两处明确偏差：消息贴底缺失、mobile agents 表格溢出。
- Decision:
  - C1：新增失败测试，锁定“消息贴底”与“mobile agents 非表格化渲染”。
  - C2：`MessagePane` 增加底部对齐容器与自动滚动；`AgentsListPage` 改为 `useIsMobile` 条件渲染（mobile 卡片 / desktop 表格）。
  - 修复后再次执行 Playwright desktop+mobile 复核并补截图。
- Rationale:
  - 以测试先红避免视觉修复回归；对现有结构做最小侵入调整，控制风险。
- Evidence:
  - Tests:
    - Red：`npm run test` 失败（`chat-layout` 找不到贴底容器、`agents-list-mobile` 检测到 table）。
    - Green：`cd src/IM/frontend && npm run test && npm run build` 全绿（11 files / 15 tests passed + build success）。
  - Entry:
    - 修复后截图：
      - `M37-chat-desktop-after-fix.png`
      - `M37-chat-mobile-after-fix.png`
      - `M37-chat-mobile-after-fix-send.png`
      - `M37-settings-desktop-after-fix.png`
      - `M37-settings-mobile-after-fix.png`
      - `M37-settings-mobile-nodes-after-fix.png`
      - `M37-settings-mobile-policies-after-fix.png`
      - `M37-settings-mobile-account-after-fix.png`
    - 验证结论：
      - chat 详情页短消息场景已默认贴底，发送后保持底部可见。
      - mobile settings agents 改为卡片布局，横向溢出消失。
- Rollback:
  - `ac014c2`（R37.2 C1）
- Commits: C1=`ac014c2`, C2=`fcb3c59`, C3=`<this-doc-commit>`
- Next:
  - R37.3：rebase main、全量门禁复跑、主干合并与 dev-tasks 状态收口。

### R37.3 第一轮验收记录与主干集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test && npm run build`
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
