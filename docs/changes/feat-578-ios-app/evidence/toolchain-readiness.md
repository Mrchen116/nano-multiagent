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

最新设备归档：`build.sh archive` 在产品 revision `5de8ffdb4`（包含已实测的管理/媒体功能、配置分界锚定，以及发送和Latest的滚动布局修复）通过，输出 arm64 IPA。Release Info.plist 为 `win.nanoim.ios`、版本 0.1.0、最低 iOS 26.0，无 ATS 任意加载例外或embedded provisioning profile。归档日志 `/tmp/nano-feat578-send-scroll-archive-r13.log`，本地产物 `output/feat578/NanoIM-5de8ffdb4-unsigned.ipa`，2,339,236 bytes，SHA-256 `6e3a9a25d939f344d851c2a0a77cc490729149e707edebabda77e724c286e044`。未签名 IPA 需 AltStore 重签，不能直接安装。

此版全27项原生测试通过（17 XCTest+10 Swift Testing），日志`/tmp/nano-feat578-ci-ios.log`，xcresult `Test-NanoIM-2026.10.05_16-29-42-+0800.xcresult`；独立R19无存活code finding。390 Simulator保留数据原地安装此版，PID4396。独立R12关闭既有M2与实时M3分界顺序问题，R13关闭多行发送布局挂起：composer立即清空、真实bash运行中可见、Home后从主屏恢复唯一完成结果和工具详情，长历史02→Latest最终消息正常可见且返回响应；root此时CPU0.0%。附件/管理此前有效范围保留。完整范围及限制见各报告，整体产品门禁与物理安装续签仍未通过。

其后同一版R15实际发现任务嵌套引用逐层返回、根任务详情入口缺失。已完成最小源码修正与成功构建，新包复验尚未完成；上列5de8归档仍含该任务问题，不能当作已完成验收的安装候选。

同一冻结源码完成本地CI：4,120项Python测试（1997 agent/PA + 2123 remaining）、808项Web测试、Ruff check/format与281份维护文档完整性通过。npm audit按仓库critical门禁通过，当前报告仍有2 low/3 moderate/2 high，无critical；未扩大范围升级Web依赖。日志为`/tmp/nano-feat578-ci-*`。[GitHub macos-26 runner清单](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md)当次仍列Xcode26.4.1路径与iOS26.4 runtime，与本unit新增iOS CI job一致；尚未建立PR，远端CI未执行。

保留的自动化证据：原生视觉第一轮 `visual-tests-r1` 通过 22 项测试（12 XCTest + 10 Swift Testing）；其后的搜索提交、布局调整均重新编译，最终归档成功。独立静态 R7/R8 未留下具体 finding。这些结果不代替真实屏幕与交互验收；独立 P6 检查使用同一 `5ab02fd65` Debug binary，已覆盖专用 iPhone 14（390）及 iPhone 14 Pro Max（430）模拟器。普通和大字体独立视觉已限定通过，见 acceptance-visual-r3；`051abdcf8` 仅新增清空搜索刷新，已做独立窄复验。旧产物和截图仅对应其记录的 revision。

专用 Bot 已通过本次独占的原生添加、保留/替换密钥、连接、停用与删除旅程，见 `M1-native-app/acceptance-r4.md`。尚待其余模拟器产品验收、Mini 可达和 AltServer、iPhone 时段/配对/免费签名。用户已明确真机准备后置到有可安装版本后；Gate 2 R2 已通过，此时序不降低最终验收标准。

`ba202f5d3` 的IM/Gateway空cadence指纹修复经过50项相关Python测试；同时包含前轮live读取保留heartbeat_json修复。当前只载入本次隔离服务，未部署生产。原生产品R5已完成心跳值保存/重开、空配置再保存和真实版本冲突反馈的窄复验；其它旅程继续记录在 acceptance-r5，不能用这些构建/测试代替全部S1–S30。
