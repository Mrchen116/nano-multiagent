# Verification Report: bugfix-577-iphone-viewport-navigation

## Round 1 — full，等待真机问题修复后收口

- reviewer: `/root/review_577_static`，独立，未参与实现；此前 code review 已完成，本轮不重复。
- verification_mode: `full`，同次核对 `corrected-delta`。
- branch: `codex/bugfix-577-iphone-viewport-navigation`
- executed_base: `1daf6676debe129088d9bd0612b489d1eba0301a`
- validated_at: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba`；现场 HEAD 已独立核实一致。
- 范围: 全部 incident Requirement/Scenario、design 决策、M1 R1–R4/W1–W3、delta、相关 current specs 与架构/测试规范。
- requires_full_verification: `false`；本轮已按 full 核对，不是轻量复验。
- 状态: **未通过，待收口**。静态核对没有新增缺陷，但 caller 转交的独立真机观察证明 R3 未满足；收到固定修复版本及完整 regression 后再更新最终 verdict。

### Summary

| 维度 | 结果 |
|---|---|
| Completeness | W1 已有证据；R1/R2/R4/W2 部分证据已到，等待完整 regression；R3 未完成，W3 门禁待关闭 |
| Correctness | 两项 delta 均有实现；真机软件键盘场景出现实际偏离，不能据静态实现判全部 covered |
| Coherence | 5 项 design 决策遵守，架构和测试责任未迁移 |

### Completeness

本 unit 是单 M1，没有独立 tasks.md，使用 design 的退出标准和 progress 交接。未以测试数量替代用户旅程。

| 退出标准 | 实际证据与边界 | 当前状态 |
|---|---|---|
| R1 登录/搜索/聊天输入及跨页比例 | progress 记录 Safari 登录聚焦/结束输入无额外放大；caller 转交产品 reviewer 主屏登录及搜索无裁切；完整跨页矩阵待 regression | 待完整证据 |
| R2 未登录安装、登录、四入口、详情刷新/重新打开 | caller 转交 HTTPS 未登录安装→登录→四入口无系统栏；刷新/再次启动等由产品 reviewer 继续记录 | 待完整证据 |
| R3 真机软件键盘开关、返回、草稿、输入/发送 | caller 转交独立实际发现：standalone composer 聚焦粘贴两行后 header 上移并与状态栏重叠，输入/发送仍完整 | **未通过** |
| R4 Safari 浏览器栏、375/430/600px、桌面1440px | progress 有 375×812、430×430、600×960 真实浏览器渲染/测量摘要；完整 Safari 和桌面证据等待 regression | 待完整证据 |
| W1 focused tests/build、manifest HTTP、字号/viewport | progress 的 8 frontend/6 HTTP tests、build 及真实 HTTP manifest 证据；直接核读实现和测试，完整前端最终日志807 passed | covered |
| W2 must-match 对照、设备/构建记录 | progress 有浏览器截图及构建资产定位；不把镜像硬件输入冒充软键盘，真机最终报告未完成 | 待 regression |
| W3 final tests、CI等价、独立review/verifier | full code review `[]` 已归档；Python4119/front807/build/Ruff/docs检查有可信结果；verifier及产品问题尚未关闭 | 待收口 |

复用可信测试：`PYTHONPATH=src <main>/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal -q` 4119 passed；`npm run test -- --maxWorkers=2` 最终86 files/807 passed/102.73s（独立读取 `output/bugfix-577/frontend-final.log` 结尾）；窄测试和构建命令/结果见 progress。首轮806 passed/1 timeout及独立文件20 passed与最终全量重跑分别记录，不将首轮描述为全绿。全仓Ruff/docs与build结果复用 caller/progress；本轮未重复全量测试、未启动服务、未操作手机或浏览器。

### Correctness

| Requirement / Scenario | 实现位置 | 回归保护/直接证据 | 状态 |
|---|---|---|---|
| delta：输入聚焦后保持比例，结束输入并跨页可用，镜像对齐及主动缩放 | `src/IM/frontend/src/styles/global.css:5594` 手机16px同时覆盖textarea与mirror；`hooks/use-mobile-viewport.ts:12` scale门控 | `app/providers.test.tsx:23,40,54` 覆盖焦点/resize/blur/卸载、桌面、主动缩放及无VisualViewport；progress computed font均16px | 静态 aligned，产品矩阵待齐 |
| delta：浏览器栏/键盘变化下标题返回、输入发送可用，恢复高度，列表安全区和详情隐藏底栏 | `global.css:6,72,76,85,90,5599` 高度/安全区；`hooks/use-mobile-viewport.ts:18` 生命周期；`app/shell/app-shell.tsx` 原有详情隐藏导航 | providers lifecycle tests和既有shell tests；真机header偏移直接反例由caller转交 | **implementation-mismatch（R3）** |
| delta：未登录入口安装、登录、四入口/详情站内导航，保留登录目标 | `public/manifest.webmanifest:2` id/start_url/scope `/`、standalone；`index.html:7`；`src/IM/app.py:216` JSON静态分发；router/auth unchanged | `tests/im_service/unit/test_app_factory.py:157` shell/manifest真实HTTP seam；caller主屏安装及登录四入口实际观察 | 静态 aligned，产品矩阵待齐 |
| delta：已登录再次启动、详情刷新及返回，登录/路由语义保持 | manifest根入口复用 `app/router.tsx` RequireAuth/index Navigate；登录return-to代码未改 | auth/router及完整前端套件保持；设备再次启动/刷新待regression | 静态 aligned，产品矩阵待齐 |
| incident：普通Safari及桌面既有体验保持 | CSS默认100dvh/100vh fallback；16px及safe-area限定767px；hook桌面不覆盖 | providers desktop test，既有shell/auth/composer/draft/history测试在807全量通过；实际Safari/桌面矩阵待regression | 待完整证据 |

current `docs/specs/im/auth-tenancy.md` 的认证协议、自然单列与纵向主操作可达没有被替换；认证页仍有独立纵向滚动，header安全区纳入最小高度。current `web-chat-ux.md` 的composer自动增高、消息历史、按会话草稿及真实anchor行为代码未修改，现有测试保留。没有主动缩放限制或认证fallback。

### Coherence

| design 决策 | 遵守 | 代码证据 |
|---|---|---|
| 1 整站manifest，沿用名称/favicon，根路由分流及深链 | 是 | manifest/index及IM窄静态路由；router/login unchanged |
| 2 手机至少16px，mirror相同metrics，允许主动缩放 | 是 | `global.css:5594` 同一规则；既有textarea/mirror padding/font/line-height/wrapping未分别改写；viewport meta无禁缩放 |
| 3 统一100dvh，100vh基线，布局容器负责safe-area | 是 | `global.css:6,72,76,85,90,451,4928,5599`；移除chat header重复top inset，保留composerbottom inset及认证滚动 |
| 4 AppProviders单hook，仅移动编辑scale≈1覆盖，失焦/卸载清理 | 是 | `main.tsx` 包含全部auth/protected路由的Providers；`providers.tsx:9`；`hooks/use-mobile-viewport.ts:4` 全部监听及清理对应。真实offset问题仍须按证据修复，design已允许该路径 |
| 5 与原生iOS App独立 | 是 | diff没有原生客户端、签名、推送或PA/Gateway/agent变更 |

架构核对：`SPEC.md:148` 的IM与agent/PA/CLI依赖红线未改变；改动仅IM静态分发/前端，无跨包import、REST/WS业务schema或数据库变化。IM manifest handler沿用现有dist候选与FileResponse，未新增通用文件服务器、缓存框架或Service Worker。

测试规范核对：扩展已有app-factory HTTP seam，manifest JSON/MIME可观察，不按私有解析函数或实现调用次数断言；新增providers测试有新的viewport到CSS生命周期owner，直接挂载真实AppProviders并驱动浏览器事件，CSS变量是设计显式公开的布局seam。保留既有AppShell覆盖，无重复新建shell tests、流水号测试或一次性E2E脚本进永久套件。真实iOS CSS/native机制交产品reviewer，不误以jsdom证明。

### Prototype / Reference Contract

verifier只核显式契约与证据链，不替代产品reviewer的视觉判断。

| must-match | M1投影 | 实现证据 | durable evidence | 状态 |
|---|---|---|---|---|
| 登录字段/提交，375/430/600及短高可滚动 | R1/W2 | 全站编辑16px、认证独立滚动、同源高度 | progress 浏览器尺寸/观察/构建资产；完整regression待写 | 待齐 |
| 列表四入口、安全区 | R2/W2 | shell顶部inset、底栏固定安全高度且不缩 | progress及caller转交主屏四入口观察 | 待完整regression |
| 详情返回/输入发送，无全局底栏 | R3/W2 | AppShell原语义、hook同步height、composer保留safe-area | progress短视口草稿；真机header重叠反例 | **未通过** |

### Issues

#### CRITICAL

- **R3 未满足，暂不允许full pass。** 契约：`specs/im/web-chat-ux.md` 的“可用高度随浏览器栏和键盘变化”及 `design.md` M1 R3；实现路径：`src/IM/frontend/src/hooks/use-mobile-viewport.ts:13` 只发布height，`global.css:5599` shell顶部安全区。caller转交独立产品reviewer发现：真实iPhone standalone聚焦composer并粘贴两行后，header上移与状态栏重叠；输入/发送可见不抵消标题返回要求。建议按该实际offset证据修复，冻结新版本，再让产品reviewer复验软键盘开关、标题返回、草稿及跨页恢复；把完整设备/操作/构建/证据定位写入regression后由verifier核对。该条是已观察未完成退出标准，不以静态推测认定某个具体offset补偿算法。

#### WARNING

- 无静态偏离；完整产品矩阵证据尚在交接中，保持待收口状态。

#### SUGGESTION

- 无。

## Corrected Delta Reconciliation

本轮delta未变；按 `executed_base...validated_at` 全部diff核对，未因当前实现错误静默调整spec。

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| 手机输入保持比例、镜像及主动缩放 | 手机16px统一规则；scale门控及清理 | providers三项；真实浏览器字号测量；完整设备跨页待齐 | 静态 aligned，最终产品证据待齐 |
| 可用高度随浏览器栏/键盘变化，标题返回可用 | dvh/CSS统一高度和单hook/safe-area | lifecycle测试有覆盖；实际standalone header重叠反例 | **implementation-mismatch** |
| 主屏未登录安装、站内登录导航、原目标 | manifest整站scope/start/id、JSON MIME路由；auth unchanged | app-factory HTTP、产品reviewer主屏四入口观察 | 静态 aligned，完整矩阵待齐 |
| 已登录再次启动、详情刷新返回 | 同一manifest/root/router及既有Cookie恢复 | full frontend pass；设备完整regression待齐 | 静态 aligned，最终产品证据待齐 |

### Uncovered Observable Behavior

None。统一移动字号覆盖认证/搜索/表单，安全区覆盖导航/认证和聊天，上述delta已覆盖这些消费者行为；新增manifest静态资产是主屏导航契约的接线，不改变业务API。没有遗漏的独立对外行为。

Outcome: **implementation-mismatch**（初轮已转交的R3直接反例；待固定修复版本及regression后重新核对，不将本记录称为最终通过）。
