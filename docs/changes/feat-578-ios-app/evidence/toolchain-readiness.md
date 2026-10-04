# 当前 Mac 工具链准备记录

记录日期：2026-10-05（Asia/Shanghai）。仅为构建资源检查，不是 Nano App 构建或产品验收。

- 主机 macOS 26.5.2，Apple Silicon。App Store 最新 Xcode 因要求 macOS 26.6 无法安装；未升级系统。
- 用户在 Chrome 登录 Apple Developer 后下载官方 `Xcode_26.4.1_Apple_silicon.xip`，解包至本次临时目录，`codesign --verify --deep --strict` 成功，再移动至此前不存在的 `/Applications/Xcode.app`。
- 用户明确回复“同意，继续设置”后接受当前显示的 Xcode and Apple SDKs Agreement，系统组件设置完成，Xcode 欢迎页可打开。
- `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -version`：Xcode 26.4.1 / Build version 17E202。
- 同样指定 `DEVELOPER_DIR` 的 `xcodebuild -showsdks` 列出 iOS 26.4 和 Simulator iOS 26.4 SDK；未改变全局 `xcode-select`。后续构建需显式指定本 Xcode 或在项目环境设此变量。
- `/tmp/nano-feat578-toolchain/Probe.swift` 只含 `import SwiftUI` 与一个 Text View；用 simulator SDK、`arm64-apple-ios26.0-simulator` 执行 `swiftc -typecheck`，exit 0。探针不属于产品代码。
- Xcode Components 正在下载独立 iOS 26.4.1 simulator runtime（8.46 GB）；当次观察 495.7 MB / 6%。`simctl list runtimes` 仍为空，不能称模拟器已可用。截图：`output/feat578/xcode-installed-runtime-download.png`。
- 安装后磁盘当次约 35 GiB 可用。未删除用户文件，保留官方 XIP。

尚待 runtime 下载/安装完成后的启动验证；Mini 可达和 AltServer、iPhone 时段/配对/免费签名条件、专用 Bot 独占试验。用户已明确真机准备后置到有可安装版本后；Gate 2 等待按此时序修订后的独立复核。
