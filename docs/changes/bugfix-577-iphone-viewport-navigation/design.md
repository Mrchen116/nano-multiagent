# bugfix-577: iPhone 输入与主屏导航 — 技术方案

> 对齐：[incident.md](incident.md)，2026-10-04 定稿。单 M1，Full Bugfix。

## Changelog

## 现状分析

### 涉及范围

前端 `index.html` 是所有 SPA 路由入口；`public/` 当前只有 favicon。`global.css` 负责 shell、认证、搜索、聊天 composer；`AppShell` 持有移动导航并在具体会话隐藏底栏；`AuthPageFrame` 是独立认证页。`AppProviders` 包裹全部路由，可挂载一次通用视口生命周期。

本次源码基线 `d21848653`；线上故障资源与同设备单变量实验详见 incident 的证据表。线上部署 revision 不由本地 SHA 推定。

### 既有约束

仅改 IM 前端；不改认证、消息、Gateway 或内核契约。保持 `<768px` 移动断点、聊天详情隐藏全局底栏、登录深链和桌面布局。用户主动缩放保持可用。本 unit 不增加原生 iOS App、Service Worker、缓存框架或签名维护服务；独立 iOS App 按用户后续明确要求由并行 feat-578 负责。

### 可复用能力

- 复用既有 CSS tokens、AppShell flex 结构、`min-height:0` 的内容滚动区、认证页独立滚动、composer 自动增高。
- 在已有手机样式中修正字号与容器高度，composer textarea 与文字镜像使用同一字号；不再造移动组件。
- 浏览器 `visualViewport` 仅作为手机输入期间的高度来源，新增一个窄 hook 统一监听和清理；不让每个表单或页面各算一套。
- Manifest 使用 Vite public 资产分发；不引入 PWA 插件。后端已有 SPA/static serving 需实查返回 JSON MIME，必要时仅为 manifest 补静态路由（不能返回 HTML fallback）。

### 相关历史

feat-340 建立移动单栏及底栏，feat-451 确立 composer 自动增高与手机输入发送。刚合并的 bugfix-576 改善浏览器认证，必须保留其 cookies/refresh/session 行为；本 unit 不用更换认证机制来处理导航工具栏。

## 架构总览

现有 SPA 页面和路由不变。静态 manifest 让主屏应用明确覆盖 `/` 下所有 IM 路由；CSS 将“大视口高度”改为“当前可用高度”，并给底栏安全区留白。输入期间的小型视口 hook 补齐 iOS 软键盘只缩小 visual viewport 的差异。

## 关键决策

1. **声明一个覆盖整站的主屏应用。** Manifest 固定 `id: /`、`start_url: /`、`scope: /`、`display: standalone`，名称沿用 `IM Frontend`，复用现有 favicon；此 unit 不改品牌。`/` 仍由当前 router/auth gate 分流，登录 return-to 行为保持。范围外链接继续遵守 current 外链行为。已按旧入口安装的图标可能需要一次重新添加才能获得安装配置；不得假装远端 HTML 能可靠改写旧安装记录。
2. **手机可编辑文字至少 16px，保持镜像排版一致。** 覆盖登录/注册、搜索、表单 input、textarea、select；针对已有 inline 小字号控件使用限定于移动断点的统一规则，必要的优先级仅用于这个平台约束。composer 镜像跟随同一值，line-height/padding/wrapping 保持匹配。不加 `user-scalable=no` 或最大缩放限制。
3. **CSS 默认用 100dvh，安全区由布局容器负责。** body/root/shell 不再各自锁死100vh，使用统一可用高度变量，兼容基线值为100vh、支持时100dvh。移动 shell 顶部留安全区、底栏高度包含 bottom inset且不收缩；具体会话沿用 composer bottom inset。认证页保持可滚动，主内容最小高度与同一高度来源一致。检查现有 header 局部 safe-area，避免重复计入。
4. **软件键盘高度只在手机编辑期间跟随 visualViewport。** 统一 hook 在 AppProviders 挂载，监听 focusin/focusout、visualViewport resize/scroll、window resize和pageshow；仅当 `<768px`、有可编辑焦点、scale 约为1时发布可视高度变量。失焦/桌面/缩放时移除覆盖，回归CSS高度；卸载移除监听。更新可以合并到 requestAnimationFrame。只调整高度，不做全局 touch 禁用、固定机型键盘高度、周期性强制scrollTo或根节点position:fixed。真机若出现独立可复现的 viewport offset 问题，再按证据修订；不先堆多层补偿。
5. **Web 修复与原生 App 独立推进。** 输入字号、100dvh及显式manifest已取得同机有效对照，577 继续修复现有 Web 入口。用户明确要求即使没有新增特性也要 iOS App，已另开 feat-578 与独立 chat；免费签名、Mac mini AltServer 续签和通知能力由该 unit 决策，不成为 577 的前置依赖。

## 接口与数据流

- `public/manifest.webmanifest` 由 `index.html` link 同源引用；无需任何登录令牌，正常 JSON 类型，不缓存旧 HTML。
- `useMobileViewport`（命名可依项目惯例）无外部参数，唯一作用是维护根元素 `--im-viewport-height` 临时覆盖。CSS 通过 `var(--im-viewport-height, 100dvh)` 使用；不读取或保存表单内容、身份、消息。
- 页面加载 → CSS决定视口/安全区 → 聚焦手机可编辑控件 → visualViewport改变 → CSS高度同步、flex内容区缩小 → blur → 清理覆盖、恢复正常高度。
- 带缩放的 visualViewport 不用于缩小 app shell；正常用户缩放由浏览器负责。
- 无 REST/WS/schema 变化。测试组件应覆盖挂载接线、焦点生命周期、无VisualViewport、手动缩放和清理，CSS/native机制依真机与真实浏览器验证。

## 前端原型

文件：[prototype.html](prototype.html)。用户需要判断：现有登录字段、聊天输入区和四入口导航在可用高度变化后是否仍完整可操作；没有新的产品信息架构。

呈现采用“现有页面背景 + 局部对照”：显示认证表单、聊天列表和聊天详情的最小必要上下文。外层单独切换模拟可用高度/键盘；产品区域只保留原有操作与文案。模拟键盘仅表示空间占用，不声称浏览器仿真出了iOS行为。

| 当前入口 / 组件 | 画面和样式依据 | 必须继承 | 增量 |
| --- | --- | --- | --- |
| Login / AuthPageFrame | 当次iPhone登录截图；global.css认证样式 | 白色卡片、teal主操作、用户名/密码/登录/注册链接 | 输入16px；窄屏滚动与边界完整 |
| Chat列表 / AppShell | 当次iPhone列表截图；AppShell四tab、global.css | 搜索、会话条目、Chat/Tasks/Agents/Me | 底栏留安全区，不被可用高度挤出 |
| Chat详情 / MessagePane | 当次iPhone聊天截图；global.css composer/header | 返回、消息内容、底部composer，详情无全局tab | 输入保持可见、字号镜像对齐 |

### 原型对齐契约

| 区域 / 状态 | 级别 | 产品入口 | 必验宽度 / 状态 | 投影 |
| --- | --- | --- | --- | --- |
| 登录输入和提交可达 | must-match | /login、/register | 375、430、600px；输入、内容滚动 | M1 R1/W2 |
| 列表四入口可达、安全区 | must-match | /chat、/tasks、/settings/agents、/me | iPhone普通/主屏；375、430px | M1 R2/W2 |
| 详情返回/输入与发送完整，无全局底栏 | must-match | /chat/:id | 键盘开/关、跨页、375、430px | M1 R3/W2 |
| 背景样例会话文本、外层演示控件 | out-of-scope | 无 | 只示意空间；真实产品沿用实际数据 | 不新增产品功能 |
| 非输入文字的精确间距和字体渲染 | may-adapt | 所有 | 沿用现有tokens，不作品牌重设计 | M1 R4 |

### 原型走查

2026-10-04 作者使用真实浏览器渲染 `http://127.0.0.1:18778/prototype.html`，检查 1440×900、375×812、430×932、600×960。截图见当次会话浏览器截图证据。1440px 三列、窄屏单列均无横向裁切；短高度下登录按钮经表单内滚动可达；四导航保留在底部；键盘占位开启时详情返回与输入/发送完整可见。输入两行草稿后 textarea 增高，关闭占位/恢复高度后文字保留。键盘占位与浏览器尺寸只验证布局表达，不证明真机软键盘或 iOS standalone 导航已经修复。独立 reviewer 可在同 URL 复查，静态源为本文件相邻 prototype.html。

## 契约层增量

- [specs/im/web-chat-ux.md](specs/im/web-chat-ux.md)：手机输入比例、主屏导航、可视区域及键盘变化下的可用性。完成后归并到 `docs/specs/im/web-chat-ux.md`。
- 认证字段也遵守上述通用规则；不重复建立auth协议需求。

## 风险与回退

- 旧安装记录可能不采纳新manifest；新安装与旧安装恢复路径分开记录。最少允许一次重新添加，不把它变成每次使用的步骤。
- dvh不代表键盘高度，hook应保留手动缩放；真机实测优先于CSS推论。若证据出现viewport offset残留，暂停该验收项并修正明确原因，不引入未经验证的补丁组合。
- 统一16px可能影响窄输入宽度和composer高亮；单独检查真实渲染，桌面规则不变。
- 回退只撤回本unit前端/manifest改动，无数据库迁移。生产更新不在本轮授权内。

## Runbook for Reviewer

无新增常驻服务；本次修改前端静态产物。验收使用独立worktree的真实IM+Gateway和静态前端，禁止使用生产账号/数据；由caller集中准备并给出实际URL、端口、构建SHA、测试用户和本机凭据文件路径。

| 服务 | 停止 | 启动 | 检查 |
| --- | --- | --- | --- |
| 隔离 IM + Gateway | `./scripts/e2e-down.sh --wt "$WT_ROOT"` | 在受控tmux里，以主仓.venv加入PATH后 `./scripts/e2e-up.sh --wt "$WT_ROOT"` | `.e2e-ports.env` 的IM_URL/openapi.json；Gateway健康 |
| 前端构建 | 无进程 | `cd src/IM/frontend && npm ci && npm run build` | index与manifest从隔离服务返回；assets对应构建 |
| 可选Vite验收入口 | 只停止本unit记录的PID/session | `VITE_IM_PROXY_TARGET="$IM_URL" npm run dev -- --host 0.0.0.0 --port <空闲高位端口>` | iPhone同一局域网可达，proxy仅到隔离IM |

**Review驱动方式**：端到端真栈，必须驱动真实客户端。走登录→四入口→聊天输入→返回→搜索→Agent工作→主屏再启动；不以API或DOM代替移动渲染。桌面375/430/600/1440px辅助检查，iPhone 15 Pro Max/iOS26.4为决定性平台。

**验收前置**：该iPhone已通过镜像连接，同LAN HTTP实验已可达且成功安装两个临时主屏应用；真实产品隔离账号由e2e脚本准备。软件键盘需要用户在真机配合短测（镜像硬件键盘不能替代），到被测构建就绪再交接具体操作；没拿到这项实测不允许产品验收通过。测试不需要Apple付费账户，不发真实外部平台消息。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
| --- | --- | --- | --- | --- | --- |
| M1-mobile-viewport | 恢复iPhone输入与站内导航可用性 | 无 | 无 | frontend index/public/global.css/AppProviders/hooks及最低层测试；IM静态manifest接线（如需）；unit证据 | [reviewer] R1 登录/搜索/输入无自动放大且跨页不裁切；R2 主屏登录、四入口、详情刷新/重新打开无系统栏侵入；R3 真机软件键盘开关时输入/发送可见，返回可用且草稿保持；R4 Safari工具栏、375/430/600px及桌面1440px不回归；[worker] W1 focused tests/build、manifest真实HTTP接线、手机字号及viewport测量；W2真实截图/原型must-match对照和设备/构建记录；W3 final窄测试、相关CI等价、独立review/verifier完整闭环 |
