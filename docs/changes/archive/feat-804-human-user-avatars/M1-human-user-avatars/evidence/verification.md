# M1 Verification Evidence — `feat-804-human-user-avatars`

## 1. 窄反馈与包级单测 / 构建矩阵

| Claim | Method | Result | Locator / Command | Limit |
|---|---|---|---|---|
| 服务端静态图片校验、EXIF 剥离、256×256 WebP 归一化、4xx 保旧、受保护可见性矩阵、实时流 `user.profile_updated` 广播、同账号并发写串行锁与 Agent/PA 零上下文污染 | Vitest 集成与契约测试 | **63 / 63 passed**（6 个测试文件） | `pnpm build && pnpm typecheck && pnpm exec vitest run apps/im-server/tests/user-avatar.test.ts apps/im-server/tests/tenancy.test.ts apps/im-server/tests/identity.test.ts apps/im-server/tests/contacts.test.ts apps/im-server/tests/personal-agent.test.ts packages/personal-assistant/tests/tool-references.test.ts` | 进程内 HTTP/WebSocket 与临时磁盘实例，不替代真实浏览器与原生模拟器交互 |
| Web / 桌面端 `AvatarCropDialog`（`>2048px` 客户端预缩图、Portal 挂载即绘 480×480 预览、ObjectURL 即时释放、显示名草稿保留）、`avatarBlobStore` 单飞缓存与登出释放、全站槽位一致性与 `.chat-message-quote` 零头像 | Vitest + TypeScript `-b` + Vite 生产静态构建 | **28 / 28 passed**（4 个测试文件，含 `account-page.test.tsx` 7/7），`tsc -b` 0 errors，`npm run build` 通过 | `cd src/IM/frontend && npx vitest run src/features/settings/account/account-page.test.tsx src/features/chat/components/person-avatar-consistency.test.tsx src/features/chat/hooks/use-membership-cache.test.tsx && npx tsc -b && npm run build` | jsdom 环境不替代真实 Chromium 视口布局与多端并发 |
| iOS 原生 `ChatRepository` v9 迁移（`actors.avatar_version` 持久元数据）、`AvatarImageProcessor` 预缩图/GIF 拒绝/512px 裁剪编码、`AvatarImageStore` ephemeral 内存缓存与世代隔离、未映射外部发送者回退及 Release 归档编译 | Xcode 26.4.1 `build.sh test` + `build.sh archive` | `NanoIMTests` 全绿通过；Release 设备归档 `** ARCHIVE SUCCEEDED **` | `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer NANO_IOS_SIMULATOR_ID=FC71F6BF-E944-43F2-B69E-7EFAD031B24D ./src/IM/ios/scripts/build.sh test` 及 `./src/IM/ios/scripts/build.sh archive` | 模拟器单测与未签名归档不替代真机相册/AltStore 无线续签 |

---

## 2. 隔离真栈 Web / 桌面端端到端体验验证

- **隔离运行环境**：`./scripts/e2e-up.sh --wt /Users/czj/.t3/userdata/antigravity-tmp/ac0a3dfd6ddd/run-3VWh0f/nano-e2e-804.UMfCXw`，同源监听 `http://127.0.0.1:64571`（独立 SQLite、独立 `IM_UPLOAD_DIR`、独立 Gateway 节点；验证与独立审查结束后统一回收）。
- **验证方法**：真实 Playwright Chromium 双上下文并发连接隔离真栈，覆盖桌面 `1280×800 @2x` 与移动窄屏 `390×844 @2x`（中英文双语）。

| 场景与契约断言 | 实测结果 | 证据定位（仓外会话产物目录 `scratch/live-evidence/`） |
|---|---|---|
| 桌面端左下角竖向导航轨基线（`.im-shell-rail` 宽 `88px`，`<UserMenu />` 位于 `x=15.5, y=736` 左下角，未挪至右上角） | **PASS** | `03-desktop-account-uploaded-rail.png`、`web-e2e-summary.json#desktop_bottom_left_rail` |
| 非法 GIF 动图与 `>5 MiB` 文件原位拦截且不弹裁剪框、不覆盖未保存显示名草稿 | **PASS** | `01-desktop-account-error-draft.png`、`web-e2e-summary.json#gif_rejected_keeps_draft` |
| `4200×3200` 大图客户端预缩图、打开裁剪框即刻渲染单画布圆形取景（`canvasCount=1`、`centerPixelAlpha=255`、无冗余双小圆预览或数值倍率） | **PASS** | `02-desktop-crop-dialog.png`、`web-e2e-summary.json#crop_dialog_decluttered_and_painted_on_open` |
| 确认保存后账号页 `56px` 圆形照片与左下角 `36px` 导航头像即时切换为 `blob:` URL，且保留未保存显示名草稿 `林夏（未保存草稿）` | **PASS** | `03-desktop-account-uploaded-rail.png`、`web-e2e-summary.json#upload_preserves_name_draft` |
| 在线同事停留在非聊天路由 `/people` 时，通过实时流 `user.profile_updated` 即时刷新对方圆形照片头像 | **PASS** | `04-peer-people-realtime-sync.png`、`web-e2e-summary.json#peer_non_chat_route_realtime_sync` |
| 群聊发言人照片头像、无头像成员柔和色首字母圆章、点击头像 `PersonPopover` 卡片同步显示照片，且引用回复块 `.chat-message-quote` 内 **0 个 `<img>` / 0 个 `.chat-avatar`** | **PASS** | `05-desktop-group-chat-quote-popover.png`、`web-e2e-summary.json#quote_block_has_zero_avatars` |
| 公司成员页 `/settings/company` 含 `pending` 待批准申请人「周宁」与已激活成员的圆形照片头像，任务详情 `/tasks/:graphId` 负责人圆形照片头像 | **PASS** | `06-desktop-company-members.png`、`07-desktop-tasks-avatar.png` |
| 移除自定义头像立即回退柔和色首字母圆章并保留未保存显示名草稿 `林夏（移除时保留草稿）` | **PASS** | `07b-desktop-account-removed-fallback.png`、`web-e2e-summary.json#remove_restores_initials_circle_and_keeps_draft` |
| 移动窄屏 `390×844` `/me` 身份卡与中英文裁剪弹窗（`208×208` 舞台，英文 `Choose another / Cancel / Save` `width=358 <= 390` 零溢出） | **PASS** | `08-mobile-me.png`、`09-mobile-crop-zh.png`、`10-mobile-crop-en.png` |
| 真栈受保护读取可见性（未登录 `401`、无关独立个人账号 `404`、可见同事 `200`）与退出登录 `URL.revokeObjectURL` 释放（`revokedCount=2`）、全程 `pageErrors=[]` | **PASS** | `web-e2e-summary.json#live_visibility_matrix`、`#logout_revokes_blob_urls`、`#zero_page_errors` |

---

## 3. 隔离真栈 iOS 原生模拟器端到端体验与沙盒无落盘核验

- **专用临时模拟器**：`NanoIM feat-804 E2E`（`iPhone 17` / iOS 26.4，UDID `A6025E88-5CCD-4D39-9243-AAAF71CE832D`，本轮新建，原有模拟器均保持 `Shutdown` 未触碰）。
- **执行入口**：`NanoIMJourney` 标准 XCUITest（`CrewdenParityUITests/testManageHumanProfilePhotoAndVerifyTeamSurfaces`）直连 `http://127.0.0.1:64571`，耗时 `61.8s` `** TEST EXECUTE SUCCEEDED **`。

| 场景与契约断言 | 实测结果 | 证据定位（代码与仓外 `scratch/live-evidence/ios-pass/`） |
|---|---|---|
| 原生群聊消息流真人圆形照片头像、无头像成员首字母圆章、引用回复条 `ChatReplyLabel` 保持纯文本竖线样式无头像 | **PASS** | `ios-group-chat-avatars.png`、`src/IM/ios/UITests/CrewdenParityUITests.swift` |
| 原生「我的」顶部 `76pt` 圆形照片头像与「个人助手」角色剪影区分、「公司成员」含 `pending` 申请人「周宁」`36pt` 圆形照片头像 | **PASS** | `ios-me-space-avatar.png`、`ios-company-members-avatars.png` |
| 「个人资料与语言」展示 `64pt` 圆形头像、`更换头像` 与 `移除头像`；编辑显示名后点击 `移除头像` 立即回退首字母圆章且保留 `林夏（草稿保留）` | **PASS** | `ios-account-with-avatar.png`、`ios-account-removed-keeps-draft.png` |
| 从系统相册 `PhotosPicker` 选择静态照片 -> `调整头像` 圆形取景裁剪缩放 -> 点击 `保存` 上传成功并即时刷新为裁剪后照片 -> 终止并冷启动恢复 | **PASS** | `ios-avatar-crop-sheet.png`、`ios-account-reuploaded.png`、`ios-cold-relaunch-inbox.png` |
| 沙盒容器磁盘与 SQLite 元数据核查：`cache_meta.schema.version = 9`，`actors` 表仅存 `avatar_version` 字符串（如 `1117f0979d7e`），整个 App Data Container 除 `chat.sqlite` 与系统状态外 **0 个头像图片文件 / 0 个 URLCache 缓存库** | **PASS** | `xcrun simctl get_app_container ... data` 全量 `find -type f` 与 `sqlite3 chat.sqlite` 核验 |

- **已知验证边界**：本轮原生体验在 iOS 26.4 Simulator + 本地隔离真栈完成，不替代真机物理相册权限弹窗、VoiceOver 实机手势与 AltStore 无线侧载续签。
