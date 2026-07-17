# feat-469-M1: clipboard-image-ingress — Tasks

> 对齐: ../design.md（spec.md v1）

## 目标

桌面 Web IM 的聊天输入框可以把 paste 事件中的单张或多张图片按剪贴板顺序加入既有待发附件区；图片独占混合粘贴，纯文本/非图片保持浏览器默认行为，失败通过现有页面级 toast 给出本地化反馈且不回滚成功项。

## 退出标准

- [ ] 单图、多图、混合图片+文本、items 优先/files fallback、纯文本、非图片与 null item 的 paste 行为符合 M1-E1～M1-E6。
- [ ] paste 与 drop 汇聚既有 `handleAdd`，保持顺序上传、partial success、pending chip 删除/随文字发送与 send busy 不变量。
- [ ] unsupported type、too large、network、unknown 上传失败均显示本地化、可关闭的页面级附件错误 toast；失败项不进入 pending，成功项保留。
- [ ] 指定 Vitest、production build 全绿，desktop Chromium 从 `/chat/:conversationId` 完成全部 must-match 原型对照且证据持久化到 `evidence/`。
- [ ] 不调用主动 Clipboard API，不提交 `dist/`、临时配置或浏览器运行产物。

## 测试策略

- 被测行为（来自退出标准）：items 图片按原序进入 pending；items 无可用图片时 files fallback 且不重复；有图才阻止默认粘贴并舍弃伴随文本；纯文本/非图片/null item 放行；粘贴附件可删、可带文字发送；send busy 不接收附件；逐项上传失败回调且成功项保留；production 组装把四类错误映射为本地化可关闭 toast。
- 已有测试在：`src/IM/frontend/src/features/chat/components/message-pane.test.tsx` 与 `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx`（扩展）。不拆新文件的理由：design 的 Milestone 范围明确锁定这两份测试文件；现有附件 fixture、drop/send 断言与 workspace fetch harness 都在对应文件中，抽移旧用例会引入与本功能无关的测试重组和行为漂移风险。本 milestone 只在现有附件段增加紧凑的行为用例，不复制 harness。
- 落层/目录/marker：`src/IM/frontend/src/features/chat/` Vitest component + integration，marker：无；真实浏览器为一次性验收证据，不新增永久 E2E 基础设施。
- 可选依赖 importorskip：无（前端 package 已声明 Playwright；仅用于一次性 Chromium 验收）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时浏览器驱动脚本删除；截图与验收报告持久化到 `M1-clipboard-image-ingress/evidence/`。

用户路径分类：`critical-path`（聊天附件输入与发送）；同时属于 issue #202 的 `bug-regression`。

UI 状态矩阵：

| 状态 | 覆盖计划 |
|---|---|
| default | 纯文本/非图片维持原生 paste；空 pending 不渲染 chip strip |
| loading | N/A；上传沿用既有逐项异步流程，无新增 loading 视觉 |
| empty | 无图片时不接管、不增加 pending |
| error | 四类错误映射到页面级 toast，失败项不入 pending，成功项保留 |
| disabled | textarea/send busy 时不接收新的 paste 附件 |
| submitting | 异步发送期间 pending/删除/新增继续冻结 |
| permission denied | N/A；只读 paste event `clipboardData`，不申请剪贴板权限 |
| long content | N/A；本 unit 不改变文本/附件长内容布局 |
| missing/nullable data | `getAsFile() = null` 放行；items 无图片才 fallback files |
| mobile viewport | N/A；spec 明确桌面浏览器范围，不改 mobile 布局 |
| desktop viewport | 1440×900 Chromium 覆盖单图、多图、混合、失败、删除与发送 |
| dark mode（如项目支持） | N/A；不新增视觉 token，复用既有 chip/toast |

测试与验收映射：

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| items/files 提取顺序、fallback 与 preventDefault 边界 | MessagePane 交互 regression + Chromium paste | 是（Vitest） |
| pending chip 删除、文字+图片发送、send busy | MessagePane 交互 regression + Chromium 真实入口 | 是（Vitest） |
| partial success 与逐项错误上报 | MessagePane 交互 regression | 是（Vitest） |
| production 页面级 typed/unknown error toast 与 dismiss | ChatWorkspace integration + Chromium 真实入口 | 是（Vitest） |
| 64×64 chip、混合 draft 空、toast 可见层级 | 1440×900 截图 + prototype comparison | 否（持久 evidence） |

Prototype / Reference Contract：

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| `#composer-pasted-images` | must-match：单/多图沿用 64×64 pending chip，可删除、可带文字发送，顺序与剪贴板一致 | desktop Chromium 单图、多图、删除、发送截图/报告 | worker/reviewer |
| `#composer-mixed` | must-match：同次 paste 只接管图片，draft 不插 URL/alt/伴随文本 | desktop Chromium 混合 paste 截图与 textarea value 记录 | worker/reviewer |
| `#attachment-error-toast` | must-match：任一拒绝/上传失败出现可见可关闭页面级错误，失败项不入 pending，成功项保留 | desktop Chromium partial-success + toast 截图/报告 | worker/reviewer |
| sidebar / message list / composer redesign | out-of-scope：保持真实产品现状 | 浏览器走查确认无布局扩改 | worker/reviewer |
| toast 精确像素/排版 | may-adapt：复用现有 page-level owner 与 i18n | 对照现有 toast 层级和可关闭语义 | worker/reviewer |

## Roadpoints

### R1 — 剪贴板图片汇聚既有附件状态机

- 状态: TODO
- 步骤: 先以 MessagePane regression 固定 items 优先保序、files fallback、不重复、mixed/default 边界、send busy、删除/发送与 partial success；再只从 paste event 的 `clipboardData` 提取图片并调用既有 `handleAdd`，失败逐项上报可选 callback。
- 验证: 聚焦运行 MessagePane tests；确认 C1 在缺少 paste 能力上失败、C2 后相关回归及既有附件测试全绿。

### R2 — 页面级本地化失败反馈与真入口验收

- 状态: TODO
- 步骤: 先以 ChatWorkspace integration 固定四类错误、partial success、dismiss；再由页面 owner 映射 typed/unknown error 并复用现有 toast。完成指定 Vitest、build 与 desktop Chromium must-match 对照，落持久 evidence。
- 验证: 120+ tests 全绿、production build 全绿、`/chat/:conversationId` desktop Chromium 无 console error/failed network（预期失败上传请求单列说明），原型逐项 match。
