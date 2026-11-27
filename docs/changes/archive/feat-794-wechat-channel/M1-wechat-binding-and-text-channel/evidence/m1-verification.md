# M1 验证证据：微信扫码绑定与基础 1:1 文本通道

验证分支：`unit/feat-794-wechat-channel`（基于 `9b24d761c` 实施 M1）  
验证日期：2026-11-26  
环境约束：全部验证在隔离 worktree 与临时运行目录（`/tmp/feat-794-m1-rt`）执行，未触碰主仓未提交改动或个人生产服务；微信上游协议与 CDN 由本地可控 twin（`scripts/e2e-wechat-twin.mjs` + `NANO_WECHAT_E2E_BASE_URL`）驱动。

## 1. 单元、契约、构建与 iOS 原生编译门禁

| 验证层 | 执行命令 | 结果摘要 | 覆盖范围与限制 |
|---|---|---|---|
| `product-contracts` & `@nano/channels` | `pnpm exec vitest run packages/product-contracts/tests/node-wechat-setup.test.ts packages/channels/tests/wechat.test.ts packages/channels/tests/feishu.test.ts packages/channels/tests/channel-credentials.test.ts` | **4 files / 11 tests passed** | 覆盖 `node.wechat.setup.*` schema、SSRF 域名门禁、uint64 无损字符串解析、三种 AES-128-ECB key 解码、代码块不断块切分、QR/IDC 重定向/PIN 错误重试/过期刷新/取消、单 poller 先停再起、owner-only 门禁、typing 续期、`-14` 自动停用与 `0600` 状态清理 |
| `personal-assistant` & `im-server` | `pnpm exec vitest run packages/personal-assistant/tests/wechat-channels.test.ts packages/personal-assistant/tests/managed-channels.test.ts packages/personal-assistant/tests/external.test.ts packages/personal-assistant/tests/single-thread.test.ts apps/im-server/tests/wechat-channel.test.ts apps/im-server/tests/external-ingress.test.ts apps/im-server/tests/node-rpc.test.ts` | **7 files / 46 tests passed** | 覆盖 `provider='wechat'` 与飞书并存建表/封存/离线自治重连、`pa · wechat` 与 `agent · wechat` 影子会话投递、`/new` `/stop` `/compact` 控制同步、PA owner 权限对齐、响应不回显 `bot_token`/`credential_envelope` |
| Web 前端测试与静态构建 | `npm --prefix src/IM/frontend test -- --run src/features/settings/agents/{wechat-channel-panel,agent-channels-panel,agent-channels-diagnostics,agent-channels-offline,agent-channels-removal-recovery}.test.tsx && (cd src/IM/frontend && npx tsc -b && npm run build)` | **5 files / 26 tests passed**，`tsc -b` 与 `vite build` 零错误 | 覆盖通道选择器、扫码弹窗（安全 SVG 元素渲染，零 `dangerouslySetInnerHTML`）、数字验证码原位重试、已连接卡片（`wxid_o••••3k92`）、`-14` 登录失效提示与重新扫码恢复 |
| 原生 iOS 构建与单元契约测试 | `pnpm check:ios-runtime` + 临时隔离 iPhone 17 Pro Simulator 执行 `xcodebuild ... -only-testing:NanoIMTests/AgentContractsTests test`（退出即删除临时模拟器） | `check:ios-runtime` 通过；**12/12 `AgentContractsTests` passed** | 覆盖 iOS 端 provider 选择引导（微信提示前往桌面/Web 扫码，飞书未添加时仍可添加）及已绑定微信状态展示与启停/重连/删除；不冒称真机扫码 |
| 全仓构建、类型与架构依赖契约 | `pnpm build && pnpm typecheck && pytest tests/contract/test_runtime_dependency_contract.py -q` | 全部通过（**14/14** 架构依赖契约通过） | 确认 `@nano/channels`、`apps/im-server`、`@nano/personal-assistant`、`apps/node` 跨包 import 边界未被破坏 |

## 2. 隔离全栈 E2E 与双视口（`1280×800` / `390×844`）浏览器核验

- **启动方式**：在 `/tmp/feat-794-m1-rt` 启动 `./scripts/e2e-up.sh --wt /tmp/feat-794-m1-rt --profile daily`，配合 `node scripts/e2e-wechat-twin.mjs`（注入 `gateway.yaml` `environment.NANO_WECHAT_E2E_BASE_URL`）。
- **验证链路与结果**：
  1. **Web 登录与扫码等待态（`1280×800`）**：使用测试账号 `nano` 登录后进入个人助手 `pa_953ecf51574a` →「通道」→「连接通道」→「微信（个人扫码）」，验证安全 SVG 二维码弹窗与引导文案对齐 `prototype.html`（截图暂存于仓外 `scratch/m1-screenshots/m1-desktop-1280-qr-wait.png`）。
  2. **数字验证码错误原位重试与绑定完成**：通过 twin `/__admin/qr` 推进至 `need_verifycode`；输入错误验证码 `000000` 验证弹窗内联展示「验证码不正确，请核对手机微信界面显示的数字后重试。」且不闪退（`m1-desktop-1280-pin-error.png`）；输入正确验证码 `482916` 完成 X25519 密文封存落库与单 poller 启动。
  3. **已连接态双视口（`1280×800` 桌面 & `390×844` 移动）**：桌面端横向展示 `重新扫码 / 重新连接 / 停用 / 删除` 与 `wxid_o••••3k92` 脱敏身份（`m1-desktop-1280-connected.png`）；`390×844` 移动端切换为 2×2 按钮网格，零横向溢出（`m1-mobile-390-connected.png`）。twin 状态确认 `max_concurrent_pollers = 1`。
  4. **真实 LLM 微信私聊往返与陌生人门禁**：通过 `/__admin/inbound` 以绑定者 `wxid_owner_3k92` 发送文本消息，触发 `sendtyping`、真实 LLM 回复回发微信（twin `sent_messages` 收到回复）并同步至内部 IM 影子会话 `pa_953ecf51574a · wechat`；非绑定者消息仅收到限频提示且未进入影子会话。
  5. **`-14` 登录失效自动停用**：通过 `/__admin/revoke` 注入 `errcode: -14`，poller 自动停止并清理本地 `cursor` / `context_token` / `quotes`，Web 通道卡片同步呈现 `登录已失效` 与「微信登录已失效，请点击『重新扫码』恢复绑定」。
- **资源回收**：验证脚本退出时执行 `./scripts/e2e-down.sh --wt /tmp/feat-794-m1-rt` 并删除 `/tmp/feat-794-m1-rt`，核实无残留 `e2e-wechat-twin` 或测试进程。
- **能力边界说明**：本轮验证使用本地可控 iLink twin 验证协议状态机与全栈接线；真实腾讯上游微信扫码将在 Stage 4 独立门禁通过后、提 PR 前启动隔离预览供用户亲自扫码验证。
