# 免费安装与维护方案

本版交付更新（2026-10-09）：用户接受先合入当前版本，见 [交付决定](release-acceptance.md)。手机实际剪贴板/大字号补测及临时状态还原见 [R4](M1-native-app/acceptance-device-r4.md)，Tailscale 已恢复测试前 Not Connected。中文 IME、VoiceOver 和下文 Mini 无线续签/自然到期实证由 [#327](https://github.com/Mrchen116/nano-multiagent/issues/327) 后续跟进；以下日期段保留当时状态，不代表维护已完成。

状态（2026-10-08）：App源码 `383a5a9b1` 保持冻结，最新原生变更 `d17e70c4f1` 仅改两份照片用途声明。免费Personal Team Release已通过Air无线原地安装；独立[真机R2](M1-native-app/acceptance-device-r2.md)完成登录、账号隔离、聊天、Files及代表管理旅程，[真机R3](M1-native-app/acceptance-device-r3.md)完成仅添加授权后的实际照片保存/选择/发送/再开，关闭DEV2-01且新增问题0。Simulator可测范围与旧公开head的五项required CI完成，新变更发布后须观察其自己的远端CI。手机Tailscale实际Connected；Mini原有屏幕共享已接通，其真实AltServer显示没有连接设备、Finder也无手机，设备侧栏显示已启用，仍需用户直接USB接Mini完成首次配对前置。完整物理中文IME/软件键盘/VoiceOver/剪贴板内容、Mini无线续签与自然到期恢复尚未通过，Full最终验收、canonical归并及归档未完成，PR仍为草稿。当前profile到期仍为2026-10-13 19:31:19（Asia/Shanghai）；原地更新不等于延长有效期。包身份和无线安装见[Air记录](evidence/air-altserver-readiness.md)，Mini实际菜单见[Mini记录](evidence/mini-altserver-readiness.md)，Simulator范围见[R5](M1-native-app/acceptance-simulator-r5.md)/[R6](M1-native-app/acceptance-simulator-r6.md)。无需购买Apple Developer Program，不使用AltStore PAL。

2026-10-06 最新安排：用户要求『模拟环境上完整测完了吗，真机先跳过』。当前只补模拟器剩余分支；更新后的真机体验、无线续签和自然到期恢复后置，不要求用户为本轮解锁镜像，也不把这些后置项目算作模拟器失败。原安装事实及最终要求保留。

2026-10-06 拓扑修正：用户补充 Mini 与手机异地，手机与当前 Air 在一起，并授权本 chat 接管已连接的 iPhone Mirroring。首次安装改在 Air 推进，Air AltServer 已安装并确认运行；当时USB尚未接入，后续配对与安装事实见下一段。下方 Mini 同网维护步骤保留为原方案，不能按现有异地条件执行或视为已验收。Remote AltServers边界见[Air 准备记录](evidence/air-altserver-readiness.md)。

随后用户已接USB、开启Developer Mode并登录Xcode。私有临时项目完成免费签名，实际profile到期2026-10-13 19:31:19（Asia/Shanghai），安装success。之后经授权完成证书信任，实际启动、隔离HTTPS登录、原生建群和真实peer回复42呈现已观察；用户否定聊天UX，正在按[本轮记录](M1-native-app/ux-correction-r1.md)修正。下方AltStore/Mini维护尚未实施，不能由Xcode USB成功替代。

## 官方约束与选择

核实日期：2026-10-05。

- [Apple Developer account](https://developer.apple.com/help/account/basics/about-your-developer-account)：Personal Team 的 provisioning profile 有效期 7 天，App ID 和设备也有限额；不是永久分发许可。
- [AltStore Classic FAQ](https://faq.altstore.io/altstore-classic/your-altstore)：免费账户同时激活的 sideload App 有数量限制；AltStore 自身占一个位置，首版 Nano 只含一个 App target，无扩展。
- [AltServer](https://faq.altstore.io/altstore-classic/altserver)：AltServer 运行时可通过 USB 或同一 Wi-Fi 侧载/刷新。后台自动尝试不构成必然成功保证。
- [macOS 安装指南](https://faq.altstore.io/altstore-classic/how-to-install-altstore-macos)：首次配对、Wi-Fi sync、信任和开发者模式依官方实际界面完成。账号凭据只在 Apple/AltStore/AltServer 本地流程输入，不记录到仓库、聊天或构建日志。
- [Apple capabilities](https://developer.apple.com/help/account/reference/supported-capabilities-ios)：不把免费签名作为 APNs 能力依据；本期不申请 push entitlement。
- [Xcode 系统要求](https://developer.apple.com/xcode/system-requirements)：Xcode 26.4.1 支持 macOS 26.2–26.x、含 iOS 26.4 SDK。当前 Mac 26.5.2，目标设备 26.4。App Store 最新版要求 macOS 26.6，已实际被拒；改从 Apple Developer 官方下载 26.4.1 Apple silicon。

用户于 2026-10-05 明确先做出 App，再安排真机；以下步骤 1–3 可先推进，4–8 在有可安装版本后安排。最终真机、同网续签和过期恢复标准不变。

## 构建与安装顺序

1. 当前 Mac 官方下载安装 Xcode 26.4.1，首次协议由用户确认；安装所需 iOS SDK/simulator 后记录 `xcodebuild -version` 与 `-showsdks`。只保留 iOS 所需平台，避免下载全部可选平台。
2. 在 unit worktree 构建 Simulator 并走原生 UI 真栈旅程。记录 revision、scheme、SDK、simulator UDID 和测试输出。不能把 HTML 原型称作 iOS build。
3. Release device archive 使用 `CODE_SIGNING_ALLOWED=NO`；构建脚本从 archive 的真实 app 建 `Payload/NanoIM.app` IPA，校验 arm64、Info.plist 与 entitlements。这个 IPA 仍需侧载工具签名才能运行。
4. Mini 从 [AltStore 官方](https://altstore.io/) 安装 AltServer，用户 GUI 登录会话持续运行。只检查/安装 AltServer，不触碰现有 IM/Gateway。设置开机登录启动需在已授权安装维护范围内完成。
5. 获得本 chat 真机操作时段后 USB 配对，Finder 开启 Wi-Fi 同步，完成设备信任和 Developer Mode。用户自行处理账号/验证码与设备安全确认，不争用其他 chat 的 iPhone Mirroring。
6. AltServer 安装 AltStore Classic；在 AltStore 导入本次 IPA 并重新签名。先核对真实安装标识：首次AltStore导入不能被当作对当前Xcode安装的直接接管（见下方身份边界）。保留既有App及数据；在AltStore建立稳定mapping后，后续更新/续签维持同一个Apple Account和mapping，记录实际profile到期与IPA commit（不记录账号密码）。
7. 从 iPhone 图标启动，登录实际可访问的 IM；完成中文输入、图片文件、前后台恢复及管理动作。测试对象使用 [Tailscale HTTPS 隔离入口](evidence/device-access-plan.md)，不改变真实生产公司成员/通道/策略。
8. 拔掉 USB，手机与 Mini 同网，AltStore 刷新 Nano；记录刷新前后真实到期/刷新结果和重新启动成功。自动刷新若未发生，实际执行手动刷新；不能把 USB 成功称作 Wi-Fi 成功。

## 日常维护与恢复

打开 AltStore 检查实际到期日；在免费 profile 到期前刷新。App 内只提供说明和前台提醒开关，不显示推测出的“续签健康”。如果失败，依次核对 Mini 登录会话和 AltServer、手机同网、配对与 Wi-Fi sync；仍失败则 USB 连接恢复。网络可达性通过实际连接确认，Tailscale 在线本身不证明 Bonjour 发现或 AltServer 可达。

过期时保留现有 App 及其标识，先恢复 AltStore，再用同一身份重签/刷新 Nano。不得为了方便先卸载 App（会丢失本机数据）；服务端聊天仍归原 Nano 账号。证书被撤销、免费 App 数量或 App ID 限额时按签名工具实际错误处理，不创建随机 Bundle ID 绕过后冒充无损更新。

工具链的实际命令与边界见 [准备记录](evidence/toolchain-readiness.md)。

## 当前资源状态

| 项目 | 已知结果 | 尚待落实 |
|---|---|---|
| 当前 Mac | macOS 26.5.2，Apple Silicon；官方 Xcode 26.4.1（17E202）及 iOS 26.4 runtime；36项原生测试、最新归档、无线原地安装与物理R2/R3范围已证 | 完整物理输入、辅助访问及手机剪贴板内容 |
| 磁盘 | 安装、runtime 和产物均保存在本机；未删除用户文件 | 后续下载前按实际空间检查 |
| Mini | SSH与既有Screen Sharing可操作，macOS26.5.2；官方AltServer1.8 /97运行，实际菜单为No Connected Devices，Finder无手机且设备显示已勾选，见[准备记录](evidence/mini-altserver-readiness.md) | 用户直接USB连接、首次信任/配对、Wi-Fi sync、登录启动与拔线刷新 |
| iPhone | 实际15 Pro Max /26.4；Air配对/Developer Mode/免费安装/信任、HTTPS登录及物理R2/R3范围已证 | 完整中文与辅助访问/剪贴板物理范围；Mini无线续签/自然到期恢复 |
| Feishu E2E | 专用 Bot 独占 listener；原生新增/凭据保留替换/connected/停用证据保留。离线、unknown/受限诊断、实际权限更新、受控停止失败及原生重试真实停止、隔离历史保留已闭环，见[R5](M1-native-app/acceptance-simulator-r5.md)/[R6](M1-native-app/acceptance-simulator-r6.md) | 本轮历史为真实IM repository种子，不代表平台收发；故障为明确受控条件，不改真实平台权限 |

验收不伪造过期或改系统时间。S30 的自然过期恢复需到期后的实际过程，或由用户明确授权等价验证后按调整的标准记录；提前手动刷新不能证明自然过期恢复。


## Xcode 安装到 AltStore 的身份边界

2026-10-08按[官方Classic源码](https://github.com/altstoreio/AltStore/blob/fafd76ee1a8a19c723146de278660aacce9ded5d/AltStore/Operations/FetchProvisioningProfilesOperation.swift#L177)核对：首次普通App导入时使用原bundle加Team后缀；只有此前由AltStore建立、且Team匹配的mapping才沿用它的resigned bundle。随后[重签流程](https://github.com/altstoreio/AltStore/blob/fafd76ee1a8a19c723146de278660aacce9ded5d/AltStore/Operations/ResignAppOperation.swift#L118)实际把CFBundleIdentifier替换为profile标识。当前Xcode安装是 `win.nanoim.ios`，不能推断首次AltStore导入会原地续签这个安装或继承它的本机容器。

因此保留当前安装，不以卸载/随机ID绕过。若建立AltStore管理的安装，必须把首次mapping、是否出现第二App及本机登录/设置边界如实记录；随后使用同一Nano账号证明原服务端历史可读，再实测该稳定mapping的无线刷新。新安装成功、原安装无线更新或文档建议均不能替代Mini S30刷新/到期恢复。当前尚未安装或导入AltStore，亦未证明Mini已与目标手机配对。
