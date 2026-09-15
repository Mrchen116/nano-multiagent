# feat-561 — 验收报告

> 对齐: `spec.md` 的验收标准

> Validation snapshot: `241db5f79b97eee14e660ce6303582e25acf644f → 57f3c1392e3b73958bac2caa57625f480000528e`
>
> Review round: 1 · Mode: full · Revalidation mode: full

## Verdict

**pass**

- Highest Required Action: `pass`
- Issues: 0（blocking 0 / major 0 / minor 0）
- 验收对象确认为 detached `57f3c1392e3b73958bac2caa57625f480000528e`；该版本前端重新 build 后，由 review worktree 的独立 SQLite、JWT、Gateway config、workspace、node identity 与高位端口 `63118` 提供真实产品入口。
- 浏览器、临时原型 HTTP server、IM 与 Gateway 均已关闭；`63118` / `64415` 无监听，PID、secret、临时 Gateway config 与 channel credential 已清理。

## 用户旅程体验

1. **现代认证入口与页间连续性**：在 1280×800 打开注册、登录，并登录进入 AppShell。三处使用同一 `nano IM` 勾选方形品牌、IBM Plex 视觉、浅蓝灰背景、白色细边框表面、青绿主动作和线性图标；认证页保持聚焦表单，没有复制登录后导航。宽屏为产品语境 + 表单双区；390×844 下变为自然单列，产品能力 chips 收起，注册和登录均无水平溢出。
2. **本地修正闭环**：空注册、空登录均同时显示字段原位错误，焦点进入用户名，认证请求计数保持 0。`poppy / 1234` 注册只在密码字段提示至少 8 位，焦点进入密码，请求计数仍为 0，且不再出现笼统“创建失败”。编辑当前字段后旧错误消失。
3. **真实服务拒绝与异常分层**：真实创建 `accept561r1` 后再次提交，409 在用户名下显示占用提示，用户名、显示名和密码均保留，焦点回到用户名。以客户端拦截复现服务端稳定的 422 `username uses a reserved runtime identity` 时，页面投影为用户名可修正提示，未展示内部原文。注册 503、登录断网/503 均显示可重试的服务提示并保留输入；已存在用户错密码与未知用户得到完全相同的 “The username or password is incorrect.”。
4. **显隐、pending 与语言**：注册和登录的密码按钮均在 `password` / `text` 间切换，值不变、不会提交。注册 pending 时双击只记录 1 个请求；字段、显隐按钮、提交按钮和页脚跳转均停用，locale 仍可用，`Creating…` 立即切成 `创建中…`，输入保持。字段错误与服务错误也会在 EN/中切换时即时翻译；`im_lang=zh` 在 reload 后继续生效。
5. **成功与路由**：注册成功直接进入 `/chat`。从 `/settings/agents?view=work#focus` 未登录进入时先到 `/login`，使用隔离账号登录后精确返回同一 path/query/hash。
6. **窄屏、滚动与无障碍**：375×667 英文空提交后唯一纵向滚动 owner 的 `clientHeight=667`、`scrollHeight=871`、`maxScroll=204`，横向差值为 0；滚到底后主按钮和页脚链接边界均在视口内。错误输入具有 `aria-invalid=true`，`aria-describedby` 同时关联规则/错误文案，首错焦点为 `username`；显隐按钮与提交状态均有可读名称。

独立浏览器截图位于本 review worktree 的 `output/playwright/feat561-acceptance/.playwright-cli/`；用于复核的主要帧为：

- `page-2026-09-15T05-15-19-081Z.png`（1280×800 注册）、`page-2026-09-15T05-15-38-927Z.png`（1280×800 登录）、`page-2026-09-15T05-27-39-705Z.png`（登录后 AppShell）
- `page-2026-09-15T05-24-30-498Z.png`（390×844 中文注册）、`page-2026-09-15T05-24-45-081Z.png`（390×844 中文登录）
- `page-2026-09-15T05-25-21-884Z.png` 与 `page-2026-09-15T05-25-33-664Z.png`（375×667 英文空错误态的焦点位置与滚动底部）

对应 durable milestone 视觉证据为 `M1-auth-form-experience/evidence/register-desktop-en.png`、`register-mobile-zh.png`、`login-desktop-en.png`、`login-mobile-en.png`、`register-short-mobile-errors-en.png` 与 `register-short-password-en.png`；独立重放所得布局和状态与这些同 snapshot 证据一致。

## Reference Artifacts Reviewed

| Reference | Required contract | Actual product evidence | Viewport / state | Comparison conclusion |
|---|---|---|---|---|
| `prototype.html` 新版品牌顶栏、表面与响应式布局 | nano IM 品牌、浅蓝灰/白表面、青绿主动作、线性图标；宽屏双区、窄屏单列、矮屏可滚 | 原型 `page-2026-09-15T05-26-12-925Z.png` / `page-2026-09-15T05-29-13-705Z.png` 对照真实产品 `05-15-19-081Z.png` / `05-24-30-498Z.png` / `05-25-33-664Z.png`；登录后 `05-27-39-705Z.png` | 1280×800 initial；390×844 initial；375×667 errors/bottom | **match**；精确字号/间距的适配仍在 may-adapt 范围，未改变层级与语言 |
| `prototype.html` 表单顺序、hint、可选标记、页脚 | 注册 Username → Display name (Optional) → Password，登录 Username → Password；规则与页脚直观 | 真实注册/登录 snapshot 与 durable 六张截图 | desktop/mobile initial | **match** |
| `prototype.html` 字段错误 | 原位文案、红色边框、首错焦点、编辑清错；短密码和重名归位 | `05-16-44-377Z.png`；snapshot `05-18-07-237Z.yml`、`05-19-50-775Z.yml`、`05-25-20-304Z.yml` | short password / duplicate / server-correctable / empty mobile | **match** |
| `prototype.html` 密码显隐 | 两页均可显隐，值不变、无提交 | snapshot `05-16-58-643Z.yml`、`05-22-35-726Z.yml`，并读取 input type/value | register/login, populated | **match** |
| `prototype.html` EN/中切换 | 输入、字段错误、服务错误、pending 均即时翻译且保留值，选择持久 | snapshot `05-17-19-449Z.yml`、`05-21-03-206Z.yml`、`05-27-03-679Z.yml`；reload 后 `im_lang=zh` | field error / pending / service error / reload | **match** |
| `prototype.html` 页面级错误与 pending | 401 与服务异常可区分；pending 清晰、去重、仅 locale 可继续操作 | snapshot `05-20-09-989Z.yml`、`05-22-49-275Z.yml`、`05-23-06-060Z.yml`、`05-20-52-420Z.yml`、`05-21-03-206Z.yml` | register 503 / login 401 / login network / pending zh-en | **match** |

## 问题清单

无。

## 验收标准覆盖

### Requirement: 认证入口属于当前 Web IM 的现代设计语言 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 桌面端打开注册或登录页 | `spec.md`；`design.md` 原型对齐契约；`prototype.html` | 1280×800 真浏览器打开两页并登录进入 AppShell，对照品牌、层级、图标、主操作与无多余导航 | `05-15-19-081Z.png`、`05-15-38-927Z.png`、`05-27-39-705Z.png` | pass | 与原型 must-match 项一致 |
| 手机端打开注册或登录页 | `spec.md`；`design.md` 原型对齐契约；`prototype.html` | 390×844 真浏览器打开两页，检查单列重排与 `scrollWidth=clientWidth=390` | `05-24-30-498Z.png`、`05-24-45-081Z.png` | pass | 非桌面等比缩放；能力 chips 在窄屏收起 |

### Requirement: 认证表单在提交前说清输入要求 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 新用户查看注册表单 | `spec.md`；`prototype.html` | 桌面/手机初始态检查字段、Optional、留空说明和“至少 8 位” | `05-15-19-081Z.png`、`05-24-30-498Z.png` | pass | 必填与可选含义清楚 |
| 用户需要核对密码 | `spec.md`；`prototype.html` | 两页输入密码，点击 Show/Hide，读取 input type/value 并确认未发请求 | snapshot `05-16-58-643Z.yml`、`05-22-35-726Z.yml` | pass | `password ↔ text`，值原样保留 |

### Requirement: 可在当前字段修正的问题就地给出反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 空注册表单被提交 | `spec.md`；`prototype.html` | 空表单点 Create account，检查两字段错误、active element 与资源请求数 | snapshot `05-16-22-210Z.yml`；`active=username`，register requests=0 | pass | 无请求 |
| 密码不足 8 位 | `spec.md`；用户附图现状 | 输入 `poppy / 1234` 提交，检查字段、焦点、请求和页面文案 | `05-16-44-377Z.png`；`active=password`，register requests=0 | pass | 无“创建失败”笼统提示 |
| 用户修正有误输入 | `spec.md`；`prototype.html` | 将错误密码改为 8 位，并在登录空错后编辑用户名 | snapshot `05-16-58-643Z.yml` 及登录清错 snapshot | pass | 当前字段错误消失，其他待修正错误保留 |
| 空登录表单被提交 | `spec.md` | 空表单点 Sign in，检查两字段错误、焦点与资源请求数 | snapshot `05-15-51-732Z.yml`；`active=username`，login requests=0 | pass | 无请求 |

### Requirement: 服务端拒绝与服务异常给出可区分反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户名已被占用 | `spec.md`；`prototype.html` | 真实注册 `accept561r1` 后重复注册，检查 409 投影、焦点和值 | snapshot `05-18-07-237Z.yml`；`active=username`；三个输入值保留 | pass | 可直接改名重试 |
| 输入被服务端规则拒绝 | `spec.md`；`design.md` 决策 4 | 对有效表单拦截为真实稳定 422 detail，检查字段投影与原文泄漏 | snapshot `05-19-50-775Z.yml`；页面无 `username uses a reserved runtime identity` | pass | 当前语言英文提示 `Choose a different username.` |
| 注册服务暂时不可用 | `spec.md`；`prototype.html` | 注册请求返回 503 + 私有 detail，检查 alert、输入与原文 | snapshot `05-20-09-989Z.yml`；三个输入保留；私有 detail 不可见 | pass | 可重试服务提示，不归因输入 |
| 登录凭据错误 | `spec.md`；current auth contract | 对已存在用户输错密码，再以未知用户名提交，比较提示 | snapshot `05-22-49-275Z.yml`、`05-28-20-432Z.yml` | pass | 两者完全相同，不泄漏存在性 |
| 登录服务暂时不可用 | `spec.md`；`prototype.html` | 对 login 请求模拟网络断开/503，与 401 文案对比 | snapshot `05-23-06-060Z.yml`、`05-27-03-679Z.yml` | pass | 可重试提示与凭据错误明显不同 |

### Requirement: 表单提交和成功跳转保持明确且可控 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 认证请求正在处理 | `spec.md`；`prototype.html` | 延迟 register，双击提交，读取请求命中、控件 disabled、语言切换后的状态 | snapshot `05-20-52-420Z.yml`、`05-21-03-206Z.yml`；hits=1 | pass | 字段/显隐/提交/页脚锁定，locale 可用；登录双击亦 hits=1 |
| 注册成功 | `spec.md` | 在全新隔离 DB 真注册 `accept561r1` | 点击后页面 URL `/chat`，AppShell 成功呈现 | pass | 无需再次输入凭据 |
| 登录成功且存在原始去向 | `spec.md`；`design.md` 决策 8 | 未登录直达 `/settings/agents?view=work#focus`，登录 `nano/nano1234` | 登录前 `/login`；登录后精确 `http://127.0.0.1:63118/settings/agents?view=work#focus` | pass | path/query/hash 均保留 |

### Requirement: 不同设备、语言和操作方式获得一致的认证反馈 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 手机窄屏使用认证表单 | `spec.md`；`design.md` 原型对齐契约；`prototype.html` | 390×844 初始态与 375×667 英文双错误态；检查横向溢出、滚动 owner、底部按钮/页脚矩形 | `05-24-30-498Z.png`、`05-24-45-081Z.png`、`05-25-21-884Z.png`、`05-25-33-664Z.png`；maxScroll=204，horizontal=0 | pass | 所有操作可到达 |
| 键盘或辅助技术用户遇到字段错误 | `spec.md`；`prototype.html` | 空提交后读取 activeElement、aria-invalid、aria-describedby 与控件可读名 | `active=username`；username error；password hint+error；`Show password` / `Create account` | pass | 可见文案与语义一致 |
| 未登录用户切换产品语言 | `spec.md`；`prototype.html` | 分别在字段错误、服务错误和 pending 中切换 EN/中，检查输入、反馈、按钮与 reload | snapshot `05-17-19-449Z.yml`、`05-21-03-206Z.yml`、`05-27-03-679Z.yml`；reload 后 `im_lang=zh` | pass | 值保留，后续认证页继续使用所选语言 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新；未改变跨包职责、拓扑或公共架构边界。
- [x] `docs/specs/im/`（长青行为契约层）：需要更新；`specs/im/auth-tenancy.md` delta 已覆盖本 unit 的认证入口行为，待 orchestrator 收尾归并 canonical。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新；未改变开发或 Agent 工作约束。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新；未修改文档体系。

需要更新的长青契约由本 unit PR 的 canonical merge 提交承载。

---

## Round 2 — Unicode targeted revalidation

> Validation snapshot: `241db5f79b97eee14e660ce6303582e25acf644f → a0cd2225646872ccc1d2569635e9194e1428be40`
>
> Review round: 2 · Mode: targeted · Revalidation mode: targeted
>
> Prior acceptance: Round 1 above (`57f3c1392e3b73958bac2caa57625f480000528e`)

### Verdict

**pass**

- Highest Required Action: `pass`
- Issues: 0（blocking 0 / major 0 / minor 0）
- Needs re-review: `false`
- 仅重验 code review 后受影响的 Unicode 长度语义；Round 1 的其余 19 个 Scenario 未被该修正影响，沿用上轮独立验收证据与结论。
- 验收对象确认为 detached `a0cd2225646872ccc1d2569635e9194e1428be40`。该版本前端重新 build 后，以 review worktree 的独立 SQLite/JWT/Gateway/runtime 和高位端口 `51620` 提供真实 `/register` 入口。

### Targeted 用户旅程

在 390×844 中文注册页一次输入 **33 个 😀 用户名 + 4 个 😀 密码**，然后点击“创建账号”：

1. 提交前用户名完整保留为 33 个 Unicode code point（66 个 UTF-16 code unit），浏览器 input `maxLength=-1`，`aria-invalid=false`。
2. 提交后用户名仍完整保留 33 个 code point，没有被截成 32 个 emoji，也没有出现用户名过长反馈。
3. 4 个 emoji 密码被判定为 4 个字符，而不是按 8 个 UTF-16 code unit 误判通过；密码字段 `aria-invalid=true`，焦点进入 `password`，显示中文“密码至少需要 8 位。”。
4. 页面没有出现笼统“创建失败”，`/im/v1/auth/register` 资源请求数保持 **0**。

真实浏览器证据位于本 review worktree：

- snapshot: `output/playwright/feat561-unicode-r2/.playwright-cli/page-2026-09-15T06-15-32-660Z.yml`
- screenshot: `output/playwright/feat561-unicode-r2/.playwright-cli/page-2026-09-15T06-15-37-278Z.png`
- 结构化观测：`usernameCodePoints=33`、`usernameCodeUnits=66`、`usernameMaxLength=-1`、`usernameInvalid=false`、`passwordCodePoints=4`、`passwordCodeUnits=8`、`passwordInvalid=true`、`active=password`、`localizedMin8=true`、`genericFailure=false`、`registerRequests=0`

### Reference Artifacts Reviewed

本轮不是视觉调整，原型 must-match 面未受影响；真实页面仍呈现 Round 1 已通过的移动端注册布局。Unicode 字符语义以最终 canonical `docs/specs/im/auth-tenancy.md` 的 “Unicode 输入按服务端字符限制处理” Scenario 和真浏览器字段/请求结果为准。

### 验收标准覆盖

#### Requirement: 可在当前字段修正的问题就地给出反馈 — targeted 结论: pass

| Scenario / focus | 期望来源 | 验证方式 | 实际证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Unicode 用户名按字符语义保留 | `specs/im/auth-tenancy.md` “Unicode 输入按服务端字符限制处理” | 真浏览器 fill 33 个 emoji，提交前后读取完整 value、code point/code unit、maxlength 与字段状态 | 33 code point / 66 code unit；`maxLength=-1`；提交前后均 33；`aria-invalid=false`；无过长反馈 | pass | 限制内输入未被浏览器提前截断 |
| 4 个 emoji 密码仍不足 8 位 | `spec.md` “密码不足 8 位”；canonical Unicode Scenario | 与上述用户名组合提交，读取焦点、字段状态、中文文案与 register 请求数 | 4 code point / 8 code unit；`active=password`；`aria-invalid=true`；“密码至少需要 8 位。”；requests=0 | pass | 未按 UTF-16 code unit 误判，也无笼统失败 |

### 问题清单

无。

### 清理与上层文档

- 浏览器和隔离 IM/Gateway 已关闭；端口 `51620` 无监听，PID、secret、临时 Gateway config 与 channel credential 已清理。
- `SPEC.md`、`AGENTS.md` / `CLAUDE.md`、`docs/specs/CONTRIBUTING.md`：无需更新。
- `docs/specs/im/auth-tenancy.md`：最终归档版本已经包含 Unicode 字符语义，无需进一步同步。
