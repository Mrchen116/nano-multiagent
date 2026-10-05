# 当前 Mac 工具链准备记录

记录日期：2026-10-05（Asia/Shanghai）。包含工具链准备及实际构建结果；不代替完整产品或真机验收。

- 主机 macOS 26.5.2，Apple Silicon。App Store 最新 Xcode 因要求 macOS 26.6 无法安装；未升级系统。
- 用户在 Chrome 登录 Apple Developer 后下载官方 `Xcode_26.4.1_Apple_silicon.xip`，解包至本次临时目录，`codesign --verify --deep --strict` 成功，再移动至此前不存在的 `/Applications/Xcode.app`。
- 用户明确回复“同意，继续设置”后接受当前显示的 Xcode and Apple SDKs Agreement，系统组件设置完成，Xcode 欢迎页可打开。
- `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -version`：Xcode 26.4.1 / Build version 17E202。
- 同样指定 `DEVELOPER_DIR` 的 `xcodebuild -showsdks` 列出 iOS 26.4 和 Simulator iOS 26.4 SDK；未改变全局 `xcode-select`。后续构建需显式指定本 Xcode 或在项目环境设此变量。
- `/tmp/nano-feat578-toolchain/Probe.swift` 只含 `import SwiftUI` 与一个 Text View；用 simulator SDK、`arm64-apple-ios26.0-simulator` 执行 `swiftc -typecheck`，exit 0。探针不属于产品代码。
- Xcode Components 下载并安装 iOS 26.4 runtime（26.4.1 / 23E254a）；iPhone 17 Pro simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257` 已启动并运行 Nano IM。
- 安装后磁盘当次约 35 GiB 可用。未删除用户文件，保留官方 XIP。

最新设备归档：`build.sh archive` 在产品 revision `051abdcf8`（含原生视觉修订、搜索清空刷新、输入框高度及任务图布局修复）通过，输出 arm64 IPA。Release Info.plist 为 `win.nanoim.ios`、版本 0.1.0、最低 iOS 26.0，无 ATS 任意加载例外。归档日志 `/tmp/nano-feat578-visual-archive-r4.log`，本地产物 `output/feat578/NanoIM-051abdcf8-unsigned.ipa`，SHA-256 `aee3b6b020c8098ff2c7f5ff24e1b79092b8c9bdc60b8986f0c5e106947bc6ca`。未签名 IPA 需 AltStore 重签，不能直接安装。

保留的自动化证据：原生视觉第一轮 `visual-tests-r1` 通过 22 项测试（12 XCTest + 10 Swift Testing）；其后的搜索提交、布局调整均重新编译，最终归档成功。独立静态 R7/R8 未留下具体 finding。这些结果不代替真实屏幕与交互验收；独立 P6 检查使用同一 `5ab02fd65` Debug binary，已覆盖专用 iPhone 14（390）及 iPhone 14 Pro Max（430）模拟器。普通和大字体独立视觉已限定通过，见 acceptance-visual-r3；`051abdcf8` 仅新增清空搜索刷新，已做独立窄复验。旧产物和截图仅对应其记录的 revision。

尚待完整模拟器产品验收、Mini 可达和 AltServer、iPhone 时段/配对/免费签名及专用 Bot 独占试验。用户已明确真机准备后置到有可安装版本后；Gate 2 R2 已通过，此时序不降低最终验收标准。
