# bugfix-528-M1 — Progress

## 启动证据

- Baseline：`origin/main@48d19d8a7809805efcb7631e75079cc09daf2eab`；独立 worktree 干净，主 checkout 未触碰。
- Scope：`AppShell` 移动底栏图标、相邻 CSS、定向测试与本 unit 文档/evidence；不改变路由、文案、未读计算或桌面 shell。
- Existing intent：`feat-340` 以 emoji 补齐三个移动入口的图形提示；本次保留入口语义，把系统字形替换为产品资产。

## R1 — 真实页面 grounding 与 ImageGen 视觉探索

- Status：DONE
- Claim：确认问题来自真实商业化底栏中的系统 emoji，而非截图或构建偏差，并获得同一套可规范化的几何语言。
- Baseline / Method：隔离 IM/Gateway + Vite，Chrome `390×844`，登录 `nano` 打开 `/chat`；before 见 `evidence/mobile-before-chat.png`。
- Result：底栏为深色 `oklch(0.19 0.012 240)`，inactive 为 muted slate，active 为品牌青绿色；emoji 自带白/彩色/蓝色材质，无法继承状态色且三者光学重量不一。
- ImageGen：使用内置 ImageGen 的 `logo-brand` 路径生成同一图标系统概念板；第一版建立圆角气泡、抽象六边形智能节点和几何人像，第二版只减少 Agent 外环连接段，得到最终参考 `evidence/imagegen-nav-concept.png`。
- Prompt 摘要：在 24px 网格上生成 Chat / AI Agent / Personal Account 三枚圆角、约 2px 笔画的商业化导航图标，同时展示深色底栏中的 muted inactive 与 teal active；Agent 使用中心六边形核心、开放六边形轨道和两个连接节点；禁止文字、水印、机器人脸、emoji、玩具、渐变、阴影、发光、3D 与装饰细节。
- Asset strategy：ImageGen 输出是 `1536×1024` 概念板，直接缩到 22px 会模糊且包含背景；最终以其轮廓、圆角笔画、开放轨道和两态色彩关系为依据，手工规范化为 `currentColor` SVG React 资产，保留高 DPI 锐度和 CSS 状态控制。
- Source locator：内置输出 `exec-15227d37-0c87-44fc-ac43-71ea4eb75a58.png`，SHA-256 `e447d57226d7f04da9482028c6f462b3e42b3b4345ef5761c3e3332788ec1c6f`。
- Limit：概念板证明设计来源和选择，不证明 22px 页面效果；页面效果由 R3 真实浏览器验收。

## R2 — SVG 规范化、接入与回归测试

- Status：DONE
- Decision：新增 `mobile-nav-icons.tsx`，用同一 `24×24` 网格、`1.8px` 圆角笔画与 `currentColor` 实现 Chat 气泡、Agent 开放六边轨道和 Me 人像；不直接使用带背景的生成位图，以免 22px 缩放模糊。
- Integration：`AppShell` 仅把 `💬 / 🤖 / 👤` 替换为三枚 SVG；路由、标签、未读计算和 badge DOM 保持原样。链接触控区域为 `88×48px`，图标视觉尺寸为 `22×22px`。
- Regression：AppShell 定向测试先按预期红灯（`svg[data-mobile-nav-icon]` 数量为 `0`），实施后 `4/4` 通过，并覆盖 active Chat、三枚语义资产和旧 emoji 不再出现。
- Review：逐文件检查实现、删除行为、调用方与 spec 对齐，未发现需要修复的 code review finding；没有引入图标库或额外运行时依赖。

## R3 — 浏览器与交付门禁

- Status：DONE
- Browser：隔离启动 IM/Gateway 与 Vite，在 Chrome 和 WebKit 的真实 `390×844` viewport 验收；Chat、Agents、Me 三个页面均只有当前入口使用 accent，另外两枚保持 muted，标签与导航目的地正确。Chrome 另以 API route 注入 `unread_count=7`，确认 Chat/Me badge 均未被遮挡。
- Metrics：三个链接在浏览器中均量得 `88×48px`；Chrome 与 WebKit console 均为 `0` error / `0` warning。证据为 `evidence/mobile-after-chat.png`、`mobile-after-agents.png`、`mobile-after-me-unread.png` 与 `mobile-after-chat-webkit.png`。
- Frontend：定向 AppShell Vitest `4/4`；`npm run build` 通过（仅既有 >500kB chunk warning）；`npm audit --audit-level=critical` 通过（仅报告 2 个 low）。
- Full frontend：首次全量运行 `636` 通过、`4` 失败；失败文件并发复跑仍受资源争用影响。逐文件复跑 `agent-detail-page` `18/18`、`agent-prompt-preview` `3/3`、`agents-list-page` `3/3`、`chat-workspace.integration` `51/51`，合计 `75/75`，确认失败为并发环境下的既有 5 秒超时/异步 mock 时序，而非本次改动回归。
- Cleanup：已关闭浏览器、Vite、IM/Gateway，并确认隔离端口无 listener；运行数据与临时截图缓存已清理，提交范围仅包含产品代码、current spec、变更单和审阅证据。
- Repository gates：`./scripts/docs-check` 通过（214 maintained sources / 67 routes）；`ruff check .` 与 `ruff format --check .` 通过（875 files）；完整非 E2E pytest 首轮 `3176` 通过、`5` 失败，失败均为四进程负载下的 Feishu worker / Gateway 启动与回收超时，五个失败 node id 随后非并发复跑 `5/5` 通过；`git diff --check` 通过；`python scripts/check_change_unit_archived.py --head-ref unit/bugfix-528-mobile-nav-icons` 确认 change unit 只存在于 archive。
