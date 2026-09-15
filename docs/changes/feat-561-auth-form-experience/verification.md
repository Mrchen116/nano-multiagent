# Verification Report: feat-561

> Validation snapshot: `241db5f79b97eee14e660ce6303582e25acf644f → 57f3c1392e3b73958bac2caa57625f480000528e`

## Summary

Mode: full  
Review round: 1  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 19/19 scenario 有实现；M1 8 项退出标准中 6 项完整可证、2 项回归证据不完整 |
| Correctness | 19/19 scenario 的实现与冻结 spec 一致；2 条稳定风险缺最低层保护 |
| Coherence | Followed |

0 critical issue(s), 2 warning(s), 0 suggestion(s) found. Fix before PR.

实现已正确解决用户附图中的核心问题：4 位密码在客户端落到密码字段提示且不发请求，重名、401 与服务异常分层处理，登录/注册页也已迁移到当前 nano IM 视觉语言。阻塞项是 design M1 明确要求的永久回归保护尚有两个缺口，不是缺功能。

## Completeness

- Tasks: 简化流程未建 `tasks.md` / `progress.md`，按 `design.md:202-206` 的唯一 M1 退出标准核对。M1-R1、R2、R3、R4、R5 和 M1-W1 有代码、测试或真浏览器 evidence；M1-W2 缺注册成功页面 seam 测试，M1-W3 缺“已有错误后切语言”的自动化/真浏览器证据。
- Spec 覆盖：6 条 Requirement / 19 个 Scenario 均有实现；未发现缺实现或改动后端规则、JWT/租户语义。
- 受影响旧测试：`auth-gate.test.tsx` 被 rewrite-merge 以匹配新密码按钮语义并加入完整深链；`app-shell.test.tsx` 保留品牌/导航回归；后端 auth route 测试保留。新建 `auth-form-experience.test.tsx` 聚合认证页可观察行为，未按 milestone 拆散文件，符合 `docs/development/testing.md`。
- 独立验证执行：定向 17/17 通过；全前端首轮并发执行时一条未改动的 chat integration 等待超时，该文件单独 52/52 通过，随后非并发全前端 83 files / 767 tests 通过；Vite/TypeScript build 通过（仅已有 chunk-size warning）；Python auth integration 7/7 通过；docs-check 和 diff-check 通过。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试 / evidence | 状态 |
|---|---|---|---|
| 现代设计语言 / 桌面 | `auth-page-frame.tsx:17-63`；`global.css:394-524` | `evidence/register-desktop-en.png`、`login-desktop-en.png` | covered |
| 现代设计语言 / 手机 | `global.css:748-809` | 390×844 两页截图；375×667 错误态截图/测量 `evidence/README.md:11-17` | covered |
| 注册必填/可选/8 位规则可见 | `register-page.tsx:111-149` | `auth-form-experience.test.tsx:75-88`；桌面/手机截图 | covered |
| 注册或登录密码显示/隐藏不改值 | 两页共用 `auth-form-fields.tsx:73-106` | `auth-form-experience.test.tsx:75-88` | covered |
| 空注册原位错误、首错聚焦、无请求 | `register-page.tsx:51-61`；`auth-form-fields.tsx:32-63` | `auth-form-experience.test.tsx:36-61` | covered |
| 4 位密码原位提示且无请求 | `auth-form-feedback.ts:37-47`；`register-page.tsx:51-61` | `auth-form-experience.test.tsx:51-60`；`evidence/README.md:19-25` | covered |
| 编辑错误字段清除旧反馈 | `login-page.tsx:37-42`；`register-page.tsx:32-38` | `auth-form-experience.test.tsx:51-54` | covered |
| 空登录原位错误、首错聚焦、无请求 | `login-page.tsx:44-51` | `auth-form-experience.test.tsx:63-73` | covered |
| 注册重名落 username，其他输入保留 | `auth-form-feedback.ts:50-66`；`register-page.tsx:77-87` | `auth-form-experience.test.tsx:90-106`；`evidence/README.md:19-25` | covered |
| 服务端可修正输入本地化且不暴露 raw detail | `auth-form-feedback.ts:50-66`；`register-page.tsx:77-84` | `auth-form-experience.test.tsx:108-123` | covered |
| 注册服务异常是可重试 alert，不清输入 | `register-page.tsx:77-87,150` | `auth-form-experience.test.tsx:125-150` | covered |
| 401 不区分用户名/密码 | `login-page.tsx:61-64` | `auth-gate.test.tsx:114-130`；`auth-form-experience.test.tsx:152-174` | covered |
| 登录服务异常与 401 可区分 | `login-page.tsx:61-64` | `auth-form-experience.test.tsx:152-174`；`evidence/README.md:27-33` | covered |
| pending 文案明确且阻止重复请求 | `login-page.tsx:44-65,97-117`；`register-page.tsx:51-87,119-154` | `auth-form-experience.test.tsx:125-150`；真浏览器结论 `evidence/README.md:27-33` | covered |
| 注册成功建 session 并进产品首页 | `register-page.tsx:67-76` | 真浏览器一次性证据 `evidence/README.md:19-25`；**无最低层永久测试** | implemented; warning |
| 登录返回完整 path/query/hash | `require-auth.tsx:26-29`；`login-page.tsx:18-20,57-60` | `auth-gate.test.tsx:132-169`；`evidence/README.md:27-33` | covered |
| 矮视口错误态无横向滚动且纵向可达 | `global.css:394-456,748-809` | `register-short-mobile-errors-en.png`；尺寸数据 `evidence/README.md:13-17` | covered |
| 字段状态/文案/聚焦与控件可读名 | `auth-form-fields.tsx:32-63,75-117`；`auth-page-frame.tsx:20-38` | `auth-form-experience.test.tsx:36-88,90-123` | covered |
| 认证页切语言立即更新且保留值/持久化 | 反馈 code 在 `login-page.tsx:23-35` / `register-page.tsx:20-30`；切换 `auth-page-frame.tsx:13-38`；持久化 `i18n/index.ts:36-46` | pending 切换/保值 `auth-form-experience.test.tsx:125-150`；持久化 `i18n.test.ts:21-27`；**无已显示 field/form error 后切换证据** | implemented; warning |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. 共享 48px 品牌顶栏 + 宽屏双区/窄屏单列，auth frame 自持纵向滚动 | 是 | `nano-brand.tsx:5-30`；`auth-page-frame.tsx:17-64`；`global.css:394-524,748-809` |
| 2. `noValidate` + 本地受控校验，服务端仍权威 | 是 | `auth-form-feedback.ts:27-47`；`login-page.tsx:44-58,88`；`register-page.tsx:51-74,110` |
| 3. state 存 feedback code，render 时翻译 | 是 | `login-page.tsx:23-35`；`register-page.tsx:20-30` |
| 4. 字段与页面错误分层，只投影稳定结果，不显示 raw detail | 是 | `auth-form-feedback.ts:50-66`；`login-page.tsx:61-64`；`register-page.tsx:77-84` |
| 5. 编辑只清当前字段和旧页面错误 | 是 | `login-page.tsx:37-42`；`register-page.tsx:32-38` |
| 6. submit 仅 pending 禁用；pending 锁字段/显隐/页脚，locale 可用 | 是 | `login-page.tsx:44-46,76-80,97-117`；`register-page.tsx:51-53,98-102,119-154`；`auth-page-frame.tsx:20-38` |
| 7. auth 顶栏复用现有 locale store | 是 | `auth-page-frame.tsx:4,13-38`；`i18n/index.ts:36-46` |
| 8. guard 生产完整内部 URL，login 原样消费 | 是 | `require-auth.tsx:17,28`；`login-page.tsx:18-20,60` |

依赖边界抽查：diff 仅修改 IM frontend 和 unit evidence，未新增 `agent` / `coding_cli` / `personal_assistant` import，未改 backend auth 或数据迁移；符合 IM 与内核隔离红线。

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 品牌顶栏、表面/主动作/线性图标，宽屏双区/窄屏单列，375×667 长错误可滚 | M1-R1 / M1-W1 | `auth-page-frame.tsx:17-64`；`global.css:394-524,748-809` | 1280×800、390×844、375×667 PNG + `evidence/README.md:11-17` | covered |
| 字段顺序、hint、可选标记、页脚跳转 | M1-R1 / M1-W1 | `login-page.tsx:68-119`；`register-page.tsx:90-156` | 登录/注册 desktop+mobile PNG | covered |
| 字段错误、错误边框、首错聚焦、编辑清错 | M1-R2 / M1-W2 | `auth-form-fields.tsx:32-63`；两页 submit/update | 错误态 PNG + 定向测试 | covered |
| 密码显示/隐藏不丢值 | M1-R3 / M1-W2 | `auth-form-fields.tsx:73-106` | `auth-form-experience.test.tsx:75-88` | covered |
| 有输入且已有错误时切中/英，值和错误保留并翻译 | M1-R4 / M1-W3 | feedback-code state + `AuthPageFrame` locale | 仅有 pending 中切换，无已有错误态的截图/测试 | warning |
| 页面级凭据/服务错误与 pending | M1-R5 / M1-W2 | 两页 catch/pending 分支 | 定向测试 + `evidence/README.md:27-33` | covered |
| 字体、精确间距、icon 绘制 | may-adapt | 全局 token / IBM Plex fallback / 线性 SVG | 现有 PNG | covered |

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

1. **注册成功的 session 入库与首页跳转没有最低层永久回归保护。** `spec.md:116-118` 要求注册成功直接进入已登录产品，`design.md:142-147,206` 且明确要求 M1-W2 在最低层页面 seam 覆盖“成功导航”。代码 `register-page.tsx:67-76` 实现正确，真浏览器一次性记录也说明曾成功，但现有永久测试只保护 login 的 session/navigation（`auth-gate.test.tsx:87-112,132-169`），`RegisterPage` 没有成功分支测试。这是 testing.md 所说的稳定用户行为且能在页面 seam 最低层观察，不应只依赖一次性 evidence。  
   **怎么改：** 扩展 `auth-form-experience.test.tsx` 或合并到现有 auth gate 页面测试：mock 201 token pair，从 `/register` 提交合法表单，断言 register 请求 payload、auth store/localStorage 已写入，且 router 最终进入产品首页（当前可观察为 `/chat`）。

2. **prototype must-match 与 M1-W3 要求的“已有错误时切语言”没有可复查证据或回归测试。** `design.md:163-173,206` 把“有输入且已有错误”列为 must-match，并要求静态/错误/pending 都立即翻译且不重置表单。实现把 feedback code 存在 state（`login-page.tsx:23-35`，`register-page.tsx:20-30`），所以代码推导正确；但现有测试是在 pending 中先切换为中文，再收到 503 错误（`auth-form-experience.test.tsx:125-150`），不能防止将来把已存在的 field/form error 回归为预翻译字符串；evidence 也没有这个 must-match 状态。  
   **怎么改：** 在 `auth-form-experience.test.tsx` 用一条端到端页面状态测试先产生 field error（或 401/service alert），保留已输入值，再点击中文，断言错误、密码显隐可读名与表单值立即更新/保留；并在 evidence README 记录与原型这一行的对照结论。无需新增第二个测试文件。

### SUGGESTION（可以修）

无。

## Corrected Delta Reconciliation

N/A（`verification_mode=full`）
