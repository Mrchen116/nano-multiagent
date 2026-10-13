# bugfix-595: As-built Design

本文在实现完成后形成，描述实际落地设计。

## 实现范围

- Base：386753d1855b337902aa967814bd6e6d73872a5e。
- 分支：codex/bugfix-595-onboarding-scroll，独立 worktree；原主仓 dirty 内容未搬入。
- 本次产品改动：onboarding.css、membership-page.tsx、global.css。
- 用户在收到改后截图和验证结果后指示“提pr”，确认按当前结果交付；不补造用户亲自操作测试。

## 最终结构与决定

首次设置根元素使用 height:100%、min-height:0、overflow-y:auto，继承现有 root 的动态窗口高度。
滚动归首次设置自身管理，保留聊天应用的 body 滚动约束。所有设置步骤共用此容器。

MembershipPage 继续使用 AuthPageFrame，把账号、错误信息、操作按内容组排列。
账号以浅底信息块呈现；操作使用单列 grid、12px 间隔。主按钮沿用现有 submit 风格，
次按钮采用同宽描边按钮和至少 45px 点击高度。新增 CSS 仅使用 im-membership 前缀。
原有 join/refresh/continuePersonal 数据和路由逻辑不变，未新增 API、状态或依赖。

## 失败、兼容与回滚

沿用原有错误提示、busy 禁用、个人访问资格和返回地址规则。
共享登录/注册组件未改；长账号可换行。回滚本次三处产品文件即可恢复原布局。

## 验证

- npm test -- src/features/onboarding/onboarding-page.test.tsx src/features/settings/models/models-page.test.tsx：14/14。
- npm test -- src/features/auth/company-access.test.tsx src/features/auth/auth-form-experience.test.tsx：25/25。
- npm run build 和 pnpm -r --if-present build：通过。
- 真 IM + Node/DSH，独立账号、数据库、node identity 和 workspace。
- 中文连接模型：1280×720、1440×900、390×844、320×568，滚轮可到保存按钮，点击命中检查通过，无横向溢出。
- 自定义 API 三个模型并展开能力：保存按钮可达；Tab 可聚焦；Chromium 模拟触摸可滚动。
- 真实 pending 测试账号的团队申请页：1280×720、390×844、320×568 主次按钮同宽、间隔 12px；刷新保留 pending，继续个人使用返回 onboarding。
- 本地证据：worktree output/playwright/bugfix595/（截图不提交）。
- 边界：无真实模型请求、无生产变更；手机与触摸为浏览器模拟，未做物理设备验收。
- 用户交付确认：“提pr”；上述浏览器操作均由 Agent 执行。
- 文档检查：234 个 maintained Markdown sources、64 个 required routes 通过；diff --check 通过。
- 本次临时 IM、Node/DSH、Vite 已停止；截图保留在本地，不进入提交。

## 测试策略与契约

保留既有四个测试文件，覆盖交互与权限回归；布局故障使用真实浏览器验证。
本次不添加镜像 CSS 实现的 JSDOM 测试，也不把一次性截图脚本纳入长期测试。
最窄契约增量见 [specs/im/agents-nodes.md](specs/im/agents-nodes.md)，已归并到 current IM agents-nodes。
团队页调整仅为既有操作的表现修复，不增加业务契约。
