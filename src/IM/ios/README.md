# Nano IM for iOS

原生 SwiftUI 客户端，最低 iOS 26。聊天、任务图、Agent 管理/Work 和“我的”复用 IM 的现有 HTTPS API；不嵌入网页，不启动本地 Agent 内核。

## 构建

需要完整 Xcode 26.4.1 或更高兼容版本及 iOS 平台组件。项目固定使用 `swift-markdown` 0.8.0，依赖版本记录在项目内 `Package.resolved`。

```bash
./src/IM/ios/scripts/build.sh build
```

脚本默认使用 `/Applications/Xcode.app/Contents/Developer`，可以通过 `DEVELOPER_DIR` 指向其他完整 Xcode。产物默认放在 `/tmp/nano-ios-build`；可用 `NANO_IOS_BUILD_ROOT` 更改，不向仓库写 DerivedData。

打开 `NanoIM.xcodeproj`，选择 NanoIM scheme 和已安装的 iPhone 模拟器即可运行。Debug 允许显式配置 loopback HTTP 开发服务；可在 scheme 的 Run environment 设置 `NANO_IM_BASE_URL=http://127.0.0.1:<隔离IM端口>`，或在登录页输入。正式 Release 只接受 HTTPS origin，不含路径。

模拟器测试：

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available
NANO_IOS_SIMULATOR_ID=<设备UDID> ./src/IM/ios/scripts/build.sh test
```

## 设备产物

```bash
./src/IM/ios/scripts/build.sh archive
```

输出 `NanoIM.xcarchive` 和 `NanoIM-unsigned.ipa`。未签名 IPA 供 AltStore Classic 重新签名，不能直接当作已安装验证。Xcode 真机调试需在 Signing & Capabilities 选择自己的 Personal Team；不要提交账户、证书或本机签名设置。

免费签名的续签和到期时间应以 AltStore 实际记录为准。该版本不使用 APNs，后台或关闭时不承诺新消息提醒；回前台重新同步。

## 代码与验证边界

- `Client/`：Keychain、token 刷新、请求取消和同源限制、WebSocket ticket/resume。
- `Features/`：四个入口及原生详情/表单，真实服务返回驱动界面。
- `UI/`：原生 Markdown、受保护媒体、Quick Look 和系统分享。
- `Tests/`：会话轮换/退出竞态、消息合并、管理请求与返回模型契约。

真实服务必须按仓库 [worktree runtime](../../../docs/development/worktree-runtime.md) 隔离。模拟器 UI 与 API 验证不代替真机的输入、文件分享、免费签名和 Mini 自动续签验收。实施范围与证据见 [feat-578](../../../docs/changes/feat-578-ios-app/spec.md)。
