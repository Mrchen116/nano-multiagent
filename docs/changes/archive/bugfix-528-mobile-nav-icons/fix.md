# bugfix-528: 移动端底部导航图标

## 原始报告

> 当前移动端的下面三个图标太丑了，完全可以用gpt的生图能力给生成三个更现代，更合适的

## 现象 / 复现

在宽度低于 768px 的 Web IM 中打开 Chat、Agents 或 Me，底部导航分别使用 `💬`、`🤖`、`👤` 系统 emoji。三者的颜色、材质、轮廓和视觉尺寸由操作系统字形决定，放在固定的深色商业化导航栏中缺少统一语言；Agent 的玩具机器人形象也弱化了长期智能体的产品语义。

复现基线：隔离启动 IM/Gateway 与 Vite，使用真实账号登录后在 Chrome 的 `390×844` viewport 打开 `/chat`。底栏可见彩色气泡、机器人和蓝色人像，inactive 状态仍保留 emoji 自带颜色，无法只通过产品的 muted / accent token 表达状态。截图见 `M1-fix/evidence/mobile-before-chat.png`。

## 根因

移动底栏最初在 `feat-340` 的视觉对齐阶段补入 emoji，只解决了“纯文字 tab 缺图标”的缺口；实现直接把三个系统字符写入 `AppShell`，没有建立适合 20–24px UI 的产品图标资产或统一几何规范。现有测试只保护三个链接、文案与未读数，没有约束图标类型、语义或 active/inactive 的产品色继承，因此操作系统 emoji 的差异一直未被回归发现。

原始设计意图是移动端始终提供 Chat、Agents、Me 三个稳定入口，并保留 Chat/Me 未读 badge、当前路由高亮和深色底栏。修复必须保住这些路由、文案、badge 与交互，只升级三枚图标及其触控/视觉呈现。

## 修复

- 先在真实 `390×844` 页面上确认深色底栏、品牌 accent 和三个入口的实际尺寸，再用内置 ImageGen 两轮生成同一套圆角几何图标概念；第二轮只简化 Agent 外环，避免机器人脸、玩具感和小尺寸噪声。
- ImageGen 概念板包含背景与两态展示，不适合直接缩为 22px 位图。实现以实际生成结果为视觉依据，将 Chat 气泡、Agent 开放六边轨道与 Me 人像规范化为同一 `24×24` 网格的 `currentColor` SVG React 资产，确保高 DPI 清晰且由既有 CSS token 控制 active / inactive。
- `AppShell` 仅替换三个 emoji 图形，保留 `/chat`、`/settings/agents`、`/me` 路由、既有标签、未读 badge 与计算逻辑；底栏链接调整为 `88×48px`，维持清晰的触控区域并让 22px 图标居中。
- 更新 IM current spec 与 AppShell 回归测试，保护三枚产品 SVG、Chat active 状态和不再回退到旧 emoji 的约束。

## 验证

- AppShell 定向 Vitest 先因找不到三枚 SVG 红灯，实施后 `4/4` 通过；frontend build 通过。
- 全量 frontend Vitest 首轮 `636` 通过、`4` 失败；将四个失败文件并发复跑时仍有资源争用，逐文件复跑最终 `75/75` 全通过，确认均为既有重型测试在并发下的 5 秒超时或异步 mock 未就绪，与本次 AppShell/CSS diff 无关。
- Chrome 与 WebKit 均以真实 `390×844` viewport 验收 Chat、Agents、Me；三个入口 active / inactive、标签、未读 badge 和 `88×48px` 点击区域正确，浏览器 console 均无 error / warning。after 截图见 `M1-fix/evidence/`。
- 隔离启动的 IM/Gateway、Vite 和浏览器均已关闭，端口确认释放；没有提交 `dist/`、运行时数据或临时截图缓存。
- 仓库 docs、lint、pytest、diff 与归档门禁结果见 `M1-fix/progress.md`。
