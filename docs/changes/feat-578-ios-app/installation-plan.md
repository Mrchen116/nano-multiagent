# 免费安装与维护方案

状态：已完成模拟器构建、21 项原生测试及 Release arm64 IPA；模拟器独立产品验收进行中，尚未签名安装到真机或续签。用户已确定当前 Mac 构建、Mac mini 运行 AltServer。无需购买 Apple Developer Program，不使用 AltStore PAL。

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
6. AltServer 安装 AltStore Classic；在 AltStore 导入本次 IPA 并重新签名。保持同一个 Apple Account、Bundle identity 与 AltStore app mapping，记录实际 profile 到期与 IPA commit（不记录账号密码）。
7. 从 iPhone 图标启动，登录实际可访问的 IM；完成中文输入、图片文件、前后台恢复及管理动作。测试对象使用 [Tailscale HTTPS 隔离入口](evidence/device-access-plan.md)，不改变真实生产公司成员/通道/策略。
8. 拔掉 USB，手机与 Mini 同网，AltStore 刷新 Nano；记录刷新前后真实到期/刷新结果和重新启动成功。自动刷新若未发生，实际执行手动刷新；不能把 USB 成功称作 Wi-Fi 成功。

## 日常维护与恢复

打开 AltStore 检查实际到期日；在免费 profile 到期前刷新。App 内只提供说明和前台提醒开关，不显示推测出的“续签健康”。如果失败，依次核对 Mini 登录会话和 AltServer、手机同网、配对与 Wi-Fi sync；仍失败则 USB 连接恢复。网络可达性通过实际连接确认，Tailscale 在线本身不证明 Bonjour 发现或 AltServer 可达。

过期时保留现有 App 及其标识，先恢复 AltStore，再用同一身份重签/刷新 Nano。不得为了方便先卸载 App（会丢失本机数据）；服务端聊天仍归原 Nano 账号。证书被撤销、免费 App 数量或 App ID 限额时按签名工具实际错误处理，不创建随机 Bundle ID 绕过后冒充无损更新。

工具链的实际命令与边界见 [准备记录](evidence/toolchain-readiness.md)。

## 当前资源状态

| 项目 | 已知结果 | 尚待落实 |
|---|---|---|
| 当前 Mac | macOS 26.5.2，Apple Silicon；官方 Xcode 26.4.1（17E202）及 iOS 26.4 runtime 已安装；模拟器运行、原生测试和设备归档通过 | 完整模拟器产品验收与真机签名 |
| 磁盘 | 安装、runtime 和产物均保存在本机；未删除用户文件 | 后续下载前按实际空间检查 |
| Mini | 原已授权 AltServer 部署位置；本轮 SSH 连接超时 | 实际可达、AltServer版本/进程/GUI会话 |
| iPhone | 用户给定 15 Pro Max / 26.4 | 本 chat 使用时段、配对/签名/开发者模式 |
| Feishu E2E | 本机专用 env 文件存在且 0600；只读身份校验 verified=true、App ID 匹配、bot ready | 真实通道试验独占 Bot 仍待确认 |

验收不伪造过期或改系统时间。S30 的自然过期恢复需到期后的实际过程，或由用户明确授权等价验证后按调整的标准记录；提前手动刷新不能证明自然过期恢复。
