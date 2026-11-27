# feat-799-desktop-hardening-private-deploy: Review

## 范围与版本

- 本次问题与需求/设计位置：
  - 需求规格：[spec.md](spec.md)
  - 技术设计与原型投射：[design.md](design.md)、[design-review.md](design-review.md)
  - Delta 行为契约：[specs/im/desktop-client.md](specs/im/desktop-client.md)、[specs/im/agents-nodes.md](specs/im/agents-nodes.md)
  - 实施取证摘要：[M1/evidence/viewport-and-runtime-verification.md](M1/evidence/viewport-and-runtime-verification.md)
- 实际 `executed_base` / `validated_at`：
  - `executed_base`：`8268bd40abdf5f485e5762e360b35f8d0fe1d51c` (`origin/develop`)
  - 首轮独立审查 `validated_at`（`pre_fix_head`）：`3086fcdd1809dab462891480349346345944df2d`
  - 增量修复与关闭复验 `validated_at`：`1642ad0289c0b76775064fb7c0d938d70a41f9ec`
- 最终 `effective_base` / `effective_through` 与保留依据：
  - `effective_base`：`509b7b6b8526f9308d666908e1bf356feaac11fc` (`origin/develop` 最新基线)
  - `effective_through`：`9ab2d7414b66ae75ef21b3d7ada749b50227c72d`（由 `1642ad0289c0b76775064fb7c0d938d70a41f9ec` 合入 `origin/develop @ 509b7b6b8`，无冲突，后续仅执行本审查归集、canonical `docs/specs/im/` 归并与 `docs/changes/archive/` 归档移动，复验结论完整保留）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 打包 SHA 归一化、虚拟存储多版本兜底提升与 `dsh-web -> zod` 补链、Windows 默认桌面快捷方式与覆盖升级停机及新种子版本推进、节点早退快败与退避、Windows 冷检/配置超时与 `deadline_at` 保活、`CatalogReads` 预热复用与在线/离线创建错误区分、官方/公网严格 HTTPS 边界与受控私网 HTTP / 自托管受管更新、Rust Desktop 单实例互斥与首启异步解包隔离、全入口跨服确认与无路由重开保态、架构依赖红线 | `change-code-review` · 独立审查子代理（`conversation://b9b89c28-f239-476f-a09c-a92022261e9b`，未参与设计与实现；首轮 `full` @ `3086fcdd1` + 二轮 `delta/closure` @ `1642ad028`） | `pass` | 独立审查 `8268bd40..3086fcdd1` 全量 diff 与 `3086fcdd1..1642ad028` 修复 diff；独立实跑 `pnpm build`、`pnpm typecheck`、`apps/im-server/tests/*.test.ts` 全量 62 个文件、相关 `apps/node`/`product-contracts`/`channels` 测试、`cargo test`（6/6，含 `local_node::tests`）、`pytest` 契约与打包单测（18/18）、`./scripts/docs-check` 全部绿灯；首轮 `F1..F5` 均已核实关闭（`0 CRITICAL, 0 WARNING`）。限制：Windows 10/11 真机 Inno Setup 向导执行、`DesktopGatewayHost.exe` 计划任务/Job Object 运行与 WebView2 原生窗口冒烟（`packaging/desktop/windows/smoke.ps1`）未在 macOS 开发机直接运行，由跨平台单测与静态审查覆盖。 |
| 最终 delta-spec 与实际实现及 canonical `docs/specs/im/` 一致性校对 | `change-code-review`（`corrected-delta`）· 独立审查子代理（`conversation://b9b89c28-f239-476f-a09c-a92022261e9b`；二轮复核 @ `1642ad028`） | `pass` | 首轮指出的 `specs/im/agents-nodes.md` 未发布安装包回退/上线门控条款遗漏、第 3 步创建私聊措辞及 `specs/im/desktop-client.md` 运行中覆盖升级契约已在 `1642ad028` 补齐，独立复核确认 `aligned`（`0 mismatch`）。 |
| Desktop 客户端首启准备/失败重试、`/login` 原地服务切换与私网提示/公网拦截、跨服切服确认与公网明文拦截弹窗、`/register`、`OnboardingWelcome`、`OnboardingPage` 三步（含第 2 步展开自定义 API 内滚与底栏常驻、第 3 步双列免滚与能力超时错误分流文案）、`FirstUseWelcome` 及普通 Web `/about` / 窄屏 `390×844` 对照体验 | `frontend-experience-review` · 独立审查子代理（`conversation://b9b89c28-f239-476f-a09c-a92022261e9b`；在 `3086fcdd1` 与 `1642ad028` 两次独立起隔离真栈 + Playwright Chromium 实测目视核查） | `pass` | 独立隔离真栈（`im-server` + `crewden-desktop --headless-host` + 本地模拟 SSE 模型服务）在 `1280×840`、`1280×720`、`390×844` 下实测全部 `must-match` 视口外层 `scrollHeight <= clientHeight` 零溢出，第 2 步展开自定义 API 仅 `.onboarding-card-body` 内滚且底部「返回 + 验证并继续」固定可见，第 3 步真栈复现能力超时精准提示并在重试后成功创建 PA 进入 `/chat/c_...` 私聊；普通 Web `/about` 与窄屏布局无回归（`0 CRITICAL, 0 WARNING`）。 |

## Findings 与关闭

- **`[F1]`（`CRITICAL` / `confirmed` -> `Closed` @ `1642ad028`）**：
  - **位置与问题**：`apps/im-server/src/agent-creation.ts` 在 `3086fcdd1` 将 `createAgent` 默认 Skill 解析切至 `readNodeCapabilitiesRaw` 后，对测试桩非 `.capabilities` 包装返回抛 `502` 并吞掉 `[502, 503, 504]`，导致 `apps/im-server/tests/configuration-edits.test.ts` 失败，且在线节点遭遇并发 `CatalogReads.invalidateNode`（`503`）或检查异常时会静默将新建普通 Agent 的 `create_default_skills` 固化为空列表。
  - **Resolution & 独立关闭依据**：`readNodeCapabilitiesRaw` 兼容非包装测试桩返回且不污染 `CatalogReads` 缓存，在线连接遭遇并发 `Catalog read superseded` / `Catalog request cancelled` 时自动重试一次；`createAgent` 仅在真实离线回退（`isOfflineFallback`）时降级空候选，在线节点检查失败直接拒绝而不落空 `default_on` Skills。独立审查者在 `1642ad028` 实跑 `apps/im-server/tests/*.test.ts` 全量 62 个测试文件确认通过并关闭。
- **`[F2]`（`WARNING` / `confirmed` -> `Closed` @ `1642ad028`）**：
  - **位置与问题**：`apps/im-server/src/personal-agent.ts` 在 `3086fcdd1` 将所有 `status === 503` 一律映射为 `node_offline`，使在线电脑的能力检查失败（`catalog_failed`）或并发失效被误报为「所选电脑当前离线」，且 `onboarding.ts` 在异步 `testing` 阶段提前触发必然被取代的预热。
  - **Resolution & 独立关闭依据**：`node-rpc.ts` 为检查异常与离线异常显式附带 `code`；`onboarding.ts` 仅在同步完成态预热（异步 `testing` 交由 `node.capabilities.changed` 预热）；`personal-agent.ts` 严格区分真实离线（`503 node_offline`）、超时（`504 node_capabilities_timeout`）与在线能力暂不可用（`502 node_capabilities_unavailable`）。独立审查者通过 `personal-agent.test.ts` 单测与真栈第 3 步实测双重核实关闭。
- **`[F3]`（`WARNING` / `confirmed` -> `Closed` @ `1642ad028`）**：
  - **位置与问题**：`packaging/desktop/windows/CrewdenDesktop.iss` 中 `AppMutex` 未在宿主创建，运行中覆盖安装缺少 `--stop` 优雅停机联动，且安装包升级后既有 `.desktop-active.json` 仍指向旧版 `versions/<old_sha>`。
  - **Resolution & 独立关闭依据**：移除无效 `AppMutex`，在 `CrewdenDesktop.iss` 新增 `PrepareToInstall` 调用 `CrewdenDesktop.exe --stop`（等待 `instance.lock` 释放并通过 `preserve_user_stopped: true` 停止全部受管节点而不污染 `user_stopped` 自启状态）；`local_node.rs` 在安装包 `seed-archives` 的 `sha256` 相对 `seed-current.json` 变化时自动推进各连接 `.desktop-active.json`（同时在 `seed-current.json` 未变时完整保留应用内 OTA 热更新版本），`spawn_managed_node_supervisor` 首轮检测到已运行节点版本不一致时执行 `restart`。独立审查者通过 `cargo test`（含 `local_node::tests`）与 `test_desktop_packaging.py` 核实关闭。
- **`[F4]` & `[F5]`（`SUGGESTION` / `confirmed` -> `Closed` @ `1642ad028`）**：
  - 已清理 `node-update.ts` 未使用字段 `embeddedSeed` 与 `package-macos-desktop.py` 冗余写入，并在 `sync_seed_desktop_defaults` 中清理官方安装包覆盖私有化安装包后的残留 `desktop-defaults.json`。
- **`[F6]`（`SUGGESTION` / 非阻断样式微调备注）**：
  - `/onboarding` 第 1 步内嵌绑定卡片行内 `<code>` 因 `onboarding.css` 后加载同优先级规则仍呈块级换行，不影响 `1280×720` 零溢出布局（`604/604`）与功能可读性，作为非阻断建议记录，无存活阻塞缺陷。

## 流程收口

- **重要目标和关键设计覆盖**：`spec.md` 与 `design.md` 承诺的四组核心目标（打包确定性与 Windows 默认桌面快捷方式及平滑覆盖升级、首次启动即时准备页与单实例锁唤醒保态、Windows 冷启动检查/创建超时与单次预热及错误分流、官方/公网严格 HTTPS 边界与独立 IM 受控私网 HTTP / 自托管更新 / 跨服唤起确认 + 桌面一屏化体验）均已完整落地并验证通过。
- **开放问题 / pending / inconclusive**：无（`0` 开放阻塞项，`0` pending，`0` inconclusive）。
- **最终 delta 校对**：`specs/im/desktop-client.md` 与 `specs/im/agents-nodes.md` 经独立审查 `corrected-delta` 确认为 `aligned`，原样归并入 `docs/specs/im/desktop-client.md`、`docs/specs/im/agents-nodes.md` 与 `docs/specs/im/spec.md`。
- **版本变化后保留 / 补验的判断与依据**：`1642ad028` 之后仅执行本审查文件落盘、canonical spec 归并与 `docs/changes/archive/` 归档移动，无代码变更，`1642ad028` 的代码、契约与真栈体验审查结论完全有效。
- **测试资源回收结果**：作者自检与独立审查拉起的全部隔离 `im-server`、`crewden-desktop --headless-host`、受管节点、模拟模型服务进程、`/tmp/feat799-*` 临时目录及 `src/IM/frontend/dist/` 本地构建产物均已完整清理回收并核实无残留。
- **交付范围与剩余事项**：完成 canonical spec 归并、单元归档与本地全量 CI 等价检查，保留开发 worktree 供后续提交/PR 合入流程使用；Windows 10/11 真机安装器向导与 WebView2 冒烟可在 Windows 打包机按 `packaging/desktop/windows/smoke.ps1` 执行。
