# M1 — 实施与验证记录

## 2026-10-05 首轮实现

- 基线：`1daf6676d`；在独立 managed worktree `/Users/czj/.codex/worktrees/unit-bugfix-577/nano-multiagent` 实施，分支 `codex/bugfix-577-iphone-viewport-navigation`。
- 使用既有 AppProviders 挂载单一 viewport hook；CSS 默认100dvh（100vh基线），输入时仅手机且无手动缩放才覆盖可视高度；统一16px手机编辑文字和composer mirror，安全区由shell/认证header/既有composer分别拥有。
- manifest覆盖整站，沿用产品名称和favicon；IM增加单独静态路由，没有增加通用文件服务器、Service Worker或认证兼容路径。
- 测试归属：既有`test_app_factory.py`扩展静态HTTP分发风险，保留其它已有覆盖；新增`app/providers.test.tsx`保护全路由接线到CSS的viewport生命周期（原先没有该风险owner）。既有AppShell测试keep。

## 自动验证

修前红测：providers 3项中2项失败（输入resize未发布高度），静态manifest HTTP返回404。实现后：

- `npm run test -- src/app/providers.test.tsx src/app/shell/app-shell.test.tsx`：8 passed。
- `PYTHONPATH=src <main>/.venv/bin/pytest -q tests/im_service/unit/test_app_factory.py`：6 passed。
- `npm run build`：tsc和Vite通过；产物`index-BQ9vVzWe.js` / `index-C57yOulR.css`。
- `PYTHONPATH=src <main>/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal -q`：4119 passed，294.47s。
- `npm run test -- --maxWorkers=2`：806 passed / 1 timeout（既有agent-detail-page skills usage测试5000ms超时）。该文件独立复跑20 passed，原超时用例569ms；不将首轮全量描述为全绿，不因一次超时修改产品/测试超时阈值。
- 串行环境重跑完整前端 `npm run test -- --maxWorkers=2`：86 test files / 807 passed，102.73s；证据`output/bugfix-577/frontend-final.log`，被测代码仍为`e6b202cb8`。
- Python变更Ruff check/format与`git diff --check`通过。
- 真实IM `GET /manifest.webmanifest`：200，`application/manifest+json`，id/start_url/scope均`/`；HTTPS入口亦返回同一构建manifest。

原始本机日志在`output/bugfix-577/`；不提交运行日志、数据库或截图缓存。

## 真实入口与证据边界

- caller真实浏览器375×812：登录字段/按钮完整；聊天详情textarea与mirror computed font均16px、无横向overflow。430×430短视口中两行草稿、返回、发送完整；600×960 Agent列表和四导航完整。截图在本聊天工具结果。
- 同一iPhone Safari的登录框聚焦/结束输入：相对聚焦前画面无额外放大或横向裁切。镜像使用硬件输入，**不替代软件键盘验收**。
- 已从未登录页创建独立`577 fixed`主屏测试图标；添加界面显示manifest指定根启动URL和既有favicon，Open as Web App开启。
- 完整产品使用当前认证的Web Locks，手机明文LAN HTTP不是secure context，主屏根入口无法完成认证初始化。没有给产品加临时认证fallback；改用受信任HTTPS继续验收。此点补充design runbook的真实环境前置，不改变产品设计或Gate 2结论。
- HTTPS只在本机Tailscale私网Serve提供：`https://jmacbook-air.tailbf614e.ts.net:8443/`→隔离IM56142的构建产物；无Funnel/公网发布。用户授权直接操作后caller已连接手机Tailscale，独立产品reviewer正在此HTTPS入口完成主屏与输入验收。

## 隔离服务与清理

- IM56142、Gateway使用本worktree独立DB/config/workspace/node；E2E身份nano/nano1234；Vite18779为辅助入口，prototype18778及RCA18777由caller持有。
- 原`e2e-up`两次连续登录触发现有限流；仅本地临时`scripts/.web577-e2e-up.sh`在readiness登录429时按Retry-After重试。原脚本不改、不提交临时副本。
- HTTPS认证使用当前`IM_PUBLIC_URL`指向上述HTTPS域名；允许的辅助origin限本次本机/LAN测试入口。临时配置不提交。
- 清理：停止本次Serve前台session、Vite session；`./scripts/e2e-down.sh --wt <本worktree>`；停止`web577-e2e`tmux，移除临时启动副本；核实端口与PID释放。尚在验收，当前保持运行。

## 当前退出状态

实施与窄测试完成，待独立产品回归（含真实软键盘）、code review、verification、最终CI和归档；不声称修后真机验收或生产发布完成。

### 后续环境与静态检查

- docs-check：241 maintained sources / 75 required routes通过；全仓Ruff check/format（1134 files）通过；npm critical audit退出0（现有7项非critical依赖告警，未升级依赖）。
- code review在`e6b202cb8`完成，独立审查返回`[]`；详见code-review.md。
- 用户授权直接操作后，caller已通过iPhone Tailscale Connect操作连接现有私网，Mac端确认该iOS peer online。继续通过HTTPS构建入口真机验证。

## R1 实测发现与修复前证据

- pre_fix_head: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba`。产品reviewer明确发现主屏composer硬件焦点令header侵入状态栏；失焦恢复，不是软件键盘已验证。初轮regression fail，静态verification待收口。
- caller在同一隔离构建dist临时加入只读视口采样（不改源码，无消息/凭据内容；GET manifest query留本机日志）。主屏冷启动873px、scale1、offsetTop0、scrollY0；composer焦点稳定后805px、scale1、offsetTop68/pageTop68/scrollY68、header/root top=-68。证据`output/bugfix-577/viewport-samples.log`。明确根因：高度适配之外仍有浏览器焦点平移。
- 修复范围：同一hook在既有编辑条件下发布实际offsetTop，手机根容器relative top跟随；blur/缩放/desktop/unmount清理。design有界修订已交原独立reviewer复核，prototype/需求/milestone不变。
- 定向红测：既有providers可视区域测试增加68px scroll偏移与blur恢复断言，3项中1项因CSS偏移为空失败。
- 本地诊断脚本将在最终build移除；不提交dist/日志。

## R2 冻结与复验

- 冻结`bd170820be5f17f17093189d36290c377b0463ff`；Gate 2有界delta R2 Approved0/0，caller完成Author Resolutions。仅同hook/CSS的实际offsetTop补偿及既有测试增量。
- focused providers+AppShell：8 passed；build通过，新assets `index-B4S4bvwT.js` / `index-D5kI87rP.css`。build已移除本地诊断注入。IM访问日志确认iPhone冷启加载该新构建；caller原焦点复现中header/返回保持在状态栏下。
- R2前端全量：806 passed / 1 failed（既有nodes-page-ws异步元素等待未及时出现，非本unit断言）；独立重跑失败文件1 passed，184ms，`output/bugfix-577/frontend-offset-retry.log`。保留完整首轮失败输出`frontend-offset-final.log`，不修改无关测试。最终远端CI仍须通过。
- docs-check：244 sources / 75 routes通过；git diff --check通过。Python源码在R2未变，复用R1 4119 passed及Ruff证据。
- 独立patch code review返回`[]`；独立产品R2已观察I1关闭，主屏冷启、Safari刷新、群聊mention/设置、草稿/返回通过；软件键盘与双指缩放不能由镜像代测。已将设备交还并向用户发出具体实机短测请求，收到结果后才能关闭I2和verification。
- 为群设置/mention准备隔离API fixture `577 viewport group` (`c_t8c198ge`，nano+e2e)。不把API建群称为手机创建菜单已通过；reviewer提到创建菜单未打开作为独立side finding保留。
