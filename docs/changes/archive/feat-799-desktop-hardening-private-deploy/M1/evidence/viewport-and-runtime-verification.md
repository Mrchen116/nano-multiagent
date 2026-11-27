# M1 隔离真栈与多视口实测记录

- **执行时间**：`2026-11-27T06:44:17Z`
- **执行环境**：Worktree `/Users/czj/.t3/worktrees/nano-multiagent/unit-feat-799-desktop-h-fc757246e440f3fe`（独立临时隔离目录 `/tmp/feat799-m1-e2e-*`，独立 SQLite、独立端口 `18921..18923` 与 `--isolated-root` 回环宿主，`CREWDEN_SUPPRESS_OS_OPEN=1`）
- **资源回收状态**：全部子进程（IM Server × 3、Crewden Desktop Headless Host × 2、Chromium）及 `/tmp/feat799-m1-e2e-*`、`src/IM/frontend/dist/` 已在脚本 `finally` 与收尾命令中完整清理回收；仓外视口截图保留于会话临时目录供本轮审查核对。

---

## 1. 独立 IM 私网 HTTP 门禁与自托管发布源校验

| 场景 | 服务环境变量摘要 | `GET /im/v1/public/install` 关键结果 | `GET /install.sh` |
|---|---|---|---|
| 私网 HTTP 默认关闭 | `IM_PUBLIC_URL=http://192.168.10.25:18921`（未设 `IM_ALLOW_PRIVATE_HTTP`） | `available: false`, `windows_x64: null`, `desktop_darwin_arm64: null`, `desktop_win32_x64: null` | `503` |
| 私网 HTTP 显式开启 + 自托管源 | `IM_PUBLIC_URL=http://192.168.10.25:18922`, `IM_ALLOW_PRIVATE_HTTP=1`, `IM_RELEASE_BASE_URL=http://192.168.10.25:18921/releases/` | `desktop_win32_x64: { download_url: "http://192.168.10.25:18921/releases/Crewden-Desktop-Setup-x64.exe", connect_url: "crewden-desktop://connect?origin=http%3A%2F%2F192.168.10.25%3A18922", version: "1.2.0" }`, `windows_x64: null`, `available: false` | `503` |

---

## 2. 首启解包隔离、深链确认与公网明文拦截

| 检查项 | 实测入口 | 观察结果 |
|---|---|---|
| 未解包态阻断源码目录穿透与即时反馈页 | `CREWDEN_SEED_ARCHIVES_DIR=<isolated>` 启动 `crewden-desktop --headless-host` | `host-state.json` 立即落盘（`host_ready: true, ready: false`）；主窗口返回内联无依赖 HTML（`运行环境初始化未完成` + 日志路径 + 重试按钮）；`GET /desktop/v1/local-node/inspect` 前置返回 `503 { code: "seed_preparing" }` |
| 跨服私网 HTTP 深链唤起确认 | `POST /desktop/internal/deep-link` (`crewden-desktop://connect?origin=http%3A%2F%2F10.0.0.42%3A8080`) | 不自动改写 `im_origin`；主窗口弹出 `desktop-server-switch-modal` 展示当前/目标服务对比与琥珀色未加密 HTTP 风险提示；点击「保留原服务」后清除挂起状态 |
| 公网/官方域名明文 HTTP 深链拦截 | `POST /desktop/internal/deep-link` (`crewden-desktop://connect?origin=http%3A%2F%2Fim.crewden.work`) | 保持原 `im_origin` 不变；主窗口弹出 `desktop-deep-link-error-modal` 明确提示必须使用 `https://` |
| 无路由普通重开唤醒保持当前页 | 停留在 `/register` 时 `POST /desktop/internal/deep-link` (`{ url: null, route: null }`) | 返回 `200`，路由保持 `/register` 不跳往 `/chat` |
| Desktop 未登录访问 `/` 或 `/about` | 打开 `/desktop/bootstrap?nonce=<nonce>&next=/about` | 自动重定向至 `/login`，且 `ProductHeader` 左上角品牌链接指向 `/login` |

---

## 3. 多视口一屏化布局测量对照表（真实 Chromium + Desktop 回环宿主）

| 场景 | 视口尺寸 | `data-crewden-desktop` | 外层 `scrollHeight / clientHeight` | 内部容器 (`selector`: `scrollHeight / clientHeight`) | 左侧插画不裁剪 / 底栏在视口内 | 结论 |
|---|---|---|---|---|---|---|
| Web `/about`（非 Desktop 对照） | `1280×840` | `null` | 正常网页流（顶栏 `100px`） | — | — | 无回归 |
| `/login` 默认态 | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.crew-account-form-region`: `451 / 451`（零内滚） | `storyFitsShell: true` | 通过 |
| `/login` 默认态 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.crew-account-form-region`: `451 / 451`（零内滚） | `storyFitsShell: true` | 通过 |
| `/login` 原地展开服务编辑 + 私网 HTTP 提示 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.crew-account-form-region`: `489 / 489`（零内滚） | `storyFitsShell: true` | 通过 |
| `/login` 原地展开服务编辑 + 公网 HTTP 报错 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.crew-account-form-region`: `496 / 496`（零内滚） | `storyFitsShell: true` | 通过 |
| `/register` 注册页 | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.crew-account-form-region`: `517 / 517`（零内滚） | `storyFitsShell: true` | 通过 |
| `/register` 注册页 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.crew-account-form-region`: `517 / 517`（零内滚） | `storyFitsShell: true` | 通过 |
| `/register` 移动端窄屏对照 | `390×844` | `"true"` | `844 / 844`，横向 `390 / 390` | 单列自适应 | `storyFitsShell: true` | 无回归 |
| `OnboardingWelcome` 欢迎页 | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.onboarding-screen`: `840 / 840` | — | 通过 |
| `OnboardingWelcome` 欢迎页 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.onboarding-screen`: `720 / 720` | — | 通过 |
| `FirstUseWelcome` 聊天空态欢迎页 | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.first-use`: `840 / 840`（零内滚） | — | 通过 |
| `FirstUseWelcome` 聊天空态欢迎页 | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.first-use`: `720 / 720`（零内滚） | — | 通过 |
| `OnboardingPage` 第 1 步（连接电脑） | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.onboarding-card-body`: `724 / 724`（零内滚） | — | 通过 |
| `OnboardingPage` 第 1 步（连接电脑） | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.onboarding-card-body`: `604 / 604`（零内滚） | — | 通过 |
| `OnboardingPage` 第 2 步初态（内置服务商） | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.onboarding-card-body`: `656 / 656`（零内滚） | `footerInViewport: true` | 通过 |
| `OnboardingPage` 第 2 步初态（内置服务商） | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.onboarding-card-body`: `536 / 536`（零内滚） | `footerInViewport: true` | 通过 |
| `OnboardingPage` 第 2 步展开自定义 API | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.onboarding-card-body`: `650 / 536`（仅表体可内滚） | `footerInViewport: true`（`← 返回` + `验证并继续` 固定可见） | 通过 |
| `OnboardingPage` 第 3 步（创建个人助手） | `1280×840` | `"true"` | `840 / 840`（零外滚） | `.onboarding-card-body`: `656 / 656`（零内滚） | `identityPreviewHidden: true`, `footerInViewport: true` | 通过 |
| `OnboardingPage` 第 3 步（创建个人助手） | `1280×720` | `"true"` | `720 / 720`（零外滚） | `.onboarding-card-body`: `536 / 536`（零内滚） | `identityPreviewHidden: true`, `footerInViewport: true` | 通过 |
