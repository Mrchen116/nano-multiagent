# feat-821 M1 Verification Evidence

## 1. 测试与构建验证摘要

| 层级 | 命令 | 结果 |
|---|---|---|
| 共享契约 + IM 更新路由 + 节点本地管理单测 | `pnpm exec vitest run packages/product-contracts/tests/node-update.test.ts apps/im-server/tests/node-updates.test.ts apps/node/tests/desktop-local-admin.test.ts apps/node/tests/node-updater.test.ts` | `4 passed`（`28/28` tests） |
| 生成客户端契约与 iOS 运行时校验 | `pnpm check:client-contracts && pnpm check:ios-runtime` | `0` drift / 全部通过 |
| Crewden Desktop Rust 单测与集成测试 | `cargo test --manifest-path apps/desktop/Cargo.toml` | `21/21 passed`（`16` lib + `4` attachment_transfer + `1` instance_lock，`0` warnings） |
| 前端 TypeScript 与全量 Vitest（含新增桌面无感更新单测） | `cd src/IM/frontend && npx tsc -b && npm test && npm run build` | `142/142` 文件通过（`1,363/1,363` tests），生产构建通过 |
| 前端类型根下共享契约独立校验 | `cd src/IM/frontend && npx tsc -p ../../../packages/product-contracts/tsconfig.json --typeRoots ./node_modules/@types --noEmit` | 通过 |

## 2. 隔离真实栈多视口浏览器交互验收（Journeys A–D）

使用独立端口、独立 SQLite、独立回环受信发布源与 `--isolated-root` 启动真实 `apps/im-server/lib/main.js` 与 `apps/desktop/target/debug/crewden-desktop --headless-host`，在 Chromium `2x` Retina 下覆盖 `1280×840`、`1280×720`、`420×680`（`zh` 与 `en`）执行全部四条验收旅程：

- **Journey A（未绑定本机节点的纯聊天桌面端静默准备 + 保草稿/保引用/保路由一键热切换）**：
  - 用户 `alex` 登录后选择「暂不绑定」，进入 `/chat/<conv_id>` 与 `Mia Lin` 真实会话，悬停引用对方消息并在输入框输入未发送草稿（含文字、Emoji 与 `@Mia Lin`，不点发送、不切换会话）。
  - 服务端发布 `v1.4.0`（`shell_protocol: 1`），`crewden-desktop` 自动静默下载并完成 SHA-256 校验与解包至 `versions/<sha256>/`，进入 `ready_to_switch`。
  - 模拟窗口失焦（`blur`，但 `window_visible == true`）：确认 `reload_generation` 不变，绝不在窗口可见时强行刷新打断用户。
  - 几何非遮挡实测：左下角展开胶囊右边界 `x = 335.0px`，右侧聊天输入区左边界 `x = 447.4px`（完全落在左侧会话列内，零像素遮挡消息流、引用条与输入框）。
  - 打开 `UserMenu` 时左下角浮层胶囊自动收起让位，关闭菜单恢复；在 `1280×720` 下点击「点一下秒换新」，页面自动热切换刷新后仍停留在同一 `/chat/<conv_id>`（`_desktop_reload` 参数自动清除），未发送草稿与回复引用条 100% 原样保留，左下角呈现薄荷绿 `✓ 已换上 v1.4.0` 确认提示。
- **Journey B（已绑定在线本机节点存在运行中任务 `active_tasks = 2` 时等待收尾与取消）**：
  - 本机节点通过真实 `/im/ws/gateway` 在线连接，触发升至 `v1.4.1` 后桌面端进入 `waiting_for_tasks`（`1280×840` 左下角胶囊展示 `⏳ 等待任务收尾` + `取消本次换新`，`420×680` 窄屏顶部流式条展示 `⏳ 等待当前任务收尾 · 跑完后自动换上 v1.4.1` + `取消换新` 且不遮挡消息流与输入框）。
  - 点击「取消本次换新」，远端更新操作标记取消并由节点回报 `cancelled`，桌面端干净回到 `ready_to_switch` 且期间未中断在途任务。
- **Journey C（未绑定「电脑」页顶置卡片、手动检查、`updater-prefs.json` 跨重启持久化、中英双语、窄屏 `/me` 与断连重试）**：
  - 未绑定本机节点访问 `/settings/nodes`：无重复遮罩弹窗阻挡，顶置 `DesktopClientUpdateCard` 清晰展示当前版本，点击「检查更新」即时反馈 `已是最新版本 ✓`；切换英文（`en`）核验文案自然无工程黑话。
  - 关闭「自动保持最新」后终止并重启同一 `--isolated-root` 的 `crewden-desktop`，确认 `persisted_port` 与 `updater-prefs.json`（`auto_update: false`）跨重启保留。
  - 模拟发布源 `503` 断连后手动检查呈现自然语言失败说明与「重试更新」，恢复发布源后点击重试立即恢复正常。
  - `420×680` 窄屏访问 `/me`：`DesktopCompactUpdateBox` 原生融入身份卡下方，且顶部不重复渲染窄屏横幅。
- **Journey D（`shell_protocol: 2` `v2.0.0` 原生客户端安装包流式下载、进度条、macOS DMG + Gatekeeper 指引与安全打开）**：
  - 服务端发布 `v2.0.0`（`shell_protocol: 2`, `macos_distribution: "unnotarized"`），桌面端自动识别为 `mode: "installer"`（全界面零 `incompatible` / `shell_protocol` / `SHA-256` 黑话）。
  - 点击「下载并升级客户端」，实时渲染 `downloading_installer` 进度条与已下载体积（`MB / MB`）；SHA-256 校验通过后进入 `installer_ready`，展示拖入 `Applications` 替换与 macOS「隐私与安全性 → 仍要打开」两步清晰指引。
  - 点击「打开新版映像」（`CREWDEN_SUPPRESS_OS_OPEN=1`），核实 `<isolated_root>/desktop/open-actions.jsonl` 准确记录 `action: "launch_installer"` 与校验通过的 `.dmg` 路径及 SHA-256。

## 3. 截图定位（仓外 Artifacts 目录）

真实界面截图保存在会话 Artifacts 目录 `screenshots/real/`（不入 Git）：
- `01-real-chat-ready-1280x840.png`：纯聊天模式左下角 `v1.4.0` 就绪胶囊 + 展开亮点 + 右侧未发草稿与引用条零遮挡（`1280×840`）
- `02-real-user-menu-ready-1280x840.png`：打开 `UserMenu` 时浮层胶囊自动让位，菜单内展示版本状态、一键秒换新与「自动保持最新」开关（`1280×840`）
- `03-real-chat-just-updated-1280x720.png`：一键秒换新自动重载后保留原会话路由、回复引用与未发草稿，并显示 `✓ 已换上 v1.4.0`（`1280×720`）
- `04-real-nodes-unbound-1280x840.png`：未绑定节点时 `/settings/nodes` 顶置 `Crewden 桌面端` 更新卡片与手动检查 `已是最新版本 ✓`（`1280×840`, `zh`）
- `05-real-nodes-en-1280x840.png`：同页面英文界面（`1280×840`, `en`）
- `06-real-narrow-me-420x680.png`：`420×680` 窄屏 `/me` 个人页内嵌更新卡片与自动更新开关
- `07-real-waiting-tasks-1280x840.png`：在线节点存在在途任务时 `⏳ 等待任务收尾` 与「取消本次换新」（`1280×840`）
- `08-real-narrow-waiting-420x680.png`：`420×680` 窄屏聊天页顶部流式等待条与底部草稿保留
- `09-real-installer-downloading-1280x840.png`：`v2.0.0` 原生客户端安装包流式下载实时进度条（`1280×840`）
- `10-real-installer-dmg-ready-1280x840.png`：`v2.0.0` macOS `.dmg` 校验就绪、拖入 `Applications` 替换及 Gatekeeper 首次打开提示（`1280×840`）

## 4. 测试资源回收核实

验收脚本在 `finally` 块内已终止本轮启动的全部临时 `im-server`、Gateway WebSocket 模拟进程、回环发布源 HTTP 服务与 `crewden-desktop` 进程，并清理临时 `--isolated-root` 与 SQLite 目录。
