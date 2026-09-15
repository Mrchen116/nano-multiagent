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

# Round 2

> Validation snapshot: `241db5f79b97eee14e660ce6303582e25acf644f → 6fb6bb010d8b01212971315fcf3262d7afbe4399`

## Summary

Mode: targeted-closure

Review round: 2

Fix delta range: `6e645a097ca6721b3f2e7908aa433cbb3742c658..6fb6bb010d8b01212971315fcf3262d7afbe4399`

Focus issues: R1-W1 注册成功的最低层永久测试；R1-W2 已有错误后切语言的回归与 prototype evidence

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 2/2 focus issues 关闭；M1-W2 / M1-W3 的缺失证据已补齐 |
| Correctness | 新测试从页面可观察 seam 断言冻结 WHEN/THEN，不绑定私有实现步骤 |
| Coherence | Followed；本轮只增加既有 auth 测试文件和 evidence 记录，未改共享边界 |

All checks passed. Ready for PR.

## Completeness

- R1-W1 已关闭：`auth-form-experience.test.tsx:136-175` 在真实 `RegisterPage` + memory router 页面 seam mock 201，保护注册请求 payload、auth store/localStorage 持久化和最终 `/chat` 导航。
- R1-W2 已关闭：`auth-form-experience.test.tsx:177-193` 先产生英文短密码字段错误，再通过认证顶栏切中文，断言已显示错误与显密码可读名立即更新，用户名/密码不被清空。`evidence/README.md:35-41` 已把该 must-match 状态列为可复查的最低层自动化证据。
- 本轮 delta 仅修改一个已有 auth 测试文件与 milestone evidence；同期 `acceptance.md` 是产品 reviewer 报告，不改代码/spec/design/delta。没有共享责任、路由或 runtime 变化，因此保留 Round 1 的 full 实现结论，无需 full re-verification。

## Correctness

| Focus / Contract | 实现位置 | 新增证据 | 状态 |
|---|---|---|---|
| 注册 201 后建立 session 并进产品首页（`spec.md:116-118`；M1-W2） | `register-page.tsx:67-76` | `auth-form-experience.test.tsx:136-175`：断言 POST body、store token、`AUTH_STORAGE_KEY` 与 router `/chat` | closed |
| 已显示错误后切语言，错误/控件翻译且输入保留（`spec.md:138-141`；prototype must-match `design.md:171`；M1-W3） | feedback-code state `register-page.tsx:20-30`；locale `auth-page-frame.tsx:13-38` | `auth-form-experience.test.tsx:177-193`；evidence 索引 `evidence/README.md:35-41` | closed |

定向执行：`npm test -- src/features/auth/auth-form-experience.test.tsx --reporter=dot` → 1 file / 9 tests passed。`git diff --check 6e645a097..6fb6bb010` 通过。

## Coherence

| 检查 | 结果 |
|---|---|
| 最低层测试 seam | 两条都从 `RegisterPage` 的用户操作和 router/store/DOM 可观察结果验证，没有直接测私有 feedback 函数或 React state |
| 测试归属 | 扩展既有 `auth-form-experience.test.tsx`，未新增 milestone 命名的平行文件，符合 `docs/development/testing.md` |
| prototype evidence | evidence README 明确记录“已显示反馈翻译且不清输入”的 Claim / Result / Locator，可追到 must-match 状态 |

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（提 PR 前必须修）

无。

### SUGGESTION（可以修）

无。

## Corrected Delta Reconciliation

> Mode: corrected-delta · review round 3 · snapshot `241db5f79b97eee14e660ce6303582e25acf644f → babc3acd10bc53971a494f4a670242b8e7c0bbee`

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/auth-tenancy.md:9-13` 认证入口延续当前 Web IM 设计语言 | `auth-page-frame.tsx:17-64`；`global.css:394-524,748-809` | milestone desktop/mobile/short-viewport PNG 与 `evidence/README.md:11-17` | aligned |
| `:15-18` 注册规则、可选显示名、8 位提示与密码显隐 | `register-page.tsx:110-146`；`auth-form-fields.tsx:70-102` | `auth-form-experience.test.tsx:103-116` | aligned |
| `:20-23` 本地可判定问题原位反馈、首错聚焦、无必然失败请求、编辑清错 | `auth-form-feedback.ts:31-51`；`login-page.tsx:44-51`；`register-page.tsx:51-61` | `auth-form-experience.test.tsx:47-100` | **delta-mismatch**：“包含短密码的认证表单”未限定为注册，会读成登录也执行 8 位下限，但 `validateLogin` 仅校验必填和 256 上限 |
| `:25-28` 重名、错误凭据与服务异常分层且保留输入 | `auth-form-feedback.ts:54-70`；`login-page.tsx:61-64`；`register-page.tsx:77-86` | `auth-form-experience.test.tsx:118-150,229-251` | aligned |
| `:30-33` 服务端可修正输入本地化且不泄露 raw detail | `auth-form-feedback.ts:54-70`；`register-page.tsx:77-84` | `auth-form-experience.test.tsx:136-150` | aligned |
| `:35-38` 未登录语言切换，规则/反馈/pending 即时更新并保值/持久 | feedback-code state `login-page.tsx:23-35` / `register-page.tsx:20-30`；`auth-page-frame.tsx:13-38`；`i18n/index.ts:36-46` | `auth-form-experience.test.tsx:194-209,212-237`；`i18n.test.ts:21-27` | aligned |
| `:40-43` 辅助技术定位错误与控件可读名 | `auth-form-fields.tsx:30-59,72-112`；两页首错 focus | `auth-form-experience.test.tsx:47-71,118-150,194-209` | aligned |
| `:45-48` 认证请求处理中明确状态、去重、locale 仍可切 | 两页 `submitting` guard/disabled；`AuthPageFrame` locale 不读 pending | `auth-form-experience.test.tsx:212-237` | aligned |
| `:50-52` 注册成功保存新 session 并进产品首页 | `register-page.tsx:67-76` | `auth-form-experience.test.tsx:153-192`；`evidence/README.md:19-25` | aligned |
| `:54-57` 登录成功返回完整 path/query/hash | `require-auth.tsx:26-29`；`login-page.tsx:18-20,57-60` | `auth-gate.test.tsx:132-169`；`evidence/README.md:27-33` | aligned |

### Uncovered Observable Behavior

1. **认证字段的长度校验与服务端 Unicode 字符语义对齐，并且不在输入阶段提前截断合法值。** 最终实现在 `auth-form-feedback.ts:27-50` 以 code point 计数镜像后端 Python/Pydantic 的 64/128/256 字符上限，并从 `auth-form-fields.tsx:3-14,39-50,81-93` 移除 HTML `maxLength`，避免浏览器按 UTF-16 code unit 把有效 emoji 输入截断。`auth-form-experience.test.tsx:74-89` 保护 33 个 emoji 用户名不被误判/截断，4 个 emoji 密码仍按 4 字符触发注册下限。这是 unit 最终 diff 新增的用户可观察行为，当前 delta 没有任何长度上限、Unicode 计数或不截断语义，无法从 canonical 契约追溯该修正。

**建议校正：** 在“可本地判定的输入问题原位反馈”中，把短密码明确限定为注册表单，并增加一条消费者可观察结果：字段长度按服务端同一字符语义判定，合法 Unicode 输入不会被浏览器提前截断，超限时才在字段原位反馈。不要把 `Array.from`、UTF-16 或 DOM 属性写入 delta。

Outcome: delta-mismatch
