# bugfix-820: Review

## 范围与版本

- 本次问题与需求/设计位置：`docs/changes/archive/bugfix-820-im-desktop-nav-and-copy/fix.md`（Issue G 桌面与窄屏个人导航隔离、Issue H 日常 Chrome 配对控制与隔离说明、Issue I 消除内部术语与硬编码词条），关联长青契约 `docs/specs/im/web-chat-ux.md`、`docs/specs/im/agents-nodes.md`。
- 实际 `executed_base` / `validated_at`：
  - 首轮联合独立审查：`executed_base = 890d74f70d1444f2fd961a7e60d02b858821abaa`（`origin/develop`），`validated_at = ab0a2ebd423b10f2548cbd8933c4812928343854`。
  - Patch / Closure 与 `corrected-delta` 复验：`pre_fix_head = ab0a2ebd423b10f2548cbd8933c4812928343854`，`validated_at = 60b97c37d84c9ae7da1c82e0e9c6e0722fa0da38`。
- 最终 `effective_base` / `effective_through` 与保留依据：`effective_base = 890d74f70d1444f2fd961a7e60d02b858821abaa`，`effective_through = 60b97c37d84c9ae7da1c82e0e9c6e0722fa0da38`（后续归档提交仅移动 `docs/changes/bugfix-820-im-desktop-nav-and-copy/` 目录并写入本报告，不改动任何业务源码、测试或 canonical specs，全部代码与前端体验审查结论有效保留）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| Q1：桌面视口消除 `/me` 返回入口与直达停留、完整保留 `AccountPage` 能力，且窄屏 `< 768px` 保持 `/me` ↔ 5 个设置子页（account / nodes / models / policies / company）`‹ 我 / ‹ Me` 闭环导航（Issue G） | `change-code-review` + `frontend-experience-review`，独立审查者（`conversation://e05239af-b5f8-48bf-addd-659068a408a3`），首轮 full（`ab0a2ebd4`）→ 二轮 patch/closure（`60b97c37d`） | `pass` | 全仓检索确认 `/me` 入口仅限窄屏底栏与 5 个子页 `isMobile` 返回链接；`MePage` 桌面视口 `<Navigate to="/settings/account" replace />`；`router.test.tsx` 覆盖桌面（`1280px`）与窄屏（`390px`）全部 5 个子页及 `/me` 行为；真实 Chromium 截图 `01`、`03`–`06`、`08`、`10`–`17` 验证桌面与窄屏中英文排版及连续跳转闭环。 |
| Q2：`BrowserPairingSection` 三种变体与各状态中英文文案准确传达「后台操作 Chrome + 复用已登录会话 vs 干净隔离浏览器不碰个人数据」且排版协调（Issue H） | `change-code-review` + `frontend-experience-review`，独立审查者（`conversation://e05239af-b5f8-48bf-addd-659068a408a3`），full（`ab0a2ebd4`，`60b97c37d` 未触碰该区域 retained） | `pass` | 与 `packages/dsh-integration/src/computer/browser.ts` 的 `daily` / `isolated` 真实行为逐项核对一致；`.browser-pairing-summary` 全宽独立行确保首行标题、徽标与按钮在中英文窄抽屉（截图 `03`、`09`）及 Agent 创建页宽卡（截图 `07`）均不折断；`web-browser-pairing.test.tsx` 与 `desktop-client.test.tsx` 通过。限制：Desktop 原生宿主专属 `desktop-strip` 展开态由组件单测覆盖，与抽屉共享同一套 `.browser-pairing-head` / `.browser-pairing-summary` 布局规则。 |
| Q3：消除 `MePage` 内部 UUID（`user.id`）、消除硬编码词条、统一 `UserMenu` / `MePage` / 设置入口中英文通俗术语，且 `PoliciesPage` 诚实反映存储用量与未接入执行的策略预设（Issue I） | `change-code-review` + `frontend-experience-review`，独立审查者（`conversation://e05239af-b5f8-48bf-addd-659068a408a3`），full（`ab0a2ebd4`，`60b97c37d` 未触碰该区域 retained） | `pass` | `MePage` 身份卡显示 `@username` 且空用户名不回退暴露 `user.id`（`me-page.test.tsx`）；`UserMenu`（截图 `02`、`08`）与 `MePage`（截图 `10`、`14`）统一为 `账号 / Account`、`电脑 / Computers`、`AI 模型与 API / AI Models & API`、`用量与团队规则 / Usage & Policies`、`成员管理 / Team members`；`PoliciesPage`（截图 `05`、`08`、`13`）如实分层展示附件容量与策略预设；`zh.json` 与 `en.json` 键树 100% 对称（`i18n.test.ts`）。 |
| Q4：归并至 `docs/specs/im/web-chat-ux.md` 与 `docs/specs/im/agents-nodes.md` 的长青契约校对（`corrected-delta`） | `change-code-review`（`corrected-delta`），独立审查者（`conversation://e05239af-b5f8-48bf-addd-659068a408a3`），首轮 `ab0a2ebd4` → 二轮 `60b97c37d` | `pass`（`aligned`） | `F1` 修复后，两份 canonical spec 条款与 `60b97c37d` 实现、回归测试及相邻契约（`auth-tenancy.md`、`desktop-client.md`）完全一致，无条件冲突或重复归属。 |

## Findings 与关闭

- **F1**（`CONFIRMED`，`severity: medium`）：
  - **位置**：`src/IM/frontend/src/features/settings/company/company-members-page.tsx:71`（关联 `src/IM/frontend/src/app/router.test.tsx:156-160`、`docs/specs/im/web-chat-ux.md:545-546`）。
  - **触发条件与影响**：首轮提交 `ab0a2ebd4` 中，窄屏 `< 768px` 下 `/settings/company` 顶部粘性窄条仍渲染裸 `‹`（`aria-label="返回" / "Back"`，热区 `40×40px`），未像其余 4 个设置子页那样提供 `‹ 我` / `‹ Me` 返回 `/me`，与 `web-chat-ux.md` 归并条款不一致且窄屏路由单测遗漏该页。
  - **Resolution**：在提交 `60b97c37d` 中将 `CompanyMembersPage` 窄屏顶部返回统一为 `isMobile` 门控的 `<Link to="/me" data-testid="company-page-back" className="company-page-back">‹ {t("me.title")}</Link>`（`min-height: 44px`），保留页面主标题 `<h1>`，并在 `router.test.tsx` 窄屏循环中补齐 `["/settings/company", "company-page-back"]` 断言及窄屏双语截图 `16`、`17`。
  - **独立关闭依据与版本**：独立审查者（`conversation://e05239af-b5f8-48bf-addd-659068a408a3`）在 `60b97c37d84c9ae7da1c82e0e9c6e0722fa0da38` 复核代码 diff、补跑 `router.test.tsx` 与 `company-access.test.tsx`（16/16 通过）并检查截图 `16`、`17`，判定 `F1` 为 **`closed`**，当前**无存活 findings**。

## 流程收口

- **重要目标和关键设计覆盖**：Issue G（桌面脱离 `/me` 单列页并保留 `AccountPage` 与窄屏闭环）、Issue H（日常 Chrome 后台自动化操作 + 登录态复用 vs 干净隔离浏览器边界文案）、Issue I（消除 UUID 与硬编码、统一全站通俗中英文术语与诚实 `PoliciesPage` 说明）均已实现并通过测试与真实画面验证。
- **开放问题 / pending / inconclusive**：无。
- **最终 delta 校对**：`aligned`（`docs/specs/im/web-chat-ux.md`、`docs/specs/im/agents-nodes.md`）。
- **版本变化后保留 / 补验的判断与依据**：`ab0a2ebd4..60b97c37d` 仅触及 `CompanyMembersPage` 窄屏返回链接、`router.test.tsx` 与 `fix.md`，已完成定向补验；Q2、Q3 未受触及故有效保留；最终归档提交仅移动 `docs/changes/` 文档目录，不影响产品代码与契约。
- **测试资源回收结果**：取证脚本使用的临时 Vite 进程、Playwright Chromium 实例及临时 `src/IM/frontend/dist/` 产物均已当场终止并清理，无残留测试进程或运行目录；当前开发 worktree 按规则保留供人工审查与后续合入后清理。
- **交付范围与剩余事项**：归档本 unit 并提交 PR（base: `develop`），跟进远端必需 CI 检查；不自动合入 PR，不触碰生产环境。
