# feat-561: 认证表单交互体验提升 — 技术方案

> 对齐: spec.md v3

## Changelog

## 现状分析

### 涉及范围

- `src/IM/frontend/src/features/auth/login-page.tsx` 与 `register-page.tsx` 各自持有表单值、单个页面级错误和提交状态；两页都使用 `noValidate`，但没有自定义本地校验。`require-auth.tsx` 当前只将 `location.pathname` 存入登录去向，会丢失受保护深链的 query/hash。
- `src/IM/frontend/src/features/auth/auth-api.ts` 已把非 2xx 响应收敛为携带 `status` 和字符串 `detail` 的 `AuthApiError`；注册页只识别 409，登录页只识别 401。
- `src/IM/frontend/src/i18n/` 已有中英文资源、本地持久化和 `setLanguage()`，但未登录路由没有语言入口。
- `src/IM/frontend/src/styles/global.css` 顶部已定义新版全局 token、IBM Plex 字体、品牌青绿与浅蓝灰表面；认证区的 `im-auth-*` 仍是改版前的居中泛化卡片。
- `src/IM/frontend/src/app/shell/app-shell.tsx` 内联定义当前勾选方形品牌标、`nano IM` 和 `internal` badge；桌面顶栏、用户菜单和移动底栏是用户指定的近期视觉基线。
- `src/IM/application/auth_service.py` 与 `src/IM/api/routes/auth.py` 是最终认证规则权威：用户名/显示名非空、密码至少 8 位、运行身份名称保留、重名拒绝；不改这些规则。

### 既有约束

- IM 不调用 `agent`，本 unit 仅在 IM 前端认证入口工作，不改包间依赖。
- 前端继续通过 `/im/v1/auth/*` 真实入口登录/注册，不以本地校验取代服务端校验。
- 错误凭据不区分“用户不存在”和“密码错误”，保持现有防用户枚举语义。
- 认证页必须从旧 `im-auth-*` 外观迁移到当前 Web IM 的品牌、token、字体、线性图标、细边框与响应式节奏；不把登录后的 Chat/Agents/用户导航伪造到未登录页。
- 全局 `body` 与 `#root` 锁定为 `100vh`，`body` 使用 `overflow: hidden`；认证 frame 必须自己拥有纵向滚动，不改登录后 AppShell 的滚动责任。
- 浏览器验收必须在隔离 worktree 内使用高位端口、独立 SQLite/JWT/runtime，不触碰生产 `:8011` 或个人 Gateway 配置。

### 可复用能力

- **用** `AuthApiError`、`login()`、`register()` 和 `useAuthStore.setSession()`：请求与会话入库路径不变。
- **用** `getCurrentLanguage()` / `setLanguage()` / `useTranslation()`：未登录语言切换复用现有持久化，不建第二份 locale store。
- **改** 现有 `im-auth-*` CSS：使用新版全局 token 重组为品牌顶栏、产品语境区和表单面板，并加入字段辅助文案、错误态、密码组合输入。
- **抽取并复用** `NanoBrand`：将 AppShell 内联的品牌标识与文字收敛为小组件，认证页与登录后顶栏共用同一标识，不复制 SVG。
- **改** `auth-gate.test.tsx` 中登录成功/失败覆盖，并在同一 auth feature 下增加页面行为测试；不为同一校验原因在 Python integration 再复制一层。
- **不用** 新表单库或新状态容器：字段数少，React 本地 state 已足够。

### 相关历史

- feat-340 引入现有 JWT 注册/登录页与路由守卫，当时主要闭环认证功能，没有字段级反馈。
- feat-554 将多用户注册正式接入生产协作流程，使用户自注册成为实际入口；本 unit 不改其租户、成员或资源归属规则。

## 架构总览

页面继续拥有业务流程和导航，两个小而有界的内部模块集中处理重复复杂度：

| 责任 | 拥有者 | 向页面暴露的表面 |
|---|---|---|
| 当前产品品牌标识 | `app/shell/nano-brand.tsx` | `NanoBrand`，供 AppShell 与认证顶栏复用 |
| 未登录页品牌顶栏、产品语境区、表单面板和 locale | `auth-page-frame.tsx` | `AuthPageFrame` |
| 字段布局、hint/error 关联、`aria-invalid`、密码显隐 | `auth-form-fields.tsx` | `AuthTextField` / `AuthPasswordField` |
| 稳定输入规则、字段错误代码、服务错误投影 | `auth-form-feedback.ts` | `validateLogin` / `validateRegistration` / `registrationFeedbackForApiError` |
| 表单值、提交状态、聚焦第一个错误、API 调用和成功导航 | `login-page.tsx` / `register-page.tsx` | 路由页面，不再向下泄漏 |
| 受保护访问的完整内部去向 | `require-auth.tsx` 生产，`login-page.tsx` 消费 | `pathname + search + hash` 字符串 |
| locale 切换与持久化 | 现有 `i18n/index.ts` | 页面上的 `AuthLocaleSwitch` 调用现有 `setLanguage()` |

这个边界把共享的产品身份、未登录页结构和可访问字段细节各藏在一处，而不把整张登录/注册表单抽成需要大量配置的通用表单引擎。

## 关键决策

**1. 认证页使用“共享品牌顶栏 + 产品语境 + 独立表单面板”的当前 Web IM 布局。**

桌面端保留与 AppShell 同高度、同边框的 48px 品牌顶栏，顶栏左侧复用 `NanoBrand`，右侧使用已有 `EN | 中` 语言语法。主区在宽屏上以两栏表达：左侧只用简短产品定位与三个可扫读能力标签提供注册语境，右侧是白色细边框表单面板。手机端保留品牌顶栏，压缩语境为标题/一句说明，表单变为自然单列表面，而非缩小桌面双栏。

新布局只使用现有 CSS token、IBM Plex 字体和线性 SVG，不新建第二套设计 token，也不加入与任务无关的动画或插画。

`AuthPageFrame` 根节点在 `#root` 内使用 `height: 100%` / `min-height: 0` / `overflow-y: auto`，顶栏 sticky，主区可随内容自然增高。这使英文长文案、多个字段错误和移动软键盘改变可用高度时，用户仍能纵向滚到主按钮与页脚。本 unit 不改全局 `body` 或 AppShell CSS。

**2. 保留 `noValidate`，用本地化的受控校验取代浏览器默认气泡。**

注册在提交时校验用户名必填/最大 64 字符、保留运行身份、显示名最大 128 字符、密码 8–256 字符；登录校验用户名和密码必填及对应最大长度。校验通过后仍由服务端权威判定。保留 `noValidate` 可避免同一页面在不同浏览器中出现不可控、不一致语言的原生错误。

**3. state 存“反馈代码”而不是已翻译文案。**

`FieldErrors<Field>` 是字段名到反馈代码的稀疏映射，页面级错误也保存代码。渲染时才经 `t()` 取得文案，因此错误显示中切换语言会立即更新，无需重新触发校验。

**4. 字段反馈和页面错误分层，只对已知稳定服务结果做投影。**

- 可在当前输入修正的问题进字段：本地校验、注册 409 重名，以及现有服务明确返回的密码长度/保留用户名拒绝。
- 无法归因到单一字段的问题进卡片内页面级 alert：登录 401 统一凭据错误，连接失败或未知服务错误为可重试故障。
- 不直接显示服务端 `detail`。`registrationFeedbackForApiError()` 是唯一翻译边界，无法识别的结果回到通用服务错误。

不为本 unit 新增后端错误 schema：现有 409 已稳定表达重名，其余已知规则都能在请求前被对齐校验；为一个小表单另建错误协议会扩大跨层面积。

**5. 用户编辑字段时清理该字段错误和旧页面错误，不在每个按键上连续校验。**

提交时一次展示所有字段错误并聚焦第一项；编辑时只清理与旧值关联的反馈，不用新错误追着每个未完成输入。这样同时满足“及时消失”与“不边输入边责备”。

**6. 提交按钮在输入不完整时仍可用，仅在请求处理中禁用。**

可用按钮让用户能主动触发并看到完整校验，避免一个没有原因的灰按钮。请求开始后锁定字段、密码显隐、页脚跳转和提交按钮，防止重复提交或响应期间切页。语言切换仍可用：它只更新本地文案，不改正在发送的 payload。

**7. 语言切换是认证品牌顶栏的轻量控件，直接复用现有 locale store。**

切换只改界面语言，不重置页面组件，因此已输入值、密码可见状态和反馈代码都保留。控件仅有中文/English 两项，不引入下拉菜单依赖。

**8. 路由守卫保存完整内部 URL，登录页仍使用一个字符串去向。**

`RequireAuth` 把 `location.pathname + location.search + location.hash` 存入 `state.from`；`LoginPage` 成功后原样交给 router `navigate(from, {replace:true})`。这不引入新路由抽象，但能保住聊天 `?message_id=`、Agent `?view=work` 和 hash 深链的真实意义。`from` 只由内部 route guard 生成，不接受外部 URL 或查询参数作为跳转目标。

## 接口与数据流

### 内部类型与组件接口

```ts
type AuthFeedbackCode =
  | "required"
  | "tooLong"
  | "passwordTooShort"
  | "reservedUsername"
  | "usernameTaken"
  | "invalidCredentials"
  | "serviceUnavailable";

type FieldErrors<Field extends string> = Partial<Record<Field, AuthFeedbackCode>>;

type AuthTextFieldProps = {
  id: string;
  label: string;
  optionalLabel?: string;
  value: string;
  onValueChange: (value: string) => void;
  autoComplete: string;
  hint?: string;
  error?: string;
  inputRef?: Ref<HTMLInputElement>;
  disabled?: boolean;
  maxLength?: number;
  usernameSemantics?: boolean;
};

type AuthPasswordFieldProps = Omit<AuthTextFieldProps, "usernameSemantics"> & {
  showLabel: string;
  hideLabel: string;
};
```

`AuthTextField` 和 `AuthPasswordField` 隐藏 label/input ID、hint/error `aria-describedby`、错误边框和可见按钮语义。它们不读取 API、router、auth store 或 i18n store，页面传入已翻译文案。

`NanoBrand` 只负责标识、产品名和可选 `internal` badge；`AuthPageFrame` 负责品牌顶栏、宽/窄屏重排、产品语境和表单容器，通过 `title` / `subtitle` / `children` / `footer` 接收两页差异。它们不读 auth API 或管理会话。

### 提交流

1. 页面阻止浏览器默认提交，运行对应的 `validate*()`。
2. 有字段错误时，一次更新 `FieldErrors`，并将焦点放到表单顺序中第一个错误；返回且不发网络请求。
3. 通过本地校验时清理旧反馈、设置 `submitting=true`，调用现有 auth API。
4. 成功时保存 token pair；注册进首页，登录返回 route guard 保留的完整 `pathname + search + hash`。
5. 失败时先将已知注册拒绝投影到字段，否则写入页面级反馈代码；最后释放 `submitting`。
6. 用户修改某字段时清理该字段错误及旧页面错误；其他输入和错误保留。

## 前端原型

- 原型文件: [prototype.html](prototype.html)
- 覆盖范围:注册/登录页之间跳转、中英文切换、字段 hint、空值/短密码错误、密码显隐、重名/错误凭据/服务异常和提交中状态。原型以特定用户名模拟响应，不连接后端。

### 现有 UX grounding

| 当前产品入口 / 组件 | 必须继承的 UX 特征 | 本次增量如何嵌入 |
|---|---|---|
| 当前 AppShell / 设置与聊天页 | 勾选方形 `nano IM` 品牌、IBM Plex、浅蓝灰背景、白色表面、细边框、青绿主动作与线性图标 | 认证页直接复用品牌组件和全局 token，宽屏以产品语境+表单面板延续层级 |
| `/register` | 用户名→显示名→密码、主按钮、登录链接的任务顺序 | 保留任务顺序，替换旧卡片外观，字段内加 hint/error 与密码显隐 |
| `/login` | 用户名→密码、主按钮、注册链接的任务顺序 | 与注册使用同一现代布局、字段/反馈语法，保留导航去向 |
| 全局 i18n | 桌面用户菜单使用 `EN | 中`，中英文即时切换与 `im_lang` 持久化 | 认证品牌顶栏复用同一语法和 store |

### 原型对齐契约

| 原型区域 / 状态 | 对齐级别 | 产品入口 | 必验 viewport / 状态 | 下游验收投影 |
|---|---|---|---|---|
| 新版品牌顶栏、浅蓝灰/白色表面、青绿主动作、线性图标与宽屏双区/窄屏单列重排 | must-match | `/register` / `/login` | 390×844 与 1280×800，初始态；375×667 空提交/英文长文案可纵向滚动 | M1-R1 / M1-W1 |
| 表单的字段顺序、规则 hint、可选标记与页脚跳转 | must-match | `/register` / `/login` | 390×844 与 1280×800，初始态 | M1-R1 / M1-W1 |
| 字段级错误、错误边框、首错焦点与编辑后清理 | must-match | `/register` / `/login` | 空提交、短密码、重名 | M1-R2 / M1-W2 |
| 密码显示/隐藏按钮与不丢值交互 | must-match | `/register` / `/login` | 密码已输入 | M1-R3 / M1-W2 |
| 中文 / English 轻量切换，切换时保留输入和错误 | must-match | `/register` / `/login` | 有输入且已有错误 | M1-R4 / M1-W3 |
| 页面级凭据/服务错误与提交中状态 | must-match | `/register` / `/login` | 401、网络失败、pending | M1-R5 / M1-W2 |
| 字体、精确间距和 icon 绘制 | may-adapt | `/register` / `/login` | 全部 | 遵循现有 token 与清晰层级 |

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im: `specs/im/auth-tenancy.md`
- gateway: no spec delta
- cli: no spec delta

## 风险与回退

- **前后端规则漂移**：本地校验只镜像已有少量稳定约束，服务端仍权威校验；对无法识别的新错误显示通用可重试提示，不静默成功。
- **错误清理过度**：只清理当前编辑字段和页面级旧错误，其他字段错误保留，避免用户失去定位。
- **密码暴露**：默认仍隐藏；只在用户主动点击时显示，页面导航/重载后恢复默认隐藏。
- **响应期间操作竞态**：`submitting` 作为唯一 pending 门禁，字段、密码显隐、页脚跳转和提交按钮在 pending 时停用；locale 仅更新本地文案，保持可用。
- **移动内容裁切**：认证 frame 是唯一纵向滚动 owner，在真实 `body overflow:hidden` 下验 375×667 长错误态，不通过放开全局 body 规避。
- **品牌复用影响 AppShell**：`NanoBrand` 抽取必须保持现有顶栏 DOM 可观察文案、`internal` test id 和尺寸，相关既有 shell 测试保留。
- **回退**：产品代码变更局限在 AppShell 品牌小组件、auth 页、auth 内部组件/校验、i18n 文案与 `im-auth-*` 样式；回退该 milestone commit 即恢复旧认证页，不涉及数据迁移。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Gateway 栈（IM 服务当前 worktree 构建的 frontend dist） | `./scripts/e2e-down.sh --wt "$(pwd)"` | `npm --prefix src/IM/frontend run build && PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/e2e-up.sh --wt "$(pwd)"` | `source .e2e-ports.env && curl -fsS "$IM_URL/register" >/dev/null` |

**Review 驱动方式**: 端到端真栈；本 unit 修改客户端面，reviewer 必须用真浏览器驱动 `/register` 和 `/login`，走查空值、短密码、重名、密码显隐、错误凭据、网络失败、pending 期间切语言、页脚跳转与带 query/hash 的受保护深链登录返回；检查 390×844 / 1280×800 初始态及 375×667 英文多错误可滚动态。

**验收前置**: 无必需仓库外资源。隔离栈的新 SQLite 先注册一个 reviewer 自定义账号，再用它验重名与登录成功；网络失败在浏览器客户端层暂时拦截 auth 请求，不停整个栈。当前 CSS 从 Google Fonts 尝试加载 IBM Plex；断网时的系统 sans fallback 是允许的降级，不把字体网络作为验收前置。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 认证表单交互闭环 | — | A | `src/IM/frontend/src/app/shell/`、`src/IM/frontend/src/features/auth/`、`src/IM/frontend/src/i18n/`、`src/IM/frontend/src/styles/global.css`、最低层前端测试与浏览器 evidence；最终归并 IM auth-tenancy 契约 | **M1-R1 [reviewer]** 注册/登录页在桌面和手机呈现当前 nano IM 品牌、色彩、字体、线性图标和表面层级；宽屏双区、窄屏单列重排不溢出，375×667 长错误态可纵向滚到主按钮/页脚，且完整显示必填/可选与密码规则。 **M1-W1 [worker]** `NanoBrand` 为 AppShell/auth 唯一品牌标识组件，现有 shell 尺寸/test id 不回归；`AuthPageFrame` 在不改全局 body/AppShell 的前提下拥有认证页纵向滚动；留存 390×844 / 1280×800 初始态与 375×667 英文多错误滚动证据及原型对照结论。 **M1-R2 [reviewer]** 空值、短密码、重名均原位可修正，首错聚焦、修改清错，本地错误不发请求。 **M1-R3 [reviewer]** 两页密码显隐不改值，提交中无重复请求。 **M1-R4 [reviewer]** 中英文可在未登录顶栏与 pending 期间切换，值和反馈保留且选择持久。 **M1-R5 [reviewer]** 401 凭据错误与可重试服务错误可区分，注册/登录成功、页脚跳转不回归；受保护深链登录后保留 path/query/hash。 **M1-W2 [worker]** 在最低层页面 seam 覆盖本地校验无 fetch、服务反馈分层、清错、聚焦、显隐、pending 去重、成功导航及 `RequireAuth` 的 path+query+hash 传递；保留已有 auth service/route 测试。 **M1-W3 [worker]** locale 切换在静态/错误/pending 状态即时翻译且不重置表单，前端定向测试、全前端测试、TypeScript/Vite build、相关 Python auth 测试、docs-check 与 `git diff --check` 通过；留存原型 must-match 的真浏览器状态截图/结论。 |
