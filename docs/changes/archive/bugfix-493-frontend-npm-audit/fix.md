# bugfix-493: 审计并修复前端 npm 依赖漏洞

## Relations

- Related: feat-388
- Related: refactor-486
- Closes: #219

## 原始报告

Issue：https://github.com/Mrchen116/nano-multiagent/issues/219

> ## 背景
>
> 在 `src/IM/frontend` 按 CI 顺序执行 clean `npm ci` 后，npm audit 报告 9 个漏洞：1 critical、6 high、2 low。
>
> 当时报告涉及：
>
> - 直接依赖：`vitest <3.2.6` 为 critical；`react-router-dom 7.0.0-pre.0–7.14.1` 与 `vite 7.0.0–7.3.3` 为 high；
> - 传递依赖：`picomatch`、`postcss`、`react-router`、`ws` 为 high，`@babel/core`、`esbuild` 为 low。
>
> npm audit 对各项都提示存在修复版本，但尚未核对 advisory 的适用条件、生产可达性和升级兼容性。当前 CI 只执行 `npm ci` 与 Vitest，不会因 audit 结果失败。
>
> ## 目标
>
> 逐项确认漏洞是否影响生产 bundle、开发服务器或测试工具链，并采用最小兼容升级消除适用风险。不要直接运行未经审查的 `npm audit fix` 批量改写 lockfile。
>
> ## 处理方向
>
> - 在 CI 使用的 Node 20 环境重新生成 audit 结果并记录 advisory；
> - 区分 production dependency、development dependency 和不可达的传递依赖；
> - 核对各直接依赖的最小安全版本以及 breaking changes；
> - 分组升级依赖并检查 lockfile diff；
> - 运行完整前端 Vitest 和生产 build；
> - 风险清零或明确接受后，再决定 CI 是否增加 audit severity 门禁。
>
> ## 验收标准
>
> - 所有 critical/high advisory 均已修复，或有基于可达性和使用场景的明确处置结论；
> - `package.json` / `package-lock.json` 只包含经过审查的必要升级；
> - 前端完整测试与生产 build 通过；
> - CI 对后续依赖漏洞的策略已经明确，不以“测试通过”代替安全判断。
>
> 来源：文档体系重构漂移审查 D-012。

## 澄清记录

- Q1: 本 unit 的 CI 策略，是否按“依赖升级后增加 `npm audit --audit-level=critical` 门禁；high 继续逐项人工判定，不强求原始 audit 归零”收口？
  A(原话): 是。升级后对完整 lockfile 增加 `npm audit --audit-level=critical` 门禁，不能用 `--omit=dev` 把测试/构建工具链排除掉。high 仍必须逐项核对并记录适用性与处置，但不要求为了 audit 数字归零而升级到 React Router 8.3；当前这个只影响 unstable RSC API 的 advisory，在本仓纯浏览器 SPA、没有 RSC/SSR 的前提下可以明确接受。以后 high 的适用性变化要重新处理，不能把这次接受写成永久白名单或全局忽略。
  Agent 解读: CI 对完整前端依赖树新增 critical 硬门；high 保留逐项判定。当前可接受的 React Router high 仅绑定“纯浏览器 SPA 且不使用 unstable RSC API”这一现状，条件变化时必须重新处置。

## 现象 / 复现

在 `src/IM/frontend` 对当前 `main` 的 `package-lock.json` 执行只读 audit，仍能稳定复现 Issue #219，而不是已经随时间消失的旧报告。

2026-08-04 使用与 CI 同一 Node major 的 Node `20.20.2` / npm `10.8.2` 执行：

```bash
npm audit --json
npm audit --omit=dev --json
```

结果：

- 完整依赖树：`1 critical / 6 high / 2 low`，共 9 个 package-level vulnerability entries，命令退出码为 1；
- 只看 production tree：`2 high`，分别是直接依赖 `react-router-dom` 与其传递依赖 `react-router`；
- 当前 lockfile 锁定 `react-router-dom/react-router 7.13.1`、`vite 7.3.1`、`vitest 3.2.4`、`picomatch 4.0.3`、`postcss 8.5.8`、`ws 8.19.0`、`@babel/core 7.29.0`、`esbuild 0.27.3`；
- 所有条目都由 npm 标记为 `fixAvailable: true`；audit 前后 `package.json` 与 `package-lock.json` 的 SHA-256 不变，真实性复核没有改写仓库 lockfile。

这 9 个条目的当前适用性如下：

| package | 依赖面 | 当前可达性与处置基线 |
|---|---|---|
| `react-router-dom` / `react-router` | 生产依赖；前端实际使用 `createBrowserRouter`、`Link`、`useNavigate` | 不能按“仅开发依赖”排除。当前是纯浏览器 SPA，代码中没有 SSR、Framework Mode、RSC 或 server action；隔离模拟升级到 `7.18.2` 后，只剩官方明确限定于 unstable RSC API 的 [`GHSA-qwww-vcr4-c8h2`](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)。该残余项按 Q1 有条件接受，不迁移到 `react-router@8.3` 追求 audit 数字归零。 |
| `vite` | 直接开发依赖；构建与 dev server | 官方 high advisories（例如任意文件读取 [`GHSA-p9ff-h696-f583`](https://github.com/advisories/GHSA-p9ff-h696-f583)）需要 dev server 对网络暴露；本仓 current 开发和 worktree runbook 均要求绑定 `127.0.0.1`，生产由 IM 提供静态 build，不运行 Vite server。风险当前不可远程利用，但安全的 7.x 修复版本已存在，应随受控升级消除。 |
| `vitest` | 直接测试依赖 | critical [`GHSA-5xrq-8626-4rwp`](https://github.com/advisories/GHSA-5xrq-8626-4rwp) 只影响显式开放 Vitest UI/API，或 Windows 上运行 UI/Browser Mode；本仓脚本只运行 `vitest run` / watch，没有 UI/API host 或 Browser Mode。它不进入生产 bundle，但仍属于完整工具链，按 Q1 不能从 CI audit 中省略，并应升级到已修复的 3.x 版本。 |
| `picomatch` | Vite/Vitest 的开发期传递依赖 | high ReDoS 需要攻击者控制 glob；本仓只处理仓库内构建/测试输入，不是生产请求面。4.x 修复版本可在现有依赖范围内取得。 |
| `postcss` | Vite 的开发期传递依赖 | high 文件读取要求处理攻击者控制的 CSS/source map；本仓构建仓库内受信 CSS，不接收用户 CSS。8.x 修复版本可取得。 |
| `ws` | jsdom 的开发期传递依赖 | high DoS 针对与不可信 WebSocket peer 的长连接；它只服务前端测试环境，不是 IM 服务端的 WebSocket 实现。8.x 修复版本可取得。 |
| `@babel/core` | Vite React plugin 的开发期传递依赖 | low 文件读取依赖恶意 source map 输入；不进入生产 runtime。7.x 修复版本可取得。 |
| `esbuild` | Vite 的开发期传递依赖 | low advisory 影响 Windows dev server 的任意文件读取；本仓生产不运行 esbuild。修复版本可随受控 Vite 依赖更新取得。 |

在仓外临时目录对相同 manifests 做 lock-only 修复模拟后，版本可在不改 `package.json` 声明的情况下更新为 `react-router-dom/react-router 7.18.2`、`vite 7.3.6`、`vitest 3.2.7` 及安全传递版本；再次 audit 只剩 `react-router` / `react-router-dom` 聚合出的 2 个 high，根 advisory 均为 `GHSA-qwww-vcr4-c8h2`。GitHub Advisory 原文明确说明：只有使用 unstable RSC APIs 的应用受影响。本仓没有该模式，因此这 2 个 package-level entries 是同一个已记录、带适用条件的接受项，不代表两个独立可达漏洞。

### Requirement: 当前适用的 critical/high 风险得到处置

#### Scenario: 完整前端依赖树重新审计

- **GIVEN** 贡献者在 CI 支持的 Node 20 环境按 lockfile 安装完整前端依赖
- **WHEN** 对完整依赖树执行 npm audit
- **THEN** 不再存在未处置的 critical advisory
- **AND** 每个仍报告的 high advisory 都有基于本仓真实使用方式的适用性与处置记录

#### Scenario: RSC-only high 在纯浏览器 SPA 中有条件接受

- **GIVEN** Web IM 继续只使用浏览器 SPA 路由，不启用 SSR、Framework Mode、RSC 或 server action
- **WHEN** audit 因 `GHSA-qwww-vcr4-c8h2` 报告 `react-router` / `react-router-dom` high
- **THEN** 维护者可以接受该当前不可达风险，而不为清零数字迁移到 React Router 8.3
- **AND** 该结论不形成永久白名单；路由运行模式或 advisory 适用条件变化时必须重新核对

### Requirement: CI 阻止新的 critical 依赖风险静默进入

#### Scenario: 完整依赖树出现 critical advisory

- **WHEN** PR 的前端完整 lockfile 被 `npm audit --audit-level=critical` 检出 critical advisory
- **THEN** Frontend CI job 失败，不能以 Vitest 或 build 通过替代安全处置
- **AND** 检查不得用 `--omit=dev` 排除测试与构建工具链

#### Scenario: 只有已复核的 high advisory

- **GIVEN** 完整依赖树没有 critical，只有已经逐项核对的 high advisory
- **WHEN** Frontend CI 执行 dependency audit
- **THEN** high 不因追求原始 audit 数字归零而自动阻止交付
- **AND** CI 输出仍保留这些条目供维护者核对，不能通过永久 ignore 或全局 allowlist 隐藏

### Requirement: 前端既有行为与开发反馈保持不变

#### Scenario: 依赖更新后的正常构建与测试

- **WHEN** 贡献者使用更新后的 lockfile 执行完整 Vitest 和生产 build
- **THEN** 两者均通过，Web IM 继续由 IM host 提供静态前端，路由、页面与用户操作保持既有行为

### 范围与非目标

本期范围：逐项审计当前 9 个条目；只做经过 lockfile diff 审查的必要依赖升级；对完整依赖树增加 critical CI 门；保留当前 high 的条件化处置结论；运行完整前端测试和生产 build。

本期不做：不启用 React Router RSC/SSR，不为清零 audit 数字迁移到 React Router 8.3，不建立永久 advisory 白名单或全局忽略，不把 Dependabot 等完整依赖治理平台并入本次 bugfix，也不借依赖升级改变 Web IM 功能或交互。

## 根因

### 直接原因

`package.json` 的 semver 范围允许取得多数修复版本，但 `package-lock.json` 长期锁定在 advisory 覆盖的旧版本。`npm ci` 的职责是忠实安装 lockfile，不会主动刷新这些版本；因此每次 clean CI 都稳定重现同一依赖树。

当前 `.github/workflows/ci.yml` 的 Frontend job 固定 Node 20，只执行 `npm ci` 和 `npm run test`。`npm ci` 即使在输出中提示 audit 摘要也不会因这些 advisory 返回失败，Vitest 通过只证明测试通过，不证明依赖安全。仓库当前也没有启用 Dependabot alerts，因而没有其他自动门禁把新披露 advisory 转成阻塞信号。

### 原始设计意图与必须保住的不变量

Frontend CI 由 `feat-388` 引入，原始目标是让前端 Vitest 回归与 Python checks 一样阻止合并。其 spec/design 明确把范围限定为 Node 20 → `npm ci` → `npm run test`，没有声称覆盖 dependency audit、生产 build 或类型检查。因此本问题不是 feat-388 已承诺行为的代码回归，而是安全责任在当时没有 owner，后来由 `refactor-486` 的 clean `npm ci` 验收首次集中记录并转入 Issue #219。

修复必须保住：

- Node 20 下 `npm ci` 的可重复安装，以及现有完整 Vitest 门禁；
- `npm run build` 能生成由 IM host 提供的静态 SPA，Web IM 路由和用户行为不变；
- 开发与 worktree Vite 继续按 current runbook 绑定本地回环地址；
- security gate 覆盖 production 与 development dependency，不把测试/构建工具链排除；
- high 风险按真实可达性逐项判断，当前 RSC-only 接受项随适用条件变化重新评估；
- 不通过未经审查的批量 `npm audit fix`、永久 ignore 或降低现有测试范围来制造“安全”结果。

### 缺陷形成与长期存活点

当前 `react-router-dom 7.13.1`、`vite 7.3.1`、`vitest 3.2.4` 等 lock 条目可追溯到 commit `822915e83e`（2026-03-03，建立前端壳体测试）；后续 commit `3f1110731c`（2026-06-16）增加 Markdown 相关依赖时，只更新了新增依赖及其传递项，没有刷新这些已满足 semver 的既存版本。相关 advisories 在 2026 年 4 月至 7 月陆续披露，所以这不是某次产品改动把安全行为改坏，而是外部风险状态变化后 lockfile 与门禁没有随之更新。

Issue #219 创建前，CI 的可观察成功条件始终只有“安装成功 + 测试通过”。缺少完整依赖树的 critical 退出门、high 适用性复核约定和自动 vulnerability alerts，使安全报告只能在人工 clean install 时偶然出现，并能在测试持续全绿的情况下长期留存。

## 修复

M1-fix 在 Node `20.20.2` / npm `10.8.2` 下对明确列出的依赖执行 lock-only 更新，没有运行
`npm audit fix`，也没有扩大 `package.json` 的声明范围。最终 lockfile 只更新了这批直接或必要传递版本：

| dependency | before | after | 处置 |
|---|---:|---:|---|
| `react-router-dom` / `react-router` | `7.13.1` | `7.18.2` | 消除除 RSC-only 项之外的 Router advisory；继续使用现有 browser/data-router API |
| `vite` | `7.3.1` | `7.3.6` | 消除当前 7.x dev-server high advisories |
| `vitest` 及同版本内部包 | `3.2.4` | `3.2.7` | 消除 `GHSA-5xrq-8626-4rwp` critical |
| `picomatch` | `4.0.3` | `4.0.5` | 消除 glob 相关 high |
| `postcss` / `nanoid` | `8.5.8` / `3.3.11` | `8.5.25` / `3.3.17` | 消除 PostCSS high；`nanoid` 随其受支持范围更新 |
| `ws` | `8.19.0` | `8.21.2` | 消除测试环境 WebSocket high |

`.github/workflows/ci.yml` 的 Frontend job 在完整 `npm ci` 后新增
`npm audit --audit-level=critical`。它没有 `--omit=dev`，所以测试与构建工具链仍在审计范围内；
只剩 high 时命令会保留报告但返回成功，新的 critical 会直接阻断 job。本次没有建立 advisory
ignore、allowlist 或其他旁路。

最终 audit 仍把 `GHSA-qwww-vcr4-c8h2` 聚合显示为 `react-router` / `react-router-dom`
两个 high entries。GitHub reviewed advisory 明确限定为 unstable RSC APIs；本仓生产入口只有
`createBrowserRouter` + `RouterProvider` 的浏览器 SPA，代码、manifest、Vite 配置和真实入口均没有
SSR、Framework Mode、RSC 或 server action。因此按 Q1 条件化接受，不升级到 React Router 8.3；
一旦路由运行模式或 advisory 适用条件变化，必须重新审计。

剩余两个 low 分别是开发期 `@babel/core` source-map 任意文件读取和 Windows 上的 `esbuild`
dev-server 文件读取。本仓生产由 IM host 提供静态 build，不接收不可信 source map，也不在 Windows
运行生产 dev server；本 milestone 不为 low 扩大 Babel/esbuild 更新面，audit 输出继续保留它们。

现有完整 Vitest 与生产 build 已覆盖依赖升级的兼容性；没有新增平行测试文件。长期回归 owner 是
Frontend CI 中的新 audit step，既有 59 个 Vitest 文件全部保留。

## 验证

### Audit Red / Green

- Baseline: `origin/main@d5274646e85033579e9ea1e4802960fd1c075b6f`，Node `20.20.2`，
  npm `10.8.2`；clean `npm ci` 后 `npm audit --json` 为
  `1 critical / 6 high / 2 low`，`npm audit --audit-level=critical` 退出码 `1`。
- Lockfile 更新后：`package-lock.json` SHA-256 为
  `bdbed83747f3e03bc15b4ed39ed52288fdbc93606e468753ade0835e59e5b750`；clean `npm ci`
  前后哈希一致。
- Green: 同一环境执行 `npm audit --audit-level=critical` 退出码 `0`；完整 audit 为
  `0 critical / 2 high / 2 low`。两个 high 都来自同一个 RSC-only advisory，没有未处置的
  applicable critical/high。

### 测试与构建

- `CI=1 NO_COLOR=1 npm run test -- --reporter=dot`：`59` files / `555` tests passed，
  Vitest `3.2.7`。输出中的既有 React `act()` / user-stream console 噪声在升级前也存在，已由
  active `bugfix-495` 单独处理，本 unit 没有改动或掩盖它。
- `npm run build`：TypeScript build 与 Vite `7.3.6` production build 通过，转换 `501` modules，
  产出静态 SPA；既有 chunk-size warning 不变。

### 真实静态入口

- Method: 在 unit worktree build 之后，用隔离端口 `53450` 启动真实 `IM.app`，由 IM host 提供
  `dist`；使用 Playwright headed Chromium 分别验证 desktop 与 `390x844` mobile viewport。
- Result: `/` 正确跳转 `/login`；创建隔离账号后进入 `/chat`；desktop 导航到
  `/settings/agents` 并 hard reload 仍成功；mobile 底栏返回 `/chat`。根 HTML、JS、CSS、favicon、
  register、sync、agents、nodes、conversations 请求均为 `2xx`，console 为 `0 errors / 0 warnings`。
- Limit: 本次不改变 Gateway/LLM 数据面，因此没有启动 Gateway 或调用模型；验证覆盖依赖升级影响的
  静态入口、Router 导航、响应式入口、console 和 network。浏览器与 IM 进程已关闭，监听端口已释放。

### Canonical spec

本修复不改变 Web IM 的用户可观察行为；dependency audit 属于 CI / 开发安全约束，按
`docs/specs/CONTRIBUTING.md` 判定为 `no spec delta`，不修改 `docs/specs/im/`。

### Review 与 final sync

- 独立 finder 对 `d5274646e85033579e9ea1e4802960fd1c075b6f..e251c2a8c` 的七个审查角度均未发现候选问题，输出为 `[]`；独立 verifier 对零候选复核后同样输出 `[]`。
- 实施完成后已 rebase 到 `origin/main@1a0fb9ea922c33551b2c5bbb3bf440102e3ddae6`。新增 upstream 内容只包含 `bugfix-496` 与 `bugfix-497` 的 active incident 文档，与本单元没有代码或文档所有权重叠；实现 diff 未变，因此保留上述 code-review、测试、build 与浏览器门禁结论。
- final-sync 后 `scripts/docs-check` 通过（`192` sources / `65` routes），`ruff check .` 与 `ruff format --check .` 通过（`812` files），`git diff --check` 通过。
- 与 GitHub Frontend job 等价的独立 clean 运行 `npm ci && npm audit --audit-level=critical && npm run test` 通过，结果仍为 `59` files / `555` tests。
- `origin/main@1a0fb9ea9` 的 GitHub CI 两个 job 均为 green。本机把 Python 与 Frontend 两个完整 job 同时运行时触发资源竞争；拆开后 Frontend 全绿，Python 全量仅剩四个本单元未改动的 Feishu multiprocessing 测试在 macOS xdist 全套件上下文失败，而相同失败集合的聚焦运行 `13 passed`。本单元不改 Python 代码或测试，不跨范围处理该本机并发问题；最终以 PR 的独立 Linux runners 必需检查为交付门禁。

#### PR 开放后的 final-sync 恢复

- PR #233 开放后，`origin/main` 从 `1a0fb9ea922c33551b2c5bbb3bf440102e3ddae6` 前进到 `be61e2d72a5fdd0f725afe837402e96582e5e0ef`。唯一新增提交只加入 `bugfix-496` 的 Feishu listener/Gateway 设计、设计评审、Gateway delta-spec 和 milestone 占位文件；没有修改 `.github/workflows/ci.yml`、`src/IM/frontend/` 或本 unit 的归档目录。
- 该增量描述未来的 Feishu worker owner-liveness 实现，并明确 IM/前端为 `no spec delta`。它不改变 npm 依赖树、critical audit 策略、前端运行代码、IM 静态托管入口或 bugfix-493 的用户旅程，因此既有 audit、Vitest、production build、真实浏览器和独立 code-review 结论全部 retained。
- 文档集合本身发生变化，所以同步后重新执行 `scripts/docs-check` 与 `git diff --check`；rebase 产生的新 PR head 重新等待 GitHub Python/Frontend 两个 required jobs 全绿，不能沿用旧 head 的 CI 状态。
