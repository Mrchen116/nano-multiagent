# 当前 Mac 工具链准备记录

更新日期：2026-10-07（Asia/Shanghai）。包含工具链准备及实际构建结果；不代替完整产品或真机验收。

最新设备归档：产品 `383a5a9b1` 的 Release archive 通过，日志 `/tmp/nano-feat578-release-sim6.log`。本地产物 `output/feat578/NanoIM-383a5a9b1-unsigned.ipa`，2,510,845 bytes，SHA-256 `8c0eea77493879b53dd113ab0ec57173f37803ba95286088a4f3ceb0a8a1c242`；arm64、bundle `win.nanoim.ios`、版本0.1.0、最低iOS26.0，无ATS例外/embedded profile。未签名，需现有免费签名流程重签；本轮不安装到真机。

原生全36项测试通过（26 XCTest + 10 Swift Testing），`/tmp/nano-feat578-image-paste-green.log`，xcresult `Test-NanoIM-2026.10.07_01-13-53-+0800.xcresult`。后续仅节点离线409中文原因、实际重连标签和自动刷新保留错误窄修，构建通过 `/tmp/nano-feat578-channel-feedback-build.log`，上述测试保留其有效范围；[独立静态R4](../M1-native-app/code-review-simulator-r4.md) finding为空。390最新安装 `383a5a9b1`，模拟器可测范围以[R5全矩阵](../M1-native-app/acceptance-simulator-r5.md)+[R6最终闭环](../M1-native-app/acceptance-simulator-r6.md)为准；430仅自动测试。物理iPhone仍8e03b3e78，完整VoiceOver及安装维护体验按用户安排后置，不能混同。此为草稿评审候选，Full最终门槛保持开放。

以下记录保留各旧版本的原范围，旧IPA不作为最新安装候选。

- 主机 macOS 26.5.2，Apple Silicon。App Store 最新 Xcode 因要求 macOS 26.6 无法安装；未升级系统。
- 用户在 Chrome 登录 Apple Developer 后下载官方 `Xcode_26.4.1_Apple_silicon.xip`，解包至本次临时目录，`codesign --verify --deep --strict` 成功，再移动至此前不存在的 `/Applications/Xcode.app`。
- 用户明确回复“同意，继续设置”后接受当前显示的 Xcode and Apple SDKs Agreement，系统组件设置完成，Xcode 欢迎页可打开。
- `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -version`：Xcode 26.4.1 / Build version 17E202。
- 同样指定 `DEVELOPER_DIR` 的 `xcodebuild -showsdks` 列出 iOS 26.4 和 Simulator iOS 26.4 SDK；未改变全局 `xcode-select`。后续构建需显式指定本 Xcode 或在项目环境设此变量。
- `/tmp/nano-feat578-toolchain/Probe.swift` 只含 `import SwiftUI` 与一个 Text View；用 simulator SDK、`arm64-apple-ios26.0-simulator` 执行 `swiftc -typecheck`，exit 0。探针不属于产品代码。
- Xcode Components 下载并安装 iOS 26.4 runtime（26.4.1 / 23E254a）；iPhone 17 Pro simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257` 已启动并运行 Nano IM。
- 安装后磁盘当次约 35 GiB 可用。未删除用户文件，保留官方 XIP。

历史设备归档：`build.sh archive` 在产品 revision `107290abe`（保留管理/媒体、配置分界及滚动修复，补齐根任务详情入口和深层引用返回）通过，输出 arm64 IPA。Release Info.plist 为 `win.nanoim.ios`、版本 0.1.0、最低 iOS 26.0，无 ATS 任意加载例外或 embedded provisioning profile。归档日志 `/tmp/nano-feat578-task-reference-archive-r16.log`，本地产物 `output/feat578/NanoIM-107290abe-unsigned.ipa`，2,339,620 bytes，SHA-256 `740cb5215440249d14eb50e02d32a653fb9bb6745a157278a575c62313819650`。未签名 IPA 需 AltStore 重签，不能直接安装。

此版全27项原生测试通过（17 XCTest+10 Swift Testing），日志 `/tmp/nano-feat578-task-reference-tests-r16.log`，xcresult `Test-NanoIM-2026.10.05_17-05-48-+0800.xcresult`；独立 R20 无存活 code finding。390 Simulator 保留数据原地安装此版，PID10990。独立 R12 关闭既有 M2 与实时 M3 分界顺序问题，R13 关闭多行发送布局挂起：composer 立即清空、真实 bash 运行中可见、Home 后从主屏恢复唯一完成结果和工具详情，长历史02→Latest最终消息正常可见且返回响应；root 当次 CPU0.0%。附件/管理此前有效范围保留。完整范围及限制见各报告，整体产品门禁与物理安装续签仍未通过。

R15 在旧 `5de8ffdb4` 实际发现任务嵌套引用逐层返回、根任务详情入口缺失。[R16 原生窄复验](../M1-native-app/acceptance-r16.md)已关闭两项问题：根详情直接可读选择/结果/说明，最深 Check 一次引用关闭全部详情进入正确群，只添加一份可编辑草稿且不自动发送；删除本次测试群后重读也移除失效回聊入口，任务关系保持。旧归档仅保留其历史证据，不再作为最新安装候选。

`5de8ffdb4` 冻结源码完成本地 CI：4,120项 Python 测试（1997 agent/PA + 2123 remaining）、808项 Web 测试、Ruff check/format与281份维护文档完整性通过；`107290abe` 仅改变 TasksView，上述未变 Python/Web 证据保留，原生27项已在新候选重新通过。npm audit 按仓库 critical 门禁通过，当前报告仍有2 low/3 moderate/2 high，无 critical；未扩大范围升级 Web 依赖。日志为 `/tmp/nano-feat578-ci-*`。[GitHub macos-26 runner清单](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-Readme.md)当次仍列 Xcode26.4.1 路径与 iOS26.4 runtime，与本 unit 新增 iOS CI job 一致；尚未建立 PR，远端 CI 未执行。

保留的自动化证据：原生视觉第一轮 `visual-tests-r1` 通过 22 项测试（12 XCTest + 10 Swift Testing）；其后的搜索提交、布局调整均重新编译，最终归档成功。独立静态 R7/R8 未留下具体 finding。这些结果不代替真实屏幕与交互验收；独立 P6 检查使用同一 `5ab02fd65` Debug binary，已覆盖专用 iPhone 14（390）及 iPhone 14 Pro Max（430）模拟器。普通和大字体独立视觉已限定通过，见 acceptance-visual-r3；`051abdcf8` 仅新增清空搜索刷新，已做独立窄复验。旧产物和截图仅对应其记录的 revision。

专用 Bot 已通过本次独占的原生添加、保留/替换密钥、连接、停用与删除旅程，见 `M1-native-app/acceptance-r4.md`；R18进一步补齐重连、真实节点离线最后已知状态、离线待删除到恢复确认的分支，未触发的停止异常和权限受限范围仍保留。Mini现已可达且官方AltServer1.8已安装运行，见[Mini准备记录](mini-altserver-readiness.md)。仍待其余精确验收分支、iPhone时段/配对/免费签名与同网续签。用户已明确真机准备后置到有可安装版本后；Gate 2 R2 已通过，此时序不降低最终验收标准。

HTTPS接入实际预验见[R19失败](../M1-native-app/acceptance-r19.md)及[R20闭环](../M1-native-app/acceptance-r20.md)。本次独占Tailscale Foreground HTTPS19443、标准证书验证与exact IM Origin下，原生登录、新群唯一请求和真实peer完成42通过。原失败由同期日志指向本机7895代理在TLS服务器握手前关闭；临时仅追加该精确tailnet域名的Wi-Fi直连豁免后，同一原生binary直接成功，日志显示19443经utun2 ready且窗口内无7895。App/证书/ATS未改；完成后已恢复原8条豁免及Serve原baseline，本次入口已关闭。此为本机Simulator证据，不代替iPhone接入和免费签名。

`ba202f5d3` 的IM/Gateway空cadence指纹修复经过50项相关Python测试；同时包含前轮live读取保留heartbeat_json修复。当前只载入本次隔离服务，未部署生产。原生产品R5已完成心跳值保存/重开、空配置再保存和真实版本冲突反馈的窄复验；其它旅程继续记录在 acceptance-r5，不能用这些构建/测试代替全部S1–S30。
