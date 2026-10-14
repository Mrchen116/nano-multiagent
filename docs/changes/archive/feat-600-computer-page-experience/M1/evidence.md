# M1 实施与真实客户端证据

## 版本与边界

- 同 PR #349 / `codex/feat-596-node-update`，worktree `/Users/czj/.codex/worktrees/feat-596-node-update/nano-multiagent`。实施基线 `bbc487e6da9cd69cfc5868906b2ce17ddbff3b6e` 已包含当时 `origin/main=290652ada2bf5fafbd4ac9f27a1514680ff78ca9`，原 feat-596 代码审查和真实后端证据仍可在其归档报告复核。
- 本次仅 Web 电脑页、局部组件/样式、中文/英文和直接回归测试。后端包、协议、更新器、DSH 屏障及聊天实现没有新增变化。当前 Web 构建 `index-D9js0oX-.js` / `index-CYZZh8ip.css`，由隔离 IM 提供。
- 真 IM `http://127.0.0.1:56745`，专用 nano 测试账号；真 managed Node `wt-runtime-67128` 与助手 `computer600-assistant`；模型 fixture 56633。0.3.0/0.4.0 候选包均基于上述后端基线构建，真实安装依赖、CLI 生命周期、DSH 与更新 worker；没有发布 release 或操作生产。
- 受控范围：下载 transport 仅映射准确候选 URL 到本地 tar；本地 SSE 模型可暂停回复；目标启动可延迟/退出。版本、hash、元数据、ready/connected 验证仍由产品执行。第二台「家里的 Mac mini」为本隔离 SQLite 的离线场景记录，不是假扮真实进程。

## 直接验证

| 范围 | 命令 / 证据 | 结果与限制 |
|---|---|---|
| 旧页面对新用户旅程的失败 | 临时恢复基线 NodesPage 后运行新 `nodes-page.test.tsx`，随后还原；`/tmp/computer600-baseline-red.log` | 3 failed，缺少按需详情与本页连接入口；这是旧实现对新验收的对照，不声称全部测试先写于实现 |
| 名称保存/空值/失败、复制成功/失败、实时离线保留草稿、空态/stale、更新语义 | 4 个 nodes 测试文件；`/tmp/computer600-tests.log` | 12 passed；最终文案、相对时间、完整诊断版本调整后再次通过 |
| 全部 Web 回归 | `npm test`；`/tmp/computer600-frontend-all.log` | 93 files / 870 passed；随后局部文案/时间修正用上述 12 项窄测试和构建覆盖 |
| 全部 TypeScript 后端回归 | `pnpm test`；`/tmp/computer600-backend-all.log` | 79 files / 294 passed；后端代码未改 |
| Web 构建 | `npm run build`；`/tmp/computer600-build.log` | passed，仅现有 bundle-size/dynamic-import 提示 |
| 架构与 diff | `python -m pytest tests/contract/test_runtime_dependency_contract.py -q`；`git diff --check` | 13 passed，diff clean |

## 作者真实客户端走查

先独立检查整体阅读和操作，再核对原型：名称/状态是首要信息，更新条内只有当前动作；无统计大卡、常驻编辑表单或列表原始错误码。桌面留有呼吸空间，手机动作换行、详情独立滚动。使用原有全局导航；全局通知不是本 unit 的改动范围。

- **S1/S2**：真实 Chromium 截图 1440×960、820×900、390×844、360×780；均无文档横向溢出。实际按钮边界桌面 40px、手机 44px。在线/离线两台列表；通过正常 PATCH 把在线电脑改为「我的 MacBook — 产品设计与长名称显示验收」，详情完整换行，最终改回「我的 MacBook」。
- **S3/S4**：桌面详情为右侧抽屉，390 手机为全屏。真实保存同时改变详情和底层列表；空名称就地报错。仅拦截该测试电脑的 config PATCH 为 503，显示失败且保留「失败时保留的名称」草稿；解除拦截后同一表单成功保存。返回焦点实际落回该电脑详情按钮。原始 ID/错误在折叠诊断里。屏幕键盘/物理 iPhone 不在本轮证据内。
- **S5**：本地模型 hold 真实 DSH 工作，Web 点击重试，操作 `266a9d7c-c1bf-4da6-bdc5-6131d1a574b4` 进入 waiting；手机显示等待任务结束与取消按钮。点击取消后于 `2026-10-14T00:34:06.669Z` cancelled，原 0.3 Node PID 72790 / DSH 72794 保持；解除 hold 后原消息完成。再次从 Web 点击更新，操作 `3178d49f-c234-4266-96dc-089496b0edd8` 经真实 switching → succeeded；切换时无取消按钮，页面说明新消息会等待，成功后显示实际 0.4.0。没有用 UI 计时器宣告成功。
- **S6**：作者打开真实回滚完成后的页面，显示「更新未完成，已恢复原版本」和重试，随后从此入口完成上述生命周期。环境准备者通过实际下载失败、目标启动失败验证了 failed/rolled_back；这部分进程自检仅是环境证据，完整用户体验由独立 reviewer 另行判断。
- **S7**：列表连接入口按需显示当前服务 `http://127.0.0.1:56745/install.sh` 的命令，Agent/手动两种模式可切换；正常复制显示成功。随后仅在此浏览器令 Clipboard API 拒绝，显示手动选中复制说明；刷新页面后已移除该故障。返回刷新仍在本页。没有执行安装或要求用户交出凭据。
- **S8 / 扩展异常**：已有直接组件回归；完整初始加载、stale、空列表、缺安装包、手机从“我”进入和英文全流程交独立验收，不能由本段推定 pass。

## 持久媒体与复验入口

作者原始媒体已复制到 `/Users/czj/Movies/Nano-Computer-Page-20261014/author/`：

- `author-1440.png`、`author-820.png`、`author-390.png`、`author-360.png`：最终构建的日常列表/有更新。
- `author-desktop-details.png`、`author-mobile-empty-name.png`、`author-mobile-save-failure.png`：详情、长名称与失败反馈。
- `author-mobile-waiting.png`、`author-mobile-cancelled.png`、`author-mobile-switching.png`、`author-mobile-succeeded.png`：真实阶段。
- `author-mobile-connect.png`、`author-mobile-copy-failed.png`：安装引导。
- `author-details.webm`、`author-update.webm`：真实交互连续录屏，无合成页面或剪接；浏览器 viewport 在更新录屏中有调整。

临时环境完整控制、reset-current、故障注入、启动/停止及存活核对见 worktree 的 `output/playwright/computer600-runtime/README.md`。其中 auth/config/数据库不提交。独立验收接管此环境，主 Agent 最终负责在更新终态后调用其 `stop.sh` 清理全部自建进程。后续门禁结论以本 unit `acceptance.md`、`verification.md`、`code-review.md` 为准。

## 交付整合（2026-10-14）

- 冻结产品 `4068b2cfdd138c8bbe3b0b9d839a910fca9d36dc`；独立 code review / full verifier 报告提交 `d1d94ea147dc200e3bc477ea8ecafaec49c7a39c`：findings `[]`、0 CRITICAL / WARNING / SUGGESTION，全部 delta aligned。独立产品验收提交 `5979e228818ab9d47cfce618dad56f48bf281996`：S1–S8、M1 A–D 和全部 must-match pass，0 issues。
- 最终 fetch 的 `origin/main` 仍为 `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`，已在分支内，无新增同步差异。`executed_base` 与 `effective_base` 均为此 SHA。后续源码仅删除 `node-display.tsx` 文件末尾一个空行，范围 diff-check 已恢复通过；没有语义、CSS 或数据流变化，无需重新验收。
- 已将独立核对 aligned 的两条 IM delta 原文归并 current `agents-nodes.md`，父级 Requirement 计数由 35 更新为 37，并完整归档本 unit；只修正归档导致的相对链接。Gate 2 的首文档用户目标、架构决定、原型与验收判据不变，原 Approved 结论 retained。上述门禁有效到本次交付树；PR 记录 `effective_through` 的精确提交。
- 补充本地 CI：`pnpm typecheck` 全通过；`pytest -m 'not e2e' -q` 56 passed / 31 deselected；ruff check 与 format 全通过；`npm audit --audit-level=critical` 为 0 vulnerabilities。最新范围 diff-check、docs-check 与显式两项 unit archive 检查见交付命令结果。
- 作者录屏另存同名 MP4，仅转为 H.264，未剪接。编码尺寸 800×600，详情 49.2 秒，更新 61 秒；页面 viewport 与截图尺寸单独记录，不能混同编码尺寸。隔离环境 runbook 已保存 `/Users/czj/Movies/Nano-Computer-Page-20261014/runtime-runbook.md`；独立验收全部媒体位于同目录 `independent-review/`。
- 产品 reviewer 完成后，主 Agent 在无 active operation 时执行该环境 `stop.sh`；IM/model 两个端口已无 listener，Node/DSH 停止。原型 18760 也已停止；独立 reviewer 的浏览器与 18761 原型服务已自行清理。主仓已有 dirty/untracked 文件未纳入本次提交。
